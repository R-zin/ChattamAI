"""Kerala Building Rules Concessions, Exemptions, and Statutory Relaxations.

Implements legal exceptions under KMBR/KPBR 2019:
- Chapter VI / Rule 27: Concessions for small plots not exceeding 1.25 ares (125 m² / ~3.08 cents).
- Rule 10(2): Low-risk single-dwelling self-certification eligibility.
- Road surrender concessions under Rule 26.
"""

from __future__ import annotations

from typing import List, Tuple
from app.rules.models import OccupancyGroup, PlanFacts


def evaluate_concessions(facts: PlanFacts) -> Tuple[List[str], List[str]]:
    """Determine eligible statutory concessions and which ones are actively applied.

    Returns:
    - eligible_concessions: All legal relaxations the plot qualifies for.
    - applied_concessions: Specific relaxations currently utilised to pass compliance.
    """
    eligible: List[str] = []
    applied: List[str] = []

    # 1. Chapter VI Small Plot Concession (Plot Area <= 125 sq.m / ~3.08 cents)
    is_small_plot = facts.plot_area_sqm <= 125.0 and facts.occupancy == OccupancyGroup.A1_RESIDENTIAL
    if is_small_plot:
        concession_name = "KMBR/KPBR 2019 Chapter VI: Small Plot Concessions (Plot Area <= 125 m²)"
        eligible.append(concession_name)

        # Check if plan actually needed the small plot setback concession to pass
        standard_front = 3.00
        concession_front = 1.80
        if concession_front <= facts.front_setback_m < standard_front:
            applied.append("Chapter VI Rule 27(1): Front Setback relaxed from 3.0m to 1.8m")

        standard_rear = 1.50
        concession_rear = 1.00
        if concession_rear <= facts.rear_setback_m < standard_rear:
            applied.append("Chapter VI Rule 27(2): Rear Setback relaxed from 1.5m to 1.0m")

        standard_side1 = 1.20
        concession_side1 = 0.90
        if concession_side1 <= facts.side_setback_1_m < standard_side1:
            applied.append("Chapter VI Rule 27(3): Side Yard 1 relaxed to 0.9m")

        standard_side2 = 1.00
        concession_side2 = 0.60
        if concession_side2 <= facts.side_setback_2_m < standard_side2:
            applied.append("Chapter VI Rule 27(3): Side Yard 2 relaxed to 0.6m")

    # 2. Rule 10(2) Low-Risk Residential Fast-Track
    is_low_risk = (
        facts.occupancy == OccupancyGroup.A1_RESIDENTIAL
        and facts.built_up_area_sqm <= 300.0
        and facts.building_height_m <= 7.0
        and facts.number_of_floors <= 2
    )
    if is_low_risk:
        eligible.append("Rule 10(2): Low-Risk Residential Deemed Permit Eligibility (Height <= 7m, Area <= 300m²)")

    # 3. Parking exemption for residential dwellings <= 150 sqm
    if facts.occupancy == OccupancyGroup.A1_RESIDENTIAL and facts.built_up_area_sqm <= 150.0:
        eligible.append("Rule 29 Table 8: Residential dwelling <= 150 m² parking exemption")
        if facts.parking_slots_provided == 0:
            applied.append("Table 8: Car parking slot requirement exempt (area <= 150 m²)")

    return eligible, applied
