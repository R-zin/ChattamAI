---
author: coordinator
channel: dispatch
agent: agent-2
task: "Phase 1.2/1.4 — latency, cost, graph robustness, observability"
files: ["app/rag/graph.py", "app/rag/llm.py", "app/rag/system.py", "app/rag/embeddings.py"]
---
# Agent-2 — Latency, cost & graph robustness (RAG optimization)

You are agent-2 in AgentHub ensemble session `20260802-121531`. Repo: ChattamAI RAG
(FastAPI + LangGraph + FAISS + OpenAI embeddings + Claude via local proxy). Read `README.md`
and `plan.md` first.

## CRITICAL shared constraints (all agents follow these)
- **Python 3.9 compatible** (local dev 3.9.6), CI on 3.12. Every module keeps
  `from __future__ import annotations`. Prefer `TYPE_CHECKING` imports over heavy runtime
  imports where reasonable. Do NOT use PEP 604 `X | None` in Pydantic models —
  `typing.Optional[X]` there. In THIS module's plain type hints you may keep `Optional[...]`.
  `asyncio.to_thread` is available on 3.9+.
- **Verifiability**: never require live network/keys to validate. All LLM/embedding calls must
  remain behind injectable seams (`Context.llm`, `EmbeddingProvider`) so they can be faked.
- Match existing Ruff style (`ruff check`, `ruff format --check` clean, 88 cols), keep docstrings.
- Commit early/often. Work ONLY inside your assigned files.

## YOUR files (do not create/edit files outside this list)
- `app/rag/graph.py`     (nodes, routing, parsing, observability)
- `app/rag/llm.py`       (ClaudeClient timeout/retry; fix OpenRouter system bug)
- `app/rag/system.py`    (async check path, caching glue)
- `app/rag/embeddings.py`(batched `embed_batch` + small `EmbeddingCache`; nothing else)

Another agent (agent-1) is also editing `system.py` and `embeddings.py` on a separate branch;
the coordinator will merge. To minimize collisions: keep your edits additive and localized
(batch method, cache class, async wrappers), do not reformat untouched lines, and do not change
`ingest` chunking or the store. Do NOT edit `vectorstore.py`, `ingestion.py`, `config.py`,
`schemas.py`, or `prompts.py`.

If you need new Settings (e.g. CACHE_TTL, timeouts), read them via `os.getenv` with a safe
default and note them in your result post for the coordinator to add to `app/config.py`.

## What to implement
1. **Async + parallel**: keep the sync LangGraph `build_compliance_graph` contract, but add an
   async check path. Where two LLM calls are independent, run them concurrently via
   `asyncio.to_thread`. Currently the pipeline is extract_facts -> retrieve -> analyze ->
   summarize (all serialized). Analyze depends on facts+retrieve, but you can overlap work:
   e.g. pre-compute the retrieval embedding while extract_facts runs, and run summarize without
   an extra serialized round-trip where safe. Add `RAGSystem.acheck()` returning the same dict
   shape as `check()`, and keep `check()` working (it may wrap `acheck` via `asyncio.run` — but
   careful: `check()` may be called from within a running loop in FastAPI sync routes; make it
   robust, e.g. detect running loop).
2. **Timeouts + retries** on the Anthropic and OpenAI clients (constructor `timeout=`,
   `max_retries=`; read from env with sane defaults).
3. **Caching**: an embedding cache (content-hash -> vector) for query embeddings, and an
   optional analysis memo keyed by (facts_hash, index_version) so an identical re-check skips
   the LLM. Small in-process TTL cache (no external store). Expose TTL via env with default.
4. **Batching**: add `embed_batch(texts, batch_size=...)` to `OpenAIEmbeddingProvider` that
   chunks large input lists into multiple `embeddings.create` calls and concatenates, plus an
   `EmbeddingCache` wrapper class implementing the same `embed()` interface.
5. **Fix LLM bug**: `OpenRouter.complete` sends the literal string `"system"` — pass the real
   `system` param.
6. **Robust parsing**: replace the naive fence-strip in `graph._parse_violations` with a
   tolerant JSON extractor (find the first `{...}` block). On parse failure, do ONE LLM repair
   retry, and if still failing set the `ComplianceState.error` field (currently unused) to a
   `parse_failed: ...` message instead of silently returning zero violations.
7. **Observability**: add lightweight per-node timing + token-ish counts into `ComplianceState`
   (e.g. a `telemetry` dict) and have `system` log one line per check: facts n, retrieved n,
   violations n, elapsed ms. No external APM.

## Out of scope for you
No chunking/threshold/dedup (agent-1), no endpoints/OCR/auth/tests/config.py. Preserve the
empty-index short-circuit to the `insufficient` node exactly (graph.py:96).

## Done when
- `ruff check`/`ruff format --check` clean; `python -c "import app.main"` OK offline.
- Demonstrate (offline, with a fake llm/store injected via `Context`) that: acheck runs the
  pipeline asynchronously; a repeated identical check hits the analysis cache (second call
  skips the LLM — prove via a counting fake); malformed analyze JSON triggers the error path,
  not silent zeros. Show outputs in your result post.

Write your summary to `.agenthub/board/results/agent-2-result.md`. Then exit.
