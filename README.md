# ChattamAI — Kerala Building Rules Compliance RAG

A Retrieval-Augmented Generation system that helps LSGD engineers compare an
uploaded building plan against the **Kerala Building Rules (KBR)** and surface
potential violations. Built with **FastAPI** (API), **LangGraph** (compliance
workflow orchestration), **FAISS** (vector store), **OpenAI embeddings**, and
**Google Gemini** (primary analysis LLM via `google-genai`, with Anthropic Claude support).

## How it works

```
building plan (text/PDF)
        │
        ▼
┌──────────────── LangGraph workflow ────────────────┐
│ 1. extract_facts  → pull regulated parameters        │
│ 2. retrieve       → cosine search KBR chunks (FAISS) │
│ 3. analyze        → Gemini compares facts vs rules   │
│ 4. summarize      → engineer-friendly report          │
└──────────────────────────────────────────────────────┘
```

If no rules are retrieved, the workflow short-circuits to an `insufficient`
branch rather than guessing.

## What's in this build

- **Optimized retrieval** — embeddings are L2-normalized and stored in a FAISS
  inner-product index, so retrieval ranks by **cosine similarity** (higher =
  better). A `MIN_SCORE` threshold drops weak matches, every chunk carries a
  `rule_id`, and ingest is **idempotent** (content-hash dedup) with an optional
  `rebuild` flag to start fresh.
- **Async pipeline + in-process caches** — `RAGSystem.acheck` runs the same
  graph asynchronously, and two TTL caches cut latency/cost: a query-embedding
  cache (`EmbeddingCache`) and an analyze-step memo that skips the analysis LLM
  on an identical re-check. Retriever facts are embedded once and reused.
- **Plumbing** — Claude/OpenAI clients are built with configurable timeouts and
  retries (`LLM_TIMEOUT`, `LLM_MAX_RETRIES`); large ingests are split into
  embedding batches (`EMBEDDING_BATCH_SIZE`).
- **Auth (opt-in, off by default)** — JWT auth is wired up: `POST
  /auth/register`, `POST /auth/login` (+ `/auth/login/json`), and `GET
  /auth/me`. Passwords are bcrypt-hashed; users live in a SQLAlchemy DB. When
  `AUTH_REQUIRED` is truthy, `POST /api/ingest` and `POST /api/check` require a
  bearer token. The credential-less smoke test on `/api/health` always passes.
- **KBR downloader** — `python -m scripts.fetch_kbr --url <URL>` fetches rule
  documents into `KBR_DATA_DIR` (offline-safe; only uses the network when run).
- **Perf harness** — `python scripts/bench_check.py --checks N` runs an
  offline, keyless benchmark and reports p50/p95 latency plus the cache win.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set OPENAI_API_KEY and GEMINI_API_KEY
```

Required env vars (see `.env.example`):
- `OPENAI_API_KEY` — embeddings (`text-embedding-3-small`)
- `GEMINI_API_KEY` — Gemini LLM analysis (`gemini-2.5-flash`, from Google AI Studio)
- *(Alternative)* `NVIDIA_API_KEY` / `NVIDIA_BASE_URL` — if using `LLM_PROVIDER=nim` (`nvidia/nemotron-3.5-super-vl-120b-a12b`)
- *(Alternative)* `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_BASE_URL` — if using `LLM_PROVIDER=anthropic`
- `KBR_DATA_DIR` — folder of KBR PDFs/text (default `./data/kbr`)

Tunables with sane defaults (see `.env.example` for the full list): `MIN_SCORE`,
`TOP_K`, `CHUNK_SIZE`/`CHUNK_OVERLAP`, the cache `*_TTL`/`*_MAXSIZE` knobs,
`EMBEDDING_BATCH_SIZE`, `LLM_TIMEOUT`/`LLM_MAX_RETRIES`, and the auth settings
(`SECRET_KEY`, `AUTH_REQUIRED`, `ADMIN_KEY`, `TIME_OUT`).

## Run

```bash
uvicorn app.main:app --reload
# docs at http://127.0.0.1:8000/docs
```

## Usage

1. **(Optional) Fetch the rules** — download KBR documents into `KBR_DATA_DIR`:
   ```bash
   python -m scripts.fetch_kbr --url https://example.org/kbr.pdf
   # or: KBR_SOURCE_URLS="https://.../a.pdf,https://.../b.txt" python -m scripts.fetch_kbr
   ```
2. **Ingest the rules** (chunks, embeds, builds the FAISS index; idempotent —
   add `{"rebuild": true}` to reindex from scratch):
   ```bash
   curl -X POST http://127.0.0.1:8000/api/ingest
   ```
3. **Check a plan** (text):
   ```bash
   curl -X POST http://127.0.0.1:8000/api/check \
     -H "Content-Type: application/json" \
     -d '{"plan_text": "3-floor building, 12m tall, 1m front setback"}'
   ```
   Or upload a file:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/check/upload -F "file=@plan.pdf"
   ```
4. **Health**: `GET /api/health`

### Auth (optional)

Registration/login are available out of the box; protecting the RAG routes is
opt-in. With `AUTH_REQUIRED=true`:
```bash
# register (needs X-Admin-Key header only if ADMIN_KEY is set)
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "eng@example.com", "password": "secret"}'
# login -> bearer token
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/login/json \
  -H "Content-Type: application/json" \
  -d '{"email": "eng@example.com", "password": "secret"}' | jq -r .access_token)
# call a protected route
curl -X POST http://127.0.0.1:8000/api/check \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"plan_text": "3-floor building, 12m tall, 1m front setback"}'
```

## Benchmark (offline, no keys)

```bash
python scripts/bench_check.py --checks 20          # human summary
python scripts/bench_check.py --checks 20 --json   # machine-readable
```
Runs N compliance checks against a fakes-backed `RAGSystem` (no OpenAI/Anthropic
keys, no network) and prints p50/p95 latency plus the latency/cost win from the
embedding cache + analysis memo versus an uncached baseline.

## Layout

```
app/
  main.py            FastAPI app + lifespan init (mounts RAG + auth routers; init_db)
  config.py          env-based settings
  schemas.py         request/response models
  routes/
    rag.py           /api/ingest (+rebuild), /api/check, /api/check/upload,
                     /api/check/plan-ocr (opt-in OCR), /api/health
    auth.py          /auth/register, /auth/login(/json), /auth/me + JWT dependencies
  rag/
    embeddings.py    EmbeddingProvider + OpenAI impl + EmbeddingCache
    vectorstore.py   FAISS store (cosine via IndexFlatIP) + dedup/rebuild
    ingestion.py     KBR + plan loaders, sentence-aware chunking, rule_id extraction
    llm.py           Anthropic Claude client
    prompts.py       prompt templates
    graph.py         LangGraph workflow (sync + async) with per-node telemetry
    system.py        RAGSystem (wires it all together) + AnalysisMemo
  services/          SQLAlchemy auth/user store (used by the auth routes)
scripts/
  fetch_kbr.py       download KBR documents into KBR_DATA_DIR
  bench_check.py     offline perf harness
data/kbr/            drop Kerala Building Rules documents here
data/index/          generated FAISS index (rules.faiss) + rules_meta.json
```

For a **line-referenced map of every function and where it lives** (full-system
flowchart, call graph, and extension/test seams), see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Production Deployment

- **Microsoft Azure (Container Apps)**: Deploy the full-stack container with Azure Files persistent volume for FAISS & SQLite. See [docs/DEPLOYMENT_AZURE.md](docs/DEPLOYMENT_AZURE.md).
- **Fly.io + Vercel + Cloudflare (Option A)**: Edge-routed deployment with persistent volume on Fly.io and React frontend on Vercel CDN. See [docs/DEPLOYMENT_OPTION_A.md](docs/DEPLOYMENT_OPTION_A.md).

## Production & Security Hardening

- **CORS Hardening**: Configurable via `CORS_ORIGINS` (defaults to local dev endpoints; set to your specific production origins e.g. `https://chattamai.vercel.app`).
- **Security Headers & CSP**: Built-in HTTP middleware injects `Content-Security-Policy`, `Strict-Transport-Security`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and `Referrer-Policy: strict-origin-when-cross-origin`.
- **Authentication**: Supports JWT token auth, TOTP 2-Factor Authentication, and Google OAuth 2.0 / OpenID Connect federation.
- **Upload Validation**: Enforces 25MB file size caps and `%PDF-` magic header bytes validation.
- **Rate Limiting**: Protects sensitive endpoints (`/auth/*`, `/api/check`, `/api/v2/*`) with configurable per-IP rate limits (`RATE_LIMIT_PER_MINUTE`).

## Limitations

- Analysis depends on what rules were ingested and retrieved; always have an
  engineer review the output before acting on it.
- Ensure production deployments set a cryptographically secure `SECRET_KEY` and define appropriate `CORS_ORIGINS`.
