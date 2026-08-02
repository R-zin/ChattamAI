"""Layout-free OCR for image / image-PDF building plans (plan.md Phase 3).

This module turns a floor-plan image (or an image-only PDF) into plain text so it
can flow through the *existing* ``extract_facts`` node unchanged — the pre-existing
``Path -> str`` seam (:func:`app.rag.ingestion.load_plan_text`). It is v1 and
deliberately "layout-free": we recover words, not geometry.

Dependency / boot-safety contract (see the agent-7 dispatch): the heavy OCR
libraries — Pillow, pytesseract, and PyMuPDF — plus the system *Tesseract binary*
are FEATURE-FLAGGED and lazily imported INSIDE the functions below. Importing this
module therefore never fails on a box without them; only calling the OCR functions
does. Use :func:`ocr_available` to give callers a clear 503 before that happens.

Requires the ``tesseract`` binary at runtime (``brew install tesseract`` /
``apt install tesseract-ocr``); it is NOT a pip dependency.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

# Image suffixes we can OCR directly with Pillow + Tesseract.
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}

# Render image-PDF pages at ~260 DPI: high enough for small dimension text,
# low enough to stay fast and memory-light.
_PDF_RENDER_DPI = 260

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


def ocr_available() -> bool:
    """Return True iff OCR can actually run on this box.

    Checks that the Python deps import AND the Tesseract binary resolves on PATH.
    Used to answer a clear 503 when OCR is requested but unavailable. Never raises;
    offline and import-safe.
    """
    for mod in ("pytesseract", "PIL", "fitz"):
        try:
            __import__(mod)
        except ImportError:
            return False
    return shutil.which("tesseract") is not None


def image_to_text(path: Path) -> str:
    """OCR a single image file to text.

    Opens with Pillow, normalises for legibility (grayscale, light autocontrast,
    upscale if the image is small), then runs ``pytesseract.image_to_string``.
    ``path`` may be anything Pillow can open (see :data:`IMAGE_EXTS`).
    """
    pytesseract = _import("pytesseract")
    Image = _import("PIL.Image")
    ImageOps = _import("PIL.ImageOps")

    with Image.open(str(path)) as img:
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
        text = pytesseract.image_to_string(gray)
    return text


def pdf_images_to_text(path: Path) -> str:
    """OCR every page of an image-only PDF and join the results.

    Renders each page via PyMuPDF (``fitz``) to a raster pixmap at
    ``_PDF_RENDER_DPI`` and runs Tesseract per page. Text PDFs should use
    ``ingestion._read_pdf`` instead; this is for scans / image-only exports.
    """
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
    "ocr_available",
    "image_to_text",
    "pdf_images_to_text",
    "normalize_ocr_text",
]
