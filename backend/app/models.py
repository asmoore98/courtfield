"""Core data model for Phase 1: labor hours by task versus the estimate.

Every tenant-owned table carries company_id. All queries go through the
current user's company_id (see auth.py), so one contractor's data never
appears in another contractor's results.

All datetimes are stored as naive UTC.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
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


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(Enum(Role))
    # Burdened labor cost per hour (wage + taxes + comp). Drives actual labor $.
    hourly_cost: Mapped[float] = mapped_column(Float, default=0.0)
    # Development-only bearer token. Replace with real auth before any live use.
    api_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    active: Mapped[bool] = mapped_column(default=True)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    client: Mapped[str] = mapped_column(String(200), default="")
    address: Mapped[str] = mapped_column(String(300), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    court_type: Mapped[CourtType] = mapped_column(Enum(CourtType))
    scope_type: Mapped[ScopeType] = mapped_column(Enum(ScopeType))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.scheduled)
    contract_amount: Mapped[float] = mapped_column(Float, default=0.0)
    # Blended labor $/hr used when the estimate was built.
    estimated_labor_rate: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

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
