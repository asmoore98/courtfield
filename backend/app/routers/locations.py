"""Crew locations: pings from crew lead phones, the live map, and the daily
on-the-job / travel report. See app/tracking.py for how time is split."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..auth import EDITS_JOBS, ENTERS_TIME, SEES_LOCATIONS, current_user, require_roles
from ..db import get_db
from ..models import Company, Job, LocationPing, Role, TimeEntry, User, utcnow
from ..schemas import to_naive_utc
from ..tracking import WINDOW_SLACK, daily_csv, daily_detail, daily_report, live_crews

router = APIRouter(prefix="/api", tags=["locations"])
sees_locations = require_roles(*SEES_LOCATIONS)
MAX_AGE = timedelta(days=7)          # phones that were offline for days can still catch up
FUTURE_SLACK = timedelta(minutes=10)


class PingIn(BaseModel):
    id: str = Field(min_length=8, max_length=36)
    recorded_at: datetime
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)

    _utc = field_validator("recorded_at")(to_naive_utc)


class PingsIn(BaseModel):
    pings: list[PingIn] = Field(max_length=500)


@router.post("/locations")
def upload_pings(body: PingsIn, user: User = Depends(require_roles(*ENTERS_TIME)), db: Session = Depends(get_db)):
    """Store pings that fall inside time this user clocked people in for.

    Anything else (off the clock, too old, a duplicate) is dropped. Both
    lists come back so the phone can clear its queue either way.
    """
    now = utcnow()
    ok = [p for p in body.pings if now - MAX_AGE <= p.recorded_at <= now + FUTURE_SLACK]
    saved, dropped = [], [p.id for p in body.pings if p not in ok]
    if ok:
        lo, hi = min(p.recorded_at for p in ok), max(p.recorded_at for p in ok)
        windows = [
            (e.clock_in - WINDOW_SLACK, (e.clock_out or now) + WINDOW_SLACK)
            for e in db.scalars(
                select(TimeEntry).where(
                    TimeEntry.company_id == user.company_id, TimeEntry.entered_by_id == user.id,
                    TimeEntry.voided_at.is_(None), TimeEntry.clock_in <= hi + WINDOW_SLACK,
                    or_(TimeEntry.clock_out.is_(None), TimeEntry.clock_out >= lo - WINDOW_SLACK),
                )
            )
        ]
        known = set(db.scalars(select(LocationPing.id).where(LocationPing.id.in_([p.id for p in ok]))))
        for p in ok:
            if p.id in known:
                saved.append(p.id)  # already have it; a resend is fine
            elif any(a <= p.recorded_at <= b for a, b in windows):
                db.add(LocationPing(id=p.id, company_id=user.company_id, user_id=user.id,
                                    recorded_at=p.recorded_at, lat=p.lat, lng=p.lng, accuracy_m=p.accuracy_m))
                known.add(p.id)
                saved.append(p.id)
            else:
                dropped.append(p.id)
    db.commit()
    return {"saved": saved, "dropped": dropped}


@router.post("/me/location-notice")
def acknowledge_notice(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.location_notice_at is None:
        user.location_notice_at = utcnow()
        db.commit()
    return {"location_notice_at": user.location_notice_at.isoformat() + "Z"}


class SiteIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


@router.post("/jobs/{job_id}/site")
def set_site(job_id: str, body: SiteIn, user: User = Depends(require_roles(*(ENTERS_TIME | EDITS_JOBS))),
             db: Session = Depends(get_db)):
    """Drop the job's site pin where the phone is. Crew leads can only set a
    missing pin, not move one the office placed."""
    job = db.get(Job, job_id)
    if job is None or job.company_id != user.company_id:
        raise HTTPException(404, "Job not found")
    if job.lat is not None and user.role not in EDITS_JOBS and user.role != Role.gm:
        raise HTTPException(409, "This job already has a site pin. Ask the office to move it.")
    job.lat, job.lng = round(body.lat, 6), round(body.lng, 6)
    db.commit()
    return {"id": job.id, "lat": job.lat, "lng": job.lng}


@router.get("/crews/live")
def get_live(user: User = Depends(sees_locations), db: Session = Depends(get_db)):
    return live_crews(db, db.get(Company, user.company_id))


def _day(value: str | None, company: Company) -> date:
    if not value:
        return datetime.now(ZoneInfo(company.timezone)).date()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "Use a date like 2026-10-16")


@router.get("/reports/daily")
def get_daily(date: str | None = None, user: User = Depends(sees_locations), db: Session = Depends(get_db)):
    company = db.get(Company, user.company_id)
    return daily_report(db, company, _day(date, company))


@router.get("/reports/daily.csv")
def get_daily_csv(date: str | None = None, user: User = Depends(sees_locations), db: Session = Depends(get_db)):
    company = db.get(Company, user.company_id)
    text, name = daily_csv(db, company, _day(date, company))
    return Response("﻿" + text, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/reports/daily/{worker_id}")
def get_daily_detail(worker_id: str, date: str | None = None, user: User = Depends(sees_locations),
                     db: Session = Depends(get_db)):
    company = db.get(Company, user.company_id)
    worker = db.get(User, worker_id)
    if worker is None or worker.company_id != company.id:
        raise HTTPException(404, "Person not found")
    d = daily_detail(db, company, _day(date, company), worker_id)
    if d is None:
        raise HTTPException(404, f"{worker.name} has no time that day")
    return d
