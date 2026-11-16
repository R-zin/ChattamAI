"""Tests for structure-aware chunking (``app.rag.structure``).

Chunks must follow the rulebook's own structure and carry a citable rule id, the
heading breadcrumb and (for PDFs) a page number. Covered: the plain-text
convention used by the sample excerpt, the gazette convention used by the Kerala
Panchayat Building Rules PDF (synthetic pages plus the real bundled document),
and graceful fallback for unstructured text.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.rag.structure import build_chunks, split_sections

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "kbr" / "sample_kbr_excerpt.txt"
GAZETTE_PDF = ROOT / "data" / "kbr" / "kerala-panchayat-building-rules-2019.pdf"


def _by_rule(pairs):
    out = {}
    for text, meta in pairs:
        out.setdefault(meta["rule_id"], []).append((text, meta))
    return out


# ---------------------------------------------------------------------------
# plain-text convention (the sample excerpt)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def sample_chunks():
    return build_chunks("sample.txt", [SAMPLE.read_text(encoding="utf-8")])


def test_sample_rules_get_citable_ids(sample_chunks):
    ids = [meta["rule_id"] for _text, meta in sample_chunks]
    for expected in ("Rule 5", "Rule 7", "5.3", "11.2", "Rule 12", "Rule 16"):
        assert expected in ids, expected


def test_sample_chunks_carry_the_heading_breadcrumb(sample_chunks):
    (text, meta) = _by_rule(sample_chunks)["5.3"][0]
    assert meta["section"].startswith("PART C SETBACKS")
    assert "5.3 Setbacks (open spaces)" in meta["section"]
    # The breadcrumb is what the store prepends before embedding.
    assert meta["context"] == meta["section"]
    assert "5.3.1 The minimum front setback" in text


def test_sample_chunks_never_cross_a_rule_boundary(sample_chunks):
    by_rule = _by_rule(sample_chunks)
    setbacks = " ".join(t for t, _m in by_rule["5.3"])
    parking = " ".join(t for t, _m in by_rule["11.2"])
    assert "car-parking" not in setbacks
    assert "front setback" not in parking


def test_text_files_have_no_page_number(sample_chunks):
    assert all("page" not in meta for _text, meta in sample_chunks)


def test_chunk_numbers_are_sequential(sample_chunks):
    numbers = [meta["chunk"] for _text, meta in sample_chunks]
    assert numbers == list(range(1, len(numbers) + 1))


def test_indented_clause_is_not_promoted_to_a_heading():
    doc = "Rule 5   Applicability\n  5.1    These rules apply to all buildings.\n"
    (section,) = split_sections([doc])
    assert section.rule_id == "Rule 5"
    assert "5.1" in section.text


# ---------------------------------------------------------------------------
# gazette convention (synthetic pages)
# ---------------------------------------------------------------------------
FOOTER = "This is a digitally signed Gazette."

GAZETTE_PAGES = [
    "CHAPTER I \nDEFINITIONS \n \n"
    "1. Short title and commencement.-   (1) These rules may be called the Rules. \n"
    "(2) They shall come into force at once. \n"
    "2. Definitions -  (1) In these rules, unless the context otherwise requires,- \n"
    "(a) 'access' means a clear approach to a plot or a building; \n"
    f"1\n{FOOTER}",
    "CHAPTER IV \nOCCUPANCY \n"
    "3.  Applicability:-These rules shall apply to all buildings. \n"
    "4 Access - (1)  The minimum width of access to a building shall be as follows. \n"
    "1. For residential use: - three metres. \n"
    "2. For industrial use: - seven metres. \n"
    f"2\n{FOOTER}",
    "5.Approval of site and plans where excavations to a depth of more \n"
    "than 1.5 metres is involved -   (1) In the case of constructions the owner shall apply. \n"
    "6.  Exterior and Interior open air spaces - (1)  Every room shall abut on an open space. \n"
    "TABLE 4 \nYARDS FOR BUILDINGS UNDER DIFFERENT OCCUPANCIES \n"
    "(1) (2) (3) \nFront 3 2 5 \nRear 1.5 1 2 \n"
    "(5) In case a group of buildings are to be put up the yards shall apply. \n"
    f"3\n{FOOTER}",
    "7. Special provisions for row buildings \n"
    "Row buildings shall not exceed ten units. \n"
    f"4\n{FOOTER}",
    "APPENDIX- A1 \n(See rule 5) \nFORM OF APPLICATION \n"
    "1. Name of the applicant - in capital letters \n"
    "8. Built-up area of existing building - in square metres \n"
    f"5\n{FOOTER}",
]


@pytest.fixture(scope="module")
def gazette_sections():
    return split_sections(GAZETTE_PAGES, paged=True)


@pytest.fixture(scope="module")
def gazette_chunks():
    return build_chunks("gazette.pdf", GAZETTE_PAGES, paged=True)


def test_gazette_rules_are_recognised_in_every_heading_style(gazette_sections):
    rule_ids = [s.rule_id for s in gazette_sections]
    # ".-", " - ", ":-", a missing dot after the number, a title that wraps onto
    # the next line, and a title with no terminating dash at all.
    for expected in ("Rule 1", "Rule 2", "Rule 3", "Rule 4", "Rule 5", "Rule 6"):
        assert expected in rule_ids, expected
    assert "Rule 7" in rule_ids


def test_wrapped_rule_title_is_joined(gazette_sections):
    rule5 = next(s for s in gazette_sections if s.rule_id == "Rule 5")
    assert (
        "excavations to a depth of more than 1.5 metres is involved" in rule5.path[-1]
    )
    assert rule5.text.startswith("(1) In the case of constructions")


def test_chapter_title_is_taken_from_the_following_line(gazette_sections):
    rule3 = next(s for s in gazette_sections if s.rule_id == "Rule 3")
    assert rule3.path[0] == "CHAPTER IV OCCUPANCY"


def test_numbered_list_items_inside_a_rule_are_not_rules(gazette_sections):
    rule4 = next(s for s in gazette_sections if s.rule_id == "Rule 4")
    assert "1. For residential use" in rule4.text
    assert "2. For industrial use" in rule4.text


def test_table_is_filed_under_its_rule(gazette_chunks):
    by_rule = _by_rule(gazette_chunks)
    (text, meta) = by_rule["Rule 6, Table 4"][0]
    assert "Front 3 2 5" in text
    assert "TABLE 4 YARDS FOR BUILDINGS UNDER DIFFERENT OCCUPANCIES" in meta["section"]


def test_sub_rule_after_a_table_returns_to_the_rule(gazette_chunks):
    # "(5) In case a group ..." is Rule 6(5), not part of Table 4; the
    # "(1) (2) (3)" column-number row must not have ended the table early.
    by_rule = _by_rule(gazette_chunks)
    assert "Rule 6(5)" in by_rule
    assert "In case a group of buildings" in by_rule["Rule 6(5)"][0][0]
    assert "(1) (2) (3)" in by_rule["Rule 6, Table 4"][0][0]


def test_sub_rule_number_is_added_to_the_rule_id(gazette_chunks):
    assert "Rule 1(1)" in _by_rule(gazette_chunks)


def test_appendix_forms_are_not_mistaken_for_rules(gazette_chunks):
    by_rule = _by_rule(gazette_chunks)
    assert "Rule 8" not in by_rule
    assert "Appendix A1" in by_rule
    assert "Built-up area of existing building" in by_rule["Appendix A1"][0][0]


def test_page_numbers_are_recorded(gazette_chunks):
    by_rule = _by_rule(gazette_chunks)
    assert by_rule["Rule 1(1)"][0][1]["page"] == 1
    assert by_rule["Rule 4(1)"][0][1]["page"] == 2
    assert by_rule["Rule 6, Table 4"][0][1]["page"] == 3
    assert by_rule["Rule 7"][0][1]["page"] == 4


def test_running_footer_and_page_numbers_are_stripped(gazette_chunks):
    for text, _meta in gazette_chunks:
        assert "digitally signed" not in text
    # The bare page number line "3" is gone, the table row "Front 3 2 5" is not.
    table = _by_rule(gazette_chunks)["Rule 6, Table 4"][0][0]
    assert table.rstrip().endswith("Rear 1.5 1 2")


def test_short_documents_keep_repeated_lines():
    # Repetition only means "footer" in a long document.
    pages = ["Rule 1 Title\nAll buildings shall comply.", "All buildings shall comply."]
    text = " ".join(s.text for s in split_sections(pages, paged=True))
    assert text.count("All buildings shall comply.") == 2


# ---------------------------------------------------------------------------
# fallback
# ---------------------------------------------------------------------------
def test_unstructured_text_falls_back_to_positional_ids():
    pairs = build_chunks("notes.txt", ["Some plain notes. Nothing structured here."])
    assert len(pairs) == 1
    text, meta = pairs[0]
    assert meta["rule_id"] == "notes.txt#chunk-1"
    assert "section" not in meta and "context" not in meta


def test_unstructured_chunk_with_inline_rule_header_uses_it():
    pairs = build_chunks("r.txt", ["Rule 99: All staircases shall be fire resistant."])
    assert pairs[0][1]["rule_id"] == "Rule 99"


def test_wrapped_one_line_rule_is_body_text_not_a_heading():
    doc = (
        "Rule 99: All staircases shall be constructed\nwith non-combustible materials."
    )
    (text, meta) = build_chunks("r.txt", [doc])[0]
    assert text == (
        "Rule 99: All staircases shall be constructed with non-combustible materials."
    )
    assert meta["rule_id"] == "Rule 99"


def test_heading_with_nothing_under_it_is_never_dropped():
    # Reads as a heading (no full stop, nothing after it) - but it is the only
    # text the rule has, so it must still be indexed.
    pairs = build_chunks("r.txt", ["Rule 99 Staircases shall be fire resistant"])
    assert [(t, m["rule_id"]) for t, m in pairs] == [
        ("Rule 99 Staircases shall be fire resistant", "Rule 99")
    ]


def test_empty_document_yields_no_chunks():
    assert build_chunks("empty.txt", ["   \n  "]) == []


# ---------------------------------------------------------------------------
# the real bundled gazette
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def real_gazette_chunks():
    from app.rag.ingestion import _read_pdf_pages

    return build_chunks(GAZETTE_PDF.name, _read_pdf_pages(GAZETTE_PDF), paged=True)


def test_real_gazette_rules_are_recognised(real_gazette_chunks):
    rules = set()
    for _text, meta in real_gazette_chunks:
        rule_id = meta["rule_id"]
        if rule_id.startswith("Rule "):
            rules.add(int(rule_id.split()[1].split("(")[0].rstrip(",")))
    # The rulebook has 109 rules; allow a few unrecognised headings.
    assert len(rules) >= 105
    assert max(rules) == 109


def test_real_gazette_key_rules_are_where_the_text_says(real_gazette_chunks):
    by_rule = _by_rule(real_gazette_chunks)
    yards = by_rule["Rule 26, Table 4"][0]
    assert "YARDS FOR BUILDINGS UNDER DIFFERENT OCCUPANCIES" in yards[1]["section"]
    assert yards[1]["page"] == 50
    fsi = by_rule["Rule 27, Table 6"][0]
    assert "COVERAGE AND FLOOR SPACE INDEX" in fsi[1]["section"]
    assert any(rule.startswith("Rule 29") for rule in by_rule)  # parking
    assert any(rule.startswith("Rule 35") for rule in by_rule)  # staircases


def test_real_gazette_footer_is_not_indexed(real_gazette_chunks):
    assert not any("digitally signed" in text for text, _meta in real_gazette_chunks)
