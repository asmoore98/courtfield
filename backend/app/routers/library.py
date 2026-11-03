"""The library: the task list (GM keeps it), subcontractors, and the
company's default rates and markups for new estimates."""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..activity import changes, history, iso, log, log_system
from ..auth import ESTIMATES, require_roles
from ..db import get_db
from ..library_starter import STARTER_TASKS, STARTER_UNITS
from ..schemas import Unit
from ..models import Company, Estimate, EstimateVersion, Job, JobTask, Role, Subcontractor, TaskKind, TaskTemplate, TaskType, User, utcnow

router = APIRouter(prefix="/api/library", tags=["library"])
estimators = require_roles(*ESTIMATES)
gm_only = require_roles(Role.gm)


# ---------- shapes ----------

class TaskTemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    aliases: str = Field(default="", max_length=2000)
    task_type: TaskType = TaskType.other
    kind: TaskKind = TaskKind.crew
    cost_rate: float | None = Field(default=None, ge=0, le=100_000)
    charge_rate: float | None = Field(default=None, ge=0, le=100_000)
    unit: Unit = "hr"
    production_rate: float | None = Field(default=None, ge=0, le=1_000_000)
    unit_price: float | None = Field(default=None, ge=0, le=1_000_000)
    coats: float | None = Field(default=None, ge=0, le=50)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def _unit_fields(self):
        if self.unit == "hr":
            self.production_rate = self.unit_price = None
        if self.unit != "sf_coat":
            self.coats = None
        return self


class ActiveIn(BaseModel):
    active: bool
    reason: str = Field(default="", max_length=1000)


class SubIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    trade: str = Field(default="", max_length=100)
    contact_name: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=254)
    notes: str = Field(default="", max_length=5000)
    links: str = Field(default="", max_length=5000)


class DefaultsIn(BaseModel):
    default_cost_rate: float = Field(ge=0, le=100_000)
    default_charge_rate: float = Field(ge=0, le=100_000)
    markup_material: float = Field(ge=0, le=1000)
    markup_equipment: float = Field(ge=0, le=1000)
    markup_subcontractor: float = Field(ge=0, le=1000)
    markup_other: float = Field(ge=0, le=1000)


DEFAULT_FIELDS = tuple(DefaultsIn.model_fields)
TASK_LABELS = {"name": "Name", "aliases": "Other names", "task_type": "Type", "kind": "Crew or sub",
               "cost_rate": "Cost rate", "charge_rate": "Charge rate", "unit": "Measured in",
               "production_rate": "Production rate", "unit_price": "Price per unit", "coats": "Coats", "notes": "Notes"}
SUB_LABELS = {"name": "Name", "trade": "Trade", "contact_name": "Contact", "phone": "Phone", "email": "Email",
              "notes": "Notes", "links": "Documents"}


def _alias_text(text: str) -> str:
    """One name per line, trimmed, no blanks or repeats (commas also split)."""
    seen, out = set(), []
    for part in text.replace(",", "\n").split("\n"):
        p = " ".join(part.split())
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return "\n".join(out)


def task_out(t: TaskTemplate) -> dict:
    return {"id": t.id, "name": t.name, "aliases": [a for a in t.aliases.split("\n") if a], "task_type": t.task_type.value,
            "kind": t.kind.value, "cost_rate": t.cost_rate, "charge_rate": t.charge_rate, "unit": t.unit or "hr",
            "production_rate": t.production_rate, "unit_price": t.unit_price, "coats": t.coats, "notes": t.notes, "active": t.active}


def sub_out(s: Subcontractor) -> dict:
    return {"id": s.id, "name": s.name, "trade": s.trade, "contact_name": s.contact_name, "phone": s.phone,
            "email": s.email, "notes": s.notes, "links": s.links, "active": s.active}


def defaults_out(c: Company) -> dict:
    return {k: getattr(c, k) for k in DEFAULT_FIELDS}


def _plain(v):
    return v.value if hasattr(v, "value") else v


# ---------- everything an estimate form needs ----------

def add_starter(db: Session, user: User) -> int:
    """Add the starter list. Names already in the library are skipped."""
    existing = list(db.scalars(select(TaskTemplate).where(TaskTemplate.company_id == user.company_id)))
    taken = {n.lower() for t in existing for n in [t.name, *t.aliases.split("\n")] if n}
    added = 0
    for name, aliases, ttype, kind in STARTER_TASKS:
        free = [a for a in aliases if a.lower() not in taken]
        if name.lower() in taken:
            continue
        unit, coats = STARTER_UNITS.get(name, ("hr", None))
        db.add(TaskTemplate(company_id=user.company_id, created_by_id=user.id, name=name, aliases="\n".join(free),
                            task_type=ttype, kind=kind, unit=unit, coats=coats))
        taken |= {name.lower(), *(a.lower() for a in free)}
        added += 1
    return added


@router.get("")
def library(user: User = Depends(estimators), db: Session = Depends(get_db)):
    c = db.get(Company, user.company_id)
    # A company starts with the starter list already in, so nobody opens an empty library.
    if not db.scalar(select(func.count()).select_from(TaskTemplate).where(TaskTemplate.company_id == user.company_id)):
        n = add_starter(db, user)
        log_system(db, user.company_id, "library", user.company_id, f"Loaded the starter task list ({n} tasks)")
        db.commit()
    tasks = db.scalars(select(TaskTemplate).where(TaskTemplate.company_id == user.company_id).order_by(func.lower(TaskTemplate.name)))
    subs = db.scalars(select(Subcontractor).where(Subcontractor.company_id == user.company_id).order_by(func.lower(Subcontractor.name)))
    return {"tasks": [task_out(t) for t in tasks], "subs": [sub_out(s) for s in subs], "defaults": defaults_out(c)}


@router.put("/defaults")
def set_defaults(body: DefaultsIn, user: User = Depends(gm_only), db: Session = Depends(get_db)):
    c = db.get(Company, user.company_id)
    labels = {"default_cost_rate": "Default cost rate", "default_charge_rate": "Default charge rate",
              "markup_material": "Material markup %", "markup_equipment": "Equipment markup %",
              "markup_subcontractor": "Sub markup %", "markup_other": "Other markup %"}
    what = changes({k: str(getattr(c, k)) for k in DEFAULT_FIELDS}, {k: str(v) for k, v in body.model_dump().items()}, labels)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    if what:
        log(db, user, "library", c.id, "Changed default rates and markups", what)
    db.commit()
    return defaults_out(c)


# ---------- tasks (GM keeps the list) ----------

def _load_task(db: Session, user: User, task_id: str) -> TaskTemplate:
    t = db.scalar(select(TaskTemplate).where(TaskTemplate.id == task_id, TaskTemplate.company_id == user.company_id))
    if t is None:
        raise HTTPException(404, "Task not found")
    return t


def _clash(db: Session, user: User, names: list[str], skip_id: str | None = None) -> str | None:
    """The library entry that already uses one of these names, if any."""
    wanted = {n.lower() for n in names if n}
    for t in db.scalars(select(TaskTemplate).where(TaskTemplate.company_id == user.company_id, TaskTemplate.active.is_(True))):
        if t.id == skip_id:
            continue
        taken = {t.name.lower(), *(a.lower() for a in t.aliases.split("\n") if a)}
        hit = wanted & taken
        if hit:
            return f"“{next(iter(hit))}” is already used by {t.name}. Each name points at one task so the hours stay comparable."
    return None


@router.post("/tasks", status_code=201)
def add_task(body: TaskTemplateIn, user: User = Depends(gm_only), db: Session = Depends(get_db)):
    data = body.model_dump() | {"name": " ".join(body.name.split()), "aliases": _alias_text(body.aliases)}
    msg = _clash(db, user, [data["name"], *data["aliases"].split("\n")])
    if msg:
        raise HTTPException(409, msg)
    t = TaskTemplate(company_id=user.company_id, created_by_id=user.id, **data)
    db.add(t)
    db.flush()
    log(db, user, "task", t.id, f"Added {t.name} to the task library")
    db.commit()
    return task_out(t)


@router.put("/tasks/{task_id}")
def edit_task(task_id: str, body: TaskTemplateIn, user: User = Depends(gm_only), db: Session = Depends(get_db)):
    t = _load_task(db, user, task_id)
    data = body.model_dump() | {"name": " ".join(body.name.split()), "aliases": _alias_text(body.aliases)}
    msg = _clash(db, user, [data["name"], *data["aliases"].split("\n")], skip_id=t.id)
    if msg:
        raise HTTPException(409, msg)
    what = changes({k: str(_plain(getattr(t, k)) if getattr(t, k) is not None else "") for k in TASK_LABELS},
                   {k: str(_plain(v)) if v is not None else "" for k, v in data.items()}, TASK_LABELS)
    for k, v in data.items():
        setattr(t, k, v)
    t.updated_at = utcnow()
    if what:
        log(db, user, "task", t.id, f"Edited {t.name}", what)
    db.commit()
    return task_out(t)


@router.patch("/tasks/{task_id}/active")
def task_active(task_id: str, body: ActiveIn, user: User = Depends(gm_only), db: Session = Depends(get_db)):
    """Tasks are never deleted (old estimates and jobs point at them); turned off, they drop out of searches."""
    t = _load_task(db, user, task_id)
    if body.active and not t.active:
        msg = _clash(db, user, [t.name, *t.aliases.split("\n")], skip_id=t.id)
        if msg:
            raise HTTPException(409, msg)
    if t.active != body.active:
        t.active = body.active
        log(db, user, "task", t.id, f"Turned {t.name} {'back on' if body.active else 'off'}", body.reason)
        db.commit()
    return task_out(t)


@router.get("/tasks/{task_id}/history")
def task_history(task_id: str, user: User = Depends(estimators), db: Session = Depends(get_db)):
    t = _load_task(db, user, task_id)
    return history(db, user.company_id, "task", t.id)


@router.post("/tasks/starter")
def load_starter(user: User = Depends(gm_only), db: Session = Depends(get_db)):
    """Add the starter list (or the tasks added to it since). Names already in the library are skipped."""
    added = add_starter(db, user)
    if added:
        log(db, user, "library", user.company_id, f"Loaded the starter task list ({added} tasks)")
    db.commit()
    return {"added": added}


# ---------- subcontractors ----------

def _load_sub(db: Session, user: User, sub_id: str) -> Subcontractor:
    s = db.scalar(select(Subcontractor).where(Subcontractor.id == sub_id, Subcontractor.company_id == user.company_id))
    if s is None:
        raise HTTPException(404, "Sub not found")
    return s


@router.post("/subs", status_code=201)
def add_sub(body: SubIn, user: User = Depends(estimators), db: Session = Depends(get_db)):
    name = " ".join(body.name.split())
    dupe = db.scalar(select(Subcontractor).where(Subcontractor.company_id == user.company_id, func.lower(Subcontractor.name) == name.lower()))
    if dupe:
        raise HTTPException(409, f"{dupe.name} is already on the sub list.")
    s = Subcontractor(company_id=user.company_id, created_by_id=user.id, **(body.model_dump() | {"name": name}))
    db.add(s)
    db.flush()
    log(db, user, "sub", s.id, "Added sub")
    db.commit()
    return sub_out(s)


@router.get("/subs/{sub_id}")
def get_sub(sub_id: str, user: User = Depends(estimators), db: Session = Depends(get_db)):
    """The sub, and the jobs and current estimates it's on with its price there."""
    s = _load_sub(db, user, sub_id)
    jobs = db.execute(select(Job.id, Job.name, Job.status, JobTask.name, JobTask.sub_price)
                      .join(JobTask, JobTask.job_id == Job.id)
                      .where(Job.company_id == user.company_id, JobTask.sub_id == s.id))
    used_jobs = [{"id": j, "name": n, "status": st.value, "task": tn, "price": p} for j, n, st, tn, p in jobs]
    used_ests = []
    rows = db.execute(select(Estimate, EstimateVersion)
                      .join(EstimateVersion, (EstimateVersion.estimate_id == Estimate.id) & (EstimateVersion.version == Estimate.current_version))
                      .where(Estimate.company_id == user.company_id, EstimateVersion.data.contains(s.id)))
    for e, v in rows:
        for t in json.loads(v.data).get("tasks", []):
            if t.get("sub_id") == s.id:
                used_ests.append({"id": e.id, "number": e.number, "name": e.name, "status": e.status.value, "task": t["name"],
                                  "price": t.get("sub_price"), "quote_link": t.get("sub_quote_link", "")})
    return sub_out(s) | {"jobs": used_jobs, "estimates": used_ests, "activity": history(db, user.company_id, "sub", s.id)}


@router.put("/subs/{sub_id}")
def edit_sub(sub_id: str, body: SubIn, user: User = Depends(estimators), db: Session = Depends(get_db)):
    s = _load_sub(db, user, sub_id)
    new = body.model_dump() | {"name": " ".join(body.name.split())}
    if new["name"].lower() != s.name.lower() and db.scalar(
            select(Subcontractor.id).where(Subcontractor.company_id == user.company_id, func.lower(Subcontractor.name) == new["name"].lower())):
        raise HTTPException(409, f"{new['name']} is already on the sub list.")
    what = changes({k: getattr(s, k) for k in SUB_LABELS}, new, SUB_LABELS)
    for k, v in new.items():
        setattr(s, k, v)
    if what:
        log(db, user, "sub", s.id, "Edited sub", what)
    db.commit()
    return sub_out(s)


@router.patch("/subs/{sub_id}/active")
def sub_active(sub_id: str, body: ActiveIn, user: User = Depends(gm_only), db: Session = Depends(get_db)):
    s = _load_sub(db, user, sub_id)
    if s.active != body.active:
        s.active = body.active
        log(db, user, "sub", s.id, "Turned sub back on" if body.active else "Turned sub off", body.reason)
        db.commit()
    return sub_out(s)
