# Plan: RAG System for Kerala Building Rules Compliance

## Context
This project aims to develop a RAG (Retrieval-Augmented Generation) system for Local Self-Government Department (LSGD) engineers in Kerala. The system will allow engineers to upload building plans provided by clients, compare them against the Kerala Building Rules (KBR), and identify potential violations.

## Scope
- Ingest and index Kerala Building Rules (PDFs/Text).
- Process uploaded building plans (likely PDF or image-based floor plans).
- Implement a RAG pipeline that retrieves relevant rules based on the plan details.
- Provide a summary of potential violations detected by the AI.

## Status legend
- **[DONE]** — implemented and merged into `feature/optimized-rag`.
- **[FUTURE]** — not yet built; deliberately out of scope for the current build.

---

## Phase 0 — Project hygiene [DONE]
- env-driven Settings with safe defaults so the app boots before all credentials exist.
- Repo housekeeping: pinned deps, `.env.example`, FastAPI app mounted under `app.main:app`.
- CI: ruff lint/format on Python 3.12 + offline smoke test on `/api/health`.
- Python 3.9 dev / 3.12 CI compatibility (no PEP 604 `X | None` in runtime positions).

## Phase 1 — Optimized RAG core [DONE]
- **Ingestion:** KBR + plan loaders (text / text-based PDF), **sentence-aware chunking**
  (paragraph/sentence boundaries, `CHUNK_SIZE`/`CHUNK_OVERLAP`), and per-chunk
  **`rule_id`** extraction.
- **Vector store:** FAISS **cosine similarity** (L2-normalized embeddings in an
  inner-product index; higher score = better), `MIN_SCORE` threshold, versioned
  on-disk format, **content-hash dedup** (idempotent ingest) + `rebuild`.
- **Latency/cost:** async compliance graph (`acheck`), query-embedding cache
  (`EMBEDDING_CACHE_*`), analyze-step memo (`ANALYSIS_CACHE_*`), embedding
  batching (`EMBEDDING_BATCH_SIZE`), and LLM timeouts/retries
  (`LLM_TIMEOUT`/`LLM_MAX_RETRIES`).
- **Observability:** per-node telemetry (ms / in-out chars) recorded and logged per check.

## Phase 2 — Plan parsing (OCR / layout) [FUTURE]
- Text-based PDF/txt parsing is done; **image-only floor plans are NOT yet supported**.
- Add OCR and/or layout analysis to read dimensions/setbacks from scanned plans.
- Expose a dedicated plan-image endpoint (e.g. `POST /api/check/plan-ocr`) behind a
  feature flag once OCR lands.

## Phase 3 — KBR acquisition [DONE]
- **Downloader:** `python -m scripts.fetch_kbr --url <URL>` fetches KBR PDFs/HTML/text
  into `KBR_DATA_DIR` (stdlib only, network only when run) with a `.provenance.json`
  sidecar per document, and an optional `--ingest` step.
- Sample/synthetic corpus available for offline development and tests.

## Phase 4 — Auth & persistence [DONE]
- `POST /auth/register`, `POST /auth/login` (+ `/auth/login/json`), `GET /auth/me`.
- **bcrypt** password hashing, **JWT** access tokens (`SECRET_KEY`, `AUTH_ALGORITHM`,
  `TIME_OUT`), SQLAlchemy user store (`DATABASE_URL`, default SQLite), idempotent
  `init_db_safe()` at startup, and admin-key gating (`ADMIN_KEY`).
- **Opt-in route protection** via `require_auth` + `AUTH_REQUIRED` (OFF by default so
  the credential-less smoke test keeps passing).

## Phase 5 — Tests [DONE]
- Fakes-backed pytest suite (deterministic offline embeddings + scripted LLM) covering
  chunking, vector-store semantics, graph routing/parsing, prompts, and API smoke.
- Note: a subset of the suite still encodes the *old* L2-distance / lenient-parse
  expectations and is being reconciled against the new cosine + strict-score semantics.

## Phase 6 — Bench & docs [DONE]
- **Perf harness:** `python scripts/bench_check.py --checks N [--json]` runs an
  offline, keyless benchmark and reports p50/p95 latency plus the
  embedding-cache + analysis-memo win versus an uncached baseline.
- Docs refreshed (README, DEVELOPMENT, `.env.example`, this roadmap) to match the
  current code.

---

## Future work
- **Layout-aware / image OCR** for scanned floor plans (Phase 2).
- **Scalable index** — IVF/HNSW FAISS index once the rule corpus outgrows the flat index.
- **Hybrid retrieval** — combine BM25/keyword search with vector cosine + re-ranking.
- **Saved reports & migrations** — persist per-user check reports; add Alembic for the
  auth/user schema.
- **Deployment hardening** — tighten CORS, require a strong `SECRET_KEY`, enable
  `AUTH_REQUIRED`, add rate limiting.

## Verification
- `python scripts/bench_check.py --checks 5` runs offline and prints a latency/cost summary.
- `pytest` runs offline against fakes (a few tests still assert the old L2-distance /
  lenient-parse behaviour and are being reconciled with the new semantics).
- Engineer review to ensure rule interpretation accuracy on real KBR documents.
