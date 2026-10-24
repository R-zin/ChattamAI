"""Deterministic compliance evaluator linking facts, tables, and statutory math.

Evaluates:
- Maximum Permissible Ground Coverage (%)
- Maximum Permissible Floor Space Index (FAR/FSI)
- Minimum Front, Rear, and Side Yards / Setbacks (m)
- Off-Street Parking Provisions (slots)
- Statutory Concessions (Chapter VI Small-Plot relaxations)

Returns an authoritative ComplianceEvaluation with exact mathematical justification.
"""

from __future__ import annotations

from typing import List
from app.rules.concessions import evaluate_concessions
from app.rules.models import (
    ComplianceEvaluation,
    OccupancyGroup,
    PlanFacts,
    RuleViolation,
)
from app.rules.tables_far import get_coverage_and_far
from app.rules.tables_parking import calculate_required_parking
from app.rules.tables_setbacks import calculate_required_setbacks


def evaluate_plan_facts(facts: PlanFacts) -> ComplianceEvaluation:
    """Run all deterministic KMBR/KPBR compliance inequalities against the plan."""
    violations: List[RuleViolation] = []
    citations: List[str] = []

    # 1. Statutory Concessions & Small-Plot Eligibility
    eligible_concessions, applied_concessions = evaluate_concessions(facts)
    is_small_plot = any("Small Plot" in c for c in eligible_concessions)

    # 2. Ground Coverage Check
    actual_coverage_pct = round(
        (facts.ground_coverage_sqm / facts.plot_area_sqm) * 100, 2
    )
    max_cov_pct, base_far, max_far, cov_citation = get_coverage_and_far(
        facts.occupancy,
        facts.road_width_m,
        facts.jurisdiction,
        facts.plot_area_sqm,
    )
    citations.append(cov_citation)

    # Chapter VI allows up to 75% coverage for small residential plots
    if is_small_plot and facts.occupancy == OccupancyGroup.A1_RESIDENTIAL:
        if max_cov_pct < 75.0:
            max_cov_pct = 75.0
            citations.append(
                "KMBR/KPBR Chapter VI Rule 27: Small plot coverage allowance up to 75%"
            )
            if actual_coverage_pct > 65.0:
                applied_concessions.append(
                    "Chapter VI: Coverage extended up to 75% for small plot"
                )

    if actual_coverage_pct > max_cov_pct:
        deficit = round(actual_coverage_pct - max_cov_pct, 2)
        violations.append(
            RuleViolation(
                rule_reference="Rule 24 / Table 4",
                parameter="Ground Coverage",
                severity="high",
                actual_value=actual_coverage_pct,
                required_value=max_cov_pct,
                unit="%",
                deficit=deficit,
                description=(
                    f"Ground coverage of {actual_coverage_pct}% exceeds the permissible maximum "
                    f"of {max_cov_pct}% by {deficit}%."
                ),
                statutory_clause="Table 4: Maximum Permissible Coverage and Floor Area Ratio",
                concession_applied="Chapter VI Small Plot" if is_small_plot else None,
                page_number=facts.source_pdf_page,
            )
        )

    # 3. Floor Area Ratio (FAR / FSI) Check
    actual_far = round(facts.built_up_area_sqm / facts.plot_area_sqm, 2)
    if actual_far > max_far:
        deficit = round(actual_far - max_far, 2)
        violations.append(
            RuleViolation(
                rule_reference="Rule 24 / Table 4",
                parameter="Floor Space Index (FAR/FSI)",
                severity="high",
                actual_value=actual_far,
                required_value=max_far,
                unit="ratio",
                deficit=deficit,
                description=(
                    f"Achieved FAR of {actual_far} exceeds maximum permissible limit of {max_far} "
                    f"(even with maximum additional fee under Rule 24)."
                ),
                statutory_clause="Table 4: Floor Area Ratio limits",
                page_number=facts.source_pdf_page,
            )
        )

    # 4. Setbacks Check (Front, Rear, Side 1, Side 2)
    req_setbacks = calculate_required_setbacks(
        facts.building_height_m,
        facts.road_width_m,
        facts.occupancy,
        is_small_plot=is_small_plot,
    )
    citations.append("KMBR/KPBR 2019 Rule 25 & Table 6: Open Spaces / Setbacks")

    setback_checks = [
        (
            "Front Setback",
            facts.front_setback_m,
            req_setbacks["front"],
            "Rule 25(1) / Table 6",
        ),
        (
            "Rear Setback",
            facts.rear_setback_m,
            req_setbacks["rear"],
            "Rule 25(2) / Table 6",
        ),
        (
            "Side Setback 1",
            facts.side_setback_1_m,
            req_setbacks["side_1"],
            "Rule 25(3) / Table 6",
        ),
        (
            "Side Setback 2",
            facts.side_setback_2_m,
            req_setbacks["side_2"],
            "Rule 25(3) / Table 6",
        ),
    ]

    for param, actual, required, ref in setback_checks:
        if actual < required:
            deficit = round(required - actual, 2)
            concession_note = (
                " (evaluated with Chapter VI Concessions)" if is_small_plot else ""
            )
            violations.append(
                RuleViolation(
                    rule_reference=ref,
                    parameter=param,
                    severity="high" if deficit >= 0.5 else "medium",
                    actual_value=actual,
                    required_value=required,
                    unit="m",
                    deficit=deficit,
                    description=(
                        f"{param} is {actual}m, but statutory minimum is {required}m "
                        f"(deficit of {deficit}m){concession_note}."
                    ),
                    statutory_clause=f"{ref}: Minimum open space requirement",
                    concession_applied="Chapter VI Small Plot"
                    if is_small_plot
                    else None,
                    page_number=facts.source_pdf_page,
                )
            )

    # 5. Parking Check
    req_parking = calculate_required_parking(facts.occupancy, facts.built_up_area_sqm)
    citations.append("KMBR/KPBR 2019 Rule 29 Table 8: Parking Provisions")

    if facts.parking_slots_provided < req_parking:
        deficit_slots = req_parking - facts.parking_slots_provided
        violations.append(
            RuleViolation(
                rule_reference="Rule 29 / Table 8",
                parameter="Car Parking Slots",
                severity="medium",
                actual_value=float(facts.parking_slots_provided),
                required_value=float(req_parking),
                unit="slots",
                deficit=float(deficit_slots),
                description=(
                    f"Plan provides {facts.parking_slots_provided} car parking space(s), but rule requires "
                    f"{req_parking} space(s) for {facts.built_up_area_sqm} m² built-up area."
                ),
                statutory_clause="Table 8: Off-street parking space requirements",
                page_number=facts.source_pdf_page,
            )
        )

    # 6. Overall Verdict
    is_compliant = len(violations) == 0
    if is_compliant:
        summary_verdict = "Fully Compliant with KMBR/KPBR 2019"
        if applied_concessions:
            summary_verdict += (
                f" (with {len(applied_concessions)} statutory concession(s) applied)"
            )
    else:
        summary_verdict = (
            f"Non-Compliant: {len(violations)} statutory violation"
            f"{'s' if len(violations) > 1 else ''} detected"
        )

    return ComplianceEvaluation(
        is_compliant=is_compliant,
        summary_verdict=summary_verdict,
        violations=violations,
        coverage_percent=actual_coverage_pct,
        max_coverage_percent=max_cov_pct,
        fsi_actual=actual_far,
        base_fsi=base_far,
        max_fsi_permitted=max_far,
        parking_required=req_parking,
        parking_slots_provided=facts.parking_slots_provided,
        concessions_eligible=eligible_concessions,
        applied_concessions=applied_concessions,
        rule_citations=list(dict.fromkeys(citations)),  # unique preserve order
    )
