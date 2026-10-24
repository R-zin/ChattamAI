"""Normalizer bridging raw PDF extractions into a validated PlanFacts model."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional
from app.pdf_intel.area_statement_parser import parse_pdf_area_statement
from app.pdf_intel.drawing_extractor import extract_title_block_info
from app.rules.models import Jurisdiction, OccupancyGroup, PlanFacts

logger = logging.getLogger(__name__)


def build_plan_facts_from_pdf(
    pdf_path: Path,
    overrides: Optional[Dict[str, Any]] = None,
) -> PlanFacts:
    """Extract and normalize building parameters from an architectural drawing PDF.

    Combines:
    - Area statement numerical schedule (coverage, built-up area, setbacks)
    - Title block metadata (jurisdiction, occupancy classification)
    - User overrides (if any passed via API request)
    """
    overrides = overrides or {}
    pdf_data = parse_pdf_area_statement(pdf_path)
    title_data = extract_title_block_info(pdf_path)

    # Merge hierarchy: extracted title -> extracted area statement -> explicit user overrides
    merged: Dict[str, Any] = {}
    if title_data.get("has_explicit_jurisdiction"):
        merged["jurisdiction"] = title_data["jurisdiction"]
    if title_data.get("has_explicit_occupancy"):
        merged["occupancy"] = title_data["occupancy"]
    merged.update(pdf_data)
    merged.update({k: v for k, v in overrides.items() if v is not None})

    # Validate essential parameters - no silent dummy fallbacks!
    missing = []
    if merged.get("plot_area_sqm") is None:
        missing.append("plot_area_sqm")
    if merged.get("ground_coverage_sqm") is None:
        missing.append("ground_coverage_sqm")
    if merged.get("built_up_area_sqm") is None:
        missing.append("built_up_area_sqm")
    if merged.get("front_setback_m") is None:
        missing.append("front_setback_m")

    if missing:
        # If mandatory parameters could not be parsed via regex text extraction,
        # attempt multimodal vision extraction with Nemotron-3.5-VL
        try:
            from app.pdf_intel.vision_extractor import (
                extract_plan_facts_with_nemotron_vl,
            )

            vision_facts = extract_plan_facts_with_nemotron_vl(pdf_path)
            if vision_facts:
                v_dict = vision_facts.model_dump()
                for k, v in v_dict.items():
                    if merged.get(k) is None and v is not None:
                        merged[k] = v
                merged.update({k: v for k, v in overrides.items() if v is not None})
                missing = [m for m in missing if merged.get(m) is None]
        except Exception as exc:
            logger.warning("Vision extraction fallback failed: %s", exc)

    if missing:
        raise ValueError(
            f"Failed to extract mandatory parameters from architectural PDF: {', '.join(missing)}. "
            f"Please ensure the PDF contains a readable Area Statement schedule or provide parameter overrides."
        )

    plot_area = float(merged["plot_area_sqm"])
    ground_cov = float(merged["ground_coverage_sqm"])
    built_up = float(merged["built_up_area_sqm"])
    height = float(merged.get("building_height_m") or 7.5)
    floors = int(merged.get("number_of_floors") or 1)
    road_width = float(merged.get("road_width_m") or 3.6)
    front_sb = float(merged["front_setback_m"])
    rear_sb = float(
        merged.get("rear_setback_m")
        if merged.get("rear_setback_m") is not None
        else 1.5
    )
    side_sb1 = float(
        merged.get("side_setback_1_m")
        if merged.get("side_setback_1_m") is not None
        else 1.2
    )
    side_sb2 = float(
        merged.get("side_setback_2_m")
        if merged.get("side_setback_2_m") is not None
        else 1.0
    )
    parking = int(merged.get("parking_slots_provided") or 0)

    jurisdiction = merged.get("jurisdiction") or Jurisdiction.PANCHAYAT
    occupancy = merged.get("occupancy") or OccupancyGroup.A1_RESIDENTIAL

    return PlanFacts(
        jurisdiction=jurisdiction,
        occupancy=occupancy,
        plot_area_sqm=plot_area,
        ground_coverage_sqm=ground_cov,
        built_up_area_sqm=built_up,
        building_height_m=height,
        number_of_floors=floors,
        road_width_m=road_width,
        front_setback_m=front_sb,
        rear_setback_m=rear_sb,
        side_setback_1_m=side_sb1,
        side_setback_2_m=side_sb2,
        parking_slots_provided=parking,
        source_pdf_page=merged.get("source_pdf_page", 1),
    )
