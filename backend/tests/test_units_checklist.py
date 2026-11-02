"""Tasks measured by the unit, court size entered once, and the site checklist."""
from conftest import auth

GM, EST, SALES, OTHER_SALES = "dev-gm", "dev-estimator", "dev-sales", "dev-other-gm"


def new_client(client, name="TEST Units Client"):
    return client.post("/api/clients", json={"name": name}, headers=auth(EST)).json()


def resurface(**over):
    """Two pickleball courts, 30 x 60 each = 3,600 SF; 3,400 SF of it gets coated."""
    d = {
        "priced": "built", "court_type": "pickleball", "scope_type": "resurfacing", "sales_tax_pct": 0, "price": 0,
        "markups": {"material": 20, "equipment": 0, "subcontractor": 0, "other": 0},
        "court": {"courts": 2, "length_ft": 60, "width_ft": 30, "paint_sf": 3400},
        "tasks": [
            # 3,600 SF at 900 SF an hour = 4 h; $0.12 a SF
            {"task_type": "prep", "name": "Pressure wash", "unit": "sf", "follows": "surface", "production_rate": 900,
             "cost_rate": 34, "unit_price": 0.12, "estimated_hours": 999},
            # 120 LF at 40 LF an hour = 3 h; $3.25 a LF
            {"task_type": "crack_fill", "name": "Crack fill", "unit": "lf", "quantity": 120, "production_rate": 40,
             "cost_rate": 34, "unit_price": 3.25},
            # 3,400 SF x 2 coats at 600 SF an hour = 11.33 h; $0.28 a SF a coat
            {"task_type": "color_coat", "name": "Color coat", "unit": "sf_coat", "follows": "paint", "coats": 2,
             "production_rate": 600, "cost_rate": 34, "unit_price": 0.28},
            # 2 courts at 6 h each = 12 h; no price per unit, so 12 h x $68
            {"task_type": "lines", "name": "Line painting", "unit": "ea", "follows": "courts", "production_rate": 6,
             "cost_rate": 34, "charge_rate": 68},
            # hourly, as before
            {"task_type": "other", "name": "Mobilization", "estimated_hours": 2, "cost_rate": 34, "charge_rate": 68},
        ],
        "cost_lines": [
            # 3,400 SF x 2 coats / 1,200 SF a pail a coat = 5.67, so 6 pails
            {"category": "material", "description": "Color concentrate", "quantity": 1, "unit": "pail", "unit_cost": 150,
             "follows": "paint", "coats": 2, "coverage": 1200},
        ],
    }
    return d | over


def test_quantities_work_out_hours_and_price(client):
    c = new_client(client)
    e = client.post("/api/estimates", json={"client_id": c["id"], "name": "TEST Units", "data": resurface()}, headers=auth(EST))
    assert e.status_code == 201, e.text
    got = client.get(f"/api/estimates/{e.json()['id']}", headers=auth(EST)).json()
    tasks, line, t = got["data"]["tasks"], got["data"]["cost_lines"][0], got["totals"]
    assert [x["quantity"] for x in tasks[:4]] == [3600, 120, 3400, 2]
    assert [x["estimated_hours"] for x in tasks] == [4, 3, 11.33, 12, 2]  # typed hours are replaced when there's a rate
    assert line["quantity"] == 6
    hours = 4 + 3 + 11.33 + 12 + 2
    assert round(t["hours"], 2) == hours and round(t["labor"], 2) == round(hours * 34, 2)
    labor_price = 3600 * 0.12 + 120 * 3.25 + 6800 * 0.28 + 12 * 68 + 2 * 68
    assert round(t["charge"]["labor"], 2) == round(labor_price, 2)
    assert round(t["price"], 2) == round(labor_price + 900 * 1.2, 2)


def test_typed_quantity_wins_over_the_court_size(client):
    c = new_client(client)
    d = resurface()
    d["tasks"][2] = d["tasks"][2] | {"follows": "", "quantity": 3000}  # estimator typed their own area
    d["court"] = {"surface_sf": 4000}  # a measured total, no length or width
    e = client.post("/api/estimates", json={"client_id": c["id"], "name": "TEST Override", "data": d}, headers=auth(EST)).json()
    tasks = client.get(f"/api/estimates/{e['id']}", headers=auth(EST)).json()["data"]["tasks"]
    assert tasks[0]["quantity"] == 4000 and tasks[2]["quantity"] == 3000 and tasks[2]["estimated_hours"] == 10


def test_job_keeps_how_the_work_is_measured(client):
    c = new_client(client)
    e = client.post("/api/estimates", json={"client_id": c["id"], "name": "TEST Units job", "data": resurface()}, headers=auth(EST)).json()
    client.post(f"/api/estimates/{e['id']}/status", json={"status": "won"}, headers=auth(GM))
    job_id = client.post(f"/api/estimates/{e['id']}/create-job", headers=auth(EST)).json()["job_id"]
    job = client.get(f"/api/jobs/{job_id}/edit", headers=auth(GM)).json()
    crack = next(t for t in job["tasks"] if t["name"] == "Crack fill")
    assert (crack["unit"], crack["quantity"], crack["production_rate"], crack["estimated_hours"]) == ("lf", 120, 40, 3)
    # editing the job: change the footage and the hours follow
    body = {k: job[k] for k in ("name", "client", "address", "court_type", "scope_type", "contract_amount", "estimated_labor_rate", "sales_tax_pct")}
    body["tasks"] = [{k: v for k, v in t.items() if k != "has_time"} for t in job["tasks"]]
    body["tasks"][1]["quantity"] = 200
    body["cost_lines"] = []
    r = client.put(f"/api/jobs/{job_id}", json=body, headers=auth(GM))
    assert r.status_code == 200, r.text
    assert next(t for t in r.json()["tasks"] if t["name"] == "Crack fill")["estimated_hours"] == 5


def test_library_task_units(client):
    body = {"name": "TEST Sealer", "task_type": "prep", "unit": "sf_coat", "coats": 1, "production_rate": 800, "unit_price": 0.15}
    r = client.post("/api/library/tasks", json=body, headers=auth(GM))
    assert r.status_code == 201 and r.json()["unit"] == "sf_coat" and r.json()["production_rate"] == 800
    tid = r.json()["id"]
    r = client.put(f"/api/library/tasks/{tid}", json=body | {"unit": "hr"}, headers=auth(GM))
    assert r.json()["production_rate"] is None and r.json()["coats"] is None  # hourly tasks have neither
    hist = client.get(f"/api/library/tasks/{tid}/history", headers=auth(EST)).json()
    assert "Measured in" in hist[0]["detail"] and "Production rate" in hist[0]["detail"]
    crack = next(t for t in client.get("/api/library", headers=auth(EST)).json()["tasks"] if t["name"] == "Crack fill")
    assert crack["unit"] == "lf"
    assert client.post("/api/library/tasks", json=body | {"name": "TEST Bad", "unit": "acres"}, headers=auth(GM)).status_code == 422


def test_site_checklist_on_the_lead(client):
    lists = client.get("/api/leads/checklists", headers=auth(SALES)).json()
    assert set(lists["scopes"]) == {"resurfacing", "repair", "new_construction"}
    c = client.post("/api/clients", json={"name": "TEST Checklist Client"}, headers=auth(SALES)).json()
    survey = {"court": {"courts": 2, "length_ft": 60, "width_ft": 30},
              "answers": {"cracks": "yes", "crack_lf": 120, "nets": "no", "net_type": "Tennis", "bogus": "x", "colors": "  "}}
    body = {"client_id": c["id"], "name": "TEST Checklist", "court_type": "pickleball", "scope_type": "resurfacing", "survey": survey}
    lead = client.post("/api/leads", json=body, headers=auth(SALES)).json()
    # hidden follow-ups (net type after "no"), unknown questions and blanks are dropped
    assert lead["survey"]["answers"] == {"cracks": "yes", "crack_lf": 120, "nets": "no"}
    assert lead["survey"]["court"]["length_ft"] == 60
    p = lead["checklist"]
    assert p["done"] == 4 and p["total"] > p["done"] and "Do the posts need replaced?" in p["missing"]

    survey["answers"] = {"cracks": "no", "crack_lf": 120, "nets": "no"}
    survey["court"]["width_ft"] = 34
    lead = client.put(f"/api/leads/{lead['id']}", json=body | {"survey": survey}, headers=auth(SALES)).json()
    assert lead["survey"]["answers"] == {"cracks": "no", "nets": "no"}
    trail = client.get(f"/api/leads/{lead['id']}", headers=auth(GM)).json()["activity"]
    change = next(a for a in trail if a["action"] == "Changed the site checklist")
    assert "Do cracks need filled? Yes → No" in change["detail"] and "120 LF → —" in change["detail"]
    assert "Court width: 30 ft → 34 ft" in change["detail"]
    # saving the lead without a checklist leaves it as it was
    lead = client.put(f"/api/leads/{lead['id']}", json=body | {"survey": None, "description": "x"}, headers=auth(SALES)).json()
    assert lead["survey"]["answers"] == {"cracks": "no", "nets": "no"}
    # no scope yet, no checklist
    blank = client.post("/api/leads", json={"client_id": c["id"], "name": "TEST No scope"}, headers=auth(SALES)).json()
    assert blank["checklist"] is None
    assert client.get(f"/api/leads/{lead['id']}", headers=auth(OTHER_SALES)).status_code == 404


def test_crews_see_the_work_not_the_money(client):
    c = new_client(client, "TEST Crew view")
    e = client.post("/api/estimates", json={"client_id": c["id"], "name": "TEST Crew view", "data": resurface()}, headers=auth(EST)).json()
    client.post(f"/api/estimates/{e['id']}/status", json={"status": "won"}, headers=auth(GM))
    job_id = client.post(f"/api/estimates/{e['id']}/create-job", headers=auth(EST)).json()["job_id"]
    for path in (f"/api/jobs/{job_id}", "/api/jobs"):
        body = client.get(path, headers=auth("dev-lead-1")).json()
        job = body if isinstance(body, dict) else next(j for j in body if j["id"] == job_id)
        crack = next(t for t in job["tasks"] if t["name"] == "Crack fill")
        assert crack["quantity"] == 120 and crack["unit"] == "lf"
        assert all(k not in t for t in job["tasks"] for k in ("cost_rate", "charge_rate", "unit_price", "sub_price"))
    costing = client.get(f"/api/jobs/{job_id}/costing", headers=auth("dev-lead-1")).json()
    assert next(t for t in costing["tasks"] if t["name"] == "Crack fill")["quantity"] == 120
