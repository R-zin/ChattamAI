"""Unit tests for LSGD Compliance Audit Report Generator (V2) and K-Smart Export."""

from pathlib import Path
import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rules.evaluator import evaluate_plan_facts
from app.rules.models import (
    Jurisdiction,
    OccupancyGroup,
    PlanFacts,
)
from app.services.pdf_report_v2 import generate_compliance_pdf_report_v2

client = TestClient(app)


@pytest.fixture
def test_plan_facts() -> PlanFacts:
    return PlanFacts(
        jurisdiction=Jurisdiction.PANCHAYAT,
        occupancy=OccupancyGroup.A1_RESIDENTIAL,
        plot_area_sqm=250.0,
        ground_coverage_sqm=100.0,
        built_up_area_sqm=180.0,
        building_height_m=8.0,
        number_of_floors=2,
        road_width_m=4.5,
        front_setback_m=3.5,
        rear_setback_m=2.0,
        side_setback_1_m=1.5,
        side_setback_2_m=1.2,
        parking_slots_provided=1,
    )


def test_generate_compliance_pdf_report_bytes(test_plan_facts: PlanFacts):
    """Verify that PDFReportCanvas produces valid, readable PDF bytes."""
    evaluation = evaluate_plan_facts(test_plan_facts)
    pdf_bytes = generate_compliance_pdf_report_v2(
        facts=test_plan_facts,
        evaluation=evaluation,
        remediations=[],
        document_title="Sample Villa Permit Plan",
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf_bytes

    # Assert that PyMuPDF can parse and open the generated PDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) >= 1
    text = doc[0].get_text("text")
    assert "LOCAL SELF GOVERNMENT DEPARTMENT" in text
    assert "KERALA BUILDING RULES" in text
    assert "FULLY COMPLIANT" in text
    doc.close()


def test_pdf_report_with_violations():
    """Verify PDF report generation when violations and remediations are present."""
    bad_facts = PlanFacts(
        jurisdiction=Jurisdiction.MUNICIPALITY,
        occupancy=OccupancyGroup.A1_RESIDENTIAL,
        plot_area_sqm=200.0,
        ground_coverage_sqm=160.0,  # 80% coverage -> violates 65% limit
        built_up_area_sqm=220.0,
        building_height_m=8.0,
        number_of_floors=2,
        road_width_m=4.0,
        front_setback_m=2.2,  # violates 3.0m
        rear_setback_m=1.8,
        side_setback_1_m=1.4,
        side_setback_2_m=1.1,
        parking_slots_provided=1,
    )
    evaluation = evaluate_plan_facts(bad_facts)
    assert evaluation.is_compliant is False

    remediations = [
        {
            "parameter": "Front Setback",
            "deficit_summary": "Short by 0.8m",
            "action": "Recede front porch wall by 0.8m to satisfy Rule 25.",
        }
    ]

    pdf_bytes = generate_compliance_pdf_report_v2(
        facts=bad_facts,
        evaluation=evaluation,
        remediations=remediations,
        document_title="Non-Compliant Plan",
    )
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = doc[0].get_text("text")
    assert "NON-COMPLIANT" in text
    assert "ACTIONABLE ARCHITECTURAL REMEDIATION" in text
    doc.close()


def test_api_check_pdf_and_export_report_endpoint(tmp_path: Path):
    """Test POST /api/v2/check/pdf/export-report endpoint returns PDF stream."""
    pdf_path = tmp_path / "plan_to_export.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text(
        (50, 50),
        "PROPOSED RESIDENTIAL BUILDING IN KERALA PANCHAYAT\n"
        "Plot Area: 260.00 Sq.m\n"
        "Ground Floor Area: 100.00 Sq.m\n"
        "Total Built-up Area: 180.00 Sq.m\n"
        "Building Height: 7.50 m\n"
        "No. of Floors: 2\n"
        "Road Width: 4.00 m\n"
        "Front Setback: 3.50 m\n"
        "Rear Setback: 2.00 m\n"
        "Side Setback 1: 1.50 m\n"
        "Side Setback 2: 1.20 m\n"
        "Car Parking: 1\n",
        fontsize=11,
    )
    doc.save(str(pdf_path))
    doc.close()

    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/api/v2/check/pdf/export-report",
            files={"file": ("plan_to_export.pdf", f, "application/pdf")},
        )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content.startswith(b"%PDF-1.4")


def test_api_ksmart_export_endpoint(test_plan_facts: PlanFacts):
    """Test POST /api/v2/reports/ksmart endpoint produces standard schema."""
    evaluation = evaluate_plan_facts(test_plan_facts)
    payload = {
        "facts": test_plan_facts.model_dump(),
        "evaluation": evaluation.model_dump(),
        "remediations": [],
    }
    resp = client.post("/api/v2/reports/ksmart", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ksmart_metadata"]["statutory_rules"] == "KPBR_2019"
    assert data["ksmart_metadata"]["jurisdiction_type"] == "PANCHAYAT"
    assert data["compliance_summary"]["overall_status"] == "APPROVED"
    assert "violations_ledger" in data
    assert "statutory_concessions" in data
