"""Prompt templates for the compliance-checking workflow."""

from __future__ import annotations

import json
from typing import Any

SYSTEM_EXTRACT = (
    "You are a senior building-plan examiner for the Kerala Local Self-Government "
    "Department. You are given the raw text of a submitted building plan. Extract "
    "the measurable planning parameters that Kerala Building Rules regulate. "
    "Return ONLY a bullet list, one parameter per line, in the form "
    "'- <parameter>: <value>'. Include: plot area, built-up area, floor space "
    "index (FSI), number of floors, building height, front/rear/side setbacks, "
    "road width abutting the plot, parking provision, occupancy/usage type, and "
    "any fire-safety or staircase details mentioned. If a value is not stated, "
    "write 'not specified'. Do not invent values."
)

SYSTEM_ANALYZE = (
    "You are a Kerala Building Rules compliance auditor. You will receive (1) the "
    "extracted planning facts of a submitted building plan, and (2) excerpts from "
    "the Kerala Building Rules that were retrieved as relevant. Determine the "
    "POTENTIAL violations by comparing the facts against the rules. You must ONLY "
    "base findings on the provided excerpts; if the excerpts do not cover a fact, "
    "mark it 'needs review - rule not retrieved'. "
    "Respond with strict JSON only, no prose, in this schema:\n"
    "{\n"
    '  "violations": [\n'
    "    {\n"
    '      "rule_reference": "<rule/section identifier from the excerpt>",\n'
    '      "severity": "high | medium | low | info",\n'
    '      "description": "<what the potential violation is>",\n'
    '      "plan_value": "<value from the plan, or null>",\n'
    '      "required_value": "<what the rule requires, or null>"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "If no potential violations are identifiable from the excerpts, return an empty "
    "violations array."
)

SYSTEM_SUMMARY = (
    "You are preparing a compliance report for an LSGD engineer. Given the "
    "extracted plan facts and the structured list of potential violations, write a "
    "concise, professional summary (3-6 sentences). State the overall risk level, "
    "the most serious issues, and recommend next steps. Do not fabricate rule "
    "numbers beyond what is provided."
)

PROMPT_ANALYZE_USER = (
    "EXTRACTED PLAN FACTS:\n{facts}\n\n"
    "RETRIEVED KERALA BUILDING RULE EXCERPTS:\n{rules}\n\n"
    "Return the JSON analysis now."
)


def build_analyze_user(facts: str, rules: str) -> str:
    return PROMPT_ANALYZE_USER.format(facts=facts, rules=rules)


def format_rules_for_prompt(rules: list[tuple[str, dict, float]]) -> str:
    lines = []
    for i, (text, meta, _score) in enumerate(rules, start=1):
        src = meta.get("source", "unknown")
        rid = meta.get("rule_id") or meta.get("chunk", i)
        lines.append(f"[{i}] ({src} / {rid})\n{text}")
    return "\n\n".join(lines)


SYSTEM_DOUBLE_CHECK = (
    "You are an independent Senior Kerala Building Rules (KMBR/KPBR) compliance auditor. "
    "Your objective is to conduct a rigorous, adversarial double-check of candidate building violations "
    "identified by an initial examiner.\n\n"
    "You will receive:\n"
    "1. EXTRACTED PLAN FACTS: Measurable parameters from the submitted building plan.\n"
    "2. RETRIEVED KERALA BUILDING RULE EXCERPTS: The governing statutory rules.\n"
    "3. PRIMARY MODEL CANDIDATE VIOLATIONS: Proposed violations flagged by the primary examiner.\n\n"
    "Audit the candidate violations on 4 critical axes:\n"
    "1. Grounding & Hallucinations: Verify that every cited rule and clause actually exists in "
    "the retrieved excerpts. Reject fabricated or ungrounded rule numbers.\n"
    "2. False Positives & Statutory Concessions: Check if statutory exceptions or concessions apply "
    "(e.g., Chapter VI Rule 27 small-plot concessions for plots up to 300 sq.m / 3 Ares, where minimum "
    "setbacks and coverage requirements are relaxed). Eliminate spurious violations where the plan "
    "qualifies for statutory exemptions.\n"
    "3. Missed Violations (False Negatives): Check if obvious non-compliant parameters in the extracted "
    "facts were overlooked by the primary examiner based on the retrieved rules. Add them if supported.\n"
    "4. Parameter & Value Accuracy: Verify numerical calculations, dimensions, and threshold comparisons "
    "(e.g., setbacks, FSI, coverage, building height, access road width). Correct mismatched values.\n\n"
    "Return strict JSON only (no markdown code blocks, no preamble, no prose) following this exact schema:\n"
    "{\n"
    '  "status": "confirmed" | "flagged_discrepancy" | "adjusted",\n'
    '  "confidence_score": <float between 0.0 and 1.0>,\n'
    '  "cross_check_notes": "<concise auditor synthesis explaining the rationale, adjustments, or confirmation>",\n'
    '  "discrepancies": [\n'
    "    {\n"
    '      "rule_reference": "<rule/section identifier>",\n'
    '      "type": "false_positive" | "hallucination" | "missed_violation" | "value_mismatch",\n'
    '      "description": "<detailed explanation of what was wrong and why>",\n'
    '      "primary_finding": "<what primary examiner concluded, or null>",\n'
    '      "verifier_finding": "<what the auditor determined>"\n'
    "    }\n"
    "  ],\n"
    '  "final_violations": [\n'
    "    {\n"
    '      "rule_reference": "<statutory rule identifier>",\n'
    '      "severity": "high" | "medium" | "low" | "info",\n'
    '      "description": "<exact violation description>",\n'
    '      "plan_value": "<value from plan or null>",\n'
    '      "required_value": "<required statutory threshold or null>"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "Guidelines for status:\n"
    "- 'confirmed': Primary candidate violations are fully grounded, accurate, and require no changes (discrepancies list is empty).\n"
    "- 'adjusted': Violations were modified, false positives removed, or missed violations added. final_violations contains the vetted set.\n"
    "- 'flagged_discrepancy': Discrepancies exist that warrant manual engineer review."
)

PROMPT_DOUBLE_CHECK_USER = (
    "EXTRACTED PLAN FACTS:\n{facts}\n\n"
    "RETRIEVED KERALA BUILDING RULE EXCERPTS:\n{rules}\n\n"
    "PRIMARY MODEL CANDIDATE VIOLATIONS:\n{primary_violations}\n\n"
    "Perform the compliance audit and return strict JSON now."
)


def build_verify_user(facts: str, rules: str, primary_violations: Any) -> str:
    if isinstance(primary_violations, (list, dict)):
        try:
            serialized = []
            if isinstance(primary_violations, list):
                for item in primary_violations:
                    if hasattr(item, "model_dump"):
                        serialized.append(item.model_dump())
                    elif hasattr(item, "dict"):
                        serialized.append(item.dict())
                    else:
                        serialized.append(item)
            else:
                serialized = primary_violations
            formatted_violations = json.dumps(serialized, indent=2)
        except Exception:
            formatted_violations = str(primary_violations)
    else:
        formatted_violations = str(primary_violations)

    return PROMPT_DOUBLE_CHECK_USER.format(
        facts=facts,
        rules=rules,
        primary_violations=formatted_violations,
    )
