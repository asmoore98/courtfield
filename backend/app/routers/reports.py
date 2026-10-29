"""Payroll timesheet and company settings that shape it."""
from datetime import date
from zoneinfo import ZoneInfo, available_timezones

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import require_roles
from ..db import get_db
from ..models import Company, Role, User
from ..reports import timesheet, timesheet_csv

router = APIRouter(prefix="/api", tags=["reports"])
payroll_roles = require_roles(Role.gm, Role.owner)


def _company(db: Session, user: User) -> Company:
    return db.get(Company, user.company_id)


def _day(week: str | None, company: Company) -> date:
    if not week:
        from datetime import datetime
        return datetime.now(ZoneInfo(company.timezone)).date()
    try:
        return date.fromisoformat(week)
    except ValueError:
        raise HTTPException(422, "Use a date like 2026-10-12 for the week")


@router.get("/reports/timesheet")
def get_timesheet(week: str | None = None, user: User = Depends(payroll_roles), db: Session = Depends(get_db)):
    company = _company(db, user)
    return timesheet(db, company, _day(week, company))


@router.get("/reports/timesheet.csv")
def get_timesheet_csv(week: str | None = None, user: User = Depends(payroll_roles), db: Session = Depends(get_db)):
    company = _company(db, user)
    text, name = timesheet_csv(db, company, _day(week, company))
    # BOM so Excel reads the file as UTF-8
    return Response("﻿" + text, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


PROPOSAL_FIELDS = ("proposal_name", "proposal_address", "proposal_phone", "proposal_email", "proposal_license",
                   "proposal_logo_url", "proposal_terms")


class CompanyOut(BaseModel):
    name: str
    timezone: str
    week_start: int
    proposal_name: str = ""
    proposal_address: str = ""
    proposal_phone: str = ""
    proposal_email: str = ""
    proposal_license: str = ""
    proposal_logo_url: str = ""
    proposal_terms: str = ""
    estimate_valid_days: int = 30


class CompanyEdit(BaseModel):
    timezone: str | None = None
    week_start: int | None = Field(default=None, ge=0, le=6)
    proposal_name: str | None = Field(default=None, max_length=200)
    proposal_address: str | None = Field(default=None, max_length=300)
    proposal_phone: str | None = Field(default=None, max_length=40)
    proposal_email: str | None = Field(default=None, max_length=254)
    proposal_license: str | None = Field(default=None, max_length=100)
    proposal_logo_url: str | None = Field(default=None, max_length=500)
    proposal_terms: str | None = Field(default=None, max_length=10000)
    estimate_valid_days: int | None = Field(default=None, ge=1, le=365)


def _company_out(c) -> CompanyOut:
    return CompanyOut(name=c.name, timezone=c.timezone, week_start=c.week_start, estimate_valid_days=c.estimate_valid_days,
                      **{k: getattr(c, k) for k in PROPOSAL_FIELDS})


@router.get("/company", response_model=CompanyOut)
def get_company(user: User = Depends(require_roles(Role.gm, Role.owner)), db: Session = Depends(get_db)):
    return _company_out(_company(db, user))


@router.patch("/company", response_model=CompanyOut)
def edit_company(body: CompanyEdit, user: User = Depends(require_roles(Role.gm)), db: Session = Depends(get_db)):
    c = _company(db, user)
    if body.timezone is not None:
        if body.timezone not in available_timezones():
            raise HTTPException(422, "Unknown time zone")
        c.timezone = body.timezone
    if body.week_start is not None:
        c.week_start = body.week_start
    if body.estimate_valid_days is not None:
        c.estimate_valid_days = body.estimate_valid_days
    for k in PROPOSAL_FIELDS:
        v = getattr(body, k)
        if v is not None:
            setattr(c, k, v.strip())
    db.commit()
    return _company_out(c)
