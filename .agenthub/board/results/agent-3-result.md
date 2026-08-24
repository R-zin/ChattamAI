---
author: agent-3
channel: results
session: 20260802-121531
task: "Phase 2 — KBR corpus downloader + vendored sample"
status: done
branch: hub/20260802-121531/agent-3/attempt-1
base: 58af064 (feature/optimized-rag tip)
commit: bbdc098
---

# Agent-3 result — Runnable KBR corpus (downloader + sample)

## Branch
All work is committed on **`hub/20260802-121531/agent-3/attempt-1`** (branched
off `58af064`, the Phase-0 / `feature/optimized-rag` base, per the coordinator's
branch-name correction). Single commit `bbdc098`. Working tree clean; `app/`
modules untouched. Did not push, did not open a PR.

## Files created (new only; no existing files edited)
- `scripts/fetch_kbr.py` — config-URL downloader CLI (434 lines).
- `scripts/__init__.py` — package marker so `python -m scripts.fetch_kbr` works
  (added; not in the dispatch's file list but required for the `-m` invocation).
- `data/kbr/sample_kbr_excerpt.txt` — labeled SAMPLE/SUBSET KBR excerpt (6495 bytes).

## Note on `.agenthub` location
The dispatch/results board lives in the MAIN repo checkout at
`$MAIN/.agenthub/...` and is gitignored (`.gitignore` has `.agenthub/`), so it is
NOT visible inside individual worktrees. I was sandboxed to the worktree and
could not write to the shared-checkout board directly; this file is written at
the same relative path inside my worktree.

## What was implemented

### scripts/fetch_kbr.py
- Runs as `python -m scripts.fetch_kbr`. Source URLs come from `--url`
  (repeatable, also accepts comma-separated) OR the `KBR_SOURCE_URLS` env var
  (comma-separated). No hardcoded/brittle single URL; default list is empty and
  it exits with a clear "no URLs provided" message + usage hint (exit code 2).
- Per-request timeout (`--timeout` / `KBR_FETCH_TIMEOUT`, default 15s) and a
  max-bytes cap (`--max-bytes` / `KBR_FETCH_MAX_BYTES`, default 20 MiB). Larger
  responses are truncated and flagged in provenance.
- Handles PDF (kept as raw bytes, `.pdf`) and HTML/plain-text (`.txt`); HTML is
  converted to readable text with a tiny dependency-free `html.parser` subclass
  that drops script/style/head content and inserts line breaks around block tags.
- **Provenance**: for each saved doc it writes `<name>.provenance.json` with
  `source_url`, `fetched_at` (ISO-8601 UTC), `bytes`, `content_type`,
  `file_name`, `truncated`. Sidecars use a non-loaded suffix so
  `load_kbr_documents` (only `.txt/.md/.text/.pdf`) ignores them.
- Stdlib only: `urllib.request` + `html.parser`. No new dependencies.
- `--ingest` optionally rebuilds the FAISS index via `app.rag.system.RAGSystem`.
  It is lazy-imported inside the function, never runs at import, and degrades
  gracefully (warns + returns 0) when `OPENAI_API_KEY` is unset.
- Clear errors: HTTP/URL/OS failures are wrapped in `RuntimeError` with the URL
  and reason; the run continues past individual failures and reports a summary.

### data/kbr/sample_kbr_excerpt.txt
Clearly-labeled SAMPLE/SUBSET header (states it is a deterministic fixture, not
the gazetted rules). Covers every regulated parameter the extraction prompt
(SYSTEM_EXTRACT) asks for, with KBR-style numbering and internally consistent
values:
- Plot area 240.0 m² (and 3-cent minimum note); built-up area ≤ 480.0 m².
- Rule 7.1 FSI = 2.0 (requires road width ≥ 7.0 m); 7.2 worked example
  240.0 × 2.0 = 480.0 m².
- Rule 7.3 max 3 floors (480.0 / 3 = 160.0 m²/floor); Rule 7.4 max height 11.0 m.
- 5.3 setbacks: front 3.0 m, rear 2.0 m, side 1.5 m (1.0 m relaxed); 5.3.4 road
  width definition + 7.0 m for full FSI.
- 11.2 parking: 1 space ≥ 12.5 m² per unit > 150.0 m²; open parking not in FSI.
- Rule 12 occupancy: Group A1 residential.
- Rule 16 fire-safety/staircase: staircase ≥ 1.2 m for >2 floors, second
  staircase for >3 floors, travel distance ≤ 22.5 m, with a SAMPLE caveat.

## Offline verification performed
- `ruff check .` and `ruff format --check .` → clean repo-wide (21 files).
- `python -c "import scripts.fetch_kbr"` → OK offline.
- `python -m scripts.fetch_kbr --help` → prints usage, exit 0, offline.
- No-network-at-import: guarded `urllib.request.urlopen`; after import + all unit
  work, `urlopen` call count stayed 0. (A cruder socket-stub test tripped Python
  3.9's `ssl` module import — a test artifact, not a code issue; the urlopen-guard
  proof is the valid one.)
- Load/chunk demo (`load_kbr_documents` + `chunk_text`, offline): loaded 1 doc
  from `KBR_DATA_DIR`, produced 7 chunks, sample rule_id = "Rule 5"; all 12
  regulated-parameter keywords present in the excerpt.
- Transform unit tests (temp dir, fake `urlopen`): html→text strips tags/scripts
  and keeps content; PDF passthrough; plain-text passthrough; truncation to cap
  sets `truncated: true`; provenance has all expected keys; filename derivation
  correct for pdf/html/bare-host URLs; unreachable source raises a clear error.
- `--ingest` without `OPENAI_API_KEY` → warns and skips (no crash, exit 0).
- No real network was used at any point in verification (fake `urlopen` /
  non-routable host only).

## Coordinator notes / hand-off
- **Env vars used (please wire into `Settings` later, all optional with defaults):**
  - `KBR_SOURCE_URLS` — comma-separated source URLs (placeholder default empty).
  - `KBR_DATA_DIR` — output dir; already mirrored in `Settings.kbr_data_dir`.
  - `KBR_FETCH_TIMEOUT` (15s), `KBR_FETCH_MAX_BYTES` (20 MiB) — new, not yet in Settings.
  - `--ingest` reads `OPENAI_API_KEY` to decide whether to build the index.
- Ingest metadata currently sets `source` + `chunk` only; `rule_id` falls back to
  the chunk index (see `prompts.format_rules_for_prompt`). The sample's KBR-style
  numbering lets Claude cite `rule_reference` directly from chunk text. If a
  future agent wants a real `rule_id` in metadata, the `*.provenance.json`
  sidecars provide origin to cite, and a regex like
  `\b(Rule\s+\d+(\.\d+)*|\d+\.\d+(\.\d+)*)\b` matches the ids used in the excerpt.
- `scripts/__init__.py` was added as a package marker; it is the only file beyond
  the two named in the dispatch.
