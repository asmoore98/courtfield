from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..auth import EDITS_JOBS, SEES_DOLLARS, current_user, require_roles
from ..costing import job_costing
from ..db import get_db
from ..models import Job, JobStatus, JobTask, Role, TimeEntry, User
from ..schemas import JobCosting, JobEditOut, JobIn, JobOut, JobStatusIn, JobUpdate, TaskOutWithTime

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def load_job(db: Session, user: User, job_id: str) -> Job:
    """Fetch a job only if it belongs to the user's company. 404 otherwise,
    so ids from other tenants can't even be confirmed to exist."""
    job = db.scalar(
        select(Job)
        .where(Job.id == job_id, Job.company_id == user.company_id)
        .options(selectinload(Job.tasks))
    )
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


def _serialize(job: Job, user: User) -> JobOut:
    out = JobOut.model_validate(job)
    if user.role not in SEES_DOLLARS:
        out.contract_amount = None
        out.estimated_labor_rate = None
    return out


def _entries(db: Session, job: Job) -> list[TimeEntry]:
    return list(
        db.scalars(
            select(TimeEntry)
            .where(TimeEntry.job_id == job.id, TimeEntry.company_id == job.company_id)
            .options(selectinload(TimeEntry.worker))
        )
    )


@router.get("", response_model=list[JobOut], response_model_exclude_none=True)
def list_jobs(status: JobStatus | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Job).where(Job.company_id == user.company_id).options(selectinload(Job.tasks)).order_by(Job.created_at.desc())
    if status:
        q = q.where(Job.status == status)
    elif user.role == Role.crew_lead:
        q = q.where(Job.status != JobStatus.complete)  # crews only need open work
    return [_serialize(j, user) for j in db.scalars(q)]


@router.post("", status_code=201, response_model=JobOut)
def create_job(body: JobIn, user: User = Depends(require_roles(*EDITS_JOBS)), db: Session = Depends(get_db)):
    data = body.model_dump(exclude={"tasks"})
    if user.role != Role.gm:
        data["status"] = JobStatus.scheduled  # only the GM starts or closes jobs
    job = Job(company_id=user.company_id, **data)
    for i, t in enumerate(body.tasks):
        job.tasks.append(JobTask(company_id=user.company_id, sort_order=i, **t.model_dump(exclude={"id", "sort_order"})))
    db.add(job)
    db.commit()
    return JobOut.model_validate(load_job(db, user, job.id))


@router.get("/summary", response_model=list[JobCosting])
def jobs_summary(user: User = Depends(require_roles(*SEES_DOLLARS)), db: Session = Depends(get_db)):
    """Estimate vs. actual for every job, for the management dashboard."""
    jobs = db.scalars(
        select(Job).where(Job.company_id == user.company_id).options(selectinload(Job.tasks)).order_by(Job.created_at.desc())
    )
    return [job_costing(j, _entries(db, j), with_dollars=True) for j in jobs]


@router.get("/{job_id}", response_model=JobOut, response_model_exclude_none=True)
def get_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _serialize(load_job(db, user, job_id), user)


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

    for k, v in body.model_dump(exclude={"tasks", "status"}).items():
        setattr(job, k, v)
    for i in removed:
        job.tasks.remove(existing[i])
    for order, t in enumerate(body.tasks):
        fields = t.model_dump(exclude={"id", "sort_order"})
        if t.id:
            for k, v in fields.items():
                setattr(existing[t.id], k, v)
            existing[t.id].sort_order = order
        else:
            job.tasks.append(JobTask(company_id=user.company_id, sort_order=order, **fields))
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
    return job_costing(job, _entries(db, job), with_dollars=user.role in SEES_DOLLARS)
