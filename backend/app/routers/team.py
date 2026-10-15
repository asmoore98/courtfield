"""People, roles, labor rates and sign-ins. GM only."""
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import auth
from ..db import get_db
from ..models import DeviceSession, Role, User, utcnow
from ..schemas import PersonEdit, PersonIn, PersonOut, PersonSaved

router = APIRouter(prefix="/api/team", tags=["team"])
gm_only = auth.require_roles(*auth.MANAGES_TEAM)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _person(db: Session, u: User) -> PersonOut:
    now = utcnow()
    live = select(DeviceSession).where(
        DeviceSession.user_id == u.id, DeviceSession.revoked_at.is_(None), DeviceSession.expires_at > now
    )
    devices = db.scalar(select(func.count()).select_from(live.subquery()))
    last = db.scalar(select(func.max(DeviceSession.last_used_at)).where(DeviceSession.user_id == u.id))
    return PersonOut(id=u.id, name=u.name, role=u.role, email=u.email, hourly_cost=u.hourly_cost, active=u.active,
                     signs_in=u.role in auth.SIGNS_IN, has_password=u.password_hash is not None,
                     devices=devices or 0, last_seen=last)


def _clean_email(db: Session, email: str | None, user_id: str | None = None) -> str | None:
    if email is None or not email.strip():
        return None
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "That email address doesn't look right.")
    taken = db.scalar(select(User.id).where(func.lower(User.email) == email, User.id != (user_id or "")))
    if taken:
        raise HTTPException(409, "Someone already uses that email to sign in.")
    return email


def _load(db: Session, gm: User, person_id: str) -> User:
    u = db.get(User, person_id)
    if u is None or u.company_id != gm.company_id:
        raise HTTPException(404, "Person not found")
    return u


@router.get("", response_model=list[PersonOut])
def list_team(gm: User = Depends(gm_only), db: Session = Depends(get_db)):
    people = db.scalars(select(User).where(User.company_id == gm.company_id).order_by(User.active.desc(), User.name))
    return [_person(db, u) for u in people]


@router.post("", response_model=PersonSaved, status_code=201)
def add_person(body: PersonIn, gm: User = Depends(gm_only), db: Session = Depends(get_db)):
    signs_in = body.role in auth.SIGNS_IN
    email = _clean_email(db, body.email)
    if signs_in and not email:
        raise HTTPException(422, "Add an email so they can sign in. Crew members who don't use the app don't need one.")
    u = User(company_id=gm.company_id, name=body.name.strip(), role=body.role, hourly_cost=body.hourly_cost,
             email=email if signs_in else None)
    db.add(u)
    db.flush()
    invite_url = auth.make_invite(db, u, gm) if signs_in else None
    db.commit()
    return PersonSaved(person=_person(db, u), invite_url=invite_url)


@router.patch("/{person_id}", response_model=PersonSaved)
def edit_person(person_id: str, body: PersonEdit, gm: User = Depends(gm_only), db: Session = Depends(get_db)):
    u = _load(db, gm, person_id)
    sent = body.model_fields_set
    if u.id == gm.id and (("role" in sent and body.role != u.role) or ("active" in sent and body.active is False)):
        raise HTTPException(409, "You can't change your own role or turn off your own access. Ask another GM.")
    if "name" in sent and body.name:
        u.name = body.name.strip()
    if "hourly_cost" in sent and body.hourly_cost is not None:
        u.hourly_cost = body.hourly_cost
    if "email" in sent:
        u.email = _clean_email(db, body.email, u.id)
    if "role" in sent and body.role is not None:
        u.role = body.role
    if u.role not in auth.SIGNS_IN:
        u.email, u.password_hash = None, None
        auth.revoke_sessions(db, u.id)
    elif not u.email:
        raise HTTPException(422, "Add an email so they can sign in with this role.")
    if "active" in sent and body.active is not None:
        u.active = body.active
        if not u.active:
            auth.revoke_sessions(db, u.id)
    db.commit()
    return PersonSaved(person=_person(db, u))


@router.post("/{person_id}/invite", response_model=PersonSaved)
def new_invite(person_id: str, gm: User = Depends(gm_only), db: Session = Depends(get_db)):
    """A fresh sign-in link: for someone who never set a password, lost the
    first link, or forgot their password."""
    u = _load(db, gm, person_id)
    if not u.active or u.role not in auth.SIGNS_IN or not u.email:
        raise HTTPException(409, "This person doesn't sign in. Give them a role that uses the app and an email first.")
    url = auth.make_invite(db, u, gm)
    db.commit()
    return PersonSaved(person=_person(db, u), invite_url=url)


@router.post("/{person_id}/signout", response_model=PersonSaved)
def sign_out_everywhere(person_id: str, gm: User = Depends(gm_only), db: Session = Depends(get_db)):
    """For a lost or replaced phone: ends every sign-in this person has."""
    u = _load(db, gm, person_id)
    auth.revoke_sessions(db, u.id)
    db.commit()
    return PersonSaved(person=_person(db, u))
