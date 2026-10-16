"""Field time: crew list, offline-friendly sync, entry listing, and office
corrections (add, fix, remove) with an audit trail."""
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..auth import ENTERS_TIME, SEES_DOLLARS, current_user, require_roles
from ..costing import entry_hours, is_off_site
from ..db import get_db
from ..models import Job, JobTask, Role, TimeEntry, TimeEntryChange, User, new_id, utcnow
from ..schemas import (
    OfficeTimeEdit, OfficeTimeIn, RemoveIn, SyncIn, SyncOut, SyncResult, TimeChangeOut,
    TimeEntryIn, TimeEntryOut, UserOut, to_naive_utc,
)

router = APIRouter(prefix="/api", tags=["time"])

MAX_SHIFT = timedelta(hours=16)
FUTURE_SLACK = timedelta(minutes=10)  # phone clocks drift
FIELD_ROLES = (Role.crew, Role.crew_lead)
_COMPARED = ("job_id", "task_id", "worker_id", "clock_in", "clock_out",
             "in_lat", "in_lng", "out_lat", "out_lng", "note")
# Who corrects time from the office. Kept to the GM so there is one owner of payroll hours.
CORRECTS_TIME = (Role.gm,)


@router.get("/crew", response_model=list[UserOut])
def list_crew(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(User).where(User.company_id == user.company_id, User.active, User.role.in_(FIELD_ROLES)).order_by(User.name)
    return list(db.scalars(q))


def _validate(db: Session, company_id: str, e: TimeEntryIn) -> str | None:
    """Return a rejection reason, or None if the entry is acceptable."""
    job = db.get(Job, e.job_id)
    if job is None or job.company_id != company_id:
        return "unknown job"
    task = db.get(JobTask, e.task_id)
    if task is None or task.job_id != job.id:
        return "task does not belong to this job"
    worker = db.get(User, e.worker_id)
    if worker is None or worker.company_id != company_id or worker.role not in FIELD_ROLES:
        return "unknown crew member"
    now = utcnow()
    if e.clock_in > now + FUTURE_SLACK:
        return "clock-in is in the future"
    if e.clock_out is not None:
        if e.clock_out < e.clock_in:
            return "clock-out is before clock-in"
        if e.clock_out > now + FUTURE_SLACK:
            return "clock-out is in the future"
        if e.clock_out - e.clock_in > MAX_SHIFT:
            return "entry is longer than 16 hours"
    elif now - e.clock_in > MAX_SHIFT:
        return "open entry is older than 16 hours; clock it out with the real time"

    # The same worker can't be on two tasks at once. Removed entries don't count.
    end = e.clock_out or datetime.max
    overlap = db.scalar(
        select(TimeEntry.id).where(
            TimeEntry.worker_id == e.worker_id,
            TimeEntry.id != e.id,
            TimeEntry.voided_at.is_(None),
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
    Entries the office has corrected keep the office's values; the phone can
    still close them. Entries the office removed are rejected.
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
            if existing.voided_at is not None:
                results.append(SyncResult(id=e.id, status="rejected", reason="the office removed this entry"))
                continue
            if all(getattr(existing, f) == getattr(e, f) for f in _COMPARED):
                results.append(SyncResult(id=e.id, status="unchanged"))
                continue
            if existing.office_edited:
                # Phone may only close an entry the office left open.
                if existing.clock_out is not None or e.clock_out is None:
                    results.append(SyncResult(id=e.id, status="stale", reason="the office corrected this entry"))
                    continue
                e = e.model_copy(update={f: getattr(existing, f) for f in
                                         ("job_id", "task_id", "worker_id", "clock_in", "in_lat", "in_lng", "note")})
            elif existing.client_updated_at > e.client_updated_at:
                results.append(SyncResult(id=e.id, status="stale", reason="server has a newer edit"))
                continue

        reason = _validate(db, user.company_id, e)
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


def _out(e: TimeEntry, job: Job, edited: bool) -> TimeEntryOut:
    return TimeEntryOut(
        id=e.id, job_id=e.job_id, task_id=e.task_id, worker_id=e.worker_id,
        worker_name=e.worker.name, task_name=e.task.name, entered_by_id=e.entered_by_id,
        clock_in=e.clock_in, clock_out=e.clock_out,
        hours=round(entry_hours(e), 2) if e.clock_out else None,
        off_site=is_off_site(e, job), note=e.note,
        in_lat=e.in_lat, in_lng=e.in_lng, out_lat=e.out_lat, out_lng=e.out_lng,
        client_updated_at=e.client_updated_at,
        edited=edited, removed=e.voided_at is not None, removed_reason=e.void_reason,
    )


@router.get("/time", response_model=list[TimeEntryOut])
def list_time(
    job_id: str | None = None,
    open_only: bool = False,
    include_removed: bool = False,
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
    if not include_removed or open_only:
        q = q.where(TimeEntry.voided_at.is_(None))
    if since:
        q = q.where(or_(TimeEntry.clock_in >= to_naive_utc(since), TimeEntry.clock_out.is_(None)))
    rows = list(db.scalars(q))
    edited = set(db.scalars(
        select(TimeEntryChange.entry_id).where(
            TimeEntryChange.entry_id.in_([e.id for e in rows]), TimeEntryChange.action != "add")
    ))
    jobs: dict[str, Job] = {}
    out = []
    for e in rows:
        job = jobs.get(e.job_id) or jobs.setdefault(e.job_id, db.get(Job, e.job_id))
        out.append(_out(e, job, e.id in edited))
    return out


# ---------- office corrections ----------

def _snapshot(e: TimeEntry) -> str:
    return json.dumps({
        "job_id": e.job_id, "task_id": e.task_id, "task": e.task.name if e.task else None,
        "worker_id": e.worker_id, "worker": e.worker.name if e.worker else None,
        "clock_in": e.clock_in.isoformat() + "Z", "clock_out": e.clock_out.isoformat() + "Z" if e.clock_out else None,
    })


def _record(db: Session, user: User, e: TimeEntry, action: str, reason: str, before: str = "") -> None:
    db.flush()
    db.refresh(e)
    db.add(TimeEntryChange(company_id=user.company_id, entry_id=e.id, changed_by_id=user.id,
                           action=action, reason=reason.strip(), before=before,
                           after="" if action == "remove" else _snapshot(e)))


def _load_entry(db: Session, user: User, entry_id: str) -> TimeEntry:
    e = db.get(TimeEntry, entry_id)
    if e is None or e.company_id != user.company_id:
        raise HTTPException(404, "Time entry not found")
    return e


@router.post("/time/office", response_model=TimeEntryOut, status_code=201)
def add_office_time(body: OfficeTimeIn, user: User = Depends(require_roles(*CORRECTS_TIME)), db: Session = Depends(get_db)):
    now = utcnow()
    candidate = TimeEntryIn(id=new_id(), client_updated_at=now, **body.model_dump(exclude={"reason"}))
    reason = _validate(db, user.company_id, candidate)
    if reason:
        raise HTTPException(422, f"Can't add this time: {reason}.")
    e = TimeEntry(company_id=user.company_id, entered_by_id=user.id, office_edited=True,
                  **candidate.model_dump())
    db.add(e)
    _record(db, user, e, "add", body.reason)
    db.commit()
    return _out(e, db.get(Job, e.job_id), False)


@router.patch("/time/{entry_id}", response_model=TimeEntryOut)
def edit_office_time(entry_id: str, body: OfficeTimeEdit, user: User = Depends(require_roles(*CORRECTS_TIME)),
                     db: Session = Depends(get_db)):
    e = _load_entry(db, user, entry_id)
    if e.voided_at is not None:
        raise HTTPException(409, "This entry was removed. Add new time instead.")
    before = _snapshot(e)
    changes = {k: getattr(body, k) for k in body.model_fields_set if k != "reason"}
    if not changes:
        raise HTTPException(422, "Nothing to change")
    candidate = TimeEntryIn(
        id=e.id, job_id=e.job_id,
        task_id=changes.get("task_id", e.task_id), worker_id=changes.get("worker_id", e.worker_id),
        clock_in=changes.get("clock_in", e.clock_in), clock_out=changes["clock_out"] if "clock_out" in changes else e.clock_out,
        client_updated_at=utcnow(),
    )
    reason = _validate(db, user.company_id, candidate)
    if reason:
        raise HTTPException(422, f"Can't save this change: {reason}.")
    for k in ("task_id", "worker_id", "clock_in", "clock_out", "client_updated_at"):
        setattr(e, k, getattr(candidate, k))
    e.office_edited = True
    _record(db, user, e, "edit", body.reason, before)
    db.commit()
    return _out(e, db.get(Job, e.job_id), True)


@router.post("/time/{entry_id}/remove", response_model=TimeEntryOut)
def remove_office_time(entry_id: str, body: RemoveIn, user: User = Depends(require_roles(*CORRECTS_TIME)),
                       db: Session = Depends(get_db)):
    e = _load_entry(db, user, entry_id)
    if e.voided_at is not None:
        raise HTTPException(409, "This entry was already removed")
    before = _snapshot(e)
    e.voided_at, e.voided_by_id, e.void_reason = utcnow(), user.id, body.reason.strip()
    e.office_edited = True
    _record(db, user, e, "remove", body.reason, before)
    db.commit()
    return _out(e, db.get(Job, e.job_id), True)


@router.get("/time/{entry_id}/history", response_model=list[TimeChangeOut])
def entry_history(entry_id: str, user: User = Depends(require_roles(*SEES_DOLLARS)), db: Session = Depends(get_db)):
    _load_entry(db, user, entry_id)
    rows = db.scalars(
        select(TimeEntryChange).where(TimeEntryChange.entry_id == entry_id)
        .options(selectinload(TimeEntryChange.changed_by)).order_by(TimeEntryChange.changed_at)
    )
    return [
        TimeChangeOut(action=c.action, reason=c.reason, changed_by=c.changed_by.name, changed_at=c.changed_at,
                      before=json.loads(c.before) if c.before else None, after=json.loads(c.after) if c.after else None)
        for c in rows
    ]
