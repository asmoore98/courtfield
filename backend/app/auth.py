"""Sign-in, sessions and role checks.

People sign in with email and password. Each signed-in phone or computer gets
its own session token (kept on the device; only its hash is stored here), good
for SESSION_DAYS and revocable by the GM, e.g. when a phone is lost or someone
leaves. New people and password resets go through one-time invite links.
"""
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .db import get_db
from .models import DeviceSession, Invite, Role, User, utcnow

_bearer = HTTPBearer(auto_error=False)

# Who sees labor dollars (rates, cost, margin). Crew leads see hours only.
SEES_DOLLARS = {Role.owner, Role.gm, Role.estimator}
# Who can enter field time.
ENTERS_TIME = {Role.gm, Role.crew_lead}
# Who can create and edit jobs and their estimated hours.
EDITS_JOBS = {Role.gm, Role.estimator}
# Who manages people, rates and sign-ins.
MANAGES_TEAM = {Role.gm}
# Roles that sign in. Plain crew members are clocked in by their crew lead.
SIGNS_IN = {Role.owner, Role.gm, Role.estimator, Role.crew_lead, Role.warehouse}

MIN_PASSWORD = 8


# ---------- secrets ----------

def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    n, r, p = 2**14, 8, 1
    digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, n, r, p, salt, digest = stored.split("$")
        check = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(check.hex(), digest)


# A real hash to compare against when the email doesn't exist, so a wrong email
# and a wrong password take the same time.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def check_login(user: User | None, password: str) -> bool:
    if user is None or not user.active or user.role not in SIGNS_IN:
        verify_password(password, _DUMMY_HASH)
        return False
    return verify_password(password, user.password_hash)


# ---------- login throttling ----------

class Throttle:
    """At most `limit` failed attempts per key in `window` seconds. In-memory,
    which is enough for a single app server."""

    def __init__(self, limit: int = 8, window: int = 15 * 60):
        self.limit, self.window = limit, window
        self._fails: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _trim(self, q: deque, now: float) -> None:
        while q and now - q[0] > self.window:
            q.popleft()

    def blocked(self, *keys: str) -> bool:
        now = time.monotonic()
        with self._lock:
            for k in keys:
                q = self._fails[k]
                self._trim(q, now)
                if len(q) >= self.limit:
                    return True
        return False

    def fail(self, *keys: str) -> None:
        now = time.monotonic()
        with self._lock:
            for k in keys:
                self._fails[k].append(now)

    def clear(self, *keys: str) -> None:
        with self._lock:
            for k in keys:
                self._fails.pop(k, None)


login_throttle = Throttle()


# ---------- sessions ----------

def start_session(db: Session, user: User, device: str = "") -> str:
    token = new_token()
    now = utcnow()
    db.add(DeviceSession(token_hash=token_hash(token), user_id=user.id, created_at=now, last_used_at=now,
                         expires_at=now + timedelta(days=config.SESSION_DAYS), device=device[:200]))
    return token


def revoke_sessions(db: Session, user_id: str, except_hash: str | None = None) -> int:
    now = utcnow()
    q = select(DeviceSession).where(DeviceSession.user_id == user_id, DeviceSession.revoked_at.is_(None))
    n = 0
    for s in db.scalars(q):
        if s.token_hash != except_hash:
            s.revoked_at = now
            n += 1
    return n


def make_invite(db: Session, user: User, created_by: User | None) -> str:
    """Create a one-time password link for this person; earlier unused links stop working."""
    now = utcnow()
    for old in db.scalars(select(Invite).where(Invite.user_id == user.id, Invite.used_at.is_(None))):
        old.expires_at = min(old.expires_at, now)
    token = new_token()
    db.add(Invite(token_hash=token_hash(token), user_id=user.id, created_by_id=created_by.id if created_by else None,
                  created_at=now, expires_at=now + timedelta(days=config.INVITE_DAYS)))
    return f"{config.PUBLIC_URL}/invite/{token}"


def find_invite(db: Session, token: str) -> Invite:
    inv = db.scalar(select(Invite).where(Invite.token_hash == token_hash(token)))
    if inv is None or inv.used_at is not None or inv.expires_at < utcnow() or not inv.user.active:
        raise HTTPException(404, "This link has expired or was already used. Ask your manager for a new one.")
    return inv


def _session_for(creds: HTTPAuthorizationCredentials | None, db: Session) -> DeviceSession:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue")
    s = db.scalar(select(DeviceSession).where(DeviceSession.token_hash == token_hash(creds.credentials)))
    now = utcnow()
    if s is None or s.revoked_at is not None or s.expires_at < now or not s.user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your sign-in has ended. Sign in again.")
    if now - s.last_used_at > timedelta(hours=1):
        s.last_used_at = now
        db.commit()
    return s


def current_session(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)) -> DeviceSession:
    return _session_for(creds, db)


def current_user(session: DeviceSession = Depends(current_session)) -> User:
    return session.user


def require_roles(*roles: Role) -> Callable[[User], User]:
    def _check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role can't do that")
        return user

    return _check


def client_ip(request: Request) -> str:
    # Behind a hosting proxy the real address is the first X-Forwarded-For entry.
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown"))
