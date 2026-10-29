"""Core data model for Phase 1: labor hours by task versus the estimate.

Every tenant-owned table carries company_id. All queries go through the
current user's company_id (see auth.py), so one contractor's data never
appears in another contractor's results.

All datetimes are stored as naive UTC.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id() -> str:
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    owner = "owner"            # investor/ownership: read-only reporting
    gm = "gm"                  # general / operations manager: full access
    estimator = "estimator"    # builds jobs and estimates
    crew_lead = "crew_lead"    # field: clocks the crew in and out by task
    crew = "crew"              # field worker; time is entered by the crew lead
    warehouse = "warehouse"    # Phase 2 (materials); read-only for now
    sales = "sales"            # brings in leads; sees proposal prices, never costs
    pm = "pm"                  # project manager; same access as an estimator for now


class CourtType(str, enum.Enum):
    tennis = "tennis"
    pickleball = "pickleball"
    basketball = "basketball"
    multi_court = "multi_court"
    turf_field = "turf_field"


class ScopeType(str, enum.Enum):
    new_construction = "new_construction"
    resurfacing = "resurfacing"
    repair = "repair"


class JobStatus(str, enum.Enum):
    scheduled = "scheduled"
    active = "active"
    complete = "complete"


class TaskType(str, enum.Enum):
    prep = "prep"
    crack_fill = "crack_fill"
    resurfacer = "resurfacer"
    color_coat = "color_coat"
    lines = "lines"
    fence = "fence"
    nets_posts = "nets_posts"
    lighting = "lighting"
    other = "other"


class CostCategory(str, enum.Enum):
    material = "material"
    equipment = "equipment"          # rentals: sprayers, lifts, dumpsters
    subcontractor = "subcontractor"  # e.g. fencing or lighting sub
    other = "other"                  # permits, freight, disposal


class MoveKind(str, enum.Enum):
    receive = "receive"    # new stock into the warehouse (from a supplier)
    to_job = "to_job"      # sent out to a job
    from_job = "from_job"  # leftovers brought back from a job
    adjust = "adjust"      # count correction (+ or -)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Local time zone for days and pay weeks (IANA name).
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York", server_default="America/New_York")
    # First day of the pay week: 0 = Monday ... 6 = Sunday.
    week_start: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # What prints at the top of a proposal. Blank fields are left off.
    proposal_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    proposal_address: Mapped[str] = mapped_column(String(300), default="", server_default="")
    proposal_phone: Mapped[str] = mapped_column(String(40), default="", server_default="")
    proposal_email: Mapped[str] = mapped_column(String(254), default="", server_default="")
    proposal_license: Mapped[str] = mapped_column(String(100), default="", server_default="")
    proposal_logo_url: Mapped[str] = mapped_column(String(500), default="", server_default="")
    proposal_terms: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Days a sent estimate stays good before it's marked expired.
    estimate_valid_days: Mapped[int] = mapped_column(Integer, default=30, server_default="30")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(Enum(Role))
    # Burdened labor cost per hour (wage + taxes + comp). Drives actual labor $.
    hourly_cost: Mapped[float] = mapped_column(Float, default=0.0)
    # Sign-in. Crew members who never use the app have no email or password;
    # crew leads clock them in. Emails are stored lowercased.
    email: Mapped[str | None] = mapped_column(String(254), unique=True, index=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # When this person acknowledged that their phone shares its location with
    # the office while their crew is on the clock. Kept as a record of notice.
    location_notice_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DeviceSession(Base):
    """One signed-in device. Only a hash of the token is stored, so a
    database leak doesn't hand out working sign-ins."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    device: Mapped[str] = mapped_column(String(200), default="")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship()


class Invite(Base):
    """A one-time link that lets a person set (or reset) their password."""

    __tablename__ = "invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(foreign_keys=[user_id])


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    client: Mapped[str] = mapped_column(String(200), default="")
    address: Mapped[str] = mapped_column(String(300), default="")
    # County parcel ID. New construction often has no street address yet.
    parcel_id: Mapped[str] = mapped_column(String(60), default="", server_default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    court_type: Mapped[CourtType] = mapped_column(Enum(CourtType))
    scope_type: Mapped[ScopeType] = mapped_column(Enum(ScopeType))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.scheduled)
    contract_amount: Mapped[float] = mapped_column(Float, default=0.0)
    # Blended labor $/hr used when the estimate was built.
    estimated_labor_rate: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Florida contractors pay sales tax on materials; applied to material lines only.
    sales_tax_pct: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    # The client record, when the job came from an estimate or was linked to one.
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id"), nullable=True, index=True)

    cost_lines: Mapped[list[CostLine]] = relationship(
        back_populates="job", order_by="CostLine.sort_order", cascade="all, delete-orphan"
    )
    tasks: Mapped[list[JobTask]] = relationship(
        back_populates="job", order_by="JobTask.sort_order", cascade="all, delete-orphan"
    )


class JobTask(Base):
    __tablename__ = "job_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType))
    name: Mapped[str] = mapped_column(String(200))
    estimated_hours: Mapped[float] = mapped_column(Float, default=0.0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    job: Mapped[Job] = relationship(back_populates="tasks")


class StockItem(Base):
    """A price-list item: what it's called, how it's counted, what it costs,
    and whether the warehouse keeps it in stock."""

    __tablename__ = "stock_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[CostCategory] = mapped_column(Enum(CostCategory), default=CostCategory.material)
    unit: Mapped[str] = mapped_column(String(20), default="")
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    sku: Mapped[str] = mapped_column(String(60), default="")
    track_stock: Mapped[bool] = mapped_column(default=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CostLine(Base):
    """One estimated non-labor cost on a job: a material, a rental, a sub, or
    anything else. Quantity x unit cost; materials also carry sales tax."""

    __tablename__ = "cost_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("job_tasks.id", ondelete="SET NULL"), nullable=True)
    item_id: Mapped[str | None] = mapped_column(ForeignKey("stock_items.id", ondelete="SET NULL"), nullable=True)
    category: Mapped[CostCategory] = mapped_column(Enum(CostCategory), default=CostCategory.material)
    description: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(20), default="")
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    job: Mapped[Job] = relationship(back_populates="cost_lines")


class StockMove(Base):
    """One movement of material: received, sent to a job, brought back, or a
    count correction. Never deleted; mistakes are voided with a reason."""

    __tablename__ = "stock_moves"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    kind: Mapped[MoveKind] = mapped_column(Enum(MoveKind))
    item_id: Mapped[str | None] = mapped_column(ForeignKey("stock_items.id"), nullable=True, index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    cost_line_id: Mapped[str | None] = mapped_column(ForeignKey("cost_lines.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(20), default="")
    quantity: Mapped[float] = mapped_column(Float)  # positive, except adjust can be negative
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)  # cost at the time of the move
    lot_number: Mapped[str] = mapped_column(String(60), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    recorded_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    voided_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    void_reason: Mapped[str] = mapped_column(Text, default="")

    recorded_by: Mapped[User] = relationship(foreign_keys=[recorded_by_id])


class TimeEntry(Base):
    """One worker's time on one task of one job.

    The id is generated on the phone so an entry made offline can be synced
    any number of times without creating duplicates.
    """

    __tablename__ = "time_entries"
    __table_args__ = (Index("ix_time_worker_in", "worker_id", "clock_in"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("job_tasks.id"), index=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    entered_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    clock_in: Mapped[datetime] = mapped_column(DateTime)
    clock_out: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    in_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    out_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    out_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    # Last-write-wins timestamp set by the device that made the change.
    client_updated_at: Mapped[datetime] = mapped_column(DateTime)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Set once anyone in the office has added or corrected this entry. From
    # then on the field app can only close it, not change what the office set.
    office_edited: Mapped[bool] = mapped_column(default=False)
    # Removed entries are kept (voided), never deleted, so payroll history holds.
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    voided_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    void_reason: Mapped[str] = mapped_column(Text, default="")

    worker: Mapped[User] = relationship(foreign_keys=[worker_id])
    task: Mapped[JobTask] = relationship()


class TimeEntryChange(Base):
    """Audit trail: one row per office add, correction or removal of a time
    entry, with the entry as it was before and after."""

    __tablename__ = "time_entry_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    entry_id: Mapped[str] = mapped_column(ForeignKey("time_entries.id"), index=True)
    changed_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    action: Mapped[str] = mapped_column(String(10))  # "add" | "edit" | "remove"
    reason: Mapped[str] = mapped_column(Text)
    before: Mapped[str] = mapped_column(Text, default="")  # JSON snapshot
    after: Mapped[str] = mapped_column(Text, default="")

    changed_by: Mapped[User] = relationship()


class LocationPing(Base):
    """Where a crew lead's phone was at one moment while their crew was on the
    clock. Only accepted inside a clocked window of time that phone's user
    entered, so nobody is tracked off the clock.

    The id is generated on the phone so a resend after a dropped connection
    doesn't make a duplicate.
    """

    __tablename__ = "location_pings"
    __table_args__ = (Index("ix_ping_user_time", "user_id", "recorded_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ---------- sales: clients, leads, estimates ----------

class Client(Base):
    """A customer: an HOA, a school, a city, an apartment complex, a homeowner.
    Leads, estimates and jobs all point back here. Never deleted; turned off."""

    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    billing_address: Mapped[str] = mapped_column(String(300), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    links: Mapped[str] = mapped_column(Text, default="")  # shared-drive links, one per line
    active: Mapped[bool] = mapped_column(default=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LeadStatus(str, enum.Enum):
    new = "new"                # waiting on an estimator
    estimating = "estimating"  # an estimate has been started
    estimated = "estimated"    # the estimate went out to the client
    dropped = "dropped"        # not pursuing it


class Lead(Base):
    """What sales brings in: who, where, and what they want, with links to
    plans and photos. An estimator turns it into an estimate."""

    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    site_address: Mapped[str] = mapped_column(String(300), default="")
    parcel_id: Mapped[str] = mapped_column(String(60), default="")
    court_type: Mapped[CourtType | None] = mapped_column(Enum(CourtType), nullable=True)
    scope_type: Mapped[ScopeType | None] = mapped_column(Enum(ScopeType), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    links: Mapped[str] = mapped_column(Text, default="")
    bid_due: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus), default=LeadStatus.new)
    status_reason: Mapped[str] = mapped_column(Text, default="")
    salesperson_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    client: Mapped[Client] = relationship()
    salesperson: Mapped[User | None] = relationship(foreign_keys=[salesperson_id])


class EstimateStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    won = "won"
    lost = "lost"
    no_bid = "no_bid"
    expired = "expired"


class Estimate(Base):
    """A priced scope of work for a client. Its content lives in numbered
    versions; every save makes a new one and old ones can't be changed."""

    __tablename__ = "estimates"
    __table_args__ = (UniqueConstraint("company_id", "number", name="uq_estimate_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(20))
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[EstimateStatus] = mapped_column(Enum(EstimateStatus), default=EstimateStatus.draft)
    salesperson_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    valid_days: Mapped[int] = mapped_column(Integer, default=30)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    client: Mapped[Client] = relationship()
    salesperson: Mapped[User | None] = relationship(foreign_keys=[salesperson_id])
    versions: Mapped[list[EstimateVersion]] = relationship(
        back_populates="estimate", order_by="EstimateVersion.version", cascade="all"
    )


class EstimateVersion(Base):
    """One saved copy of an estimate's content, as JSON. Locked once saved;
    only the GM can remove one, and that's a void with a reason, not a delete."""

    __tablename__ = "estimate_versions"
    __table_args__ = (UniqueConstraint("estimate_id", "version", name="uq_estimate_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    estimate_id: Mapped[str] = mapped_column(ForeignKey("estimates.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[str] = mapped_column(Text)  # JSON: site, tasks, cost lines, price, proposal text
    price: Mapped[float] = mapped_column(Float, default=0.0)       # what the client pays
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)  # what it costs us
    note: Mapped[str] = mapped_column(Text, default="")             # what changed in this version
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    voided_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    void_reason: Mapped[str] = mapped_column(Text, default="")

    estimate: Mapped[Estimate] = relationship(back_populates="versions")
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])


class Activity(Base):
    """The paper trail: who did what to a client, lead, estimate or job, and
    when. Rows are only ever added."""

    __tablename__ = "activity"
    __table_args__ = (Index("ix_activity_subject", "company_id", "kind", "subject_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    kind: Mapped[str] = mapped_column(String(20))        # client | lead | estimate | job
    subject_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(200))      # plain words, e.g. "Marked won"
    detail: Mapped[str] = mapped_column(Text, default="")  # reason, note, or what changed
    by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # empty = automatic
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    by: Mapped[User | None] = relationship()
