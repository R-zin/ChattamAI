"""Tests for the PDF and HTML compliance report export endpoint (offline)."""

from __future__ import annotations

import io
import pypdf

PLAN = "3 floor building, 12m tall, 1m front setback"


def test_export_report_pdf(app_client):
    app_client.post("/api/check", json={"plan_text": PLAN})
    reports = app_client.get("/api/reports").json()
    assert reports
    target_id = reports[0]["report_id"]

    resp = app_client.get(f"/api/reports/{target_id}/export?format=pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment;" in resp.headers.get("content-disposition", "")
    assert (
        f"kbr_compliance_report_{target_id:06d}.pdf"
        in resp.headers["content-disposition"]
    )

    # Verify PDF content with pypdf
    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) >= 1
    page_text = reader.pages[0].extract_text()
    assert "BUILDING RULES COMPLIANCE ASSESSMENT REPORT" in page_text
    assert f"CHATTAM-REP-{target_id:06d}" in page_text


def test_export_report_html(app_client):
    app_client.post("/api/check", json={"plan_text": PLAN})
    reports = app_client.get("/api/reports").json()
    assert reports
    target_id = reports[0]["report_id"]

    resp = app_client.get(f"/api/reports/{target_id}/export?format=html")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    text = resp.text
    assert "<!DOCTYPE html>" in text
    assert f"CHATTAM-REP-{target_id:06d}" in text
    assert "Building Rules Compliance Assessment Report" in text


def test_export_report_not_found(app_client):
    resp = app_client.get("/api/reports/9999999/export")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Report not found"
