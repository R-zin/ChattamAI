"""KMBR / KPBR 2019 Table 5 & 6: Minimum Open Spaces (Setbacks).

Governed by Rule 25 & Rule 26:
- Front setback (distance between abutting street line / plot boundary and building line)
- Rear setback
- Side yard 1 and Side yard 2 setbacks
- Scales with building height and accounts for Chapter VI small-plot concessions.
"""

from __future__ import annotations

import math
from typing import Dict
from app.rules.models import OccupancyGroup


def calculate_required_setbacks(
    height_m: float,
    road_width_m: float,
    occupancy: OccupancyGroup,
    is_small_plot: bool = False,
) -> Dict[str, float]:
    """Calculate the statutory minimum setbacks in metres.

    Parameters:
    - height_m: Building height in metres from ground level to terrace.
    - road_width_m: Abutting road width in metres.
    - occupancy: Occupancy classification.
    - is_small_plot: True if plot area <= 125 sqm (Chapter VI concession applies).
    """
    # 1. Small-Plot Concessions (Chapter VI / Rule 27 for residential plots <= 125 m²)
    if (
        is_small_plot
        and occupancy == OccupancyGroup.A1_RESIDENTIAL
        and height_m <= 10.0
    ):
        return {
            "front": 1.80,  # Concession front setback (Rule 27(1))
            "rear": 1.00,  # Concession rear setback (Rule 27(2))
            "side_1": 0.90,  # Concession side yard 1
            "side_2": 0.60,  # Concession side yard 2
        }

    # 2. Commercial / Mercantile (Group F) has enhanced front setback requirements
    if occupancy == OccupancyGroup.F_MERCANTILE:
        if height_m <= 10.0:
            return {"front": 4.50, "rear": 2.00, "side_1": 1.50, "side_2": 1.50}
        elif height_m <= 16.0:
            return {"front": 5.00, "rear": 2.50, "side_1": 2.00, "side_2": 2.00}

    # 3. Standard Residential & General Occupancies (Table 6)
    if height_m <= 10.0:
        # Category 1: Up to 10 metres
        return {
            "front": 3.00,
            "rear": 1.50,
            "side_1": 1.20,
            "side_2": 1.00,
        }
    elif height_m <= 16.0:
        # Category 2: Above 10m up to 16 metres
        return {
            "front": 4.00,
            "rear": 2.00,
            "side_1": 1.50,
            "side_2": 1.50,
        }
    else:
        # Category 3: High-Rise (> 16 metres)
        # Baseline: 5m front, 3m rear, 2m sides.
        # Add 0.50m for every 3m (or fraction thereof) above 16m.
        extra_height = max(0.0, height_m - 16.0)
        increment_steps = math.ceil(extra_height / 3.0)
        step_adder = increment_steps * 0.50

        return {
            "front": round(5.00 + step_adder, 2),
            "rear": round(3.00 + step_adder, 2),
            "side_1": round(2.00 + step_adder, 2),
            "side_2": round(2.00 + step_adder, 2),
        }
