import uuid
from datetime import datetime, timedelta, timezone

from conftest import auth

GM, LEAD, OWNER, EST, OTHER = "dev-gm", "dev-lead-2", "dev-owner", "dev-estimator", "dev-other-gm"


def now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.isoformat()


def job_named(client, fragment, token=GM):
    return next(j for j in client.get("/api/jobs", headers=auth(token)).json() if fragment in j["name"])


def worker_named(client, name):
    return next(w for w in client.get("/api/crew", headers=auth(LEAD)).json() if w["name"] == name)


def entry(job, task, worker, clock_in, clock_out=None, updated=None, **extra):
    return {
        "id": extra.pop("id", str(uuid.uuid4())), "job_id": job["id"], "task_id": task["id"],
        "worker_id": worker["id"], "clock_in": iso(clock_in),
        "clock_out": iso(clock_out) if clock_out else None,
        "client_updated_at": iso(updated or clock_out or clock_in), **extra,
    }


def sync(client, *entries, token=LEAD):
    r = client.post("/api/time/sync", json={"entries": list(entries)}, headers=auth(token))
    assert r.status_code == 200, r.text
    return [x["status"] for x in r.json()["results"]], r.json()["results"]


# ---------- auth and roles ----------

def test_requires_token(client):
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/jobs", headers=auth("nope")).status_code == 401


def test_crew_lead_never_sees_dollars(client):
    jobs = client.get("/api/jobs", headers=auth(LEAD)).json()
    assert jobs and all("contract_amount" not in j and "estimated_labor_rate" not in j for j in jobs)
    costing = client.get(f"/api/jobs/{jobs[0]['id']}/costing", headers=auth(LEAD)).json()
    assert "actual_labor_cost" not in costing and "actual_labor_cost" not in costing["tasks"][0]
    assert client.get("/api/jobs/summary", headers=auth(LEAD)).status_code == 403


def test_crew_lead_only_sees_open_jobs(client):
    statuses = {j["status"] for j in client.get("/api/jobs", headers=auth(LEAD)).json()}
    assert "complete" not in statuses


def test_owner_is_read_only(client):
    assert client.get("/api/jobs/summary", headers=auth(OWNER)).status_code == 200
    assert client.post("/api/time/sync", json={"entries": []}, headers=auth(OWNER)).status_code == 403
    assert client.post("/api/jobs", json={}, headers=auth(OWNER)).status_code == 403


def test_estimator_creates_job_crew_lead_cannot(client):
    body = {"name": "Test Job", "court_type": "pickleball", "scope_type": "repair",
            "estimated_labor_rate": 30, "tasks": [{"task_type": "prep", "name": "Prep", "estimated_hours": 4}]}
    assert client.post("/api/jobs", json=body, headers=auth(LEAD)).status_code == 403
    r = client.post("/api/jobs", json=body, headers=auth(EST))
    assert r.status_code == 201 and r.json()["tasks"][0]["estimated_hours"] == 4


# ---------- tenant isolation ----------

def test_other_tenant_sees_nothing(client):
    job = job_named(client, "Seabreeze")
    assert client.get("/api/jobs", headers=auth(OTHER)).json() == []
    assert client.get(f"/api/jobs/{job['id']}", headers=auth(OTHER)).status_code == 404
    assert client.get(f"/api/jobs/{job['id']}/costing", headers=auth(OTHER)).status_code == 404
    assert client.get("/api/time", headers=auth(OTHER)).json() == []


def test_other_tenant_cannot_write_time_to_our_job(client):
    job = job_named(client, "Seabreeze")
    w = worker_named(client, "Andre Wells")
    statuses, results = sync(client, entry(job, job["tasks"][0], w, now() - timedelta(hours=1)), token=OTHER)
    assert statuses == ["rejected"] and results[0]["reason"] == "unknown job"


# ---------- syncing field time ----------

def test_clock_in_out_is_idempotent_and_counts(client):
    job = job_named(client, "Seabreeze")
    task, w = job["tasks"][0], worker_named(client, "Andre Wells")
    start = now() - timedelta(hours=3)
    e = entry(job, task, w, start)

    assert sync(client, e)[0] == ["saved"]
    assert sync(client, e)[0] == ["unchanged"]            # resend after flaky signal
    cost = client.get(f"/api/jobs/{job['id']}/costing", headers=auth(GM)).json()
    assert cost["crew_on_site"] == 1 and cost["tasks"][0]["open_hours"] > 2.9

    closed = {**e, "clock_out": iso(start + timedelta(hours=3)), "client_updated_at": iso(start + timedelta(hours=3))}
    assert sync(client, closed)[0] == ["saved"]
    cost = client.get(f"/api/jobs/{job['id']}/costing", headers=auth(GM)).json()
    t0 = cost["tasks"][0]
    assert cost["crew_on_site"] == 0 and t0["actual_hours"] == 3.0
    assert t0["hours_used_pct"] == 0.5 and t0["status"] == "under"   # 3 of 6 estimated
    assert t0["actual_labor_cost"] == 3 * 26                            # Andre's cost rate


def test_older_edit_is_stale(client):
    job = job_named(client, "Seabreeze")
    w = worker_named(client, "Andre Wells")
    start = now() - timedelta(hours=4)
    newer = entry(job, job["tasks"][0], w, start, start + timedelta(hours=2), updated=start + timedelta(hours=3))
    older = {**newer, "clock_out": iso(start + timedelta(hours=1)), "client_updated_at": iso(start + timedelta(hours=1))}
    assert sync(client, newer)[0] == ["saved"]
    assert sync(client, older)[0] == ["stale"]


def test_switching_tasks_in_one_offline_batch(client):
    job = job_named(client, "Seabreeze")
    a, b = job["tasks"][0], job["tasks"][1]
    w = worker_named(client, "Kenny Ruiz")
    t0 = now() - timedelta(hours=5)
    switch = t0 + timedelta(hours=2)
    first = entry(job, a, w, t0)
    assert sync(client, first)[0] == ["saved"]
    # Offline: close task A and start task B at the same moment; phone sends B first.
    close_a = {**first, "clock_out": iso(switch), "client_updated_at": iso(switch)}
    open_b = entry(job, b, w, switch, updated=switch + timedelta(seconds=1))
    assert sync(client, open_b, close_a)[0] == ["saved", "saved"]


def test_overlap_rejected(client):
    job = job_named(client, "Seabreeze")
    w = worker_named(client, "Andre Wells")
    t0 = now() - timedelta(hours=6)
    assert sync(client, entry(job, job["tasks"][0], w, t0, t0 + timedelta(hours=3)))[0] == ["saved"]
    statuses, results = sync(client, entry(job, job["tasks"][1], w, t0 + timedelta(hours=2), t0 + timedelta(hours=4)))
    assert statuses == ["rejected"] and "overlaps" in results[0]["reason"]


def test_bad_entries_rejected(client):
    job = job_named(client, "Seabreeze")
    other_job = job_named(client, "Coral Ridge")
    w = worker_named(client, "Andre Wells")
    t0 = now() - timedelta(hours=2)
    cases = [
        (entry(job, job["tasks"][0], w, t0, t0 - timedelta(minutes=5)), "before clock-in"),
        (entry(job, other_job["tasks"][0], w, t0), "does not belong"),
        (entry(job, job["tasks"][0], w, now() + timedelta(hours=2)), "future"),
        (entry(job, job["tasks"][0], w, t0 - timedelta(hours=20), t0), "16 hours"),
    ]
    for e, reason in cases:
        statuses, results = sync(client, e)
        assert statuses == ["rejected"] and reason in results[0]["reason"], (reason, results)


def test_off_site_flag(client):
    job = job_named(client, "Seabreeze")
    w = worker_named(client, "Andre Wells")
    t0 = now() - timedelta(hours=2)
    e = entry(job, job["tasks"][0], w, t0, t0 + timedelta(hours=1), in_lat=27.0, in_lng=-80.5)
    sync(client, e)
    rows = client.get(f"/api/time?job_id={job['id']}", headers=auth(GM)).json()
    assert next(r for r in rows if r["id"] == e["id"])["off_site"] is True


# ---------- dashboard ----------

def test_summary_flags_overrun_on_completed_job(client):
    summary = client.get("/api/jobs/summary", headers=auth(GM)).json()
    palm = next(j for j in summary if "Palm Hollow" in j["job_name"])
    assert palm["hours_used_pct"] > 1.0
    assert palm["labor_variance"] is not None
    active = next(j for j in summary if j["status"] == "active")
    assert active["labor_variance"] is None and active["crew_on_site"] == 3
