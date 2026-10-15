"""Weekly timesheet for payroll.

Hours are grouped by person and by local day (the company's time zone), for
one pay week. Overtime is hours over 40 in the pay week, the federal (FLSA)
rule that Florida follows; it's only split out for field roles, since
salaried office staff are usually exempt. Payroll should still confirm who
is overtime-eligible.

An entry counts on the day it started. Entries still on the clock aren't
counted yet and are flagged instead.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .costing import entry_hours, is_off_site
from .models import Company, Job, Role, TimeEntry, TimeEntryChange

OT_THRESHOLD = 40.0
OT_MULTIPLIER = 1.5
LONG_DAY = 12.0
HOURLY_ROLES = {Role.crew, Role.crew_lead}
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def week_bounds(company: Company, any_day: date) -> tuple[date, date]:
    start = any_day - timedelta(days=(any_day.weekday() - company.week_start) % 7)
    return start, start + timedelta(days=7)


def _utc_naive(d: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(d, time.min, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)


def _local(dt: datetime, tz: ZoneInfo) -> datetime:
    return dt.replace(tzinfo=timezone.utc).astimezone(tz)


def _entries(db: Session, company: Company, start: date, end: date) -> list[TimeEntry]:
    tz = ZoneInfo(company.timezone)
    return list(db.scalars(
        select(TimeEntry)
        .where(
            TimeEntry.company_id == company.id,
            TimeEntry.voided_at.is_(None),
            TimeEntry.clock_in >= _utc_naive(start, tz),
            TimeEntry.clock_in < _utc_naive(end, tz),
        )
        .options(selectinload(TimeEntry.worker), selectinload(TimeEntry.task))
        .order_by(TimeEntry.clock_in)
    ))


def timesheet(db: Session, company: Company, any_day: date) -> dict:
    tz = ZoneInfo(company.timezone)
    start, end = week_bounds(company, any_day)
    days = [start + timedelta(days=i) for i in range(7)]
    entries = _entries(db, company, start, end)
    corrected = set(db.scalars(
        select(TimeEntryChange.entry_id).where(TimeEntryChange.entry_id.in_([e.id for e in entries]))
    ))
    jobs = {j.id: j for j in db.scalars(select(Job).where(Job.id.in_({e.job_id for e in entries})))}

    people: dict[str, dict] = {}
    for e in entries:
        w = e.worker
        p = people.setdefault(w.id, {
            "worker_id": w.id, "name": w.name, "role": w.role, "hourly_cost": w.hourly_cost,
            "days": [0.0] * 7, "jobs": defaultdict(float),
            "open_entries": 0, "corrected": 0, "off_site": 0,
        })
        if e.clock_out is None:
            p["open_entries"] += 1
            continue
        h = entry_hours(e)
        i = (_local(e.clock_in, tz).date() - start).days
        p["days"][i] += h
        p["jobs"][jobs[e.job_id].name] += h
        p["corrected"] += e.id in corrected
        p["off_site"] += is_off_site(e, jobs[e.job_id])

    rows = []
    for p in sorted(people.values(), key=lambda x: x["name"]):
        total = sum(p["days"])
        hourly = p["role"] in HOURLY_ROLES
        regular = min(total, OT_THRESHOLD) if hourly else total
        overtime = max(0.0, total - OT_THRESHOLD) if hourly else 0.0
        rows.append({
            "worker_id": p["worker_id"], "name": p["name"], "role": p["role"],
            "days": [round(h, 2) for h in p["days"]],
            "total_hours": round(total, 2), "regular_hours": round(regular, 2), "overtime_hours": round(overtime, 2),
            "overtime_tracked": hourly,
            "labor_cost": round((regular + overtime * OT_MULTIPLIER) * p["hourly_cost"], 2),
            "jobs": [{"job": k, "hours": round(v, 2)} for k, v in sorted(p["jobs"].items(), key=lambda kv: -kv[1])],
            "flags": {
                "open_entries": p["open_entries"], "corrected": p["corrected"], "off_site": p["off_site"],
                "long_days": sum(1 for h in p["days"] if h > LONG_DAY),
            },
        })

    return {
        "week_start": start.isoformat(),
        "week_end": (end - timedelta(days=1)).isoformat(),
        "timezone": company.timezone,
        "days": [{"date": d.isoformat(), "label": DAY_NAMES[d.weekday()]} for d in days],
        "people": rows,
        "totals": {
            "days": [round(sum(r["days"][i] for r in rows), 2) for i in range(7)],
            "total_hours": round(sum(r["total_hours"] for r in rows), 2),
            "regular_hours": round(sum(r["regular_hours"] for r in rows), 2),
            "overtime_hours": round(sum(r["overtime_hours"] for r in rows), 2),
            "labor_cost": round(sum(r["labor_cost"] for r in rows), 2),
        },
    }


def _cell(v):
    """Keep spreadsheet apps from running text that starts like a formula."""
    v = "" if v is None else str(v)
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


def timesheet_csv(db: Session, company: Company, any_day: date) -> tuple[str, str]:
    """One row per time entry, then one summary row per person. Opens in
    Excel or Google Sheets and imports into most payroll systems."""
    tz = ZoneInfo(company.timezone)
    start, end = week_bounds(company, any_day)
    entries = _entries(db, company, start, end)
    corrected = set(db.scalars(
        select(TimeEntryChange.entry_id).where(TimeEntryChange.entry_id.in_([e.id for e in entries]))
    ))
    jobs = {j.id: j for j in db.scalars(select(Job).where(Job.id.in_({e.job_id for e in entries})))}
    sheet = timesheet(db, company, any_day)

    buf = io.StringIO()
    raw = csv.writer(buf)

    class _Safe:
        def writerow(self, row):
            raw.writerow([_cell(c) for c in row])

    w = _Safe()
    w.writerow(["Pay week", f"{start.isoformat()} to {(end - timedelta(days=1)).isoformat()}", "Time zone", company.timezone])
    w.writerow([])
    w.writerow(["Person", "Date", "Job", "Task", "Clock in", "Clock out", "Hours", "Corrected by office", "Off site", "Note"])
    for e in sorted(entries, key=lambda x: (x.worker.name, x.clock_in)):
        cin = _local(e.clock_in, tz)
        cout = _local(e.clock_out, tz) if e.clock_out else None
        w.writerow([
            e.worker.name, cin.date().isoformat(), jobs[e.job_id].name, e.task.name,
            cin.strftime("%H:%M"), cout.strftime("%H:%M") if cout else "STILL ON THE CLOCK",
            f"{entry_hours(e):.2f}" if cout else "",
            "yes" if e.id in corrected else "", "yes" if is_off_site(e, jobs[e.job_id]) else "", e.note,
        ])
    w.writerow([])
    w.writerow(["Person", "Role", "Regular hours", "Overtime hours", "Total hours", "Labor cost (OT at 1.5x)"])
    for r in sheet["people"]:
        w.writerow([r["name"], r["role"].value if hasattr(r["role"], "value") else r["role"],
                    f"{r['regular_hours']:.2f}", f"{r['overtime_hours']:.2f}" if r["overtime_tracked"] else "n/a",
                    f"{r['total_hours']:.2f}", f"{r['labor_cost']:.2f}"])
    name = f"timesheet-{start.isoformat()}.csv"
    return buf.getvalue(), name
