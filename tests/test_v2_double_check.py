"""Tests for the V2 Multi-Agent Statutory Verifier Node & Pipeline Integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag.multi_agent_graph import (
    build_multi_agent_graph,
    node_statutory_cross_checker,
)
from app.rules.models import Jurisdiction, OccupancyGroup, PlanFacts
from app.schemas import VerificationResult

client = TestClient(app)


class MockVerifierLLM:
    """Mock verifier client simulating secondary LLM responses in V2 pipeline."""

    def __init__(
        self,
        response_json: Optional[Dict[str, Any]] = None,
        model: str = "deepseek-r1",
        should_fail: bool = False,
        malformed_json: bool = False,
    ) -> None:
        self.response_json = response_json
        self.model = model
        self.provider = "mock_verifier"
        self.should_fail = should_fail
        self.malformed_json = malformed_json
        self.calls: List[Dict[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        if self.should_fail:
            raise RuntimeError("Secondary statutory verifier endpoint timeout")
        if self.malformed_json:
            return "Non-JSON response: [Error: unparseable text]"
        if self.response_json is not None:
            return json.dumps(self.response_json)
        return json.dumps(
            {
                "status": "confirmed",
                "confidence_score": 0.99,
                "cross_check_notes": "All symbolic evaluation findings verified against KBR 2019.",
                "discrepancies": [],
                "final_violations": [],
            }
        )


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "sample_v2_drawing.pdf"
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
def sample_state() -> Dict[str, Any]:
    facts = PlanFacts(
        jurisdiction=Jurisdiction.PANCHAYAT,
        occupancy=OccupancyGroup.A1_RESIDENTIAL,
        plot_area_sqm=300.0,
        built_up_area_sqm=210.0,
        ground_coverage_sqm=120.0,
        building_height_m=7.5,
        number_of_floors=2,
        road_width_m=4.0,
        front_setback_m=3.5,
        rear_setback_m=2.0,
        side_setback_1_m=1.5,
        side_setback_2_m=1.2,
        parking_slots_provided=1,
    )
    return {
        "plan_facts": facts,
        "classification": {
            "jurisdiction": "panchayat",
            "occupancy": "A1_RESIDENTIAL",
            "confidence": 0.95,
        },
        "symbolic_result": {
            "is_compliant": True,
            "violations": [],
            "rule_citations": ["KMBR/KPBR 2019 Rule 25", "KMBR/KPBR 2019 Rule 27"],
        },
        "critic_result": {
            "active_violations": [],
            "exonerated_violations": [],
            "is_compliant": True,
            "applied_concessions": ["Rule 27 Small Plot Setbacks"],
            "eligible_concessions": ["Rule 27 Small Plot Setbacks"],
        },
        "telemetry": {},
    }


def test_node_statutory_cross_checker_skipped_when_verifier_disabled(
    sample_state: Dict[str, Any], monkeypatch
):
    """When verifier is disabled, node returns status='skipped' with zero overhead."""
    monkeypatch.setattr("app.rag.multi_agent_graph.get_verifier_client", lambda: None)
    res = node_statutory_cross_checker(sample_state)

    assert "verification" in res
    assert res["verification"]["status"] == "skipped"
    assert res["verification"]["reason"] == "verifier_disabled"
    assert "verifier_ms" in res["telemetry"]


def test_node_statutory_cross_checker_executes_and_emits_verified_status(
    sample_state: Dict[str, Any], monkeypatch
):
    """When verifier mock is active, node audits plan facts and emits verified status."""
    verifier_payload = {
        "status": "confirmed",
        "confidence_score": 0.98,
        "cross_check_notes": "Statutory cross-check confirms full compliance with KPBR 2019.",
        "discrepancies": [],
        "final_violations": [],
    }
    mock_verifier = MockVerifierLLM(
        response_json=verifier_payload, model="qwen-2.5-32b"
    )
    monkeypatch.setattr(
        "app.rag.multi_agent_graph.get_verifier_client", lambda: mock_verifier
    )

    res = node_statutory_cross_checker(sample_state)

    assert "verification" in res
    v = res["verification"]
    assert v["status"] == "confirmed"
    assert v["verified_by_model"] == "qwen-2.5-32b"
    assert v["confidence_score"] == 0.98
    assert (
        v["cross_check_notes"]
        == "Statutory cross-check confirms full compliance with KPBR 2019."
    )
    assert v["discrepancies"] == []
    assert len(mock_verifier.calls) == 1

    # Verify Pydantic schema validation
    validated = VerificationResult(**v)
    assert validated.status == "confirmed"


def test_node_statutory_cross_checker_records_discrepancy(monkeypatch):
    """When verifier detects a discrepancy, it is captured in verification state."""
    discrepancy_payload = {
        "status": "flagged_discrepancy",
        "confidence_score": 0.91,
        "cross_check_notes": "Flagged potential false positive under Rule 27 small-plot clause.",
        "discrepancies": [
            {
                "rule_reference": "Rule 27",
                "type": "false_positive",
                "description": "Rear setback is 1.2m, which conforms to the 1.0m concession.",
                "primary_finding": "Rear setback 1.2m violates standard 2.0m requirement.",
                "verifier_finding": "Small-plot concession applies; compliant.",
            }
        ],
        "final_violations": [],
    }
    mock_verifier = MockVerifierLLM(
        response_json=discrepancy_payload, model="llama-3.3-70b"
    )
    monkeypatch.setattr(
        "app.rag.multi_agent_graph.get_verifier_client", lambda: mock_verifier
    )

    state = {
        "drawing_facts": {
            "plot_area_sqm": 250.0,
            "building_height_m": 7.0,
            "rear_setback_m": 1.2,
        },
        "evaluation": {
            "violations": [
                {
                    "parameter": "Rear Setback",
                    "observed": 1.2,
                    "required": 2.0,
                    "rule_citation": "Rule 25",
                }
            ],
            "rule_citations": ["Rule 25", "Rule 27"],
        },
    }

    res = node_statutory_cross_checker(state)
    v = res["verification"]
    assert v["status"] == "flagged_discrepancy"
    assert len(v["discrepancies"]) == 1
    assert v["discrepancies"][0]["type"] == "false_positive"
    assert v["discrepancies"][0]["rule_reference"] == "Rule 27"


def test_node_statutory_cross_checker_handles_exceptions_gracefully(
    sample_state: Dict[str, Any], monkeypatch
):
    """When verifier raises an exception, node catches it and returns error status."""
    failing_verifier = MockVerifierLLM(should_fail=True)
    monkeypatch.setattr(
        "app.rag.multi_agent_graph.get_verifier_client", lambda: failing_verifier
    )

    res = node_statutory_cross_checker(sample_state)

    assert "verification" in res
    v = res["verification"]
    assert v["status"] == "error"
    assert "timeout" in v["error"].lower()


def test_node_statutory_cross_checker_handles_malformed_json_gracefully(
    sample_state: Dict[str, Any], monkeypatch
):
    """When verifier emits unparseable non-JSON text, node records error status."""
    malformed_verifier = MockVerifierLLM(malformed_json=True)
    monkeypatch.setattr(
        "app.rag.multi_agent_graph.get_verifier_client", lambda: malformed_verifier
    )

    res = node_statutory_cross_checker(sample_state)

    assert "verification" in res
    v = res["verification"]
    assert v["status"] == "error"
    assert "json" in v["error"].lower()


@pytest.mark.asyncio
async def test_multi_agent_graph_integration_with_verifier(
    sample_pdf: Path, monkeypatch
):
    """Verify full graph execution with statutory cross-checker node active."""
    verifier_payload = {
        "status": "confirmed",
        "confidence_score": 0.97,
        "cross_check_notes": "End-to-end multi-agent verification verified all symbolic calculations.",
        "discrepancies": [],
        "final_violations": [],
    }
    mock_verifier = MockVerifierLLM(
        response_json=verifier_payload, model="nim/meta-llama-3"
    )
    monkeypatch.setattr(
        "app.rag.multi_agent_graph.get_verifier_client", lambda: mock_verifier
    )

    graph = build_multi_agent_graph()
    result = await graph.ainvoke({"pdf_path": str(sample_pdf)})

    assert "verification" in result
    assert result["verification"]["status"] == "confirmed"
    assert result["verification"]["verified_by_model"] == "nim/meta-llama-3"
    assert "verifier_ms" in result["telemetry"]


def test_api_v2_check_pdf_response_includes_verification(sample_pdf: Path, monkeypatch):
    """Verify POST /api/v2/check/pdf response includes the verification audit block."""
    # Test 1: Verifier disabled (default passthrough)
    monkeypatch.setattr("app.rag.multi_agent_graph.get_verifier_client", lambda: None)
    with open(sample_pdf, "rb") as f:
        resp = client.post(
            "/api/v2/check/pdf",
            files={"file": ("drawing.pdf", f, "application/pdf")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "verification" in data
    assert data["verification"]["status"] == "skipped"

    # Test 2: Verifier enabled with confirmed audit
    verifier_payload = {
        "status": "confirmed",
        "confidence_score": 0.99,
        "cross_check_notes": "Statutory cross-checker confirmed symbolic evaluation via REST API.",
        "discrepancies": [],
        "final_violations": [],
    }
    mock_verifier = MockVerifierLLM(
        response_json=verifier_payload, model="groq/llama-3.3-70b-versatile"
    )
    monkeypatch.setattr(
        "app.rag.multi_agent_graph.get_verifier_client", lambda: mock_verifier
    )
    with open(sample_pdf, "rb") as f:
        resp2 = client.post(
            "/api/v2/check/pdf",
            files={"file": ("drawing.pdf", f, "application/pdf")},
        )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert "verification" in data2
    assert data2["verification"]["status"] == "confirmed"
    assert data2["verification"]["verified_by_model"] == "groq/llama-3.3-70b-versatile"
    assert data2["verification"]["confidence_score"] == 0.99
