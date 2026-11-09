"""Tests for the dual LLM verification node and V1 LangGraph state machine integration."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
import pytest

from app.rag.graph import (
    ComplianceState,
    Context,
    build_async_compliance_graph,
    build_compliance_graph,
    verify_analysis,
)
from app.rag.system import RAGSystem
from app.schemas import ComplianceResponse, VerificationResult
from tests.conftest import FakeEmbeddingProvider, FakeLLM, make_populated_store_into


class MockVerifierLLM:
    """Mock verifier client simulating secondary LLM responses."""

    def __init__(
        self,
        response_json: Optional[Dict[str, Any]] = None,
        model: str = "gpt-4o-mini",
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
            raise RuntimeError("Secondary verifier connection timed out")
        if self.malformed_json:
            return "This is not valid JSON at all: {broken,"
        if self.response_json is not None:
            return json.dumps(self.response_json)
        return json.dumps({"status": "confirmed", "final_violations": []})


SAMPLE_PRIMARY_VIOLATIONS = [
    {
        "rule_reference": "Rule 24(1)",
        "severity": "high",
        "description": "Front setback is 1.5m, required 3.0m.",
        "plan_value": "1.5m",
        "required_value": "3.0m",
    },
    {
        "rule_reference": "Rule 27",
        "severity": "medium",
        "description": "Rear setback is 1.2m, required 2.0m.",
        "plan_value": "1.2m",
        "required_value": "2.0m",
    },
]

SAMPLE_FACTS = (
    "- plot area: 250 sq.m\n"
    "- number of floors: 2\n"
    "- building height: 7m\n"
    "- front setback: 1.5m\n"
    "- rear setback: 1.2m"
)

SAMPLE_RETRIEVED = [
    (
        "Rule 24(1): Minimum front setback for residential buildings is 3.0m.",
        {"source": "KMBR 2019", "rule_id": "Rule 24(1)"},
        0.88,
    ),
    (
        "Rule 27: Small plot concessions apply for plots not exceeding 3 Ares (300 sq.m). "
        "Rear setback may be reduced to 1.0m for residential buildings under 10m height.",
        {"source": "KMBR 2019", "rule_id": "Rule 27"},
        0.85,
    ),
]


def test_verify_analysis_skipped_when_verifier_llm_none():
    """When verifier_llm is None, verify_analysis skips with zero overhead."""
    ctx = Context(llm=FakeLLM(), store=None, verifier_llm=None)
    state: ComplianceState = {
        "facts": SAMPLE_FACTS,
        "retrieved": SAMPLE_RETRIEVED,
        "violations": list(SAMPLE_PRIMARY_VIOLATIONS),
    }

    result = verify_analysis(state, ctx)
    assert result["primary_violations"] == SAMPLE_PRIMARY_VIOLATIONS
    assert result["verification"]["status"] == "skipped"
    assert result["verification"]["reason"] == "verifier_disabled"
    assert result["verification"]["primary_violations_count"] == 2
    assert result["verification"]["final_violations_count"] == 2
    assert "verify_analysis" in result["telemetry"]


def test_verify_analysis_confirms_valid_violations():
    """When verifier agrees with candidate violations, status is confirmed."""
    verifier_payload = {
        "status": "confirmed",
        "confidence_score": 0.98,
        "cross_check_notes": "All violations grounded in Rule 24 and Rule 27.",
        "discrepancies": [],
        "final_violations": SAMPLE_PRIMARY_VIOLATIONS,
    }
    verifier = MockVerifierLLM(response_json=verifier_payload, model="deepseek-r1")
    ctx = Context(llm=FakeLLM(), store=None, verifier_llm=verifier)
    state: ComplianceState = {
        "facts": SAMPLE_FACTS,
        "retrieved": SAMPLE_RETRIEVED,
        "violations": list(SAMPLE_PRIMARY_VIOLATIONS),
    }

    result = verify_analysis(state, ctx)
    assert result["primary_violations"] == SAMPLE_PRIMARY_VIOLATIONS
    assert result["violations"] == SAMPLE_PRIMARY_VIOLATIONS
    v_data = result["verification"]
    assert v_data["status"] == "confirmed"
    assert v_data["verified_by_model"] == "deepseek-r1"
    assert v_data["confidence_score"] == 0.98
    assert v_data["discrepancies"] == []
    assert v_data["primary_violations_count"] == 2
    assert v_data["final_violations_count"] == 2
    assert len(verifier.calls) == 1


def test_verify_analysis_removes_false_positive_and_records_discrepancy():
    """Under Rule 27 small-plot concession, rear setback of 1.2m is permitted (not a violation)."""
    vetted_violations = [SAMPLE_PRIMARY_VIOLATIONS[0]]  # Only Rule 24(1) front setback remains
    verifier_payload = {
        "status": "adjusted",
        "confidence_score": 0.96,
        "cross_check_notes": (
            "Removed rear setback violation under Rule 27 small-plot concession: "
            "plot is 250 sq.m (<= 300 sq.m), requiring only 1.0m rear setback; plan provides 1.2m."
        ),
        "discrepancies": [
            {
                "rule_reference": "Rule 27",
                "type": "false_positive",
                "description": "Plot area 250 sq.m qualifies for Chapter VI Rule 27 concession. Rear setback of 1.2m complies.",
                "primary_finding": "Rear setback is 1.2m, required 2.0m.",
                "verifier_finding": "1.2m exceeds 1.0m small-plot concession requirement. No violation.",
            }
        ],
        "final_violations": vetted_violations,
    }
    verifier = MockVerifierLLM(response_json=verifier_payload, model="gpt-4o-mini")
    ctx = Context(llm=FakeLLM(), store=None, verifier_llm=verifier)
    state: ComplianceState = {
        "facts": SAMPLE_FACTS,
        "retrieved": SAMPLE_RETRIEVED,
        "violations": list(SAMPLE_PRIMARY_VIOLATIONS),
    }

    result = verify_analysis(state, ctx)
    assert len(result["primary_violations"]) == 2
    assert len(result["violations"]) == 1
    assert result["violations"][0]["rule_reference"] == "Rule 24(1)"

    v_data = result["verification"]
    assert v_data["status"] == "adjusted"
    assert v_data["primary_violations_count"] == 2
    assert v_data["final_violations_count"] == 1
    assert len(v_data["discrepancies"]) == 1
    assert v_data["discrepancies"][0]["type"] == "false_positive"
    assert v_data["discrepancies"][0]["rule_reference"] == "Rule 27"


def test_verify_analysis_removes_hallucinations_and_records_discrepancy():
    """Verifier identifies and purges hallucinated rules not found in retrieved excerpts."""
    hallucinated_violation = {
        "rule_reference": "Rule 999(Z)",
        "severity": "high",
        "description": "Solar panel orientation must be exactly 180 degrees south.",
        "plan_value": "150 deg",
        "required_value": "180 deg",
    }
    primary_with_hallucination = [SAMPLE_PRIMARY_VIOLATIONS[0], hallucinated_violation]

    verifier_payload = {
        "status": "adjusted",
        "confidence_score": 0.94,
        "cross_check_notes": "Removed Rule 999(Z) as it does not exist in KMBR.",
        "discrepancies": [
            {
                "rule_reference": "Rule 999(Z)",
                "type": "hallucination",
                "description": "Rule 999(Z) is completely fabricated and absent from statutory rules.",
                "primary_finding": "Solar panel orientation violation under Rule 999(Z)",
                "verifier_finding": "Rule does not exist; pruned.",
            }
        ],
        "final_violations": [SAMPLE_PRIMARY_VIOLATIONS[0]],
    }
    verifier = MockVerifierLLM(response_json=verifier_payload)
    ctx = Context(llm=FakeLLM(), store=None, verifier_llm=verifier)
    state: ComplianceState = {
        "facts": SAMPLE_FACTS,
        "retrieved": SAMPLE_RETRIEVED,
        "violations": primary_with_hallucination,
    }

    result = verify_analysis(state, ctx)
    assert len(result["primary_violations"]) == 2
    assert len(result["violations"]) == 1
    assert result["violations"][0]["rule_reference"] == "Rule 24(1)"
    assert result["verification"]["discrepancies"][0]["type"] == "hallucination"


def test_verify_analysis_error_recovery_retains_primary_violations():
    """On verifier network timeout or exception, pipeline catches it, logs, and retains primary violations."""
    verifier = MockVerifierLLM(should_fail=True)
    ctx = Context(llm=FakeLLM(), store=None, verifier_llm=verifier)
    state: ComplianceState = {
        "facts": SAMPLE_FACTS,
        "retrieved": SAMPLE_RETRIEVED,
        "violations": list(SAMPLE_PRIMARY_VIOLATIONS),
    }

    result = verify_analysis(state, ctx)
    assert result["primary_violations"] == SAMPLE_PRIMARY_VIOLATIONS
    assert result["violations"] == SAMPLE_PRIMARY_VIOLATIONS
    assert result["verification"]["status"] == "error"
    assert "timed out" in result["verification"]["error"]
    assert result["verification"]["primary_violations_count"] == 2
    assert result["verification"]["final_violations_count"] == 2


def test_verify_analysis_malformed_json_fallback():
    """When verifier returns unparseable text, gracefully fall back to primary violations."""
    verifier = MockVerifierLLM(malformed_json=True)
    ctx = Context(llm=FakeLLM(), store=None, verifier_llm=verifier)
    state: ComplianceState = {
        "facts": SAMPLE_FACTS,
        "retrieved": SAMPLE_RETRIEVED,
        "violations": list(SAMPLE_PRIMARY_VIOLATIONS),
    }

    result = verify_analysis(state, ctx)
    assert result["violations"] == SAMPLE_PRIMARY_VIOLATIONS
    assert result["verification"]["status"] == "error"
    assert "JSON" in result["verification"]["error"]


def test_sync_compliance_graph_with_mock_verifier(tmp_path):
    """End-to-end sync compliance graph execution with mock verifier."""
    provider = FakeEmbeddingProvider()
    llm = FakeLLM(analyze_mode="ok")
    verifier = MockVerifierLLM(
        response_json={
            "status": "confirmed",
            "confidence_score": 0.99,
            "cross_check_notes": "Graph verification passed.",
            "discrepancies": [],
            "final_violations": [
                {
                    "rule_reference": "Rule 5",
                    "severity": "high",
                    "description": "Front setback below minimum.",
                    "plan_value": "1m",
                    "required_value": "1.8m",
                }
            ],
        }
    )

    from app.rag.vectorstore import RuleVectorStore

    store = RuleVectorStore(provider, str(tmp_path / "index"))
    store.load_or_create()
    make_populated_store_into(store)

    ctx = Context(llm=llm, store=store, verifier_llm=verifier)
    graph = build_compliance_graph(ctx)

    state = graph.invoke(
        {"plan_text": "3 floor building, 12m tall, 1m front setback", "top_k": 2}
    )

    assert "violations" in state
    assert len(state["violations"]) == 1
    assert "primary_violations" in state
    assert state["verification"]["status"] == "confirmed"
    assert len(verifier.calls) == 1


@pytest.mark.asyncio
async def test_async_compliance_graph_with_mock_verifier(tmp_path):
    """End-to-end async compliance graph execution with mock verifier."""
    provider = FakeEmbeddingProvider()
    llm = FakeLLM(analyze_mode="ok")
    verifier = MockVerifierLLM(
        response_json={
            "status": "confirmed",
            "confidence_score": 0.97,
            "cross_check_notes": "Async graph verification confirmed.",
            "discrepancies": [],
            "final_violations": [
                {
                    "rule_reference": "Rule 5",
                    "severity": "high",
                    "description": "Front setback below minimum.",
                    "plan_value": "1m",
                    "required_value": "1.8m",
                }
            ],
        }
    )

    from app.rag.vectorstore import RuleVectorStore

    store = RuleVectorStore(provider, str(tmp_path / "index"))
    store.load_or_create()
    make_populated_store_into(store)

    ctx = Context(llm=llm, store=store, verifier_llm=verifier)
    agraph = build_async_compliance_graph(ctx)

    state = await agraph.ainvoke(
        {"plan_text": "3 floor building, 12m tall, 1m front setback", "top_k": 2}
    )

    assert "violations" in state
    assert len(state["violations"]) == 1
    assert "primary_violations" in state
    assert state["verification"]["status"] == "confirmed"
    assert len(verifier.calls) == 1


def test_rag_system_check_integrates_verifier(tmp_path):
    """RAGSystem check shapes verification object and validates against ComplianceResponse."""
    provider = FakeEmbeddingProvider()
    llm = FakeLLM(analyze_mode="ok")
    verifier = MockVerifierLLM(
        response_json={
            "status": "adjusted",
            "confidence_score": 0.95,
            "cross_check_notes": "Adjusted in RAGSystem check.",
            "discrepancies": [
                {
                    "rule_reference": "Rule 5",
                    "type": "value_mismatch",
                    "description": "Corrected required value to 1.8m.",
                    "primary_finding": "1.5m",
                    "verifier_finding": "1.8m",
                }
            ],
            "final_violations": [
                {
                    "rule_reference": "Rule 5",
                    "severity": "high",
                    "description": "Front setback below minimum.",
                    "plan_value": "1m",
                    "required_value": "1.8m",
                }
            ],
        }
    )

    rag = RAGSystem(
        provider=provider,
        llm=llm,
        index_dir=str(tmp_path / "index"),
        verifier_llm=verifier,
    )
    make_populated_store_into(rag._store)

    result = rag.check("3 floor building, 12m tall, 1m front setback", top_k=2)

    assert "verification" in result
    assert result["verification"]["status"] == "adjusted"
    assert len(result["verification"]["discrepancies"]) == 1

    # Validate against Pydantic ComplianceResponse schema
    response = ComplianceResponse(**result)
    assert response.verification is not None
    assert isinstance(response.verification, VerificationResult)
    assert response.verification.status == "adjusted"
    assert response.verification.confidence_score == 0.95
