"""HTTP tests for the compliance API, fully offline via injected fakes.

The ``app_client`` fixture boots the real FastAPI app through a TestClient and
then overrides ``app.state.rag`` with a fake-backed ``RAGSystem`` (FakeLLM +
FakeEmbeddingProvider), so no OpenAI/Anthropic call or network access happens.
A separate default-boot client (no override, no credentials) is used to assert
graceful-degraded health, matching the CI smoke expectation.
"""

from __future__ import annotations

import io

from app.schemas import ComplianceResponse, HealthResponse

PLAN = "3 floor building, 12m tall, 1m front setback"


def test_root_lists_endpoints(app_client):
    resp = app_client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "ChattamAI RAG"
    assert body["endpoints"]["health"] == "/api/health"


def test_health_ok_with_fakes(app_client):
    resp = app_client.get("/api/health")
    assert resp.status_code == 200
    health = HealthResponse(**resp.json())
    assert health.embeddings_ready is True
    assert health.llm_ready is True
    assert health.status == "ok"
    # app_client preloads two rules into the index.
    assert health.index_size == 2


def test_check_returns_shaped_compliance_response(app_client):
    resp = app_client.post("/api/check", json={"plan_text": PLAN})
    assert resp.status_code == 200
    body = ComplianceResponse(**resp.json())

    assert body.violations, "expected at least one violation"
    v = body.violations[0]
    assert v.rule_reference == "Rule 5"
    assert v.severity == "high"
    assert v.plan_value == "1m"
    assert v.required_value == "1.8m"

    assert body.retrieved_rules, "expected retrieved rules"
    rr = body.retrieved_rules[0]
    assert rr.source == "kbr.txt"
    assert rr.excerpt
    assert isinstance(rr.score, float)

    assert body.summary
    assert isinstance(body.extracted_facts, list) and body.extracted_facts


def test_check_requires_plan_text(app_client):
    # empty plan_text violates min_length=1 -> 422
    resp = app_client.post("/api/check", json={"plan_text": ""})
    assert resp.status_code == 422
    resp = app_client.post("/api/check", json={})
    assert resp.status_code == 422


def test_check_respects_top_k(app_client):
    resp = app_client.post("/api/check", json={"plan_text": PLAN, "top_k": 1})
    assert resp.status_code == 200
    body = ComplianceResponse(**resp.json())
    assert len(body.retrieved_rules) == 1


def test_upload_rejects_unsupported_extension(app_client):
    files = {"file": ("plan.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")}
    resp = app_client.post("/api/check/upload", files=files)
    assert resp.status_code == 415
    assert "Unsupported file type" in resp.json()["detail"]


def test_upload_accepts_text_file(app_client):
    files = {"file": ("plan.txt", io.BytesIO(PLAN.encode("utf-8")), "text/plain")}
    resp = app_client.post("/api/check/upload", files=files)
    assert resp.status_code == 200
    body = ComplianceResponse(**resp.json())
    assert body.violations


def test_upload_rejects_other_binary_extensions(app_client):
    for name in ("plan.docx", "plan.jpg", "plan.exe"):
        files = {"file": (name, io.BytesIO(b"data"), "application/octet-stream")}
        resp = app_client.post("/api/check/upload", files=files)
        assert resp.status_code == 415, name


# -- default boot (no injected rag, no credentials) -------------------------
def test_default_boot_health_is_degraded():
    from fastapi.testclient import TestClient

    from app.main import app

    # No app.state.rag override and no keys -> embeddings/llm not ready, but the
    # endpoint must still return 200 (the CI smoke expectation). The lifespan
    # builds a default RAGSystem which degrades gracefully offline.
    with TestClient(app) as client:
        resp = client.get("/api/health")
    assert resp.status_code == 200
    health = HealthResponse(**resp.json())
    assert health.status in {"ok", "degraded"}


def test_default_boot_root_is_200():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
