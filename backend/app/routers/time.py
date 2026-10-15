"""Field time: crew list, offline-friendly sync, and entry listing."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..auth import ENTERS_TIME, current_user, require_roles
from ..costing import entry_hours, is_off_site
from ..db import get_db
from ..models import Job, JobTask, Role, TimeEntry, User, utcnow
from ..schemas import SyncIn, SyncOut, SyncResult, TimeEntryIn, TimeEntryOut, UserOut, to_naive_utc

router = APIRouter(prefix="/api", tags=["time"])

MAX_SHIFT = timedelta(hours=16)
FUTURE_SLACK = timedelta(minutes=10)  # phone clocks drift
FIELD_ROLES = (Role.crew, Role.crew_lead)
_COMPARED = ("job_id", "task_id", "worker_id", "clock_in", "clock_out",
             "in_lat", "in_lng", "out_lat", "out_lng", "note")


@router.get("/crew", response_model=list[UserOut])
def list_crew(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(User).where(User.company_id == user.company_id, User.active, User.role.in_(FIELD_ROLES)).order_by(User.name)
    return list(db.scalars(q))


def _validate(db: Session, user: User, e: TimeEntryIn) -> str | None:
    """Return a rejection reason, or None if the entry is acceptable."""
    job = db.get(Job, e.job_id)
    if job is None or job.company_id != user.company_id:
        return "unknown job"
    task = db.get(JobTask, e.task_id)
    if task is None or task.job_id != job.id:
        return "task does not belong to this job"
    worker = db.get(User, e.worker_id)
    if worker is None or worker.company_id != user.company_id or worker.role not in FIELD_ROLES:
        return "unknown crew member"
    now = utcnow()
    if e.clock_in > now + FUTURE_SLACK:
        return "clock-in is in the future"
    if e.clock_out is not None:
        if e.clock_out < e.clock_in:
            return "clock-out is before clock-in"
        if e.clock_out - e.clock_in > MAX_SHIFT:
            return "entry is longer than 16 hours"
    elif now - e.clock_in > MAX_SHIFT:
        return "open entry is older than 16 hours; clock it out with the real time"

    # The same worker can't be on two tasks at once.
    end = e.clock_out or datetime.max
    overlap = db.scalar(
        select(TimeEntry.id).where(
            TimeEntry.worker_id == e.worker_id,
            TimeEntry.id != e.id,
            TimeEntry.clock_in < end,
            or_(TimeEntry.clock_out.is_(None), TimeEntry.clock_out > e.clock_in),
        )
    )
    if overlap:
        return f"overlaps another entry for {worker.name}"
    return None


@router.post("/time/sync", response_model=SyncOut)
def sync_time(body: SyncIn, user: User = Depends(require_roles(*ENTERS_TIME)), db: Session = Depends(get_db)):
    """Upsert time entries sent from the field app.

    Safe to resend: an entry the server already has is reported as
    "unchanged". If the server holds a newer edit of the same entry, the
    incoming one is "stale" and ignored (last write wins by device time).
    Entries are applied oldest-change first so a clock-out on one task lands
    before the clock-in on the next.
    """
    results: list[SyncResult] = []
    for e in sorted(body.entries, key=lambda x: x.client_updated_at):
        existing = db.get(TimeEntry, e.id)
        if existing is not None:
            if existing.company_id != user.company_id:
                results.append(SyncResult(id=e.id, status="rejected", reason="id already in use"))
                continue
            if all(getattr(existing, f) == getattr(e, f) for f in _COMPARED):
                results.append(SyncResult(id=e.id, status="unchanged"))
                continue
            if existing.client_updated_at > e.client_updated_at:
                results.append(SyncResult(id=e.id, status="stale", reason="server has a newer edit"))
                continue

        reason = _validate(db, user, e)
        if reason:
            results.append(SyncResult(id=e.id, status="rejected", reason=reason))
            continue

        fields = e.model_dump(exclude={"id"})
        if existing is None:
            db.add(TimeEntry(id=e.id, company_id=user.company_id, entered_by_id=user.id, **fields))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
            existing.synced_at = utcnow()
        db.flush()  # later entries in this batch see this one for overlap checks
        results.append(SyncResult(id=e.id, status="saved"))
    db.commit()
    return SyncOut(results=results)


@router.get("/time", response_model=list[TimeEntryOut])
def list_time(
    job_id: str | None = None,
    open_only: bool = False,
    since: datetime | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if user.role in (Role.crew, Role.warehouse):
        raise HTTPException(403, "Your role can't do that")
    q = (
        select(TimeEntry)
        .where(TimeEntry.company_id == user.company_id)
        .options(selectinload(TimeEntry.worker), selectinload(TimeEntry.task))
        .order_by(TimeEntry.clock_in.desc())
        .limit(1000)
    )
    if job_id:
        q = q.where(TimeEntry.job_id == job_id)
    if open_only:
        q = q.where(TimeEntry.clock_out.is_(None))
    if since:
        q = q.where(or_(TimeEntry.clock_in >= to_naive_utc(since), TimeEntry.clock_out.is_(None)))
    jobs: dict[str, Job] = {}
    out = []
    for e in db.scalars(q):
        job = jobs.get(e.job_id) or jobs.setdefault(e.job_id, db.get(Job, e.job_id))
        out.append(
            TimeEntryOut(
                id=e.id, job_id=e.job_id, task_id=e.task_id, worker_id=e.worker_id,
                worker_name=e.worker.name, task_name=e.task.name,
                clock_in=e.clock_in, clock_out=e.clock_out,
                hours=round(entry_hours(e), 2) if e.clock_out else None,
                off_site=is_off_site(e, job), note=e.note,
            )
        )
    return out
