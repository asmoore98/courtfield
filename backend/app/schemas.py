"""Request and response shapes for the API."""
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import CourtType, JobStatus, Role, ScopeType, TaskType


def to_naive_utc(value: datetime | None) -> datetime | None:
    """Store everything as naive UTC; treat naive input as already UTC."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- users ----------

class UserOut(ORM):
    id: str
    name: str
    role: Role


class MeOut(UserOut):
    company_id: str
    company_name: str
    sees_dollars: bool
    enters_time: bool


# ---------- jobs ----------

class TaskIn(BaseModel):
    task_type: TaskType
    name: str = Field(min_length=1, max_length=200)
    estimated_hours: float = Field(ge=0)
    sort_order: int = 0


class TaskOut(ORM):
    id: str
    task_type: TaskType
    name: str
    estimated_hours: float
    sort_order: int


class JobIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    client: str = ""
    address: str = ""
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    court_type: CourtType
    scope_type: ScopeType
    status: JobStatus = JobStatus.scheduled
    contract_amount: float = Field(default=0, ge=0)
    estimated_labor_rate: float = Field(default=0, ge=0)
    tasks: list[TaskIn] = []


class JobStatusIn(BaseModel):
    status: JobStatus


class JobOut(ORM):
    id: str
    name: str
    client: str
    address: str
    lat: float | None
    lng: float | None
    court_type: CourtType
    scope_type: ScopeType
    status: JobStatus
    tasks: list[TaskOut]
    # Only filled in for roles that see dollars; omitted otherwise.
    contract_amount: float | None = None
    estimated_labor_rate: float | None = None


# ---------- time ----------

class TimeEntryIn(BaseModel):
    """Full state of one entry as the phone knows it. Sent on every sync."""

    id: str = Field(min_length=8, max_length=36)
    job_id: str
    task_id: str
    worker_id: str
    clock_in: datetime
    clock_out: datetime | None = None
    in_lat: float | None = None
    in_lng: float | None = None
    out_lat: float | None = None
    out_lng: float | None = None
    note: str = Field(default="", max_length=2000)
    client_updated_at: datetime

    _utc = field_validator("clock_in", "clock_out", "client_updated_at")(to_naive_utc)


class SyncIn(BaseModel):
    entries: list[TimeEntryIn] = Field(max_length=500)


class SyncResult(BaseModel):
    id: str
    status: str  # "saved" | "unchanged" | "stale" | "rejected"
    reason: str | None = None


class SyncOut(BaseModel):
    results: list[SyncResult]


class TimeEntryOut(ORM):
    id: str
    job_id: str
    task_id: str
    worker_id: str
    worker_name: str
    task_name: str
    clock_in: datetime
    clock_out: datetime | None
    hours: float | None
    off_site: bool
    note: str


# ---------- costing ----------

class TaskCosting(BaseModel):
    task_id: str
    name: str
    task_type: TaskType
    estimated_hours: float
    actual_hours: float          # closed entries only
    open_hours: float            # crews still clocked in, counted to now
    hours_used_pct: float | None # (actual + open) / estimated
    status: str                  # "under" | "near" | "over" | "no_estimate"
    estimated_labor_cost: float | None = None
    actual_labor_cost: float | None = None


class JobCosting(BaseModel):
    job_id: str
    job_name: str
    status: JobStatus
    estimated_hours: float
    actual_hours: float
    open_hours: float
    hours_used_pct: float | None
    crew_on_site: int
    tasks: list[TaskCosting]
    contract_amount: float | None = None
    estimated_labor_cost: float | None = None
    actual_labor_cost: float | None = None
    labor_cost_used_pct: float | None = None
    labor_variance: float | None = None  # complete jobs only; positive = over budget
