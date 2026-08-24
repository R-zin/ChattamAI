---
author: coordinator
channel: dispatch
agent: agent-8
task: "Phase 6 — perf harness (bench_check.py) + docs/env/roadmap close-out"
files: ["scripts/bench_check.py", "scripts/__init__.py (create if absent)", "README.md", "DEVELOPMENT.md", ".env.example", "plan.md"]
---

# Agent-8 — Bench + docs (Phase 6)

You are agent-8 in AgentHub ensemble session `20260802-121531`. Repo: ChattamAI RAG
(FastAPI + LangGraph + FAISS + OpenAI embeddings + Claude via local proxy). Read
`README.md`, `DEVELOPMENT.md`, `plan.md` first, then the integrated
`feature/optimized-rag` tree.

## CRITICAL shared constraints
- **Python 3.9 compatible** (dev 3.9.6), CI 3.12. `from __future__ import annotations`
  in modules; NO PEP 604 `X | None` in runtime positions. Ruff-clean (88 cols).
- **Offline-verifiable**: the perf harness must run WITHOUT OpenAI/Anthropic keys
  (inject fakes through the existing seams). Docs must match the CURRENT code.
- Do NOT touch `app/rag/*`, `app/routes/*`, `app/services/*`, `app/config.py`,
  `app/schemas.py`, `app/main.py`, `requirements*.txt`, or `tests/` (other agents own
  those). Your app/ contact is read-only.

## Get the tree
Branch off the LATEST `feature/optimized-rag` (tip `9e899a8` or later — it includes
the coordinator's Settings polish). Create `hub/20260802-121531/agent-8/attempt-1`,
commit there only. (The AgentsDK worktree dir is auto-named; ensure commits land on
the named `hub/...` branch.)

## 1. `scripts/bench_check.py` — perf harness (offline, keyless)
A CLI that runs N compliance checks against a **fakes-backed** RAGSystem and reports
latency + cost deltas vs. an uncached baseline. Requirements:
- Accept `--checks N` (default 20), `--repeat/--identical` to exercise the analysis
  memo hit path, `--top-k`, `--no-embedding-cache` and `--no-analysis-cache` to force
  the uncached baseline for comparison, and `--json` to emit machine-readable output.
- Build a `RAGSystem(provider=FakeEmbeddingProvider(), llm=FakeLLM(), index_dir=<tmp>)`,
  ingest a small synthetic KBR corpus (a few rules like setback/FSI/parking so
  retrieve has something to find), then time `rag.check(...)` per call.
- Measure per-node timings from the result `telemetry` (extract/retrieve/analyze/
  summarize ms) and counts (facts/retrieved/violations). Report p50/p95 of total
  `check` latency, and the cache impact: identical-repeat latency (analysis memo +
  embedding cache hits) vs. the forced-uncached run, plus embedding-API call counts
  (wrap the fake provider to count invocations).
- Spin up **local fakes inline** (don't import from `tests/`): a deterministic
  `FakeEmbeddingProvider` (hash of text → stable unit vector; the real store now does
  cosine over L2-normalized vectors, so identical text must score ≈1.0) and a
  `FakeLLM` with a `complete(system, user)` returning canned extract/analyze/
  summarize payloads (include a valid `{"violations":[...]} `analyze` JSON).
- Print one human summary line + an optional JSON blob. Make the wins explicit:
  e.g. `repeat: 3.1ms vs first: 480ms (99% faster, memo+cache hit)`.
- `python scripts/bench_check.py --checks 5` must run start-to-finish offline. Use
  argparse stdlib only (no new deps).

## 2. Docs refresh (README.md + DEVELOPMENT.md §7)
- **README.md**: add the new capabilities shipped in this build — optimized retrieval
  (cosine similarity, higher=better, `MIN_SCORE` threshold, rule_id population,
  idempotent ingest + `rebuild`), async `acheck` + in-process caches (embedding +
  analysis memo) for latency/token savings, plumbing timeouts/retries, the KBR
  downloader (`python -m scripts.fetch_kbr`), JWT **auth** (`/auth/register`,
  `/auth/login`, optional `AUTH_REQUIRED`), and the new **OCR** endpoint
  `POST /api/check/plan-ocr` (feature-flagged). Update the Quickstart to show:
  configure env → optionally fetch KBR → `POST /api/ingest` (mention `rebuild`) →
  `POST /api/check`. Keep it concise and accurate to the code.
- **DEVELOPMENT.md §7**: the SQLAlchemy/auth layer is now USED (auth router mounted,
  `init_db_safe` in lifespan, bcrypt hashing, JWT) — correct the stale "currently
  unused" claim. Add a short "Optimizations" section documenting cosine retrieval +
  `MIN_SCORE`, sentence-aware chunking, the async graph + EmbeddingCache + AnalysisMemo,
  embedding batching (`EMBEDDING_BATCH_SIZE`), LLM timeout/retries, and the perf
  harness. Add the **Python 3.9-dev / 3.12-CI** caveat (no PEP 604 in models/runtime).
- Do NOT invent env vars or endpoints — cross-check everything against the code.

## 3. `.env.example`
Append the full set of NEW tunables with one-line comments, grouped sensibly:
`MIN_SCORE`, `EMBEDDING_CACHE_TTL`, `EMBEDDING_CACHE_MAXSIZE`, `EMBEDDING_BATCH_SIZE`,
`EMBEDDING_CACHE_ENABLED`, `ANALYSIS_CACHE_TTL`, `ANALYSIS_CACHE_MAXSIZE`,
`LLM_TIMEOUT`, `LLM_MAX_RETRIES`, `OCR_ENABLED`, `SECRET_KEY`, `AUTH_ALGORITHM`,
`AUTH_REQUIRED`, `ADMIN_KEY`, `TIME_OUT`. (KBR source: `scripts/fetch_kbr.py` already
exists — reference it in a comment.) Keep existing entries intact.

## 4. `plan.md`
Update the roadmap to reflect what's DONE (Phase 0 hygiene, Phase 1 optimized RAG
core, Phase 2 KBR downloader+sample, auth/DB finish+mount, OCR, tests, bench). Mark
completed items clearly; keep any genuinely-future work (e.g. layout-aware OCR,
IVF/HNSW index for large corpus, hybrid BM25, Alembic) as "Future".

## Done when
- `python scripts/bench_check.py --checks 5` runs offline end-to-end and prints a
  sensible latency/cost summary (and `--json` validates).
- README/DEVELOPMENT/.env.example/plan.md accurately describe the CURRENT tree; no
  stale "unused auth" claims, no invented knobs.
- `ruff check scripts/bench_check.py` + `ruff format --check` clean; 3.9-imports OK.
- Write `.agenthub/board/results/agent-8-result.md` (YAML frontmatter
  `author: agent-8`, `channel: results`) and reply with: the bench summary you
  observed (p50/p95, cache win), docs sections changed, and env vars added. Then exit.
