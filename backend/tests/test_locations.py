import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from conftest import auth

from app.tracking import ON_JOB, TRAVEL, UNKNOWN, Point, segments

GM, EST, WH, LEAD, LEAD2, OWNER, OTHER = ("dev-gm", "dev-estimator", "dev-warehouse", "dev-lead-1", "dev-lead-2",
                                          "dev-owner", "dev-other-gm")


def z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def now() -> datetime:
    return datetime.now(timezone.utc)


def job_named(client, frag):
    return next(j for j in client.get("/api/jobs", headers=auth(GM)).json() if frag in j["name"])


def crew(client):
    return {c["name"]: c for c in client.get("/api/crew", headers=auth(GM)).json()}


def ping(t, lat, lng, acc=10):
    return {"id": str(uuid.uuid4()), "recorded_at": z(t), "lat": lat, "lng": lng, "accuracy_m": acc}


# ---------- pure math ----------

JOB = SimpleNamespace(lat=26.5, lng=-80.0)
NOPIN = SimpleNamespace(lat=None, lng=None)
T0 = datetime(2026, 10, 16, 12, 0)
FAR = (26.55, -80.0)   # ~5.5 km north


def at(m, where=None, acc=None):
    lat, lng = where or (JOB.lat, JOB.lng)
    return Point(T0 + timedelta(minutes=m), lat, lng, acc)


def totals(segs):
    out = {ON_JOB: 0, TRAVEL: 0, UNKNOWN: 0}
    for a, b, s in segs:
        out[s] += (b - a).total_seconds() / 60
    return out


def test_segments_drive_then_on_site():
    pts = [at(0, FAR), at(10, (26.52, -80.0)), at(25), at(60), at(120)]
    t = totals(segments(T0, T0 + timedelta(minutes=120), pts, JOB))
    assert t == {ON_JOB: 95, TRAVEL: 25, UNKNOWN: 0}


def test_segments_supply_run_and_locked_phone_on_site():
    # on site, gap with phone locked (still on site), leaves for supplies, back
    pts = [at(0), at(90), at(100, FAR), at(140, FAR), at(150), at(180)]
    t = totals(segments(T0, T0 + timedelta(minutes=180), pts, JOB))
    assert t[ON_JOB] == 90 + 30 and t[TRAVEL] == 60


def test_segments_cant_tell():
    end = T0 + timedelta(minutes=120)
    assert totals(segments(T0, end, [at(10)], NOPIN))[UNKNOWN] == 120
    assert totals(segments(T0, end, [], JOB))[UNKNOWN] == 120
    # first point 45 min after clock-in, last 50 min before clock-out
    t = totals(segments(T0, end, [at(45), at(70)], JOB))
    assert t == {ON_JOB: 25, TRAVEL: 0, UNKNOWN: 95}


def test_gps_accuracy_gives_some_slack():
    edge = (JOB.lat + 0.0042, JOB.lng)  # ~467 m, just outside 400 m
    end = T0 + timedelta(minutes=30)
    assert totals(segments(T0, end, [at(0), at(30, edge)], JOB))[TRAVEL] == 30
    assert totals(segments(T0, end, [at(0), at(30, edge, acc=100)], JOB))[ON_JOB] == 30


# ---------- pings ----------

def test_pings_only_while_own_crew_is_clocked_in(client):
    coral = job_named(client, "Coral Ridge")
    t = now()
    body = {"pings": [
        ping(t - timedelta(minutes=1), coral["lat"], coral["lng"]),          # on the clock
        ping(t - timedelta(hours=5), coral["lat"], coral["lng"]),            # before clock-in
        ping(t + timedelta(hours=1), coral["lat"], coral["lng"]),            # future
    ]}
    r = client.post("/api/locations", json=body, headers=auth(LEAD))
    assert r.status_code == 200
    assert r.json()["saved"] == [body["pings"][0]["id"]]
    assert set(r.json()["dropped"]) == {body["pings"][1]["id"], body["pings"][2]["id"]}
    # resend is harmless
    again = client.post("/api/locations", json={"pings": body["pings"][:1]}, headers=auth(LEAD)).json()
    assert again["saved"] == [body["pings"][0]["id"]]
    # lead 2 has nobody on the clock today: nothing is kept
    r2 = client.post("/api/locations", json={"pings": [ping(t, 26.5, -80.0)]}, headers=auth(LEAD2)).json()
    assert r2["saved"] == [] and len(r2["dropped"]) == 1
    for who in (WH, EST, OWNER):
        assert client.post("/api/locations", json={"pings": []}, headers=auth(who)).status_code == 403


def test_location_notice(client):
    me = client.get("/api/me", headers=auth(LEAD)).json()
    assert me["location_notice_at"] is None and me["sees_locations"] is False
    assert client.post("/api/me/location-notice", headers=auth(LEAD)).status_code == 200
    assert client.get("/api/me", headers=auth(LEAD)).json()["location_notice_at"]
    assert client.get("/api/me", headers=auth(GM)).json()["sees_locations"] is True


# ---------- live ----------

def test_live_map(client):
    r = client.get("/api/crews/live", headers=auth(GM))
    assert r.status_code == 200
    crews = r.json()["crews"]
    assert len(crews) == 1
    c = crews[0]
    assert c["lead_name"] == "Marco Diaz" and "Coral Ridge" in c["job_name"]
    assert {m["name"] for m in c["crew"]} == {"Marco Diaz", "Luis Vega", "Tyler Brooks"}
    assert c["on_site"] is True and c["distance_m"] < 400 and c["stale"] is False and c["trail"]
    assert client.get("/api/crews/live", headers=auth(OWNER)).status_code == 200
    for who in (EST, WH, LEAD):
        assert client.get("/api/crews/live", headers=auth(who)).status_code == 403
    assert client.get("/api/crews/live", headers=auth(OTHER)).json()["crews"] == []


# ---------- daily report ----------

def _today(client):
    tz = ZoneInfo(client.get("/api/company", headers=auth(GM)).json()["timezone"])
    return tz, datetime.now(tz).date()


def test_daily_report_today(client):
    tz, today = _today(client)
    r = client.get(f"/api/reports/daily?date={today}", headers=auth(GM))
    assert r.status_code == 200
    people = {p["name"]: p for p in r.json()["people"]}
    luis = people["Luis Vega"]
    assert luis["still_on_clock"] and luis["last_out"] is None
    parts = luis["on_job_hours"] + luis["travel_hours"] + luis["unknown_hours"]
    assert abs(parts - luis["clocked_hours"]) < 0.02
    if (datetime.now(tz) - timedelta(hours=2, minutes=20)).date() == today:
        assert luis["travel_hours"] == 0.5 and luis["unknown_hours"] == 0
        assert luis["longest_gap_min"] >= 40 and any("Longest stretch" in f for f in luis["flags"])
    for who in (EST, WH, LEAD):
        assert client.get("/api/reports/daily", headers=auth(who)).status_code == 403
    assert client.get("/api/reports/daily", headers=auth(OTHER)).json()["people"] == []
    assert client.get("/api/reports/daily?date=yesterday", headers=auth(GM)).status_code == 422


def test_daily_detail_and_csv(client):
    _, today = _today(client)
    luis = crew(client)["Luis Vega"]
    d = client.get(f"/api/reports/daily/{luis['id']}?date={today}", headers=auth(GM))
    assert d.status_code == 200
    d = d.json()
    assert d["segments"] and d["points"] and d["jobs"][0]["lat"]
    assert {s["state"] for s in d["segments"]} <= {ON_JOB, TRAVEL, UNKNOWN}
    assert client.get(f"/api/reports/daily/{luis['id']}?date={today}", headers=auth(OTHER)).status_code == 404
    assert client.get(f"/api/reports/daily/{luis['id']}?date=2020-01-01", headers=auth(GM)).status_code == 404
    csv = client.get(f"/api/reports/daily.csv?date={today}", headers=auth(GM))
    assert csv.status_code == 200 and "Luis Vega" in csv.text and "On the job" in csv.text


def test_travel_between_jobs_and_unclocked_gap(client):
    """Clock in on one job, drive to another with the crew still clocked in,
    then a break between entries."""
    coral, seabreeze = job_named(client, "Coral Ridge"), job_named(client, "Seabreeze")
    kenny = crew(client)["Kenny Ruiz"]
    _, today = _today(client)
    # A morning yesterday-or-earlier would cross pay weeks; use 3 days ago, 7:00 local.
    tz = ZoneInfo(client.get("/api/company", headers=auth(GM)).json()["timezone"])
    day = today - timedelta(days=3)
    start = datetime(day.year, day.month, day.day, 7, 0, tzinfo=tz)
    e1 = {"id": str(uuid.uuid4()), "job_id": coral["id"], "task_id": coral["tasks"][0]["id"], "worker_id": kenny["id"],
          "clock_in": z(start), "clock_out": z(start + timedelta(hours=2)), "in_lat": coral["lat"], "in_lng": coral["lng"],
          "out_lat": seabreeze["lat"], "out_lng": seabreeze["lng"], "client_updated_at": z(start + timedelta(hours=2))}
    e2 = {"id": str(uuid.uuid4()), "job_id": seabreeze["id"], "task_id": seabreeze["tasks"][0]["id"], "worker_id": kenny["id"],
          "clock_in": z(start + timedelta(hours=2, minutes=30)), "clock_out": z(start + timedelta(hours=4, minutes=30)),
          "in_lat": seabreeze["lat"], "in_lng": seabreeze["lng"], "out_lat": seabreeze["lat"], "out_lng": seabreeze["lng"],
          "client_updated_at": z(start + timedelta(hours=4, minutes=30))}
    res = client.post("/api/time/sync", json={"entries": [e1, e2]}, headers=auth(LEAD2)).json()["results"]
    assert all(r["status"] == "saved" for r in res), res
    # on site at Coral until 8:15, then driving to Seabreeze (phone open at 8:15 and 8:45)
    pings = [ping(start + timedelta(minutes=75), coral["lat"], coral["lng"]),
             ping(start + timedelta(minutes=105), (coral["lat"] + seabreeze["lat"]) / 2, coral["lng"])]
    assert len(client.post("/api/locations", json={"pings": pings}, headers=auth(LEAD2)).json()["saved"]) == 2
    rep = client.get(f"/api/reports/daily?date={day}", headers=auth(GM)).json()
    k = next(p for p in rep["people"] if p["name"] == "Kenny Ruiz")
    assert k["clocked_hours"] == 4 and k["on_job_hours"] == 3.25 and k["travel_hours"] == 0.75
    assert k["between_entries_hours"] == 0.5 and k["jobs"] == [coral["name"], seabreeze["name"]]


# ---------- site pin ----------

def test_crew_lead_sets_missing_site_pin(client):
    body = {"name": "No pin yet", "court_type": "tennis", "scope_type": "repair", "estimated_labor_rate": 30,
            "tasks": [{"task_type": "prep", "name": "Prep", "estimated_hours": 4}]}
    job = client.post("/api/jobs", json=body, headers=auth(EST)).json()
    assert job["lat"] is None
    r = client.post(f"/api/jobs/{job['id']}/site", json={"lat": 26.6, "lng": -80.1}, headers=auth(LEAD))
    assert r.status_code == 200 and r.json()["lat"] == 26.6
    assert client.post(f"/api/jobs/{job['id']}/site", json={"lat": 26.7, "lng": -80.1}, headers=auth(LEAD)).status_code == 409
    assert client.post(f"/api/jobs/{job['id']}/site", json={"lat": 26.7, "lng": -80.1}, headers=auth(GM)).status_code == 200
    assert client.post(f"/api/jobs/{job['id']}/site", json={"lat": 26.7, "lng": -80.1}, headers=auth(WH)).status_code == 403
    assert client.post(f"/api/jobs/{job['id']}/site", json={"lat": 26.7, "lng": -80.1}, headers=auth(OTHER)).status_code == 404
