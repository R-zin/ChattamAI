---
author: agent-5
channel: results
agent: agent-5
task: "Reconcile Phase-5 tests to the merged optimized RAG behavior"
status: complete
branch: hub/20260802-121531/agent-5/attempt-2
base: 8cfd21e
commit: 8c081b8
---

# Agent-5 Result — Reconcile tests to optimized behavior

## Summary
Re-pinned the offline test suite onto the merged `feature/optimized-rag` state
(agents 1+2+3+4 all landed, plus my attempt-1 suite). The suite went from **17
failed + 8 errored** on the old pins to **69 passed, 0 failed**. All changes are
in `tests/` only — **no feature code was edited or reverted**. I verified every
NEW contract by reading the merged source and probing it live, rather than
trusting the coordinator summary (one of the coordinator's stated behaviors was
inaccurate — see "Coordinator-summary correction" below).

## Status
- Branch: **`hub/20260802-121531/agent-5/attempt-2`** (off `feature/optimized-rag`
  tip `8cfd21e`). Committed there only; no PR, no push.
- `pytest -q` → **69 passed**, **fully offline** (proven by re-running with all
  outbound sockets disabled + all credential env vars stripped; also green with
  ambient env), on the local CPython **3.9.6** venv.
- `ruff check tests/` → **All checks passed!** ; `ruff format --check tests/` →
  **8 files already formatted**.
- `python -c "import app.main"` → **OK** offline with no keys.
- Coverage (`--source=app`): `graph.py` 92%, `vectorstore.py` 89%,
  `prompts.py`/`schemas.py`/`main.py` 100%, `system.py` 69%, `routes/rag.py` 78%.
  Uncovered lines remain the real-network bodies (`embeddings.py` OpenAI/cache
  internals 34%, `llm.py` 47%) and `ingestion.py` PDF path — the intended
  offline shape. **75% total.**

## Coordinator-summary correction (verified against code)
The coordinator said fenced JSON returns `([], None)`. **Verified live**: a
``` json fence actually **parses successfully** to `([...], None)` (the
`lstrip("`")` + balanced-brace extractor recovers it). So my
`test_json_fence_is_parsed` / `test_bare_backtick_fence_is_parsed` assert
parsed-with-`None`-error. The rest of the summary (tuple shape, error-on-
unparseable, prose recovery, cosine/threshold, sha256, sentence chunking)
matched the code exactly.

## What changed per failing group (tests/ only)
- **`conftest.py` (fixtures)**
  - `FakeEmbeddingProvider` REWRITTEN: deterministic **token feature-hashing**
    (each distinct token adds +1 to a hashed bucket; vector L2-normalised).
    Identical text -> cosine 1.0; topically-related text -> positive cosine;
    unrelated -> ~0. This makes the new **cosine `IndexFlatIP`** store retrieve
    the *semantically matching* chunk (a "front setback" query ranks Rule 5
    first), which the old random-hash fake could not (its cross-text cosines
    were negative and got dropped by the default `min_score=0.0` threshold).
    Default `dim=256` keeps collisions rare. (This is what un-broke the
    `/api/check` + `RAGSystem.check()` shape/top_k tests — retrieval now returns
    hits instead of short-circuiting to `insufficient`.)
  - `FakeLLM` gained **`repair_mode`** (default `"malformed"`) to script the
    analyze node's ONE repair retry (`SYSTEM_ANALYZE_REPAIR`), so the error path
    and the repair-recovery path are both exercisable.
  - Set `DATABASE_URL` to a tmp file **before** app import so agent-4's auth/DB
    (`app.services.database` reads env at import) writes to the temp dir, not a
    stray `chattamai.db` in the test CWD.
  - Installed the already-declared auth deps (`python-jose`, `passlib[bcrypt]`,
    `bcrypt<4.1`) into my local venv — `app.main` now imports the auth router,
    which needs `jose`. (Not a code change; just dev-env deps from
    `requirements.txt`.)
- **`test_parsing.py`** — `_parse_violations` now returns `(violations, error)`.
  Asserted: plain/fenced/prose-embedded JSON -> `([...], None)`; unparseable /
  malformed / non-dict / `violations`-not-a-list / empty -> `([], "parse_failed:
  ...")`; valid-object-missing-key -> `([], None)`. No more silent `[]`.
- **`test_chunking.py`** — sentence-aware contract: empty/whitespace -> `[]`
  (kept); whitespace-normalise; `<= size` bound (kept); **whole-sentence packing**
  (no mid-sentence cut, verified concrete first-chunk output); **the immediately
  -preceding sentence always bridges into the next chunk even at `overlap=0`**
  (my earlier `overlap=0 => no repetition` assumption was WRONG and was the last
  failure); **larger `overlap` pulls in additional earlier context**; clause
  number `8.1.2` not split; over-long sentence hard-splits with `<= size`.
- **`test_vectorstore.py`** — cosine **higher=better**: exact copy == `1.0` ranked
  FIRST, descending order, topical query ranks the matching rule first; threshold
  filtering (store-default `score_threshold` applied + per-call override wins);
  `add_texts` returns added-count, dedups identical content (idempotent, returns
  0 on re-add), and sets a `sha256` meta while preserving passed meta; persistence
  round-trip preserves size + retrieval, and the meta file now carries
  `version`/`model`/`dim`/`hashes`/`texts`/`metas`.
- **`test_graph.py`** — malformed analyze now triggers ONE repair retry that, on
  failure, sets `error="parse_failed: ..."` (summarize still runs; violations
  `[]`) — replaced the old `"error" not in out` pin. Added
  `test_analyze_repair_retry_recovers_valid_json` for the repair-success path.
  Routing, full-fake-run, and empty-index `insufficient` short-circuit tests
  unchanged (still green).
- **`test_api.py`** — **no edits needed**; it went fully green once the conftest
  fake produced real retrieval hits and the auth deps/`DATABASE_URL` were sorted.
  Covers `/`, `/api/health` (ok + default-boot degraded), `/api/check` shape +
  422 + `top_k`, `/api/check/upload` 415 (.png/.docx/.jpg/.exe) + 200 (.txt).

## Real bugs found in merged feature code
**None.** All 25 initial failures were the intentional behavior flips you
flagged. I additionally verified the new async plumbing is sound offline:
`await rag.acheck(...)` works, and calling the sync `rag.check(...)` **from
inside a running event loop** does not raise (agent-2's helper-thread fallback),
both under the fakes. RAG routes remain unprotected with `AUTH_REQUIRED` unset
(`require_auth` no-op by default), and lifespan `init_db_safe()` never breaks
the RAG boot — matching my API tests' assumptions.

## Notes / non-blocking observations (not fixing; FYI only)
- `app/rag/graph.py::analyze` keys the analysis memo on
  `(facts_hash, ctx.store.size)`. A rebuild that replaces content but keeps the
  same `size` would reuse a stale memo. Out of my scope; flagging for agent-2 /
  whoever owns the memo.
- `chunk_sentences` re-includes the prior sentence even at `overlap=0` (the
  bridge is unconditional; `overlap` only budgets *extra* context). Behavior is
  intentional per the docstring; just calling out that "overlap=0" does not mean
  "no shared sentence", in case the term is documented elsewhere as zero-overlap.
