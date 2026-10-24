"""KMBR / KPBR 2019 Table 7 & 8: Off-Street Parking Requirements.

Governed by Rule 29:
- Dictates minimum car parking spaces based on Occupancy Group and total built-up area.
- Group A1 residential dwellings under 150 m² are exempt from mandatory car parking.
- Commercial, assembly, and office occupancies have strict parking-per-square-metre quotas.
"""

from __future__ import annotations

import math
from app.rules.models import OccupancyGroup


def calculate_required_parking(
    occupancy: OccupancyGroup, built_up_area_sqm: float
) -> int:
    """Calculate the statutory minimum car parking slots required."""
    if built_up_area_sqm <= 0:
        return 0

    if occupancy == OccupancyGroup.A1_RESIDENTIAL:
        # Residential:
        # <= 150 sqm: Nil (exempt)
        # 151 - 300 sqm: 1 slot
        # > 300 sqm: 1 + 1 slot for every additional 150 sqm (or fraction)
        if built_up_area_sqm <= 150.0:
            return 0
        elif built_up_area_sqm <= 300.0:
            return 1
        else:
            excess = built_up_area_sqm - 300.0
            extra_slots = math.ceil(excess / 150.0)
            return 1 + extra_slots

    elif occupancy == OccupancyGroup.F_MERCANTILE:
        # 1 slot for every 60 m² of built-up area
        return max(1, math.ceil(built_up_area_sqm / 60.0))

    elif occupancy == OccupancyGroup.E_OFFICE:
        # 1 slot for every 75 m² of built-up area
        return max(1, math.ceil(built_up_area_sqm / 75.0))

    elif occupancy == OccupancyGroup.C_MEDICAL:
        # 1 slot for every 75 m² of built-up area
        return max(1, math.ceil(built_up_area_sqm / 75.0))

    elif occupancy == OccupancyGroup.D_ASSEMBLY:
        # 1 slot for every 30 m² of built-up area
        return max(1, math.ceil(built_up_area_sqm / 30.0))

    elif occupancy == OccupancyGroup.B_EDUCATIONAL:
        # 1 slot for every 150 m² of built-up area
        return max(1, math.ceil(built_up_area_sqm / 150.0))

    elif occupancy in (
        OccupancyGroup.G1_INDUSTRIAL_NON_HAZARDOUS,
        OccupancyGroup.G2_INDUSTRIAL_HAZARDOUS,
        OccupancyGroup.H_STORAGE,
    ):
        # 1 slot for every 200 m² of built-up area
        return max(1, math.ceil(built_up_area_sqm / 200.0))

    # General fallback
    return max(0, math.ceil(built_up_area_sqm / 100.0))
