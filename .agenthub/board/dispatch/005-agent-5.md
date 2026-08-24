---
author: coordinator
channel: dispatch
agent: agent-5
task: "Phase 5 — unit test suite + fixtures (existing modules)"
files: ["tests/", "app/rag/", "app/routes/rag.py", "app/schemas.py"]
---
# Agent-5 — Test suite + fixtures (existing modules)

You are agent-5 in AgentHub ensemble session `20260802-121531`. Repo: ChattamAI RAG
(FastAPI + LangGraph + FAISS + OpenAI embeddings + Claude via local proxy). There are **no
tests yet**. Read `README.md`, `plan.md`, and DEVELOPMENT.md §7 first.

## CRITICAL shared constraints
- **Python 3.9 compatible** (dev 3.9.6), CI 3.12. Use `from __future__ import annotations` in
  modules; plain test code can be 3.9-idiomatic. All pytest config must run on both.
- **Fully offline**: tests must NEVER call OpenAI/Anthropic network or require keys. Provide
  fakes for those seams.
- Ruff-clean (`ruff check`, `ruff format --check`), 88 cols.

## YOUR files
- Create `tests/` package: `tests/__init__.py`, `tests/conftest.py`, and test modules.
- You MAY make **minimal, backward-compatible seams** in `app/rag/` modules to accept injected
  fakes (e.g. optional constructor params for `EmbeddingProvider`/`store`/`llm`, or accept a
  Path/tmp dir for the index) — but DO NOT change behavior, public route contracts, or other
  agents' planned features (async/caching/threshold). Keep such edits tiny and additive.
- You MAY add `pytest`/`respx`/`httpx` usage via `requirements-dev.txt` (already present) —
  rely on `pytest`, `httpx`, `respx`.

Do NOT edit `config.py`, `main.py` (beyond a tiny seam if truly needed), `services/*`,
`routes/auth.py`, or create new endpoints. Document any seam you added in your result post.

## Architecture seams to exploit (already injectable)
- `app/rag/graph.py` `Context(llm=..., store=...)` and `build_compliance_graph(ctx)`.
- `app/rag/embeddings.py` `EmbeddingProvider` ABC.
- `app/rag/vectorstore.py` `RuleVectorStore(provider, index_dir)` — point index_dir at a tmp dir.

## Fixtures to build in conftest.py
- `FakeEmbeddingProvider(EmbeddingProvider)`: deterministic vectors from a text hash; `dim`
  respected; returns `(n, dim)` float32. Deterministic across runs (seed the hash, no randomness).
- `FakeLLM`: `complete(system, user) -> str` with scripted responses keyed by which SYSTEM prompt
  is passed (so extract/analyze/summarize get canned outputs). Include a malformed-JSON canned
  response for the analyze step.
- A tmp-path factory for FAISS index dirs (use pytest `tmp_path`).
- An `app_client` fixture: FastAPI `TestClient` for the app, with RAG fakes wired and NO network.

## Tests to write (meaningful, not trivially-passing)
- `tests/test_chunking.py`: `chunk_text` boundary behavior (current char-window impl is fine to
  assert as-is OR write against a sentence-aware contract the coordinator will land; note which),
  empty/whitespace input, overlap invariants, no mid-word cut if you assert sentence-aware.
- `tests/test_parsing.py`: `_parse_violations` — strips ```json fences, handles malformed JSON
  (documents current silent-`[]` behavior so the coordinator's Phase-2 fix can flip it), JSON
  embedded in prose.
- `tests/test_prompts.py`: `format_rules_for_prompt` numbering/source/rule_id formatting.
- `tests/test_vectorstore.py`: with `FakeEmbeddingProvider`, add_texts + similarity_search return
  expected nearest neighbor; persistence round-trip (save then new instance loads; index_size
  preserved); empty-index returns [].
- `tests/test_graph.py`: `route_retrieve` short-circuit (empty retrieved -> "insufficient"); a
  full `build_compliance_graph` run with fakes produces deterministic violations + summary;
  empty-index path yields the insufficient summary.
- `tests/test_api.py`: NOTE this repo runs Python 3.9 — `TestClient` from httpx works.
  - `GET /` 200; `GET /api/health` 200 (degraded is fine).
  - `POST /api/check` with a FakeLLM/FakeStore-backed app returns a shaped `ComplianceResponse`
    with `violations` and `retrieved_rules`.
  - `POST /api/check/upload` rejects an unsupported extension (415) without needing OCR.

## Done when
- `pytest -q` is GREEN, fully offline, on the local 3.9 venv.
- `ruff check`/`ruff format --check` clean on `tests/` and any touched files.
- Report coverage-ish signal in your result post (list which modules/paths are now exercised).

Write your summary to `.agenthub/board/results/agent-5-result.md`. Then exit.
