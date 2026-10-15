"""Server-side setup commands, run on the host (e.g. from its shell):

    python -m app.admin create-company --company "Armor Courts" --name "Andrew Moore" --email you@example.com
        Creates a company and its first general manager, and prints a one-time
        link to set the GM's password. Everyone else is added from the Team screen.

    python -m app.admin signin-link --email you@example.com
        Prints a fresh password link, e.g. if the only GM is locked out.

    python -m app.admin wait-for-db
        Waits up to 3 minutes for the database to accept connections. Run at
        start, since a new database can still be starting when the app boots.

    python -m app.admin bootstrap
        Run at every start (see start.sh). If the database has no company yet
        and INITIAL_COMPANY, INITIAL_GM_NAME and INITIAL_GM_EMAIL are set, it
        creates them and prints the GM's password link to the server log.
        Otherwise it does nothing. Lets a first deploy finish without a shell.
"""
import os
import argparse
import sys

from sqlalchemy import func, select

from . import auth
from .db import SessionLocal
from .models import Company, Role, User


def create_company(company: str, name: str, email: str) -> None:
    email = email.strip().lower()
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(func.lower(User.email) == email)):
            sys.exit(f"{email} already has a sign-in. Use signin-link instead.")
        co = Company(name=company.strip())
        db.add(co)
        db.flush()
        gm = User(company_id=co.id, name=name.strip(), role=Role.gm, email=email)
        db.add(gm)
        db.flush()
        url = auth.make_invite(db, gm, None)
        db.commit()
    print(f"Created {company} with {name} as general manager.")
    print(f"Open this link to set the password (works once, expires in 7 days):\n\n  {url}\n")


def signin_link(email: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
        if user is None or not user.active:
            sys.exit(f"No active sign-in for {email}.")
        url = auth.make_invite(db, user, None)
        db.commit()
    print(f"Password link for {user.name}:\n\n  {url}\n")


def wait_for_db(timeout_s: int = 180) -> None:
    import time

    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    from .db import engine

    deadline = time.monotonic() + timeout_s
    attempt = 0
    while True:
        attempt += 1
        try:
            with engine.connect() as conn:
                conn.execute(text("select 1"))
            if attempt > 1:
                print(f"Database is up (after {attempt} tries).")
            return
        except OperationalError as e:
            if time.monotonic() > deadline:
                sys.exit(f"Database still not reachable after {timeout_s}s: {e.orig}")
            if attempt == 1:
                print("Waiting for the database to accept connections...")
            time.sleep(3)


def bootstrap() -> None:
    company, name, email = (os.environ.get(k, "").strip() for k in ("INITIAL_COMPANY", "INITIAL_GM_NAME", "INITIAL_GM_EMAIL"))
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Company)):
            return
    if not (company and name and email):
        print("No company yet. Set INITIAL_COMPANY, INITIAL_GM_NAME and INITIAL_GM_EMAIL and redeploy, "
              "or run: python -m app.admin create-company ...")
        return
    print("=" * 70)
    create_company(company, name, email)
    print("=" * 70)


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m app.admin")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-company", help="create a company and its first GM")
    c.add_argument("--company", required=True)
    c.add_argument("--name", required=True, help="the GM's full name")
    c.add_argument("--email", required=True, help="the GM's sign-in email")
    s = sub.add_parser("signin-link", help="new password link for an existing person")
    s.add_argument("--email", required=True)
    sub.add_parser("bootstrap", help="first-start setup from INITIAL_* environment variables")
    sub.add_parser("wait-for-db", help="wait until the database accepts connections")
    a = p.parse_args()
    if a.cmd == "wait-for-db":
        wait_for_db()
    elif a.cmd == "bootstrap":
        bootstrap()
    elif a.cmd == "create-company":
        create_company(a.company, a.name, a.email)
    else:
        signin_link(a.email)


if __name__ == "__main__":
    main()
