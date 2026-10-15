import csv
import io
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from conftest import auth

ET = ZoneInfo("America/New_York")


def monday_weeks_ago(n):
    today = datetime.now(ET).date()
    return today - timedelta(days=today.weekday()) - timedelta(weeks=n)


def at(d: date, hh: int, mm: int = 0) -> str:
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).astimezone(timezone.utc).isoformat()


def add(client, job, task, worker, d, start_h, hours, reason="Test hours"):
    end = datetime(d.year, d.month, d.day, start_h, tzinfo=ET) + timedelta(hours=hours)
    r = client.post("/api/time/office", headers=auth("dev-gm"), json={
        "job_id": job["id"], "task_id": task["id"], "worker_id": worker["id"],
        "clock_in": at(d, start_h), "clock_out": end.astimezone(timezone.utc).isoformat(), "reason": reason})
    assert r.status_code == 201, r.text
    return r.json()


def setup(client):
    job = next(j for j in client.get("/api/jobs", headers=auth("dev-gm")).json() if "Seabreeze" in j["name"])
    crew = {c["name"]: c for c in client.get("/api/crew", headers=auth("dev-lead-1")).json()}
    return job, crew


def test_week_with_overtime(client):
    job, crew = setup(client)
    mon = monday_weeks_ago(8)
    for i in range(5):
        add(client, job, job["tasks"][0], crew["Luis Vega"], mon + timedelta(days=i), 7, 9)  # 45 h
    add(client, job, job["tasks"][1], crew["Andre Wells"], mon + timedelta(days=2), 7, 6)
    r = client.get(f"/api/reports/timesheet?week={(mon + timedelta(days=3)).isoformat()}", headers=auth("dev-gm"))
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["week_start"] == mon.isoformat() and t["days"][0]["label"] == "Mon"
    luis = next(p for p in t["people"] if p["name"] == "Luis Vega")
    assert luis["days"] == [9, 9, 9, 9, 9, 0, 0]
    assert (luis["regular_hours"], luis["overtime_hours"], luis["total_hours"]) == (40, 5, 45)
    assert luis["labor_cost"] == round((40 + 5 * 1.5) * 27, 2)
    assert luis["flags"]["corrected"] == 5  # all added from the office
    andre = next(p for p in t["people"] if p["name"] == "Andre Wells")
    assert andre["days"][2] == 6 and andre["overtime_hours"] == 0
    assert t["totals"]["total_hours"] == 51 and t["totals"]["overtime_hours"] == 5


def test_week_start_setting_moves_late_sunday_entry(client):
    job, crew = setup(client)
    mon = monday_weeks_ago(9)
    sunday = mon - timedelta(days=1)
    add(client, job, job["tasks"][0], crew["Kenny Ruiz"], sunday, 22, 1)   # Sunday 10-11 pm ET
    week_of_sunday = client.get(f"/api/reports/timesheet?week={sunday.isoformat()}", headers=auth("dev-gm")).json()
    assert any(p["name"] == "Kenny Ruiz" for p in week_of_sunday["people"])        # Mon-Sun week ending that Sunday
    assert client.patch("/api/company", json={"week_start": 6}, headers=auth("dev-gm")).status_code == 200
    sun_week = client.get(f"/api/reports/timesheet?week={sunday.isoformat()}", headers=auth("dev-gm")).json()
    assert sun_week["week_start"] == sunday.isoformat() and sun_week["days"][0]["label"] == "Sun"
    kenny = next(p for p in sun_week["people"] if p["name"] == "Kenny Ruiz")
    assert kenny["days"][0] == 1


def test_open_entries_flagged_not_counted(client):
    t = client.get("/api/reports/timesheet", headers=auth("dev-gm")).json()
    marco = next(p for p in t["people"] if p["name"] == "Marco Diaz")
    assert marco["flags"]["open_entries"] == 1


def test_who_can_see_payroll(client):
    assert client.get("/api/reports/timesheet", headers=auth("dev-owner")).status_code == 200
    for key in ("dev-estimator", "dev-lead-1"):
        assert client.get("/api/reports/timesheet", headers=auth(key)).status_code == 403
        assert client.get("/api/reports/timesheet.csv", headers=auth(key)).status_code == 403
    assert client.patch("/api/company", json={"week_start": 6}, headers=auth("dev-owner")).status_code == 403
    assert client.patch("/api/company", json={"timezone": "Mars/Base"}, headers=auth("dev-gm")).status_code == 422
    other = client.get("/api/reports/timesheet", headers=auth("dev-other-gm")).json()
    assert other["people"] == []


def test_csv_export(client):
    job, crew = setup(client)
    team = client.get("/api/team", headers=auth("dev-gm")).json()
    tyler = next(p for p in team if p["name"] == "Tyler Brooks")
    client.patch(f"/api/team/{tyler['id']}", json={"name": "=HYPERLINK(1)"}, headers=auth("dev-gm"))
    mon = monday_weeks_ago(10)
    add(client, job, job["tasks"][0], {"id": tyler["id"]}, mon, 7, 8)
    r = client.get(f"/api/reports/timesheet.csv?week={mon.isoformat()}", headers=auth("dev-gm"))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert f"timesheet-{mon.isoformat()}.csv" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.text.lstrip("﻿"))))
    detail = next(row for row in rows if row and row[1] == mon.isoformat())
    assert detail[0] == "'=HYPERLINK(1)" and detail[4] == "07:00" and detail[5] == "15:00" and detail[6] == "8.00"
    assert ["Person", "Role", "Regular hours", "Overtime hours", "Total hours", "Labor cost (OT at 1.5x)"] in rows
    # Current week shows anyone still on the clock
    now_csv = client.get("/api/reports/timesheet.csv", headers=auth("dev-gm")).text
    assert "STILL ON THE CLOCK" in now_csv
