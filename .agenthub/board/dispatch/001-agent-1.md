---
author: coordinator
channel: dispatch
agent: agent-1
task: "Phase 1.1 — retrieval quality & correctness"
files: ["app/rag/ingestion.py", "app/rag/vectorstore.py", "app/rag/system.py", "app/rag/embeddings.py"]
---
# Agent-1 — Retrieval quality & correctness (RAG optimization)

You are agent-1 in AgentHub ensemble session `20260802-121531`. Repo: ChattamAI, a RAG
system to check building plans against the Kerala Building Rules (FastAPI + LangGraph +
FAISS + OpenAI embeddings + Claude via local proxy). Read `README.md` and `plan.md` first.

## CRITICAL shared constraints (all agents follow these)
- **Python 3.9 compatible** (local dev is 3.9.6) but CI tests on 3.12. Keep
  `from __future__ import annotations` at the top of every module. Do NOT use PEP 604
  `X | None` in runtime positions or in Pydantic model field annotations — use
  `typing.Optional[X]`. Builtin generics in annotations (`list[str]`) are OK only because of
  the future import.
- **Verifiability**: never require live network, OpenAI, or Anthropic keys to check your work.
  Any sample data must be deterministic and offline.
- Match existing code style (Ruff-enforced: `ruff check` and `ruff format` must stay clean).
  Max line length 88. Keep docstrings.
- Commit early and often with clear messages. Work ONLY inside your assigned files.

## YOUR files (do not create/edit files outside this list)
- `app/rag/ingestion.py`  (chunking, loaders, rule-id extraction)
- `app/rag/vectorstore.py` (score semantics, threshold, dedup/rebuild)
- `app/rag/system.py`      (rebuild flag in ingest, rule_id threading in check)
- `app/rag/embeddings.py`  (fix `NVIDA_API_KEY` env-var typo -> `NVIDIA_API_KEY`; nothing else)

If you believe a new Settings flag is needed, DO NOT add it yourself — instead read it with a
safe default locally and leave a note in your result post so the coordinator adds it to
`app/config.py` during integration (something else owns config.py).

## What to implement
1. **Sentence-aware chunking** in `ingestion.chunk_text`: split on paragraph then sentence
   boundaries, pack sentences into windows of `chunk_size` chars with `chunk_overlap` — never
   cut mid-word/mid-sentence. Token-free (no tokenizer dep). Keep the public signature.
2. **Rule-id extraction**: add a helper that detects rule/section headers in a chunk
   (e.g. leading `Rule 12`, `Section 5.3`, `5.3`, `Annexure`) and returns a `rule_id` string
   (or None). Use it during ingest to populate chunk metadata.
3. **Score semantics + threshold** in `RuleVectorStore.similarity_search`: FAISS `IndexFlatL2`
   returns squared-L2 distance (lower=better). Normalize embeddings and/or convert distance to
   a **similarity score** (higher=better, e.g. `1/(1+d)`), return that, and drop results below
   a `min_score` threshold (read `MIN_SCORE` via `os.getenv` default `0.0`). Document the new
   semantics in the method docstring.
4. **Dedup + rebuild** in the store + `system.ingest`: content-hash dedup so re-running ingest
   does not duplicate vectors; add a `rebuild: bool = False` param to `RAGSystem.ingest` and a
   `reset()` method on the store that clears index + meta so rebuild starts fresh. Persist as
   today (rules.faiss + rules_meta.json).
5. **rule_id threading** in `system.check`: include `rule_id` (from meta) in each
   `retrieved_rules` dict so `schemas.RuleReference.rule_id` is populated.
6. Fix the `NVIDA_API_KEY` typo in `embeddings.py`.

## Out of scope for you (other agents / coordinator)
No async/await changes, no caching/LLM-call changes, no new endpoints, no OCR, no auth, no
tests, no config.py edits. Agent-2 owns graph/llm/caching.

## Done when
- `ruff check` and `ruff format --check` pass on your files.
- `python -c "import app.main"` succeeds (offline, no keys).
- A quick inline `python - <<'PY'` script demonstrates: chunking splits on sentence boundaries;
  ingest is idempotent (re-run => index_size unchanged); similarity scores are higher=better and
  below-threshold hits are filtered. Show the output in your result post.

Write your summary to `.agenthub/board/results/agent-1-result.md` (YAML frontmatter + the
Result Summary template from the coordination doc). Then exit.
