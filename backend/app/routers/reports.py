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


class CompanyOut(BaseModel):
    name: str
    timezone: str
    week_start: int


class CompanyEdit(BaseModel):
    timezone: str | None = None
    week_start: int | None = Field(default=None, ge=0, le=6)


@router.get("/company", response_model=CompanyOut)
def get_company(user: User = Depends(require_roles(Role.gm, Role.owner)), db: Session = Depends(get_db)):
    c = _company(db, user)
    return CompanyOut(name=c.name, timezone=c.timezone, week_start=c.week_start)


@router.patch("/company", response_model=CompanyOut)
def edit_company(body: CompanyEdit, user: User = Depends(require_roles(Role.gm)), db: Session = Depends(get_db)):
    c = _company(db, user)
    if body.timezone is not None:
        if body.timezone not in available_timezones():
            raise HTTPException(422, "Unknown time zone")
        c.timezone = body.timezone
    if body.week_start is not None:
        c.week_start = body.week_start
    db.commit()
    return CompanyOut(name=c.name, timezone=c.timezone, week_start=c.week_start)
