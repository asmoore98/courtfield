"""Clients: who the work is for. Shared by sales, estimating and the office."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..activity import changes, history, iso, log
from ..auth import ESTIMATES, SALES_SIDE, require_roles
from ..db import get_db
from ..models import Client, Estimate, Job, Lead, Role, User
from ..sales_schemas import ClientActiveIn, ClientIn

router = APIRouter(prefix="/api/clients", tags=["clients"])
sales_side = require_roles(*SALES_SIDE)

FIELDS = {"name": "Name", "contact_name": "Contact", "phone": "Phone", "email": "Email",
          "billing_address": "Billing address", "notes": "Notes", "links": "Plans & documents"}


def load_client(db: Session, user: User, client_id: str) -> Client:
    c = db.scalar(select(Client).where(Client.id == client_id, Client.company_id == user.company_id))
    if c is None:
        raise HTTPException(404, "Client not found")
    return c


def client_out(c: Client) -> dict:
    return {"id": c.id, "name": c.name, "contact_name": c.contact_name, "phone": c.phone, "email": c.email,
            "billing_address": c.billing_address, "notes": c.notes, "links": c.links, "active": c.active,
            "created_at": iso(c.created_at)}


def _counts(db: Session, model, company_id: str) -> dict[str, int]:
    rows = db.execute(select(model.client_id, func.count()).where(model.company_id == company_id).group_by(model.client_id))
    return {cid: n for cid, n in rows if cid}


@router.get("")
def list_clients(include_inactive: bool = False, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    q = select(Client).where(Client.company_id == user.company_id).order_by(func.lower(Client.name))
    if not include_inactive:
        q = q.where(Client.active.is_(True))
    leads, ests, jobs = (_counts(db, m, user.company_id) for m in (Lead, Estimate, Job))
    return [client_out(c) | {"leads": leads.get(c.id, 0), "estimates": ests.get(c.id, 0), "jobs": jobs.get(c.id, 0)}
            for c in db.scalars(q)]


@router.post("", status_code=201)
def add_client(body: ClientIn, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    name = body.name.strip()
    dupe = db.scalar(select(Client).where(Client.company_id == user.company_id, func.lower(Client.name) == name.lower()))
    if dupe:
        raise HTTPException(409, f"There's already a client named {dupe.name}. Pick them from the list instead.")
    c = Client(company_id=user.company_id, created_by_id=user.id, **{k: (v.strip() if isinstance(v, str) else v) for k, v in body.model_dump().items()})
    db.add(c)
    db.flush()
    log(db, user, "client", c.id, "Added client")
    db.commit()
    return client_out(c)


@router.get("/{client_id}")
def get_client(client_id: str, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    c = load_client(db, user, client_id)
    own_only = user.role == Role.sales
    leads = db.scalars(select(Lead).where(Lead.client_id == c.id, Lead.company_id == user.company_id).order_by(Lead.created_at.desc()))
    ests = db.scalars(select(Estimate).where(Estimate.client_id == c.id, Estimate.company_id == user.company_id).order_by(Estimate.created_at.desc()))
    jobs = db.scalars(select(Job).where(Job.client_id == c.id, Job.company_id == user.company_id).order_by(Job.created_at.desc()))
    from .estimates import estimate_row  # avoid a circular import at load time
    return client_out(c) | {
        "leads": [{"id": l.id, "name": l.name, "status": l.status.value, "created_at": iso(l.created_at)}
                  for l in leads if not own_only or user.id in (l.salesperson_id, l.created_by_id)],
        "estimates": [estimate_row(db, e, user) for e in ests if not own_only or e.salesperson_id == user.id],
        "jobs": [{"id": j.id, "name": j.name, "status": j.status.value} for j in jobs] if user.role in ESTIMATES else [],
        "activity": history(db, user.company_id, "client", c.id),
    }


@router.put("/{client_id}")
def edit_client(client_id: str, body: ClientIn, user: User = Depends(sales_side), db: Session = Depends(get_db)):
    c = load_client(db, user, client_id)
    new = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.model_dump().items()}
    if new["name"].lower() != c.name.lower():
        dupe = db.scalar(select(Client).where(Client.company_id == user.company_id, func.lower(Client.name) == new["name"].lower()))
        if dupe:
            raise HTTPException(409, f"There's already a client named {dupe.name}.")
    what = changes({k: getattr(c, k) for k in FIELDS}, new, FIELDS)
    for k, v in new.items():
        setattr(c, k, v)
    if what:
        log(db, user, "client", c.id, "Edited client", what)
    db.commit()
    return client_out(c)


@router.patch("/{client_id}/active")
def set_active(client_id: str, body: ClientActiveIn, user: User = Depends(require_roles(Role.gm)), db: Session = Depends(get_db)):
    """Clients are never deleted; the GM can turn one off so it drops out of pick lists."""
    c = load_client(db, user, client_id)
    if c.active != body.active:
        c.active = body.active
        log(db, user, "client", c.id, "Turned client back on" if body.active else "Turned client off", body.reason)
        db.commit()
    return client_out(c)
