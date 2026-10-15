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


# ---------- editing jobs ----------

def test_edit_job_add_rename_reorder_remove(client):
    job = job_named(client, "Seabreeze")
    edit = client.get(f"/api/jobs/{job['id']}/edit", headers=auth(EST)).json()
    t = edit["tasks"]
    body = {k: edit[k] for k in ("name", "client", "address", "lat", "lng", "court_type", "scope_type", "contract_amount", "estimated_labor_rate")}
    body["contract_amount"] = 12500
    body["tasks"] = [
        {**t[1], "estimated_hours": 9},                                     # moved to first, hours changed
        {**t[0], "name": "Pressure wash, blow off & prep"},                 # renamed
        {"task_type": "nets_posts", "name": "New nets", "estimated_hours": 2},  # added
        *t[2:4],                                                            # t[4] (Lines) removed
    ]
    r = client.put(f"/api/jobs/{job['id']}", json=body, headers=auth(EST))
    assert r.status_code == 200, r.text
    out = r.json()
    assert [x["name"] for x in out["tasks"]] == [t[1]["name"], "Pressure wash, blow off & prep", "New nets", t[2]["name"], t[3]["name"]]
    assert out["tasks"][0]["estimated_hours"] == 9 and out["contract_amount"] == 12500
    assert out["status"] == "scheduled"


def test_cannot_remove_task_with_logged_time(client):
    job = job_named(client, "Coral Ridge")  # first task has crew hours
    edit = client.get(f"/api/jobs/{job['id']}/edit", headers=auth(GM)).json()
    assert edit["tasks"][0]["has_time"] is True and edit["tasks"][-1]["has_time"] is False
    body = {k: edit[k] for k in ("name", "client", "address", "lat", "lng", "court_type", "scope_type", "contract_amount", "estimated_labor_rate")}
    body["tasks"] = edit["tasks"][1:]
    r = client.put(f"/api/jobs/{job['id']}", json=body, headers=auth(GM))
    assert r.status_code == 409 and "Base check" in r.json()["detail"]
    # Nothing changed
    assert len(client.get(f"/api/jobs/{job['id']}/edit", headers=auth(GM)).json()["tasks"]) == len(edit["tasks"])


def test_edit_rejects_foreign_task_and_wrong_roles(client):
    a, b = job_named(client, "Seabreeze"), job_named(client, "Coral Ridge")
    edit = client.get(f"/api/jobs/{a['id']}/edit", headers=auth(GM)).json()
    body = {k: edit[k] for k in ("name", "client", "address", "lat", "lng", "court_type", "scope_type", "contract_amount", "estimated_labor_rate")}
    body["tasks"] = [*edit["tasks"], {**b["tasks"][0]}]
    assert client.put(f"/api/jobs/{a['id']}", json=body, headers=auth(GM)).status_code == 422
    body["tasks"] = edit["tasks"]
    for token in (LEAD, OWNER):
        assert client.put(f"/api/jobs/{a['id']}", json=body, headers=auth(token)).status_code == 403
    assert client.put(f"/api/jobs/{a['id']}", json=body, headers=auth(OTHER)).status_code == 404


def test_estimator_cannot_create_active_job(client):
    body = {"name": "X", "court_type": "tennis", "scope_type": "repair", "status": "active", "tasks": []}
    assert client.post("/api/jobs", json=body, headers=auth(EST)).json()["status"] == "scheduled"
    assert client.post("/api/jobs", json=body, headers=auth(GM)).json()["status"] == "active"


# ---------- office corrections ----------

def _open_coral_entry(client):
    rows = client.get("/api/time?open_only=true", headers=auth(GM)).json()
    return next(r for r in rows if r["worker_name"] == "Luis Vega")


def test_gm_adds_time_for_dead_phone_day(client):
    job = job_named(client, "Seabreeze")
    w = worker_named(client, "Andre Wells")
    t0 = now() - timedelta(days=1, hours=6)
    body = {"job_id": job["id"], "task_id": job["tasks"][0]["id"], "worker_id": w["id"],
            "clock_in": iso(t0), "clock_out": iso(t0 + timedelta(hours=4)), "reason": "Crew lead's phone was dead"}
    assert client.post("/api/time/office", json=body, headers=auth(LEAD)).status_code == 403
    assert client.post("/api/time/office", json=body, headers=auth(EST)).status_code == 403
    r = client.post("/api/time/office", json=body, headers=auth(GM))
    assert r.status_code == 201, r.text
    cost = client.get(f"/api/jobs/{job['id']}/costing", headers=auth(GM)).json()
    assert cost["tasks"][0]["actual_hours"] == 4.0
    hist = client.get(f"/api/time/{r.json()['id']}/history", headers=auth(OWNER)).json()
    assert [h["action"] for h in hist] == ["add"] and hist[0]["changed_by"] == "Sam Ortiz"
    # Missing reason is refused
    assert client.post("/api/time/office", json={**body, "reason": ""}, headers=auth(GM)).status_code == 422


def test_gm_fixes_entry_and_phone_cannot_undo_it(client):
    e = _open_coral_entry(client)
    fixed_in = now() - timedelta(hours=1)
    r = client.patch(f"/api/time/{e['id']}", json={"clock_in": iso(fixed_in), "reason": "Arrived at 1pm, not noon"}, headers=auth(GM))
    assert r.status_code == 200, r.text
    assert r.json()["edited"] is True and r.json()["clock_out"] is None

    # The crew lead's phone still has the old clock-in and now clocks out.
    phone = {"id": e["id"], "job_id": e["job_id"], "task_id": e["task_id"], "worker_id": e["worker_id"],
             "clock_in": e["clock_in"], "clock_out": iso(now()), "client_updated_at": iso(now())}
    statuses, _ = sync(client, phone, token="dev-lead-1")
    assert statuses == ["saved"]
    row = next(x for x in client.get("/api/time", headers=auth(GM)).json() if x["id"] == e["id"])
    assert row["clock_in"].startswith(fixed_in.strftime("%Y-%m-%dT%H:%M")) and row["clock_out"] is not None
    # Once closed by the office's terms, further phone edits are stale.
    statuses, _ = sync(client, {**phone, "clock_out": iso(now() - timedelta(minutes=5)), "client_updated_at": iso(now())}, token="dev-lead-1")
    assert statuses == ["stale"]

    hist = client.get(f"/api/time/{e['id']}/history", headers=auth(GM)).json()
    assert hist[0]["action"] == "edit" and hist[0]["before"]["clock_in"] != hist[0]["after"]["clock_in"]


def test_gm_removes_entry_keeps_record(client):
    e = _open_coral_entry(client)
    job_id = e["job_id"]
    before = client.get(f"/api/jobs/{job_id}/costing", headers=auth(GM)).json()["crew_on_site"]
    r = client.post(f"/api/time/{e['id']}/remove", json={"reason": "Clocked in by mistake"}, headers=auth(GM))
    assert r.status_code == 200 and r.json()["removed"] is True
    after = client.get(f"/api/jobs/{job_id}/costing", headers=auth(GM)).json()["crew_on_site"]
    assert after == before - 1
    ids = [x["id"] for x in client.get(f"/api/time?job_id={job_id}", headers=auth(GM)).json()]
    assert e["id"] not in ids
    removed = [x for x in client.get(f"/api/time?job_id={job_id}&include_removed=true", headers=auth(GM)).json() if x["id"] == e["id"]]
    assert removed and removed[0]["removed_reason"] == "Clocked in by mistake"
    # Phone resending it is told the office removed it
    phone = {k: e[k] for k in ("id", "job_id", "task_id", "worker_id", "clock_in")} | {"clock_out": iso(now()), "client_updated_at": iso(now())}
    statuses, results = sync(client, phone, token="dev-lead-1")
    assert statuses == ["rejected"] and "removed" in results[0]["reason"]
    # Worker can be clocked in again (removed entry no longer blocks overlap)
    statuses, _ = sync(client, {**phone, "id": str(uuid.uuid4()), "clock_out": None}, token="dev-lead-1")
    assert statuses == ["saved"]


def test_correction_rules(client):
    e = _open_coral_entry(client)
    bad = client.patch(f"/api/time/{e['id']}", json={"clock_out": iso(now() - timedelta(hours=5)), "reason": "typo test"}, headers=auth(GM))
    assert bad.status_code == 422 and "before clock-in" in bad.json()["detail"]
    assert client.patch(f"/api/time/{e['id']}", json={"reason": "nothing"}, headers=auth(GM)).status_code == 422
    assert client.patch(f"/api/time/{e['id']}", json={"clock_out": iso(now()), "reason": "x"}, headers=auth(GM)).status_code == 422
    other_gm = client.patch(f"/api/time/{e['id']}", json={"clock_out": iso(now()), "reason": "Done for day"}, headers=auth(OTHER))
    assert other_gm.status_code == 404
