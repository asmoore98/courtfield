"""Leads: what sales brings in for an estimator to price, with the site
checklist sales fills in on site."""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..activity import changes, history, iso, log
from ..auth import SALES_SIDE, require_roles
from ..checklists import COURT_BLOCK, CHECKLISTS, answer_text, labels, progress, tidy
from ..db import get_db
from ..models import Estimate, Lead, LeadStatus, Role, User, utcnow
from ..sales_schemas import LeadIn, LeadStatusIn, SiteSurvey
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


def outcome(lead: Lead, statuses: list[str]) -> str:
    """Where the lead stands, following its estimates: won if any estimate
    was won, lost / no bid once every estimate was turned down, expired if
    they ran out, otherwise its own stage (new, being estimated, sent)."""
    if lead.status == LeadStatus.dropped:
        return "dropped"
    s = set(statuses)
    if "won" in s:
        return "won"
    if s and s <= {"lost", "no_bid"}:
        return "lost" if "lost" in s else "no_bid"
    if s and s <= {"lost", "no_bid", "expired"}:
        return "expired"
    return lead.status.value


def _estimate_statuses(db: Session, company_id: str, lead_ids: list[str]) -> dict[str, list[str]]:
    rows = db.execute(select(Estimate.lead_id, Estimate.status).where(Estimate.company_id == company_id, Estimate.lead_id.in_(lead_ids)))
    out: dict[str, list[str]] = {}
    for lid, st in rows:
        out.setdefault(lid, []).append(st.value)
    return out


def survey_of(lead: Lead) -> dict:
    try:
        return SiteSurvey.model_validate(json.loads(lead.survey)).model_dump() if lead.survey else SiteSurvey().model_dump()
    except ValueError:
        return SiteSurvey().model_dump()


COURT_LABELS = {"courts": ("Number of courts", ""), "length_ft": ("Court length", "ft"), "width_ft": ("Court width", "ft"),
                "surface_sf": ("Measured surface", "SF"), "paint_sf": ("Paintable area", "SF")}


def survey_changes(old: dict, new: dict, scope: str | None) -> str:
    """Each changed answer, old → new, for the activity trail."""
    out = []
    for k, (label, unit) in COURT_LABELS.items():
        a, b = old["court"].get(k), new["court"].get(k)
        if a != b:
            fmt = lambda v: "—" if v is None else f"{v:g}{' ' + unit if unit else ''}"
            out.append(f"{label}: {fmt(a)} → {fmt(b)}")
    qs = labels(scope)
    for k in list(dict.fromkeys([*old["answers"], *new["answers"]])):
        a, b = old["answers"].get(k), new["answers"].get(k)
        if a != b:
            qq = qs.get(k)
            label = qq["label"] if qq else k
            out.append(f"{label}{'' if label.endswith('?') else ':'} {answer_text(qq, a)} → {answer_text(qq, b)}")
    return "; ".join(out)


def _clean_survey(body: LeadIn) -> str:
    sv = body.survey or SiteSurvey()
    scope = body.scope_type.value if body.scope_type else None
    return json.dumps({"court": sv.court.model_dump(), "answers": tidy(scope, sv.answers)})


def lead_out(lead: Lead, statuses: list[str] | None = None) -> dict:
    survey = survey_of(lead)
    scope = lead.scope_type.value if lead.scope_type else None
    return {
        "survey": survey, "checklist": progress(scope, survey),
        "outcome": outcome(lead, statuses or []),
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
    leads = [l for l in db.scalars(q) if _mine(l, user)]
    from .estimates import refresh_expiry
    refresh_expiry(db, list(db.scalars(select(Estimate).where(Estimate.company_id == user.company_id, Estimate.lead_id.is_not(None)))))
    st = _estimate_statuses(db, user.company_id, [l.id for l in leads])
    return [lead_out(l, st.get(l.id)) for l in leads]


@router.get("/checklists")
def checklists(user: User = Depends(sales_side)):
    """The site checklist for each kind of work."""
    return {"court": COURT_BLOCK, "scopes": CHECKLISTS}


@router.post("", status_code=201)
def add_lead(body: LeadIn, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    load_client(db, user, body.client_id)
    _check_salesperson(db, user, body.salesperson_id)
    data = body.model_dump(exclude={"survey"}) | {"survey": _clean_survey(body)}
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
    ests = list(db.scalars(select(Estimate).where(Estimate.lead_id == lead.id, Estimate.company_id == user.company_id).order_by(Estimate.created_at)))
    from .estimates import refresh_expiry
    refresh_expiry(db, ests)
    return lead_out(lead, [e.status.value for e in ests]) | {
        "estimates": [estimate_row(db, e, user) for e in ests if user.role != Role.sales or e.salesperson_id == user.id],
        "activity": history(db, user.company_id, "lead", lead.id),
    }


@router.put("/{lead_id}")
def edit_lead(lead_id: str, body: LeadIn, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    lead = load_lead(db, user, lead_id)
    client = load_client(db, user, body.client_id)
    _check_salesperson(db, user, body.salesperson_id)
    new = body.model_dump(exclude={"survey"})
    if user.role == Role.sales:
        new["salesperson_id"] = lead.salesperson_id or user.id
    what = changes({k: _plain(getattr(lead, k)) for k in FIELDS}, {k: _plain(new[k]) for k in FIELDS}, FIELDS)
    if lead.client_id != client.id:
        what = "; ".join(filter(None, [f"Client: {lead.client.name} → {client.name}", what]))
    checklist_what = ""
    if body.survey is not None:
        before = survey_of(lead)
        new["survey"] = _clean_survey(body)
        checklist_what = survey_changes(before, json.loads(new["survey"]), _plain(new["scope_type"]))
    for k, v in new.items():
        setattr(lead, k, v)
    lead.updated_at = utcnow()
    if what:
        log(db, user, "lead", lead.id, "Edited lead", what)
    if checklist_what:
        log(db, user, "lead", lead.id, "Changed the site checklist", checklist_what)
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
