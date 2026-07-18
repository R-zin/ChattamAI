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
- **SQLAlchemy** — present in `app/services/` but **currently unused** by the RAG app (see §7)

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
│   ├── main.py            FastAPI app + lifespan (eager RAGSystem init) + CORS + root route
│   ├── config.py          Settings (Pydantic) loaded from env, cached via lru_cache
│   ├── schemas.py         Request/response Pydantic models for the API
│   │
│   ├── rag/               ← the heart of the system
│   │   ├── system.py       RAGSystem: owns provider/store/llm/graph; ingest() + check()
│   │   ├── graph.py        LangGraph workflow (nodes, routing, builder)
│   │   ├── ingestion.py    Load KBR docs + plan files; chunk_text() (overlapping windows)
│   │   ├── embeddings.py   EmbeddingProvider ABC + OpenAIEmbeddingProvider
│   │   ├── vectorstore.py  RuleVectorStore: FAISS IndexFlatL2 + JSON metadata on disk
│   │   ├── llm.py          ClaudeClient: thin wrapper over the Anthropic SDK
│   │   └── prompts.py      SYSTEM_* prompt templates + helpers
│   │
│   ├── routes/
│   │   ├── rag.py          /api/health, /api/ingest, /api/check, /api/check/upload
│   │   └── auth.py         ⚠️ NOT wired into the app — dead code (see §7)
│   │
│   └── services/          ⚠️ DB layer — unused by the RAG app (see §7)
│       ├── database.py     SQLAlchemy engine/session/Base (reads DATABASE_URL)
│       ├── database_init.py  create_all (has a broken relative import)
│       └── dbmodel.py      User / UserSession models
│
├── data/
│   ├── kbr/               Drop KBR PDFs/txt here (ingestion reads this dir)
│   └── index/             Generated FAISS index (rules.faiss) + rules_meta.json
│
├── .env.example           All env vars with sane defaults
├── requirements.txt       Pinned dependencies
├── README.md              User-facing setup + usage
└── plan.md                Product roadmap (Phase 1–3)
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
- Chunks each doc (`chunk_text`, overlapping windows) and embeds + adds to FAISS.
- **Persists** the index to `data/index/rules.faiss` + `rules_meta.json`, so it
  survives restarts — you only need to ingest once (or when rules change).
- Returns `{documents, chunks, index_size}`.

### `check` — `POST /api/check` (JSON body) or `POST /api/check/upload` (file)
- `plan_text` (free text of the plan) → runs the LangGraph workflow.
- `top_k` is optional per-request override of `TOP_K`.
- Returns `{extracted_facts, summary, violations, retrieved_rules}`.
- Uploads are streamed to a temp file then parsed with `load_plan_text`.

### `health` — `GET /api/health`
- Returns readiness flags: `status` is `"ok"` only if **both** embeddings and LLM
  are ready, otherwise `"degraded"`.

**Typical dev loop:**
```bash
cp .env.example .env          # set OPENAI_API_KEY; proxy already configured
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload # NOTE: module is app.main, not main

curl -X POST http://127.0.0.1:8000/api/ingest
curl -X POST http://127.0.0.1:8000/api/check -H "Content-Type: application/json" \
  -d '{"plan_text": "3-floor building, 12m tall, 1m front setback"}'
```

---

## 6. How retrieval & embedding work

- `EmbeddingProvider` is an **abstract interface** (`app/rag/embeddings.py`). Only
  the OpenAI impl exists today; swapping to a local/HF model means adding another
  subclass — nothing else changes.
- `RuleVectorStore` uses a **flat L2 FAISS index** (`IndexFlatL2`). It keeps the
  chunk texts + metadata in a parallel JSON file because FAISS only stores vectors.
  On retrieval it returns `(text, meta, score)` tuples; smaller L2 distance = more
  similar.
- Retrieval query = the **extracted facts** (not the raw plan text), which usually
  retrieves more relevant rules.

---

## 7. ⚠️ Known gaps / things NOT to trust yet

These are important before you build further:

1. **`app/routes/auth.py` is dead code.** `app/main.py` only mounts `rag_routes`.
   The auth router is never included, so its `/admin` key check does nothing. If
   you want auth, you must `app.include_router(auth.auth_router)` and finish it.
2. **`app/services/*` DB layer is unused.** No route uses SQLAlchemy; the RAG app
   has no database. `database_init.py` has a **broken import**
   (`from database import ...` should be `from app.services.database import ...`),
   and `database.py` will crash if `DATABASE_URL` is unset (`create_engine(None)`).
   `dbmodel.py` also reads `TIME_OUT` at import time. Treat this as scaffolding.
3. **CORS is wide open** (`allow_origins=["*"]`) in `app/main.py`. Tighten this
   before any public deployment.
4. **CI path bug.** `.github/workflows/github-actions.yml` runs
   `uvicorn main:app`, but the module is `app.main:app`. That job will fail as
   written. The Lint workflow (ruff/black/isort) is fine.
5. **No tests.** There is no test suite yet — only the CI smoke check on `/health`.
6. **Image-only floor plans are unsupported** (by design, Phase 2 in `plan.md`).
   `ingestion.py` only handles text-based PDFs/txt. OCR/layout analysis is future work.
7. **`data/kbr/` is empty.** You must add the actual KBR documents before
   ingesting; nothing is indexed by default.
8. **Index is rebuilt by append, not recreated.** Re-running `/api/ingest` adds to
   the existing index. To start fresh, delete `data/index/`.

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

- **Plan parsing (Phase 2):** add OCR/layout analysis for image-based floor plans.
- **Retrieval quality:** try hybrid search (keyword + vector), re-ranking, or
  metadata filtering (rule section, occupancy type).
- **Structured analysis:** `analyze` already requests strict JSON; you could make
  the schema a Pydantic model and validate it instead of best-effort parsing
  (`graph.py:_parse_violations`).
- **Auth & persistence:** wire up `routes/auth.py` + `services/` if you want users
  and saved reports.
- **Frontend:** only the API exists today; a UI for engineers would be a new layer.
```
