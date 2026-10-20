"""Statutory Critic Agent: Eliminates false-positives by cross-checking exceptions and concessions."""

from __future__ import annotations

from typing import Any, Dict, List
from app.rules.concessions import evaluate_concessions
from app.rules.models import PlanFacts, RuleViolation


def critique_violations(
    facts: PlanFacts,
    violations: List[RuleViolation],
) -> Dict[str, Any]:
    """Examine flagged violations against statutory concessions and legal exceptions."""
    eligible_concessions, applied_concessions = evaluate_concessions(facts)
    is_small_plot = any("Small Plot" in c for c in eligible_concessions)

    active_violations: List[RuleViolation] = []
    exonerated_violations: List[Dict[str, Any]] = []

    for v in violations:
        # Check if small-plot concession exonerates setback violation
        if is_small_plot and "Setback" in v.parameter:
            # Check concession thresholds
            if v.parameter == "Front Setback" and v.actual_value >= 1.80:
                exonerated_violations.append({
                    "parameter": v.parameter,
                    "original_deficit": v.deficit,
                    "concession": "Chapter VI Rule 27(1): Front setback concession (>= 1.8m) applies.",
                })
                continue
            elif v.parameter == "Rear Setback" and v.actual_value >= 1.00:
                exonerated_violations.append({
                    "parameter": v.parameter,
                    "original_deficit": v.deficit,
                    "concession": "Chapter VI Rule 27(2): Rear setback concession (>= 1.0m) applies.",
                })
                continue
            elif "Side" in v.parameter and v.actual_value >= 0.60:
                exonerated_violations.append({
                    "parameter": v.parameter,
                    "original_deficit": v.deficit,
                    "concession": "Chapter VI Rule 27(3): Side yard concession (>= 0.6m) applies.",
                })
                continue

        # Check parking exemption for <= 150 sqm residential
        if v.parameter == "Car Parking Slots" and facts.built_up_area_sqm <= 150.0:
            exonerated_violations.append({
                "parameter": v.parameter,
                "original_deficit": v.deficit,
                "concession": "Rule 29 Table 8: Residential dwelling <= 150 m² is exempt from car parking.",
            })
            continue

        active_violations.append(v)

    return {
        "active_violations": active_violations,
        "exonerated_violations": exonerated_violations,
        "is_compliant": len(active_violations) == 0,
        "eligible_concessions": eligible_concessions,
        "applied_concessions": applied_concessions,
    }
