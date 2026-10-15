"""Load made-up sample data for local development.

Everything here is fictional: company, people, jobs, hours and rates. No
customer data belongs in this file.

    python -m app.seed          # from backend/, wipes and reloads the dev DB
"""
import random
import uuid
from datetime import datetime, timedelta, time

from . import config
from .auth import hash_password
from .db import Base, SessionLocal, engine
from .models import (
    Company, CourtType, Job, JobStatus, JobTask, Role, ScopeType, TaskType, TimeEntry, User, utcnow,
)

# Dev tokens. Sign in on the front end by pasting one of these.
# Sample sign-ins (development only). Every sample account uses DEV_PASSWORD.
DEV_PASSWORD = "courtfield-dev"
ACCOUNTS = {
    "dev-gm": ("Sam Ortiz", Role.gm, 0),
    "dev-owner": ("Pat Lin", Role.owner, 0),
    "dev-estimator": ("Riley Shaw", Role.estimator, 0),
    "dev-lead-1": ("Marco Diaz", Role.crew_lead, 38),
    "dev-lead-2": ("Jordan Kemp", Role.crew_lead, 36),
}
CREW = [("Luis Vega", 27), ("Tyler Brooks", 25), ("Andre Wells", 26), ("Kenny Ruiz", 24)]

JOBS = [
    # name, client, court, scope, status, contract, rate, lat, lng, tasks[(type, name, est_hours)], overrun factor
    ("Palm Hollow HOA – 4 Pickleball Resurface", "Palm Hollow HOA", CourtType.pickleball, ScopeType.resurfacing,
     JobStatus.complete, 28500, 32, 26.531, -80.091,
     [(TaskType.prep, "Pressure wash & prep", 16), (TaskType.crack_fill, "Crack repair", 12),
      (TaskType.resurfacer, "Acrylic resurfacer (2 coats)", 24), (TaskType.color_coat, "Color coats (2)", 24),
      (TaskType.lines, "Line striping", 10), (TaskType.nets_posts, "Nets & posts", 4)], 1.18),
    ("Westgate Park – Tennis Court Repair", "City of Westgate (sample)", CourtType.tennis, ScopeType.repair,
     JobStatus.complete, 9800, 32, 26.552, -80.120,
     [(TaskType.prep, "Clean & prep", 6), (TaskType.crack_fill, "Crack fill + birdbath patch", 14),
      (TaskType.color_coat, "Spot color & blend", 8), (TaskType.lines, "Re-stripe", 6)], 0.94),
    ("Coral Ridge Academy – 2 Tennis New Build", "Coral Ridge Academy (sample)", CourtType.tennis, ScopeType.new_construction,
     JobStatus.active, 142000, 33, 26.512, -80.074,
     [(TaskType.prep, "Base check & flood test", 10), (TaskType.resurfacer, "Resurfacer (2 coats)", 30),
      (TaskType.color_coat, "Color coats (2)", 28), (TaskType.lines, "Lines", 12),
      (TaskType.fence, "10' chain-link fence", 60), (TaskType.nets_posts, "Posts & nets", 6)], None),
    ("Seabreeze Club – Basketball Resurface", "Seabreeze Club (sample)", CourtType.basketball, ScopeType.resurfacing,
     JobStatus.scheduled, 11200, 32, 26.578, -80.065,
     [(TaskType.prep, "Pressure wash & prep", 6), (TaskType.crack_fill, "Crack repair", 6),
      (TaskType.resurfacer, "Resurfacer (1 coat)", 8), (TaskType.color_coat, "Color coats (2)", 10),
      (TaskType.lines, "Lines", 5)], None),
]


def _workday_entries(rng, job, tasks_hours, crew, start_day, lead):
    """Spread total hours per task across crew-days, 8-hour days, in task order."""
    entries, day, slot_hours = [], start_day, {w.id: 0.0 for w in crew}
    for task, hours in tasks_hours:
        remaining = hours
        while remaining > 0.1:
            for w in crew:
                if remaining <= 0.1:
                    break
                used = slot_hours[w.id]
                if used >= 8:
                    continue
                chunk = min(remaining, 8 - used, rng.choice([2, 3, 4, 4, 5]))
                start = datetime.combine(day, time(11, 0)) + timedelta(hours=used)  # 7:00 ET
                end = start + timedelta(hours=chunk)
                entries.append(TimeEntry(
                    id=str(uuid.uuid4()), company_id=job.company_id, job_id=job.id, task_id=task.id,
                    worker_id=w.id, entered_by_id=lead.id, clock_in=start, clock_out=end,
                    in_lat=job.lat + rng.uniform(-0.0004, 0.0004), in_lng=job.lng + rng.uniform(-0.0004, 0.0004),
                    out_lat=job.lat, out_lng=job.lng, client_updated_at=end,
                ))
                slot_hours[w.id] += chunk
                remaining -= chunk
            if all(v >= 8 for v in slot_hours.values()):
                day += timedelta(days=1)
                slot_hours = {w.id: 0.0 for w in crew}
    return entries


def dev_email(key: str) -> str:
    """dev-lead-1 -> lead-1@sample.test"""
    return f"{key.removeprefix('dev-')}@sample.test"


def seed() -> None:
    if not config.IS_DEV:
        raise SystemExit("Refusing to load sample data: COURTFIELD_ENV is not 'dev'. This would wipe the database.")
    rng = random.Random(7)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()

    co = Company(name="Sample Court Builders")
    db.add(co)
    db.flush()

    users = {}
    pw = hash_password(DEV_PASSWORD)
    for key, (name, role, cost) in ACCOUNTS.items():
        users[key] = User(company_id=co.id, name=name, role=role, hourly_cost=cost,
                          email=dev_email(key), password_hash=pw)
    crew = [User(company_id=co.id, name=n, role=Role.crew, hourly_cost=c) for n, c in CREW]
    db.add_all([*users.values(), *crew])

    # A second tenant, so isolation is visible in development too.
    other = Company(name="Other Contractor (tenant isolation check)")
    db.add(other)
    db.flush()
    db.add(User(company_id=other.id, name="Other GM", role=Role.gm, email=dev_email("dev-other-gm"), password_hash=pw))
    db.flush()

    today = utcnow().date()
    lead1, lead2 = users["dev-lead-1"], users["dev-lead-2"]
    team_a = [lead1, crew[0], crew[1]]
    team_b = [lead2, crew[2], crew[3]]

    for i, (name, client, court, scope, status, contract, rate, lat, lng, tasks, factor) in enumerate(JOBS):
        job = Job(company_id=co.id, name=name, client=client, address="Sample address", lat=lat, lng=lng,
                  court_type=court, scope_type=scope, status=status, contract_amount=contract, estimated_labor_rate=rate)
        for n, (tt, tname, est) in enumerate(tasks):
            job.tasks.append(JobTask(company_id=co.id, task_type=tt, name=tname, estimated_hours=est, sort_order=n))
        db.add(job)
        db.flush()

        team, lead = (team_a, lead1) if i % 2 == 0 else (team_b, lead2)
        if status == JobStatus.complete:
            start = today - timedelta(days=30 - i * 12)
            actual = [(t, t.estimated_hours * factor * rng.uniform(0.85, 1.15)) for t in job.tasks]
            db.add_all(_workday_entries(rng, job, actual, team, start, lead))
        elif status == JobStatus.active:
            # Done: first task (over), second (partly). Crew on site right now.
            done = [(job.tasks[0], job.tasks[0].estimated_hours * 1.35), (job.tasks[1], job.tasks[1].estimated_hours * 0.6)]
            db.add_all(_workday_entries(rng, job, done, team, today - timedelta(days=4), lead))
            now = utcnow()
            for w in team:
                db.add(TimeEntry(
                    id=str(uuid.uuid4()), company_id=co.id, job_id=job.id, task_id=job.tasks[1].id,
                    worker_id=w.id, entered_by_id=lead.id, clock_in=now - timedelta(hours=2, minutes=15),
                    in_lat=lat, in_lng=lng, client_updated_at=now - timedelta(hours=2, minutes=15),
                ))
    db.commit()
    db.close()
    print(f"Seeded sample data. Sign in as any of {', '.join(dev_email(k) for k in ACCOUNTS)} with password {DEV_PASSWORD}")


if __name__ == "__main__":
    seed()
