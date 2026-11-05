from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..activity import history, iso, log
from ..auth import ASSIGNS_CREWS, CREATES_JOBS, EDITS_JOBS, SEES_DOLLARS, current_user, require_roles
from ..costing import job_costing
from ..materials import material_actual_cost
from ..db import get_db
from ..models import CostLine, Job, JobCrew, JobReport, JobStatus, JobTask, Role, TaskType, TimeEntry, User, utcnow
from ..schemas import JobCosting, JobEditOut, JobIn, JobOut, JobStatusIn, JobUpdate, TaskOutWithTime

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def load_job(db: Session, user: User, job_id: str) -> Job:
    """Fetch a job only if it belongs to the user's company. 404 otherwise,
    so ids from other tenants can't even be confirmed to exist."""
    job = db.scalar(
        select(Job)
        .where(Job.id == job_id, Job.company_id == user.company_id)
        .options(*JOB_LOAD)
    )
    if job is None or not _sees(job, user):
        raise HTTPException(404, "Job not found")
    return job


JOB_LOAD = (selectinload(Job.tasks), selectinload(Job.cost_lines), selectinload(Job.crew_lead),
            selectinload(Job.crew).selectinload(JobCrew.user))


def _sees(job: Job, user: User) -> bool:
    """A crew lead sees the jobs sent to them, and nothing else."""
    return user.role != Role.crew_lead or job.crew_lead_id == user.id


def _open_problems(db: Session, company_id: str, job_ids: list[str]) -> dict[str, int]:
    if not job_ids:
        return {}
    rows = db.execute(select(JobReport.job_id, func.count()).where(
        JobReport.company_id == company_id, JobReport.job_id.in_(job_ids), JobReport.kind == "problem",
        JobReport.resolved_at.is_(None)).group_by(JobReport.job_id))
    return dict(rows.all())


def field_info(job: Job, problems: int = 0) -> dict:
    return {"crew_lead_id": job.crew_lead_id, "crew_lead_name": job.crew_lead.name if job.crew_lead else None,
            "crew_members": sorted(({"id": c.user_id, "name": c.user.name} for c in job.crew), key=lambda x: x["name"]),
            "start_date": job.start_date, "started_at": job.started_at, "site_walk_at": job.site_walk_at,
            "scope_text": job.scope_text or "", "open_problems": problems}


def _serialize(job: Job, user: User, problems: int = 0) -> JobOut:
    out = JobOut.model_validate(job).model_copy(update=field_info(job, problems))
    if user.role not in SEES_DOLLARS:
        out.contract_amount = None
        out.estimated_labor_rate = None
        out.sales_tax_pct = None
        out.cost_lines = None
        for t in out.tasks:  # crews see the work and the hours, never the money
            t.cost_rate = t.charge_rate = t.sub_price = t.unit_price = None
            t.sub_quote_link = ""
    return out


def check_task_refs(db: Session, tasks, company_id: str) -> None:
    """Subs and library entries named on tasks must belong to this company."""
    from ..models import Subcontractor, TaskTemplate
    for model, ids in ((Subcontractor, {t.sub_id for t in tasks if t.sub_id}), (TaskTemplate, {t.template_id for t in tasks if t.template_id})):
        if ids:
            found = set(db.scalars(select(model.id).where(model.id.in_(ids), model.company_id == company_id)))
            if ids - found:
                raise HTTPException(422, "A task points at a sub or library entry that doesn't exist")


def task_fields(t) -> dict:
    """What gets stored for a task. Sub tasks have no crew hours."""
    from ..models import TaskKind
    # markups, court links, sizes and all-in pricing live on the estimate
    f = t.model_dump(exclude={"id", "sort_order", "markup_pct", "follows", "checklist_note", "all_in",
                              "size_length_ft", "size_width_ft", "size_depth_in", "tons_per_cy"})
    if t.kind == TaskKind.sub:
        f["estimated_hours"] = 0.0
        f.update(unit="hr", quantity=None, coats=None, production_rate=None, unit_price=None, crew_size=None)
    else:
        f["sub_id"], f["sub_price"], f["sub_quote_link"] = None, None, ""
    return f


def _check_items(db: Session, lines, company_id: str) -> None:
    from ..models import StockItem
    ids = {ln.item_id for ln in lines if ln.item_id}
    if ids:
        found = set(db.scalars(select(StockItem.id).where(StockItem.id.in_(ids), StockItem.company_id == company_id)))
        if ids - found:
            raise HTTPException(422, "A cost line points at a price-list item that doesn't exist")


def _apply_cost_lines(job: Job, lines, tasks_in_order: list[JobTask], company_id: str) -> None:
    """Replace the job's cost lines with `lines`, keeping ids for lines sent
    back with one. task_index points into this save's task list."""
    existing = {c.id: c for c in job.cost_lines}
    sent = {ln.id for ln in lines if ln.id}
    if sent - set(existing):
        raise HTTPException(422, "A cost line in this save doesn't belong to this job")
    for cid in set(existing) - sent:
        job.cost_lines.remove(existing[cid])
    for order, ln in enumerate(lines):
        if ln.task_index is not None and ln.task_index >= len(tasks_in_order):
            raise HTTPException(422, f"Cost line {order + 1} points at a task that isn't in the job")
        task = tasks_in_order[ln.task_index] if ln.task_index is not None else None
        fields = dict(category=ln.category, description=ln.description.strip(), quantity=ln.quantity,
                      unit=ln.unit.strip(), unit_cost=ln.unit_cost, sort_order=order, task_id=task.id if task else None,
                      item_id=ln.item_id, in_house=ln.in_house)
        if ln.id:
            for k, v in fields.items():
                setattr(existing[ln.id], k, v)
        else:
            job.cost_lines.append(CostLine(company_id=company_id, **fields))


def _entries(db: Session, job: Job) -> list[TimeEntry]:
    return list(
        db.scalars(
            select(TimeEntry)
            .where(TimeEntry.job_id == job.id, TimeEntry.company_id == job.company_id, TimeEntry.voided_at.is_(None))
            .options(selectinload(TimeEntry.worker))
        )
    )


@router.get("", response_model=list[JobOut], response_model_exclude_none=True)
def list_jobs(status: JobStatus | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Job).where(Job.company_id == user.company_id).options(*JOB_LOAD).order_by(Job.created_at.desc())
    if status:
        q = q.where(Job.status == status)
    elif user.role in (Role.crew_lead, Role.warehouse):
        q = q.where(Job.status != JobStatus.complete)  # crews only need open work
    if user.role == Role.crew_lead:
        q = q.where(Job.crew_lead_id == user.id)  # only the jobs sent to them
    jobs = list(db.scalars(q))
    probs = _open_problems(db, user.company_id, [j.id for j in jobs])
    return [_serialize(j, user, probs.get(j.id, 0)) for j in jobs]


@router.post("", status_code=201, response_model=JobOut)
def create_job(body: JobIn, user: User = Depends(require_roles(*CREATES_JOBS)), db: Session = Depends(get_db)):
    """A job with no estimate behind it (a callback, a small patch). GM only;
    everything else starts as an estimate and becomes a job when it's won."""
    job = build_job(db, user, body)
    db.commit()
    return JobOut.model_validate(load_job(db, user, job.id))


def build_job(db: Session, user: User, body: JobIn, client_id: str | None = None) -> Job:
    """Add a job with its tasks and cost lines. The caller commits."""
    data = body.model_dump(exclude={"tasks", "cost_lines"})
    if user.role != Role.gm:
        data["status"] = JobStatus.scheduled  # only the GM starts or closes jobs
    job = Job(company_id=user.company_id, client_id=client_id, **data)
    check_task_refs(db, body.tasks, user.company_id)
    for i, t in enumerate(body.tasks):
        job.tasks.append(JobTask(company_id=user.company_id, sort_order=i, **task_fields(t)))
    db.add(job)
    db.flush()  # task ids for cost lines
    _check_items(db, body.cost_lines, user.company_id)
    _apply_cost_lines(job, body.cost_lines, list(job.tasks), user.company_id)
    db.flush()
    return job


@router.get("/summary", response_model=list[JobCosting])
def jobs_summary(user: User = Depends(require_roles(*SEES_DOLLARS)), db: Session = Depends(get_db)):
    """Estimate vs. actual for every job, for the management dashboard."""
    jobs = list(db.scalars(
        select(Job).where(Job.company_id == user.company_id).options(*JOB_LOAD).order_by(Job.created_at.desc())
    ))
    probs = _open_problems(db, user.company_id, [j.id for j in jobs])
    return [job_costing(j, _entries(db, j), with_dollars=True) | {"materials_actual_cost": material_actual_cost(db, j)}
            | field_info(j, probs.get(j.id, 0)) for j in jobs]


@router.get("/{job_id}", response_model=JobOut, response_model_exclude_none=True)
def get_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = load_job(db, user, job_id)
    return _serialize(job, user, _open_problems(db, user.company_id, [job.id]).get(job.id, 0))


def _tasks_with_time(db: Session, job: Job) -> set[str]:
    rows = db.execute(
        select(TimeEntry.task_id, func.count()).where(TimeEntry.job_id == job.id).group_by(TimeEntry.task_id)
    )
    return {task_id for task_id, n in rows if n}


def _edit_view(db: Session, job: Job) -> JobEditOut:
    used = _tasks_with_time(db, job)
    out = JobEditOut.model_validate(job, from_attributes=True)
    out.tasks = [TaskOutWithTime.model_validate(t).model_copy(update={"has_time": t.id in used}) for t in job.tasks]
    return out


@router.get("/{job_id}/edit", response_model=JobEditOut)
def get_for_edit(job_id: str, user: User = Depends(require_roles(*EDITS_JOBS)), db: Session = Depends(get_db)):
    return _edit_view(db, load_job(db, user, job_id))


@router.put("/{job_id}", response_model=JobEditOut)
def update_job(job_id: str, body: JobUpdate, user: User = Depends(require_roles(*EDITS_JOBS)), db: Session = Depends(get_db)):
    """Replace the job's details and its task list in one save.

    Tasks sent with an id are updated; tasks without one are added; existing
    tasks left out are removed, unless crew time is already logged against
    them (that would orphan real hours), in which case nothing is saved.
    """
    job = load_job(db, user, job_id)
    existing = {t.id: t for t in job.tasks}

    sent_ids = [t.id for t in body.tasks if t.id]
    unknown = [i for i in sent_ids if i not in existing]
    if unknown or len(sent_ids) != len(set(sent_ids)):
        raise HTTPException(422, "A task in this save doesn't belong to this job")

    removed = set(existing) - set(sent_ids)
    blocked = removed & _tasks_with_time(db, job)
    if blocked:
        names = ", ".join(sorted(existing[i].name for i in blocked))
        raise HTTPException(409, f"Crew time is logged on {names}, so it can't be removed. Set its hours instead.")

    check_task_refs(db, body.tasks, user.company_id)
    for k, v in body.model_dump(exclude={"tasks", "status", "cost_lines"}).items():
        setattr(job, k, v)
    for i in removed:
        for line in job.cost_lines:
            if line.task_id == i:
                line.task_id = None
        job.tasks.remove(existing[i])
    in_order: list[JobTask] = []
    for order, t in enumerate(body.tasks):
        fields = task_fields(t)
        if t.id:
            for k, v in fields.items():
                setattr(existing[t.id], k, v)
            existing[t.id].sort_order = order
            in_order.append(existing[t.id])
        else:
            nt = JobTask(company_id=user.company_id, sort_order=order, **fields)
            job.tasks.append(nt)
            in_order.append(nt)
    db.flush()  # ids for new tasks
    if body.cost_lines is not None:
        _check_items(db, body.cost_lines, user.company_id)
        _apply_cost_lines(job, body.cost_lines, in_order, user.company_id)
    db.commit()
    db.expire(job)  # reload tasks in their new order
    return _edit_view(db, load_job(db, user, job.id))


@router.patch("/{job_id}/status", response_model=JobOut)
def set_status(job_id: str, body: JobStatusIn, user: User = Depends(require_roles(Role.gm)), db: Session = Depends(get_db)):
    job = load_job(db, user, job_id)
    job.status = body.status
    db.commit()
    return JobOut.model_validate(job)


@router.get("/{job_id}/costing", response_model=JobCosting, response_model_exclude_none=True)
def get_costing(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role in (Role.crew, Role.warehouse):
        raise HTTPException(403, "Your role can't do that")
    job = load_job(db, user, job_id)
    out = job_costing(job, _entries(db, job), with_dollars=user.role in SEES_DOLLARS)
    if user.role in SEES_DOLLARS:
        out["materials_actual_cost"] = material_actual_cost(db, job)
    return out | field_info(job, _open_problems(db, user.company_id, [job.id]).get(job.id, 0))


# ---------- out to the field ----------

class CrewIn(BaseModel):
    crew_lead_id: str | None = None
    crew_ids: list[str] = Field(default=[], max_length=50)
    start_date: date | None = None


def assign_crew(db: Session, user: User, job: Job, body: CrewIn) -> None:
    """Set who runs the job, who's on it and when it starts. The caller commits."""
    from .time import FIELD_ROLES
    people = {u.id: u for u in db.scalars(select(User).where(
        User.company_id == user.company_id, User.active.is_(True), User.id.in_({body.crew_lead_id, *body.crew_ids} - {None})))}
    if body.crew_lead_id and (body.crew_lead_id not in people or people[body.crew_lead_id].role != Role.crew_lead):
        raise HTTPException(422, "Pick a crew lead from the team")
    ids = [i for i in dict.fromkeys(body.crew_ids) if i != body.crew_lead_id]
    if any(i not in people or people[i].role not in FIELD_ROLES for i in ids):
        raise HTTPException(422, "Everyone on the crew has to be on the team as crew or a crew lead")
    before = (job.crew_lead.name if job.crew_lead else None, sorted(c.user.name for c in job.crew), job.start_date)
    job.crew_lead_id, job.start_date = body.crew_lead_id, body.start_date
    job.crew_lead = people.get(body.crew_lead_id)
    job.crew.clear()
    db.flush()
    for i in ids:
        job.crew.append(JobCrew(company_id=user.company_id, user_id=i, user=people[i]))
    after = (people[body.crew_lead_id].name if body.crew_lead_id else None, sorted(people[i].name for i in ids), body.start_date)
    if before != after:
        what = []
        if before[0] != after[0]:
            what.append(f"Crew lead: {before[0] or '—'} → {after[0] or '—'}")
        if before[1] != after[1]:
            what.append(f"Crew: {', '.join(after[1]) or 'nobody else'}")
        if before[2] != after[2]:
            what.append(f"Start: {before[2].isoformat() if before[2] else '—'} → {after[2].isoformat() if after[2] else '—'}")
        log(db, user, "job", job.id, "Sent to the field" if before[0] is None and after[0] else "Changed the crew or start date", "; ".join(what))


@router.put("/{job_id}/crew", response_model=JobOut, response_model_exclude_none=True)
def set_crew(job_id: str, body: CrewIn, user: User = Depends(require_roles(*ASSIGNS_CREWS)), db: Session = Depends(get_db)):
    job = load_job(db, user, job_id)
    assign_crew(db, user, job, body)
    db.commit()
    db.expire(job)
    return get_job(job_id, user, db)


class StartIn(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


SETUP_TASK = "Site walk and setup"


@router.post("/{job_id}/start", response_model=JobOut, response_model_exclude_none=True)
def start_on_site(job_id: str, body: StartIn, user: User = Depends(require_roles(Role.crew_lead, Role.gm)), db: Session = Depends(get_db)):
    """The crew is on site: the site pin (if there isn't one) is set where the
    crew lead stands, the job is in progress, and there's a "Site walk and
    setup" task for the crew to be on the clock for while they look it over."""
    job = load_job(db, user, job_id)
    if job.status == JobStatus.complete:
        raise HTTPException(409, "This job is complete.")
    if job.lat is None and body.lat is not None and body.lng is not None:
        job.lat, job.lng = round(body.lat, 6), round(body.lng, 6)
        log(db, user, "job", job.id, "Set the site pin on site")
    if job.started_at is None:
        job.started_at = utcnow()
        log(db, user, "job", job.id, "On site, crew clocked in")
    if not any(t.name == SETUP_TASK for t in job.tasks):
        job.tasks.insert(0, JobTask(company_id=user.company_id, task_type=TaskType.prep, name=SETUP_TASK, estimated_hours=0,
                                    sort_order=-1))
    job.status = JobStatus.active
    db.commit()
    db.expire(job)
    return get_job(job_id, user, db)


@router.post("/{job_id}/walked", response_model=JobOut, response_model_exclude_none=True)
def site_walked(job_id: str, user: User = Depends(require_roles(Role.crew_lead, Role.gm)), db: Session = Depends(get_db)):
    job = load_job(db, user, job_id)
    if job.site_walk_at is None:
        job.site_walk_at = utcnow()
        log(db, user, "job", job.id, "Walked the site")
        db.commit()
    return get_job(job_id, user, db)


class ProgressIn(BaseModel):
    pct: int = Field(ge=0, le=100)  # 100 = done, 0 = not started (clears it)
    note: str = Field(default="", max_length=2000)


@router.post("/{job_id}/tasks/{task_id}/progress", response_model=JobOut, response_model_exclude_none=True)
def task_progress(job_id: str, task_id: str, body: ProgressIn, user: User = Depends(require_roles(Role.crew_lead, *ASSIGNS_CREWS)),
                  db: Session = Depends(get_db)):
    """The crew lead says how far along a task is (50%, 100%…), with a note
    and photos. Hours come from the clock, not from this."""
    job = load_job(db, user, job_id)
    t = next((x for x in job.tasks if x.id == task_id), None)
    if t is None:
        raise HTTPException(404, "Task not found")
    t.progress = "done" if body.pct == 100 else "partial" if body.pct > 0 else ""
    t.progress_pct = body.pct or None
    t.progress_note = body.note.strip()
    t.progress_at, t.progress_by_id = utcnow(), user.id
    word = "done" if body.pct == 100 else f"{body.pct}% done" if body.pct else "not started (cleared)"
    log(db, user, "job", job.id, f"Marked {t.name} {word}", body.note.strip())
    db.commit()
    return get_job(job_id, user, db)


class ReportIn(BaseModel):
    kind: str = Field(default="problem", pattern="^(problem|note)$")
    text: str = Field(min_length=3, max_length=5000)


class ResolveIn(BaseModel):
    resolution: str = Field(min_length=3, max_length=2000)


def report_out(r: JobReport) -> dict:
    return {"id": r.id, "kind": r.kind, "text": r.text, "by": r.created_by.name, "at": iso(r.created_at),
            "resolved_at": iso(r.resolved_at), "resolved_by": r.resolved_by.name if r.resolved_by else None, "resolution": r.resolution}


@router.get("/{job_id}/reports")
def list_reports(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """What the crew found on site, and the job's history."""
    if user.role in (Role.crew, Role.warehouse, Role.sales):
        raise HTTPException(403, "Your role can't do that")
    job = load_job(db, user, job_id)
    rows = db.scalars(select(JobReport).where(JobReport.job_id == job.id, JobReport.company_id == user.company_id)
                      .order_by(JobReport.created_at.desc()))
    return {"reports": [report_out(r) for r in rows],
            "activity": history(db, user.company_id, "job", job.id) if user.role != Role.crew_lead else []}


@router.post("/{job_id}/reports", status_code=201)
def add_report(job_id: str, body: ReportIn, user: User = Depends(require_roles(Role.crew_lead, *EDITS_JOBS)), db: Session = Depends(get_db)):
    job = load_job(db, user, job_id)
    r = JobReport(company_id=user.company_id, job_id=job.id, kind=body.kind, text=body.text.strip(), created_by_id=user.id)
    db.add(r)
    db.flush()
    log(db, user, "job", job.id, "Reported a problem on site" if body.kind == "problem" else "Added a site note", body.text.strip()[:300])
    db.commit()
    db.refresh(r)
    return report_out(r)


@router.post("/{job_id}/reports/{report_id}/resolve")
def resolve_report(job_id: str, report_id: str, body: ResolveIn, user: User = Depends(require_roles(*ASSIGNS_CREWS)),
                   db: Session = Depends(get_db)):
    job = load_job(db, user, job_id)
    r = db.scalar(select(JobReport).where(JobReport.id == report_id, JobReport.job_id == job.id))
    if r is None:
        raise HTTPException(404, "Report not found")
    if r.resolved_at is None:
        r.resolved_at, r.resolved_by_id, r.resolution = utcnow(), user.id, body.resolution.strip()
        log(db, user, "job", job.id, "Handled a problem from the site", body.resolution.strip()[:300])
        db.commit()
        db.refresh(r)
    return report_out(r)
