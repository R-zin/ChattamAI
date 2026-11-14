# ChattamAI

Kerala Building Rules (KBR) compliance checker. Users upload a building plan (PDF/image); the
app extracts facts, retrieves KBR rules (FAISS + BM25), evaluates them (symbolic V2 engine +
LLM, optional second-LLM verifier) and produces reports. One container serves the FastAPI
API and the built React app on port 8000. Primary deployment: Azure Container Apps.

## Commands

```bash
# Backend (Python 3.9 locally, CI tests 3.10 and 3.12; keep code 3.9-compatible)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q -m "not live_nvidia"          # offline; fakes + respx, no network
ruff check . && ruff format --check .   # CI pins ruff 0.14.5
uvicorn app.main:app --reload           # needs provider keys in .env

# Frontend
cd frontend && npm ci && npm test -- --run && npm run build
npm run dev                             # proxies /api and /auth to :8000
```

## Layout

- `app/config.py` single source of settings (`get_settings()`); env placeholders (`none`, empty) = unset.
- `app/main.py` app, middleware (security headers, rate limit), SPA fallback; lifespan builds `RAGSystem`, `init_db_safe`, background ingest.
- `app/bootstrap.py` first-boot KBR seeding + auto-ingest. `app/routes/` `rag.py` (v1 + health), `rag_v2.py`, `auth.py`.
- `app/rag/` graph, vector store, embeddings, LLM clients, OCR. `app/rules/` symbolic engine. `app/pdf_intel/` plan extraction. `app/services/` DB, TOTP, OAuth, reports.
- `frontend/src/data.js` the whole API layer plus mock data. `infra/main.bicep` + `.github/workflows/` deployment.
- `docs/ARCHITECTURE.md` has a function-level map.

## Behaviour that is easy to get wrong

- **Providers are explicit.** Set `LLM_PROVIDER` and `EMBEDDING_PROVIDER`; changing the embedding provider changes the vector dimension and the index is rebuilt.
- **Health has three endpoints.** `/api/health` is always 200 with `status` + `issues`; `/api/health/ready` is 503 unless ok; `/api/health/live` is process-only. Deploy gates use `ready`.
- **Registration is admin-gated when `ADMIN_KEY` is set** (always, on Azure) unless `ALLOW_SELF_REGISTRATION` is true. The UI reads `GET /auth/config` to hide the sign-up link. Emails are normalised to lower-case; lookups are case-insensitive.
- **UI uses design tokens only.** Colours are `--c-*` variables in `frontend/src/index.css` mapped to Tailwind (`bg-surface`, `text-ink-2`, `border-line`, `text-danger`...). Never write hex values or `text-white`/`bg-black` in components (a test fails). Light is the default theme; dark is `[data-theme='dark']`, toggled by `src/theme.js`. Status = colour + label + glyph. See `docs/redesign/README.md`; `frontend/scripts/ui-audit` is the browser audit.
- **Mock data is opt-in** (`VITE_USE_MOCKS=true`). Empty `VITE_API_URL` means same origin. Never reintroduce silent mock fallbacks on API errors.
- **Unknown `/api/*` and `/auth/*` must 404 as JSON**, not fall through to the SPA.
- **Rate limiting trusts `X-Forwarded-For` only via `TRUSTED_PROXY_COUNT`** (image default 1; 0 ignores the header). State is per replica, so Azure `maxReplicas` stays 1 (SQLite + FAISS are per replica too).
- **Data volume masks baked-in files.** The KBR corpus ships at `/app/seed/kbr` and is copied into `KBR_DATA_DIR` at boot.
- Tests disable startup ingest via an autouse fixture (`AUTO_INGEST=0`); tests that exercise it set it explicitly.
- Migrations: `entrypoint.sh` runs `alembic upgrade head`; the `ALTER TABLE` fallbacks in `database_init.py` only run when Alembic failed.

## Verification before declaring done

Run the backend suite, ruff check + format check, and for frontend changes `npm test -- --run` and `npm run build`.
Docker/Azure paths (image build, Bicep, the deploy workflow) are not exercised by the test suite.
