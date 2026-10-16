"""Where crews were while on the clock: live positions and the daily report.

Crew members don't carry the app; their crew lead clocks them in. So a crew
member's location is the location of the phone that clocked them in. That
phone sends a ping every few minutes while the app is open and anyone it
clocked in is on the clock, plus a stamp at every clock-in and clock-out.

How the daily report splits clocked time, from those points:

* On the job: the phone was within the job's site radius at both ends of a
  stretch between two points.
* Travel: either end of the stretch was away from the job site (driving to
  it, between jobs, a supply run).
* Can't tell: the job has no site pin, there are no points at all, or the
  first or last point is more than EDGE_GAP from clock-in or clock-out.

A web app only gets GPS while it's open, so a locked phone leaves gaps. A gap
with the phone on site at both ends counts as on the job; a gap with either
end away counts as travel. The report shows the longest gap so the office can
judge how much to trust a day.
"""
from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from .costing import OFF_SITE_METERS, distance_m
from .models import Company, Job, JobStatus, LocationPing, TimeEntry, User, utcnow
from .reports import _cell, _local, _utc_naive

EDGE_GAP = timedelta(minutes=30)     # farther than this from clock-in/out to a point -> can't tell
WINDOW_SLACK = timedelta(minutes=2)  # pings this close outside a clocked window still count
MAX_ACCURACY_BONUS = 150             # meters of GPS uncertainty allowed on top of the site radius
LONG_GAP_MIN = 30                    # flag days with a stretch this long without a location
STALE_MIN = 15                       # live map: older than this, the phone is probably locked

ON_JOB, TRAVEL, UNKNOWN = "on_job", "travel", "unknown"


@dataclass(frozen=True)
class Point:
    t: datetime
    lat: float
    lng: float
    accuracy: float | None = None


def site_distance(p: Point, job: Job) -> float | None:
    if job.lat is None or job.lng is None:
        return None
    return distance_m(p.lat, p.lng, job.lat, job.lng)


def on_site(p: Point, job: Job) -> bool | None:
    d = site_distance(p, job)
    if d is None:
        return None
    slack = min(p.accuracy or 0, MAX_ACCURACY_BONUS)
    return d <= OFF_SITE_METERS + slack


def entry_points(entry: TimeEntry, pings: list[Point], end: datetime) -> list[Point]:
    """The clock-in stamp, pings inside the window, and the clock-out stamp."""
    pts = []
    if entry.in_lat is not None and entry.in_lng is not None:
        pts.append(Point(entry.clock_in, entry.in_lat, entry.in_lng))
    for p in pings:
        if entry.clock_in - WINDOW_SLACK <= p.t <= end + WINDOW_SLACK:
            pts.append(Point(min(max(p.t, entry.clock_in), end), p.lat, p.lng, p.accuracy))
    if entry.clock_out is not None and entry.out_lat is not None and entry.out_lng is not None:
        pts.append(Point(entry.clock_out, entry.out_lat, entry.out_lng))
    return sorted(pts, key=lambda p: p.t)


def segments(start: datetime, end: datetime, pts: list[Point], job: Job) -> list[tuple[datetime, datetime, str]]:
    """Split [start, end] into on-the-job, travel and can't-tell stretches."""
    if end <= start:
        return []
    if job.lat is None or job.lng is None or not pts:
        return [(start, end, UNKNOWN)]
    states = [on_site(p, job) for p in pts]
    out: list[tuple[datetime, datetime, str]] = []

    def add(a, b, s):
        if b <= a:
            return
        if out and out[-1][2] == s and out[-1][1] == a:
            out[-1] = (out[-1][0], b, s)
        else:
            out.append((a, b, s))

    first, last = pts[0], pts[-1]
    lead = first.t - start
    add(start, first.t, (ON_JOB if states[0] else TRAVEL) if lead <= EDGE_GAP else UNKNOWN)
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        add(a.t, b.t, ON_JOB if states[i] and states[i + 1] else TRAVEL)
    tail = end - last.t
    add(last.t, end, (ON_JOB if states[-1] else TRAVEL) if tail <= EDGE_GAP else UNKNOWN)
    return out


def longest_gap_minutes(start: datetime, end: datetime, pts: list[Point]) -> float:
    marks = [start] + [p.t for p in pts] + [end]
    return max(((b - a).total_seconds() / 60 for a, b in zip(marks, marks[1:])), default=0)


def _pings_by_user(db: Session, company_id: str, user_ids: set[str], start: datetime, end: datetime) -> dict[str, list[Point]]:
    by_user: dict[str, list[Point]] = defaultdict(list)
    if not user_ids:
        return by_user
    rows = db.scalars(
        select(LocationPing)
        .where(LocationPing.company_id == company_id, LocationPing.user_id.in_(user_ids),
               LocationPing.recorded_at >= start - WINDOW_SLACK, LocationPing.recorded_at <= end + WINDOW_SLACK)
        .order_by(LocationPing.recorded_at)
    )
    for r in rows:
        by_user[r.user_id].append(Point(r.recorded_at, r.lat, r.lng, r.accuracy_m))
    return by_user


def _iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.isoformat() + "Z"


def _h(seconds: float) -> float:
    return round(seconds / 3600, 2)


# ---------- daily report ----------

def _day_entries(db: Session, company: Company, day: date, worker_id: str | None = None) -> tuple[list[TimeEntry], datetime, datetime]:
    tz = ZoneInfo(company.timezone)
    start, end = _utc_naive(day, tz), _utc_naive(day + timedelta(days=1), tz)
    q = (
        select(TimeEntry)
        .where(TimeEntry.company_id == company.id, TimeEntry.voided_at.is_(None),
               TimeEntry.clock_in < end, or_(TimeEntry.clock_out.is_(None), TimeEntry.clock_out > start))
        .options(selectinload(TimeEntry.worker), selectinload(TimeEntry.task))
        .order_by(TimeEntry.clock_in)
    )
    if worker_id:
        q = q.where(TimeEntry.worker_id == worker_id)
    return list(db.scalars(q)), start, end


def _analyze(db: Session, company: Company, day: date, worker_id: str | None = None) -> dict:
    """Per person: their entries that day, each split into stretches."""
    entries, day_start, day_end = _day_entries(db, company, day, worker_id)
    now = utcnow()
    jobs = {j.id: j for j in db.scalars(select(Job).where(Job.id.in_({e.job_id for e in entries})))}
    pings = _pings_by_user(db, company.id, {e.entered_by_id for e in entries}, day_start, day_end)
    people: dict[str, dict] = {}
    for e in entries:
        job = jobs[e.job_id]
        raw_end = e.clock_out or now
        start, end = max(e.clock_in, day_start), min(raw_end, day_end)
        if end <= start:
            continue
        pts = entry_points(e, pings.get(e.entered_by_id, []), raw_end)
        segs = [(max(a, start), min(b, end), s) for a, b, s in segments(e.clock_in, raw_end, pts, job)]
        segs = [x for x in segs if x[1] > x[0]]
        p = people.setdefault(e.worker_id, {"worker": e.worker, "entries": []})
        p["entries"].append({
            "entry": e, "job": job, "start": start, "end": end, "segments": segs,
            "points": [x for x in pts if start - WINDOW_SLACK <= x.t <= end + WINDOW_SLACK],
            "open": e.clock_out is None,
            "no_pin": job.lat is None or job.lng is None,
            "no_points": not pts,
            "longest_gap": longest_gap_minutes(start, end, [x for x in pts if start <= x.t <= end]),
        })
    return {"people": people, "day_start": day_start, "day_end": day_end}


def _summary(worker: User, items: list[dict]) -> dict:
    tot = Counter()
    for it in items:
        for a, b, s in it["segments"]:
            tot[s] += (b - a).total_seconds()
    gaps = 0.0
    ordered = sorted(items, key=lambda x: x["start"])
    for prev, nxt in zip(ordered, ordered[1:]):
        g = (nxt["start"] - prev["end"]).total_seconds()
        if g > 60:
            gaps += g
    flags = []
    if any(it["open"] for it in items):
        flags.append("Still on the clock")
    no_pin = sorted({it["job"].name for it in items if it["no_pin"]})
    if no_pin:
        flags.append(f"No site pin: {', '.join(no_pin)}")
    if any(it["no_points"] and not it["no_pin"] for it in items):
        flags.append("Some time has no location (phone location off or entered from the office)")
    gap = max((it["longest_gap"] for it in items), default=0)
    if gap >= LONG_GAP_MIN:
        flags.append(f"Longest stretch without a location: {round(gap)} min")
    clocked = sum((it["end"] - it["start"]).total_seconds() for it in items)
    jobs = []
    for it in ordered:
        if it["job"].name not in jobs:
            jobs.append(it["job"].name)
    return {
        "worker_id": worker.id, "name": worker.name, "role": worker.role.value,
        "first_in": _iso(ordered[0]["start"]), "last_out": None if ordered[-1]["open"] else _iso(ordered[-1]["end"]),
        "clocked_hours": _h(clocked), "on_job_hours": _h(tot[ON_JOB]), "travel_hours": _h(tot[TRAVEL]),
        "unknown_hours": _h(tot[UNKNOWN]), "between_entries_hours": _h(gaps),
        "still_on_clock": any(it["open"] for it in items), "jobs": jobs, "entries": len(items),
        "longest_gap_min": round(gap), "flags": flags,
    }


def daily_report(db: Session, company: Company, day: date) -> dict:
    a = _analyze(db, company, day)
    people = sorted((_summary(p["worker"], p["entries"]) for p in a["people"].values()), key=lambda r: r["name"])
    totals = {k: round(sum(p[k] for p in people), 2) for k in
              ("clocked_hours", "on_job_hours", "travel_hours", "unknown_hours", "between_entries_hours")}
    return {"date": day.isoformat(), "timezone": company.timezone, "people": people, "totals": totals}


def daily_detail(db: Session, company: Company, day: date, worker_id: str) -> dict | None:
    a = _analyze(db, company, day, worker_id)
    p = a["people"].get(worker_id)
    if p is None:
        return None
    items = sorted(p["entries"], key=lambda x: x["start"])
    segs, points, jobs = [], [], {}
    for it in items:
        job, e = it["job"], it["entry"]
        jobs[job.id] = {"id": job.id, "name": job.name, "lat": job.lat, "lng": job.lng, "radius_m": OFF_SITE_METERS}
        for a_, b_, s in it["segments"]:
            segs.append({"start": _iso(a_), "end": _iso(b_), "state": s, "job": job.name, "task": e.task.name,
                         "hours": _h((b_ - a_).total_seconds())})
        for x in it["points"]:
            points.append({"t": _iso(x.t), "lat": x.lat, "lng": x.lng, "on_site": on_site(x, job), "job": job.name})
    seen, uniq = set(), []
    for x in sorted(points, key=lambda x: x["t"]):
        k = (x["t"], round(x["lat"], 6), round(x["lng"], 6))
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return {
        "date": day.isoformat(), "timezone": company.timezone, "summary": _summary(p["worker"], items),
        "segments": segs, "points": uniq, "jobs": list(jobs.values()),
        "entries": [{"job": it["job"].name, "task": it["entry"].task.name, "start": _iso(it["start"]),
                     "end": None if it["open"] else _iso(it["end"])} for it in items],
    }


def daily_csv(db: Session, company: Company, day: date) -> tuple[str, str]:
    tz = ZoneInfo(company.timezone)
    a = _analyze(db, company, day)
    buf = io.StringIO()
    w = csv.writer(buf)
    row = lambda r: w.writerow([_cell(c) for c in r])  # noqa: E731
    fmt = lambda iso: _local(datetime.fromisoformat(iso[:-1]), tz).strftime("%H:%M") if iso else ""  # noqa: E731
    row(["Daily report", day.isoformat(), "Time zone", company.timezone])
    row([])
    row(["Person", "First in", "Last out", "Clocked hours", "On the job", "Travel", "Can't tell",
         "Unclocked between entries", "Jobs", "Notes"])
    people = sorted(a["people"].values(), key=lambda p: p["worker"].name)
    for p in people:
        s = _summary(p["worker"], p["entries"])
        row([s["name"], fmt(s["first_in"]), fmt(s["last_out"]) or "STILL ON THE CLOCK",
             f"{s['clocked_hours']:.2f}", f"{s['on_job_hours']:.2f}", f"{s['travel_hours']:.2f}",
             f"{s['unknown_hours']:.2f}", f"{s['between_entries_hours']:.2f}", "; ".join(s["jobs"]), "; ".join(s["flags"])])
    row([])
    row(["Person", "From", "To", "Hours", "Where", "Job", "Task"])
    label = {ON_JOB: "On the job", TRAVEL: "Travel", UNKNOWN: "Can't tell"}
    for p in people:
        for it in sorted(p["entries"], key=lambda x: x["start"]):
            for a_, b_, st in it["segments"]:
                row([p["worker"].name, _local(a_, tz).strftime("%H:%M"), _local(b_, tz).strftime("%H:%M"),
                     f"{(b_ - a_).total_seconds() / 3600:.2f}", label[st], it["job"].name, it["entry"].task.name])
    return buf.getvalue(), f"daily-report-{day.isoformat()}.csv"


# ---------- live ----------

def live_crews(db: Session, company: Company) -> dict:
    now = utcnow()
    open_entries = list(db.scalars(
        select(TimeEntry)
        .where(TimeEntry.company_id == company.id, TimeEntry.voided_at.is_(None), TimeEntry.clock_out.is_(None))
        .options(selectinload(TimeEntry.worker), selectinload(TimeEntry.task))
    ))
    by_phone: dict[str, list[TimeEntry]] = defaultdict(list)
    for e in open_entries:
        by_phone[e.entered_by_id].append(e)
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(by_phone)))}
    jobs = {j.id: j for j in db.scalars(select(Job).where(Job.id.in_({e.job_id for e in open_entries})))}
    since = min((e.clock_in for e in open_entries), default=now)
    pings = _pings_by_user(db, company.id, set(by_phone), max(since, now - timedelta(hours=16)), now)

    crews = []
    for uid, entries in by_phone.items():
        lead = users[uid]
        job_id = Counter(e.job_id for e in entries).most_common(1)[0][0]
        job = jobs[job_id]
        start = min(e.clock_in for e in entries)
        pts = [p for p in pings.get(uid, []) if p.t >= start - WINDOW_SLACK]
        for e in entries:
            if e.in_lat is not None and e.in_lng is not None:
                pts.append(Point(e.clock_in, e.in_lat, e.in_lng))
        pts.sort(key=lambda p: p.t)
        last = pts[-1] if pts else None
        dist = site_distance(last, job) if last else None
        crews.append({
            "lead_id": uid, "lead_name": lead.name, "lead_role": lead.role.value,
            "job_id": job.id, "job_name": job.name,
            "crew": sorted(({"worker_id": e.worker_id, "name": e.worker.name, "job": jobs[e.job_id].name,
                             "task": e.task.name, "since": _iso(e.clock_in)} for e in entries), key=lambda c: c["name"]),
            "last": None if last is None else {"t": _iso(last.t), "lat": last.lat, "lng": last.lng,
                                               "accuracy_m": last.accuracy,
                                               "age_min": round((now - last.t).total_seconds() / 60)},
            "distance_m": None if dist is None else round(dist),
            "on_site": None if last is None else on_site(last, job),
            "stale": last is None or (now - last.t) > timedelta(minutes=STALE_MIN),
            "trail": [{"lat": p.lat, "lng": p.lng} for p in pts if p.t >= now - timedelta(hours=2)][-80:],
        })
    crews.sort(key=lambda c: c["lead_name"])
    pinned = db.scalars(select(Job).where(Job.company_id == company.id, Job.lat.is_not(None), Job.lng.is_not(None),
                                          Job.status != JobStatus.complete))
    job_pins = {j.id: {"id": j.id, "name": j.name, "lat": j.lat, "lng": j.lng} for j in pinned}
    for j in jobs.values():
        if j.lat is not None and j.lng is not None:
            job_pins[j.id] = {"id": j.id, "name": j.name, "lat": j.lat, "lng": j.lng}
    return {"now": _iso(now), "radius_m": OFF_SITE_METERS, "crews": crews, "jobs": list(job_pins.values())}
