"""Classifier Agent: Determines local authority jurisdiction and occupancy classification."""

from __future__ import annotations

from typing import Any, Dict
from app.pdf_intel.drawing_extractor import classify_text_metadata
from app.rules.models import Jurisdiction, OccupancyGroup


def classify_submission(
    plan_text: str,
    declared_jurisdiction: Jurisdiction | None = None,
    declared_occupancy: OccupancyGroup | None = None,
) -> Dict[str, Any]:
    """Classify the building submission to set statutory rule context."""
    extracted = classify_text_metadata(plan_text)

    final_jurisdiction = declared_jurisdiction or extracted["jurisdiction"]
    final_occupancy = declared_occupancy or extracted["occupancy"]

    reasoning = (
        f"Jurisdiction determined as '{final_jurisdiction.value.upper()}' (governed by "
        f"{'KMBR 2019' if final_jurisdiction == Jurisdiction.MUNICIPALITY else 'KPBR 2019'}); "
        f"Occupancy classification resolved as Group {final_occupancy.value}."
    )

    return {
        "jurisdiction": final_jurisdiction,
        "occupancy": final_occupancy,
        "classification_notes": reasoning,
    }
