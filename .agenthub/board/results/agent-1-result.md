---
author: agent-1
channel: results
agent: agent-1
task: "Phase 1.1 — retrieval quality & correctness"
status: complete
branch: hub/20260802-121531/agent-1/attempt-1
base: 58af064
commit: f9935d6
---

# Agent-1 Result — Phase 1.1 Retrieval quality & correctness

## Summary
Implemented all five spec items. Retrieval now ranks by **true cosine similarity**
(higher = more similar) instead of raw FAISS L2 distance, chunking never splits
mid-sentence, every excerpt carries a citable `rule_id`, ingest is idempotent, and
the NVIDIA env-var typo is fixed. All work is confined to the four assigned files.

## What changed (per file)
- **`app/rag/embeddings.py`**
  - Fixed `NVIDA_API_KEY` → `NVIDIA_API_KEY` (the only behavioural fix required here).
  - Added `l2_normalize()` + `EmbeddingProvider.embed_normalized()` so vectors can be
    unit-normalised for cosine search; removed a redundant inner `import os`.
- **`app/rag/vectorstore.py`**
  - Switched from un-normalised `IndexFlatL2` (squared-L2 *distance*, lower=better) to
    L2-normalised `IndexFlatIP`, so `similarity_search` returns a cosine similarity in
    `[-1, 1]` where **higher = better**.
  - Added min-similarity threshold filtering (store default + per-call override).
  - Added **content-hash (sha256) dedup** → re-ingest is idempotent; `reset()` for rebuilds.
  - Versioned the on-disk metadata (`version: 2`) and reject incompatible old indexes so
    stale L2-distance vectors are never mixed with new cosine vectors.
- **`app/rag/ingestion.py`**
  - New `split_sentences()` (whitespace-collapse + conservative boundary regex that does
    **not** split clause numbers like `8.1.2`) and `chunk_sentences()` which packs whole
    sentences into `chunk_size` windows with `chunk_overlap` context carried across the
    boundary. Over-long single sentences fall back to a bounded char-window split so no
    chunk exceeds `chunk_size`. `chunk_text` keeps its signature and routes to it.
  - New `extract_rule_id()` — token-free regex detection of a leading rule/section header
    (`Rule 12`, `Rules 12(3)`, `Section 5.3`, `5.3`, `Annexure II`, …), returns `None` if absent.
- **`app/rag/system.py`**
  - `ingest(..., rebuild: bool = False)`: idempotent by default (skips already-indexed
    chunks); `rebuild=True` calls `store.reset()` first. Response now includes `skipped`.
    Chunk `rule_id` = detected header, else stable `"{source}#chunk-{n}"` fallback.
  - `check()` threads `rule_id` into each `retrieved_rules` dict (populates
    `schemas.RuleReference.rule_id`).
  - Threshold plumbed from the **`MIN_SCORE`** env var (default `0.0`). See Settings note.

## Done-when verification (offline, no keys, deterministic fake embeddings)
`ruff check` → **All checks passed!** ; `ruff format --check .` → **19 files already formatted** ;
`python -c "import app.main"` → **import app.main OK**.

Inline `python - <<PY` demo output (sentence-aware ingest → cosine store):
```
1) chunk_text -> 3 chunks; each ends at a sentence boundary:
      'Rule 12. The front setback shall be 3.0 metres.'
      'The front setback shall be 3.0 metres. The rear setback shall be 2.0 metres.'
      'The rear setback shall be 2.0 metres. Parking of one car per dwelling is mandatory.'
2) idempotent ingest: size after 1st=3, after 2nd(re-run)=3     # re-run adds 0
3) cosine scores (higher=better), best-first:
     +0.8660  kbr#1
     +0.5774  kbr#2
     +0.0000  kbr#3
   threshold=0.95 -> 0 hits; unrelated query @0.5 -> 0 hits
DONE-WHEN CHECKS: ALL PASS
```
Also verified offline: `extract_rule_id` over 8 cases (incl. `8.1.2`, `Annexure II`, no-header →
`None`); end-to-end `RAGSystem.ingest` (header-detected `rule_id` present in metadata) and
`check()` (violations parsed, `rule_id` in `retrieved_rules`); persistence round-trip + `reset()`.
Pydantic compat: `IngestResponse` tolerates the new `skipped` key; `ComplianceResponse` accepts
`rule_id` in retrieved rules.

## Settings / env notes for the coordinator
- **Promote `MIN_SCORE` to `config.Settings`** (spec item 3). I did *not* edit `config.py`
  (owned elsewhere). It is read in `app/rag/system.py::_default_score_threshold()` via
  `os.getenv("MIN_SCORE")`, default `0.0` (keep all non-negative-similarity hits). Once you add a
  `min_score: float = 0.0` Settings field, swap the body of `_default_score_threshold()` to
  `return get_settings().min_score`.
- **Index semantics changed**: any pre-existing `data/index/rules.faiss` from the old
  `IndexFlatL2` code is versioned-out (auto-rebuilt on next ingest). Users should run
  `POST /api/ingest` once (or the coordinator may add a `rebuild` request field to the
  `/ingest` endpoint — currently `rebuild` is only reachable programmatically, since routes/
  schemas are out of my scope).

## Integration risks / notes for other agents
- **agent-2 (graph/llm)**: `retrieved` tuples are still `(text, meta, score)`; score is now
  cosine (higher=better). `graph.retrieve` / `format_rules_for_prompt` / `_parse_violations`
  are untouched and keep working; the empty-index → `insufficient` short-circuit is preserved.
- **`meta` now includes `rule_id` and `sha256`.** `format_rules_for_prompt` already prefers
  `rule_id` (falls back to `chunk`), so prompt citations improve automatically.
- Threshold default `0.0` is permissive (only drops negative-cosine hits), so default retrieval
  behaviour is unchanged; tightening is opt-in via `MIN_SCORE`.
- No changes to endpoints, async, caching, OCR, auth, or tests — left to their owners.
