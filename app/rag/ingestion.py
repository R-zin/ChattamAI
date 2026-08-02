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

# Sentence boundary: end-of-sentence punctuation (optionally followed by a
# closing quote/bracket) then whitespace. Legal/rule text uses ".", ";", ":",
# and clause numbers, so we keep the split conservative to avoid cutting across
# sub-clauses like "8.1.2" (no whitespace after the dot).
_SENTENCE_RE = re.compile(r"(?<=[.!?;])\s+(?=[A-Z0-9(\"'])")

# Rule/section header patterns at the start of a chunk (case-insensitive).
# Covers "Rule 12", "Rules 12(3)", "Section 5.3", "Sec. 5.3", "Clause 4",
# "Annexure II", and a bare leading clause number like "5.3." / "5.3 ".
_RULE_HEADER_RES = (
    re.compile(
        r"^\s*(?:rule[s]?|section|sec\.?|clause|sub-?rule|article)\s+"
        r"([A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*(?:\(\w+\))?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(annexure|schedule|appendix|chapter|part)\s+([A-Za-z0-9IVX]+)",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*((?:\d+\.)+\d*)\s"),
)


def extract_rule_id(chunk: str) -> str | None:
    """Best-effort detection of a rule/section identifier at the head of a chunk.

    Returns a normalised identifier string (e.g. ``"Rule 12"``, ``"5.3"``,
    ``"Annexure II"``) when the chunk opens with a recognisable header, else
    ``None``. Pure regex — token-free and offline.
    """
    if not chunk:
        return None
    head = chunk.lstrip()[:120]

    m = _RULE_HEADER_RES[0].match(head)
    if m:
        label = head[: m.start(1)].strip()
        return f"{label} {m.group(1)}".replace("  ", " ")

    m = _RULE_HEADER_RES[1].match(head)
    if m:
        return f"{m.group(1).capitalize()} {m.group(2)}"

    m = _RULE_HEADER_RES[2].match(head)
    if m:
        return m.group(1).rstrip(".")

    return None


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


def split_sentences(text: str) -> List[str]:
    """Split normalised text into sentences.

    Whitespace is collapsed first so the boundary regex sees single spaces.
    This is deliberately conservative: it avoids splitting on the periods in
    rule/clause numbers ("8.1.2") because those are not followed by whitespace.
    """
    norm = re.sub(r"\s+", " ", text).strip()
    if not norm:
        return []
    return [s for s in _SENTENCE_RE.split(norm) if s]


def _hard_split(sentence: str, size: int, overlap: int) -> List[str]:
    """Fallback char-window split for a single over-long sentence."""
    step = max(1, size - overlap)
    parts: List[str] = []
    for start in range(0, len(sentence), step):
        piece = sentence[start : start + size]
        if piece:
            parts.append(piece)
        if start + size >= len(sentence):
            break
    return parts


def chunk_sentences(
    text: str, size: int | None = None, overlap: int | None = None
) -> List[str]:
    """Split text into chunks that never cut across a sentence boundary.

    Sentences are packed greedily into ``size``-bounded chunks. To preserve
    local context across boundaries, each new chunk re-includes the trailing
    sentences of the previous chunk up to ``overlap`` characters. A single
    sentence longer than ``size`` falls back to a char-window split so we never
    emit a chunk larger than ``size``.
    """
    settings = get_settings()
    size = size or settings.chunk_size
    overlap = overlap if overlap is not None else settings.chunk_overlap
    overlap = max(0, min(overlap, size - 1))

    sentences = split_sentences(text)
    if not sentences:
        return []

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append(" ".join(current).strip())
        current = []
        current_len = 0

    def seed_overlap(closed: List[str]) -> None:
        """Re-include trailing sentences of the just-closed chunk so context
        carries across the boundary, up to ``overlap`` characters."""
        nonlocal current, current_len
        tail: List[str] = []
        tail_len = 0
        for s in reversed(closed):
            extra = len(s) if tail_len == 0 else tail_len + 1 + len(s)
            if tail and extra > overlap:
                break
            tail.insert(0, s)
            tail_len = extra
        current = tail
        current_len = sum(len(s) for s in tail) + max(0, len(tail) - 1)

    for sentence in sentences:
        if len(sentence) > size:
            # Over-long sentence: close the chunk and hard-split the sentence.
            flush()
            chunks.extend(_hard_split(sentence, size, overlap))
            continue

        added = len(sentence) if current_len == 0 else current_len + 1 + len(sentence)
        if added > size and current:
            closed = current
            flush()
            seed_overlap(closed)

        current.append(sentence)
        current_len = (
            len(sentence) if current_len == 0 else current_len + 1 + len(sentence)
        )

    flush()
    return [c for c in chunks if c]


def chunk_text(
    text: str, size: int | None = None, overlap: int | None = None
) -> List[str]:
    """Split text into overlapping chunks.

    Defaults to sentence-aware chunking so retrieved excerpts are coherent
    whole sentences/clauses rather than arbitrary character windows.
    """
    return chunk_sentences(text, size=size, overlap=overlap)


def load_plan_text(path: Path) -> str:
    """Extract text from an uploaded building-plan file (txt or pdf)."""
    suffix = path.suffix.lower()
    if suffix in _TEXT_EXTS:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix in _PDF_EXTS:
        return _read_pdf(path)
    raise ValueError(f"Unsupported plan file type: {suffix}")
