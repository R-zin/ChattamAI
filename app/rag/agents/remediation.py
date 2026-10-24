"""Remediation Agent: Generates actionable architectural recommendations for violations."""

from __future__ import annotations

from typing import Any, Dict, List
from app.rules.models import PlanFacts, RuleViolation


def generate_remediations(
    facts: PlanFacts,
    violations: List[RuleViolation],
) -> List[Dict[str, Any]]:
    """Produce concrete, mathematically actionable remedies for each violation."""
    remediations: List[Dict[str, Any]] = []

    for v in violations:
        if v.parameter == "Ground Coverage":
            max_allowed_sqm = round(facts.plot_area_sqm * (v.required_value / 100.0), 2)
            excess_sqm = round(facts.ground_coverage_sqm - max_allowed_sqm, 2)
            remediations.append(
                {
                    "parameter": v.parameter,
                    "deficit_summary": f"Exceeds max permissible coverage by {v.deficit}% ({excess_sqm} m²)",
                    "action": (
                        f"Reduce ground floor footprint by at least {excess_sqm} m² (e.g. shift utility "
                        f"rooms or open car porch to upper levels or cantilevered first floor) to meet "
                        f"the {v.required_value}% statutory limit."
                    ),
                    "target_value": f"Max {max_allowed_sqm} m² ground coverage",
                }
            )

        elif "FAR" in v.parameter or "Floor Space Index" in v.parameter:
            max_allowed_built_up = round(facts.plot_area_sqm * v.required_value, 2)
            excess_sqm = round(facts.built_up_area_sqm - max_allowed_built_up, 2)
            remediations.append(
                {
                    "parameter": v.parameter,
                    "deficit_summary": f"Built-up area exceeds max permissible FAR of {v.required_value} by {excess_sqm} m²",
                    "action": (
                        f"Reduce total built-up area by at least {excess_sqm} m² across floors, or verify "
                        f"eligibility for additional purchasable FAR under Rule 24 (subject to LSGD fees)."
                    ),
                    "target_value": f"Max {max_allowed_built_up} m² total built-up area",
                }
            )

        elif "Setback" in v.parameter:
            remediations.append(
                {
                    "parameter": v.parameter,
                    "deficit_summary": f"Short by {v.deficit} m (provided {v.actual_value}m, required {v.required_value}m)",
                    "action": (
                        f"Recede the building line along the {v.parameter.lower()} by {v.deficit} m, "
                        f"or reduce projecting roof eaves / cantilevered balconies beyond 0.6m in this open yard."
                    ),
                    "target_value": f"Minimum {v.required_value} m clear setback",
                }
            )

        elif "Parking" in v.parameter:
            missing_slots = int(v.deficit)
            remediations.append(
                {
                    "parameter": v.parameter,
                    "deficit_summary": f"Short by {missing_slots} parking slot{'s' if missing_slots > 1 else ''}",
                    "action": (
                        f"Designate {missing_slots} additional standard car parking space{'s' if missing_slots > 1 else ''} "
                        f"(minimum size 2.5m x 5.0m each with unobstructed driveway access) within plot open space or stilt floor."
                    ),
                    "target_value": f"Minimum {int(v.required_value)} parking slots",
                }
            )

    return remediations
