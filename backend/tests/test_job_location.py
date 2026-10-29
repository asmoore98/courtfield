"""Parcel ID on jobs, and the address-to-map-pin lookup."""
from conftest import auth

from app.routers import geocode

GM, LEAD, EST, OTHER = "dev-gm", "dev-lead-2", "dev-estimator", "dev-other-gm"

BODY = {"name": "TEST Parcel Job", "court_type": "tennis", "scope_type": "new_construction",
        "address": "", "parcel_id": "3402-501-0012-000-3",
        "tasks": [{"task_type": "prep", "name": "Prep", "estimated_hours": 4}]}


def test_parcel_id_saves_and_updates(client):
    r = client.post("/api/jobs", json=BODY, headers=auth(EST))
    assert r.status_code == 201 and r.json()["parcel_id"] == "3402-501-0012-000-3"
    job_id = r.json()["id"]
    edit = client.get(f"/api/jobs/{job_id}/edit", headers=auth(GM)).json()
    edit["parcel_id"] = "3402-501-0012-000-4"
    edit["address"] = "100 Court Way, Port St. Lucie, FL 34952"
    r = client.put(f"/api/jobs/{job_id}", json=edit, headers=auth(GM))
    assert r.status_code == 200
    assert r.json()["parcel_id"].endswith("-4") and r.json()["address"].startswith("100 Court Way")


def test_parcel_id_is_optional(client):
    body = {k: v for k, v in BODY.items() if k != "parcel_id"}
    r = client.post("/api/jobs", json=body, headers=auth(GM))
    assert r.status_code == 201 and r.json()["parcel_id"] == ""


def test_parcel_id_hidden_from_other_company(client):
    job_id = client.post("/api/jobs", json=BODY, headers=auth(GM)).json()["id"]
    assert client.get(f"/api/jobs/{job_id}", headers=auth(OTHER)).status_code == 404


def test_geocode_found(client, monkeypatch):
    seen = {}

    def fake(address):
        seen["address"] = address
        return {"lat": 27.27, "lng": -80.35, "matched_address": "100 COURT WAY, PORT ST LUCIE, FL, 34952"}

    monkeypatch.setattr(geocode, "census_lookup", fake)
    r = client.get("/api/geocode", params={"address": "  100 Court Way, Port St Lucie FL  "}, headers=auth(EST))
    assert r.status_code == 200 and r.json()["lat"] == 27.27
    assert seen["address"] == "100 Court Way, Port St Lucie FL"


def test_geocode_not_found_and_down(client, monkeypatch):
    monkeypatch.setattr(geocode, "census_lookup", lambda a: None)
    r = client.get("/api/geocode", params={"address": "nowhere at all"}, headers=auth(GM))
    assert r.status_code == 404 and "city and ZIP" in r.json()["detail"]

    def down(a):
        raise OSError("timed out")

    monkeypatch.setattr(geocode, "census_lookup", down)
    assert client.get("/api/geocode", params={"address": "100 Court Way"}, headers=auth(GM)).status_code == 502


def test_geocode_is_for_job_editors_only(client, monkeypatch):
    monkeypatch.setattr(geocode, "census_lookup", lambda a: None)
    assert client.get("/api/geocode", params={"address": "100 Court Way"}, headers=auth(LEAD)).status_code == 403
    assert client.get("/api/geocode", params={"address": "100 Court Way"}).status_code == 401


def test_census_response_parsing(monkeypatch):
    import io
    import json

    payload = {"result": {"addressMatches": [{"matchedAddress": "1 A ST, X, FL, 1", "coordinates": {"x": -80.1234567, "y": 26.7654321}}]}}

    class Res(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(geocode.urllib.request, "urlopen", lambda req, timeout: Res(json.dumps(payload).encode()))
    assert geocode.census_lookup("1 A St") == {"lat": 26.765432, "lng": -80.123457, "matched_address": "1 A ST, X, FL, 1"}
    monkeypatch.setattr(geocode.urllib.request, "urlopen", lambda req, timeout: Res(b'{"result": {"addressMatches": []}}'))
    assert geocode.census_lookup("1 A St") is None
