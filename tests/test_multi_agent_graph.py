"""Unit and integration tests for the LangGraph Multi-Agent Orchestrator."""

from pathlib import Path
import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag.multi_agent_graph import build_multi_agent_graph

client = TestClient(app)


@pytest.fixture
def compliant_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "compliant.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text(
        (50, 50),
        "PROPOSED RESIDENTIAL BUILDING IN KERALA PANCHAYAT\n"
        "Plot Area: 300.00 Sq.m\n"
        "Ground Floor Area: 120.00 Sq.m\n"
        "Total Built-up Area: 210.00 Sq.m\n"
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
    return pdf_path


@pytest.fixture
def small_plot_concession_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "small_concession.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text(
        (50, 50),
        "PROPOSED VILLA ON SMALL PLOT - GRAMA PANCHAYAT\n"
        "Plot Area: 100.00 Sq.m\n"
        "Ground Floor Area: 60.00 Sq.m\n"
        "Total Built-up Area: 110.00 Sq.m\n"
        "Building Height: 6.50 m\n"
        "No. of Floors: 2\n"
        "Road Width: 3.00 m\n"
        "Front Setback: 2.00 m\n"  # Standard requires 3m, but concession requires 1.8m -> Compliant!
        "Rear Setback: 1.20 m\n"  # Standard requires 1.5m, concession requires 1.0m -> Compliant!
        "Side Setback 1: 1.00 m\n"
        "Side Setback 2: 0.80 m\n"
        "Car Parking: 0\n",
        fontsize=11,
    )
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def non_compliant_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "non_compliant.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text(
        (50, 50),
        "PROPOSED COMMERCIAL BUILDING - KOCHI MUNICIPALITY\n"
        "Plot Area: 400.00 Sq.m\n"
        "Ground Floor Area: 280.00 Sq.m\n"  # 70% coverage -> max is 60% for commercial!
        "Total Built-up Area: 500.00 Sq.m\n"
        "Building Height: 11.00 m\n"
        "No. of Floors: 3\n"
        "Road Width: 6.00 m\n"
        "Front Setback: 3.00 m\n"  # Commercial > 10m requires 5.0m front setback!
        "Rear Setback: 1.50 m\n"  # Commercial > 10m requires 2.5m rear setback!
        "Side Setback 1: 1.20 m\n"  # Commercial > 10m requires 2.0m side setback!
        "Side Setback 2: 1.00 m\n"
        "Car Parking: 2\n",  # 500 sqm commercial requires 9 slots!
        fontsize=11,
    )
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.mark.asyncio
async def test_multi_agent_graph_compliant_flow(compliant_pdf: Path):
    """Test full multi-agent flow on a compliant PDF."""
    graph = build_multi_agent_graph()
    result = await graph.ainvoke({"pdf_path": str(compliant_pdf)})
    
    assert result["critic_result"]["is_compliant"] is True
    assert len(result["critic_result"]["active_violations"]) == 0
    assert "FULLY COMPLIANT" in result["executive_summary"]
    assert "intake_ms" in result["telemetry"]
    assert "symbolic_eval_ms" in result["telemetry"]
    assert "critic_ms" in result["telemetry"]


@pytest.mark.asyncio
async def test_statutory_critic_concession_application(small_plot_concession_pdf: Path):
    """Test that Statutory Critic suppresses false positive violations under Rule 27."""
    graph = build_multi_agent_graph()
    result = await graph.ainvoke({"pdf_path": str(small_plot_concession_pdf)})
    
    critic = result["critic_result"]
    assert critic["is_compliant"] is True
    assert len(critic["active_violations"]) == 0
    assert len(critic["applied_concessions"]) > 0


@pytest.mark.asyncio
async def test_remediation_generation_on_violations(non_compliant_pdf: Path):
    """Test that Remediation Agent generates specific architectural fixes."""
    graph = build_multi_agent_graph()
    result = await graph.ainvoke({"pdf_path": str(non_compliant_pdf)})
    
    assert result["critic_result"]["is_compliant"] is False
    remediations = result["remediations"]
    assert len(remediations) > 0
    
    # Check that remediation contains concrete actions
    params_remediated = [r["parameter"] for r in remediations]
    assert "Ground Coverage" in params_remediated
    assert any("Setback" in p for p in params_remediated)


def test_api_v2_check_pdf_endpoint(compliant_pdf: Path):
    """Test POST /api/v2/check/pdf endpoint with multipart upload."""
    with open(compliant_pdf, "rb") as f:
        resp = client.post(
            "/api/v2/check/pdf",
            files={"file": ("plan.pdf", f, "application/pdf")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_compliant"] is True
    assert data["verdict"] == "Compliant"
    assert data["plan_facts"]["plot_area_sqm"] == 300.0
    assert "telemetry" in data
