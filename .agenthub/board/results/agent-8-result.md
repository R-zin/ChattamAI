---
author: agent-8
channel: results
agent: agent-8
task: "Phase 6 — perf harness (bench_check.py) + docs/env/roadmap close-out"
status: complete
branch: hub/20260802-121531/agent-8/attempt-1
base: 9e899a8
commit: ac9fe4a
---

# Agent-8 Result — Phase 6 Bench + docs

## Summary
Built an **offline, keyless perf harness** (`scripts/bench_check.py`) that runs N
compliance checks against a fakes-backed `RAGSystem` (no OpenAI/Anthropic keys, no
network) and reports p50/p95 latency plus the embedding-cache + analysis-memo win
versus an uncached baseline. Also refreshed `README.md`, `DEVELOPMENT.md`,
`.env.example`, and `plan.md` so they accurately describe the current
`feature/optimized-rag` tree (the stale "auth/DB unused" claim is corrected). All
work is confined to the assigned files; **`app/` was read-only** for me.

## Observed bench summary (`--checks 20`, offline)
Command: `python scripts/bench_check.py --checks 20 [--json]` — runs end-to-end
offline. Representative numbers (FakeLLM latency=5ms/call; absolute ms vary run to
run, the *relative* win is the signal):

- **cached arm**   (embedding-cache + analysis-memo, identical repeats):
  `p50=15.4ms p95=16.6ms  (emb_calls=5, llm_calls=41)`
- **uncached baseline** (no caches, unique plans):
  `p50=23.0ms p95=24.5ms  (emb_calls=43, llm_calls=60)`
- **cache win:** repeat ≈ `15ms` vs first ≈ `22ms` (**~30–37% faster** via
  embedding-cache+analysis-memo); **~33–37% faster p50 than the uncached baseline**.
- **cost delta (20 checks):** embedding-API calls saved **38**, analyze-LLM calls
  saved **19** (analyze ran once, memo'd on the 19 repeats; extract+summarize still
  run per call). `retrieved=3, violations=1, index_size=3`.

## How the harness works (and why it's faithful)
- Inline fakes (NOT imported from `tests/`, per the rules): a deterministic
  `FakeEmbeddingProvider` (hashed bag-of-words → L2-normalised unit vectors, so
  shared tokens get positive cosine and identical text scores ~1.0 — the real store
  ranks by cosine/higher=better) and a `FakeLLM.complete(system, user)` keyed on
  `SYSTEM_EXTRACT`/`SYSTEM_ANALYZE`/`SYSTEM_SUMMARY` with a valid
  `{"violations":[...]}` analyze payload.
- Builds `RAGSystem(provider=FakeEmbeddingProvider(), llm=FakeLLM(), index_dir=<tmp>)`
  and ingests a 3-rule synthetic KBR corpus (one file per rule → one chunk + rule_id
  each). Drives `rag._agraph.ainvoke(...)` (the same pipeline `check()` uses) so
  per-node `telemetry` (extract_facts/retrieve/analyze/summarize ms) is read from the
  raw graph state; total latency is wall-clocked per call.
- The FakeLLM's extract answer embeds a `plan-id` derived from the plan text, so
  unique plans → unique facts → unique analysis-memo (`facts_hash`) keys, which is
  what makes the uncached baseline genuinely miss the memo while the identical-repeat
  cached arm hits it.
- CLI: `--checks N` (default 20), `--repeat/--identical` (default on) vs `--unique`,
  `--top-k K`, `--no-embedding-cache`, `--no-analysis-cache`, `--json`.
- Verified: cached-arm `--no-*`/`--unique` collapse to baseline (~0 calls saved,
  analyze runs every call) — confirming the harness isolates the cache effect.

## Docs sections changed
- **README.md** — added "What's in this build" (cosine retrieval/MIN_SCORE/rule_id/
  idempotent ingest+rebuild, async `acheck` + embedding/analysis caches, timeouts/
  retries, JWT auth, KBR downloader, perf harness); rewrote Quickstart (configure env
  → optionally fetch KBR → `POST /api/ingest` w/ `rebuild` → `POST /api/check`); new
  Auth snippet + Benchmark section; updated Layout + Limitations.
- **DEVELOPMENT.md** — §7 rewritten: auth/DB is now **used** (router mounted,
  `init_db_safe()` in lifespan, bcrypt, JWT; protection opt-in via `AUTH_REQUIRED`,
  OFF by default) — the stale "currently unused"/"dead code" claims removed. Added an
  **Optimizations** subsection (cosine + MIN_SCORE, sentence-aware chunking, async
  graph + EmbeddingCache + AnalysisMemo, `EMBEDDING_BATCH_SIZE`, LLM timeout/retries,
  telemetry + harness) and a **Python 3.9-dev/3.12-CI caveat** (no PEP 604 in runtime
  positions). Also updated §1 stack, §3 layout, §4 env table, §5 operations (rebuild/
  idempotency/async/telemetry + fetch_kbr dev loop), §6 cosine semantics, §9.
- **plan.md** — restructured into Phases 0–6 marked **[DONE]** (hygiene, optimized RAG
  core, KBR downloader, auth/DB, tests, bench+docs) with genuinely-future work kept as
  **[FUTURE]** (layout/image OCR, IVF/HNSW, hybrid BM25, Alembic, hardening).
- **.env.example** — appended the new tunables, grouped, each verified against
  `app/config.py`.

## Env vars added (all cross-checked against the code — no invented knobs)
`MIN_SCORE`, `EMBEDDING_CACHE_ENABLED`, `EMBEDDING_CACHE_TTL`,
`EMBEDDING_CACHE_MAXSIZE`, `EMBEDDING_BATCH_SIZE`, `ANALYSIS_CACHE_TTL`,
`ANALYSIS_CACHE_MAXSIZE`, `LLM_TIMEOUT`, `LLM_MAX_RETRIES`, `SECRET_KEY`,
`AUTH_ALGORITHM`, `AUTH_REQUIRED`, `ADMIN_KEY`, `TIME_OUT`, `DATABASE_URL`.

## ⚠️ Discrepancy vs. dispatch — OCR is NOT in the tree
The dispatch asked me to document a feature-flagged **`POST /api/check/plan-ocr`**
endpoint and an **`OCR_ENABLED`** tunable. **Neither exists in the current code**:
there is no OCR route anywhere (verified: mounted routes are only
`/api/health|/ingest|/check|/check/upload|/setmodel` + `/auth/register|login|
login/json|me`), and `grep -ri ocr` finds only the "OCR is future work" comment in
`ingestion.py`. `OCR_ENABLED` is not in `config.py`. Per the hard rule "do NOT invent
env vars or endpoints," I did **not** document them as shipped — OCR/phase-2 is
recorded as **future work** in plan.md and DEVELOPMENT.md §7/§9 instead. If the
coordinator intended OCR to land in another agent's diff, it isn't on
`feature/optimized-rag` yet.

## Verification performed
- `python scripts/bench_check.py --checks 5` runs offline end-to-end and prints a
  sensible latency/cost summary (above); `--json` emits a valid, parseable blob.
- `ruff check scripts/bench_check.py` — clean; `ruff format --check` — clean. Whole-repo
  `ruff check .` — clean.
- Imports + syntax OK on Python 3.9.6 (`from __future__ import annotations`; no PEP 604
  in runtime positions; `typing.Optional` used).
- Every documented env var confirmed present in `app/config.py`; every documented
  endpoint confirmed mounted (enumerated via the FastAPI app's routes).

## Pre-existing issue I did NOT touch (owned by other agents)
`pytest` at base `9e899a8` shows **18 failed / 34 passed** — failures are in
`tests/test_vectorstore.py`, `test_parsing.py`, `test_graph.py`, `test_chunking.py`,
`test_api.py` and assert the **old** `IndexFlatL2` distance semantics and lenient-parse
behavior (e.g. `test_scores_are_ascending_distances`, `test_malformed_json_returns_empty_silently`).
I confirmed these failures pre-exist at the base commit (I stashed my changes and re-ran
— identical 18 failures), so they are an integration/testing-semantics reconciliation,
not something my bench+docs changes introduced. I documented this candidly in
DEVELOPMENT.md §5 and plan.md instead of claiming a green suite. Coordinators may want
agent-5 (tests) to reconcile those expectations with the new cosine + strict-score
semantics.
