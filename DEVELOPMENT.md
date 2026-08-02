# ChattamAI — Developer Guide

This guide explains how the project is structured, how the pieces fit together,
and what you need to know to keep developing it. It is meant to be read alongside
`README.md` (user-facing setup) and `plan.md` (product roadmap).

---

## 1. What this project is

**ChattamAI** is a Retrieval-Augmented Generation (RAG) service for **Kerala
Building Rules (KBR)** compliance checking. It is aimed at LSGD engineers: they
upload a building plan, and the system compares the plan's regulated parameters
against the KBR and flags potential violations.

**Stack**
- **FastAPI** — HTTP API (`app/main.py`)
- **LangGraph** — orchestrates the multi-step compliance workflow (`app/rag/graph.py`)
- **FAISS** (CPU) — vector store for KBR chunks (`app/rag/vectorstore.py`)
- **OpenAI embeddings** (`text-embedding-3-small`) — for semantic retrieval
- **Anthropic Claude** — the analysis LLM, reached through a **local proxy**
  (`ANTHROPIC_BASE_URL=http://127.0.0.1:8082`), not direct Anthropic API
- **pypdf** — text extraction from PDFs
- **SQLAlchemy + passlib[bcrypt] + python-jose** — the auth/user store
  (`app/services/`), used by the `/auth/*` routes (see §7)

---

## 2. The end-to-end flow

A compliance check runs as a **LangGraph state machine** with these nodes:

```
plan_text
   │
   ▼
extract_facts  ── Claude pulls regulated parameters (plot area, setbacks, FSI, …)
   │
   ▼
retrieve       ── embeds the extracted facts, FAISS similarity search over KBR chunks
   │
   ├── no rules found ──► insufficient  ──► END (short-circuit, no guessing)
   │
   ▼
analyze        ── Claude compares facts vs. retrieved rules → JSON violations
   │
   ▼
summarize      ── Claude writes an engineer-friendly report ──► END
```

- The graph is built once at startup and stored on `app.state.rag` (see
  `app/main.py` lifespan + `app/rag/system.py`).
- **Short-circuit:** if retrieval returns nothing, the workflow goes to
  `insufficient` instead of fabricating violations. This is intentional.
- The LLM and vector store are injected into the graph via a `Context`
  dataclass, so they can be swapped/tested independently.

---

## 3. Project layout

```
ChattamAI/
├── app/
│   ├── main.py            FastAPI app + lifespan (eager RAGSystem init + init_db_safe)
│   │                      + CORS + root route; mounts the RAG and auth routers
│   ├── config.py          Settings (Pydantic) loaded from env, cached via lru_cache
│   ├── schemas.py         Request/response Pydantic models for the API
│   │
│   ├── rag/               ← the heart of the system
│   │   ├── system.py       RAGSystem: owns provider/store/llm/graph; ingest() + check()
│   │   │                   + acheck() and the AnalysisMemo
│   │   ├── graph.py        LangGraph workflow (sync + async builders, per-node telemetry)
│   │   ├── ingestion.py    Load KBR docs + plan files; sentence-aware chunk_text();
│   │   │                   extract_rule_id()
│   │   ├── embeddings.py   EmbeddingProvider ABC + OpenAIEmbeddingProvider + EmbeddingCache
│   │   ├── vectorstore.py  RuleVectorStore: FAISS IndexFlatIP (cosine) + JSON metadata
│   │   │                   + content-hash dedup/rebuild
│   │   ├── llm.py          ClaudeClient: thin wrapper over the Anthropic SDK (timeout/retries)
│   │   └── prompts.py      SYSTEM_* prompt templates + helpers
│   │
│   ├── routes/
│   │   ├── rag.py          /api/health, /api/ingest (+rebuild), /api/check, /api/check/upload
│   │   └── auth.py         /auth/register, /auth/login(/json), /auth/me + JWT dependencies
│   │                       (mounted; protection is opt-in via AUTH_REQUIRED — see §7)
│   │
│   └── services/          Auth/user DB layer (used by the /auth/* routes; see §7)
│       ├── database.py     SQLAlchemy engine/session/Base (reads DATABASE_URL)
│       ├── database_init.py  idempotent create_all via init_db_safe()
│       └── dbmodel.py      User model + bcrypt hashing + JWT helpers
│
├── scripts/
│   ├── fetch_kbr.py       Download KBR documents into KBR_DATA_DIR (network only when run)
│   └── bench_check.py     Offline perf harness (fakes-backed, no API keys)
│
├── data/
│   ├── kbr/               Drop KBR PDFs/txt here (ingestion reads this dir)
│   └── index/             Generated FAISS index (rules.faiss) + rules_meta.json
│
├── .env.example           All env vars with sane defaults
├── requirements.txt       Pinned dependencies
├── README.md              User-facing setup + usage
└── plan.md                Product roadmap
```

---

## 4. Configuration (`app/config.py` + `.env.example`)

All settings come from env vars, with defaults so the app can import even before
every credential exists. The cached `get_settings()` is the single source of truth.

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | — | **Required** for embeddings. No key ⇒ `embeddings_ready=False`. |
| `OPENAI_BASE_URL` | — | Optional proxy for embeddings |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `EMBEDDING_DIM` | `1536` | Must match the model (index is built to this dim) |
| `ANTHROPIC_BASE_URL` | `http://127.0.0.1:8082` | Local Claude proxy |
| `ANTHROPIC_AUTH_TOKEN` | `freecc` | Proxy auth token |
| `LLM_MODEL` | `claude-3-5-sonnet-20241022` | Model the proxy serves |
| `LLM_MAX_TOKENS` | `2048` | Max completion tokens |
| `KBR_DATA_DIR` | `./data/kbr` | Folder of KBR PDFs/txt to ingest |
| `INDEX_DIR` | `./data/index` | Where the FAISS index is written |
| `CHUNK_SIZE` | `1000` | Chunk window (chars) |
| `CHUNK_OVERLAP` | `150` | Overlap between chunks |
| `TOP_K` | `6` | Rules retrieved per check |
| `MIN_SCORE` | `0.0` | Min cosine-similarity to keep a hit (higher=better; 0 = off) |
| `EMBEDDING_CACHE_ENABLED` | `1` | Toggle the query-embedding cache |
| `EMBEDDING_CACHE_TTL` | `300` | Query-embedding cache TTL (seconds) |
| `EMBEDDING_CACHE_MAXSIZE` | `1024` | Max cached query embeddings |
| `EMBEDDING_BATCH_SIZE` | `128` | Max texts per `embeddings.create` call |
| `ANALYSIS_CACHE_TTL` | `300` | Analyze-step memo TTL (seconds) |
| `ANALYSIS_CACHE_MAXSIZE` | `512` | Max memoized analyses |
| `LLM_TIMEOUT` | `60` | Per-request timeout (s) for the Claude/OpenAI clients |
| `LLM_MAX_RETRIES` | `2` | Retry budget for LLM/embedding requests |
| `SECRET_KEY` | insecure dev default | JWT signing key — override in production |
| `AUTH_ALGORITHM` | `HS256` | JWT signing algorithm |
| `AUTH_REQUIRED` | unset (off) | Truthy ⇒ require a bearer token on `/api/ingest` & `/api/check` |
| `ADMIN_KEY` | unset | If set, `/auth/register` requires an `X-Admin-Key` header |
| `TIME_OUT` | `3600` | Access-token TTL / session timeout (seconds) |
| `DATABASE_URL` | `sqlite:///./chattamai.db` | Auth/user store connection string |

> **Note on APIs:** the LLM does **not** call Anthropic directly. It goes through
> the local proxy at `127.0.0.1:8082`. If that proxy is down, `check` will fail at
> request time with a clear error (the system still boots).

---

## 5. The two operations

Both live on `RAGSystem` (`app/rag/system.py`) and are exposed as routes in
`app/routes/rag.py`.

### `ingest` — `POST /api/ingest`
- Reads every `.pdf`/`.txt`/`.md`/`.text` in `KBR_DATA_DIR` (via
  `load_kbr_documents`).
- Chunks each doc (sentence-aware `chunk_text`), detects a `rule_id` per chunk,
  then embeds (in batches) + adds to FAISS.
- **Idempotent:** chunks already in the index (matched by content hash) are
  skipped, so re-running ingest does not duplicate vectors. Pass
  `{"rebuild": true}` (or `rag.ingest(rebuild=True)`) to drop the index and
  rebuild from the source documents.
- **Persists** the index to `data/index/rules.faiss` + `rules_meta.json`, so it
  survives restarts — you only need to ingest once (or when rules change).
- Returns `{documents, chunks, index_size, skipped}`.

### `check` — `POST /api/check` (JSON body) or `POST /api/check/upload` (file)
- `plan_text` (free text of the plan) → runs the LangGraph workflow.
- `top_k` is optional per-request override of `TOP_K`.
- Internally `RAGSystem.check()` drives the **async** graph (`acheck`); it is
  safe to call with or without an active event loop. Two caches cut cost on
  repeats: the query-embedding cache and the analyze-step memo.
- Returns `{extracted_facts, summary, violations, retrieved_rules}`; each
  `retrieved_rules` entry has `source`, `rule_id`, `excerpt`, and a cosine
  `score` (higher = better). Per-node timing/counts are logged per check and
  recorded in the graph state's `telemetry`.
- Uploads are streamed to a temp file then parsed with `load_plan_text`.

### `health` — `GET /api/health`
- Returns readiness flags: `status` is `"ok"` only if **both** embeddings and LLM
  are ready, otherwise `"degraded"`.

**Typical dev loop:**
```bash
cp .env.example .env          # set OPENAI_API_KEY; proxy already configured
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# (optional) fetch KBR source docs into KBR_DATA_DIR, or drop files there manually
python -m scripts.fetch_kbr --url https://example.org/kbr.pdf

uvicorn app.main:app --reload # NOTE: module is app.main, not main

curl -X POST http://127.0.0.1:8000/api/ingest
curl -X POST http://127.0.0.1:8000/api/check -H "Content-Type: application/json" \
  -d '{"plan_text": "3-floor building, 12m tall, 1m front setback"}'
```

**Offline check (no API keys):** the perf harness and the test suite both run
against fakes, so you can validate changes without OpenAI/Anthropic credentials:
```bash
python scripts/bench_check.py --checks 5   # latency + cache-win summary
pytest                                     # unit tests (fakes-backed)
```
Note: a handful of tests still assert the *old* `IndexFlatL2` distance /
lenient-parse behaviour and are being reconciled with the new cosine +
strict-score semantics — they are not a signal that your change broke something
if you only touched retrieval/parsing.

---

## 6. How retrieval & embedding work

- `EmbeddingProvider` is an **abstract interface** (`app/rag/embeddings.py`). Only
  the OpenAI impl exists today; swapping to a local/HF model means adding another
  subclass — nothing else changes.
- `RuleVectorStore` keeps chunk texts + metadata in a parallel JSON file because
  FAISS only stores vectors. Embeddings are **L2-normalized** and stored in a
  flat **inner-product** index (`IndexFlatIP`), so the returned score is a true
  **cosine similarity in [-1, 1] where higher = more similar** (this replaced the
  original `IndexFlatL2` raw-distance semantics). Hits below `MIN_SCORE` are
  dropped. The on-disk format is versioned (`_INDEX_VERSION`) so an index saved
  under the old L2 semantics is ignored and rebuilt rather than mis-read.
- Retrieval query = the **extracted facts** (not the raw plan text), which usually
  retrieves more relevant rules. The query embedding is computed once, cached
  (`EmbeddingCache`), and reused.

---

## 7. ⚠️ Known gaps / things NOT to trust yet

These are important before you build further. (The auth/DB layer is now **wired
up and used** — see items 1–2 — but the deployment-hardening gaps remain.)

1. **Auth is real but opt-in and OFF by default.** `app/main.py` mounts the auth
   router and calls `init_db_safe()` in the lifespan, so the SQLite tables exist
   at startup. `POST /auth/register`, `POST /auth/login` (+ `/auth/login/json`)
   and `GET /auth/me` work; passwords are **bcrypt-hashed** and login returns a
   **JWT** (`python-jose`). Protection of the RAG routes is gated by
   `AUTH_REQUIRED` (falsy by default): only when truthy does the `require_auth`
   dependency enforce a bearer token on `POST /api/ingest` and `POST /api/check`,
   so the credential-less smoke test on `/api/health` keeps passing. The default
   `SECRET_KEY` is an insecure dev value — override it in production.
2. **`app/services/*` DB layer backs the auth routes now.** It is used for user
   accounts (SQLAlchemy + `DATABASE_URL`, default SQLite) and the broken relative
   import and `create_engine(None)` crash were fixed during integration. The RAG
   pipeline itself still does **not** use the DB — checks and ingestion are
   stateless apart from the FAISS index on disk. Saved reports / per-user history
   are future work.
3. **CORS is wide open** (`allow_origins=["*"]`) in `app/main.py`. Tighten this
   before any public deployment.
4. **Image-only floor plans are unsupported** (by design, future work in
   `plan.md`). `ingestion.py` only handles text-based PDFs/txt; there is **no**
   OCR endpoint yet. OCR/layout analysis is future work.
5. **`data/kbr/` is empty by default.** Add KBR documents (or fetch them with
   `python -m scripts.fetch_kbr --url <URL>`) before ingesting; nothing useful is
   indexed until you do.
6. **Re-running `/api/ingest` is idempotent but additive.** Re-ingesting the same
   documents is a no-op (content-hash dedup), and new documents are appended. To
   start fresh, either post `{"rebuild": true}` or delete `data/index/`.

### Optimizations shipped in this build

- **Cosine retrieval.** Embeddings are L2-normalized and stored in a FAISS
  `IndexFlatIP`, so the score is a true cosine similarity (higher = better, in
  [-1, 1]). `MIN_SCORE` (default `0.0`, off) drops hits below the threshold.
- **Sentence-aware chunking.** `chunk_text` splits on paragraph/sentence
  boundaries and packs whole sentences into `CHUNK_SIZE` windows with
  `CHUNK_OVERLAP` context — never cutting mid-sentence.
- **Async graph + two caches.** `RAGSystem.acheck` runs the workflow on an async
  graph, overlapping the (independent) query-embedding warm-up with fact
  extraction. An `EmbeddingCache` memos query embeddings
  (`EMBEDDING_CACHE_*`), and an `AnalysisMemo` skips the analysis LLM on an
  identical re-check (`ANALYSIS_CACHE_*`).
- **Embedding batching + LLM plumbing.** Ingestion embeds in batches
  (`EMBEDDING_BATCH_SIZE`); the Claude/OpenAI clients honor `LLM_TIMEOUT` and
  `LLM_MAX_RETRIES`.
- **Per-node telemetry + perf harness.** Every check records per-node
  ms/in/out-char/token-ish counts (`telemetry` in the graph state, logged per
  check). `scripts/bench_check.py` runs an offline, keyless benchmark that
  reports p50/p95 latency and the cache win — see §9.

### Python version caveat (read before editing models)

Local dev runs **Python 3.9** while CI lints/tests on **3.12**. Keep
`from __future__ import annotations` at the top of every module, and **never**
use PEP 604 unions (`X | None`) in *runtime* positions — Pydantic model field
annotations, dataclass fields with runtime defaults, `isinstance` checks, etc.
Use `typing.Optional[X]` there. (Bare `X | None` inside a *string/lazy*
annotation that is never evaluated at runtime is fine thanks to the future
import; the `app/rag` helpers use this.) Ruff targets `py39`, so `ruff check` +
`ruff format` must stay clean on 3.9.

---

## 8. Coding conventions

- **`from __future__ import annotations`** at the top of every module (lets you use
  `X | None` and `list[...]` syntax on Python 3.9+).
- **Linting:** `ruff`, `black`, `isort` (enforced in CI on Python 3.12). Run
  `ruff check .`, `black .`, `isort .` before pushing.
- **Dependency injection:** the API gets `RAGSystem` via a FastAPI `Depends`
  (`get_rag`) reading `app.state.rag`.
- **Lazy imports:** heavy clients (openai, anthropic, faiss) are imported inside
  functions/constructors so the app imports cheaply and missing credentials fail
  gracefully at request time, not at boot.
- **Config** is accessed through `get_settings()` everywhere — never read env vars
  directly in business logic.

---

## 9. Where to extend next (hints from `plan.md`)

- **Plan parsing:** add OCR / layout analysis for image-based floor plans (still
  future work; there is no `/api/check/plan-ocr` endpoint yet).
- **Retrieval quality:** try hybrid search (keyword + vector, e.g. BM25 + cosine),
  re-ranking, metadata filtering (rule section, occupancy type), or an IVF/HNSW
  index once the corpus outgrows the flat index.
- **Structured analysis:** `analyze` already requests strict JSON; you could make
  the schema a Pydantic model and validate it instead of best-effort parsing
  (`graph.py:_parse_violations`).
- **Auth & persistence:** auth is wired up (see §7); the natural next step is
  saving per-user check reports to the DB and adding Alembic migrations.
- **Performance:** measure changes with the offline harness —
  `python scripts/bench_check.py --checks 20 [--json]` — which reports p50/p95
  latency and the embedding-cache + analysis-memo win versus an uncached
  baseline, all without API keys.
- **Frontend:** only the API exists today; a UI for engineers would be a new layer.
```
