"""KMBR / KPBR 2019 Table 4: Maximum Permissible Coverage and Floor Area Ratio (FAR/FSI).

Governed by Rule 24:
- Coverage is the percentage of the plot area covered by the ground floor plinth.
- FAR (Floor Space Index) is total built-up area divided by plot area.
- Base FAR is free of additional government fee; Max FAR requires additional fee.
- Road width restricts the maximum achievable FAR for higher-density developments.
"""

from __future__ import annotations

from typing import Tuple
from app.rules.models import Jurisdiction, OccupancyGroup


# Table 4 baseline records: (Max Coverage %, Base FAR, Max Achievable FAR)
TABLE_4_SPECS = {
    OccupancyGroup.A1_RESIDENTIAL: {
        "max_coverage": 65.0,
        "base_far": 2.75,
        "max_far": 4.00,
        "citation": "KMBR/KPBR 2019 Rule 24 Table 4 (Occupancy Group A1)",
    },
    OccupancyGroup.A2_SPECIAL_RESIDENTIAL: {
        "max_coverage": 60.0,
        "base_far": 2.50,
        "max_far": 3.50,
        "citation": "KMBR/KPBR 2019 Rule 24 Table 4 (Occupancy Group A2)",
    },
    OccupancyGroup.B_EDUCATIONAL: {
        "max_coverage": 40.0,
        "base_far": 1.50,
        "max_far": 2.50,
        "citation": "KMBR/KPBR 2019 Rule 24 Table 4 (Occupancy Group B)",
    },
    OccupancyGroup.C_MEDICAL: {
        "max_coverage": 40.0,
        "base_far": 2.00,
        "max_far": 3.00,
        "citation": "KMBR/KPBR 2019 Rule 24 Table 4 (Occupancy Group C)",
    },
    OccupancyGroup.D_ASSEMBLY: {
        "max_coverage": 40.0,
        "base_far": 1.50,
        "max_far": 2.50,
        "citation": "KMBR/KPBR 2019 Rule 24 Table 4 (Occupancy Group D)",
    },
    OccupancyGroup.E_OFFICE: {
        "max_coverage": 50.0,
        "base_far": 2.00,
        "max_far": 3.00,
        "citation": "KMBR/KPBR 2019 Rule 24 Table 4 (Occupancy Group E)",
    },
    OccupancyGroup.F_MERCANTILE: {
        "max_coverage": 60.0,
        "base_far": 2.00,
        "max_far": 3.00,
        "citation": "KMBR/KPBR 2019 Rule 24 Table 4 (Occupancy Group F)",
    },
    OccupancyGroup.G1_INDUSTRIAL_NON_HAZARDOUS: {
        "max_coverage": 60.0,
        "base_far": 1.75,
        "max_far": 2.50,
        "citation": "KMBR/KPBR 2019 Rule 24 Table 4 (Occupancy Group G1)",
    },
    OccupancyGroup.G2_INDUSTRIAL_HAZARDOUS: {
        "max_coverage": 40.0,
        "base_far": 1.00,
        "max_far": 1.50,
        "citation": "KMBR/KPBR 2019 Rule 24 Table 4 (Occupancy Group G2)",
    },
    OccupancyGroup.H_STORAGE: {
        "max_coverage": 60.0,
        "base_far": 1.50,
        "max_far": 2.50,
        "citation": "KMBR/KPBR 2019 Rule 24 Table 4 (Occupancy Group H)",
    },
    OccupancyGroup.I_HAZARDOUS: {
        "max_coverage": 30.0,
        "base_far": 0.70,
        "max_far": 1.00,
        "citation": "KMBR/KPBR 2019 Rule 24 Table 4 (Occupancy Group I)",
    },
    OccupancyGroup.J_MULTIPLEX: {
        "max_coverage": 50.0,
        "base_far": 2.00,
        "max_far": 3.00,
        "citation": "KMBR/KPBR 2019 Rule 24 Table 4 (Occupancy Group J)",
    },
}


def get_coverage_and_far(
    occupancy: OccupancyGroup,
    road_width_m: float,
    jurisdiction: Jurisdiction,
    plot_area_sqm: float = 0.0,
) -> Tuple[float, float, float, str]:
    """Return (max_coverage_pct, base_far, max_far, rule_citation) for given parameters.

    Accounts for:
    - Panchayat relaxation: KPBR permits up to 70% coverage for plots <= 5 ares (500 sqm)
      in Grama Panchayats for Group A1 residential.
    - Road width caps: FAR > 2.5 requires minimum 7.0m access road; FAR > 3.0 requires 10.0m.
    """
    spec = TABLE_4_SPECS.get(occupancy, TABLE_4_SPECS[OccupancyGroup.A1_RESIDENTIAL])
    max_coverage = spec["max_coverage"]
    base_far = spec["base_far"]
    max_far = spec["max_far"]
    citation = spec["citation"]

    # KPBR Rule 27 relaxation for rural residential
    if jurisdiction == Jurisdiction.PANCHAYAT and occupancy == OccupancyGroup.A1_RESIDENTIAL:
        if 0 < plot_area_sqm <= 500.0:
            max_coverage = 70.0
            citation += " (KPBR Rule 27 relaxation for plots <= 500m²)"

    # Road width constraint on high-density FAR:
    # Rule 24 Note: Permissible additional FAR is contingent on access road width
    if road_width_m < 3.0:
        # Access less than 3m limits FAR strictly to base FAR or 1.5 max
        max_far = min(base_far, 1.50)
    elif road_width_m < 7.0:
        # Roads between 3.0m and 7.0m cannot exceed FAR 2.50
        max_far = min(max_far, 2.50)
    elif road_width_m < 10.0:
        # Roads between 7.0m and 10.0m capped at 3.00
        max_far = min(max_far, 3.00)

    return max_coverage, base_far, max_far, citation
