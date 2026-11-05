"""Crews: each crew lead's usual people, set up by the GM on the Team tab.

When a job is sent out, picking the crew lead fills in their crew; it can
still be changed for that one job (someone out sick, a helper). A person is
on one crew at a time: adding them to a crew takes them off the other one.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..activity import log
from ..auth import ASSIGNS_CREWS, require_roles
from ..db import get_db
from ..models import Crew, CrewMember, Role, User

router = APIRouter(prefix="/api/crews", tags=["crews"])
FIELD = (Role.crew, Role.crew_lead)


class CrewIn(BaseModel):
    name: str = Field(default="", max_length=100)
    member_ids: list[str] = Field(default_factory=list, max_length=100)


def _out(c: Crew) -> dict:
    members = sorted((m.user for m in c.members if m.user.active), key=lambda u: u.name)
    return {"id": c.id, "lead_id": c.lead_id, "lead_name": c.lead.name, "name": c.name or f"{c.lead.name}'s crew",
            "members": [{"id": u.id, "name": u.name} for u in members]}


def _all(db: Session, company_id: str) -> list[Crew]:
    return list(db.scalars(select(Crew).where(Crew.company_id == company_id)
                           .options(selectinload(Crew.lead), selectinload(Crew.members).selectinload(CrewMember.user))))


@router.get("")
def list_crews(user: User = Depends(require_roles(*ASSIGNS_CREWS)), db: Session = Depends(get_db)):
    return sorted((_out(c) for c in _all(db, user.company_id) if c.lead.active), key=lambda c: c["lead_name"])


@router.put("/{lead_id}")
def set_crew(lead_id: str, body: CrewIn, user: User = Depends(require_roles(Role.gm)), db: Session = Depends(get_db)):
    lead = db.get(User, lead_id)
    if lead is None or lead.company_id != user.company_id or lead.role != Role.crew_lead or not lead.active:
        raise HTTPException(422, "Pick a crew lead who's on the team.")
    ids = list(dict.fromkeys(i for i in body.member_ids if i != lead_id))
    people = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids), User.company_id == user.company_id))} if ids else {}
    if any(i not in people or people[i].role not in FIELD or not people[i].active for i in ids):
        raise HTTPException(422, "Only people on the field crew can be on a crew.")
    crews = {c.lead_id: c for c in _all(db, user.company_id)}
    # A crew lead can't be on someone else's crew too.
    for c in crews.values():
        if any(m.user_id == lead_id for m in c.members):
            raise HTTPException(409, f"{lead.name} is on {c.lead.name}'s crew. Take them off that crew first.")
    crew = crews.get(lead_id)
    if crew is None:
        crew = Crew(company_id=user.company_id, lead_id=lead_id, lead=lead)
        db.add(crew)
    before = sorted(m.user.name for m in crew.members)
    crew.name = body.name.strip()
    moved = []
    for other in crews.values():  # someone added here comes off their old crew
        if other is crew:
            continue
        for m in [m for m in other.members if m.user_id in people]:
            other.members.remove(m)
            moved.append(f"{m.user.name} (was on {other.lead.name}'s crew)")
    crew.members.clear()
    db.flush()
    for i in ids:
        crew.members.append(CrewMember(company_id=user.company_id, user_id=i, user=people[i]))
    after = sorted(people[i].name for i in ids)
    log(db, user, "crew", lead_id, "Set up the crew" if not before and not crews.get(lead_id) else "Changed the crew",
        f"{lead.name}: {', '.join(after) or 'nobody else'}" + (f". Moved: {'; '.join(moved)}" if moved else ""))
    db.commit()
    db.refresh(crew)
    return _out(crew) | {"moved": moved}


@router.delete("/{lead_id}")
def remove_crew(lead_id: str, user: User = Depends(require_roles(Role.gm)), db: Session = Depends(get_db)):
    """Jobs already sent out keep the crew they were sent with."""
    crew = db.scalar(select(Crew).where(Crew.company_id == user.company_id, Crew.lead_id == lead_id))
    if crew is None:
        raise HTTPException(404, "Crew not found")
    log(db, user, "crew", lead_id, "Removed the crew", crew.lead.name)
    db.delete(crew)
    db.commit()
    return {"ok": True}
