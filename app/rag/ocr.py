"""Layout-free OCR for image / image-PDF building plans (plan.md Phase 3).

This module turns a floor-plan image (or an image-only PDF) into plain text so it
can flow through the *existing* ``extract_facts`` node unchanged — the pre-existing
``Path -> str`` seam (:func:`app.rag.ingestion.load_plan_text`).

The default path stays deliberately "layout-free" (:func:`image_to_text` /
:func:`pdf_images_to_text`): we recover words, not geometry, and that behaviour is
unchanged. On top of it sits an OPTIONAL geometry-aware pass
(:func:`image_to_layout_text`) that uses Tesseract TSV output to recover *where*
each word sits (``left``/``top``/``width``/``height``/``conf``), group words back
into lines and columns, and render simple aligned "label: value" table rows as
``key: value`` hints so dimensional/tabular data (setbacks, heights, FSI tables)
survives OCR in reading order. The layout pass degrades gracefully: a missing
binary, an import failure, or malformed TSV all fall back to the words-only text
rather than ever crashing OCR.

Dependency / boot-safety contract (see the agent-7 dispatch): the heavy OCR
libraries — Pillow, pytesseract, and PyMuPDF — plus the system *Tesseract binary*
are FEATURE-FLAGGED and lazily imported INSIDE the functions below. Importing this
module therefore never fails on a box without them; only calling the OCR functions
does. Use :func:`ocr_available` to give callers a clear 503 before that happens.

Two engines, chosen by ``Settings.ocr_provider`` (``OCR_PROVIDER``):

* ``nim`` — PaddleOCR via NVIDIA NIM (:mod:`app.rag.paddle_ocr`). Needs Pillow +
  PyMuPDF and an NVIDIA API key (or a self-hosted NIM URL); no Tesseract. It
  always returns geometry, so both the plain and layout entry points produce
  layout-aware text. If the NIM call fails and Tesseract is installed, OCR falls
  back to Tesseract and logs a warning.
* ``tesseract`` — local pytesseract. Requires the ``tesseract`` binary at runtime
  (``brew install tesseract`` / ``apt install tesseract-ocr``); it is NOT a pip
  dependency.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Image suffixes we can OCR directly with Pillow + Tesseract.
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}

# Render image-PDF pages at ~260 DPI: high enough for small dimension text,
# low enough to stay fast and memory-light.
_PDF_RENDER_DPI = 260

# One recognised word plus its bounding box, as captured from Tesseract TSV data.
# Keys mirror the TSV columns: ``text`` (the word), ``left``/``top``/``width``/
# ``height`` (pixel box) and ``conf`` (recognition confidence, 0-100 or -1).
WordBox = Dict[str, object]

# --- Geometry / layout tuning constants -------------------------------------------
# Two words sit on the SAME line when their vertical centres differ by no more than
# this fraction of the average word height. Generous enough to absorb OCR jitter on
# a scanned rule line, tight enough to keep adjacent FSI/setback rows distinct.
_LINE_Y_TOLERANCE = 0.6
# A line is rendered as a ``label: value`` pair only when it splits into exactly two
# horizontal clusters whose gap is at least this many times the average word width.
# This is what keeps "front setback    1.8m" attached while leaving prose alone.
_COLUMN_GAP_FACTOR = 1.8
# Drop empty / whitespace-only TSV rows and sub-noise confidence words before any
# geometry math; ``-1`` / ``conf < 0`` marks structural (non-word) TSV rows.
_MIN_CONFIDENCE = 0.0

# A digit run that may contain a single OCR mis-read of a vertical stroke: a ``|``,
# ``l``, ``I``, or ``!`` sitting between digits. We only rewrite when BOTH neighbours
# are digits so genuine words ("1l bottle", "A|B") are untouched.
_DIGIT_RUN_BAR_RE = re.compile(r"(?<=\d)[|lI!](?=\d)")

# A decimal point OCR'd as a stray space or comma inside a number: "12 5" or "12,5"
# that clearly read as one measurement. Conservative: only glue "<digit><sep><digit>"
# when the right-hand group has 1-3 digits (a fractional part), never joining across
# a thousands-style grouping we might be misreading. This is intentionally narrow.
_GLUED_DECIMAL_RE = re.compile(r"\b(\d+)[, ](\d{1,2})\b")

# Whitespace collapse: runs of spaces/tabs/newlines -> the single most-intentful
# separator is preserved by first normalising newlines, then spaces.
_MULTI_NEWLINE_RE = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)+")
_WS_RUN_RE = re.compile(r"[ \t]{2,}")


logger = logging.getLogger(__name__)


def _provider() -> str:
    """The configured OCR engine: ``"nim"`` (PaddleOCR) or ``"tesseract"``."""
    from app.config import get_settings

    return (get_settings().ocr_provider or "tesseract").strip().lower()


def _import(name: str):
    """Import an OCR dependency lazily, raising a clear error if it is absent."""
    try:
        module = __import__(name)
    except ImportError as exc:  # pragma: no cover - depends on the host box
        raise RuntimeError(
            f"OCR dependency '{name}' is not installed. Install the OCR extras "
            "(pillow / pytesseract / PyMuPDF) and the system 'tesseract' binary "
            "to check image/image-PDF plans, or disable OCR."
        ) from exc
    # Dotted names resolve on the top module via getattr.
    for part in name.split(".")[1:]:
        module = getattr(module, part)
    return module


def tesseract_available() -> bool:
    """True iff pytesseract/Pillow/PyMuPDF import and the binary is on PATH."""
    for mod in ("pytesseract", "PIL", "fitz"):
        try:
            __import__(mod)
        except ImportError:
            return False
    return shutil.which("tesseract") is not None


def ocr_unavailable_reason() -> Optional[str]:
    """Why OCR cannot run with the configured engine, or None when it can.

    Never raises; offline and import-safe (no network call is made).
    """
    provider = _provider()
    if provider == "nim":
        for mod in ("PIL", "fitz"):
            try:
                __import__(mod)
            except ImportError:
                return (
                    "OCR is unavailable: Pillow and PyMuPDF are required for PaddleOCR."
                )
        from app.config import get_settings

        settings = get_settings()
        if (
            "api.nvidia.com" in (settings.paddleocr_url or "")
            and not settings.nvidia_api_key
        ):
            return "PaddleOCR (OCR_PROVIDER=nim) needs NVIDIA_API_KEY for the hosted NIM endpoint."
        return None
    if provider == "tesseract":
        if tesseract_available():
            return None
        return (
            "OCR is unavailable on this server (missing Pillow/pytesseract/"
            "PyMuPDF or the Tesseract binary)."
        )
    return f"Unknown OCR_PROVIDER '{provider}' (use 'nim' or 'tesseract')."


def ocr_available() -> bool:
    """Return True iff OCR can actually run with the configured engine.

    Used to answer a clear 503 when OCR is requested but unavailable. Never raises;
    offline and import-safe.
    """
    return ocr_unavailable_reason() is None


def _paddle_boxes(img) -> List["WordBox"]:
    from app.rag.paddle_ocr import client_from_settings

    return client_from_settings().image_word_boxes(img)


def _with_tesseract_fallback(nim_call, tesseract_call):
    """Run the PaddleOCR path; on failure fall back to Tesseract when installed."""
    try:
        return nim_call()
    except Exception as exc:
        if not tesseract_available():
            raise
        logger.warning("PaddleOCR failed (%s); falling back to Tesseract", exc)
        return tesseract_call()


def _paddle_image_text(path: Path) -> str:
    gray = _load_gray_image(path)
    try:
        return word_boxes_to_text(_paddle_boxes(gray))
    finally:
        gray.close()


def _paddle_pdf_text(path: Path) -> str:
    fitz = _import("fitz")
    Image = _import("PIL.Image")

    import io

    pages = []
    zoom = _PDF_RENDER_DPI / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(str(path)) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
            try:
                pages.append(word_boxes_to_text(_paddle_boxes(img)))
            finally:
                img.close()
    return "\n".join(pages)


def _load_gray_image(path: Path):
    """Open ``path`` and normalise it for Tesseract (shared by text + layout paths).

    Grayscale, upscale if small so tiny dimension labels resolve, then a light
    autocontrast to even out illumination and harden glyphs. Returns the open
    grayscale image; the caller owns closing it.
    """
    Image = _import("PIL.Image")
    ImageOps = _import("PIL.ImageOps")

    img = Image.open(str(path))
    gray = img.convert("L")
    # Upscale small scans so tiny dimension labels resolve for Tesseract.
    if max(gray.size) < 1500:
        ratio = 1500 / max(gray.size)
        gray = gray.resize(
            (int(gray.width * ratio), int(gray.height * ratio)),
            Image.LANCZOS,
        )
    # Even out illumination and binarise lightly for cleaner glyphs.
    gray = ImageOps.autocontrast(gray)
    return gray


def image_to_text(path: Path) -> str:
    """OCR a single image file to text.

    Opens with Pillow, normalises for legibility (grayscale, light autocontrast,
    upscale if the image is small), then runs ``pytesseract.image_to_string``.
    ``path`` may be anything Pillow can open (see :data:`IMAGE_EXTS`).
    With ``OCR_PROVIDER=nim`` the PaddleOCR NIM is used instead.
    """
    if _provider() == "nim":
        return _with_tesseract_fallback(
            lambda: _paddle_image_text(path), lambda: _tesseract_image_text(path)
        )
    return _tesseract_image_text(path)


def _tesseract_image_text(path: Path) -> str:
    pytesseract = _import("pytesseract")

    gray = _load_gray_image(path)
    try:
        text = pytesseract.image_to_string(gray)
    finally:
        gray.close()
    return text


def pdf_images_to_text(path: Path) -> str:
    """OCR every page of an image-only PDF and join the results.

    Renders each page via PyMuPDF (``fitz``) to a raster pixmap at
    ``_PDF_RENDER_DPI`` and runs Tesseract per page. Text PDFs should use
    ``ingestion._read_pdf`` instead; this is for scans / image-only exports.
    With ``OCR_PROVIDER=nim`` each page goes to the PaddleOCR NIM instead.
    """
    if _provider() == "nim":
        return _with_tesseract_fallback(
            lambda: _paddle_pdf_text(path), lambda: _tesseract_pdf_text(path)
        )
    return _tesseract_pdf_text(path)


def _tesseract_pdf_text(path: Path) -> str:
    fitz = _import("fitz")
    pytesseract = _import("pytesseract")
    Image = _import("PIL.Image")

    import io  # local: only needed on this path

    pages = []
    zoom = _PDF_RENDER_DPI / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(str(path)) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
            img = _import("PIL.ImageOps").autocontrast(img)
            pages.append(pytesseract.image_to_string(img))
    return "\n".join(pages)


# ---------------------------------------------------------------------------
# Geometry-aware extraction (optional, additive — image_to_text stays default)
# ---------------------------------------------------------------------------
def tsv_to_word_boxes(data: Dict[str, List[object]]) -> List[WordBox]:
    """Turn a Tesseract TSV dict into flat word boxes, dropping junk rows.

    ``data`` is the column-oriented dict that ``pytesseract.image_to_data``
    returns (``Output.DICT``): parallel lists keyed ``text``, ``left``, ``top``,
    ``width``, ``height``, ``conf``. Tesseract also emits structural rows
    (page/block/paragraph/line headers) that carry an empty ``text`` and a
    negative ``conf``; those, plus sub-noise words and non-string text, are
    filtered out. Anything unreadable (missing keys, non-numeric geometry) makes
    the whole call return ``[]`` so the caller degrades gracefully.
    """
    if not isinstance(data, dict):
        return []
    try:
        texts = data["text"]
        n = len(texts)
        lefts, tops = data["left"], data["top"]
        widths, heights = data["width"], data["height"]
        confs = data["conf"]
        if not all(len(col) == n for col in (lefts, tops, widths, heights, confs)):
            return []
    except (KeyError, TypeError):
        return []

    boxes: List[WordBox] = []
    for i in range(n):
        word = texts[i]
        if not isinstance(word, str):
            continue
        word = word.strip()
        if not word:
            continue
        try:
            conf = float(confs[i])
            left = int(lefts[i])
            top = int(tops[i])
            width = int(widths[i])
            height = int(heights[i])
        except (TypeError, ValueError):
            # A malformed row poisons the geometry; skip it rather than guess.
            continue
        if conf < _MIN_CONFIDENCE:
            # Structural TSV rows (conf == -1) and sub-noise words.
            continue
        boxes.append(
            {
                "text": word,
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "conf": conf,
            }
        )
    return boxes


def _vertical_center(box: WordBox) -> float:
    """Vertical centre of a word box (the robust line-membership signal)."""
    return float(box["top"]) + float(box["height"]) / 2.0


def group_words_into_lines(boxes: List[WordBox]) -> List[List[WordBox]]:
    """Cluster word boxes into horizontal lines (reading-order, top to bottom).

    Greedy sweep sorted by vertical centre: a word joins the open line while its
    centre stays within ``_LINE_Y_TOLERANCE`` of the running line's average word
    height apart from the line's average centre; otherwise it opens a new line.
    Each returned line is itself ordered left-to-right (``left``). Deterministic
    and tolerant of per-word OCR jitter.
    """
    if not boxes:
        return []
    ordered = sorted(boxes, key=lambda b: (_vertical_center(b), float(b["left"])))
    lines: List[List[WordBox]] = []
    for box in ordered:
        center = _vertical_center(box)
        height = float(box["height"])
        if lines:
            current = lines[-1]
            mean_center = sum(_vertical_center(b) for b in current) / len(current)
            mean_height = sum(float(b["height"]) for b in current) / len(current)
            tol = _LINE_Y_TOLERANCE * max(mean_height, height, 1.0)
            if abs(center - mean_center) <= tol:
                current.append(box)
                continue
        lines.append([box])
    # Order each line's words left-to-right so text reconstructs in reading order.
    for line in lines:
        line.sort(key=lambda b: float(b["left"]))
    return lines


def line_to_text(line: List[WordBox]) -> str:
    """Render one line of word boxes as text, preserving column order.

    Words are joined with a single space; a wide horizontal gap (>=
    ``_COLUMN_GAP_FACTOR`` times the average word width) becomes a ``" : "``
    separator, which is what keeps a tabular ``label    value`` row reading as a
    clean ``label: value`` fact for downstream extraction.
    """
    if not line:
        return ""
    pieces = [str(line[0]["text"])]
    widths = [float(b["width"]) for b in line if float(b["width"]) > 0]
    mean_width = sum(widths) / len(widths) if widths else 0.0
    for prev, cur in zip(line, line[1:]):
        gap = float(cur["left"]) - (float(prev["left"]) + float(prev["width"]))
        if mean_width > 0 and gap >= _COLUMN_GAP_FACTOR * mean_width:
            pieces.append(":")  # rendered as "<label> : <value>" after join-tidy
        pieces.append(str(cur["text"]))
    text = " ".join(pieces)
    # Tidy a " :" column separator we just introduced into ": ".
    return text.replace(" : ", ": ")


def word_boxes_to_text(boxes: List[WordBox]) -> str:
    """Reconstruct reading-order text (with table->kv hints) from word boxes.

    Groups into lines, renders each with column gaps preserved, and joins lines
    with newlines. Empty input yields ``""`` so callers degrade cleanly.
    """
    lines = group_words_into_lines(boxes)
    return "\n".join(line_to_text(line) for line in lines if line)


def dataframe_to_word_boxes(df: object) -> List[WordBox]:
    """Adapt a Tesseract ``Output.DATAFRAME`` to word boxes (best-effort).

    Uses pandas' ``to_dict('list')`` and feeds the result through
    :func:`tsv_to_word_boxes` so a single parsing path serves both TSV shapes.
    Assumes ``df`` quacks like a pandas DataFrame; anything else returns ``[]``.
    """
    try:
        data = df.to_dict("list")  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        return []
    return tsv_to_word_boxes(data)


def image_to_layout_text(
    path: Path, fallback_to_plain: bool = True
) -> Tuple[str, Optional[str]]:
    """OCR an image to *layout-aware* text, or fall back to words-only text.

    Returns ``(text, note)``. On the happy path ``note`` is ``None`` and ``text``
    is reading-order text with ``label: value`` table hints. If Tesseract TSV
    output is unavailable (import error, missing binary, empty/degenerate data,
    any exception mid-extraction) and ``fallback_to_plain`` is True, we run the
    plain :func:`image_to_text` path instead and set ``note`` to a short reason —
    OCR NEVER crashes because geometry failed. If ``fallback_to_plain`` is False,
    a hard failure re-raises the original exception.

    With ``OCR_PROVIDER=nim`` PaddleOCR supplies the geometry; if it fails and
    ``fallback_to_plain`` is True, the Tesseract layout pass runs instead (when
    installed) and ``note`` records why.
    """
    if _provider() == "nim":
        try:
            return _paddle_image_text(path), None
        except Exception as exc:
            if not fallback_to_plain or not tesseract_available():
                raise
            logger.warning("PaddleOCR failed (%s); falling back to Tesseract", exc)
            text, note = _tesseract_layout_text(path, fallback_to_plain)
            return text, note or f"paddleocr_failed: {exc}"
    return _tesseract_layout_text(path, fallback_to_plain)


def _tesseract_layout_text(
    path: Path, fallback_to_plain: bool = True
) -> Tuple[str, Optional[str]]:
    try:
        pytesseract = _import("pytesseract")
        Output = _import("pytesseract.Output")
        gray = _load_gray_image(path)
        try:
            try:
                data = pytesseract.image_to_data(gray, output_type=Output.DICT)
            except Exception as exc:  # bad frame, engine hiccup, no binary
                if not fallback_to_plain:
                    raise
                return _plain(path), f"layout_ocr_failed: {exc}"
        finally:
            gray.close()
        boxes = tsv_to_word_boxes(data)
        if not boxes:
            # Degenerate TSV (nothing recognised) — plain string is more useful.
            if not fallback_to_plain:
                raise RuntimeError("no usable word boxes from Tesseract TSV")
            return _plain(path), "layout_ocr_failed: no word boxes"
        return word_boxes_to_text(boxes), None
    except Exception as exc:
        if not fallback_to_plain:
            raise
        try:
            return _plain(path), f"layout_ocr_failed: {exc}"
        except Exception:
            # Even the plain path failed (e.g. Pillow cannot open the file):
            # surface a clear empty result rather than crash the pipeline.
            return "", f"ocr_unavailable: {exc}"


def _plain(path: Path) -> str:
    """Words-only Tesseract fallback for the layout pass.

    Resolved through the module attribute so tests can stub ``image_to_text``.
    """
    if _provider() == "nim":
        return _tesseract_image_text(path)
    return image_to_text(path)


def normalize_ocr_text(text: str) -> str:
    """Conservatively clean raw OCR output before it feeds ``extract_facts``.

    Steps, each deliberately conservative (idempotent, offline, no model):
      * collapse runs of blank lines and intra-line whitespace,
      * rejoin a decimal point OCR'd as a space/comma inside a number
        ("12 5" -> "12.5", "4,75" -> "4.75"),
      * fix an unambiguous vertical stroke inside a digit run ("3|0" -> "30"),
      * strip dangling page-junk lines (a lone page number, form feeds).

    The function is idempotent: ``normalize_ocr_text(normalize_ocr_text(x)) ==
    normalize_ocr_text(x)``. It never invents or deletes whole tokens.
    """
    if not text:
        return ""
    out = text.replace("\r\n", "\n").replace("\r", "\n")
    # Form feeds / page breaks become single blank lines.
    out = out.replace("\f", "\n\n")
    # Unambiguous digit-run fixes first (3|0 -> 30).
    out = _DIGIT_RUN_BAR_RE.sub("0", out)
    # Rejoin glued decimals: "<int><space|comma><1-2 digits>" -> "<int>.<frac>".
    out = _GLUED_DECIMAL_RE.sub(r"\1.\2", out)
    # Collapse horizontal whitespace, then 3+ newlines down to a blank line.
    out = _WS_RUN_RE.sub(" ", out)
    out = _MULTI_NEWLINE_RE.sub("\n\n", out)
    # Drop lines that are pure page junk (a lone number / stray punctuation).
    lines = [ln.strip() for ln in out.split("\n")]
    lines = [ln for ln in lines if ln and not re.fullmatch(r"[\d\-–—|_.]+", ln)]
    return "\n".join(lines).strip()


__all__ = [
    "IMAGE_EXTS",
    "WordBox",
    "ocr_available",
    "ocr_unavailable_reason",
    "tesseract_available",
    "image_to_text",
    "image_to_layout_text",
    "pdf_images_to_text",
    "normalize_ocr_text",
    "tsv_to_word_boxes",
    "dataframe_to_word_boxes",
    "group_words_into_lines",
    "line_to_text",
    "word_boxes_to_text",
]
