---
agent: agent-4
task: "Phase 4 — auth & DB finish + mount (non-invasive)"
branch: hub/20260802-121531/agent-4/attempt-1
base: 58af064 (feature/optimized-rag integration line)
status: complete
---

# Agent-4 result — Auth & DB finish + mount

## Approach
Finished the auth scaffolding and mounted it, keeping the RAG path and the
credential-less CI smoke test (`GET /api/health`, `/`) untouched and green.

- **bcrypt** replaced the unsalted SHA-512 in `dbmodel.py` via passlib's
  `CryptContext(schemes=["bcrypt"])`. Added `hash_password` + `verify_password`
  (the latter returns False instead of raising on a malformed/foreign hash, so a
  legacy SHA-512 value can never "verify"). One-line migration note is on
  `hash_password`. **Note: previously-stored SHA-512 hashes will not verify —
  those users must re-register.** (DB was unused, so likely nothing to migrate.)
- **JWT** via python-jose. `create_access_token(user_id, email)` signs claims
  `{sub, email, exp}` with `SECRET_KEY`/`AUTH_ALGORITHM`; `exp` = now + `TIME_OUT`
  seconds. `decode_access_token` validates signature + expiry.
- **Models**: `User.user_id` / `UserSession.session_id` now default to uuid4 hex;
  timestamps use `datetime.utcnow` (naive UTC, consistent with JWT `exp`). Fixed
  the `relationship("userSession")` -> `relationship("UserSession")` class-name
  reference (SQLAlchemy class lookups are case-sensitive; the old string would
  fail mapper configuration once the relationship is actually used).
- **init_db** wired into lifespan via a new `init_db_safe()` in
  `database_init.py`. It is idempotent (`create_all`) and **never raises** — a
  missing/unreachable DB is logged as a warning and returns False, so RAG boot
  is unaffected. Verified: bogus `DATABASE_URL` → `init_db_safe()` returns False,
  app still boots.
- **Mounted** `auth_router` in `main.py`; RAG boot block (eager `RAGSystem()`)
  is unchanged. The default SQLite file (`chattamai.db`) is created relative to
  the process CWD and is gitignored (`*.db`), so no repo artifacts are produced.

## Endpoints (all under `/auth`)
- `POST /auth/register` (201) — creates a user, bcrypt-hashes the password,
  never returns the hash. **Gating choice (documented):** if env `ADMIN_KEY` is
  set, the request must send a matching `X-Admin-Key` header; if `ADMIN_KEY` is
  unset, registration is open/self-service (so the first user can be created).
  Duplicate email → 409.
- `POST /auth/login` (OAuth2 password form, works with Swagger Authorize;
  `tokenUrl=/auth/login`). Verifies credentials, returns `TokenResponse`
  `{access_token, token_type:"bearer", expires_in}`. Bad creds → 401.
- `POST /auth/login/json` — JSON-body convenience login (same behavior).
- `GET /auth/me` — always requires a valid bearer token; returns the user.
- `get_current_user` dependency (OAuth2 bearer) — decodes the JWT and loads the
  user; 401 on missing/invalid/expired token or unknown user.
- `require_auth` dependency — **opt-in, OFF by default.** When `AUTH_REQUIRED`
  is falsy it is a no-op returning `None` (existing behavior + CI smoke
  unchanged). When truthy (`1/true/yes/on`) it enforces `get_current_user`.
  Exported for the coordinator to attach to `/api/ingest` / `/api/check` later:
  `@router.post("/ingest", dependencies=[Depends(require_auth)])`. I did NOT edit
  `routes/rag.py`.

## Files changed (all within ownership)
- `app/services/dbmodel.py` — bcrypt hash/verify, JWT create/decode, uuid PKs,
  UTC timestamps, `SECRET_KEY`/`AUTH_ALGORITHM`/`DEFAULT_TIME_OUT` env reads.
- `app/routes/auth.py` — full register/login/JWT/me + `get_current_user` +
  `require_auth`.
- `app/services/database_init.py` — added `init_db_safe()` (never raises);
  `init_db()` behavior unchanged.
- `app/main.py` — mount `auth_router`; call `init_db_safe()` in lifespan.
- `app/schemas.py` — ADDED `RegisterRequest`, `LoginRequest`, `TokenResponse`,
  `UserResponse`. Existing RAG models untouched.
- `requirements.txt` — new `# Auth` section.
- `.agenthub_demo/agent4_demo.py`, `.agenthub_demo/agent4_require_auth_demo.py`
  — offline TestClient verification scripts (kept for the coordinator).

`app/services/database.py` needed no change (already worked).
**Protected files untouched** (verified `git diff 58af064 HEAD --name-only` is
empty for): `app/rag/*`, `app/config.py`, `app/routes/rag.py`.

## Dependencies added (requirements.txt, "# Auth" section)
```
python-jose[cryptography]==3.5.0
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
```
`bcrypt==4.0.1` is pinned deliberately: passlib 1.7.4 reads `bcrypt.__about__`
(removed in bcrypt>=4.1) **and** bcrypt>=5 hard-errors on passlib's internal
>72-byte wrap-bug probe. `passlib[bcrypt]` alone pulls bcrypt 5.0.0, which makes
`CryptContext(...).hash()` raise `ValueError: password cannot be longer than 72
bytes`. Pinning `bcrypt<4.1` resolves it; verified clean (no warning) with
`python -W error::UserWarning`. Both deps import fine on local Python 3.9.6.

## Offline verification (temp DATABASE_URL SQLite, removed after)
Ran two TestClient scripts (temp SQLite file under a `mkdtemp`, removed
afterward). All assertions PASS:

`agent4_demo.py`:
- health 200 no-auth; root 200 no-auth
- register 201, password hash not exposed; duplicate register 409
- login 200 → JWT; wrong password 401
- decode JWT → `sub`+`email` match the created user
- `GET /auth/me` 200 with token; 401 without token

`agent4_require_auth_demo.py` (mini app with one `Depends(require_auth)` route):
- `AUTH_REQUIRED` unset → 200 no-token
- `AUTH_REQUIRED=false` → 200 no-token
- `AUTH_REQUIRED=true` → 401 no-token; 401 bad-token; 200 valid-token

Also ran a real `uvicorn app.main:app` boot from a temp CWD with empty creds
(exactly like CI): `/` → 200, `/api/health` → 200 (status `degraded`), and the
mounted auth router served register→login→`me` end-to-end. `chattamai.db` was
created in the temp CWD, not the repo, and `init_db_safe` ran at startup without
breaking boot.

Repo-wide gates clean:
- `ruff check .` → All checks passed
- `ruff format --check .` → 21 files already formatted
- `python -c "import app.main, app.routes.auth"` → OK (only pre-existing
  urllib3/langgraph warnings from importing the RAG system; unrelated to auth).

## Env / Settings notes for the coordinator
These are read via `os.getenv` with safe defaults in `app/services/dbmodel.py`
and `app/routes/auth.py` (I did not edit `app/config.py`). Promote into
`app.config.Settings` when convenient:

| Var | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | `chattamai-insecure-dev-secret-change-me` | JWT signing key. **MUST override in prod.** |
| `AUTH_ALGORITHM` | `HS256` | JWT algorithm |
| `TIME_OUT` | `3600` | access-token TTL (seconds); reused for `expires_in` |
| `AUTH_REQUIRED` | unset/off | truthy → `require_auth` enforces a token on routes it's attached to |
| `ADMIN_KEY` | unset | if set, `POST /auth/register` requires matching `X-Admin-Key` header |
| `DATABASE_URL` | `sqlite:///./chattamai.db` | existing; auth tables created here at startup |

Suggested `.env.example` additions (not done — file not in my ownership):
`SECRET_KEY=`, `AUTH_REQUIRED=false`, `ADMIN_KEY=`.

## Integration risks / notes
1. **Opt-in protection is a no-op until wired.** `require_auth` is exported but
   NOT attached to any route (per spec, I left `routes/rag.py` alone). Auth
   currently protects only `/auth/me`. Coordinator must add
   `dependencies=[Depends(require_auth)]` (or `Depends(get_current_user)`) to
   `/api/ingest`, `/api/check`, `/api/check/upload` as desired.
2. **Insecure default `SECRET_KEY`.** Must be overridden via env in any real
   deployment; the default is only for offline/dev so the module imports and the
   demo runs.
3. **bcrypt 72-byte limit.** bcrypt limits passwords to 72 bytes; the register
   schema enforces `min_length=8` but no max. Consider a max-length or a
   pre-hash (e.g. SHA-256 then bcrypt) if very long passwords are expected. Not
   a blocker for typical use.
4. **Legacy SHA-512 hashes won't verify.** If any user rows exist from the old
   scheme, they must re-register/reset. (DB was previously unused.)
5. **Open registration when `ADMIN_KEY` unset.** This is the documented
   first-user convenience. Set `ADMIN_KEY` to lock registration behind an admin
   header in shared environments.
6. **JWT is stateless**; `UserSession` table exists but is not yet consulted for
   revocation/expiry on each request (logout/invalidate is future work).
7. **CORS is wide open** (`allow_origins=["*"]`) — pre-existing, unrelated to
   auth, but tighten before public deployment.

Branch with final commits: **`hub/20260802-121531/agent-4/attempt-1`** (base
`58af064`). Not pushed, no PR, per instructions.
