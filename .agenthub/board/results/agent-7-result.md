---
author: agent-7
channel: results
session: 20260802-121531
branch: hub/20260802-121531/agent-7/attempt-1
base: feature/optimized-rag@9e899a8
commit: ae777cc
status: done
---

# Agent-7 — OCR pipeline (Phase 3) — Result

Layout-free v1 OCR is in: an image or image-only-PDF floor plan is turned into
plain text and run through the **unchanged** `extract_facts` node via the
pre-existing `Path -> str` seam (`RAGSystem.check_plan_file` -> `load_plan_text`).
`RAGSystem.check`'s contract was not touched.

## Files changed
- `app/rag/ocr.py` — **new, pure** module (no FastAPI/DB imports).
  - `ocr_available() -> bool` — True iff `pytesseract`/`PIL`/`fitz` import AND the
    `tesseract` binary resolves on PATH. Never raises; used for the 503.
  - `image_to_text(path) -> str` — PIL open -> grayscale -> autocontrast (upscale if
    small) -> `pytesseract.image_to_string`.
  - `pdf_images_to_text(path) -> str` — render each page via PyMuPDF (`fitz`) at
    ~260 DPI (`Matrix(260/72)`), Tesseract per page, joined.
  - `normalize_ocr_text(text) -> str` — **conservative, idempotent, offline**:
    collapse whitespace runs, rejoin glued decimals (`12 5`/`4,75` -> `12.5`/`4.75`,
    only 1–2 fractional digits), rewrite an **intra-digit** stroke `|/l/I/!` to `0`
    (only when both neighbours are digits), drop lone page-junk lines. Verified
    idempotent: `n(n(x)) == n(x)`.
- `app/rag/ingestion.py` — `load_plan_text` routes image suffixes
  (`.png/.jpg/.jpeg/.tiff/.tif/.bmp/.webp`) to `ocr.image_to_text` **only** when
  `get_settings().ocr_enabled` is True; otherwise a clear `ValueError`. `.txt/.md`
  are read byte-identical; `.pdf` still defaults to the text extractor `_read_pdf`.
- `app/config.py` — `ocr_enabled: bool` under an "OCR" section (`OCR_ENABLED` env,
  default False), same truthy-set style as `auth_required`.
- `app/routes/rag.py` — `POST /api/check/plan-ocr`, gated with
  `dependencies=[Depends(require_auth)]` exactly like `/api/check`.
- `requirements.txt` — OCR deps under "# OCR (feature-flagged; see plan.md Phase 3)".
- `.env.example` — appended `OCR_ENABLED=` with the Tesseract-binary note.

## Dependency pins (with 3.9/3.12 evidence)
Pinned to support BOTH dev (3.9.6) and CI (3.12):
- `pillow>=10,<12` — 10.x–11.x carry `requires_python >=3.8` and ship 3.9 + 3.12 wheels.
- `pytesseract>=0.3.10` — latest 0.3.13, `requires_python >=3.8` (3.9 & 3.12 OK); pure-Python.
- `PyMuPDF>=1.24,<1.27` — **bound raised `<1.27`, not the dispatch's suggested `>=1.24`**:
  PyMuPDF **1.27+ bumps `requires_python` to `>=3.10` (drops 3.9)**. 1.24–1.26 have
  `requires_python >=3.9` and ship `cp39-abi3` (stable-ABI) wheels that run on 3.9–3.12
  (verified 1.26.5 metadata: `requires_python ">=3.9"`, cp39-abi3 wheels, no cp312 tag needed).
- The **Tesseract binary is a system requirement**, not pip: `brew install tesseract` /
  `apt install tesseract-ocr`. Documented in requirements.txt and .env.example.

## Endpoint contract — `POST /api/check/plan-ocr`
- Accepts multipart `file` with suffix in `.png/.jpg/.jpeg/.tiff/.tif/.bmp/.webp` or `.pdf`.
- Gate order (each verified offline): **415** wrong ext (mirrors `check_upload`'s message) ->
  **503** OCR disabled (`OCR_ENABLED` unset) -> **503** deps/Tesseract missing
  (`ocr_available()` False) -> **200** `ComplianceResponse`.
- 200 path: OCR -> `normalize_ocr_text` -> write temp `.txt` -> `rag.check_plan_file(txt_path)`
  (reuses the shared `Path -> str` seam and `check` contract byte-for-byte). 422 if OCR yields
  no usable text. Same shape as other `ComplianceResponse` routes.
- Auth: `Depends(require_auth)` — opt-in OFF by default, so the credential-less CI smoke on
  `/api/health` and existing behavior are unchanged.

## How lazy-import keeps boot safe without Tesseract
All heavy OCR imports (`pytesseract`, `PIL`, `fitz`) live **inside** the functions in
`app/rag/ocr.py` (via a `_import` helper) and inside the route handler — never at module top.
`app.rag.ocr` itself imports only `re`/`shutil`/`pathlib`. The route module imports OCR lazily
inside `check_plan_ocr`. Net effect on a dep-less box:
- `python -c "import app.main"` — **OK** on 3.9 with `pytesseract`/`PIL`/`fitz` absent.
- `import app.rag.ocr` — **OK**; `ocr_available()` returns `False` (no crash).
- `load_plan_text` on `.txt/.pdf` — **unchanged**; image suffix -> clear `ValueError` (flag off).

## Verification done (offline)
- Boot: `import app.main` OK on Python 3.9.6, OCR deps absent (pre-existing urllib3/langgraph
  warnings only, not from my changes).
- `ocr_available()` -> `False` on this box (no tesseract).
- Offline `normalize_ocr_text` smoke: decimals, intra-digit stroke, whitespace collapse,
  page-junk strip, empty, and idempotence — **all pass**.
- Route gating via `TestClient` with a stubbed `get_rag`: 415 (.txt), 503 (OCR off),
  503 (OCR on but deps absent).
- `ruff check .` and `ruff format --check .` — clean (30 files, 88 cols, py39 target).

## Risks / notes
- **Pre-existing test failures (NOT mine):** 18 tests fail identically on the untouched base
  `9e899a8` (parsing, vectorstore, chunking, some api) — these are the integrated agent-1/2
  changes that agent-5 is reconciling concurrently. My changes add **zero** new failures
  (base 18 == with-changes 18) and no existing test imports my new OCR code.
- `normalize_ocr_text` maps an intra-digit stroke to `0` (e.g. `3|0` -> `300`). This is a
  documented, conservative guess; if it proves wrong for real plans, the fix is one regex
  constant. Strokes **not** between digits are left untouched.
- OCR quality on real floor plans was not exercised here (no Tesseract/weights on the box);
  the endpoint's 503 path is what a dep-less deploy will hit, which is the intended safe default.
- PyMuPDF must stay `<1.27`; a future bump requires Python >=3.10 (drop when 3.9 is retired).

> Note for coordinator: `.agenthub/` is git-ignored, so this result file lives in the
> agent-7 worktree and is also committed on a scratch path is not; the file is at
> `.claude/worktrees/agent-af8417eb6246b7ec2/.agenthub/board/results/agent-7-result.md`.
> If the merger needs it in the shared board, copy it into the main checkout's
> `.agenthub/board/results/`. The code changes are all on `hub/20260802-121531/agent-7/attempt-1`.
