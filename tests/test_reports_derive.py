"""Additional edge-case tests for report status derivation + ReportOut schema.

Complements ``tests/test_reports_persist.py`` (which covers persistence and the
common severity paths) by pinning the unknown-severity and robustness branches
of :func:`app.services.report_model.derive_status`, and the ORM round-trip of
the ``ReportOut`` read-model. Offline; no network.
"""

from __future__ import annotations

from app.schemas_reports import ReportOut
from app.services.report_model import derive_status


# -- derive_status edge cases -------------------------------------------------
def test_unknown_severity_maps_to_warning_not_pass():
    # An unrecognised severity must never silently report a pass.
    assert derive_status([{"severity": "critical"}]) == "warning"
    assert derive_status([{"severity": ""}]) == "warning"
    assert derive_status([{}]) == "warning"


def test_unknown_plus_high_is_fail():
    assert derive_status([{"severity": "bogus"}, {"severity": "high"}]) == "fail"


def test_unknown_plus_info_is_warning():
    # info alone is "pass", but an unknown severity forces "warning".
    assert derive_status([{"severity": "info"}, {"severity": "???"}]) == "warning"


def test_severity_matching_is_case_insensitive():
    assert derive_status([{"severity": "HIGH"}]) == "fail"
    assert derive_status([{"severity": "High"}]) == "fail"
    assert derive_status([{"severity": "LOW"}]) == "warning"


def test_non_dict_violations_are_tolerated():
    # None / non-dict entries must not raise; treated as unknown -> warning.
    assert derive_status([None]) == "warning"
    assert derive_status([{"severity": "low"}, None]) == "warning"


def test_empty_and_none_violations_pass():
    assert derive_status([]) == "pass"
    assert derive_status(None) == "pass"


# -- ReportOut read-model -----------------------------------------------------
def test_report_out_validates_from_orm_attributes():
    class _Row:
        report_id = 7
        created_at = None
        plan_text = "a plan"
        source = "check"
        summary = "s"
        extracted_facts = ["f1", "f2"]
        violations = [{"severity": "high"}]
        retrieved_rules = [{"rule_id": "Rule 5"}]
        status = "fail"
        user_id = None

    out = ReportOut.model_validate(_Row())
    assert out.report_id == 7
    assert out.status == "fail"
    assert out.violations == [{"severity": "high"}]
    assert out.user_id is None


def test_report_out_all_optional_fields_default_none():
    # Only report_id is required; a partial row still validates.
    out = ReportOut(report_id=1)
    assert out.summary is None
    assert out.extracted_facts is None
    assert out.violations is None
    assert out.status is None
