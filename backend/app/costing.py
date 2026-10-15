"""Estimate-versus-actual math. Pure functions over loaded rows, easy to test."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime

from .models import Job, JobStatus, TimeEntry, utcnow

NEAR_THRESHOLD = 0.90   # at or above 90% of estimated hours -> "near"
OFF_SITE_METERS = 400   # GPS stamp farther than this from the job pin -> flagged


def entry_hours(entry: TimeEntry, now: datetime | None = None) -> float:
    end = entry.clock_out or (now or utcnow())
    return max(0.0, (end - entry.clock_in).total_seconds() / 3600)


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def is_off_site(entry: TimeEntry, job: Job) -> bool:
    if job.lat is None or job.lng is None:
        return False
    for lat, lng in ((entry.in_lat, entry.in_lng), (entry.out_lat, entry.out_lng)):
        if lat is not None and lng is not None and distance_m(lat, lng, job.lat, job.lng) > OFF_SITE_METERS:
            return True
    return False


def _status(used_pct: float | None) -> str:
    if used_pct is None:
        return "no_estimate"
    if used_pct > 1.0:
        return "over"
    if used_pct >= NEAR_THRESHOLD:
        return "near"
    return "under"


def job_costing(job: Job, entries: list[TimeEntry], with_dollars: bool, now: datetime | None = None) -> dict:
    now = now or utcnow()
    closed_h: dict[str, float] = defaultdict(float)
    open_h: dict[str, float] = defaultdict(float)
    cost: dict[str, float] = defaultdict(float)
    on_site: set[str] = set()

    for e in entries:
        h = entry_hours(e, now)
        if e.clock_out is None:
            open_h[e.task_id] += h
            on_site.add(e.worker_id)
        else:
            closed_h[e.task_id] += h
        cost[e.task_id] += h * (e.worker.hourly_cost or 0.0)

    tasks = []
    for t in job.tasks:
        used = (closed_h[t.id] + open_h[t.id]) / t.estimated_hours if t.estimated_hours > 0 else None
        row = {
            "task_id": t.id,
            "name": t.name,
            "task_type": t.task_type,
            "estimated_hours": round(t.estimated_hours, 2),
            "actual_hours": round(closed_h[t.id], 2),
            "open_hours": round(open_h[t.id], 2),
            "hours_used_pct": None if used is None else round(used, 4),
            "status": _status(used),
        }
        if with_dollars:
            row["estimated_labor_cost"] = round(t.estimated_hours * job.estimated_labor_rate, 2)
            row["actual_labor_cost"] = round(cost[t.id], 2)
        tasks.append(row)

    est = sum(t.estimated_hours for t in job.tasks)
    act = sum(closed_h.values())
    opn = sum(open_h.values())
    out = {
        "job_id": job.id,
        "job_name": job.name,
        "status": job.status,
        "estimated_hours": round(est, 2),
        "actual_hours": round(act, 2),
        "open_hours": round(opn, 2),
        "hours_used_pct": round((act + opn) / est, 4) if est > 0 else None,
        "crew_on_site": len(on_site),
        "tasks": tasks,
    }
    if with_dollars:
        est_cost = round(est * job.estimated_labor_rate, 2)
        act_cost = round(sum(cost.values()), 2)
        out |= {
            "contract_amount": job.contract_amount,
            "estimated_labor_cost": est_cost,
            "actual_labor_cost": act_cost,
            "labor_cost_used_pct": round(act_cost / est_cost, 4) if est_cost > 0 else None,
            # Only meaningful once the job is finished; mid-job, watch the
            # per-task hours instead.
            "labor_variance": round(act_cost - est_cost, 2) if job.status == JobStatus.complete else None,
        }
    return out
