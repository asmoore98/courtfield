"""Request shapes for clients, leads and estimates."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .models import CourtType, EstimateStatus, LeadStatus, ScopeType, TaskKind
from .quantities import material_qty, worked_hours
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


class CourtInfo(BaseModel):
    """The court's size, entered once. Surface SF is courts x length x width
    unless someone typed a measured total; paintable SF is the surface unless
    it's different (e.g. a strip outside the fence that isn't coated)."""

    courts: int | None = Field(default=None, ge=0, le=200)
    length_ft: float | None = Field(default=None, ge=0, le=5000)
    width_ft: float | None = Field(default=None, ge=0, le=5000)
    surface_sf: float | None = Field(default=None, ge=0, le=10_000_000)  # typed total, overrides the math
    paint_sf: float | None = Field(default=None, ge=0, le=10_000_000)    # typed paintable area

    def surface(self) -> float | None:
        if self.surface_sf is not None:
            return self.surface_sf
        if self.length_ft and self.width_ft:
            return round(self.length_ft * self.width_ft * (self.courts if self.courts else 1), 2)
        return None

    def paint(self) -> float | None:
        return self.paint_sf if self.paint_sf is not None else self.surface()

    def amount(self, follows: str) -> float | None:
        return {"surface": self.surface, "paint": self.paint,
                "courts": lambda: float(self.courts) if self.courts else None}[follows]()


Answer = bool | float | str | list[str] | None


class SiteSurvey(BaseModel):
    """What sales found on site: the court size and the checklist answers,
    keyed by question id (checklists.py)."""

    court: CourtInfo = Field(default_factory=CourtInfo)
    answers: dict[str, Answer] = Field(default_factory=dict, max_length=200)

    @model_validator(mode="after")
    def _sizes(self):
        for k, v in self.answers.items():
            if len(k) > 40:
                raise ValueError("Checklist question id is too long")
            if isinstance(v, str) and len(v) > 2000:
                raise ValueError("A checklist answer is too long (2,000 characters at most)")
            if isinstance(v, list) and (len(v) > 30 or any(len(x) > 200 for x in v)):
                raise ValueError("A checklist answer has too many choices")
        return self


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
    survey: SiteSurvey | None = None  # None keeps what's saved


class LeadStatusIn(BaseModel):
    status: LeadStatus
    reason: str = Field(default="", max_length=1000)


class Markups(BaseModel):
    """Default percent added over cost for each kind of cost. Any line or sub
    can have its own markup instead."""

    material: float = Field(default=0, ge=0, le=1000)
    equipment: float = Field(default=0, ge=0, le=1000)
    subcontractor: float = Field(default=0, ge=0, le=1000)
    other: float = Field(default=0, ge=0, le=1000)


class EstimateData(BaseModel):
    """Everything in one version of an estimate."""

    # "built": the price adds itself up from charge rates and markups, plus an
    # adjustment. "typed": the price was typed in (estimates saved before Batch 3).
    priced: Literal["typed", "built"] = "typed"
    markups: Markups = Field(default_factory=Markups)
    # Percent added on top of everything (after each item's own markup).
    overall_markup: float = Field(default=0, ge=-100, le=1000)
    adjustment: float = Field(default=0, ge=-100_000_000, le=100_000_000)
    adjustment_reason: str = Field(default="", max_length=1000)

    site_address: str = Field(default="", max_length=300)
    parcel_id: str = Field(default="", max_length=60)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    court_type: CourtType
    scope_type: ScopeType
    court: CourtInfo = Field(default_factory=CourtInfo)
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
    def _from_court(self):
        """Quantities that follow the court size are filled in here, so they're
        always right whatever the screen sent."""
        for t in self.tasks:
            if t.follows and t.kind == TaskKind.crew:
                amt = self.court.amount(t.follows)
                if amt is not None:
                    t.quantity = amt
                    h = worked_hours(t.unit, t.quantity, t.coats, t.production_rate)
                    if h is not None:
                        t.estimated_hours = h
        for ln in self.cost_lines:
            if ln.follows in ("surface", "paint") and ln.coverage:
                amt = self.court.amount(ln.follows)
                if amt is not None:
                    ln.quantity = material_qty(amt, ln.coats, ln.coverage)
        return self

    @model_validator(mode="after")
    def _task_links(self):
        for i, ln in enumerate(self.cost_lines):
            if ln.task_index is not None and ln.task_index >= len(self.tasks):
                raise ValueError(f"Cost line {i + 1} points at a task that isn't in the estimate")
        if self.priced == "built" and round(self.adjustment, 2) != 0 and len(self.adjustment_reason.strip()) < 3:
            raise ValueError("Say why the price was adjusted")
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
