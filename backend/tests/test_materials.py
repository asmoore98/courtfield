from conftest import auth

GM, EST, WH, LEAD, OWNER, OTHER = "dev-gm", "dev-estimator", "dev-warehouse", "dev-lead-1", "dev-owner", "dev-other-gm"


def job_named(client, frag, token=GM):
    return next(j for j in client.get("/api/jobs", headers=auth(token)).json() if frag in j["name"])


def item_named(client, name, token=GM):
    return next(i for i in client.get("/api/items", headers=auth(token)).json() if i["name"] == name)


def materials(client, job, token=GM):
    r = client.get(f"/api/jobs/{job['id']}/materials", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def row(mats, desc):
    return next(r for r in mats["rows"] if r["description"] == desc)


def move(client, token=WH, **body):
    return client.post("/api/stock/moves", json=body, headers=auth(token))


# ---------- price list ----------

def test_price_list_roles_and_prices_hidden(client):
    est_items = client.get("/api/items", headers=auth(EST)).json()
    assert est_items and all("unit_cost" in i for i in est_items)
    for t in (WH, LEAD):
        items = client.get("/api/items", headers=auth(t)).json()
        assert items and all("unit_cost" not in i for i in items)
    r = client.post("/api/items", json={"name": "Windscreen", "unit": "roll", "unit_cost": 210, "track_stock": True}, headers=auth(EST))
    assert r.status_code == 201
    assert client.post("/api/items", json={"name": "windscreen", "unit_cost": 1}, headers=auth(GM)).status_code == 409
    for t in (WH, LEAD, OWNER):
        assert client.post("/api/items", json={"name": "X"}, headers=auth(t)).status_code == 403
    assert client.patch(f"/api/items/{r.json()['id']}", json={"unit_cost": 225}, headers=auth(GM)).json()["unit_cost"] == 225
    assert client.get("/api/items", headers=auth(OTHER)).json() == []


def test_estimate_lines_link_to_price_list(client):
    resurfacer = item_named(client, "Acrylic resurfacer", EST)
    body = {"name": "Linked", "court_type": "tennis", "scope_type": "resurfacing", "estimated_labor_rate": 30,
            "tasks": [{"task_type": "prep", "name": "Prep", "estimated_hours": 4}],
            "cost_lines": [{"category": "material", "description": "Acrylic resurfacer", "quantity": 6, "unit": "pail",
                            "unit_cost": 120, "item_id": resurfacer["id"]}]}
    r = client.post("/api/jobs", json=body, headers=auth(EST))
    assert r.status_code == 201 and r.json()["cost_lines"][0]["item_id"] == resurfacer["id"]
    body["cost_lines"][0]["item_id"] = "not-a-real-item"
    assert client.post("/api/jobs", json=body, headers=auth(EST)).status_code == 422


# ---------- job material list ----------

def test_job_list_from_estimate_with_sent_returned_and_extras(client):
    coral = job_named(client, "Coral Ridge")
    m = materials(client, coral, GM)
    res = row(m, "Acrylic resurfacer")
    assert (res["planned"], res["sent"], res["returned"], res["used"]) == (30, 30, 3, 27)
    assert res["lots"] == ["AR-2291"] and res["status"] == "sent" and res["used_vs_planned"] == -3
    cc = row(m, "Color coat concentrate")
    assert cc["status"] == "partly_sent" and cc["left_to_send"] == 12
    extra = row(m, "Crack filler")
    assert extra["on_estimate"] is False and extra["sent"] == 2
    # subs, rentals and other costs aren't material rows
    assert all("fence" not in r["description"].lower() and "rental" not in r["description"].lower() for r in m["rows"])
    assert res["actual_cost"] == 27 * 120 and "estimated_cost" in res
    assert m["summary"]["not_on_estimate"] == 1


def test_crew_lead_and_warehouse_see_list_without_dollars(client):
    coral = job_named(client, "Coral Ridge", token=LEAD)
    for t in (LEAD, WH):
        m = materials(client, coral, t)
        assert m["rows"] and all("actual_cost" not in r and "estimated_cost" not in r for r in m["rows"])
        assert "actual_cost" not in m["summary"]
    assert client.get(f"/api/jobs/{coral['id']}/materials", headers=auth(OTHER)).status_code == 404


def test_send_and_return_flow_updates_stock(client):
    coral = job_named(client, "Coral Ridge")
    cc = row(materials(client, coral), "Color coat concentrate")
    stock_before = item_named(client, "Color coat concentrate", WH)["on_hand"]
    r = move(client, kind="to_job", job_id=coral["id"], row_key=cc["key"], quantity=12, lot_number="CC-1190")
    assert r.status_code == 201, r.text
    assert r.json()["on_hand_after"] == stock_before - 12
    cc = row(materials(client, coral), "Color coat concentrate")
    assert cc["sent"] == 24 and cc["status"] == "sent" and cc["lots"] == ["CC-1187", "CC-1190"]
    # bring back 2; can't bring back more than is out
    assert move(client, kind="from_job", job_id=coral["id"], row_key=cc["key"], quantity=30).status_code == 422
    assert move(client, kind="from_job", job_id=coral["id"], row_key=cc["key"], quantity=2).status_code == 201
    assert item_named(client, "Color coat concentrate", WH)["on_hand"] == stock_before - 10
    assert row(materials(client, coral), "Color coat concentrate")["used"] == 22


def test_send_by_item_matches_estimate_line_and_free_text_extra(client):
    coral = job_named(client, "Coral Ridge")
    lp = item_named(client, "Line paint", WH)
    assert move(client, kind="to_job", job_id=coral["id"], item_id=lp["id"], quantity=4).status_code == 201
    m = materials(client, coral)
    assert row(m, "Line paint")["sent"] == 4 and row(m, "Line paint")["on_estimate"] is True
    assert move(client, kind="to_job", job_id=coral["id"], description="Blue painters tape", unit="roll", quantity=6).status_code == 201
    tape = row(materials(client, coral), "Blue painters tape")
    assert tape["on_estimate"] is False and tape["sent"] == 6
    assert move(client, kind="from_job", job_id=coral["id"], row_key=tape["key"], quantity=2).status_code == 201


def test_receive_and_count_correction(client):
    sand = item_named(client, "Silica sand", WH)
    assert move(client, kind="receive", item_id=sand["id"], quantity=100, unit_cost=8.5, note="PO 1123").status_code == 201
    r = move(client, kind="adjust", item_id=sand["id"], quantity=-5, note="Count: 5 bags torn")
    assert r.status_code == 201 and r.json()["on_hand_after"] == sand["on_hand"] + 95
    assert move(client, kind="adjust", item_id=sand["id"], quantity=0).status_code == 422
    rental = item_named(client, "Pressure washer rental", GM)
    assert move(client, kind="receive", item_id=rental["id"], quantity=1).status_code == 422  # not stocked


def test_who_can_log_moves(client):
    coral = job_named(client, "Coral Ridge")
    sand = item_named(client, "Silica sand", GM)
    for t in (LEAD, EST, OWNER):
        assert move(client, token=t, kind="to_job", job_id=coral["id"], item_id=sand["id"], quantity=1).status_code == 403
    assert move(client, token=GM, kind="to_job", job_id=coral["id"], item_id=sand["id"], quantity=1).status_code == 201
    assert move(client, token=OTHER, kind="to_job", job_id=coral["id"], item_id=sand["id"], quantity=1).status_code == 404


def test_void_with_reason_and_guard(client):
    coral = job_named(client, "Coral Ridge")
    hist = client.get(f"/api/jobs/{coral['id']}/materials/moves", headers=auth(WH)).json()
    sent_res = next(h for h in hist if h["description"] == "Acrylic resurfacer" and h["kind"] == "to_job")
    # voiding the send would leave a return bigger than what went out
    assert client.post(f"/api/stock/moves/{sent_res['id']}/void", json={"reason": "wrong job"}, headers=auth(WH)).status_code == 409
    back = next(h for h in hist if h["kind"] == "from_job")
    r = client.post(f"/api/stock/moves/{back['id']}/void", json={"reason": "Logged twice"}, headers=auth(WH))
    assert r.status_code == 200 and r.json()["voided"] is True
    assert row(materials(client, coral), "Acrylic resurfacer")["returned"] == 0
    assert client.post(f"/api/stock/moves/{back['id']}/void", json={"reason": "again"}, headers=auth(WH)).status_code == 409
    hist = client.get(f"/api/jobs/{coral['id']}/materials/moves", headers=auth(LEAD)).json()
    assert any(h["voided"] and h["void_reason"] == "Logged twice" for h in hist) and all("unit_cost" not in h for h in hist)


def test_actual_material_cost_in_costing(client):
    coral = job_named(client, "Coral Ridge")
    c = client.get(f"/api/jobs/{coral['id']}/costing", headers=auth(GM)).json()
    # 27 resurfacer x120 + 40 sand x9 + 12 color x150 + 2 crack filler x38
    assert c["materials_actual_cost"] == 27 * 120 + 40 * 9 + 12 * 150 + 2 * 38
    assert "materials_actual_cost" not in client.get(f"/api/jobs/{coral['id']}/costing", headers=auth(LEAD)).json()


def test_warehouse_sees_open_jobs_only_and_no_costing(client):
    jobs = client.get("/api/jobs", headers=auth(WH)).json()
    assert jobs and all(j["status"] != "complete" for j in jobs) and all("cost_lines" not in j for j in jobs)
    me = client.get("/api/me", headers=auth(WH)).json()
    assert me["manages_stock"] is True and me["edits_prices"] is False
