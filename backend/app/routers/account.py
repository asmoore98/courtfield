"""Your own account (Settings tab): profile, how the app looks, password,
signed-in devices, and the suggestion box."""
import json
import os
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, undefer

from .. import auth, mailer
from ..activity import iso, log
from ..db import SessionLocal, get_db
from ..models import DeviceSession, Feedback, Photo, Role, User, utcnow
from ..schemas import MeOut
from .auth import me_out

router = APIRouter(prefix="/api/me", tags=["account"])
feedback_router = APIRouter(prefix="/api/feedback", tags=["feedback"])

START_TABS = ("", "field", "office", "leads", "estimates", "clients", "library", "crews", "materials", "timesheets", "team", "settings")


class Prefs(BaseModel):
    theme: Literal["system", "light", "dark"] = "system"
    text: Literal["normal", "large"] = "normal"
    start: str = Field(default="", max_length=20)  # which tab opens first ("" = the usual one)


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    prefs: Prefs | None = None


class PasswordIn(BaseModel):
    current: str = Field(min_length=1, max_length=200)
    new: str = Field(min_length=8, max_length=200)


def prefs_of(user: User) -> dict:
    try:
        return Prefs(**json.loads(user.prefs or "{}")).model_dump()
    except (ValueError, TypeError):
        return Prefs().model_dump()


@router.patch("", response_model=MeOut)
def update_me(body: ProfileIn, user: User = Depends(auth.current_user), db: Session = Depends(get_db)):
    if body.name is not None and " ".join(body.name.split()) != user.name:
        old, user.name = user.name, " ".join(body.name.split())
        log(db, user, "person", user.id, "Changed their name", f"{old} → {user.name}")
    if body.phone is not None:
        user.phone = body.phone.strip()
    if body.prefs is not None:
        if body.prefs.start not in START_TABS:
            raise HTTPException(422, "That isn't a tab in the app")
        user.prefs = json.dumps(body.prefs.model_dump())
    db.commit()
    return me_out(db, user)


@router.post("/password")
def change_password(body: PasswordIn, session: DeviceSession = Depends(auth.current_session), db: Session = Depends(get_db)):
    user = session.user
    if not auth.verify_password(body.current, user.password_hash):
        raise HTTPException(403, "Your current password isn't right.")
    if body.new.strip().lower() in {(user.email or "").lower(), user.name.lower()}:
        raise HTTPException(422, "Pick a password that isn't your name or email.")
    user.password_hash = auth.hash_password(body.new)
    out = auth.revoke_sessions(db, user.id, except_hash=session.token_hash)  # other devices sign in again
    log(db, user, "person", user.id, "Changed their password")
    db.commit()
    return {"ok": True, "signed_out": out}


@router.get("/devices")
def my_devices(session: DeviceSession = Depends(auth.current_session), db: Session = Depends(get_db)):
    now = utcnow()
    rows = db.scalars(select(DeviceSession).where(DeviceSession.user_id == session.user_id, DeviceSession.revoked_at.is_(None),
                                                  DeviceSession.expires_at > now).order_by(DeviceSession.last_used_at.desc()))
    return [{"id": s.id, "device": s.device or "Unknown device", "last_used": iso(s.last_used_at), "this_one": s.id == session.id}
            for s in rows]


@router.post("/devices/sign-out-others")
def sign_out_others(session: DeviceSession = Depends(auth.current_session), db: Session = Depends(get_db)):
    n = auth.revoke_sessions(db, session.user_id, except_hash=session.token_hash)
    db.commit()
    return {"signed_out": n}


# ---------- the suggestion box ----------

class FeedbackIn(BaseModel):
    kind: Literal["idea", "problem"] = "idea"
    text: str = Field(min_length=3, max_length=5000)
    page: str = Field(default="", max_length=100)
    device: str = Field(default="", max_length=200)


class FeedbackStatusIn(BaseModel):
    status: Literal["new", "seen", "done"]
    reply: str = Field(default="", max_length=2000)


def feedback_out(f: Feedback, shots: int = 0) -> dict:
    return {"id": f.id, "kind": f.kind, "text": f.text, "page": f.page, "by": f.user.name, "at": iso(f.created_at),
            "sent": f.sent_at is not None, "emailed": f.emailed_at is not None, "email_error": f.email_error,
            "status": f.status, "reply": f.reply, "screenshots": shots}


def load_feedback(db: Session, user: User, feedback_id: str) -> Feedback:
    f = db.get(Feedback, feedback_id)
    if f is None or f.company_id != user.company_id or (f.user_id != user.id and user.role != Role.gm):
        raise HTTPException(404, "Not found")
    return f


def _recipients() -> list[str]:
    return [a.strip() for a in os.environ.get("FEEDBACK_TO", "").split(",") if a.strip()]


def email_feedback(feedback_id: str, app_url: str) -> None:
    """Runs after the response: email the suggestion with its screenshots."""
    db = SessionLocal()
    try:
        f = db.get(Feedback, feedback_id)
        to = _recipients()
        if not to or not mailer.configured():
            f.email_error = "Email isn't set up on the server yet (SMTP and FEEDBACK_TO)."
            db.commit()
            return
        shots = list(db.scalars(select(Photo).where(Photo.kind == "feedback", Photo.subject_id == f.id, Photo.removed_at.is_(None))
                                .options(undefer(Photo.data))))
        word = "Problem" if f.kind == "problem" else "Idea"
        first = " ".join(f.text.split())[:60]
        text = (f"{word} from {f.user.name} ({f.user.role.value.replace('_', ' ')})\n"
                f"{'Where: ' + f.page + chr(10) if f.page else ''}"
                f"When: {f.created_at:%b %d, %Y %I:%M %p} UTC\n"
                f"Device: {f.device or 'unknown'}\n\n{f.text}\n\n"
                f"{len(shots)} screenshot{'s' if len(shots) != 1 else ''} attached.\n"
                f"See it in the app: {app_url} (Settings → Suggestions from the team)\n")
        attachments = [(p.name or f"screenshot-{i + 1}.jpg", p.content_type, p.data) for i, p in enumerate(shots)]
        try:
            mailer.send(to, f"Courtfield {word.lower()}: {first}", text, attachments, reply_to=f.user.email)
            f.emailed_at, f.email_error = utcnow(), ""
        except Exception as e:  # noqa: BLE001 — kept on the record, shown to the GM
            f.email_error = f"Couldn't email it: {e}"[:500]
        db.commit()
    finally:
        db.close()


@feedback_router.post("", status_code=201)
def new_feedback(body: FeedbackIn, user: User = Depends(auth.current_user), db: Session = Depends(get_db)):
    """Saved first, so screenshots can be added to it; then sent."""
    f = Feedback(company_id=user.company_id, user_id=user.id, kind=body.kind, text=body.text.strip(),
                 page=body.page.strip(), device=body.device.strip(), user=user)
    db.add(f)
    db.commit()
    return feedback_out(f)


@feedback_router.post("/{feedback_id}/send")
def send_feedback(feedback_id: str, request: Request, tasks: BackgroundTasks, user: User = Depends(auth.current_user),
                  db: Session = Depends(get_db)):
    f = load_feedback(db, user, feedback_id)
    if f.sent_at is None:
        f.sent_at = utcnow()
        db.commit()
        from .. import config
        tasks.add_task(email_feedback, f.id, config.PUBLIC_URL)
    return feedback_out(f)


@feedback_router.get("")
def list_feedback(user: User = Depends(auth.current_user), db: Session = Depends(get_db)):
    """The GM sees everyone's; everyone else sees what they sent."""
    q = select(Feedback).where(Feedback.company_id == user.company_id, Feedback.sent_at.is_not(None)).order_by(Feedback.created_at.desc())
    if user.role != Role.gm:
        q = q.where(Feedback.user_id == user.id)
    rows = list(db.scalars(q.limit(200)))
    counts: dict[str, int] = {}
    for p in db.scalars(select(Photo).where(Photo.kind == "feedback", Photo.subject_id.in_([f.id for f in rows]), Photo.removed_at.is_(None))):
        counts[p.subject_id] = counts.get(p.subject_id, 0) + 1
    return {"items": [feedback_out(f, counts.get(f.id, 0)) for f in rows], "email_ready": mailer.configured() and bool(_recipients())}


@feedback_router.patch("/{feedback_id}")
def set_feedback_status(feedback_id: str, body: FeedbackStatusIn, user: User = Depends(auth.require_roles(Role.gm)),
                        db: Session = Depends(get_db)):
    f = load_feedback(db, user, feedback_id)
    f.status, f.reply = body.status, body.reply.strip() or f.reply
    db.commit()
    return feedback_out(f)
