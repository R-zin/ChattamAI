---
author: agent-5
channel: results
agent: agent-5
task: "Phase 5 — unit test suite + fixtures (existing modules)"
status: complete
branch: hub/20260802-121531/agent-5/attempt-1
base: 58af064
commit: 1bfb5b2
---

# Agent-5 Result — Phase 5 test suite + fixtures (existing modules)

## Summary
Built a **fully offline** `tests/` package (8 files, **52 tests, all passing**)
measured against the CURRENT pre-optimization code on base `58af064`.
Deterministic fakes stand in for OpenAI embeddings and the Anthropic LLM; FAISS
indexes live in pytest `tmp_path`; the FastAPI app is exercised through an httpx
`TestClient` with fakes injected via `app.state.rag`. **Proven offline**: the
suite passes with all outbound sockets hard-disabled and all credential env vars
unset. `ruff check` and `ruff format --check` are clean on the whole repo.

## Branch / status
- Branch holding my final commits: **`hub/20260802-121531/agent-5/attempt-1`**
  (created from Phase-0 base `58af064`, per the coordinator's correction).
- `pytest -q` → **52 passed** (offline, local CPython 3.9.6 venv, and re-verified
  green under socket-block + with ambient env present).
- `ruff check .` → **All checks passed!** ; `ruff format --check .` → **27 files
  already formatted**.

## Fixtures built (`tests/conftest.py`)
- **`FakeEmbeddingProvider(EmbeddingProvider)`** — deterministic, no randomness:
  SHA-256 of the text is expanded into a centred, **unit** `dim`-vector
  (respects `dim`; returns `(n, dim)` float32). Identical texts embed
  identically, so an exact-copy query is always its own nearest neighbour. It
  also records `calls` for assertion.
- **`FakeLLM`** — `complete(system, user) -> str` scripted by which SYSTEM prompt
  is passed (`SYSTEM_EXTRACT` → canned `- param: value` bullets; `SYSTEM_ANALYZE`
  → canned violations JSON; `SYSTEM_SUMMARY` → canned report). `analyze_mode`
  selects the analyze body: `ok` / `malformed` / `fenced` (```json) / `prose`.
  Records `calls` so tests assert node ordering.
- **tmp-path FAISS fixtures** — `index_dir` (pytest `tmp_path`), `store` (empty),
  `populated_store` + `make_populated_store(...)` with a small deterministic
  KBR-like rule set, and `build_rag_system(...)` / `make_populated_store_into(...)`.
- **`app_client`** — FastAPI `TestClient` (httpx-backed); boots the real app via
  lifespan, then overrides `app.state.rag` with a fake-backed `RAGSystem`. Exposes
  `.fake_llm` / `.fake_provider` for per-test inspection. No network anywhere.

## Test modules and what they cover
- **`test_chunking.py`** (7) — pins CURRENT char-window `chunk_text` behaviour:
  empty/whitespace → `[]`; whitespace normalisation; `size` bound per chunk;
  `step = size - overlap` shared-character overlap invariant; full source coverage;
  window boundaries land on `i*step`. **Sentence-aware flip noted** (see below).
- **`test_parsing.py`** — `_parse_violations`: plain JSON, ```json fence, bare ```
  fence all parse; **malformed JSON returns `[]` silently (documented so the
  Phase-2 fix can flip it to set `error`)**; non-dict top-level → `[]`; missing
  `violations` key → `[]`; empty string → `[]`; **JSON embedded in prose is NOT
  recovered today (returns `[]`)** — flagged for agent-2's tolerant extractor.
- **`test_prompts.py`** — `format_rules_for_prompt`: 1-based numbering;
  `[{i}] ({source} / {rule_id})` rendering; fallbacks `rule_id` → `chunk` → index
  and `source` → `unknown`; blank-line join; empty input; `build_analyze_user`
  interpolation.
- **`test_vectorstore.py`** — with `FakeEmbeddingProvider`: provider shape/dtype
  and determinism; `add_texts` sizing; exact-copy query ranked first;
  **ascending raw squared-L2 distances with exact match == 0.0 (CURRENT semantics)**;
  `k` capped by index size; empty index → `[]`; uninitialised store → `[]`;
  **persistence round-trip** (save then a new `RuleVectorStore` over the same dir
  reloads, `size` preserved, retrieval works); `rules.faiss`/`rules_meta.json`
  written; empty-add no-op; missing metas → `{}`.
- **`test_graph.py`** — `route_retrieve` short-circuit (`[]`/`{}` → `insufficient`,
  non-empty → `analyze`); full `build_compliance_graph` run with fakes yields the
  scripted violations + summary + facts and calls extract→analyze→summarize in
  order; malformed analyze JSON → `violations == []` but summarize still runs and
  **no `error` key (current silent behaviour)**; empty-index path yields the
  insufficient summary and skips analyze/summarize; `RAGSystem.check()` shapes the
  response (`extracted_facts` bullet-stripped, `retrieved_rules` with
  source/excerpt/score).
- **`test_api.py`** — `GET /` 200 + endpoint map; `GET /api/health` 200 (ok with
  fakes, **degraded-with-no-keys on default boot** — the CI smoke expectation);
  `POST /api/check` returns a shaped `ComplianceResponse` (violations +
  retrieved_rules + facts + summary); `plan_text` validation → 422; `top_k`
  respected; `POST /api/check/upload` **415** on `.png/.docx/.jpg/.exe` (no OCR /
  network needed) and 200 on `.txt`; default-boot `/` and `/api/health` are 200
  with no credentials.

## Coverage-ish signal (coverage.py, `--source=app`)
100%: `config.py`, `main.py`, `schemas.py`, `rag/graph.py`, `rag/prompts.py`.
95% `vectorstore.py`; 78% `routes/rag.py`; 71% `system.py`. **79% total.** The
uncovered lines are exactly the network surfaces the suite must NOT touch:
`rag/embeddings.py` 49% (OpenAI/Nvidia HTTP bodies), `rag/llm.py` 43%
(Anthropic/OpenRouter), `rag/ingestion.py` 53% (PDF read + `load_kbr_documents` dir
scan). This is the intended offline shape.

## Seam added to app/rag/* (documented, additive, backward-compatible)
- **`app/rag/system.py` — `RAGSystem.__init__`** gained three OPTIONAL keyword
  params: `provider=None`, `llm=None`, `index_dir=None`. When a `provider`/`llm`
  is supplied it is used directly and readiness is set `True`, skipping the real
  OpenAI/Anthropic construction; `index_dir` points the FAISS store at a tmp dir.
  **When all are omitted the original construction path runs byte-for-byte** and
  default startup still degrades gracefully with no credentials (verified). No
  other module/behaviour/contract changed; no endpoints touched.
- Supporting new repo files: **`pyproject.toml`** (ruff: 88 cols + `target-version
  py39`, isort first-party `app`/`tests`, relax `E731`; pytest: `testpaths`,
  `asyncio_mode=auto`) and a **`.gitignore`** entry for the local `.venv-tests/`.
  Neither is in any other agent's assigned file list.

## Reconciliation notes for the post-optimization agents
My tests deliberately pin the CURRENT behaviour and **annotate which assertions
the landed/planned changes are expected to flip**. When the coordinator merges
agent-1/agent-2, update these specific assertions (test comments say the same):
- **agent-1 score semantics (already landed on agent-1 branch)**: `similarity_search`
  now returns **cosine similarity, HIGHER=better**, with a `min_score` threshold.
  `test_vectorstore.py` currently asserts ascending distances and `self-match ==
  0.0`. After merge, the self match should be the MAX score (≈ 1.0 for the
  normalised fake) and ordering becomes **descending**. The empty-index → `[]`,
  `k`-cap, persistence, and `(text, meta, score)` tuple shape assertions are
  stable. agent-1 also adds `rule_id` to retrieved dicts — my
  `test_check_*`/`format_rules` tests already tolerate extra keys.
- **agent-1 sentence-aware chunking (already landed)**: `test_chunking.py`'s
  boundary/`i*step`/mid-word assertions pin the old char-window and SHOULD be
  rewritten to the sentence-aware contract (no mid-word/sentence cut). The
  empty-input and `size`-bound assertions stay valid.
- **agent-2 `_parse_violations` (planned)**: malformed JSON will set
  `ComplianceState.error` instead of silently returning `[]`, and prose-embedded
  JSON will be recovered. Flip `test_parsing.py::test_malformed_json_returns_
  empty_silently`, `test_json_embedded_in_prose_not_recovered_currently`, and
  `test_graph.py::test_analyze_malformed_json_*` accordingly (they assert the
  current silent path / absent `error`).
- **agent-2 acheck/caching (planned)**: add new tests for `acheck()`; my
  `check()` sync-path tests must keep passing (agent-2 keeps `check()` working).
- **agent-4 auth (planned, opt-in/OFF by default)**: my API tests assume auth is
  OFF; they should remain green. If the coordinator attaches `require_auth`, gate
  new tests on `AUTH_REQUIRED`.
- My `RAGSystem.__init__` seam is additive and does not collide textually with
  agent-1's or agent-2's `system.py` edits (they touch `ingest`/`check`/acheck; I
  touch only the constructor body), but a 3-way merge of `system.py` will need a
  quick eyeball since more than one agent edits that file.

## How to run
```
python3.9 -m venv .venv-tests && source .venv-tests/bin/activate
pip install -r requirements-dev.txt
pytest -q            # offline, 52 passed
ruff check . && ruff format --check .
```
