"""Normalizer bridging raw PDF extractions into a validated PlanFacts model."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from app.pdf_intel.area_statement_parser import parse_pdf_area_statement
from app.pdf_intel.drawing_extractor import extract_title_block_info
from app.rules.models import Jurisdiction, OccupancyGroup, PlanFacts


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
    merged: Dict[str, Any] = {
        "jurisdiction": title_data.get("jurisdiction", Jurisdiction.PANCHAYAT),
        "occupancy": title_data.get("occupancy", OccupancyGroup.A1_RESIDENTIAL),
    }
    merged.update(pdf_data)
    merged.update({k: v for k, v in overrides.items() if v is not None})

    # Validate essential parameters or apply safe domain fallbacks
    plot_area = float(merged.get("plot_area_sqm") or 200.0)
    ground_cov = float(merged.get("ground_coverage_sqm") or (plot_area * 0.45))
    built_up = float(merged.get("built_up_area_sqm") or (ground_cov * 1.5))
    height = float(merged.get("building_height_m") or 7.5)
    floors = int(merged.get("number_of_floors") or 2)
    road_width = float(merged.get("road_width_m") or 3.6)
    front_sb = float(merged.get("front_setback_m") if merged.get("front_setback_m") is not None else 3.0)
    rear_sb = float(merged.get("rear_setback_m") if merged.get("rear_setback_m") is not None else 1.5)
    side_sb1 = float(merged.get("side_setback_1_m") if merged.get("side_setback_1_m") is not None else 1.2)
    side_sb2 = float(merged.get("side_setback_2_m") if merged.get("side_setback_2_m") is not None else 1.0)
    parking = int(merged.get("parking_slots_provided") or 0)

    return PlanFacts(
        jurisdiction=merged["jurisdiction"],
        occupancy=merged["occupancy"],
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
