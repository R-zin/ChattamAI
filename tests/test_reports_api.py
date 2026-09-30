"""Tests for GET /api/reports and GET /api/reports/{id} endpoints (offline)."""

from __future__ import annotations

import io

from app.services.database import SessionLocal
from app.services.report_model import Report

PLAN = "3 floor building, 12m tall, 1m front setback"


def _report_count() -> int:
    db = SessionLocal()
    try:
        return db.query(Report).count()
    finally:
        db.close()


def test_list_reports_returns_array(app_client):
    # Post a check so at least one report exists
    resp_check = app_client.post("/api/check", json={"plan_text": PLAN})
    assert resp_check.status_code == 200

    resp = app_client.get("/api/reports")
    assert resp.status_code == 200
    reports = resp.json()
    assert isinstance(reports, list)
    assert len(reports) >= 1
    r = reports[0]
    assert "report_id" in r
    assert "status" in r
    assert "violations" in r


def test_list_reports_pagination(app_client):
    app_client.post("/api/check", json={"plan_text": PLAN})
    app_client.post("/api/check", json={"plan_text": PLAN})

    resp = app_client.get("/api/reports?limit=1&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_reports_status_filter(app_client):
    # Canned fake check yields "fail" status due to high severity violation
    app_client.post("/api/check", json={"plan_text": PLAN})

    resp_fail = app_client.get("/api/reports?status=fail")
    assert resp_fail.status_code == 200
    for r in resp_fail.json():
        assert r["status"] == "fail"


def test_get_report_by_id_success(app_client):
    app_client.post("/api/check", json={"plan_text": PLAN})
    reports = app_client.get("/api/reports").json()
    assert reports
    target_id = reports[0]["report_id"]

    resp = app_client.get(f"/api/reports/{target_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["report_id"] == target_id
    assert body["status"] == reports[0]["status"]


def test_get_report_by_id_404(app_client):
    resp = app_client.get("/api/reports/99999999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Report not found"


def test_upload_persists_report(app_client):
    before = _report_count()
    files = {"file": ("plan.txt", io.BytesIO(PLAN.encode("utf-8")), "text/plain")}
    resp = app_client.post("/api/check/upload", files=files)
    assert resp.status_code == 200
    assert _report_count() == before + 1

    reports = app_client.get("/api/reports?limit=1").json()
    assert reports[0]["source"] == "upload"
