"""Request and response shapes for the API."""
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from .models import CostCategory, CourtType, JobStatus, Role, ScopeType, TaskType


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
    edits_jobs: bool
    manages_stock: bool = False
    edits_prices: bool = False


# ---------- jobs ----------

class TaskIn(BaseModel):
    id: str | None = None  # set when editing an existing task; omit for a new one
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


class CostLineIn(BaseModel):
    id: str | None = None
    category: CostCategory = CostCategory.material
    description: str = Field(min_length=1, max_length=200)
    quantity: float = Field(ge=0, le=1_000_000)
    unit: str = Field(default="", max_length=20)
    unit_cost: float = Field(ge=0, le=10_000_000)
    # Position of the linked task in this save's task list (new tasks have no id yet).
    task_index: int | None = Field(default=None, ge=0)
    item_id: str | None = None  # price-list item this line came from


class CostLineOut(ORM):
    id: str
    category: CostCategory
    description: str
    quantity: float
    unit: str
    unit_cost: float
    task_id: str | None
    item_id: str | None = None
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
    sales_tax_pct: float = Field(default=0, ge=0, le=20)
    tasks: list[TaskIn] = Field(default=[], max_length=100)
    cost_lines: list[CostLineIn] = Field(default=[], max_length=300)


class JobUpdate(JobIn):
    """Full replacement of a job's details and task list. Status changes go
    through PATCH /status (GM only), so status here is ignored. Leaving
    cost_lines out keeps the job's lines as they are."""

    status: JobStatus | None = None
    cost_lines: list[CostLineIn] | None = Field(default=None, max_length=300)


class JobStatusIn(BaseModel):
    status: JobStatus


class TaskOutWithTime(TaskOut):
    has_time: bool = False  # time is logged against it, so it can't be removed


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
    sales_tax_pct: float | None = None
    cost_lines: list[CostLineOut] | None = None


class JobEditOut(JobOut):
    tasks: list[TaskOutWithTime]


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
    in_lat: float | None = None
    in_lng: float | None = None
    out_lat: float | None = None
    out_lng: float | None = None
    client_updated_at: datetime
    edited: bool = False
    removed: bool = False
    removed_reason: str = ""

    @field_serializer("clock_in", "clock_out", "client_updated_at")
    def _as_utc(self, v: datetime | None):
        # Stored naive UTC; say so explicitly so browsers don't read it as local time.
        return None if v is None else v.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


class OfficeTimeIn(BaseModel):
    """Time added from the office, e.g. a crew lead's phone was dead."""

    job_id: str
    task_id: str
    worker_id: str
    clock_in: datetime
    clock_out: datetime
    reason: str = Field(min_length=3, max_length=500)

    _utc = field_validator("clock_in", "clock_out")(to_naive_utc)


class OfficeTimeEdit(BaseModel):
    """A correction. Only the fields sent are changed; clock_out may be sent
    as null to reopen an entry."""

    task_id: str | None = None
    worker_id: str | None = None
    clock_in: datetime | None = None
    clock_out: datetime | None = None
    reason: str = Field(min_length=3, max_length=500)

    _utc = field_validator("clock_in", "clock_out")(to_naive_utc)


class RemoveIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class TimeChangeOut(BaseModel):
    action: str
    reason: str
    changed_by: str
    changed_at: datetime
    before: dict | None
    after: dict | None

    @field_serializer("changed_at")
    def _as_utc(self, v: datetime):
        return v.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


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
    # Estimate summary (dollars roles only)
    estimate: dict | None = None
    materials_actual_cost: float | None = None  # sent minus returned, at cost


# ---------- sign-in ----------

class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)
    device: str = Field(default="", max_length=200)


class SessionOut(BaseModel):
    token: str
    me: MeOut


class InviteInfo(BaseModel):
    name: str
    email: str | None
    company_name: str
    resetting: bool  # true when the person already had a password


class SetPasswordIn(BaseModel):
    password: str = Field(min_length=8, max_length=200)
    device: str = Field(default="", max_length=200)


# ---------- team ----------

class PersonOut(BaseModel):
    id: str
    name: str
    role: Role
    email: str | None
    hourly_cost: float
    active: bool
    signs_in: bool
    has_password: bool
    devices: int
    last_seen: datetime | None

    @field_serializer("last_seen")
    def _as_utc(self, v: datetime | None):
        return None if v is None else v.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


class PersonIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: Role
    email: str | None = Field(default=None, max_length=254)
    hourly_cost: float = Field(default=0, ge=0, le=1000)


class PersonEdit(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: Role | None = None
    email: str | None = Field(default=None, max_length=254)
    hourly_cost: float | None = Field(default=None, ge=0, le=1000)
    active: bool | None = None


class PersonSaved(BaseModel):
    person: PersonOut
    invite_url: str | None = None
