"""Offline demo for agent-4 auth. Uses a temp SQLite DATABASE_URL, then removes it.

Run:  python .agenthub_demo/agent4_demo.py
Exits non-zero on any failed assertion.
"""

from __future__ import annotations

import os
import sys
import tempfile

# Repo root on sys.path so `import app...` works when run as a script.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
os.chdir(_REPO_ROOT)

# --- Point the DB at a temp SQLite file BEFORE importing app modules ---
_tmpdir = tempfile.mkdtemp(prefix="agent4_demo_")
_db_path = os.path.join(_tmpdir, "demo.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
# Deterministic secret + empty creds mimic the CI smoke environment.
os.environ["SECRET_KEY"] = "demo-secret-key"
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.dbmodel import decode_access_token  # noqa: E402

failures = []


def check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name} {extra}")
    if not cond:
        failures.append(name)


def main() -> int:
    with TestClient(app) as client:
        # 1. /api/health works with NO credentials (CI smoke path).
        r = client.get("/api/health")
        check("health 200 no-auth", r.status_code == 200, f"(got {r.status_code})")

        # 2. root works with no credentials.
        r = client.get("/")
        check("root 200 no-auth", r.status_code == 200, f"(got {r.status_code})")

        # 3. register a user (open self-service, ADMIN_KEY unset).
        r = client.post(
            "/auth/register",
            json={"email": "demo@example.com", "password": "supersecret1"},
        )
        check("register 201", r.status_code == 201, f"(got {r.status_code}: {r.text})")
        body = r.json() if r.status_code == 201 else {}
        check("register hides password", "password" not in body)
        uid = body.get("user_id")

        # 4. duplicate registration is rejected.
        r = client.post(
            "/auth/register",
            json={"email": "demo@example.com", "password": "supersecret1"},
        )
        check("duplicate register 409", r.status_code == 409, f"(got {r.status_code})")

        # 5. password stored hashed, not plaintext (verify column via login flow).
        # 6. login (OAuth2 form) -> JWT.
        r = client.post(
            "/auth/login",
            data={"username": "demo@example.com", "password": "supersecret1"},
        )
        check("login 200", r.status_code == 200, f"(got {r.status_code}: {r.text})")
        token = r.json().get("access_token") if r.status_code == 200 else None
        check("login returns token", bool(token))

        # 7. wrong password rejected.
        r = client.post(
            "/auth/login",
            data={"username": "demo@example.com", "password": "wrongpass1"},
        )
        check("login wrong-pass 401", r.status_code == 401, f"(got {r.status_code})")

        # 8. decode the JWT -> user claims.
        claims = decode_access_token(token) if token else {}
        check(
            "jwt decode -> sub+email",
            claims.get("sub") == uid and claims.get("email") == "demo@example.com",
            f"(sub={claims.get('sub')})",
        )

        # 9. /auth/me with token -> 200 and correct user.
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        check(
            "me 200 with token",
            r.status_code == 200 and r.json().get("user_id") == uid,
            f"(got {r.status_code})",
        )

        # 10. /auth/me without token -> 401 (get_current_user always enforces).
        r = client.get("/auth/me")
        check("me 401 without token", r.status_code == 401, f"(got {r.status_code})")

    print("-" * 50)
    if failures:
        print(f"FAILED: {len(failures)} check(s): {failures}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    code = main()
    # cleanup the temp DB file/dir
    try:
        os.remove(_db_path)
        os.rmdir(_tmpdir)
        print(f"cleaned up temp db: {_db_path}")
    except OSError as e:
        print(f"cleanup warning: {e}")
    sys.exit(code)
