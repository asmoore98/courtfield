"""Batch 5: tasks priced by the unit or built up, sizes, lines that follow
their task, and the court border."""
from app.routers.estimates import totals
from app.sales_schemas import EstimateData


def est(tasks, lines=(), court=None, **kw):
    return EstimateData(priced="built", court_type="tennis", scope_type="new_construction", court=court or {},
                        tasks=list(tasks), cost_lines=list(lines), **kw)


def test_base_rock_from_size_with_machine_time_per_load():
    # 100 x 60 ft, 4 in deep: 74.07 CY x 1.4 = 103.7 tons
    rock = {"task_type": "site_work", "name": "Base rock", "unit": "ton", "follows": "size", "size_length_ft": 100,
            "size_width_ft": 60, "size_depth_in": 4, "tons_per_cy": 1.4, "production_rate": 0.1, "cost_rate": 30, "charge_rate": 50}
    lines = [
        # rock itself, 5% extra for waste, bought by the ton
        {"category": "material", "description": "Base rock", "unit": "ton", "unit_cost": 20, "quantity": 0,
         "task_index": 0, "follows": "task", "per_amount": 1.05, "per_every": 1, "markup_pct": 10},
        # the loader: 45 min for every 20-ton load, whole loads (6 loads)
        {"category": "equipment", "description": "Loader", "unit": "hr", "unit_cost": 150, "quantity": 0,
         "task_index": 0, "follows": "task", "per_amount": 0.75, "per_every": 20, "markup_pct": 0},
    ]
    d = est([rock], lines)
    assert d.tasks[0].quantity == 103.7
    assert d.tasks[0].estimated_hours == 10.37
    assert d.cost_lines[0].quantity == 109  # 103.7 x 1.05 = 108.9, whole tons
    assert d.cost_lines[1].quantity == 4.5   # ceil(103.7 / 20) = 6 loads x 0.75 hr
    t = totals(d)
    assert round(t["labor"], 2) == 311.10 and t["material"] == 2180 and t["equipment"] == 675
    # built up: labor at its rate + each line with its markup
    assert t["price"] == round(10.37 * 50 + 2180 * 1.1 + 675, 2)


def test_all_in_task_charges_its_unit_price_only():
    clear = {"task_type": "site_work", "name": "Clearing", "unit": "acre", "quantity": 2, "production_rate": 8,
             "cost_rate": 30, "unit_price": 4000, "all_in": True}
    lines = [{"category": "equipment", "description": "Mulcher", "unit": "day", "unit_cost": 900, "quantity": 2, "task_index": 0, "markup_pct": 20},
             {"category": "fee", "description": "Burn permit", "unit": "", "unit_cost": 75, "quantity": 1, "task_index": 0},
             {"category": "material", "description": "Erosion fence", "unit": "LF", "unit_cost": 1, "quantity": 100}]
    t = totals(est([clear], lines, sales_tax_pct=7))
    # the customer pays 2 acres x $4,000; the mulcher and permit are our cost inside it
    assert t["price"] == 8000 + 100 * 1.07
    assert t["total_cost"] == 16 * 30 + 1800 + 75 + 100 + 7
    assert t["fees"] == 0  # the permit is inside the all-in price, not passed through on top
    # its own row in the price breakdown: everything inside the price per unit
    assert t["all_in"]["cost"] == 16 * 30 + 1800 + 75 and t["charge"]["all_in"] == 8000 and t["charge"]["labor"] == 0
    assert t["fee"] == 0 and t["subtotal"] == 8000 + 107


def test_court_with_a_border_band():
    court = {"courts": 1, "length_ft": 94, "width_ft": 50, "border_ft": 5}
    tasks = [{"task_type": "color_coat", "name": "Court color", "unit": "sf_coat", "coats": 2, "follows": "playing", "unit_price": 0.5},
             {"task_type": "color_coat", "name": "Border color", "unit": "sf_coat", "coats": 2, "follows": "border", "unit_price": 0.5},
             {"task_type": "resurfacer", "name": "Resurfacer", "unit": "sf_coat", "coats": 2, "follows": "surface", "unit_price": 0.25}]
    d = est(tasks, court=court)
    assert [t.quantity for t in d.tasks] == [4700, 1540, 6240]  # 94x50, 104x60 - 94x50, 104x60
    assert totals(d)["price"] == round((4700 + 1540) * 2 * 0.5 + 6240 * 2 * 0.25, 2)


def test_old_estimates_price_the_same():
    """Tasks saved before Batch 5 are built up, as they were."""
    t = {"task_type": "prep", "name": "Prep", "unit": "hr", "estimated_hours": 10, "cost_rate": 30, "charge_rate": 60}
    ln = {"category": "material", "description": "Filler", "unit": "pail", "unit_cost": 100, "quantity": 2, "task_index": 0, "markup_pct": 25}
    assert totals(est([t], [ln]))["price"] == 600 + 250


def test_library_parts_and_starter_materials(client):
    from conftest import auth
    items = client.get("/api/items", headers=auth("dev-estimator")).json()
    rock = next(i for i in items if i["name"] == "Base rock (crushed limerock)")
    assert rock["starter_price"] and rock["unit"] == "ton"
    color = next(i for i in items if i["name"] == "Color coat concentrate")
    assert color.get("coverage_sf") is None or color["coverage_sf"] > 0
    # checking the price clears the starter flag
    r = client.patch(f"/api/items/{rock['id']}", json={"price_checked": True}, headers=auth("dev-estimator")).json()
    assert r["starter_price"] is False
    # loading the starter list again adds nothing new
    assert client.post("/api/items/starter", headers=auth("dev-gm")).json()["added"] == 0
    # a library task with parts
    body = {"name": "TEST Base rock spread", "task_type": "site_work", "unit": "ton", "all_in": True, "parts": [
        {"category": "material", "description": "Base rock (crushed limerock)", "item_id": rock["id"], "unit": "ton", "how": "task", "per_amount": 1.05, "per_every": 1},
        {"category": "equipment", "description": "Dump truck haul", "unit": "load", "how": "task", "per_amount": 1, "per_every": 20}]}
    t = client.post("/api/library/tasks", json=body, headers=auth("dev-gm")).json()
    assert t["all_in"] and len(t["parts"]) == 2 and t["parts"][1]["per_every"] == 20
    t = client.put(f"/api/library/tasks/{t['id']}", json=body | {"parts": body["parts"][:1]}, headers=auth("dev-gm")).json()
    assert len(t["parts"]) == 1
    hist = client.get(f"/api/library/tasks/{t['id']}/history", headers=auth("dev-gm")).json()
    assert any("Parts" in (h.get("detail") or "") for h in hist)
    # starter tasks get their usual parts
    lib = client.get("/api/library", headers=auth("dev-estimator")).json()
    resurf = next(x for x in lib["tasks"] if x["name"] == "Acrylic resurfacer")
    assert resurf["parts"] and resurf["parts"][0]["per_every"] == 600 and resurf["parts"][0]["item_id"]
