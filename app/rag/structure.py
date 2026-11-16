"""Structure-aware chunking of rule documents.

Flat chunking loses where an excerpt sits in the rulebook: a chunk that says
"Front ... 3 2 5 7.5" is useless unless you know it is Table 4 (yards) under
Rule 26 in Chapter IV. This module walks a document line by line, recognises
its headings, and emits chunks that each carry

* ``rule_id``  - a citable identifier such as ``Rule 26`` or ``Rule 26, Table 4``
* ``section``  - the heading breadcrumb (``CHAPTER IV OCCUPANCY > 26. Exterior
  and Interior open air spaces``)
* ``context``  - the breadcrumb the vector store prepends before embedding and
  lexical indexing (contextual retrieval), so the chunk is findable by the
  words of its headings as well as its body
* ``page``     - the 1-based page it starts on, for paged sources (PDF)

Two heading styles are recognised: the gazetted Kerala rules (``CHAPTER IV``,
``26. Exterior and Interior open air spaces - (1) ...``, ``TABLE 4``) and the
plain-text convention (``PART C -- SETBACKS``, ``Rule 7  Floor space index``,
``5.3 Setbacks``). A document with no recognisable headings degrades to the
previous flat behaviour. Pure regex, deterministic, offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

_WS_RE = re.compile(r"\s+")

# Level 0: CHAPTER IV / PART C -- TITLE / APPENDIX A1 / SCHEDULE II / ANNEXURE.
_DIVISION_RE = re.compile(
    r"^\s*(CHAPTER|PART|APPENDIX|SCHEDULE|ANNEXURE)\s*[-–—]?\s*"
    r"([A-Z0-9]+(?:[-.][A-Z0-9]+)*)\b\s*(?:[-–—:]+\s*(.*))?$"
)
# Level 2: TABLE 4 / TABLE 6 : COVERAGE AND FLOOR SPACE INDEX.
_TABLE_RE = re.compile(r"^\s*TABLE\s+(\d+[A-Z]?)\b\s*[:\-–—]?\s*(.*)$")
# Level 1 (plain text): "Rule 7   Floor space index, number of floors".
_RULE_WORD_RE = re.compile(
    r"^(Rule|Section|Regulation)\s+(\d+[A-Z]?)\b[\s.:\-–—]*(.*)$"
)
# Level 1 (plain text): an unindented "5.3 Setbacks for Residential buildings".
_NUMBERED_TITLE_RE = re.compile(r"^(\d+(?:\.\d+)+)\s+([A-Z][^\n]{2,90})$")
# Level 1 (gazette): "26.  Exterior and Interior open air spaces - (1) Every".
# The dot after the number is sometimes missing ("28 Access - (1) The ...").
_GAZETTE_RULE_RE = re.compile(r"^\s*(\d{1,3})(\s*\.\s*|\s+)([A-Z].*)$")
# Where a gazette rule title ends and its body begins.
_TITLE_END_RE = re.compile(
    r"\s*[.:]\s*[-–—]+"  # ".-"  ":-"  ". -"
    r"|\s+[-–—]+(?=\s|\(|$)"  # " - "
    r"|[-–—]+\s*(?=\(\d)"  # "roads- (1)"
    r"|\.\s*(?=\(\d)"  # "etc.(1)"
    r"|\s+(?=\(1\))"  # "WELLS  (1)"
)
_SUBRULE_HEAD_RE = re.compile(r"^\((\d{1,2})\)")
# Distinguishes "(5) In case a group ..." from a "(1) (2) (3)" column row.
_SUBRULE_RESUME_RE = re.compile(r"^\(\d{1,2}\)\s+[A-Z][a-z]")
_ALL_CAPS_RE = re.compile(r"^[A-Z0-9 ,.&/()\-–—:']{4,120}$")

# A gazette rule number may skip a few (a heading we failed to recognise) but
# never jumps far or goes backwards; numbered list items inside a rule do.
_MAX_RULE_GAP = 8


@dataclass
class Section:
    """A run of body text under one heading path."""

    path: Tuple[str, ...]
    rule_id: Optional[str]
    page: Optional[int]
    lines: List[str] = field(default_factory=list)
    # (line index, page) each time the page changes inside the section.
    page_marks: List[Tuple[int, int]] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _clean(text: str) -> str:
    return _WS_RE.sub(" ", text).strip(" \t-–—:.")


def _title_and_body(rest: str) -> Tuple[str, str, bool]:
    """Split ``"Title - (1) body"`` into ``(title, body, terminated)``."""
    match = _TITLE_END_RE.search(rest)
    if match:
        return _clean(rest[: match.start()]), rest[match.end() :].strip(), True
    return _clean(rest), "", False


class _Walker:
    """Single pass over the lines, tracking the heading stack."""

    def __init__(self) -> None:
        self.sections: List[Section] = []
        self.division: Optional[str] = None
        self.division_id: Optional[str] = None
        self.rule: Optional[str] = None
        self.rule_id: Optional[str] = None
        self.table: Optional[str] = None
        self.table_id: Optional[str] = None
        self.last_rule_no = 0
        self.in_back_matter = False
        self.current: Optional[Section] = None
        self.page: Optional[int] = None
        # The section opened by the latest rule heading, until text arrives.
        self._bare_rule: Optional[Section] = None

    # -- section bookkeeping ------------------------------------------------
    def _path(self) -> Tuple[str, ...]:
        return tuple(p for p in (self.division, self.rule, self.table) if p)

    def _rule_ref(self) -> Optional[str]:
        if self.rule_id and self.table_id:
            return f"{self.rule_id}, {self.table_id}"
        return self.table_id or self.rule_id or self.division_id

    def _open(self) -> None:
        self.current = Section(
            path=self._path(), rule_id=self._rule_ref(), page=self.page
        )
        self.sections.append(self.current)

    def add_text(self, line: str) -> None:
        if self.current is None:
            self._open()
        section = self.current
        assert section is not None
        self._bare_rule = None
        if self.page is not None and (
            not section.page_marks or section.page_marks[-1][1] != self.page
        ):
            section.page_marks.append((len(section.lines), self.page))
        section.lines.append(line)

    # -- headings -----------------------------------------------------------
    def keep_bare_rule(self) -> None:
        """A rule heading with nothing under it is itself the rule's text.

        ``Rule 99 Staircases shall be fire resistant`` on a line of its own
        reads as a heading; dropping it would silently lose the rule.
        """
        if self._bare_rule is not None and self.rule:
            self._bare_rule.lines.append(self.rule)
        self._bare_rule = None

    def division_heading(self, kind: str, number: str, title: str) -> None:
        self.keep_bare_rule()
        label = f"{kind.upper()} {number}"
        self.division = f"{label} {title}".strip() if title else label
        self.division_id = f"{kind.capitalize()} {number}"
        self.rule = self.rule_id = self.table = self.table_id = None
        # Appendices and schedules are forms and fee tables: their numbered
        # lines are not rules.
        self.in_back_matter = kind.upper() in ("APPENDIX", "SCHEDULE", "ANNEXURE")
        self._open()

    def rule_heading(self, rule_id: str, label: str) -> None:
        self.keep_bare_rule()
        self.rule, self.rule_id = label, rule_id
        self.table = self.table_id = None
        self._open()
        self._bare_rule = self.current

    def table_heading(self, number: str, title: str) -> None:
        self.table_id = f"Table {number}"
        self.table = f"TABLE {number} {title}".strip()
        self._open()

    def close_table(self) -> None:
        self.table = self.table_id = None
        self._open()


def _boilerplate_lines(pages: Sequence[str]) -> frozenset:
    """Lines repeated on many pages (running headers / footers).

    A gazette prints "This is a digitally signed Gazette." at the foot of every
    page; indexed as body text it pollutes whichever rule happens to straddle a
    page break. Only applied to documents long enough for repetition to mean
    something.
    """
    if len(pages) < 5:
        return frozenset()
    counts: dict = {}
    for page_text in pages:
        for line in {ln.strip() for ln in page_text.splitlines()}:
            if len(line) >= 12:
                counts[line] = counts.get(line, 0) + 1
    floor = max(3, int(len(pages) * 0.3))
    return frozenset(line for line, n in counts.items() if n >= floor)


def split_sections(pages: Sequence[str], paged: bool = False) -> List[Section]:
    """Split a document (one string per page) into heading-scoped sections."""
    walker = _Walker()
    boilerplate = _boilerplate_lines(pages) if paged else frozenset()
    for page_no, page_text in enumerate(pages, start=1):
        walker.page = page_no if paged else None
        lines = [
            ln
            for ln in page_text.splitlines()
            if ln.strip() not in boilerplate
            # A bare page number on its own line.
            and not (paged and ln.strip() == str(page_no))
        ]
        i = 0
        while i < len(lines):
            raw = lines[i]
            line = raw.rstrip()
            stripped = line.strip()
            i += 1
            if not stripped:
                continue
            nxt = lines[i].strip() if i < len(lines) else ""
            # A plain-text heading stands alone: it is not a sentence, and the
            # line after it is blank, indented or absent. "Rule 99: Staircases
            # shall be fire resistant." is a one-line rule, not a heading.
            stands_alone = not stripped.endswith((".", ";", ",")) and (
                i >= len(lines) or not lines[i].strip() or lines[i][:1].isspace()
            )

            match = _DIVISION_RE.match(stripped)
            if match and stripped == stripped.upper():
                title = _clean(match.group(3) or "")
                # Gazette style puts the chapter title on the following line.
                if not title and nxt and _ALL_CAPS_RE.match(nxt):
                    if not _DIVISION_RE.match(nxt) and not _TABLE_RE.match(nxt):
                        title = _clean(nxt)
                        i += 1
                walker.division_heading(match.group(1), match.group(2), title)
                continue

            match = _TABLE_RE.match(stripped)
            if match:
                title = _clean(match.group(2) or "")
                if not title and nxt and _ALL_CAPS_RE.match(nxt):
                    title = _clean(nxt)
                    i += 1
                walker.table_heading(match.group(1), title)
                continue

            # Plain-text heading styles; switched off once gazette-numbered
            # rules have been seen, where a line may merely begin "Rule 25 of".
            if not walker.in_back_matter and walker.last_rule_no == 0:
                match = _RULE_WORD_RE.match(stripped)
                if (
                    match
                    and stands_alone
                    and not raw[:1].isspace()
                    and len(stripped) <= 110
                ):
                    title = _clean(match.group(3))
                    rule_id = f"{match.group(1)} {match.group(2)}"
                    walker.rule_heading(rule_id, f"{rule_id} {title}".strip())
                    continue

                match = _NUMBERED_TITLE_RE.match(line)
                if match and stands_alone:
                    walker.rule_heading(
                        match.group(1), f"{match.group(1)} {_clean(match.group(2))}"
                    )
                    continue

            if not walker.in_back_matter:
                match = _GAZETTE_RULE_RE.match(line)
                if match:
                    number = int(match.group(1))
                    gap = number - walker.last_rule_no
                    dotted = "." in match.group(2)
                    title, body, terminated = _title_and_body(match.group(3))
                    # A title that wraps: its terminating dash is on the next line.
                    if not terminated and nxt and gap == 1:
                        more_title, more_body, more_term = _title_and_body(nxt)
                        if more_term and len(title) + len(more_title) <= 180:
                            title = f"{title} {more_title}".strip()
                            body, terminated = more_body, True
                            i += 1
                    if dotted:
                        accepted = (terminated and 0 < gap <= _MAX_RULE_GAP) or (
                            gap == 1 and len(title) <= 80
                        )
                    else:
                        # No dot: only the very next rule, and only with a
                        # terminated title, so table rows are never promoted.
                        accepted = terminated and gap == 1
                    if accepted and title:
                        walker.last_rule_no = number
                        walker.rule_heading(f"Rule {number}", f"{number}. {title}")
                        if body:
                            walker.add_text(body)
                        continue

            # A numbered sub-rule resumes after a table: "(5) In case a group".
            if walker.table and _SUBRULE_RESUME_RE.match(stripped):
                walker.close_table()
            walker.add_text(line)
    walker.keep_bare_rule()
    return [s for s in walker.sections if s.text.strip()]


def _page_for_chunk(chunk: str, section: Section, cursor: List[int]) -> Optional[int]:
    """Best-effort page of a chunk: find where its opening words fall.

    ``cursor`` carries the line index reached by the previous chunk so the
    search only moves forward (chunks are emitted in document order).
    """
    if section.page is None:
        return None
    probe = chunk[:48]
    lines = section.lines
    # Search a sliding window of normalised lines from the cursor onward
    # (a window, because table cells extract as one short word per line).
    for start in range(cursor[0], len(lines)):
        window = _WS_RE.sub(" ", " ".join(lines[start : start + 12])).strip()
        if probe[:24] and probe[:24] in window:
            cursor[0] = start
            break
    page = section.page
    for line_idx, page_no in section.page_marks:
        if line_idx <= cursor[0]:
            page = page_no
        else:
            break
    return page


def build_chunks(
    source: str,
    pages: Sequence[str],
    paged: bool = False,
    size: Optional[int] = None,
    overlap: Optional[int] = None,
) -> List[Tuple[str, dict]]:
    """Chunk one document into ``(text, meta)`` pairs with structural metadata.

    ``pages`` is the document split by page (a single-element list for a text
    file). Each section is packed with the sentence-aware chunker, so chunks
    never cross a rule boundary and never cut a sentence.
    """
    from app.rag.ingestion import chunk_sentences, extract_rule_id

    out: List[Tuple[str, dict]] = []
    for section in split_sections(pages, paged=paged):
        cursor = [0]
        breadcrumb = " > ".join(section.path)
        for chunk in chunk_sentences(section.text, size=size, overlap=overlap):
            number = len(out) + 1
            rule_id = section.rule_id
            if rule_id and rule_id.startswith("Rule ") and "," not in rule_id:
                sub = _SUBRULE_HEAD_RE.match(chunk)
                if sub:
                    rule_id = f"{rule_id}({sub.group(1)})"
            if not rule_id:
                rule_id = extract_rule_id(chunk) or f"{source}#chunk-{number}"
            meta = {"source": source, "chunk": number, "rule_id": rule_id}
            if breadcrumb:
                meta["section"] = breadcrumb
                meta["context"] = breadcrumb
            page = _page_for_chunk(chunk, section, cursor)
            if page is not None:
                meta["page"] = page
            out.append((chunk, meta))
    return out
