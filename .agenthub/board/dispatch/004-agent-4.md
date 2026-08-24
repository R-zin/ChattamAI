---
author: coordinator
channel: dispatch
agent: agent-4
task: "Phase 4 — auth & DB finish + mount (non-invasive)"
files: ["app/routes/auth.py", "app/services/dbmodel.py", "app/services/database.py", "app/services/database_init.py", "app/main.py", "app/schemas.py"]
---
# Agent-4 — Auth & DB finish + mount (non-invasive)

You are agent-4 in AgentHub ensemble session `20260802-121531`. Repo: ChattamAI RAG
(FastAPI + LangGraph + FAISS). Read `README.md`, `DEVELOPMENT.md` (§7), and the existing
`app/routes/auth.py` + `app/services/*` first.

## CRITICAL shared constraints
- **Python 3.9 compatible** (dev 3.9.6), CI 3.12. Keep `from __future__ import annotations`.
  In Pydantic models use `typing.Optional[X]`, never PEP 604 `X | None`.
- **Non-invasive to the RAG path / CI smoke**: `GET /api/health` and `/` MUST keep working with
  NO credentials (the CI smoke test boots with empty keys and expects HTTP 200). Auth
  protection must be **opt-in** and OFF by default.
- Verifiable offline: use SQLite for the DB; do not require external services. Ruff-clean,
  keep docstrings, commit often.

## YOUR files (do not edit others)
- `app/routes/auth.py`        — real login/register/JWT
- `app/services/dbmodel.py`   — bcrypt hashing + session model
- `app/services/database.py`  — engine/session (keep working)
- `app/services/database_init.py` — init_db on startup
- `app/main.py`               — mount auth router, call init_db() in lifespan
- `app/schemas.py`            — ADD auth request/response models ONLY (do not change existing RAG models)

Do NOT touch `app/rag/*`, `app/config.py`, or `app/routes/rag.py`. If you need settings
(SECRET_KEY, AUTH_REQUIRED flag, token TTL), read via `os.getenv` with safe defaults and note
them for the coordinator to add to `app/config.py`.

## New dependencies (add to `requirements.txt` under an "# Auth" comment)
`passlib[bcrypt]==1.7.4`, `python-jose[cryptography]==3.5.0`  (both support 3.9).
NOTE: passlib 1.7.4 + bcrypt>=4.1 has a known `__about__` warning — it still works; you may
prefix the requirements line comment noting this, or pin `bcrypt<4.1`. Verify by importing.

## What to implement
1. **bcrypt** password hashing in `dbmodel.py` (`hash_password` using passlib bcrypt; add
   `verify_password`). Replace the unsalted SHA-512. Keep a one-line migration note.
2. **init_db** wired into `main.py` lifespan so the SQLite tables exist at startup
   (idempotent `create_all`). Guard so failure to init DB never breaks the RAG boot.
3. **Mount** `auth_router` in `main.py`.
4. **`POST /auth/register`**: create a user (hashed password). Gate it sensibly — either
   admin-key header OR allow-first-user-when-empty (document your choice).
5. **`POST /auth/login`**: verify credentials and return a JWT (`python-jose`), expiry from
   `TIME_OUT`/session TTL setting. Include user id + email in claims.
6. **`get_current_user` dependency** (OAuth2 bearer) that decodes the JWT and loads the user.
7. **Opt-in protection**: a tiny dependency `require_auth` that, only when `AUTH_REQUIRED=true`,
   enforces `get_current_user` on mutating/paid endpoints. Wire it in a way that defaults OFF so
   existing behavior + CI smoke are unchanged. You may expose the dependency for the coordinator
   to attach to `/api/ingest`/`/api/check` later — DO NOT edit `routes/rag.py` yourself.

## Done when
- `ruff check`/`ruff format --check` clean; `python -c "import app.main, app.routes.auth"` OK.
- New deps import cleanly on 3.9.
- Offline demo (inline script or a `TestClient`): register, login -> JWT, decode -> user; and a
  protection check shows `/api/health` 200 with no auth while a protected route 401s without a
  token when AUTH_REQUIRED=true (you can demonstrate the dependency directly). SQLite file
  created under a temp DATABASE_URL, then removed. Show output in result post.

Write your summary to `.agenthub/board/results/agent-4-result.md`. Then exit.
