"""Authentication and role checks.

DEVELOPMENT ONLY: users authenticate with a static bearer token stored on the
user row. Swap this for real login (hashed passwords or an identity provider,
short-lived sessions) before the app touches real job data.
"""
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Role, User

_bearer = HTTPBearer(auto_error=False)


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    user = db.scalar(select(User).where(User.api_token == creds.credentials, User.active))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    def _check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role can't do that")
        return user

    return _check


# Who sees labor dollars (rates, cost, margin). Crew leads see hours only.
SEES_DOLLARS = {Role.owner, Role.gm, Role.estimator}
# Who can enter field time.
ENTERS_TIME = {Role.gm, Role.crew_lead}
# Who can create and edit jobs and their estimated hours.
EDITS_JOBS = {Role.gm, Role.estimator}
