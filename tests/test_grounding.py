"""Tests for citation grounding (``app.rag.grounding``): is each finding's cited
rule among the retrieved excerpts, and does that excerpt state the required
value? Deterministic; no model involved."""

from __future__ import annotations

import pytest

from app.rag.grounding import (
    extract_rule_identifiers,
    ground_violation,
    ground_violations,
)

SETBACKS = (
    "5.3.1 The minimum front setback from the plot boundary abutting the road "
    "shall be 3.0 metres. 5.3.2 The minimum rear setback shall be 2.0 metres.",
    {"source": "sample.txt", "rule_id": "5.3", "section": "PART C > 5.3 Setbacks"},
    0.9,
)
YARDS = (
    "Front 3 2 5 7.5 Rear 1.5 1 2 3",
    {"source": "kpbr.pdf", "rule_id": "Rule 26, Table 4", "section": "26. Open spaces"},
    0.8,
)
PARKING = (
    "(1) Area of each off-street parking space shall not be less than 15 sq. metres.",
    {"source": "kpbr.pdf", "rule_id": "Rule 29(1)"},
    0.7,
)
UNLABELLED = (
    "Every building shall comply with Rule 35 on staircases of width 1.2 metres.",
    {"source": "n.txt", "rule_id": "n.txt#chunk-4"},
    0.6,
)
RETRIEVED = [SETBACKS, YARDS, PARKING, UNLABELLED]


def _finding(reference, required=None):
    return {
        "rule_reference": reference,
        "severity": "high",
        "description": "x",
        "plan_value": "1m",
        "required_value": required,
    }


# -- identifier extraction ----------------------------------------------------
@pytest.mark.parametrize(
    "reference, rules, tables",
    [
        ("Rule 23(4)", ["23"], []),
        ("Rule 5.3.1", ["5.3.1"], []),
        ("Rule 25(1) / Table 6", ["25"], ["6"]),
        ("KPBR 2019 Rule 27", ["27"], []),
        ("Section 5.3 and Rule 7", ["5.3", "7"], []),
        ("needs review - rule not retrieved", [], []),
        ("", [], []),
    ],
)
def test_extract_rule_identifiers(reference, rules, tables):
    assert extract_rule_identifiers(reference) == {"rules": rules, "tables": tables}


# -- single finding -------------------------------------------------------------
def test_grounded_when_rule_retrieved_and_value_stated():
    record = ground_violation(_finding("5.3.1", "3.0 m"), RETRIEVED)
    assert record["status"] == "grounded"
    assert record["citations"] == [1]
    assert record["value_supported"] is True


def test_value_match_ignores_trailing_zero_and_units():
    # "≥ 3 metres" in the finding vs "3.0 metres" in the rule.
    assert ground_violation(_finding("5.3", "≥ 3 metres"), RETRIEVED)["status"] == (
        "grounded"
    )


def test_grounded_by_rule_id_including_sub_rule():
    # The chunk is filed as "Rule 29(1)"; the finding cites "Rule 29".
    record = ground_violation(_finding("Rule 29", "15 sq.m"), RETRIEVED)
    assert record["status"] == "grounded"
    assert record["citations"] == [3]


def test_grounded_by_table_number():
    record = ground_violation(_finding("Table 4", "7.5 m"), RETRIEVED)
    assert record["status"] == "grounded"
    assert record["citations"] == [2]


def test_grounded_when_rule_is_named_inside_an_unlabelled_chunk():
    record = ground_violation(_finding("Rule 35", "1.2 m"), RETRIEVED)
    assert record["status"] == "grounded"
    assert record["citations"] == [4]


def test_grounded_without_a_required_value():
    record = ground_violation(_finding("Rule 26", None), RETRIEVED)
    assert record["status"] == "grounded"
    assert record["value_supported"] is None


def test_partial_when_rule_retrieved_but_value_absent():
    record = ground_violation(_finding("Rule 29", "99 sq.m"), RETRIEVED)
    assert record["status"] == "partial"
    assert record["citations"] == [3]
    assert record["value_supported"] is False


def test_partial_when_value_is_found_under_a_different_rule():
    # "Rule 99" was never retrieved, but 2.0 metres is in the setbacks excerpt.
    record = ground_violation(_finding("Rule 99", "2.0 m"), RETRIEVED)
    assert record["status"] == "partial"
    assert 1 in record["citations"]
    assert "not under the rule this finding cites" in record["note"]


def test_ungrounded_when_cited_rule_was_never_retrieved():
    record = ground_violation(_finding("Rule 23(4)", "42 m"), RETRIEVED)
    assert record["status"] == "ungrounded"
    assert record["citations"] == []


def test_uncited_when_no_rule_is_named():
    record = ground_violation(
        _finding("needs review - rule not retrieved", None), RETRIEVED
    )
    assert record["status"] == "uncited"


def test_a_quantity_is_not_mistaken_for_a_rule_number():
    # "7.5" in "7.5 metres" must not ground a citation of "Rule 7".
    hit = ("The height shall not exceed 7.5 metres.", {"rule_id": "x#chunk-1"}, 0.5)
    assert ground_violation(_finding("Rule 7"), [hit])["status"] == "ungrounded"


def test_clause_prefix_grounds_its_parent_rule():
    # A chunk containing clause "5.3 Setbacks ..." supports a citation of Rule 5.
    hit = ("5.3 Setbacks for residential buildings apply.", {"rule_id": "c#chunk-1"}, 1)
    assert ground_violation(_finding("Rule 5"), [hit])["status"] == "grounded"


def test_year_in_reference_is_not_a_rule_number():
    record = ground_violation(_finding("KPBR 2019 Rule 29", "15 sq.m"), RETRIEVED)
    assert record["status"] == "grounded"
    assert record["citations"] == [3]


def test_nothing_retrieved_means_ungrounded():
    assert ground_violation(_finding("Rule 5", "3 m"), [])["status"] == "ungrounded"


# -- summary --------------------------------------------------------------------
def test_summary_counts_and_score():
    findings = [
        _finding("5.3.1", "3.0 m"),  # grounded
        _finding("Rule 29", "99 sq.m"),  # partial
        _finding("Rule 23(4)", "42 m"),  # ungrounded
        _finding("needs review", None),  # uncited
    ]
    summary = ground_violations(findings, RETRIEVED)
    assert summary["total"] == 4
    assert (summary["grounded"], summary["partial"]) == (1, 1)
    assert (summary["ungrounded"], summary["uncited"]) == (1, 1)
    assert summary["score"] == pytest.approx(0.375)  # (1 + 0.5) / 4
    assert [item["violation_index"] for item in summary["items"]] == [0, 1, 2, 3]


def test_summary_with_no_findings_scores_one():
    assert ground_violations([], RETRIEVED) == {
        "total": 0,
        "score": 1.0,
        "grounded": 0,
        "partial": 0,
        "ungrounded": 0,
        "uncited": 0,
        "items": [],
    }


def test_findings_are_never_modified_or_removed():
    findings = [_finding("Rule 23(4)", "42 m")]
    snapshot = [dict(f) for f in findings]
    ground_violations(findings, RETRIEVED)
    assert findings == snapshot


def test_malformed_findings_are_skipped_not_fatal():
    summary = ground_violations(["not a dict", _finding("5.3", "3 m")], RETRIEVED)
    assert summary["total"] == 1
    assert summary["items"][0]["violation_index"] == 1
