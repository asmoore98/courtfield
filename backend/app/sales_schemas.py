"""Request shapes for clients, leads and estimates."""
from datetime import date

from pydantic import BaseModel, Field, model_validator

from .models import CourtType, EstimateStatus, LeadStatus, ScopeType
from .schemas import CostLineIn, TaskIn

LONG = 5000


class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    contact_name: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=254)
    billing_address: str = Field(default="", max_length=300)
    notes: str = Field(default="", max_length=LONG)
    links: str = Field(default="", max_length=LONG)


class ClientActiveIn(BaseModel):
    active: bool
    reason: str = Field(default="", max_length=1000)


class LeadIn(BaseModel):
    client_id: str
    name: str = Field(min_length=1, max_length=200)
    site_address: str = Field(default="", max_length=300)
    parcel_id: str = Field(default="", max_length=60)
    court_type: CourtType | None = None
    scope_type: ScopeType | None = None
    description: str = Field(default="", max_length=LONG)
    links: str = Field(default="", max_length=LONG)
    bid_due: date | None = None
    salesperson_id: str | None = None


class LeadStatusIn(BaseModel):
    status: LeadStatus
    reason: str = Field(default="", max_length=1000)


class EstimateData(BaseModel):
    """Everything in one version of an estimate."""

    site_address: str = Field(default="", max_length=300)
    parcel_id: str = Field(default="", max_length=60)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    court_type: CourtType
    scope_type: ScopeType
    price: float = Field(default=0, ge=0, le=100_000_000)  # what the client pays
    estimated_labor_rate: float = Field(default=0, ge=0)
    sales_tax_pct: float = Field(default=0, ge=0, le=20)
    tasks: list[TaskIn] = Field(default=[], max_length=100)
    cost_lines: list[CostLineIn] = Field(default=[], max_length=300)
    scope_text: str = Field(default="", max_length=LONG)   # proposal: the work, in words
    exclusions: str = Field(default="", max_length=LONG)   # proposal: what's not included
    links: str = Field(default="", max_length=LONG)        # plans, photos: shared-drive links
    notes: str = Field(default="", max_length=LONG)        # internal only, never on the proposal

    @model_validator(mode="after")
    def _task_links(self):
        for i, ln in enumerate(self.cost_lines):
            if ln.task_index is not None and ln.task_index >= len(self.tasks):
                raise ValueError(f"Cost line {i + 1} points at a task that isn't in the estimate")
        return self


class EstimateIn(BaseModel):
    client_id: str
    lead_id: str | None = None
    name: str = Field(min_length=1, max_length=200)
    salesperson_id: str | None = None
    valid_days: int | None = Field(default=None, ge=1, le=365)
    data: EstimateData
    note: str = Field(default="", max_length=1000)


class EstimateStatusIn(BaseModel):
    status: EstimateStatus
    note: str = Field(default="", max_length=1000)


class NoteIn(BaseModel):
    note: str = Field(default="", max_length=1000)


class VoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
