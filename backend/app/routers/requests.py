"""Material from the field: asking for more, and checking it's all there.

Checking: the shop checks the truck is loaded before it leaves, and the
crew lead checks it's all on site, item by item. Anything short on site goes
to the office as a problem. Checks are kept as a record.

More material:

The crew lead asks on the job and signs for it by name. The warehouse, GM or a PM sees every
open request on the Materials tab and marks it sent or declines it with a
reason. Every step is in the job's history; nothing is deleted.
"""
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..activity import iso, log
from ..auth import current_user, require_roles
from ..db import get_db
from ..materials import job_materials
from ..models import JobReport, MaterialCheck, MaterialRequest, Role, StockItem, User, utcnow
from .jobs import load_job

router = APIRouter(prefix="/api", tags=["material requests"])
HANDLERS = (Role.gm, Role.pm, Role.warehouse)
ASKERS = (Role.crew_lead, Role.gm, Role.pm)


class RequestIn(BaseModel):
    item_id: str | None = None
    description: str = Field(min_length=1, max_length=200)
    quantity: float = Field(gt=0, le=1_000_000)
    unit: str = Field(default="", max_length=20)
    reason: str = Field(min_length=3, max_length=2000)
    signed_name: str = Field(min_length=2, max_length=200)
    i_am_responsible: bool


class HandleIn(BaseModel):
    status: str = Field(pattern="^(sent|declined)$")
    note: str = Field(default="", max_length=2000)


def request_out(r: MaterialRequest) -> dict:
    return {"id": r.id, "job_id": r.job_id, "job_name": r.job.name, "description": r.description, "quantity": r.quantity,
            "unit": r.unit, "reason": r.reason, "by": r.requested_by.name, "signed_name": r.signed_name, "at": iso(r.created_at),
            "status": r.status, "handled_by": r.handled_by.name if r.handled_by else None, "handled_at": iso(r.handled_at),
            "handled_note": r.handled_note}


LOAD = (selectinload(MaterialRequest.job), selectinload(MaterialRequest.requested_by), selectinload(MaterialRequest.handled_by))


@router.post("/jobs/{job_id}/material-requests", status_code=201)
def ask(job_id: str, body: RequestIn, user: User = Depends(require_roles(*ASKERS)), db: Session = Depends(get_db)):
    job = load_job(db, user, job_id)  # a crew lead: only their own jobs
    if not body.i_am_responsible:
        raise HTTPException(422, "Tick the box to sign for it.")
    if body.item_id and not db.scalar(select(StockItem.id).where(StockItem.id == body.item_id, StockItem.company_id == user.company_id)):
        raise HTTPException(422, "That item isn't on the price list")
    r = MaterialRequest(company_id=user.company_id, job_id=job.id, item_id=body.item_id, description=body.description.strip(),
                        quantity=body.quantity, unit=body.unit.strip(), reason=body.reason.strip(), requested_by_id=user.id,
                        signed_name=body.signed_name.strip())
    db.add(r)
    db.flush()
    log(db, user, "job", job.id, f"Asked for more material: {body.quantity:g} {body.unit.strip()} {r.description}".replace("  ", " "),
        f"{body.reason.strip()} (signed: {r.signed_name})")
    db.commit()
    return request_out(db.scalar(select(MaterialRequest).where(MaterialRequest.id == r.id).options(*LOAD)))


@router.get("/jobs/{job_id}/material-requests")
def for_job(job_id: str, user: User = Depends(require_roles(*ASKERS, Role.warehouse, Role.estimator, Role.owner)), db: Session = Depends(get_db)):
    job = load_job(db, user, job_id)
    rows = db.scalars(select(MaterialRequest).where(MaterialRequest.job_id == job.id, MaterialRequest.company_id == user.company_id)
                      .options(*LOAD).order_by(MaterialRequest.created_at.desc()))
    return [request_out(r) for r in rows]


@router.get("/material-requests")
def all_open(status: str = "open", user: User = Depends(require_roles(*HANDLERS)), db: Session = Depends(get_db)):
    q = select(MaterialRequest).where(MaterialRequest.company_id == user.company_id).options(*LOAD).order_by(MaterialRequest.created_at)
    if status == "recent":  # still waiting, or handled in the last 3 days
        q = q.where(or_(MaterialRequest.status == "open", MaterialRequest.handled_at >= utcnow() - timedelta(days=3)))
    elif status != "all":
        q = q.where(MaterialRequest.status == status)
    return [request_out(r) for r in db.scalars(q)]


@router.post("/material-requests/{request_id}/handle")
def handle(request_id: str, body: HandleIn, user: User = Depends(require_roles(*HANDLERS)), db: Session = Depends(get_db)):
    r = db.scalar(select(MaterialRequest).where(MaterialRequest.id == request_id, MaterialRequest.company_id == user.company_id).options(*LOAD))
    if r is None:
        raise HTTPException(404, "Request not found")
    if body.status == "declined" and len(body.note.strip()) < 3:
        raise HTTPException(422, "Say why it's declined.")
    if r.status == "open":
        r.status, r.handled_by, r.handled_at, r.handled_note = body.status, user, utcnow(), body.note.strip()
        log(db, user, "job", r.job_id, f"{'Sent' if body.status == 'sent' else 'Declined'} the material asked for: {r.description}",
            body.note.strip())
        db.commit()
        r = db.scalar(select(MaterialRequest).where(MaterialRequest.id == r.id).options(*LOAD))
    return request_out(r)


@router.get("/alerts")
def alerts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Counts for the tab badges: problems from the site waiting on the GM or
    a PM, and material asked for from the field that hasn't gone out."""
    from sqlalchemy import func

    from ..models import JobReport
    out = {"problems": 0, "material_requests": 0}
    if user.role in (Role.gm, Role.pm):
        out["problems"] = db.scalar(select(func.count()).select_from(JobReport).where(
            JobReport.company_id == user.company_id, JobReport.kind == "problem", JobReport.resolved_at.is_(None))) or 0
    if user.role in HANDLERS:
        out["material_requests"] = db.scalar(select(func.count()).select_from(MaterialRequest).where(
            MaterialRequest.company_id == user.company_id, MaterialRequest.status == "open")) or 0
    return out



# ---------- checking the material is there ----------

CHECKERS = {"loaded": (Role.gm, Role.pm, Role.warehouse), "on_site": (Role.crew_lead, Role.gm, Role.pm)}


class CheckItem(BaseModel):
    key: str = Field(max_length=80)
    here: float = Field(ge=0, le=10_000_000)


class CheckIn(BaseModel):
    kind: str = Field(pattern="^(loaded|on_site)$")
    items: list[CheckItem] = Field(default_factory=list, max_length=500)  # only the ones that aren't all there
    note: str = Field(default="", max_length=2000)


def check_out(c: MaterialCheck) -> dict:
    return {"id": c.id, "kind": c.kind, "all_here": c.all_here, "items": json.loads(c.items or "[]"), "note": c.note,
            "by": c.checked_by.name, "at": iso(c.checked_at)}


def _expected(db: Session, job, kind: str) -> list[dict]:
    """What should be there: on the truck, everything planned (or sent, if
    more went); on site, what the shop sent (or what's planned, if nothing
    has been recorded as sent yet)."""
    rows = job_materials(db, job, with_dollars=False)["rows"]
    anything_sent = any(r["sent"] > 0 for r in rows)
    out = []
    for r in rows:
        if kind == "loaded":
            want = max(r["planned"], r["sent"])
        else:
            want = r["sent"] if anything_sent else r["planned"]
        if want > 0:
            out.append({"key": r["key"], "description": r["description"], "unit": r["unit"], "expected": round(want, 3)})
    return out


@router.get("/jobs/{job_id}/material-checks")
def list_checks(job_id: str, user: User = Depends(require_roles(*ASKERS, Role.warehouse, Role.estimator, Role.owner)),
                db: Session = Depends(get_db)):
    job = load_job(db, user, job_id)
    rows = db.scalars(select(MaterialCheck).where(MaterialCheck.job_id == job.id, MaterialCheck.company_id == user.company_id)
                      .options(selectinload(MaterialCheck.checked_by)).order_by(MaterialCheck.checked_at.desc()))
    return {"expected": {k: _expected(db, job, k) for k in ("loaded", "on_site")}, "checks": [check_out(c) for c in rows]}


@router.post("/jobs/{job_id}/material-checks", status_code=201)
def add_check(job_id: str, body: CheckIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in CHECKERS[body.kind]:
        raise HTTPException(403, "Your role can't do that")
    job = load_job(db, user, job_id)
    here = {i.key: i.here for i in body.items}
    items, short = [], []
    for r in _expected(db, job, body.kind):
        got = here.get(r["key"], r["expected"])
        item = r | {"here": round(got, 3)}
        items.append(item)
        if got < r["expected"] - 1e-9:
            short.append(item)
    if not items:
        raise HTTPException(409, "There's no material on this job's list to check.")
    note = body.note.strip()
    if short and len(note) < 3:
        raise HTTPException(422, "Say what happened with what's short (a few words).")
    c = MaterialCheck(company_id=user.company_id, job_id=job.id, kind=body.kind, all_here=not short,
                      items=json.dumps(items), note=note, checked_by_id=user.id)
    db.add(c)
    lines = "; ".join(f"{s['description']}: {s['here']:g} of {s['expected']:g} {s['unit']}".strip() for s in short)
    where = "loaded on the truck" if body.kind == "loaded" else "on site"
    if short:
        log(db, user, "job", job.id, f"Checked the material {where}: {len(short)} short", f"{lines}. {note}")
        if body.kind == "on_site":  # the office needs to know now
            db.add(JobReport(company_id=user.company_id, job_id=job.id, kind="problem", created_by_id=user.id,
                             text=f"Material short on site: {lines}. {note}"))
    else:
        log(db, user, "job", job.id, f"Checked the material {where}: all there", note)
    db.commit()
    db.refresh(c)
    return check_out(c)


@router.get("/material-checks/latest")
def latest_checks(user: User = Depends(require_roles(*HANDLERS)), db: Session = Depends(get_db)):
    """For the shop's list of jobs: the last check of each kind on each job."""
    out: dict[str, dict] = {}
    rows = db.scalars(select(MaterialCheck).where(MaterialCheck.company_id == user.company_id)
                      .options(selectinload(MaterialCheck.checked_by)).order_by(MaterialCheck.checked_at))
    for c in rows:
        out.setdefault(c.job_id, {})[c.kind] = {"all_here": c.all_here, "by": c.checked_by.name, "at": iso(c.checked_at)}
    return out
