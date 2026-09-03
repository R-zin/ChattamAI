"""Tests for /api/check report persistence (T1.1), fully offline.

The ``app_client`` fixture boots the real FastAPI app (which runs the
best-effort ``init_db_safe`` -> alembic/create_all against the tmp DATABASE_URL
conftest points at) and injects fake RAG embeddings/LLM, so POSTing /api/check
exercises the persist hook with no network access. Rows are read back through
the app's own ``SessionLocal``/``Report`` model.
"""

from __future__ import annotations

from app.services.database import SessionLocal
from app.services.report_model import Report, derive_status

PLAN = "3 floor building, 12m tall, 1m front setback"


def _report_count() -> int:
    db = SessionLocal()
    try:
        return db.query(Report).count()
    finally:
        db.close()


def _latest_report():
    db = SessionLocal()
    try:
        return db.query(Report).order_by(Report.report_id.desc()).first()
    finally:
        db.close()


def test_check_persists_a_report_row(app_client):
    before = _report_count()
    resp = app_client.post("/api/check", json={"plan_text": PLAN})
    assert resp.status_code == 200
    assert _report_count() == before + 1


def test_persisted_report_fields_match_response(app_client):
    resp = app_client.post("/api/check", json={"plan_text": PLAN})
    assert resp.status_code == 200
    body = resp.json()

    row = _latest_report()
    assert row is not None
    assert row.plan_text == PLAN
    assert row.source == "check"
    assert row.summary == body["summary"]
    assert row.extracted_facts == body["extracted_facts"]
    assert row.violations == body["violations"]
    assert isinstance(row.retrieved_rules, list)


def test_status_derivation_rule():
    assert derive_status([]) == "pass"
    assert derive_status(None) == "pass"
    assert derive_status([{"severity": "low"}]) == "warning"
    assert derive_status([{"severity": "medium"}]) == "warning"
    assert derive_status([{"severity": "low"}, {"severity": "high"}]) == "fail"
    assert derive_status([{"severity": "info"}]) == "pass"


def test_high_severity_check_persists_fail_status(app_client):
    # The fake LLM (analyze_mode="ok") reports one high-severity violation.
    resp = app_client.post("/api/check", json={"plan_text": PLAN})
    assert resp.status_code == 200
    row = _latest_report()
    assert row is not None
    assert row.status == "fail"


def test_unauthenticated_check_persists_null_user_id(app_client):
    # app_client posts with AUTH_REQUIRED unset, so require_auth is a no-op and
    # the report must persist with a NULL user_id rather than erroring.
    resp = app_client.post("/api/check", json={"plan_text": PLAN})
    assert resp.status_code == 200
    row = _latest_report()
    assert row is not None
    assert row.user_id is None
