"""LangGraph Multi-Agent Orchestrator for ChattamAI 2.0.

Cooperative cyclical workflow:
1. Intake & Extract (Architectural PDF or text) -> PlanFacts
2. Classifier Agent -> Determines statutory Jurisdiction & Occupancy Group
3. Symbolic Evaluator Node -> Zero-hallucination mathematical compliance checks
4. Statutory Critic Node -> Concession & legal exception validator (suppresses false positives)
5. Remediation Agent -> Actionable mathematical redesign proposals
6. Synthesizer -> Produces executive compliance verdict and telemetry
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import END, StateGraph

from app.pdf_intel.normalizer import build_plan_facts_from_pdf
from app.rag.agents.classifier import classify_submission
from app.rag.agents.remediation import generate_remediations
from app.rag.agents.statutory_critic import critique_violations
from app.rules.evaluator import evaluate_plan_facts
from app.rules.models import PlanFacts, RuleViolation


class MultiAgentComplianceState(TypedDict, total=False):
    pdf_path: Optional[str]
    plan_text: Optional[str]
    plan_facts: Optional[PlanFacts]
    classification: Optional[Dict[str, Any]]
    symbolic_result: Optional[Dict[str, Any]]
    critic_result: Optional[Dict[str, Any]]
    remediations: Optional[List[Dict[str, Any]]]
    executive_summary: Optional[str]
    telemetry: Optional[Dict[str, Any]]


def node_intake_and_extract(state: MultiAgentComplianceState) -> Dict[str, Any]:
    """Extract structured PlanFacts from architectural PDF or text input."""
    t0 = time.perf_counter()
    if state.get("plan_facts") is not None:
        facts = state["plan_facts"]
    elif state.get("pdf_path"):
        pdf_p = Path(state["pdf_path"])
        facts = build_plan_facts_from_pdf(pdf_p)
    else:
        # Fallback default plan facts from text
        from app.pdf_intel.drawing_extractor import classify_text_metadata
        text = state.get("plan_text", "")
        meta = classify_text_metadata(text)
        facts = PlanFacts(
            jurisdiction=meta["jurisdiction"],
            occupancy=meta["occupancy"],
            plot_area_sqm=200.0,
            built_up_area_sqm=180.0,
            ground_coverage_sqm=90.0,
            building_height_m=8.0,
            number_of_floors=2,
            road_width_m=4.0,
            front_setback_m=3.0,
            rear_setback_m=1.8,
            side_setback_1_m=1.4,
            side_setback_2_m=1.2,
            parking_slots_provided=1,
        )

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "plan_facts": facts,
        "telemetry": {"intake_ms": elapsed},
    }


def node_classify(state: MultiAgentComplianceState) -> Dict[str, Any]:
    """Classify the building submission to set proper statutory context."""
    t0 = time.perf_counter()
    facts = state["plan_facts"]
    classification = classify_submission(
        plan_text=state.get("plan_text", ""),
        declared_jurisdiction=facts.jurisdiction,
        declared_occupancy=facts.occupancy,
    )
    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "classification": classification,
        "telemetry": {**state.get("telemetry", {}), "classify_ms": elapsed},
    }


def node_symbolic_evaluator(state: MultiAgentComplianceState) -> Dict[str, Any]:
    """Run deterministic symbolic compliance evaluation on plan facts."""
    t0 = time.perf_counter()
    facts = state["plan_facts"]
    eval_result = evaluate_plan_facts(facts)
    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "symbolic_result": eval_result.model_dump(),
        "telemetry": {**state.get("telemetry", {}), "symbolic_eval_ms": elapsed},
    }


def node_statutory_critic(state: MultiAgentComplianceState) -> Dict[str, Any]:
    """Examine violations and apply statutory concessions to avoid false positives."""
    t0 = time.perf_counter()
    facts = state["plan_facts"]
    raw_violations_data = state["symbolic_result"]["violations"]
    raw_violations = [RuleViolation(**v) for v in raw_violations_data]

    critic_res = critique_violations(facts, raw_violations)
    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "critic_result": {
            "active_violations": [v.model_dump() for v in critic_res["active_violations"]],
            "exonerated_violations": critic_res["exonerated_violations"],
            "is_compliant": critic_res["is_compliant"],
            "applied_concessions": critic_res["applied_concessions"],
            "eligible_concessions": critic_res["eligible_concessions"],
        },
        "telemetry": {**state.get("telemetry", {}), "critic_ms": elapsed},
    }


def node_remediation(state: MultiAgentComplianceState) -> Dict[str, Any]:
    """Generate architectural recommendations for any remaining violations."""
    t0 = time.perf_counter()
    facts = state["plan_facts"]
    active_v_data = state["critic_result"]["active_violations"]
    active_v = [RuleViolation(**v) for v in active_v_data]

    remediations = generate_remediations(facts, active_v)
    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "remediations": remediations,
        "telemetry": {**state.get("telemetry", {}), "remediation_ms": elapsed},
    }


def node_synthesizer(state: MultiAgentComplianceState) -> Dict[str, Any]:
    """Generate executive summary and final compliance package."""
    t0 = time.perf_counter()
    facts = state["plan_facts"]
    critic = state["critic_result"]
    active_v = critic["active_violations"]
    concessions = critic["applied_concessions"]

    if len(active_v) == 0:
        summary = (
            f"Building plan is FULLY COMPLIANT with {facts.jurisdiction.value.capitalize()} "
            f"Building Rules (KPBR/KMBR 2019) for Group {facts.occupancy.value} Occupancy. "
            f"Ground coverage is {facts.ground_coverage_sqm:.1f} m² "
            f"({(facts.ground_coverage_sqm/facts.plot_area_sqm)*100:.1f}%), "
            f"and achieved FAR is {facts.built_up_area_sqm/facts.plot_area_sqm:.2f}."
        )
        if concessions:
            summary += f" Statutory concessions successfully applied: {', '.join(concessions)}."
    else:
        summary = (
            f"Building plan is NON-COMPLIANT. {len(active_v)} statutory violation"
            f"{'s' if len(active_v) > 1 else ''} detected requiring design revision. "
            f"Key issues: {', '.join(v['parameter'] for v in active_v)}. "
            f"Remediation actions generated."
        )

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "executive_summary": summary,
        "telemetry": {**state.get("telemetry", {}), "synthesizer_ms": elapsed},
    }


def build_multi_agent_graph():
    """Build and compile the multi-agent compliance LangGraph."""
    graph = StateGraph(MultiAgentComplianceState)
    graph.add_node("intake", node_intake_and_extract)
    graph.add_node("classify", node_classify)
    graph.add_node("symbolic_eval", node_symbolic_evaluator)
    graph.add_node("critic", node_statutory_critic)
    graph.add_node("remediation", node_remediation)
    graph.add_node("synthesizer", node_synthesizer)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "classify")
    graph.add_edge("classify", "symbolic_eval")
    graph.add_edge("symbolic_eval", "critic")
    graph.add_edge("critic", "remediation")
    graph.add_edge("remediation", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph.compile()
