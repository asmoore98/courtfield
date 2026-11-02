"""Task library, subs, per-task rates, markups and built prices."""
from conftest import auth

GM, EST, PM, SALES, LEAD, OTHER = "dev-gm", "dev-estimator", "dev-pm", "dev-sales", "dev-lead-2", "dev-other-gm"


def lib(client, token=EST):
    r = client.get("/api/library", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def task_named(client, name):
    return next(t for t in lib(client)["tasks"] if t["name"] == name)


def new_client(client, name="TEST Pricing Client"):
    return client.post("/api/clients", json={"name": name}, headers=auth(EST)).json()


def built(**over):
    """An estimate priced from rates and markups.

    Crew: 10 h grading at $95 cost / $175 charge, 8 h color coat at $34 / $68.
    Sub: fence, $5,000. Lines: paint $1,000 (+7% tax), rental $500, other $200.
    Markups: material 20, equipment 15, sub 10, other 10.
    """
    d = {
        "priced": "built", "court_type": "tennis", "scope_type": "new_construction", "sales_tax_pct": 7, "price": 1,
        "markups": {"material": 20, "equipment": 15, "subcontractor": 10, "other": 10},
        "tasks": [
            {"task_type": "site_work", "name": "Rough grading", "estimated_hours": 10, "cost_rate": 95, "charge_rate": 175},
            {"task_type": "color_coat", "name": "Color coat", "estimated_hours": 8, "cost_rate": 34, "charge_rate": 68},
            {"task_type": "fence", "name": "Chain-link fence, new", "kind": "sub", "sub_price": 5000, "estimated_hours": 12},
        ],
        "cost_lines": [
            {"category": "material", "description": "Acrylic paint", "quantity": 10, "unit": "pail", "unit_cost": 100, "task_index": 1},
            {"category": "equipment", "description": "Skid steer", "quantity": 1, "unit": "day", "unit_cost": 500, "in_house": True},
            {"category": "other", "description": "Permit", "quantity": 1, "unit": "each", "unit_cost": 200},
        ],
    }
    return d | over


COST = 10 * 95 + 8 * 34 + 5000 + 1000 + 70 + 500 + 200          # 7,992
CHARGE = 10 * 175 + 8 * 68 + 5000 * 1.1 + 1070 * 1.2 + 500 * 1.15 + 200 * 1.1  # 9,873


# ---------- library ----------

def test_gm_keeps_the_task_list(client):
    data = lib(client)
    assert len(data["tasks"]) > 40 and data["defaults"]["default_charge_rate"] == 68
    grading = task_named(client, "Rough grading")
    assert "cut and fill" in grading["aliases"] and grading["cost_rate"] == 95
    body = {"name": "Court cleaning", "aliases": "clean court, cleaning court", "task_type": "prep"}
    assert client.post("/api/library/tasks", json=body, headers=auth(EST)).status_code == 403
    r = client.post("/api/library/tasks", json=body, headers=auth(GM))
    assert r.status_code == 201 and r.json()["aliases"] == ["clean court", "cleaning court"]
    # one name, one task: a name already used anywhere in the library is refused
    clash = client.post("/api/library/tasks", json={"name": "Wash court", "aliases": "power wash"}, headers=auth(GM))
    assert clash.status_code == 409 and "Pressure wash" in clash.json()["detail"]
    tid = r.json()["id"]
    r = client.put(f"/api/library/tasks/{tid}", json=body | {"cost_rate": 30, "charge_rate": 60}, headers=auth(GM))
    assert r.json()["charge_rate"] == 60
    hist = client.get(f"/api/library/tasks/{tid}/history", headers=auth(EST)).json()
    assert hist[0]["action"] == "Edited Court cleaning" and "Charge rate" in hist[0]["detail"]
    assert client.patch(f"/api/library/tasks/{tid}/active", json={"active": False}, headers=auth(GM)).json()["active"] is False
    assert client.get("/api/library", headers=auth(SALES)).status_code == 403
    assert lib(client, OTHER)["tasks"] == []  # another company's library is its own


def test_starter_list_skips_names_already_there(client):
    assert client.post("/api/library/tasks/starter", headers=auth(EST)).status_code == 403
    assert client.post("/api/library/tasks/starter", headers=auth(GM)).json()["added"] == 0  # sample data already has it
    r = client.post("/api/library/tasks/starter", headers=auth(OTHER))
    assert r.json()["added"] > 40
    assert client.post("/api/library/tasks/starter", headers=auth(OTHER)).json()["added"] == 0


def test_defaults_gm_only(client):
    body = {"default_cost_rate": 36, "default_charge_rate": 72, "markup_material": 25, "markup_equipment": 15,
            "markup_subcontractor": 12, "markup_other": 10}
    assert client.put("/api/library/defaults", json=body, headers=auth(EST)).status_code == 403
    assert client.put("/api/library/defaults", json=body, headers=auth(GM)).json()["markup_material"] == 25


def test_subs(client):
    r = client.post("/api/library/subs", json={"name": "TEST Fence Co", "trade": "Fence", "phone": "555-0300"}, headers=auth(EST))
    assert r.status_code == 201
    sub = r.json()
    assert client.post("/api/library/subs", json={"name": "test fence co"}, headers=auth(PM)).status_code == 409
    assert client.patch(f"/api/library/subs/{sub['id']}/active", json={"active": False}, headers=auth(EST)).status_code == 403
    assert client.get(f"/api/library/subs/{sub['id']}", headers=auth(OTHER)).status_code == 404
    # used on an estimate: shows up on the sub's page with its price
    c = new_client(client)
    d = built()
    d["tasks"][2] |= {"sub_id": sub["id"], "sub_quote_link": "https://drive.google.com/fence-quote"}
    e = client.post("/api/estimates", json={"client_id": c["id"], "name": "TEST w/ sub", "data": d}, headers=auth(EST)).json()
    page = client.get(f"/api/library/subs/{sub['id']}", headers=auth(EST)).json()
    assert page["estimates"][0]["number"] == e["number"] and page["estimates"][0]["price"] == 5000
    # another company's sub can't be put on a task
    theirs = client.post("/api/library/subs", json={"name": "Theirs"}, headers=auth(OTHER)).json()
    d["tasks"][2]["sub_id"] = theirs["id"]
    assert client.post("/api/estimates", json={"client_id": c["id"], "name": "x", "data": d}, headers=auth(EST)).status_code == 422


# ---------- pricing ----------

def test_built_price_adds_itself_up(client):
    c = new_client(client)
    r = client.post("/api/estimates", json={"client_id": c["id"], "name": "TEST Built", "data": built()}, headers=auth(EST))
    assert r.status_code == 201, r.text
    e = client.get(f"/api/estimates/{r.json()['id']}", headers=auth(EST)).json()
    t = e["totals"]
    assert round(t["total_cost"], 2) == COST
    assert round(t["built_price"], 2) == round(CHARGE, 2) and e["price"] == round(CHARGE, 2)  # the screen's price=1 is ignored
    assert t["charge"]["labor"] == 10 * 175 + 8 * 68 and t["subcontractor"] == 5000
    assert e["data"]["tasks"][2]["estimated_hours"] == 12  # kept as sent in the estimate; jobs drop sub hours
    assert e["data"]["cost_lines"][1]["in_house"] is True


def test_adjustment_needs_a_reason_and_is_logged(client):
    c = new_client(client)
    bad = {"client_id": c["id"], "name": "TEST Adj", "data": built(adjustment=-373)}
    assert client.post("/api/estimates", json=bad, headers=auth(EST)).status_code == 422
    ok = {"client_id": c["id"], "name": "TEST Adj", "data": built(adjustment=-373, adjustment_reason="Round to $9,500")}
    e = client.post("/api/estimates", json=ok, headers=auth(EST)).json()
    assert e["price"] == round(CHARGE - 373, 2)
    act = client.get(f"/api/estimates/{e['id']}", headers=auth(GM)).json()["activity"]
    assert "Price adjusted −$373.00: Round to $9,500" in act[0]["detail"]
    assert client.post("/api/estimates", json={"client_id": c["id"], "name": "x", "data": built(adjustment=-20000, adjustment_reason="way too low")},
                       headers=auth(EST)).status_code == 422


def test_sales_sees_price_not_the_breakdown(client):
    c = new_client(client)
    me = client.get("/api/me", headers=auth(SALES)).json()["id"]
    e = client.post("/api/estimates", json={"client_id": c["id"], "name": "TEST Sales", "salesperson_id": me, "data": built()},
                    headers=auth(EST)).json()
    text = client.get(f"/api/estimates/{e['id']}", headers=auth(SALES)).text
    assert all(w not in text for w in ("charge", "markup", "cost_rate", "total_cost", "sub_price"))
    prop = client.get(f"/api/estimates/{e['id']}/proposal", headers=auth(SALES)).text
    assert all(w not in prop for w in ("charge", "markup", "cost_rate", "sub_price", "5000"))


def test_job_from_built_estimate_keeps_task_rates(client):
    c = new_client(client)
    e = client.post("/api/estimates", json={"client_id": c["id"], "name": "TEST Job", "data": built()}, headers=auth(EST)).json()
    client.post(f"/api/estimates/{e['id']}/status", json={"status": "won"}, headers=auth(GM))
    job_id = client.post(f"/api/estimates/{e['id']}/create-job", headers=auth(EST)).json()["job_id"]
    job = client.get(f"/api/jobs/{job_id}/edit", headers=auth(GM)).json()
    grading, fence = job["tasks"][0], job["tasks"][2]
    assert grading["cost_rate"] == 95 and grading["charge_rate"] == 175
    assert fence["kind"] == "sub" and fence["sub_price"] == 5000 and fence["estimated_hours"] == 0  # crew can't log hours against a sub
    assert job["contract_amount"] == round(CHARGE, 2) and job["cost_lines"][1]["in_house"] is True
    costing = client.get(f"/api/jobs/{job_id}/costing", headers=auth(GM)).json()
    assert costing["estimated_labor_cost"] == 10 * 95 + 8 * 34
    assert costing["estimate"]["subcontractor"] == 5000 and round(costing["estimate"]["total_cost"], 2) == COST
    assert costing["tasks"][2]["kind"] == "sub" and costing["tasks"][2]["sub_price"] == 5000
    lead_view = client.get(f"/api/jobs/{job_id}/costing", headers=auth(LEAD)).json()
    assert lead_view["tasks"][2]["kind"] == "sub" and "sub_price" not in lead_view["tasks"][2]  # crew leads never see dollars


def test_old_single_rate_still_works(client):
    """Jobs and estimates from before per-task rates use the old single rate."""
    body = {"name": "TEST Old style", "court_type": "tennis", "scope_type": "repair", "estimated_labor_rate": 30,
            "tasks": [{"task_type": "prep", "name": "Prep", "estimated_hours": 10},
                      {"task_type": "lines", "name": "Lines", "estimated_hours": 5, "cost_rate": 40}]}
    job = client.post("/api/jobs", json=body, headers=auth(GM)).json()
    assert client.get(f"/api/jobs/{job['id']}/costing", headers=auth(GM)).json()["estimated_labor_cost"] == 10 * 30 + 5 * 40


def test_markups_per_line_per_sub_and_on_the_whole_job(client):
    """Paint at 7%, sealant at 2%, the sub at its own 5%, then 4% on everything."""
    c = new_client(client)
    d = built(sales_tax_pct=0, overall_markup=4)
    d["tasks"][2]["markup_pct"] = 5
    d["cost_lines"] = [
        {"category": "material", "description": "Paint", "quantity": 10, "unit": "pail", "unit_cost": 100, "markup_pct": 7},
        {"category": "material", "description": "Sealant", "quantity": 5, "unit": "pail", "unit_cost": 100, "markup_pct": 2},
        {"category": "material", "description": "Sand", "quantity": 1, "unit": "ton", "unit_cost": 100},  # default 20%
    ]
    e = client.post("/api/estimates", json={"client_id": c["id"], "name": "TEST Markups", "data": d}, headers=auth(EST)).json()
    t = client.get(f"/api/estimates/{e['id']}", headers=auth(EST)).json()["totals"]
    labor = 10 * 175 + 8 * 68
    mats = 1000 * 1.07 + 500 * 1.02 + 100 * 1.2
    sub = 5000 * 1.05
    subtotal = labor + mats + sub
    assert round(t["subtotal"], 2) == round(subtotal, 2)
    assert round(t["price"], 2) == round(subtotal * 1.04, 2)
    cost = 10 * 95 + 8 * 34 + 1600 + 5000
    assert round(t["markup_pct"], 4) == round((subtotal * 1.04 - cost) / cost, 4)
    # markups stay on the estimate; the job keeps costs and the contract price
    client.post(f"/api/estimates/{e['id']}/status", json={"status": "won"}, headers=auth(GM))
    job_id = client.post(f"/api/estimates/{e['id']}/create-job", headers=auth(EST)).json()["job_id"]
    job = client.get(f"/api/jobs/{job_id}/edit", headers=auth(GM)).json()
    assert job["contract_amount"] == round(subtotal * 1.04, 2) and "markup_pct" not in job["cost_lines"][0]
    # Sales never sees any of it
    text = client.get(f"/api/estimates/{e['id']}/proposal", headers=auth(GM)).text
    assert "markup" not in text and "overall" not in text
