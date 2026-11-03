"""Estimates: a priced scope of work for a client, kept as locked versions.

- Every save makes a new version. Old versions can't be changed; only the GM
  can remove one, and that's a void with a reason that stays on record.
- Status: draft → sent → won / lost / no bid, or expired when a sent estimate
  passes its valid-for days. Every change is in the activity trail.
- Sales sees their own estimates' status and price and can open the proposal;
  only GM, estimators and PMs see what the work costs us.
- A won estimate becomes a job with one tap.
"""
import json
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..activity import history, iso, log, log_system
from ..auth import ESTIMATES, SALES_SIDE, require_roles
from ..db import get_db
from ..quantities import labor_charge
from ..models import (
    Client, Company, Estimate, EstimateStatus, EstimateVersion, Job, Lead, LeadStatus, Role, StockItem, TaskKind, User, utcnow,
)
from ..sales_schemas import EstimateData, EstimateIn, EstimateStatusIn, NoteIn, VoidIn
from ..schemas import JobIn
from .clients import load_client
from .jobs import build_job, check_task_refs

router = APIRouter(prefix="/api/estimates", tags=["estimates"])
sales_side = require_roles(*SALES_SIDE)
estimators = require_roles(*ESTIMATES)

FOLLOW_UP_DAYS = 15
STATUS_WORDS = {"draft": "Draft", "sent": "Sent", "won": "Won", "lost": "Lost", "no_bid": "No bid", "expired": "Expired"}
SALESPEOPLE_ROLES = (Role.sales, Role.gm, Role.pm, Role.estimator)


# ---------- money ----------

def totals(d: EstimateData) -> dict:
    """What the work costs us and what we charge, by kind, and the margin.
    Mirrors estimateOf() on the front end.

    Cost: crew hours x each task's cost rate (or the old single rate), sub
    prices, and cost lines, plus sales tax on materials.
    Charge (built pricing): crew work at its price per unit, or hours x
    charge rate; every line and sub plus
    its own markup (or the default for its kind; materials are marked up with
    their tax); then the markup on the whole job; then the adjustment.
    Fees (permits, city fees) pass through at cost: no markup of any kind.
    """
    crew = [t for t in d.tasks if t.kind == TaskKind.crew]
    subs = [t for t in d.tasks if t.kind == TaskKind.sub]
    hours = sum(t.estimated_hours for t in crew)
    labor = sum(t.estimated_hours * (t.cost_rate if t.cost_rate is not None else d.estimated_labor_rate) for t in crew)
    cat = {"material": 0.0, "equipment": 0.0, "subcontractor": 0.0, "other": 0.0, "fee": 0.0}
    charge = {"labor": sum(labor_charge(t) for t in crew),
              "material": 0.0, "equipment": 0.0, "subcontractor": 0.0, "other": 0.0}
    fees = 0.0
    tax = 0.0
    for ln in d.cost_lines:
        k = ln.category.value
        cost = ln.quantity * ln.unit_cost
        if k == "fee":
            cat["fee"] += cost
            fees += cost
            continue
        line_tax = cost * d.sales_tax_pct / 100 if k == "material" else 0.0
        m = ln.markup_pct if ln.markup_pct is not None else getattr(d.markups, k)
        cat[k] += cost
        tax += line_tax
        charge[k] += (cost + line_tax) * (1 + m / 100)
    for t in subs:
        m = t.markup_pct if t.markup_pct is not None else d.markups.subcontractor
        cat["subcontractor"] += t.sub_price or 0
        charge["subcontractor"] += (t.sub_price or 0) * (1 + m / 100)
    total = labor + tax + sum(cat.values())
    subtotal = sum(charge.values())
    overall = subtotal * d.overall_markup / 100
    built = subtotal + overall + fees
    price = round(built + d.adjustment, 2) if d.priced == "built" else d.price
    profit = price - total
    return {"hours": hours, "labor": labor, **cat, "sales_tax": tax, "total_cost": total,
            "charge": {k: round(v, 2) for k, v in charge.items()}, "subtotal": round(subtotal, 2), "fees": round(fees, 2),
            "overall_markup": d.overall_markup if d.priced == "built" else 0, "overall_amount": round(overall, 2),
            "built_price": round(built, 2), "adjustment": d.adjustment if d.priced == "built" else 0, "priced": d.priced,
            "price": price, "profit": profit, "margin_pct": profit / price if price > 0 else None,
            "markup_pct": profit / total if total > 0 else None}


def finalize(d: EstimateData) -> EstimateData:
    """Built prices are worked out here, never taken from the screen."""
    if d.priced == "built":
        price = totals(d)["price"]
        if price < 0:
            raise HTTPException(422, "The adjustment takes the price below zero.")
        d = d.model_copy(update={"price": price})
    return d


# ---------- loading and rules ----------

def _visible(e: Estimate, user: User) -> bool:
    return user.role != Role.sales or e.salesperson_id == user.id


def load_estimate(db: Session, user: User, estimate_id: str) -> Estimate:
    e = db.scalar(select(Estimate).where(Estimate.id == estimate_id, Estimate.company_id == user.company_id)
                  .options(selectinload(Estimate.client), selectinload(Estimate.salesperson),
                           selectinload(Estimate.versions).selectinload(EstimateVersion.created_by)))
    if e is None or not _visible(e, user):
        raise HTTPException(404, "Estimate not found")
    refresh_expiry(db, [e])
    return e


def valid_until(e: Estimate) -> datetime | None:
    return e.sent_at + timedelta(days=e.valid_days) if e.sent_at else None


def refresh_expiry(db: Session, ests) -> None:
    """A sent estimate past its valid-for days is marked expired, automatically."""
    now = utcnow()
    changed = False
    for e in ests:
        until = valid_until(e)
        if e.status == EstimateStatus.sent and until and now >= until:
            e.status = EstimateStatus.expired
            e.updated_at = now
            log_system(db, e.company_id, "estimate", e.id, "Expired", f"Not accepted within {e.valid_days} days of being sent.")
            changed = True
    if changed:
        db.commit()


def follow_up(e: Estimate, now: datetime | None = None) -> str | None:
    """Why someone should call the client about this estimate, or None."""
    now = now or utcnow()
    if e.status == EstimateStatus.sent and e.sent_at:
        last = max(e.sent_at, e.last_follow_up_at or e.sent_at)
        days = (now - last).days
        if days >= FOLLOW_UP_DAYS:
            since = "sent" if last == e.sent_at else "the last follow-up"
            return f"{days} days since {since}. Check in with the client."
    if e.status == EstimateStatus.expired:
        until = valid_until(e)
        if until and (e.last_follow_up_at is None or e.last_follow_up_at < until):
            return "Expired without an answer. Reach out before it goes cold."
    return None


def current(e: Estimate) -> EstimateVersion:
    return next(v for v in e.versions if v.version == e.current_version)


def estimate_row(db: Session, e: Estimate, user: User) -> dict:
    """One line in a list. Sales gets the price, never the cost."""
    v = current(e)
    row = {
        "id": e.id, "number": e.number, "name": e.name, "client_id": e.client_id, "client_name": e.client.name,
        "status": e.status.value, "status_label": STATUS_WORDS[e.status.value], "version": e.current_version,
        "price": v.price, "salesperson": e.salesperson.name if e.salesperson else None, "salesperson_id": e.salesperson_id,
        "sent_at": iso(e.sent_at), "valid_until": iso(valid_until(e)), "valid_days": e.valid_days,
        "follow_up": follow_up(e), "last_follow_up_at": iso(e.last_follow_up_at),
        "job_id": e.job_id, "lead_id": e.lead_id, "created_at": iso(e.created_at), "updated_at": iso(e.updated_at),
    }
    if user.role in ESTIMATES:
        row["total_cost"] = v.total_cost
        row["margin_pct"] = (v.price - v.total_cost) / v.price if v.price > 0 else None
    return row


def _version_out(v: EstimateVersion, user: User) -> dict:
    out = {"version": v.version, "created_at": iso(v.created_at), "by": v.created_by.name, "note": v.note,
           "price": v.price, "removed": v.voided_at is not None, "removed_reason": v.void_reason}
    if user.role in ESTIMATES:
        out["total_cost"] = v.total_cost
    return out


def _check_refs(db: Session, user: User, body: EstimateIn) -> Client:
    client = load_client(db, user, body.client_id)
    if body.salesperson_id and not db.scalar(select(User.id).where(
            User.id == body.salesperson_id, User.company_id == user.company_id, User.active.is_(True))):
        raise HTTPException(422, "That salesperson isn't on the team")
    ids = {ln.item_id for ln in body.data.cost_lines if ln.item_id}
    if ids:
        found = set(db.scalars(select(StockItem.id).where(StockItem.id.in_(ids), StockItem.company_id == user.company_id)))
        if ids - found:
            raise HTTPException(422, "A cost line points at a price-list item that doesn't exist")
    check_task_refs(db, body.data.tasks, user.company_id)
    return client


def _new_version(e: Estimate, user: User, body: EstimateIn, number: int) -> EstimateVersion:
    d = finalize(body.data)
    t = totals(d)
    return EstimateVersion(company_id=user.company_id, estimate_id=e.id, version=number, created_by_id=user.id,
                           data=d.model_dump_json(), price=t["price"], total_cost=t["total_cost"], note=body.note.strip())


def _adjust_note(d: EstimateData) -> str:
    if d.priced != "built" or round(d.adjustment, 2) == 0:
        return ""
    sign = "+" if d.adjustment > 0 else "−"
    return f"Price adjusted {sign}${abs(d.adjustment):,.2f}: {d.adjustment_reason.strip()}"


def _next_number(db: Session, company_id: str) -> str:
    year = utcnow().year
    taken = db.scalars(select(Estimate.number).where(Estimate.company_id == company_id, Estimate.number.like(f"E-{year}-%")))
    seq = max((int(m.group(1)) for n in taken if (m := re.fullmatch(rf"E-{year}-(\d+)", n))), default=0) + 1
    return f"E-{year}-{seq:03d}"


# ---------- routes ----------

@router.get("/people")
def salespeople(user: User = Depends(sales_side), db: Session = Depends(get_db)):
    """Who can be named as the salesperson on a lead or estimate."""
    people = db.scalars(select(User).where(User.company_id == user.company_id, User.active.is_(True),
                                           User.role.in_(SALESPEOPLE_ROLES)).order_by(User.name))
    return [{"id": p.id, "name": p.name, "role": p.role.value} for p in people]


@router.get("")
def list_estimates(status: EstimateStatus | None = None, client_id: str | None = None,
                   user: User = Depends(sales_side), db: Session = Depends(get_db)):
    q = (select(Estimate).where(Estimate.company_id == user.company_id)
         .options(selectinload(Estimate.client), selectinload(Estimate.salesperson), selectinload(Estimate.versions))
         .order_by(Estimate.updated_at.desc()))
    if user.role == Role.sales:
        q = q.where(Estimate.salesperson_id == user.id)
    if client_id:
        q = q.where(Estimate.client_id == client_id)
    ests = list(db.scalars(q))
    refresh_expiry(db, ests)
    return [estimate_row(db, e, user) for e in ests if status is None or e.status == status]


@router.post("", status_code=201)
def create_estimate(body: EstimateIn, user: User = Depends(estimators), db: Session = Depends(get_db)):
    _check_refs(db, user, body)
    lead = None
    if body.lead_id:
        lead = db.scalar(select(Lead).where(Lead.id == body.lead_id, Lead.company_id == user.company_id))
        if lead is None:
            raise HTTPException(422, "That lead doesn't exist")
    company = db.get(Company, user.company_id)
    for attempt in range(3):  # two people saving at the same moment could grab the same number
        e = Estimate(company_id=user.company_id, number=_next_number(db, user.company_id), client_id=body.client_id,
                     lead_id=body.lead_id, name=body.name.strip(), created_by_id=user.id, current_version=1,
                     salesperson_id=body.salesperson_id or (lead.salesperson_id if lead else None),
                     valid_days=body.valid_days or company.estimate_valid_days)
        db.add(e)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise HTTPException(409, "Couldn't number the estimate. Save again.")
    db.add(_new_version(e, user, body, 1))
    log(db, user, "estimate", e.id, f"Started estimate {e.number} (v1)", "; ".join(filter(None, [body.note.strip(), _adjust_note(body.data)])))
    if lead:
        if lead.status == LeadStatus.new:
            lead.status = LeadStatus.estimating
            lead.updated_at = utcnow()
        log(db, user, "lead", lead.id, f"Estimate {e.number} started")
    db.commit()
    return estimate_row(db, load_estimate(db, user, e.id), user)


@router.get("/{estimate_id}")
def get_estimate(estimate_id: str, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    e = load_estimate(db, user, estimate_id)
    versions = [v for v in e.versions if user.role == Role.gm or v.voided_at is None]
    out = estimate_row(db, e, user) | {
        "versions": [_version_out(v, user) for v in reversed(versions)],
        "activity": history(db, user.company_id, "estimate", e.id),
        "client": {"id": e.client.id, "name": e.client.name, "contact_name": e.client.contact_name,
                   "phone": e.client.phone, "email": e.client.email},
    }
    if user.role in ESTIMATES:
        v = current(e)
        d = EstimateData.model_validate_json(v.data)
        out["data"] = json.loads(v.data)
        out["totals"] = totals(d)
    return out


@router.get("/{estimate_id}/versions/{number}")
def get_version(estimate_id: str, number: int, user: User = Depends(estimators), db: Session = Depends(get_db)):
    e = load_estimate(db, user, estimate_id)
    v = next((v for v in e.versions if v.version == number), None)
    if v is None or (v.voided_at is not None and user.role != Role.gm):
        raise HTTPException(404, "Version not found")
    d = EstimateData.model_validate_json(v.data)
    return _version_out(v, user) | {"data": json.loads(v.data), "totals": totals(d), "current": v.version == e.current_version}


@router.post("/{estimate_id}/versions", status_code=201)
def save_version(estimate_id: str, body: EstimateIn, user: User = Depends(estimators), db: Session = Depends(get_db)):
    """Saving an edit never changes an old version: it adds the next one."""
    e = load_estimate(db, user, estimate_id)
    if e.status == EstimateStatus.won:
        raise HTTPException(409, "This estimate is won and locked. Changes go on the job from here.")
    client = _check_refs(db, user, body)
    number = max(v.version for v in e.versions) + 1
    db.add(_new_version(e, user, body, number))
    moved = []
    if e.client_id != client.id:
        moved.append(f"Client: {e.client.name} → {client.name}")
    if e.name != body.name.strip():
        moved.append(f"Name: {e.name} → {body.name.strip()}")
    e.client_id, e.name, e.current_version = client.id, body.name.strip(), number
    if body.salesperson_id is not None:
        e.salesperson_id = body.salesperson_id or None
    if body.valid_days:
        e.valid_days = body.valid_days
    e.updated_at = utcnow()
    log(db, user, "estimate", e.id, f"Saved v{number}", "; ".join(filter(None, [body.note.strip(), _adjust_note(body.data), *moved])))
    db.commit()
    db.expire(e)
    return estimate_row(db, load_estimate(db, user, e.id), user)


@router.post("/{estimate_id}/status")
def set_status(estimate_id: str, body: EstimateStatusIn, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    e = load_estimate(db, user, estimate_id)
    if e.job_id:
        raise HTTPException(409, "A job was made from this estimate, so its status is locked.")
    if body.status == EstimateStatus.expired:
        raise HTTPException(422, "Estimates expire on their own when their valid-for days run out.")
    if body.status in (EstimateStatus.lost, EstimateStatus.no_bid) and len(body.note.strip()) < 3:
        raise HTTPException(422, "Say why, so we can learn from it (price, timing, went with someone else…).")
    if body.status == e.status and body.status != EstimateStatus.sent:
        return estimate_row(db, e, user)
    if body.status == EstimateStatus.sent and e.status != EstimateStatus.won and not body.checked_customer_text:
        raise HTTPException(422, "Read what the customer will see on the proposal and tick the box first.")
    old = e.status
    now = utcnow()
    e.status = body.status
    e.updated_at = now
    if body.status == EstimateStatus.sent:
        e.sent_at, e.last_follow_up_at, e.decided_at = now, None, None
    elif body.status in (EstimateStatus.won, EstimateStatus.lost, EstimateStatus.no_bid):
        e.decided_at = now
    else:
        e.decided_at = None
    verb = "Re-sent" if old == body.status == EstimateStatus.sent else f"Marked {STATUS_WORDS[body.status.value].lower()}"
    log(db, user, "estimate", e.id, f"{verb} (v{e.current_version})", body.note.strip())
    if e.lead_id:
        lead = db.get(Lead, e.lead_id)
        if lead:
            lead.updated_at = now
            if body.status == EstimateStatus.sent and lead.status in (LeadStatus.new, LeadStatus.estimating):
                lead.status = LeadStatus.estimated
            words = "sent to the client" if body.status == EstimateStatus.sent else f"marked {STATUS_WORDS[body.status.value].lower()}"
            log(db, user, "lead", lead.id, f"Estimate {e.number} {words}", body.note.strip())
    db.commit()
    return estimate_row(db, e, user)


@router.post("/{estimate_id}/follow-up")
def log_follow_up(estimate_id: str, body: NoteIn, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    e = load_estimate(db, user, estimate_id)
    if len(body.note.strip()) < 3:
        raise HTTPException(422, "Write a line about the follow-up (who you talked to, what they said).")
    e.last_follow_up_at = utcnow()
    log(db, user, "estimate", e.id, "Followed up with the client", body.note.strip())
    db.commit()
    return estimate_row(db, e, user)


@router.post("/{estimate_id}/versions/{number}/remove")
def remove_version(estimate_id: str, number: int, body: VoidIn, user: User = Depends(require_roles(Role.gm)),
                   db: Session = Depends(get_db)):
    """GM only. The version is kept on record, marked removed with the reason."""
    e = load_estimate(db, user, estimate_id)
    v = next((v for v in e.versions if v.version == number), None)
    if v is None or v.voided_at is not None:
        raise HTTPException(404, "Version not found")
    left = [x for x in e.versions if x.voided_at is None and x.version != number]
    if not left:
        raise HTTPException(409, "That's the only version left. An estimate needs at least one.")
    if e.job_id and v.version == e.current_version:
        raise HTTPException(409, "The job was made from this version, so it stays.")
    v.voided_at, v.voided_by_id, v.void_reason = utcnow(), user.id, body.reason.strip()
    if e.current_version == number:
        e.current_version = max(x.version for x in left)
    e.updated_at = utcnow()
    log(db, user, "estimate", e.id, f"Removed v{number}", body.reason.strip())
    db.commit()
    return estimate_row(db, e, user)


@router.post("/{estimate_id}/create-job", status_code=201)
def create_job(estimate_id: str, user: User = Depends(estimators), db: Session = Depends(get_db)):
    """Turn a won estimate into a job: site, tasks, hours and costs carry over."""
    e = load_estimate(db, user, estimate_id)
    if e.status != EstimateStatus.won:
        raise HTTPException(409, "Mark the estimate won first.")
    if e.job_id:
        raise HTTPException(409, "A job was already made from this estimate.")
    v = current(e)
    d = EstimateData.model_validate_json(v.data)
    body = JobIn(name=e.name, client=e.client.name, address=d.site_address, parcel_id=d.parcel_id, lat=d.lat, lng=d.lng,
                 **{f"site_{k}": getattr(d, f"site_{k}") for k in ("street", "city", "state", "zip")},
                 court_type=d.court_type, scope_type=d.scope_type, contract_amount=d.price,
                 estimated_labor_rate=d.estimated_labor_rate, sales_tax_pct=d.sales_tax_pct,
                 tasks=[t.model_copy(update={"id": None, "template_id": t.template_id}) for t in d.tasks],
                 cost_lines=[c.model_copy(update={"id": None}) for c in d.cost_lines])
    job = build_job(db, user, body, client_id=e.client_id)
    e.job_id = job.id
    e.updated_at = utcnow()
    log(db, user, "estimate", e.id, f"Made job from v{v.version}")
    log(db, user, "job", job.id, f"Made from estimate {e.number} v{v.version}")
    db.commit()
    return {"job_id": job.id}


@router.get("/{estimate_id}/proposal")
def proposal(estimate_id: str, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    """What the client sees: scope and price. No costs, markups or margins,
    whoever asks for it."""
    e = load_estimate(db, user, estimate_id)
    v = current(e)
    d = EstimateData.model_validate_json(v.data)
    c = db.get(Company, user.company_id)
    issued = e.sent_at or v.created_at
    return {
        "company": {"name": c.proposal_name or c.name, "address": c.proposal_address, "phone": c.proposal_phone,
                    "email": c.proposal_email, "license": c.proposal_license, "logo_url": c.proposal_logo_url,
                    "terms": c.proposal_terms},
        "client": {"name": e.client.name, "contact_name": e.client.contact_name, "phone": e.client.phone,
                   "email": e.client.email, "billing_address": e.client.billing_address},
        "number": e.number, "version": v.version, "name": e.name, "status": e.status.value,
        "issued": iso(issued), "valid_until": iso(issued + timedelta(days=e.valid_days)), "valid_days": e.valid_days,
        "site_address": d.site_address, "parcel_id": d.parcel_id, "court_type": d.court_type.value, "scope_type": d.scope_type.value,
        "scope_text": d.scope_text, "work_items": [t.name for t in d.tasks], "exclusions": d.exclusions, "price": d.price,
        "notes": d.customer_notes,
        # fees are listed so the client sees they're already in the price
        "fees": [{"description": ln.description, "amount": round(ln.quantity * ln.unit_cost, 2)}
                 for ln in d.cost_lines if ln.category.value == "fee" and ln.quantity * ln.unit_cost > 0],
        "salesperson": e.salesperson.name if e.salesperson else None,
    }
