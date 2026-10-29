"""Clients, leads, estimates with locked versions, proposals, and jobs from won estimates."""
import json
from datetime import timedelta

from conftest import auth

from app.db import SessionLocal
from app.models import Estimate, utcnow

GM, EST, PM, SALES, LEAD, OWNER, OTHER = "dev-gm", "dev-estimator", "dev-pm", "dev-sales", "dev-lead-2", "dev-owner", "dev-other-gm"

DATA = {
    "site_address": "1 Test Way, Stuart, FL 34994", "parcel_id": "55-38-41-000", "court_type": "pickleball",
    "scope_type": "new_construction", "price": 50000, "estimated_labor_rate": 30, "sales_tax_pct": 7,
    "tasks": [{"task_type": "prep", "name": "Clearing & grading", "estimated_hours": 20},
              {"task_type": "color_coat", "name": "Color coats", "estimated_hours": 10}],
    "cost_lines": [{"category": "material", "description": "Acrylic paint", "quantity": 10, "unit": "pail", "unit_cost": 100, "task_index": 1},
                   {"category": "subcontractor", "description": "A1 Fence", "quantity": 1, "unit": "job", "unit_cost": 5000}],
    "scope_text": "Two new pickleball courts.", "exclusions": "Permits by owner.", "links": "https://drive.google.com/x",
    "notes": "INTERNAL: tight on price, they have another bid",
}
COST_WORDS = ("total_cost", "unit_cost", "estimated_labor_rate", "margin", "INTERNAL", "cost_lines", "profit")


def new_client(client, token=SALES, name="TEST Client"):
    r = client.post("/api/clients", json={"name": name, "phone": "555-0100"}, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()


def new_estimate(client, client_id, token=EST, **extra):
    body = {"client_id": client_id, "name": "TEST Courts", "data": DATA} | extra
    r = client.post("/api/estimates", json=body, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()


def me_id(client, token):
    return client.get("/api/me", headers=auth(token)).json()["id"]


def backdate(estimate_id, **fields):
    db = SessionLocal()
    e = db.get(Estimate, estimate_id)
    for k, v in fields.items():
        setattr(e, k, v)
    db.commit()
    db.close()


# ---------- clients ----------

def test_clients_shared_and_tracked(client):
    c = new_client(client)
    assert client.post("/api/clients", json={"name": "test client"}, headers=auth(GM)).status_code == 409  # same name
    r = client.put(f"/api/clients/{c['id']}", json={"name": "TEST Client", "phone": "555-0199"}, headers=auth(EST))
    assert r.status_code == 200 and r.json()["phone"] == "555-0199"
    detail = client.get(f"/api/clients/{c['id']}", headers=auth(GM)).json()
    assert detail["activity"][0]["action"] == "Edited client" and "555-0100 → 555-0199" in detail["activity"][0]["detail"]
    assert client.get(f"/api/clients/{c['id']}", headers=auth(OTHER)).status_code == 404
    assert client.get("/api/clients", headers=auth(LEAD)).status_code == 403
    # never deleted, only turned off (GM)
    assert client.patch(f"/api/clients/{c['id']}/active", json={"active": False}, headers=auth(SALES)).status_code == 403
    assert client.patch(f"/api/clients/{c['id']}/active", json={"active": False, "reason": "dupe"}, headers=auth(GM)).json()["active"] is False
    assert c["id"] not in [x["id"] for x in client.get("/api/clients", headers=auth(GM)).json()]


# ---------- leads ----------

def test_sales_owns_their_leads(client):
    c = new_client(client)
    r = client.post("/api/leads", json={"client_id": c["id"], "name": "TEST Lead", "description": "2 courts", "links": "https://drive.google.com/a",
                                        "salesperson_id": me_id(client, GM)}, headers=auth(SALES))
    assert r.status_code == 201 and r.json()["salesperson_id"] == me_id(client, SALES)  # can't hand it to someone else
    gm_lead = client.post("/api/leads", json={"client_id": c["id"], "name": "GM's lead"}, headers=auth(GM)).json()
    seen = [l["id"] for l in client.get("/api/leads", headers=auth(SALES)).json()]
    assert r.json()["id"] in seen and gm_lead["id"] not in seen
    assert client.get(f"/api/leads/{gm_lead['id']}", headers=auth(SALES)).status_code == 404
    assert gm_lead["id"] in [l["id"] for l in client.get("/api/leads", headers=auth(EST)).json()]
    assert client.post(f"/api/leads/{gm_lead['id']}/status", json={"status": "dropped"}, headers=auth(GM)).status_code == 422  # needs a reason
    assert client.post(f"/api/leads/{gm_lead['id']}/status", json={"status": "dropped", "reason": "No budget"}, headers=auth(GM)).json()["status"] == "dropped"


# ---------- estimates ----------

def test_estimate_versions_are_locked(client):
    c = new_client(client)
    lead = client.post("/api/leads", json={"client_id": c["id"], "name": "TEST Lead"}, headers=auth(SALES)).json()
    assert client.post("/api/estimates", json={"client_id": c["id"], "name": "x", "data": DATA}, headers=auth(SALES)).status_code == 403
    e = new_estimate(client, c["id"], lead_id=lead["id"])
    assert e["number"].startswith(f"E-{utcnow().year}-") and e["version"] == 1 and e["salesperson_id"] == me_id(client, SALES)
    assert client.get(f"/api/leads/{lead['id']}", headers=auth(SALES)).json()["status"] == "estimating"
    second = new_estimate(client, c["id"])
    assert int(second["number"][-3:]) == int(e["number"][-3:]) + 1

    v2 = client.post(f"/api/estimates/{e['id']}/versions", json={"client_id": c["id"], "name": "TEST Courts",
                     "data": DATA | {"price": 48000}, "note": "Knocked off lighting"}, headers=auth(EST)).json()
    assert v2["version"] == 2 and v2["price"] == 48000
    v1 = client.get(f"/api/estimates/{e['id']}/versions/1", headers=auth(EST)).json()
    assert v1["price"] == 50000 and v1["data"]["price"] == 50000 and v1["current"] is False

    # only the GM removes a version, with a reason, and it stays on record
    assert client.post(f"/api/estimates/{e['id']}/versions/1/remove", json={"reason": "typo"}, headers=auth(EST)).status_code == 403
    assert client.post(f"/api/estimates/{e['id']}/versions/1/remove", json={"reason": "Wrong client sizes"}, headers=auth(GM)).status_code == 200
    assert client.get(f"/api/estimates/{e['id']}/versions/1", headers=auth(EST)).status_code == 404
    gm_view = client.get(f"/api/estimates/{e['id']}", headers=auth(GM)).json()
    assert [v["removed"] for v in gm_view["versions"]] == [False, True]
    assert [v["version"] for v in client.get(f"/api/estimates/{e['id']}", headers=auth(EST)).json()["versions"]] == [2]
    assert client.post(f"/api/estimates/{e['id']}/versions/2/remove", json={"reason": "last one"}, headers=auth(GM)).status_code == 409
    actions = [a["action"] for a in gm_view["activity"]]
    assert "Removed v1" in actions and "Saved v2" in actions


def test_sales_never_sees_costs(client):
    c = new_client(client)
    e = new_estimate(client, c["id"], salesperson_id=me_id(client, SALES))
    for path in (f"/api/estimates/{e['id']}", "/api/estimates", f"/api/estimates/{e['id']}/proposal", f"/api/clients/{c['id']}"):
        text = client.get(path, headers=auth(SALES)).text
        assert all(w not in text for w in COST_WORDS), (path, [w for w in COST_WORDS if w in text])
    assert client.get(f"/api/estimates/{e['id']}/versions/1", headers=auth(SALES)).status_code == 403
    # the proposal never carries costs, whoever opens it
    text = client.get(f"/api/estimates/{e['id']}/proposal", headers=auth(GM)).text
    assert all(w not in text for w in COST_WORDS)
    assert json.loads(text)["price"] == 50000 and json.loads(text)["work_items"] == ["Clearing & grading", "Color coats"]
    # estimators and PMs see the cost
    assert client.get(f"/api/estimates/{e['id']}", headers=auth(PM)).json()["total_cost"] == 30 * 30 + 1000 + 70 + 5000


def test_sales_only_sees_their_estimates(client):
    c = new_client(client)
    mine = new_estimate(client, c["id"], salesperson_id=me_id(client, SALES))
    theirs = new_estimate(client, c["id"], salesperson_id=me_id(client, GM))
    ids = [x["id"] for x in client.get("/api/estimates", headers=auth(SALES)).json()]
    assert mine["id"] in ids and theirs["id"] not in ids
    assert client.get(f"/api/estimates/{theirs['id']}", headers=auth(SALES)).status_code == 404
    assert client.get(f"/api/estimates/{mine['id']}", headers=auth(OTHER)).status_code == 404


def test_status_follow_up_and_expiry(client):
    c = new_client(client)
    lead = client.post("/api/leads", json={"client_id": c["id"], "name": "TEST Lead"}, headers=auth(SALES)).json()
    e = new_estimate(client, c["id"], lead_id=lead["id"])
    r = client.post(f"/api/estimates/{e['id']}/status", json={"status": "sent"}, headers=auth(SALES))
    assert r.json()["status"] == "sent" and r.json()["follow_up"] is None
    assert client.get(f"/api/leads/{lead['id']}", headers=auth(SALES)).json()["status"] == "estimated"
    assert client.post(f"/api/estimates/{e['id']}/status", json={"status": "lost"}, headers=auth(SALES)).status_code == 422  # say why
    assert client.post(f"/api/estimates/{e['id']}/status", json={"status": "expired"}, headers=auth(GM)).status_code == 422  # automatic only

    backdate(e["id"], sent_at=utcnow() - timedelta(days=16))
    assert "16 days since sent" in client.get(f"/api/estimates/{e['id']}", headers=auth(SALES)).json()["follow_up"]
    assert client.post(f"/api/estimates/{e['id']}/follow-up", json={"note": ""}, headers=auth(SALES)).status_code == 422
    assert client.post(f"/api/estimates/{e['id']}/follow-up", json={"note": "Board meets Tuesday"}, headers=auth(SALES)).json()["follow_up"] is None

    backdate(e["id"], sent_at=utcnow() - timedelta(days=31), last_follow_up_at=utcnow() - timedelta(days=16))
    row = next(x for x in client.get("/api/estimates", headers=auth(GM)).json() if x["id"] == e["id"])
    assert row["status"] == "expired" and "Expired" in row["follow_up"]
    activity = client.get(f"/api/estimates/{e['id']}", headers=auth(GM)).json()["activity"]
    assert activity[0]["action"] == "Expired" and activity[0]["by"] == "Courtfield (automatic)"
    # re-sending restarts the clock
    assert client.post(f"/api/estimates/{e['id']}/status", json={"status": "sent", "note": "Revised"}, headers=auth(SALES)).json()["status"] == "sent"


def test_won_estimate_becomes_a_job(client):
    c = new_client(client)
    e = new_estimate(client, c["id"], salesperson_id=me_id(client, SALES))
    assert client.post(f"/api/estimates/{e['id']}/create-job", headers=auth(EST)).status_code == 409  # not won yet
    assert client.post(f"/api/estimates/{e['id']}/status", json={"status": "won", "note": "Signed"}, headers=auth(SALES)).status_code == 200
    assert client.post(f"/api/estimates/{e['id']}/create-job", headers=auth(SALES)).status_code == 403
    r = client.post(f"/api/estimates/{e['id']}/create-job", headers=auth(EST))
    assert r.status_code == 201
    job = client.get(f"/api/jobs/{r.json()['job_id']}/edit", headers=auth(GM)).json()
    assert job["name"] == "TEST Courts" and job["client"] == "TEST Client" and job["status"] == "scheduled"
    assert job["parcel_id"] == "55-38-41-000" and job["contract_amount"] == 50000
    assert [t["name"] for t in job["tasks"]] == ["Clearing & grading", "Color coats"]
    assert job["cost_lines"][0]["task_id"] == job["tasks"][1]["id"]
    # locked from here
    assert client.post(f"/api/estimates/{e['id']}/create-job", headers=auth(EST)).status_code == 409
    assert client.post(f"/api/estimates/{e['id']}/status", json={"status": "lost", "note": "x x x"}, headers=auth(GM)).status_code == 409
    assert client.post(f"/api/estimates/{e['id']}/versions", json={"client_id": c["id"], "name": "x", "data": DATA}, headers=auth(EST)).status_code == 409
    assert r.json()["job_id"] in [j["id"] for j in client.get(f"/api/clients/{c['id']}", headers=auth(GM)).json()["jobs"]]


def test_bad_estimate_input(client):
    c = new_client(client)
    bad = DATA | {"cost_lines": [{"category": "material", "description": "x", "quantity": 1, "unit": "", "unit_cost": 1, "task_index": 9}]}
    assert client.post("/api/estimates", json={"client_id": c["id"], "name": "x", "data": bad}, headers=auth(EST)).status_code == 422
    other_client = client.post("/api/clients", json={"name": "Theirs"}, headers=auth(OTHER)).json()
    assert client.post("/api/estimates", json={"client_id": other_client["id"], "name": "x", "data": DATA}, headers=auth(EST)).status_code == 404


# ---------- settings ----------

def test_proposal_header_settings(client):
    r = client.patch("/api/company", json={"proposal_name": "Armor Courts (test)", "proposal_license": "CBC000000",
                                           "estimate_valid_days": 45}, headers=auth(GM))
    assert r.status_code == 200 and r.json()["proposal_license"] == "CBC000000"
    assert client.patch("/api/company", json={"proposal_name": "x"}, headers=auth(OWNER)).status_code == 403
    c = new_client(client)
    e = new_estimate(client, c["id"])
    assert e["valid_days"] == 45
    assert client.get(f"/api/estimates/{e['id']}/proposal", headers=auth(GM)).json()["company"]["name"] == "Armor Courts (test)"


def test_lead_follows_its_estimates(client):
    c = new_client(client)
    lead = client.post("/api/leads", json={"client_id": c["id"], "name": "TEST Lead outcome"}, headers=auth(SALES)).json()
    assert lead["outcome"] == "new"
    e = new_estimate(client, c["id"], lead_id=lead["id"], salesperson_id=me_id(client, SALES))
    assert client.get(f"/api/leads/{lead['id']}", headers=auth(SALES)).json()["outcome"] == "estimating"
    client.post(f"/api/estimates/{e['id']}/status", json={"status": "sent"}, headers=auth(SALES))
    assert client.get(f"/api/leads/{lead['id']}", headers=auth(SALES)).json()["outcome"] == "estimated"
    client.post(f"/api/estimates/{e['id']}/status", json={"status": "lost", "note": "Price"}, headers=auth(SALES))
    row = next(l for l in client.get("/api/leads", headers=auth(SALES)).json() if l["id"] == lead["id"])
    assert row["outcome"] == "lost"
    client.post(f"/api/estimates/{e['id']}/status", json={"status": "won", "note": "They came back"}, headers=auth(SALES))
    detail = client.get(f"/api/leads/{lead['id']}", headers=auth(SALES)).json()
    assert detail["outcome"] == "won" and detail["activity"][0]["action"] == f"Estimate {e['number']} marked won"
