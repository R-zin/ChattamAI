"""Document ingestion: read Kerala Building Rules and building-plan uploads.

Supports plain text and text-based PDFs. Image-only floor plans are out of scope
for this pass (they need OCR / layout analysis) — see plan.md Phase 2.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from app.config import get_settings

# Extensions we know how to read directly.
_TEXT_EXTS = {".txt", ".md", ".text"}
_PDF_EXTS = {".pdf"}


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(parts)


def load_kbr_documents(data_dir: Path | None = None) -> List[Tuple[str, str]]:
    """Return list of (text, source_name) for every readable file in data_dir."""
    settings = get_settings()
    data_dir = Path(data_dir or settings.kbr_data_dir)
    if not data_dir.exists():
        return []

    docs: List[Tuple[str, str]] = []
    for path in sorted(data_dir.iterdir()):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        try:
            if suffix in _TEXT_EXTS:
                text = path.read_text(encoding="utf-8", errors="ignore")
            elif suffix in _PDF_EXTS:
                text = _read_pdf(path)
            else:
                continue
        except Exception as exc:  # noqa: BLE001 - skip unreadable files
            print(f"[ingest] skipped {path.name}: {exc}")
            continue
        if text.strip():
            docs.append((text, path.name))
    return docs


def chunk_text(
    text: str, size: int | None = None, overlap: int | None = None
) -> List[str]:
    """Split text into overlapping character windows."""
    settings = get_settings()
    size = size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    # Normalise whitespace to keep chunks clean and comparable.
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    step = max(1, size - overlap)
    chunks: List[str] = []
    for start in range(0, len(text), step):
        chunk = text[start : start + size]
        if chunk:
            chunks.append(chunk)
        if start + size >= len(text):
            break
    return chunks


def load_plan_text(path: Path) -> str:
    """Extract text from an uploaded building-plan file (txt or pdf)."""
    suffix = path.suffix.lower()
    if suffix in _TEXT_EXTS:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix in _PDF_EXTS:
        return _read_pdf(path)
    raise ValueError(f"Unsupported plan file type: {suffix}")
