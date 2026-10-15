"""Material tracking: what each job is planned to use, what went out to it,
what came back, and what the warehouse has on hand.

The job's material list starts from its estimate (material cost lines). Every
movement is a StockMove. A move to or from a job is matched to a list row by
its cost line, else by price-list item, else by name; anything that matches
no planned line shows up as "not on the estimate".
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import CostCategory, Job, MoveKind, StockItem, StockMove

SIGN = {MoveKind.receive: 1, MoveKind.from_job: 1, MoveKind.to_job: -1, MoveKind.adjust: 1}


def on_hand(db: Session, company_id: str, item_ids: list[str] | None = None) -> dict[str, float]:
    """Stock on hand per item: received + returned - sent + adjustments."""
    q = select(StockMove.item_id, StockMove.kind, func.sum(StockMove.quantity)).where(
        StockMove.company_id == company_id, StockMove.voided_at.is_(None), StockMove.item_id.is_not(None)
    ).group_by(StockMove.item_id, StockMove.kind)
    if item_ids is not None:
        q = q.where(StockMove.item_id.in_(item_ids))
    totals: dict[str, float] = defaultdict(float)
    for item_id, kind, qty in db.execute(q):
        totals[item_id] += SIGN[kind] * (qty or 0)
    return {k: round(v, 3) for k, v in totals.items()}


def _row_key_for(move: StockMove, line_ids: set[str], item_to_line: dict[str, str]) -> str:
    if move.cost_line_id and move.cost_line_id in line_ids:
        return f"line:{move.cost_line_id}"
    if move.item_id and move.item_id in item_to_line:
        return f"line:{item_to_line[move.item_id]}"
    if move.item_id:
        return f"item:{move.item_id}"
    return f"name:{move.description.strip().lower()}"


def job_moves(db: Session, job: Job, include_voided: bool = False) -> list[StockMove]:
    q = select(StockMove).where(StockMove.job_id == job.id, StockMove.company_id == job.company_id,
                                StockMove.kind.in_([MoveKind.to_job, MoveKind.from_job])).order_by(StockMove.recorded_at)
    if not include_voided:
        q = q.where(StockMove.voided_at.is_(None))
    return list(db.scalars(q))


def job_materials(db: Session, job: Job, with_dollars: bool) -> dict:
    lines = [ln for ln in job.cost_lines if ln.category == CostCategory.material]
    line_ids = {ln.id for ln in lines}
    item_to_line: dict[str, str] = {}
    for ln in lines:
        if ln.item_id and ln.item_id not in item_to_line:
            item_to_line[ln.item_id] = ln.id

    rows: dict[str, dict] = {}
    for ln in lines:
        rows[f"line:{ln.id}"] = {
            "key": f"line:{ln.id}", "cost_line_id": ln.id, "item_id": ln.item_id, "description": ln.description,
            "unit": ln.unit, "planned": ln.quantity, "on_estimate": True, "_est_unit_cost": ln.unit_cost,
        }

    moves = job_moves(db, job)
    sent: dict[str, float] = defaultdict(float)
    back: dict[str, float] = defaultdict(float)
    cost: dict[str, float] = defaultdict(float)
    lots: dict[str, list[str]] = defaultdict(list)
    for m in moves:
        key = _row_key_for(m, line_ids, item_to_line)
        if key not in rows:
            rows[key] = {"key": key, "cost_line_id": None, "item_id": m.item_id, "description": m.description,
                         "unit": m.unit, "planned": 0.0, "on_estimate": False, "_est_unit_cost": 0.0}
        if m.kind == MoveKind.to_job:
            sent[key] += m.quantity
            cost[key] += m.quantity * m.unit_cost
            if m.lot_number and m.lot_number not in lots[key]:
                lots[key].append(m.lot_number)
        else:
            back[key] += m.quantity
            cost[key] -= m.quantity * m.unit_cost

    out_rows = []
    for key, r in rows.items():
        s, b = sent[key], back[key]
        used = s - b
        planned = r["planned"]
        status = ("not_sent" if s == 0 else "partly_sent" if s < planned - 1e-9 else "over_sent" if s > planned + 1e-9 and r["on_estimate"]
                  else "sent")
        row = {k: v for k, v in r.items() if not k.startswith("_")}
        row |= {
            "sent": round(s, 3), "returned": round(b, 3), "used": round(used, 3),
            "left_to_send": round(max(0.0, planned - s), 3),
            "used_vs_planned": round(used - planned, 3),
            "status": status, "lots": lots[key],
        }
        if with_dollars:
            row["estimated_cost"] = round(planned * r["_est_unit_cost"], 2)
            row["actual_cost"] = round(cost[key], 2)
        out_rows.append(row)

    summary = {
        "rows": len(out_rows),
        "not_sent": sum(1 for r in out_rows if r["status"] == "not_sent" and r["planned"] > 0),
        "fully_sent": sum(1 for r in out_rows if r["on_estimate"] and r["status"] in ("sent", "over_sent")),
        "not_on_estimate": sum(1 for r in out_rows if not r["on_estimate"]),
        "returns_logged": sum(1 for r in out_rows if r["returned"] > 0),
    }
    if with_dollars:
        summary["estimated_cost"] = round(sum(r["estimated_cost"] for r in out_rows), 2)
        summary["actual_cost"] = round(sum(r["actual_cost"] for r in out_rows), 2)
    return {"job_id": job.id, "job_name": job.name, "status": job.status, "rows": out_rows, "summary": summary}


def row_for(db: Session, job: Job, key: str) -> dict | None:
    for r in job_materials(db, job, with_dollars=False)["rows"]:
        if r["key"] == key:
            return r
    return None


def material_actual_cost(db: Session, job: Job) -> float:
    total = 0.0
    for m in job_moves(db, job):
        total += (m.quantity if m.kind == MoveKind.to_job else -m.quantity) * m.unit_cost
    return round(total, 2)


def items_by_id(db: Session, company_id: str, ids: set[str]) -> dict[str, StockItem]:
    if not ids:
        return {}
    return {i.id: i for i in db.scalars(select(StockItem).where(StockItem.id.in_(ids), StockItem.company_id == company_id))}
