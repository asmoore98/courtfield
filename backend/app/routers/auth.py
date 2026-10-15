"""Sign in, sign out, and accept an invite link."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import auth
from ..db import get_db
from ..models import Company, DeviceSession, User, utcnow
from ..schemas import InviteInfo, LoginIn, MeOut, SessionOut, SetPasswordIn

router = APIRouter(prefix="/api/auth", tags=["auth"])

BAD_LOGIN = "That email and password don't match. Check them, or ask your manager for a new sign-in link."


def me_out(db: Session, user: User) -> MeOut:
    company = db.get(Company, user.company_id)
    return MeOut(
        id=user.id, name=user.name, role=user.role, company_id=company.id, company_name=company.name,
        sees_dollars=user.role in auth.SEES_DOLLARS, enters_time=user.role in auth.ENTERS_TIME,
        edits_jobs=user.role in auth.EDITS_JOBS,
    )


@router.post("/login", response_model=SessionOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    keys = (f"email:{email}", f"ip:{auth.client_ip(request)}")
    if auth.login_throttle.blocked(*keys):
        raise HTTPException(429, "Too many tries. Wait 15 minutes, or ask your manager for a new sign-in link.")
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if not auth.check_login(user, body.password):
        auth.login_throttle.fail(*keys)
        raise HTTPException(401, BAD_LOGIN)
    auth.login_throttle.clear(f"email:{email}")
    token = auth.start_session(db, user, body.device or request.headers.get("user-agent", ""))
    db.commit()
    return SessionOut(token=token, me=me_out(db, user))


@router.post("/logout", status_code=204)
def logout(session: DeviceSession = Depends(auth.current_session), db: Session = Depends(get_db)):
    session.revoked_at = utcnow()
    db.commit()


@router.get("/invite/{token}", response_model=InviteInfo)
def invite_info(token: str, db: Session = Depends(get_db)):
    inv = auth.find_invite(db, token)
    company = db.get(Company, inv.user.company_id)
    return InviteInfo(name=inv.user.name, email=inv.user.email, company_name=company.name,
                      resetting=inv.user.password_hash is not None)


@router.post("/invite/{token}", response_model=SessionOut)
def accept_invite(token: str, body: SetPasswordIn, request: Request, db: Session = Depends(get_db)):
    inv = auth.find_invite(db, token)
    user = inv.user
    if body.password.strip().lower() in {(user.email or "").lower(), user.name.lower()}:
        raise HTTPException(422, "Pick a password that isn't your name or email.")
    user.password_hash = auth.hash_password(body.password)
    inv.used_at = utcnow()
    auth.revoke_sessions(db, user.id)  # a reset signs out every other device
    session_token = auth.start_session(db, user, body.device or request.headers.get("user-agent", ""))
    db.commit()
    return SessionOut(token=session_token, me=me_out(db, user))
