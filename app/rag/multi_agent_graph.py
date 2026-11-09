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

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import END, StateGraph

from app.pdf_intel.normalizer import build_plan_facts_from_pdf
from app.rag.agents.classifier import classify_submission
from app.rag.agents.remediation import generate_remediations
from app.rag.agents.statutory_critic import critique_violations
from app.rag.graph import _extract_json
from app.rag.llm import get_verifier_client
from app.rag.prompts import SYSTEM_DOUBLE_CHECK, build_verify_user
from app.rules.evaluator import evaluate_plan_facts
from app.rules.models import Jurisdiction, OccupancyGroup, PlanFacts, RuleViolation

logger = logging.getLogger(__name__)


class MultiAgentComplianceState(TypedDict, total=False):
    pdf_path: Optional[str]
    plan_text: Optional[str]
    plan_facts: Optional[PlanFacts]
    drawing_facts: Optional[Any]
    classification: Optional[Dict[str, Any]]
    symbolic_result: Optional[Dict[str, Any]]
    evaluation: Optional[Dict[str, Any]]
    critic_result: Optional[Dict[str, Any]]
    verification: Optional[Dict[str, Any]]
    remediations: Optional[List[Dict[str, Any]]]
    executive_summary: Optional[str]
    telemetry: Optional[Dict[str, Any]]


MultiAgentState = MultiAgentComplianceState


async def node_intake_and_extract(state: MultiAgentComplianceState) -> Dict[str, Any]:
    """Extract structured PlanFacts from architectural PDF or text input."""
    t0 = time.perf_counter()
    if state.get("plan_facts") is not None:
        facts = state["plan_facts"]
    elif state.get("pdf_path"):
        pdf_p = Path(state["pdf_path"])
        facts = await asyncio.to_thread(build_plan_facts_from_pdf, pdf_p)
    else:
        # Fallback default plan facts from text
        from app.pdf_intel.drawing_extractor import classify_text_metadata

        text = state.get("plan_text", "")
        meta = classify_text_metadata(text)
        facts = PlanFacts(
            jurisdiction=meta.get("jurisdiction") or Jurisdiction.PANCHAYAT,
            occupancy=meta.get("occupancy") or OccupancyGroup.A1_RESIDENTIAL,
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

    # Reconcile PlanFacts with resolved classification if updated
    resolved_jurisdiction = classification["jurisdiction"]
    resolved_occupancy = classification["occupancy"]
    if (
        facts.jurisdiction != resolved_jurisdiction
        or facts.occupancy != resolved_occupancy
    ):
        facts = facts.model_copy(
            update={
                "jurisdiction": resolved_jurisdiction,
                "occupancy": resolved_occupancy,
            }
        )

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "plan_facts": facts,
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
            "active_violations": [
                v.model_dump() for v in critic_res["active_violations"]
            ],
            "exonerated_violations": critic_res["exonerated_violations"],
            "is_compliant": critic_res["is_compliant"],
            "applied_concessions": critic_res["applied_concessions"],
            "eligible_concessions": critic_res["eligible_concessions"],
        },
        "telemetry": {**state.get("telemetry", {}), "critic_ms": elapsed},
    }


def node_statutory_cross_checker(state: MultiAgentState) -> Dict[str, Any]:
    """Audit symbolic violations & exonerations against statutory nuances with secondary LLM."""
    t0 = time.perf_counter()
    verifier_llm = get_verifier_client()

    if verifier_llm is None:
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "verification": {"status": "skipped", "reason": "verifier_disabled"},
            "telemetry": {**state.get("telemetry", {}), "verifier_ms": elapsed},
        }

    # Extract facts from drawing_facts or plan_facts
    facts_obj = state.get("drawing_facts") or state.get("plan_facts")
    eval_dict = state.get("evaluation") or state.get("symbolic_result") or {}
    classification = state.get("classification") or {}
    critic_result = state.get("critic_result") or {}

    active_violations = (
        critic_result.get("active_violations")
        if critic_result.get("active_violations") is not None
        else eval_dict.get("violations", [])
    )
    exonerated_violations = critic_result.get("exonerated_violations", [])
    applied_concessions = critic_result.get("applied_concessions", [])

    try:
        # Format facts
        if hasattr(facts_obj, "model_dump"):
            facts_str = json.dumps(facts_obj.model_dump(), indent=2)
        elif isinstance(facts_obj, dict):
            facts_str = json.dumps(facts_obj, indent=2)
        else:
            facts_str = str(facts_obj or "")

        if classification:
            facts_str += f"\n\nClassification:\n{json.dumps(classification, indent=2)}"

        # Format governing statutory rules and excerpts
        rules_lines = [
            "Kerala Municipality / Panchayat Building Rules (KMBR / KPBR 2019)"
        ]
        if eval_dict.get("rule_citations"):
            rules_lines.append(f"Citations: {', '.join(eval_dict['rule_citations'])}")
        if exonerated_violations:
            rules_lines.append(
                f"Exonerated Violations (via statutory concessions):\n{json.dumps(exonerated_violations, indent=2)}"
            )
        if applied_concessions:
            rules_lines.append(
                f"Applied Statutory Concessions: {', '.join(applied_concessions)}"
            )
        rules_str = "\n\n".join(rules_lines)

        user_prompt = build_verify_user(facts_str, rules_str, active_violations)
        raw = verifier_llm.complete(SYSTEM_DOUBLE_CHECK, user_prompt)
        parsed = _extract_json(raw)

        elapsed = round((time.perf_counter() - t0) * 1000, 2)

        if parsed is None:
            logger.warning(
                "node_statutory_cross_checker: failed to parse JSON from verifier output: %r",
                (raw or "")[:120],
            )
            return {
                "verification": {
                    "status": "error",
                    "error": "Failed to extract valid JSON from verifier output",
                    "primary_violations_count": len(active_violations),
                    "final_violations_count": len(active_violations),
                },
                "telemetry": {**state.get("telemetry", {}), "verifier_ms": elapsed},
            }

        confidence = parsed.get("confidence_score", 1.0)
        try:
            confidence_score = float(confidence)
        except (TypeError, ValueError):
            confidence_score = 1.0

        final_violations = parsed.get("final_violations")
        final_count = (
            len(final_violations)
            if isinstance(final_violations, list)
            else len(active_violations)
        )

        verification_dict = {
            "status": parsed.get("status", "confirmed"),
            "verified_by_model": getattr(verifier_llm, "model", "custom"),
            "confidence_score": confidence_score,
            "cross_check_notes": parsed.get("cross_check_notes"),
            "discrepancies": parsed.get("discrepancies", []),
            "primary_violations_count": len(active_violations),
            "final_violations_count": final_count,
        }
        return {
            "verification": verification_dict,
            "telemetry": {**state.get("telemetry", {}), "verifier_ms": elapsed},
        }
    except Exception as exc:
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        logger.warning("node_statutory_cross_checker failed: %s", exc, exc_info=True)
        return {
            "verification": {
                "status": "error",
                "error": str(exc),
                "primary_violations_count": len(active_violations)
                if "active_violations" in locals()
                else 0,
                "final_violations_count": len(active_violations)
                if "active_violations" in locals()
                else 0,
            },
            "telemetry": {**state.get("telemetry", {}), "verifier_ms": elapsed},
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
            f"({(facts.ground_coverage_sqm / facts.plot_area_sqm) * 100:.1f}%), "
            f"and achieved FAR is {facts.built_up_area_sqm / facts.plot_area_sqm:.2f}."
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
    graph.add_node("statutory_cross_checker", node_statutory_cross_checker)
    graph.add_node("remediation", node_remediation)
    graph.add_node("synthesizer", node_synthesizer)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "classify")
    graph.add_edge("classify", "symbolic_eval")
    graph.add_edge("symbolic_eval", "critic")
    graph.add_edge("critic", "statutory_cross_checker")
    graph.add_edge("statutory_cross_checker", "remediation")
    graph.add_edge("remediation", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph.compile()


COMPILED_GRAPH = build_multi_agent_graph()


def get_multi_agent_graph():
    """Return the cached, pre-compiled singleton instance of the multi-agent graph."""
    global COMPILED_GRAPH
    if COMPILED_GRAPH is None:
        COMPILED_GRAPH = build_multi_agent_graph()
    return COMPILED_GRAPH
