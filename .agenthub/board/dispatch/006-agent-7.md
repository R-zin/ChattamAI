---
author: coordinator
channel: dispatch
agent: agent-7
task: "Phase 3 — OCR pipeline for image/image-PDF building plans (layout-free v1)"
files: ["app/rag/ocr.py", "app/rag/ingestion.py", "app/routes/rag.py", "app/config.py", "app/schemas.py (only if truly needed)", "requirements.txt", ".env.example"]
---

# Agent-7 — OCR pipeline (Phase 3)

You are agent-7 in AgentHub ensemble session `20260802-121531`. Repo: ChattamAI RAG
(FastAPI + LangGraph + FAISS + OpenAI embeddings + Claude via local proxy). Read
`README.md`, `plan.md` (Phase 3), `.agenthub/board/dispatch/001-agent-1.md` context,
and inspect the integrated `feature/optimized-rag` tree before editing.

## CRITICAL shared constraints
- **Python 3.9 compatible** (dev 3.9.6), CI 3.12. Use `from __future__ import
  annotations` in modules; **NO PEP 604 `X | None` in runtime positions / pydantic
  models** (use `typing.Optional`). Keep ruff-clean (`ruff check` + `ruff format --check`, 88 cols).
- **Offline-verifiable**: OCR is lazily imported + feature-flagged so a box WITHOUT
  Tesseract still boots and passes the existing offline tests. Never require
  network or any API key at import time.
- Do NOT touch `tests/` (agent-5 owns it and is reconciling concurrently). Do NOT
  edit `app/services/*`, `app/routes/auth.py`, or unrelated RAG modules beyond the
  minimal `load_plan_text` hook below.

## Get the tree
Branch off the LATEST `feature/optimized-rag` (tip `9e899a8` — includes my Settings
polish). Create branch `hub/20260802-121531/agent-7/attempt-1`. Commit there only;
no PR/push. (Note the AgentsDK worktree dir is auto-named; ensure your commits land
on the named `hub/...` branch so the DAG tools can track it.)

## Goal (from approved plan)
Let users upload an image or image-only PDF floor plan and get a compliance check.
This is **layout-free v1**: turn the plan image into plain text via OCR and feed the
existing `extract_facts` node unchanged. The interface is the pre-existing
`Path -> str` seam — do not change `RAGSystem.check`'s contract.

## Implement

1. **`app/rag/ocr.py`** (new, pure module; no FastAPI/DB imports):
   - `ocr_available() -> bool` — True iff OCR deps (`pytesseract`/`pillow`, and
     `PyMuPDF` for PDFs) import AND the Tesseract binary resolves. Used for a clear
     503 when OCR is requested but unavailable.
   - `image_to_text(path: Path) -> str` — open with PIL, optionally upscale/
     grayscale auto-threshold for legibility, run `pytesseract.image_to_string`.
   - `pdf_images_to_text(path: Path) -> str` — render each page via `PyMuPDF`
     (`fitz`) to a raster pixmap at ~200-300 DPI, run Tesseract per page, join.
   - `normalize_ocr_text(text: str) -> str` — collapse runs of whitespace, fix
     common OCR confusions conservatively (e.g. stray `|`/`l` inside digit runs
     when unambiguous), split glued decimal points, strip page junk. Keep it
     conservative and unit-tested by the caller contract (idempotent, offline).
   - Lazy-import the OCR libs INSIDE the functions (not module top) so importing
     this module never fails when deps are absent.

2. **`app/rag/ingestion.py`** — extend `load_plan_text` so image suffixes
   (`.png/.jpg/.jpeg/.tiff/.tif/.bmp/.webp`) and, when `--ocr` is implied, image
   PDFs route to `ocr.image_to_text` / `ocr.pdf_images_to_text` **with a flag**:
   only when `get_settings().ocr_enabled` is True; otherwise raise a clear
   ValueError telling the user OCR is disabled/unsupported. Keep `_read_pdf`
   (text PDFs) as the default for `.pdf`. Keep the existing `.txt/.md` behaviour
   byte-identical.

3. **`app/config.py`** — add `ocr_enabled: bool = os.getenv("OCR_ENABLED", "")...`
   (default False) under a clearly-labelled "OCR" section, mirroring the style of
   the existing fields.

4. **`app/routes/rag.py` — `POST /api/check/plan-ocr`** (opt-in OCR endpoint):
   - Accept an image (`.png/.jpg/.jpeg/.tiff/.tif/.bmp/.webp`) or image-only `.pdf`
     upload. Reject other extensions with 415 (mirror `check_upload`'s message).
   - If `get_settings().ocr_enabled` is False → 503 "OCR is disabled" detail.
   - Else 200 `ComplianceResponse` by running the existing `RAGSystem.check_plan_file`
     on the OCR-normalised text file (reuses the same `Path -> str` seam).
   - Gate it with `dependencies=[Depends(require_auth)]` exactly like `/api/check`
     so it matches the auth posture of the other paid/mutating routes (opt-in off).

5. **`requirements.txt`** — add under a "# OCR (feature-flagged; see plan.md Phase 3)"
   comment: `pillow`, `pytesseract`, `PyMuPDF`. Pin to versions that support BOTH
   Python 3.9 and 3.12 (verify; e.g. `PyMuPDF>=1.24`, `pillow>=10,<12`,
   `pytesseract>=0.3.10`). Note in a comment that the **Tesseract binary** is a
   system requirement (`brew install tesseract` / `apt install tesseract-ocr`).

6. **`.env.example`** — append `OCR_ENABLED=` (False by default) with a comment that
   Tesseract must be installed for image plans.

## Done when
- `python -c "import app.main"` OK on 3.9 with OCR deps **absent** (feature-flagged import path).
- With deps installed: `ocr_available()` reflects Tesseract presence; a tiny offline
  smoke that exercises `normalize_ocr_text` on a crafted string passes (you may add a
  scratch check under `/tmp`, but do NOT add test files — that's agent-5/Wave-3).
- `ruff check` + `ruff format --check` clean on every file you touched.
- The existing offline suite still passes where it touched your files (load_plan_text
  text/PDF unchanged; image suffixes only gated behind the flag).
- Write `.agenthub/board/results/agent-7-result.md` and reply with: files changed,
  pins chosen (with 3.9/3.12 evidence), the endpoint contract, how lazy-import keeps
  boot safe, and any risks. Then exit.
