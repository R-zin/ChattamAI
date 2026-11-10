"""Tests for API resilience, exception handlers, rate limiting headers, and error responses."""

from __future__ import annotations

from datetime import timedelta
import io
from unittest.mock import MagicMock, patch

import fitz
import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app, reset_rate_limits
from app.schemas import VerificationResult
from app.services.database import SessionLocal
from app.services.dbmodel import User, create_access_token, hash_password, new_id


@pytest.fixture(autouse=True)
def _clear_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


def test_validation_error_handler_response(app_client: TestClient):
    """Ensure RequestValidationError returns structured 422 with code and formatted details."""
    resp = app_client.post("/api/check", json={"plan_text": ""})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "plan_text" in body["detail"]
    assert isinstance(body["errors"], list)
    assert len(body["errors"]) > 0


def test_unhandled_exception_handler_returns_500():
    """Ensure unexpected exceptions return clean 500 JSON without leaking tracebacks."""
    from fastapi.routing import APIRoute

    def _test_crash():
        raise RuntimeError("Database cluster exploded")

    route = APIRoute("/_test_unhandled_crash_endpoint", _test_crash, methods=["GET"])
    app.router.routes.insert(0, route)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/_test_unhandled_crash_endpoint")
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == "INTERNAL_SERVER_ERROR"
        assert (
            body["detail"] == "An internal server error occurred. Please retry later."
        )
    finally:
        if route in app.router.routes:
            app.router.routes.remove(route)


def test_rate_limit_retry_after_header(app_client: TestClient, monkeypatch):
    """Ensure HTTP 429 response includes the standard Retry-After header."""
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)

    # 2 requests succeed or fail with normal route status
    r1 = app_client.post("/auth/login/json", json={"email": "a@b.com", "password": "x"})
    r2 = app_client.post("/auth/login/json", json={"email": "a@b.com", "password": "x"})
    assert r1.status_code != 429
    assert r2.status_code != 429

    # 3rd request should hit rate limit
    r3 = app_client.post("/auth/login/json", json={"email": "a@b.com", "password": "x"})
    assert r3.status_code == 429
    assert "retry-after" in r3.headers
    retry_after = int(r3.headers["retry-after"])
    assert 1 <= retry_after <= 60
    assert r3.json()["detail"] == "Too many requests. Please slow down."


def test_spa_fallback_blocks_api_and_auth_paths(app_client: TestClient):
    """Ensure missing /api/ and /auth/ routes return 404 JSON instead of SPA index.html."""
    r_api = app_client.get("/api/nonexistent-endpoint")
    assert r_api.status_code == 404
    assert r_api.json()["detail"] == "Endpoint not found"

    r_auth = app_client.get("/auth/nonexistent-auth")
    assert r_auth.status_code == 404
    assert r_auth.json()["detail"] == "Endpoint not found"

    r_api_exact = app_client.get("/api")
    assert r_api_exact.status_code == 404
    assert r_api_exact.json()["detail"] == "Endpoint not found"


def test_verification_result_retains_reason_and_error():
    """Ensure VerificationResult retains reason and error attributes when serialized."""
    res_skipped = VerificationResult(
        status="skipped",
        confidence_score=1.0,
        reason="Model disabled by administrator",
    )
    dumped_skipped = res_skipped.model_dump()
    assert dumped_skipped["reason"] == "Model disabled by administrator"
    assert dumped_skipped["error"] is None

    res_err = VerificationResult(
        status="error",
        confidence_score=0.0,
        error="LLM provider timed out after 30s",
    )
    dumped_err = res_err.model_dump()
    assert dumped_err["error"] == "LLM provider timed out after 30s"
    assert dumped_err["reason"] is None


def test_empty_file_uploads_rejected_with_400(app_client: TestClient, monkeypatch):
    """Ensure /api/kbr/upload, /api/check/upload, and /api/check/plan-ocr reject empty files."""
    # /api/check/upload with empty file
    empty_file = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
    resp = app_client.post("/api/check/upload", files=empty_file)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Uploaded file is empty."

    # /api/kbr/upload with empty file
    empty_kbr = {"file": ("empty_rule.txt", io.BytesIO(b""), "text/plain")}
    resp_kbr = app_client.post("/api/kbr/upload", files=empty_kbr)
    assert resp_kbr.status_code == 400
    assert resp_kbr.json()["detail"] == "Uploaded file is empty."

    # /api/check/plan-ocr with empty file (enable OCR so it passes gating)
    settings = get_settings()
    monkeypatch.setattr(settings, "ocr_enabled", True)
    with patch("app.rag.ocr.ocr_available", return_value=True):
        empty_img = {"file": ("empty_plan.png", io.BytesIO(b""), "image/png")}
        resp_ocr = app_client.post("/api/check/plan-ocr", files=empty_img)
        assert resp_ocr.status_code == 400
        assert resp_ocr.json()["detail"] == "Uploaded file is empty."


def test_upstream_timeout_returns_504_in_check(app_client: TestClient):
    """Ensure httpx.TimeoutException maps to 504 Gateway Timeout in /api/check and /api/check/upload."""
    plan_text = "3 floor building, 12m tall, 1m front setback"
    with patch(
        "app.rag.system.RAGSystem.check",
        side_effect=httpx.ReadTimeout("Read timed out"),
    ):
        resp = app_client.post("/api/check", json={"plan_text": plan_text})
        assert resp.status_code == 504
        assert "timed out" in resp.json()["detail"]

    with patch(
        "app.rag.system.RAGSystem.check_plan_file",
        side_effect=httpx.ConnectTimeout("Connect timed out"),
    ):
        files = {
            "file": ("plan.txt", io.BytesIO(plan_text.encode("utf-8")), "text/plain")
        }
        resp = app_client.post("/api/check/upload", files=files)
        assert resp.status_code == 504
        assert "timed out" in resp.json()["detail"]


def test_rules_search_vectorstore_error_returns_503(app_client: TestClient):
    """Ensure vectorstore / embedding errors in /api/rules/search return 503."""
    mock_store = MagicMock()
    mock_store.size = 5
    mock_store.similarity_search.side_effect = RuntimeError("FAISS index unreadable")
    app_client.app.state.rag._store = mock_store

    resp = app_client.get("/api/rules/search?q=setback")
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"]


def test_v2_check_pdf_handles_corrupted_pdf_and_timeout(app_client: TestClient):
    """Ensure /api/v2/check/pdf handles fitz.FileDataError as 400 and timeouts as 504."""
    pdf_bytes = b"%PDF-1.4 test valid header"

    mock_graph = MagicMock()
    mock_graph.ainvoke.side_effect = fitz.FileDataError("corrupted stream")

    with patch("app.routes.rag_v2.get_multi_agent_graph", return_value=mock_graph):
        resp = app_client.post(
            "/api/v2/check/pdf",
            files={"file": ("drawing.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert resp.status_code == 400
        assert (
            resp.json()["detail"]
            == "Corrupted or unreadable architectural drawing PDF."
        )

    mock_graph.ainvoke.side_effect = httpx.ReadTimeout("LLM service timeout")
    with patch("app.routes.rag_v2.get_multi_agent_graph", return_value=mock_graph):
        resp = app_client.post(
            "/api/v2/check/pdf",
            files={"file": ("drawing.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert resp.status_code == 504
        assert "timed out" in resp.json()["detail"]


def test_v2_check_pdf_export_report_handles_corrupted_pdf_and_timeout(
    app_client: TestClient,
):
    """Ensure /api/v2/check/pdf/export-report handles fitz.FileDataError as 400 and timeouts as 504."""
    pdf_bytes = b"%PDF-1.4 test valid header"

    mock_graph = MagicMock()
    mock_graph.ainvoke.side_effect = fitz.FileDataError("corrupted stream")

    with patch("app.routes.rag_v2.get_multi_agent_graph", return_value=mock_graph):
        resp = app_client.post(
            "/api/v2/check/pdf/export-report",
            files={"file": ("drawing.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert resp.status_code == 400
        assert (
            resp.json()["detail"]
            == "Corrupted or unreadable architectural drawing PDF."
        )

    mock_graph.ainvoke.side_effect = httpx.ConnectTimeout("LLM timeout")
    with patch("app.routes.rag_v2.get_multi_agent_graph", return_value=mock_graph):
        resp = app_client.post(
            "/api/v2/check/pdf/export-report",
            files={"file": ("drawing.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert resp.status_code == 504
        assert "timed out" in resp.json()["detail"]


def test_v2_evaluate_catches_math_errors(app_client: TestClient):
    """Ensure /api/v2/evaluate catches arithmetic / division by zero errors and returns 422."""
    payload = {
        "jurisdiction": "panchayat",
        "occupancy": "A1",
        "plot_area_sqm": 250.0,
        "built_up_area_sqm": 180.0,
        "ground_coverage_sqm": 100.0,
        "building_height_m": 8.0,
        "number_of_floors": 2,
        "road_width_m": 4.0,
        "front_setback_m": 2.2,
        "rear_setback_m": 1.6,
        "side_setback_1_m": 1.3,
        "side_setback_2_m": 1.1,
        "parking_slots_provided": 1,
    }
    with patch(
        "app.routes.rag_v2.evaluate_plan_facts",
        side_effect=ZeroDivisionError("float division by zero"),
    ):
        resp = app_client.post("/api/v2/evaluate", json=payload)
        assert resp.status_code == 422
        assert (
            "Invalid numeric parameters for compliance calculation"
            in resp.json()["detail"]
        )


def test_get_current_user_expired_token(app_client: TestClient):
    """Ensure expired JWT returns 401 with standard expired error description in WWW-Authenticate."""
    db = SessionLocal()
    user_id = new_id()
    try:
        user = User(
            user_id=user_id,
            email=f"expired_{user_id}@example.com",
            password=hash_password("valid-password"),
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    # Create token that expired 10 seconds ago
    expired_token = create_access_token(
        user_id=user_id,
        email=f"expired_{user_id}@example.com",
        expires_delta=timedelta(seconds=-10),
    )

    resp = app_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Session expired. Please log in again."
    auth_header = resp.headers.get("www-authenticate", "")
    assert 'error="invalid_token"' in auth_header
    assert "The access token expired" in auth_header
