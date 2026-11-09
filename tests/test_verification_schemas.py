"""Tests for dual LLM verification response schemas and prompts."""

from __future__ import annotations

import json

from app.rag.prompts import (
    PROMPT_DOUBLE_CHECK_USER,
    SYSTEM_DOUBLE_CHECK,
    build_verify_user,
)
from app.schemas import (
    ComplianceResponse,
    DiscrepancyItem,
    HealthResponse,
    RuleReference,
    VerificationResult,
    Violation,
)


def test_discrepancy_item_validation():
    """Verify DiscrepancyItem fields and serialization."""
    item = DiscrepancyItem(
        rule_reference="Chapter VI Rule 27",
        type="false_positive",
        description="Plot area is 250 sq.m (<= 3 Ares), exempt under small-plot concession",
        primary_finding="Rear setback of 1.5m violates general 2.0m rule",
        verifier_finding="Rear setback permitted up to 1.0m under Rule 27 concession",
    )
    assert item.rule_reference == "Chapter VI Rule 27"
    assert item.type == "false_positive"
    assert "small-plot concession" in item.description

    dumped = item.model_dump()
    assert dumped["type"] == "false_positive"
    assert dumped["primary_finding"] is not None
    assert dumped["verifier_finding"] is not None


def test_verification_result_confirmed_status():
    """Verify VerificationResult with confirmed status and default values."""
    res = VerificationResult(
        status="confirmed",
        verified_by_model="gpt-4o-mini",
        confidence_score=0.98,
        cross_check_notes="All primary violations verified against Chapter IV and VI rules.",
        discrepancies=[],
        primary_violations_count=2,
        final_violations_count=2,
    )
    assert res.status == "confirmed"
    assert res.verified_by_model == "gpt-4o-mini"
    assert res.confidence_score == 0.98
    assert len(res.discrepancies) == 0
    assert res.primary_violations_count == 2
    assert res.final_violations_count == 2

    # Check serialization
    payload = res.model_dump()
    assert payload["status"] == "confirmed"
    assert json.loads(res.model_dump_json())["status"] == "confirmed"


def test_verification_result_adjusted_with_discrepancies():
    """Verify VerificationResult with adjusted status and discrepancy items."""
    discrepancy = DiscrepancyItem(
        rule_reference="Rule 34(2)",
        type="hallucination",
        description="Rule 34(2) does not exist in retrieved statutory excerpts",
        primary_finding="Flagged stair width violation under Rule 34(2)",
        verifier_finding="Removed hallucinated rule reference",
    )
    res = VerificationResult(
        status="adjusted",
        verified_by_model="llama-3.3-70b-versatile",
        confidence_score=0.92,
        cross_check_notes="Removed 1 hallucinated rule reference.",
        discrepancies=[discrepancy],
        primary_violations_count=3,
        final_violations_count=2,
    )
    assert res.status == "adjusted"
    assert len(res.discrepancies) == 1
    assert res.discrepancies[0].type == "hallucination"
    assert res.primary_violations_count == 3
    assert res.final_violations_count == 2


def test_compliance_response_backwards_compatible_without_verification():
    """ComplianceResponse must instantiate cleanly without verification field (default None)."""
    resp = ComplianceResponse(
        extracted_facts=["Plot area: 500 sq.m", "Height: 12m"],
        summary="Building complies with general requirements.",
        violations=[
            Violation(
                rule_reference="Rule 24",
                severity="medium",
                description="Front setback insufficient",
                plan_value="2.5m",
                required_value="3.0m",
            )
        ],
        retrieved_rules=[
            RuleReference(
                source="kmbr_2019.pdf",
                rule_id="Rule 24",
                excerpt="Front setback must be at least 3m...",
                score=0.88,
            )
        ],
    )
    assert resp.verification is None
    dumped = resp.model_dump()
    assert "verification" in dumped
    assert dumped["verification"] is None


def test_compliance_response_with_verification():
    """ComplianceResponse accepts full VerificationResult."""
    verification_payload = VerificationResult(
        status="confirmed",
        verified_by_model="gpt-4o-mini",
        confidence_score=0.95,
        cross_check_notes="Double-checked and confirmed.",
        primary_violations_count=1,
        final_violations_count=1,
    )
    resp = ComplianceResponse(
        extracted_facts=["Plot area: 500 sq.m"],
        summary="Compliant.",
        violations=[],
        retrieved_rules=[],
        verification=verification_payload,
    )
    assert resp.verification is not None
    assert resp.verification.status == "confirmed"
    assert resp.verification.verified_by_model == "gpt-4o-mini"
    assert resp.verification.confidence_score == 0.95


def test_health_response_verifier_fields():
    """HealthResponse includes default and custom verifier fields."""
    # Defaults
    default_health = HealthResponse(
        status="ok",
        index_size=100,
        embeddings_ready=True,
        llm_ready=True,
    )
    assert default_health.verifier_enabled is False
    assert default_health.verifier_provider is None
    assert default_health.verifier_model is None
    assert default_health.verifier_ready is False

    # Configured
    active_health = HealthResponse(
        status="ok",
        index_size=100,
        embeddings_ready=True,
        llm_ready=True,
        verifier_enabled=True,
        verifier_provider="openai",
        verifier_model="gpt-4o-mini",
        verifier_ready=True,
    )
    assert active_health.verifier_enabled is True
    assert active_health.verifier_provider == "openai"
    assert active_health.verifier_model == "gpt-4o-mini"
    assert active_health.verifier_ready is True

    payload = active_health.model_dump()
    assert payload["verifier_ready"] is True
    assert payload["verifier_model"] == "gpt-4o-mini"


def test_prompts_and_build_verify_user():
    """Verify double-check system prompt and user prompt builder."""
    assert "independent Senior Kerala Building Rules" in SYSTEM_DOUBLE_CHECK
    assert "Grounding & Hallucinations" in SYSTEM_DOUBLE_CHECK
    assert "Chapter VI Rule 27 small-plot concessions" in SYSTEM_DOUBLE_CHECK
    assert "Missed Violations" in SYSTEM_DOUBLE_CHECK
    assert "Parameter & Value Accuracy" in SYSTEM_DOUBLE_CHECK
    assert "PRIMARY MODEL CANDIDATE VIOLATIONS" in PROMPT_DOUBLE_CHECK_USER

    facts = "Plot area: 280 sq.m, Height: 9.5m"
    rules = "[1] (kmbr / R27) Small plot concessions apply for plots <= 300 sq.m"
    candidate_violations = [
        Violation(
            rule_reference="Rule 25",
            severity="high",
            description="Rear setback 1.2m is less than 1.5m",
            plan_value="1.2m",
            required_value="1.5m",
        )
    ]

    prompt = build_verify_user(facts, rules, candidate_violations)
    assert "EXTRACTED PLAN FACTS:" in prompt
    assert facts in prompt
    assert "RETRIEVED KERALA BUILDING RULE EXCERPTS:" in prompt
    assert rules in prompt
    assert "PRIMARY MODEL CANDIDATE VIOLATIONS:" in prompt
    assert "Rule 25" in prompt
    assert "Rear setback 1.2m" in prompt
