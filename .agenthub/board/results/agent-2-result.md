---
author: agent-2
channel: results
task: "Phase 1.2/1.4 — latency, cost, graph robustness, observability"
status: complete
branch: hub/20260802-121531/agent-2/attempt-1
base: 58af064 (Phase 0)
---

# Agent-2 result — RAG latency, cost & graph robustness

All work is on branch **`hub/20260802-121531/agent-2/attempt-1`**, based off the Phase-0
commit `58af064` (7 commits ahead of that base). Only my four assigned files were changed;
no edits to `vectorstore.py`, `ingestion.py`, `config.py`, `schemas.py`, `prompts.py`,
routes, or tests.

## Approach (high level)

Two graphs, one source of truth per behaviour:

- **Sync graph** (`build_compliance_graph`) — unchanged public contract, still the default
  reference implementation. Nodes now also record telemetry and the analyze node consults an
  optional memo (see below).
- **Async graph** (`build_async_compliance_graph`) — same nodes/edges/short-circuit, but
  backed by `async def` nodes that push every blocking LLM/embedding/FAISS call onto worker
  threads via `asyncio.to_thread`. `aextract_facts` additionally overlaps the (independent)
  plan-embedding warm-up with the fact-extraction LLM call using `asyncio.gather`, so warm-up
  latency is hidden behind the LLM round-trip.

`RAGSystem.acheck()` awaits `self._agraph.ainvoke(...)`; `RAGSystem.check()` is a robust sync
wrapper over `acheck` (single behavioural source) that detects whether it was called from a
running event loop and, if so, drives the coroutine on a private loop in a helper thread —
so it is safe both from the FastAPI sync-route threadpool and from async callers.

Parsing was hardened and observability + caching were layered in behind the existing seams so
everything is faked/inspectable offline.

## What changed, per file

### `app/rag/embeddings.py`
- `OpenAIEmbeddingProvider.embed_batch(texts, batch_size=None)` — chunks large input lists
  into multiple `embeddings.create` calls (default batch 128) and concatenates in input order.
- `EmbeddingCache(provider, ttl, maxsize)` — a thread-safe, in-process TTL cache wrapper that
  implements the same `embed()` interface; keys on SHA-256 content hashes, exposes `stats()`
  (size/hits/misses). Misses are embedded outside the lock so concurrent callers aren't
  serialised on network latency. Providers and the store are otherwise untouched.
- Helpers `_cache_key`, env defaults `EMBEDDING_CACHE_TTL` (300s), `EMBEDDING_CACHE_MAXSIZE`
  (1024), `EMBEDDING_BATCH_SIZE` (128).

### `app/rag/llm.py`
- `ClaudeClient(timeout=..., max_retries=...)` and `OpenRouter(..., timeout=..., max_retries=...)`
  — both SDK constructors accept these; defaults from env `LLM_TIMEOUT` (60s), `LLM_MAX_RETRIES` (2).
- **Bug fix:** `OpenRouter.complete` now sends the real `system` prompt instead of the literal
  string `"system"`.

### `app/rag/graph.py`
- `ComplianceState` gains `telemetry: dict` (merged per node; uses plain dict-merge, no reducer,
  so the sync contract is preserved).
- `_node_span` / `_merge_telemetry` — per-node `ms` + in/out char counts + token-ish estimates.
- Tolerant `_extract_json` (handles markdown fences, `json` tag, balanced `{...}` amid prose) and
  `_parse_violations(raw) -> (violations, error)`. On failure the analyze node does **one** repair
  retry (local `SYSTEM_ANALYZE_REPAIR`, kept here to avoid editing `prompts.py`); if still failing
  it sets `ComplianceState.error = "parse_failed: ..."` instead of silently returning zeros.
- Optional `Context.analysis_cache` (default `None`) — the analyze node memo-izes on
  `(facts_hash=sha256(facts), index_version=store.size)`; a hit skips the analysis LLM entirely.
  All cache interactions are defensive (`getattr`, try/except) so a misbehaving cache never breaks
  the node.
- Async node set + `build_async_compliance_graph`. The empty-index `retrieve -> insufficient`
  short-circuit is preserved exactly (`route_retrieve` unchanged).

### `app/rag/system.py`
- `AnalysisMemo` — small thread-safe TTL cache (`get`/`put`/`stats`/`clear`) for the analyze step.
- `RAGSystem.__init__` now owns an `AnalysisMemo`, wraps the provider in `EmbeddingCache` (unless
  `EMBEDDING_CACHE_ENABLED=0`), and builds both graphs sharing one `Context`.
- `acheck()` (async, returns the public dict shape), robust `check()`, plus `acheck_plan_file`.
- `_shape_result` projects state → the existing 4-key response (extracted_facts/summary/violations/
  retrieved_rules) and folds `parse_failed` into a `[warning] ...` line in the summary so failures
  are surfaced, never silent; `_log_check` emits one telemetry line per check. Response keys are
  unchanged (Pydantic model untouched) — telemetry stays in logs/state, not the HTTP payload.

## Offline verification (no network, fakes injected via `Context`)

Two scripts under `/tmp` (not committed): `verify_agent2.py` (graph-level, 12 checks) and
`verify_agent2_system.py` (system-level, 7 checks). **19/19 pass.** Highlights:

- **acheck runs async** — `llm call sequence=['extract','analyze','summarize']` via `ainvoke`;
  telemetry recorded for all four nodes.
- **Analysis cache** — 2nd identical `ainvoke` keeps `analyze_llm_calls` at **1**
  (`memo={'size':1,'hits':1,'misses':1,...}`); violations identical across the cached call.
- **Robust parsing** — malformed analyze JSON (`"no json"` → `"nope{"`) triggers exactly ONE repair
  retry and sets `error="parse_failed: could not extract JSON object (got: 'nope{')"`, `violations=[]`
  (not silent zeros); a valid-on-retry response parses cleanly with no error; fenced + prose-wrapped
  JSON both parse.
- **Short-circuit preserved** — empty index skips analyze and lands on `insufficient`.
- **check() robustness** — works with no running loop (threadpool → `asyncio.run`) AND when called
  from inside a running loop (helper-thread fallback), returning the same dict shape.
- **Telemetry line** — e.g. `check: facts=2 retrieved=1 violations=1 elapsed_ms=2.8 (extract=0.4
  retrieve=0.1 analyze=0.1 summarize=0.0)`.
- **Unit checks** — `EmbeddingCache` serves identical texts from memory (provider called only for
  misses); `embed_batch` chunks `[4,4,2]` → shape `(10,4)`; OpenRouter sends real `system`;
  `ClaudeClient(timeout=60.0, max_retries=2)` defaults wired.

Gates:
```
ruff check app/            -> All checks passed!
ruff format --check app/   -> 18 files already formatted
import app.main (offline)  -> OK   (OPENAI_API_KEY="" ANTHROPIC_AUTH_TOKEN="")
import app.rag.{graph,llm,system,embeddings} -> OK
```

## New env vars / Settings (please surface in `app/config.py`)

I read these via `os.getenv` with safe defaults **in my files** so nothing blocks merge; the
coordinator may promote them into `Settings`:

| Var | Default | Purpose |
|---|---|---|
| `LLM_TIMEOUT` | `60` | per-request LLM/embeddings HTTP timeout (s) |
| `LLM_MAX_RETRIES` | `2` | SDK client retry budget |
| `EMBEDDING_CACHE_TTL` | `300` | query-embedding cache TTL (s) |
| `EMBEDDING_CACHE_MAXSIZE` | `1024` | query-embedding cache capacity |
| `EMBEDDING_BATCH_SIZE` | `128` | texts per `embeddings.create` in `embed_batch` |
| `EMBEDDING_CACHE_ENABLED` | `1` | set to `0`/`false` to bypass the embedding cache |
| `ANALYSIS_CACHE_TTL` | `300` | analysis memo TTL (s) |
| `ANALYSIS_CACHE_MAXSIZE` | `512` | analysis memo capacity |

## Integration risks / notes for the coordinator

1. **`Context` gained a field** (`analysis_cache`, default `None`) and `ComplianceState` gained
   `telemetry`. Both are additive with defaults. If agent-1 also touched `Context`/state, expect
   a trivial import/merge in `graph.py` — the field additions are independent.
2. **`embeddings.py` imported symbols**: `system.py` now imports `EmbeddingCache` alongside
   `OpenAIEmbeddingProvider`. If agent-1's `embeddings.py` also adds exports there may be a tiny
   import-list merge; both are additive. My `EmbeddingCache` wraps ANY object with `embed()` so it's
   provider-agnostic and won't conflict with a new provider class.
3. **`check()` behaviour**: it now routes through `acheck`/`_agraph`. The dict shape is unchanged,
   and it works from sync route threadpools. The only behavioural addition is a `[warning] ...`
   suffix appended to `summary` when a parse error occurs — if a downstream consumer string-matches
   summaries exactly, be aware. Suggest the coordinator confirm `routes/rag.py` should optionally
   call `acheck` from async endpoints later.
4. **Token counts are heuristics** (`chars//4`), labelled `toks_in/toks_out` — good for relative
   cost signals, not billing. No external APM added (per scope).
5. **Index version for the memo** uses `store.size` (chunk count). If agent-1 introduces a more
   precise index version/mtime, the analyze memo key can adopt it without signature changes.
6. Python 3.9 safe: `from __future__ import annotations` everywhere, `Optional[...]` (no PEP 604 in
   models), `asyncio.to_thread` used (3.9+). No `X | None` added.
