import os
import tempfile

import pytest

_db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db_file}")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.auth import login_throttle  # noqa: E402
from app.seed import ACCOUNTS, DEV_PASSWORD, dev_email, seed  # noqa: E402

TOKENS: dict[str, str] = {}


@pytest.fixture()
def client():
    seed()
    login_throttle._fails.clear()
    c = TestClient(app)
    TOKENS.clear()
    for key in [*ACCOUNTS, "dev-other-gm"]:
        r = c.post("/api/auth/login", json={"email": dev_email(key), "password": DEV_PASSWORD})
        assert r.status_code == 200, r.text
        TOKENS[key] = r.json()["token"]
    return c


def auth(key: str) -> dict:
    """Headers for a sample account (by its key, e.g. "dev-gm"), or a raw token."""
    return {"Authorization": f"Bearer {TOKENS.get(key, key)}"}
