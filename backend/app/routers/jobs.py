from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import EDITS_JOBS, SEES_DOLLARS, current_user, require_roles
from ..costing import job_costing
from ..db import get_db
from ..models import Job, JobStatus, JobTask, Role, TimeEntry, User
from ..schemas import JobCosting, JobIn, JobOut, JobStatusIn

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
    job = Job(company_id=user.company_id, **data)
    for i, t in enumerate(body.tasks):
        job.tasks.append(JobTask(company_id=user.company_id, sort_order=t.sort_order or i, **t.model_dump(exclude={"sort_order"})))
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
