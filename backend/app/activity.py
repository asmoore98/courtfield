"""The paper trail. Every change to a client, lead, estimate or job made
through the sales screens adds a row here: who, when, what, and why."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Activity, User


def iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def log(db: Session, user: User | None, kind: str, subject_id: str, action: str, detail: str = "") -> None:
    db.add(Activity(company_id=user.company_id if user else None, kind=kind, subject_id=subject_id,
                    action=action[:200], detail=detail, by_id=user.id if user else None))


def log_system(db: Session, company_id: str, kind: str, subject_id: str, action: str, detail: str = "") -> None:
    db.add(Activity(company_id=company_id, kind=kind, subject_id=subject_id, action=action[:200], detail=detail, by_id=None))


def history(db: Session, company_id: str, kind: str, subject_id: str) -> list[dict]:
    rows = db.scalars(
        select(Activity)
        .where(Activity.company_id == company_id, Activity.kind == kind, Activity.subject_id == subject_id)
        .options(selectinload(Activity.by))
        .order_by(Activity.at.desc(), Activity.id)
    )
    return [{"at": iso(a.at), "by": a.by.name if a.by else "Courtfield (automatic)", "action": a.action, "detail": a.detail} for a in rows]


def changes(before: dict, after: dict, labels: dict[str, str]) -> str:
    """'Phone: 555-0100 → 555-0199; Email: (blank) → a@b.com' for the fields that changed."""
    out = []
    for k, label in labels.items():
        a, b = before.get(k), after.get(k)
        if (a or "") != (b or ""):
            out.append(f"{label}: {a or '(blank)'} → {b or '(blank)'}")
    return "; ".join(out)
