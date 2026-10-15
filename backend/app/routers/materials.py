"""Price list, job material lists, and warehouse stock moves."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_serializer
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..auth import EDITS_PRICES, MANAGES_STOCK, SEES_DOLLARS, SEES_MATERIALS, current_user, require_roles
from ..db import get_db
from ..materials import job_materials, on_hand, row_for
from ..models import CostCategory, CostLine, Job, MoveKind, StockItem, StockMove, User, utcnow

router = APIRouter(prefix="/api", tags=["materials"])


# ---------- schemas ----------

class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: CostCategory = CostCategory.material
    unit: str = Field(default="", max_length=20)
    unit_cost: float = Field(default=0, ge=0, le=10_000_000)
    sku: str = Field(default="", max_length=60)
    track_stock: bool = True


class ItemEdit(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: CostCategory | None = None
    unit: str | None = Field(default=None, max_length=20)
    unit_cost: float | None = Field(default=None, ge=0, le=10_000_000)
    sku: str | None = Field(default=None, max_length=60)
    track_stock: bool | None = None
    active: bool | None = None


class ItemOut(BaseModel):
    id: str
    name: str
    category: CostCategory
    unit: str
    sku: str
    track_stock: bool
    active: bool
    unit_cost: float | None = None   # hidden from roles that don't see dollars
    on_hand: float | None = None     # tracked items only


class MoveIn(BaseModel):
    kind: MoveKind
    quantity: float = Field(ge=-1_000_000, le=1_000_000)
    job_id: str | None = None
    row_key: str | None = Field(default=None, max_length=260)  # a row from the job's material list
    item_id: str | None = None
    description: str | None = Field(default=None, max_length=200)  # for things not on the price list
    unit: str | None = Field(default=None, max_length=20)
    unit_cost: float | None = Field(default=None, ge=0)  # receive only: what was paid
    lot_number: str = Field(default="", max_length=60)
    note: str = Field(default="", max_length=500)


class VoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class MoveOut(BaseModel):
    id: str
    kind: MoveKind
    item_id: str | None
    job_id: str | None
    job_name: str | None = None
    description: str
    unit: str
    quantity: float
    lot_number: str
    note: str
    recorded_by: str
    recorded_at: datetime
    voided: bool
    void_reason: str
    unit_cost: float | None = None
    on_hand_after: float | None = None

    @field_serializer("recorded_at")
    def _utc(self, v: datetime):
        return v.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


# ---------- helpers ----------

def _item_out(i: StockItem, user: User, stock: dict[str, float]) -> ItemOut:
    return ItemOut(id=i.id, name=i.name, category=i.category, unit=i.unit, sku=i.sku, track_stock=i.track_stock, active=i.active,
                   unit_cost=i.unit_cost if user.role in SEES_DOLLARS else None,
                   on_hand=stock.get(i.id, 0.0) if i.track_stock else None)


def _move_out(m: StockMove, user: User, job_names: dict[str, str] | None = None) -> MoveOut:
    return MoveOut(id=m.id, kind=m.kind, item_id=m.item_id, job_id=m.job_id,
                   job_name=(job_names or {}).get(m.job_id) if m.job_id else None,
                   description=m.description, unit=m.unit, quantity=m.quantity, lot_number=m.lot_number, note=m.note,
                   recorded_by=m.recorded_by.name, recorded_at=m.recorded_at, voided=m.voided_at is not None,
                   void_reason=m.void_reason, unit_cost=m.unit_cost if user.role in SEES_DOLLARS else None)


def _load_item(db: Session, user: User, item_id: str) -> StockItem:
    i = db.get(StockItem, item_id)
    if i is None or i.company_id != user.company_id:
        raise HTTPException(404, "Item not found")
    return i


def _load_job(db: Session, user: User, job_id: str) -> Job:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.company_id == user.company_id).options(selectinload(Job.cost_lines)))
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


def _name_taken(db: Session, company_id: str, name: str, except_id: str | None = None) -> bool:
    return db.scalar(select(StockItem.id).where(
        StockItem.company_id == company_id, func.lower(StockItem.name) == name.strip().lower(), StockItem.id != (except_id or "")
    )) is not None


# ---------- price list ----------

@router.get("/items", response_model=list[ItemOut], response_model_exclude_none=True)
def list_items(include_inactive: bool = False, user: User = Depends(require_roles(*SEES_MATERIALS)), db: Session = Depends(get_db)):
    q = select(StockItem).where(StockItem.company_id == user.company_id).order_by(StockItem.name)
    if not include_inactive:
        q = q.where(StockItem.active)
    items = list(db.scalars(q))
    stock = on_hand(db, user.company_id)
    return [_item_out(i, user, stock) for i in items]


@router.post("/items", response_model=ItemOut, status_code=201, response_model_exclude_none=True)
def add_item(body: ItemIn, user: User = Depends(require_roles(*EDITS_PRICES)), db: Session = Depends(get_db)):
    if _name_taken(db, user.company_id, body.name):
        raise HTTPException(409, "There's already an item with that name on the price list.")
    i = StockItem(company_id=user.company_id, **(body.model_dump() | {"name": body.name.strip(), "unit": body.unit.strip()}))
    db.add(i)
    db.commit()
    return _item_out(i, user, {})


@router.patch("/items/{item_id}", response_model=ItemOut, response_model_exclude_none=True)
def edit_item(item_id: str, body: ItemEdit, user: User = Depends(require_roles(*EDITS_PRICES)), db: Session = Depends(get_db)):
    i = _load_item(db, user, item_id)
    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        if _name_taken(db, user.company_id, data["name"], i.id):
            raise HTTPException(409, "There's already an item with that name on the price list.")
        data["name"] = data["name"].strip()
    for k, v in data.items():
        if v is not None:
            setattr(i, k, v)
    db.commit()
    return _item_out(i, user, on_hand(db, user.company_id, [i.id]))


# ---------- job material list ----------

@router.get("/jobs/{job_id}/materials")
def get_job_materials(job_id: str, user: User = Depends(require_roles(*SEES_MATERIALS)), db: Session = Depends(get_db)):
    job = _load_job(db, user, job_id)
    out = job_materials(db, job, with_dollars=user.role in SEES_DOLLARS)
    stock = on_hand(db, user.company_id, [r["item_id"] for r in out["rows"] if r["item_id"]])
    for r in out["rows"]:
        r["on_hand"] = stock.get(r["item_id"]) if r["item_id"] else None
    return out


@router.get("/jobs/{job_id}/materials/moves", response_model=list[MoveOut], response_model_exclude_none=True)
def get_job_moves(job_id: str, user: User = Depends(require_roles(*SEES_MATERIALS)), db: Session = Depends(get_db)):
    job = _load_job(db, user, job_id)
    moves = db.scalars(select(StockMove).where(StockMove.job_id == job.id, StockMove.company_id == user.company_id)
                       .options(selectinload(StockMove.recorded_by)).order_by(StockMove.recorded_at.desc()))
    return [_move_out(m, user) for m in moves]


# ---------- stock moves ----------

def _resolve_target(db: Session, user: User, body: MoveIn, job: Job | None) -> dict:
    """Work out item, cost line, name, unit and cost for a move."""
    line = None
    item = None
    if body.row_key:
        kind, _, ref = body.row_key.partition(":")
        if kind == "line":
            line = next((ln for ln in (job.cost_lines if job else []) if ln.id == ref and ln.category == CostCategory.material), None)
            if line is None:
                raise HTTPException(422, "That material line isn't on this job")
            item = db.get(StockItem, line.item_id) if line.item_id else None
        elif kind == "item":
            item = _load_item(db, user, ref)
        elif kind == "name":
            pass
        else:
            raise HTTPException(422, "Unknown material row")
    if body.item_id and item is None:
        item = _load_item(db, user, body.item_id)
    if item is not None and line is None and job is not None:
        line = next((ln for ln in job.cost_lines if ln.item_id == item.id and ln.category == CostCategory.material), None)

    if line is not None:
        desc, unit = line.description, line.unit or (item.unit if item else "")
        cost = item.unit_cost if item else line.unit_cost
    elif item is not None:
        desc, unit, cost = item.name, item.unit, item.unit_cost
    else:
        desc = (body.description or (body.row_key or "").partition(":")[2]).strip()
        if not desc:
            raise HTTPException(422, "Say what the material is: pick a line, a price-list item, or type a name")
        unit, cost = (body.unit or "").strip(), 0.0
    return {"item": item, "line": line, "description": desc, "unit": unit, "unit_cost": cost}


@router.post("/stock/moves", response_model=MoveOut, status_code=201, response_model_exclude_none=True)
def add_move(body: MoveIn, user: User = Depends(require_roles(*MANAGES_STOCK)), db: Session = Depends(get_db)):
    job = None
    if body.kind in (MoveKind.to_job, MoveKind.from_job):
        if not body.job_id:
            raise HTTPException(422, "Pick the job")
        job = _load_job(db, user, body.job_id)
        if body.quantity <= 0:
            raise HTTPException(422, "Quantity must be more than zero")
    elif body.kind == MoveKind.receive:
        if body.quantity <= 0:
            raise HTTPException(422, "Quantity must be more than zero")
    elif body.quantity == 0:
        raise HTTPException(422, "A count correction can't be zero")

    t = _resolve_target(db, user, body, job)
    if body.kind in (MoveKind.receive, MoveKind.adjust):
        if t["item"] is None or not t["item"].track_stock:
            raise HTTPException(422, "Receiving and counts are for price-list items the warehouse stocks")

    if body.kind == MoveKind.from_job:
        probe = StockMove(kind=MoveKind.from_job, item_id=t["item"].id if t["item"] else None,
                          cost_line_id=t["line"].id if t["line"] else None, description=t["description"])
        from ..materials import _row_key_for
        lines = [ln for ln in job.cost_lines if ln.category == CostCategory.material]
        item_to_line = {}
        for ln in lines:
            if ln.item_id and ln.item_id not in item_to_line:
                item_to_line[ln.item_id] = ln.id
        key = _row_key_for(probe, {ln.id for ln in lines}, item_to_line)
        row = row_for(db, job, key)
        out_now = (row["sent"] - row["returned"]) if row else 0.0
        if body.quantity > out_now + 1e-9:
            raise HTTPException(422, f"Only {out_now:g} {t['unit']} of {t['description']} is out on this job, so that much can't come back.".replace("  ", " "))

    cost = t["unit_cost"]
    if body.kind == MoveKind.receive and body.unit_cost is not None:
        cost = body.unit_cost
    m = StockMove(company_id=user.company_id, kind=body.kind, item_id=t["item"].id if t["item"] else None,
                  job_id=job.id if job else None, cost_line_id=t["line"].id if t["line"] else None,
                  description=t["description"], unit=t["unit"], quantity=body.quantity, unit_cost=cost,
                  lot_number=body.lot_number.strip(), note=body.note.strip(), recorded_by_id=user.id)
    db.add(m)
    db.commit()
    db.refresh(m)
    out = _move_out(m, user)
    if m.item_id and t["item"].track_stock:
        out.on_hand_after = on_hand(db, user.company_id, [m.item_id]).get(m.item_id, 0.0)
    return out


@router.post("/stock/moves/{move_id}/void", response_model=MoveOut, response_model_exclude_none=True)
def void_move(move_id: str, body: VoidIn, user: User = Depends(require_roles(*MANAGES_STOCK)), db: Session = Depends(get_db)):
    m = db.get(StockMove, move_id)
    if m is None or m.company_id != user.company_id:
        raise HTTPException(404, "Entry not found")
    if m.voided_at is not None:
        raise HTTPException(409, "Already voided")
    if m.kind == MoveKind.to_job and m.job_id:
        job = _load_job(db, user, m.job_id)
        before = {r["key"]: r for r in job_materials(db, job, False)["rows"]}
        m.voided_at = utcnow()
        db.flush()
        after = {r["key"]: r for r in job_materials(db, job, False)["rows"]}
        bad = [k for k, r in after.items() if r["returned"] > r["sent"] + 1e-9 and before.get(k)]
        if bad:
            db.rollback()
            raise HTTPException(409, "Void the return for this material first; otherwise more would have come back than went out.")
    m.voided_at, m.voided_by_id, m.void_reason = utcnow(), user.id, body.reason.strip()
    db.commit()
    db.refresh(m)
    return _move_out(m, user)


@router.get("/stock/moves", response_model=list[MoveOut], response_model_exclude_none=True)
def list_moves(item_id: str | None = None, limit: int = 200,
               user: User = Depends(require_roles(*(MANAGES_STOCK | {*SEES_DOLLARS}))), db: Session = Depends(get_db)):
    q = (select(StockMove).where(StockMove.company_id == user.company_id)
         .options(selectinload(StockMove.recorded_by)).order_by(StockMove.recorded_at.desc()).limit(min(limit, 1000)))
    if item_id:
        q = q.where(StockMove.item_id == item_id)
    moves = list(db.scalars(q))
    names = dict(db.execute(select(Job.id, Job.name).where(Job.id.in_({m.job_id for m in moves if m.job_id}))).all())
    return [_move_out(m, user, names) for m in moves]
