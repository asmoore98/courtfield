"""Leads: what sales brings in for an estimator to price."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..activity import changes, history, iso, log
from ..auth import SALES_SIDE, require_roles
from ..db import get_db
from ..models import Estimate, Lead, LeadStatus, Role, User, utcnow
from ..sales_schemas import LeadIn, LeadStatusIn
from .clients import load_client

router = APIRouter(prefix="/api/leads", tags=["leads"])
sales_side = require_roles(*SALES_SIDE)

FIELDS = {"name": "Project", "site_address": "Site address", "parcel_id": "Parcel ID", "court_type": "Court type",
          "scope_type": "Scope", "description": "Details", "links": "Plans & documents", "bid_due": "Bid due"}


def _mine(lead: Lead, user: User) -> bool:
    return user.role != Role.sales or user.id in (lead.salesperson_id, lead.created_by_id)


def load_lead(db: Session, user: User, lead_id: str) -> Lead:
    lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.company_id == user.company_id)
                     .options(selectinload(Lead.client), selectinload(Lead.salesperson)))
    if lead is None or not _mine(lead, user):
        raise HTTPException(404, "Lead not found")
    return lead


def _check_salesperson(db: Session, user: User, person_id: str | None) -> None:
    if person_id and not db.scalar(select(User.id).where(User.id == person_id, User.company_id == user.company_id, User.active.is_(True))):
        raise HTTPException(422, "That salesperson isn't on the team")


def lead_out(lead: Lead) -> dict:
    return {
        "id": lead.id, "client_id": lead.client_id, "client_name": lead.client.name, "name": lead.name,
        "site_address": lead.site_address, "parcel_id": lead.parcel_id,
        "court_type": lead.court_type.value if lead.court_type else None,
        "scope_type": lead.scope_type.value if lead.scope_type else None,
        "description": lead.description, "links": lead.links,
        "bid_due": lead.bid_due.isoformat() if lead.bid_due else None,
        "status": lead.status.value, "status_reason": lead.status_reason,
        "salesperson_id": lead.salesperson_id, "salesperson": lead.salesperson.name if lead.salesperson else None,
        "created_at": iso(lead.created_at), "updated_at": iso(lead.updated_at),
    }


def _plain(v):
    return v.value if hasattr(v, "value") else (v.isoformat() if hasattr(v, "isoformat") else v)


@router.get("")
def list_leads(status: LeadStatus | None = None, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    q = (select(Lead).where(Lead.company_id == user.company_id)
         .options(selectinload(Lead.client), selectinload(Lead.salesperson)).order_by(Lead.created_at.desc()))
    if status:
        q = q.where(Lead.status == status)
    return [lead_out(l) for l in db.scalars(q) if _mine(l, user)]


@router.post("", status_code=201)
def add_lead(body: LeadIn, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    load_client(db, user, body.client_id)
    _check_salesperson(db, user, body.salesperson_id)
    data = body.model_dump()
    if user.role == Role.sales:
        data["salesperson_id"] = user.id  # sales always owns what they bring in
    lead = Lead(company_id=user.company_id, created_by_id=user.id, **data)
    db.add(lead)
    db.flush()
    log(db, user, "lead", lead.id, "Added lead")
    db.commit()
    return lead_out(load_lead(db, user, lead.id))


@router.get("/{lead_id}")
def get_lead(lead_id: str, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    lead = load_lead(db, user, lead_id)
    from .estimates import estimate_row
    ests = db.scalars(select(Estimate).where(Estimate.lead_id == lead.id, Estimate.company_id == user.company_id).order_by(Estimate.created_at))
    return lead_out(lead) | {
        "estimates": [estimate_row(db, e, user) for e in ests if user.role != Role.sales or e.salesperson_id == user.id],
        "activity": history(db, user.company_id, "lead", lead.id),
    }


@router.put("/{lead_id}")
def edit_lead(lead_id: str, body: LeadIn, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    lead = load_lead(db, user, lead_id)
    client = load_client(db, user, body.client_id)
    _check_salesperson(db, user, body.salesperson_id)
    new = body.model_dump()
    if user.role == Role.sales:
        new["salesperson_id"] = lead.salesperson_id or user.id
    what = changes({k: _plain(getattr(lead, k)) for k in FIELDS}, {k: _plain(new[k]) for k in FIELDS}, FIELDS)
    if lead.client_id != client.id:
        what = "; ".join(filter(None, [f"Client: {lead.client.name} → {client.name}", what]))
    for k, v in new.items():
        setattr(lead, k, v)
    lead.updated_at = utcnow()
    if what:
        log(db, user, "lead", lead.id, "Edited lead", what)
    db.commit()
    db.expire(lead)
    return lead_out(load_lead(db, user, lead.id))


@router.post("/{lead_id}/status")
def set_status(lead_id: str, body: LeadStatusIn, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    """Drop a lead (with a reason) or bring it back. The estimating statuses
    follow the lead's estimates on their own."""
    lead = load_lead(db, user, lead_id)
    if body.status not in (LeadStatus.new, LeadStatus.dropped):
        raise HTTPException(422, "A lead moves to estimating when an estimate is started for it.")
    if body.status == LeadStatus.dropped and len(body.reason.strip()) < 3:
        raise HTTPException(422, "Say why the lead is being dropped.")
    if lead.status != body.status:
        old = lead.status
        lead.status = body.status
        lead.status_reason = body.reason.strip()
        lead.updated_at = utcnow()
        log(db, user, "lead", lead.id, "Dropped lead" if body.status == LeadStatus.dropped else f"Reopened lead (was {old.value})", body.reason.strip())
        db.commit()
    return lead_out(lead)
