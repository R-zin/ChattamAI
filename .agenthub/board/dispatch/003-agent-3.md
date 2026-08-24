---
author: coordinator
channel: dispatch
agent: agent-3
task: "Phase 2 — KBR corpus downloader + vendored sample"
files: ["scripts/fetch_kbr.py", "data/kbr/sample_kbr_excerpt.txt"]
---
# Agent-3 — Runnable KBR corpus (downloader + sample)

You are agent-3 in AgentHub ensemble session `20260802-121531`. Repo: ChattamAI RAG
(FastAPI + LangGraph + FAISS + OpenAI embeddings + Claude). Read `README.md`, `plan.md`, and
`app/rag/ingestion.py` (the loader/chunker you must be compatible with) first.

## CRITICAL shared constraints (all agents follow these)
- **Python 3.9 compatible** (dev 3.9.6), CI 3.12. Keep `from __future__ import annotations`.
- **Verifiability / offline-safe**: the downloader must NEVER hit the network at import or
  unless explicitly invoked. The vendored sample must be a real, readable text excerpt the
  pipeline can ingest fully offline. No network in your verification.
- Ruff-clean (`ruff check`, `ruff format --check`), keep docstrings, 88 cols. Commit often.

## YOUR files (create these; do not edit other files)
- `scripts/fetch_kbr.py`   — CLI downloader (new file; create `scripts/` dir)
- `data/kbr/sample_kbr_excerpt.txt` — a labeled, representative KBR sample excerpt

Do NOT edit `app/config.py`, `app/main.py`, or any `app/rag/*`. If you want a configurable
source URL list, read it from env (`KBR_SOURCE_URLS`, comma-separated) with a documented
placeholder default, and note it for the coordinator to wire into `Settings` later.

## What to implement
1. **`scripts/fetch_kbr.py`** runnable as `python -m scripts.fetch_kbr`:
   - Reads one or more source URLs from `KBR_SOURCE_URLS` (comma-separated) or CLI
     `--url` args. Do not hardcode a single brittle URL.
   - Downloads each with a short timeout and a max-size cap; saves into `KBR_DATA_DIR`
     (default `./data/kbr`). Handles PDF and HTML/plain-text sources (for HTML, strip tags to
     text with a tiny dependency-free parser). Uses only `urllib`/`html.parser` (no new deps).
   - Records provenance: for each saved doc, write/append a small `.provenance.json` (source
     URL, fetched-at ISO timestamp, bytes) so chunk metadata can later cite origin.
   - Optionally `--ingest` calls into the app to build the index after download (guard it so it
     does not run at import, and degrade gracefully without API keys).
   - Clear, actionable errors when a source is unreachable.
2. **`data/kbr/sample_kbr_excerpt.txt`**: a clearly-labeled SAMPLE/SUBSET of Kerala Building
   Rules covering the regulated parameters the prompts extract — plot area, built-up area, FSI,
   number of floors, building height, front/rear/side setbacks, road width, parking, occupancy
   type, and a fire-safety/staircase note. Use plausible KBR-style section numbering
   (e.g. "Rule 5 ...", "5.3 Setbacks", "11.2 Parking") so the rule-id extraction works. This is
   the deterministic fixture other agents/tests rely on — make values internally consistent.

## Done when
- `ruff check`/`ruff format --check` pass on your files.
- `python -c "import scripts.fetch_kbr"` works offline.
- Show (offline) that `app.rag.ingestion.load_kbr_documents` + `chunk_text` can load and chunk
  `sample_kbr_excerpt.txt` (e.g. an inline script printing chunk count + a sample rule_id).
- `python -m scripts.fetch_kbr --help` prints usage. Do not actually download during your run.

Write your summary to `.agenthub/board/results/agent-3-result.md`. Then exit.
