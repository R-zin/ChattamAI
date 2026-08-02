"""Demo of the opt-in require_auth guard.

Shows that require_auth is OFF by default (no token needed) and enforces a valid
bearer token only when AUTH_REQUIRED=true. This mirrors how the coordinator would
attach it to /api/ingest or /api/check without editing routes/rag.py.

Run:  python .agenthub_demo/agent4_require_auth_demo.py
"""

from __future__ import annotations

import os
import sys
import tempfile

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
os.chdir(_REPO_ROOT)

_tmpdir = tempfile.mkdtemp(prefix="agent4_guard_")
_db_path = os.path.join(_tmpdir, "guard.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SECRET_KEY"] = "demo-secret-key"

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.routes.auth import require_auth  # noqa: E402
from app.services.database_init import init_db  # noqa: E402
from app.services.dbmodel import User, create_access_token, hash_password, new_id  # noqa: E402
from app.services.database import SessionLocal  # noqa: E402


def _seed_user() -> str:
    init_db()
    db = SessionLocal()
    try:
        u = User(
            user_id=new_id(),
            email="guard@example.com",
            password=hash_password("passw0rd!"),
        )
        db.add(u)
        db.commit()
        return create_access_token(user_id=u.user_id, email=u.email)
    finally:
        db.close()


# A minimal app with ONE protected route, demonstrating the dependency directly.
mini = FastAPI()


@mini.post("/protected", dependencies=[Depends(require_auth)])
def protected():
    return {"ok": True}


def run() -> int:
    failures = []

    def check(name, cond, extra=""):
        print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
        if not cond:
            failures.append(name)

    token = _seed_user()

    with TestClient(mini) as client:
        # AUTH_REQUIRED unset -> guard is a no-op -> route reachable with no token.
        os.environ.pop("AUTH_REQUIRED", None)
        r = client.post("/protected")
        check(
            "AUTH_REQUIRED unset: 200 no-token",
            r.status_code == 200,
            f"(got {r.status_code})",
        )

        os.environ["AUTH_REQUIRED"] = "false"
        r = client.post("/protected")
        check(
            "AUTH_REQUIRED=false: 200 no-token",
            r.status_code == 200,
            f"(got {r.status_code})",
        )

        # AUTH_REQUIRED=true -> 401 without a token, 200 with a valid token.
        os.environ["AUTH_REQUIRED"] = "true"
        r = client.post("/protected")
        check(
            "AUTH_REQUIRED=true: 401 no-token",
            r.status_code == 401,
            f"(got {r.status_code})",
        )

        r = client.post("/protected", headers={"Authorization": "Bearer not-a-token"})
        check(
            "AUTH_REQUIRED=true: 401 bad-token",
            r.status_code == 401,
            f"(got {r.status_code})",
        )

        r = client.post("/protected", headers={"Authorization": f"Bearer {token}"})
        check(
            "AUTH_REQUIRED=true: 200 valid-token",
            r.status_code == 200,
            f"(got {r.status_code})",
        )

    print("-" * 50)
    if failures:
        print(f"FAILED: {failures}")
        return 1
    print("ALL GUARD CHECKS PASSED")
    return 0


if __name__ == "__main__":
    code = run()
    try:
        os.remove(_db_path)
        os.rmdir(_tmpdir)
        print(f"cleaned up temp db: {_db_path}")
    except OSError as e:
        print(f"cleanup warning: {e}")
    sys.exit(code)
