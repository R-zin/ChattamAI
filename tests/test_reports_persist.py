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
    if body.get("verification") is not None:
        assert row.verification == body["verification"]


def test_persisted_report_stores_active_verification(app_client):
    from tests.test_double_check import MockVerifierLLM
    from app.rag.graph import Context, build_compliance_graph, build_async_compliance_graph

    verifier = MockVerifierLLM(
        response_json={
            "status": "confirmed",
            "confidence_score": 0.99,
            "cross_check_notes": "All candidate violations double-checked.",
            "discrepancies": [],
            "final_violations": [
                {
                    "rule_reference": "Rule 5",
                    "severity": "high",
                    "description": "Front setback below the permitted minimum.",
                    "plan_value": "1m",
                    "required_value": "1.8m",
                }
            ],
        },
        model="mock-gpt4",
    )
    rag = app_client.app.state.rag
    rag.verifier_llm = verifier
    rag.verifier_ready = True
    rag.verifier_model = "mock-gpt4"
    ctx = Context(
        llm=rag._llm,
        store=rag._store,
        default_top_k=rag.settings.top_k,
        analysis_cache=rag._analysis_memo,
        verifier_llm=verifier,
    )
    rag._graph = build_compliance_graph(ctx)
    rag._agraph = build_async_compliance_graph(ctx)

    resp = app_client.post("/api/check", json={"plan_text": PLAN})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("verification") is not None
    assert body["verification"]["status"] == "confirmed"

    row = _latest_report()
    assert row is not None
    assert row.verification is not None
    assert row.verification["status"] == "confirmed"
    assert row.verification["verified_by_model"] == "mock-gpt4"
    assert row.verification["confidence_score"] == 0.99


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
