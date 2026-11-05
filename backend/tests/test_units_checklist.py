"""Tasks measured by the unit, court size entered once, the site checklist, addresses and photos."""
import base64

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
    assert p["done"] == 4 and p["total"] > p["done"] and "Any net post work?" in p["missing"]

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
    lead_id = client.get("/api/me", headers=auth("dev-lead-1")).json()["id"]
    assert client.get(f"/api/jobs/{job_id}", headers=auth("dev-lead-1")).status_code == 404  # not theirs yet
    client.put(f"/api/jobs/{job_id}/crew", json={"crew_lead_id": lead_id}, headers=auth(GM))
    for path in (f"/api/jobs/{job_id}", "/api/jobs"):
        body = client.get(path, headers=auth("dev-lead-1")).json()
        job = body if isinstance(body, dict) else next(j for j in body if j["id"] == job_id)
        crack = next(t for t in job["tasks"] if t["name"] == "Crack fill")
        assert crack["quantity"] == 120 and crack["unit"] == "lf"
        assert all(k not in t for t in job["tasks"] for k in ("cost_rate", "charge_rate", "unit_price", "sub_price"))
    costing = client.get(f"/api/jobs/{job_id}/costing", headers=auth("dev-lead-1")).json()
    assert next(t for t in costing["tasks"] if t["name"] == "Crack fill")["quantity"] == 120


def test_checklist_follows_the_court_type(client):
    c = client.post("/api/clients", json={"name": "TEST Hoops Client"}, headers=auth(SALES)).json()
    answers = {"nets": "yes", "net_count": 2, "goals": "yes", "goals_work": "Replace existing", "goal_count": 2,
               "goal_footing": "Yes", "surface": "Other", "surface_other": " Pavers ", "cracks_note": "Mostly by the north fence",
               "cracks": "no", "fence": "yes", "fence_work": "Repair", "fence_lf": 40, "fence_height": "8 ft"}
    body = {"client_id": c["id"], "name": "TEST Hoops", "court_type": "basketball", "scope_type": "resurfacing",
            "survey": {"court": {}, "answers": answers}}
    lead = client.post("/api/leads", json=body, headers=auth(SALES)).json()
    kept = lead["survey"]["answers"]
    assert "nets" not in kept and "net_count" not in kept      # no nets on a basketball court
    assert kept["goals_work"] == "Replace existing" and kept["goal_footing"] == "Yes"
    assert kept["surface_other"] == "Pavers" and kept["cracks_note"] == "Mostly by the north fence"
    assert "fence_height" not in kept                          # only asked for a new or replaced fence
    assert not any("net" in m.lower() for m in lead["checklist"]["missing"])
    # switching to tennis: the goal answers go, the net questions come in
    lead = client.put(f"/api/leads/{lead['id']}", json=body | {"court_type": "tennis"}, headers=auth(SALES)).json()
    assert "goals" not in lead["survey"]["answers"] and lead["survey"]["answers"]["net_count"] == 2
    trail = client.get(f"/api/leads/{lead['id']}", headers=auth(GM)).json()["activity"]
    assert any("Any basketball goal work? Yes → —" in (a["detail"] or "") for a in trail)
    # the history names the "other" and the notes
    lists = client.get("/api/leads/checklists", headers=auth(SALES)).json()["scopes"]["resurfacing"]
    ids = [q["id"] for sec in lists for q in sec["questions"]]
    assert ids.index("surface_other") == ids.index("surface") + 1


def test_address_in_parts(client):
    c = client.post("/api/clients", json={"name": "TEST Address Client", "billing_street": "9 Sample Ct", "billing_city": "Stuart",
                                          "billing_state": "FL", "billing_zip": "34994"}, headers=auth(SALES)).json()
    assert c["billing_address"] == "9 Sample Ct, Stuart, FL 34994" and c["billing_city"] == "Stuart"
    body = {"client_id": c["id"], "name": "TEST Address", "site_street": " 100 Sample Way ", "site_city": "Jupiter",
            "site_state": "FL", "site_zip": "33458"}
    lead = client.post("/api/leads", json=body, headers=auth(SALES)).json()
    assert lead["site_address"] == "100 Sample Way, Jupiter, FL 33458" and lead["site_street"] == "100 Sample Way"
    # an old one-line address with no parts is kept as it was
    old = client.post("/api/leads", json={"client_id": c["id"], "name": "TEST Old", "site_address": "1 Old Rd, Stuart, FL"},
                      headers=auth(SALES)).json()
    assert old["site_address"] == "1 Old Rd, Stuart, FL"
    # the estimate carries the parts to the job
    d = resurface(site_street="5 Court Ln", site_city="Stuart", site_state="FL", site_zip="34994")
    e = client.post("/api/estimates", json={"client_id": c["id"], "name": "TEST Address est", "data": d}, headers=auth(EST)).json()
    client.post(f"/api/estimates/{e['id']}/status", json={"status": "won"}, headers=auth(GM))
    job_id = client.post(f"/api/estimates/{e['id']}/create-job", headers=auth(EST)).json()["job_id"]
    job = client.get(f"/api/jobs/{job_id}", headers=auth(GM)).json()
    assert job["address"] == "5 Court Ln, Stuart, FL 34994" and job["site_city"] == "Stuart"


JPEG = base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 2000).decode()


def test_photos_on_leads_and_estimates(client):
    c = client.post("/api/clients", json={"name": "TEST Photo Client"}, headers=auth(SALES)).json()
    lead = client.post("/api/leads", json={"client_id": c["id"], "name": "TEST Photos"}, headers=auth(SALES)).json()
    add = lambda token, **kw: client.post("/api/photos", json={"kind": "lead", "subject_id": lead["id"], "name": "north.jpg",
                                                               "data": JPEG, "thumb": JPEG} | kw, headers=auth(token))
    r = add(SALES)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert add(SALES, data=base64.b64encode(b"not a picture at all").decode()).status_code == 422
    assert add(OTHER_SALES).status_code == 404                  # another company's lead
    img = client.get(f"/api/photos/{pid}?size=thumb", headers=auth(SALES))
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg" and img.content[:3] == b"\xff\xd8\xff"
    assert client.get(f"/api/photos/{pid}", headers=auth("dev-lead-1")).status_code == 403  # crews don't see leads
    # an estimate from the lead shows the lead's photos too
    e = client.post("/api/estimates", json={"client_id": c["id"], "lead_id": lead["id"], "name": "TEST Photos est",
                                            "data": resurface()}, headers=auth(EST)).json()
    ph = client.get(f"/api/photos?kind=estimate&id={e['id']}", headers=auth(EST)).json()
    assert [(p["id"], p["from"]) for p in ph] == [(pid, "lead")]
    # removing: whoever added it or the GM, with a reason, and it's in the history
    assert client.post(f"/api/photos/{pid}/remove", json={"reason": "Blurry"}, headers=auth(EST)).status_code == 403
    assert client.post(f"/api/photos/{pid}/remove", json={"reason": "x"}, headers=auth(SALES)).status_code == 422
    assert client.post(f"/api/photos/{pid}/remove", json={"reason": "Blurry"}, headers=auth(SALES)).status_code == 200
    assert client.get(f"/api/photos?kind=lead&id={lead['id']}", headers=auth(SALES)).json() == []
    acts = [a["action"] for a in client.get(f"/api/leads/{lead['id']}", headers=auth(GM)).json()["activity"]]
    assert "Added a photo" in acts and "Removed a photo" in acts


def test_drive_folder_link(client):
    r = client.patch("/api/company", json={"drive_folder_url": " https://drive.google.com/drive/folders/sample "}, headers=auth(GM))
    assert r.status_code == 200, r.text
    assert client.get("/api/me", headers=auth(SALES)).json()["drive_url"] == "https://drive.google.com/drive/folders/sample"


def test_fees_pass_through_and_print_on_the_proposal(client):
    c = new_client(client, "TEST Fees")
    d = resurface(overall_markup=10, notes="Board is slow to pay", customer_notes="Gate code 1234 needed on arrival")
    d["cost_lines"].append({"category": "fee", "description": "Building permit (county)", "quantity": 1, "unit": "each",
                            "unit_cost": 450, "markup_pct": 50})
    e = client.post("/api/estimates", json={"client_id": c["id"], "name": "TEST Fees", "data": d}, headers=auth(EST)).json()
    t = client.get(f"/api/estimates/{e['id']}", headers=auth(EST)).json()["totals"]
    assert t["fees"] == 450 and t["fee"] == 450
    assert round(t["price"], 2) == round(t["subtotal"] * 1.10 + 450, 2)  # no markup of any kind on the fee
    prop = client.get(f"/api/estimates/{e['id']}/proposal", headers=auth(EST)).json()
    assert prop["fees"] == [{"description": "Building permit (county)", "amount": 450}]
    assert prop["notes"] == "Gate code 1234 needed on arrival" and "slow to pay" not in str(prop)
    # marking it sent needs the box ticked
    r = client.post(f"/api/estimates/{e['id']}/status", json={"status": "sent"}, headers=auth(EST))
    assert r.status_code == 422 and "tick" in r.json()["detail"]
    r = client.post(f"/api/estimates/{e['id']}/status", json={"status": "sent", "checked_customer_text": True}, headers=auth(EST))
    assert r.json()["status"] == "sent"


def test_sales_sends_a_lead_to_estimating(client):
    c = client.post("/api/clients", json={"name": "TEST Hand-off"}, headers=auth(SALES)).json()
    lead = client.post("/api/leads", json={"client_id": c["id"], "name": "TEST Hand-off", "scope_type": "resurfacing"},
                       headers=auth(SALES)).json()
    assert lead["sent_at"] is None
    lead = client.post(f"/api/leads/{lead['id']}/send", json={}, headers=auth(SALES)).json()
    assert lead["sent_at"] and lead["sent_by"]
    trail = client.get(f"/api/leads/{lead['id']}", headers=auth(EST)).json()["activity"]
    assert trail[0]["action"].startswith("Sent to estimating (") and "not answered" in trail[0]["action"]
    assert client.post(f"/api/leads/{lead['id']}/unsend", json={}, headers=auth(SALES)).json()["sent_at"] is None
    client.post(f"/api/leads/{lead['id']}/send", json={}, headers=auth(SALES))
    client.post("/api/estimates", json={"client_id": c["id"], "lead_id": lead["id"], "name": "TEST Hand-off", "data": resurface()},
                headers=auth(EST))
    assert client.post(f"/api/leads/{lead['id']}/unsend", json={}, headers=auth(SALES)).status_code == 409


def test_checklist_note_stays_on_the_estimate(client):
    c = new_client(client, "TEST Note to task")
    d = resurface()
    d["tasks"][1]["checklist_note"] = "Sales: cracks along the north fence"
    e = client.post("/api/estimates", json={"client_id": c["id"], "name": "TEST Note", "data": d}, headers=auth(EST)).json()
    got = client.get(f"/api/estimates/{e['id']}", headers=auth(EST)).json()["data"]["tasks"][1]
    assert got["checklist_note"] == "Sales: cracks along the north fence"
    client.post(f"/api/estimates/{e['id']}/status", json={"status": "won"}, headers=auth(GM))
    job_id = client.post(f"/api/estimates/{e['id']}/create-job", headers=auth(EST)).json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}", headers=auth(GM)).status_code == 200


def test_crew_size_rides_along(client):
    c = new_client(client, "TEST Crew size")
    d = resurface()
    d["tasks"][4] = d["tasks"][4] | {"crew_size": 4, "estimated_hours": 32}  # 4 people, 8 hours each
    e = client.post("/api/estimates", json={"client_id": c["id"], "name": "TEST Crew size", "data": d}, headers=auth(EST)).json()
    t = client.get(f"/api/estimates/{e['id']}", headers=auth(EST)).json()
    assert t["data"]["tasks"][4]["crew_size"] == 4 and t["totals"]["hours"] == round(4 + 3 + 11.33 + 12 + 32, 2)
    client.post(f"/api/estimates/{e['id']}/status", json={"status": "won"}, headers=auth(GM))
    job_id = client.post(f"/api/estimates/{e['id']}/create-job", headers=auth(EST)).json()["job_id"]
    mob = next(x for x in client.get(f"/api/jobs/{job_id}", headers=auth(GM)).json()["tasks"] if x["name"] == "Mobilization")
    assert mob["crew_size"] == 4 and mob["estimated_hours"] == 32



def test_sending_a_job_to_the_field(client):
    """Won estimate → job, sent to a crew lead with a crew and a start date.
    The crew lead sees only their jobs, starts it on site, and reports problems."""
    c = new_client(client, "TEST Field")
    e = client.post("/api/estimates", json={"client_id": c["id"], "name": "TEST Field", "data": resurface()}, headers=auth(EST)).json()
    client.post(f"/api/estimates/{e['id']}/status", json={"status": "won"}, headers=auth(GM))
    lead1 = client.get("/api/me", headers=auth("dev-lead-1")).json()["id"]
    crew = [u for u in client.get("/api/crew", headers=auth(GM)).json() if u["role"] == "crew"]
    body = {"crew_lead_id": lead1, "crew_ids": [crew[0]["id"], crew[1]["id"]], "start_date": "2026-11-16"}
    # estimators make jobs but don't send them out
    assert client.post(f"/api/estimates/{e['id']}/create-job", json=body, headers=auth(EST)).status_code == 403
    r = client.post(f"/api/estimates/{e['id']}/create-job", json=body, headers=auth("dev-pm"))
    assert r.status_code == 201, r.text
    job_id = r.json()["job_id"]
    job = client.get(f"/api/jobs/{job_id}", headers=auth(GM)).json()
    assert job["crew_lead_id"] == lead1 and job["start_date"] == "2026-11-16" and len(job["crew_members"]) == 2
    costing = client.get(f"/api/jobs/{job_id}/costing", headers=auth(GM)).json()  # the job page
    assert len(costing["crew_members"]) == 2 and costing["crew_lead_id"] == lead1
    # the crew lead sees it; the other crew lead doesn't
    assert any(j["id"] == job_id for j in client.get("/api/jobs", headers=auth("dev-lead-1")).json())
    assert not any(j["id"] == job_id for j in client.get("/api/jobs", headers=auth("dev-lead-2")).json())
    assert client.get(f"/api/jobs/{job_id}", headers=auth("dev-lead-2")).status_code == 404
    # bad picks are refused
    assert client.put(f"/api/jobs/{job_id}/crew", json={"crew_lead_id": crew[0]["id"]}, headers=auth(GM)).status_code == 422
    assert client.put(f"/api/jobs/{job_id}/crew", json=body, headers=auth(EST)).status_code == 403
    # on site: start it, the pin is set where they stand
    r = client.post(f"/api/jobs/{job_id}/start", json={"lat": 27.2, "lng": -80.25}, headers=auth("dev-lead-1"))
    assert r.status_code == 200 and r.json()["status"] == "active" and r.json()["started_at"].endswith("Z") and r.json()["lat"] == 27.2
    assert client.post(f"/api/jobs/{job_id}/start", json={}, headers=auth("dev-lead-2")).status_code == 404
    # a problem on site, then the office handles it
    p = client.post(f"/api/jobs/{job_id}/reports", json={"kind": "problem", "text": "Big crack by the north post, not on the estimate"},
                    headers=auth("dev-lead-1"))
    assert p.status_code == 201
    assert client.get(f"/api/jobs/{job_id}", headers=auth(GM)).json()["open_problems"] == 1
    summary = next(j for j in client.get("/api/jobs/summary", headers=auth(GM)).json() if j["job_id"] == job_id)
    assert summary["open_problems"] == 1 and summary["crew_lead_name"] and summary["start_date"] == "2026-11-16"
    assert client.post(f"/api/jobs/{job_id}/reports/{p.json()['id']}/resolve", json={"resolution": "x"}, headers=auth(GM)).status_code == 422
    r = client.post(f"/api/jobs/{job_id}/reports/{p.json()['id']}/resolve", json={"resolution": "Added a change order"}, headers=auth(GM))
    assert r.json()["resolved_by"]
    got = client.get(f"/api/jobs/{job_id}/reports", headers=auth(GM)).json()
    assert got["reports"][0]["resolution"] == "Added a change order"
    assert [a["action"] for a in got["activity"]][:4] == ["Handled a problem from the site", "Reported a problem on site",
                                                          "On site, crew clocked in", "Set the site pin on site"]


def _sent_job(client, name):
    c = new_client(client, name)
    d = resurface(scope_text="Pressure wash, fill cracks, 2 coats of color, lines.")
    d["tasks"][1] = d["tasks"][1] | {"crew_size": 3}
    e = client.post("/api/estimates", json={"client_id": c["id"], "name": name, "data": d}, headers=auth(EST)).json()
    client.post(f"/api/estimates/{e['id']}/status", json={"status": "won"}, headers=auth(GM))
    lead1 = client.get("/api/me", headers=auth("dev-lead-1")).json()["id"]
    return client.post(f"/api/estimates/{e['id']}/create-job", json={"crew_lead_id": lead1}, headers=auth(GM)).json()["job_id"]


def test_on_site_clock_in_walk_and_progress(client):
    job_id = _sent_job(client, "TEST On site")
    LEAD = "dev-lead-1"
    job = client.post(f"/api/jobs/{job_id}/start", json={"lat": 27.1, "lng": -80.2}, headers=auth(LEAD)).json()
    setup = job["tasks"][0]
    assert setup["name"] == "Site walk and setup" and job["scope_text"].startswith("Pressure wash") and job.get("site_walk_at") is None
    # starting again doesn't add a second setup task
    job = client.post(f"/api/jobs/{job_id}/start", json={}, headers=auth(LEAD)).json()
    assert sum(t["name"] == "Site walk and setup" for t in job["tasks"]) == 1
    assert client.post(f"/api/jobs/{job_id}/walked", headers=auth(LEAD)).json()["site_walk_at"]
    # what was reported stays visible to the crew lead
    client.post(f"/api/jobs/{job_id}/reports", json={"kind": "note", "text": "Gate code is 1234"}, headers=auth(LEAD))
    assert client.get(f"/api/jobs/{job_id}/reports", headers=auth(LEAD)).json()["reports"][0]["text"] == "Gate code is 1234"
    # marking a task done or partly done, with a photo on the task
    crack = next(t for t in job["tasks"] if t["name"] == "Crack fill")
    assert crack["crew_size"] == 3
    r = client.post(f"/api/jobs/{job_id}/tasks/{crack['id']}/progress", json={"pct": 120}, headers=auth(LEAD))
    assert r.status_code == 422  # 0 to 100
    r = client.post(f"/api/jobs/{job_id}/tasks/{crack['id']}/progress", json={"pct": 50, "note": "North side done"}, headers=auth(LEAD))
    t = next(x for x in r.json()["tasks"] if x["id"] == crack["id"])
    assert t["progress"] == "partial" and t["progress_pct"] == 50
    jpeg = base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 500).decode()
    assert client.post("/api/photos", json={"kind": "task", "subject_id": crack["id"], "name": "done.jpg", "data": jpeg, "thumb": jpeg},
                       headers=auth(LEAD)).status_code == 201
    assert client.post("/api/photos", json={"kind": "task", "subject_id": crack["id"], "name": "x.jpg", "data": jpeg, "thumb": jpeg},
                       headers=auth("dev-lead-2")).status_code == 404  # not their job
    client.post(f"/api/jobs/{job_id}/tasks/{crack['id']}/progress", json={"pct": 100}, headers=auth(LEAD))
    costing = client.get(f"/api/jobs/{job_id}/costing", headers=auth(GM)).json()
    assert next(x for x in costing["tasks"] if x["name"] == "Crack fill")["progress"] == "done"
    # the office sees who's on which task right now
    from datetime import datetime, timedelta, timezone
    w = next(x for x in client.get("/api/crew", headers=auth(LEAD)).json() if x["role"] == "crew")
    t0 = (datetime.now(timezone.utc) - timedelta(minutes=20)).replace(microsecond=0).isoformat()
    client.post("/api/time/sync", json={"entries": [{"id": "11111111-2222-3333-4444-555555555555", "job_id": job_id, "task_id": crack["id"],
                "worker_id": w["id"], "clock_in": t0, "clock_out": None, "client_updated_at": t0}]}, headers=auth(LEAD))
    on = client.get(f"/api/jobs/{job_id}/costing", headers=auth(GM)).json()["on_clock"]
    assert [(x["worker"], x["task"]) for x in on] == [(w["name"], "Crack fill")] and on[0]["since"].endswith("Z")
    summary = next(j for j in client.get("/api/jobs/summary", headers=auth(GM)).json() if j["job_id"] == job_id)
    assert summary["on_clock"][0]["task"] == "Crack fill"
    acts = [a["action"] for a in client.get(f"/api/jobs/{job_id}/reports", headers=auth(GM)).json()["activity"]]
    assert "Marked Crack fill done" in acts and "Added a photo to Crack fill" in acts and "Walked the site" in acts


def test_crew_lead_asks_for_material_and_signs(client):
    job_id = _sent_job(client, "TEST More material")
    body = {"description": "Color concentrate", "quantity": 2, "unit": "pail", "reason": "Ran short on the second coat",
            "signed_name": "Marco Diaz", "i_am_responsible": False}
    assert client.post(f"/api/jobs/{job_id}/material-requests", json=body, headers=auth("dev-lead-1")).status_code == 422
    assert client.post(f"/api/jobs/{job_id}/material-requests", json=body | {"i_am_responsible": True}, headers=auth("dev-lead-2")).status_code == 404
    r = client.post(f"/api/jobs/{job_id}/material-requests", json=body | {"i_am_responsible": True}, headers=auth("dev-lead-1"))
    assert client.get("/api/alerts", headers=auth("dev-warehouse")).json()["material_requests"] >= 1
    assert client.get("/api/alerts", headers=auth("dev-lead-1")).json() == {"problems": 0, "material_requests": 0}
    assert r.status_code == 201 and r.json()["signed_name"] == "Marco Diaz"
    rid = r.json()["id"]
    assert client.get("/api/material-requests", headers=auth("dev-lead-1")).status_code == 403
    open_ = client.get("/api/material-requests", headers=auth("dev-warehouse")).json()
    assert [x["id"] for x in open_] == [rid] and open_[0]["job_name"] == "TEST More material"
    assert client.post(f"/api/material-requests/{rid}/handle", json={"status": "declined"}, headers=auth("dev-warehouse")).status_code == 422
    r = client.post(f"/api/material-requests/{rid}/handle", json={"status": "sent", "note": "On the truck"}, headers=auth("dev-warehouse"))
    assert r.json()["status"] == "sent" and r.json()["handled_by"]
    mine = client.get(f"/api/jobs/{job_id}/material-requests", headers=auth("dev-lead-1")).json()
    assert mine[0]["status"] == "sent" and mine[0]["handled_note"] == "On the truck"
    assert client.get("/api/material-requests", headers=auth("dev-warehouse")).json() == []


def test_crew_lead_fixes_their_crews_time_with_a_trail(client):
    from datetime import datetime, timedelta, timezone
    job_id = _sent_job(client, "TEST Lead fixes time")
    LEAD = "dev-lead-1"
    job = client.post(f"/api/jobs/{job_id}/start", json={}, headers=auth(LEAD)).json()
    task = next(t for t in job["tasks"] if t["name"] == "Crack fill")
    worker = next(w for w in client.get("/api/crew", headers=auth(LEAD)).json() if w["role"] == "crew")
    t0 = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=9)
    body = {"job_id": job_id, "task_id": task["id"], "worker_id": worker["id"], "clock_in": t0.isoformat(),
            "clock_out": (t0 + timedelta(hours=8)).isoformat(), "reason": "Phone died, he was here all day"}
    # another crew lead can't touch this job's time, or even see it
    assert client.post("/api/time/office", json=body, headers=auth("dev-lead-2")).status_code == 403
    assert client.get(f"/api/time?job_id={job_id}", headers=auth("dev-lead-2")).status_code == 404
    r = client.post("/api/time/office", json=body, headers=auth(LEAD))
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    rows = client.get(f"/api/time?job_id={job_id}", headers=auth(LEAD)).json()
    assert rows[0]["can_fix"] and rows[0]["changed_by_lead"]
    # a fix needs a reason
    assert client.patch(f"/api/time/{eid}", json={"clock_out": (t0 + timedelta(hours=7)).isoformat(), "reason": ""},
                        headers=auth(LEAD)).status_code == 422
    r = client.patch(f"/api/time/{eid}", json={"clock_out": (t0 + timedelta(hours=7)).isoformat(), "reason": "Left at 3, not 4"},
                     headers=auth(LEAD))
    assert r.status_code == 200 and r.json()["hours"] == 7.0
    hist = client.get(f"/api/time/{eid}/history", headers=auth(GM)).json()
    assert [h["action"] for h in hist] == ["add", "edit"] and hist[1]["by_crew_lead"] and hist[1]["reason"] == "Left at 3, not 4"
    assert hist[1]["before"]["clock_out"] != hist[1]["after"]["clock_out"]
    # the office sees it on the job's history, with the reason
    acts = client.get(f"/api/jobs/{job_id}/reports", headers=auth(GM)).json()["activity"]
    changed = next(a for a in acts if a["action"].startswith("Changed"))
    assert worker["name"] in changed["action"] and "Left at 3, not 4" in changed["detail"] and "Was Crack fill" in changed["detail"]
    office_rows = client.get(f"/api/time?job_id={job_id}", headers=auth(GM)).json()
    assert office_rows[0]["changed_by_lead"]
    # once the office corrects it, the crew lead can't change it again
    client.patch(f"/api/time/{eid}", json={"clock_in": (t0 + timedelta(minutes=30)).isoformat(), "reason": "Checked the gate log"},
                 headers=auth(GM))
    assert client.patch(f"/api/time/{eid}", json={"clock_in": t0.isoformat(), "reason": "No he was here"},
                        headers=auth(LEAD)).status_code == 403
    assert not client.get(f"/api/time?job_id={job_id}", headers=auth(LEAD)).json()[0]["can_fix"]
    # older than a week: the office only
    old = body | {"clock_in": (t0 - timedelta(days=9)).isoformat(), "clock_out": (t0 - timedelta(days=9) + timedelta(hours=2)).isoformat()}
    assert client.post("/api/time/office", json=old, headers=auth(LEAD)).status_code == 403
    # removing is kept too
    r = client.post("/api/time/office", json=body | {"clock_in": (t0 - timedelta(days=1)).isoformat(),
                                                     "clock_out": (t0 - timedelta(days=1) + timedelta(hours=1)).isoformat()}, headers=auth(LEAD))
    assert client.post(f"/api/time/{r.json()['id']}/remove", json={"reason": "Wrong day"}, headers=auth(LEAD)).status_code == 200
    acts = [a["action"] for a in client.get(f"/api/jobs/{job_id}/reports", headers=auth(GM)).json()["activity"]]
    assert any(a.startswith("Removed") for a in acts)



def test_material_checked_loaded_and_on_site(client):
    job_id = _sent_job(client, "TEST Material check")
    LEAD = "dev-lead-1"
    got = client.get(f"/api/jobs/{job_id}/material-checks", headers=auth(LEAD)).json()
    planned = got["expected"]["on_site"]
    assert planned and not got["checks"] and "unit_cost" not in planned[0]
    # the shop checks the truck before it leaves; the crew lead can't do that one
    assert client.post(f"/api/jobs/{job_id}/material-checks", json={"kind": "loaded"}, headers=auth(LEAD)).status_code == 403
    r = client.post(f"/api/jobs/{job_id}/material-checks", json={"kind": "loaded"}, headers=auth("dev-warehouse"))
    assert r.status_code == 201 and r.json()["all_here"]
    # on site, one item is short: a reason is needed, and the office gets a problem
    short = {"key": planned[0]["key"], "here": max(0, planned[0]["expected"] - 1)}
    assert client.post(f"/api/jobs/{job_id}/material-checks", json={"kind": "on_site", "items": [short]},
                       headers=auth(LEAD)).status_code == 422
    r = client.post(f"/api/jobs/{job_id}/material-checks", json={"kind": "on_site", "items": [short], "note": "One pail left at the shop"},
                    headers=auth(LEAD))
    assert r.status_code == 201 and not r.json()["all_here"]
    reports = client.get(f"/api/jobs/{job_id}/reports", headers=auth(GM)).json()["reports"]
    assert reports[0]["kind"] == "problem" and reports[0]["text"].startswith("Material short on site")
    assert client.get("/api/alerts", headers=auth(GM)).json()["problems"] >= 1
    latest = client.get("/api/material-checks/latest", headers=auth("dev-warehouse")).json()[job_id]
    assert latest["loaded"]["all_here"] and not latest["on_site"]["all_here"]
    assert client.post(f"/api/jobs/{job_id}/material-checks", json={"kind": "on_site"}, headers=auth("dev-lead-2")).status_code == 404


def test_gm_sets_up_crews_and_the_lead_brings_them(client):
    crews = client.get("/api/crews", headers=auth(GM)).json()
    assert {c["lead_name"] for c in crews} == {"Marco Diaz", "Jordan Kemp"}
    marco = next(c for c in crews if c["lead_name"] == "Marco Diaz")
    jordan = next(c for c in crews if c["lead_name"] == "Jordan Kemp")
    assert len(marco["members"]) == 2 and marco["name"] == "Marco Diaz's crew"
    # only the GM changes crews; PMs see them for scheduling; crew leads don't
    assert client.get("/api/crews", headers=auth("dev-pm")).status_code == 200
    assert client.get("/api/crews", headers=auth("dev-lead-1")).status_code == 403
    assert client.put(f"/api/crews/{marco['lead_id']}", json={"member_ids": []}, headers=auth("dev-pm")).status_code == 403
    # moving someone from Jordan's crew to Marco's takes them off Jordan's
    mover = jordan["members"][0]
    r = client.put(f"/api/crews/{marco['lead_id']}", json={"name": "Crew A", "member_ids": [m["id"] for m in marco["members"]] + [mover["id"]]},
                   headers=auth(GM))
    assert r.status_code == 200 and len(r.json()["members"]) == 3 and r.json()["name"] == "Crew A" and r.json()["moved"]
    jordan_now = next(c for c in client.get("/api/crews", headers=auth(GM)).json() if c["lead_id"] == jordan["lead_id"])
    assert mover["id"] not in [m["id"] for m in jordan_now["members"]]
    # only field people, and a lead has to be a crew lead
    office = client.get("/api/me", headers=auth(EST)).json()["id"]
    assert client.put(f"/api/crews/{marco['lead_id']}", json={"member_ids": [office]}, headers=auth(GM)).status_code == 422
    worker = marco["members"][0]["id"]
    assert client.put(f"/api/crews/{worker}", json={"member_ids": []}, headers=auth(GM)).status_code == 422
    assert client.delete(f"/api/crews/{jordan['lead_id']}", headers=auth(GM)).status_code == 200
    assert len(client.get("/api/crews", headers=auth(GM)).json()) == 1
