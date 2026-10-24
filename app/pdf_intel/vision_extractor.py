"""Multimodal Vision Extractor using NVIDIA Nemotron 3.5 Super VL 120B.

Renders architectural drawing PDF sheets to high-resolution raster images
and uses multimodal vision-language models to extract certified Area Statements,
Site Plans, and statutory compliance parameters directly into PlanFacts models.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import fitz

from app.config import get_settings
from app.rules.models import Jurisdiction, OccupancyGroup, PlanFacts

logger = logging.getLogger(__name__)

NEMOTRON_VL_SYSTEM_PROMPT = """You are an expert architectural blueprint and CAD drawing analyzer specialized in Kerala Building Rules (KMBR / KPBR).
Your job is to read the architectural drawing image, locate the Area Statement schedule table, Site Plan, and Title Block, and extract the exact statutory parameters in square metres and metres.

Return ONLY a valid JSON object matching this schema:
{
  "jurisdiction": "panchayat" or "municipality",
  "occupancy": "A1" or other valid Chapter IV group,
  "plot_area_sqm": <float, total plot area in square metres>,
  "ground_coverage_sqm": <float, plinth / ground coverage area in square metres>,
  "built_up_area_sqm": <float, total built-up / gross floor area in square metres>,
  "building_height_m": <float, total building height in metres from ground to terrace floor>,
  "number_of_floors": <int, total number of floors>,
  "road_width_m": <float, width of abutting access road in metres>,
  "front_setback_m": <float, clear front setback distance in metres>,
  "rear_setback_m": <float, clear rear setback distance in metres>,
  "side_setback_1_m": <float, first / larger side yard setback in metres>,
  "side_setback_2_m": <float, second / smaller side yard setback in metres>,
  "parking_slots_provided": <int, number of car parking slots provided>
}

Rules:
1. All areas must be converted to square metres (sqm). If in cents, multiply by 40.47. If in sqft, divide by 10.764.
2. All setbacks and heights must be in metres (m). If in feet/inches, convert to metres (1 ft = 0.3048 m).
3. If ground coverage is specified as a percentage, multiply by plot_area_sqm.
4. Output raw JSON only. Do not wrap in markdown or add conversational filler.
"""

NEMOTRON_VL_EXTRACTION_PROMPT = (
    "Extract all architectural schedule parameters and site plan setbacks from this drawing into JSON."
)


def render_pdf_page_to_image(
    pdf_path: Path,
    page_num: int = 0,
    target_dpi: int = 150,
) -> Tuple[bytes, str]:
    """Render a PDF sheet into high-resolution JPEG bytes for vision models.

    Scales the page dynamically to keep maximum dimensions around 2048px for optimal
    token economy and vision model performance.
    """
    doc = fitz.open(str(pdf_path))
    if len(doc) == 0 or page_num >= len(doc):
        return b"", "image/jpeg"

    page = doc[page_num]
    rect = page.rect
    max_dim = max(rect.width, rect.height)
    if max_dim > 0:
        target_max_pixels = 2048.0
        zoom = min(2.5, max(1.0, target_max_pixels / max_dim))
    else:
        zoom = target_dpi / 72.0

    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix)
    img_bytes = pix.tobytes("jpeg")
    return img_bytes, "image/jpeg"


def _clean_json_text(raw_text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse JSON object from LLM response text."""
    if not raw_text or not raw_text.strip():
        return None

    cleaned = raw_text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Fallback to regex search for { ... }
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    return None


def _normalize_jurisdiction(raw_val: Any) -> Jurisdiction:
    """Normalize jurisdiction string to Jurisdiction enum."""
    val = str(raw_val or "").strip().lower()
    if any(k in val for k in ("municip", "corp", "urban", "kmbr")):
        return Jurisdiction.MUNICIPALITY
    return Jurisdiction.PANCHAYAT


def _normalize_occupancy(raw_val: Any) -> OccupancyGroup:
    """Normalize occupancy string to OccupancyGroup enum."""
    val = str(raw_val or "").strip().upper().replace(" ", "").replace("-", "")
    for group in OccupancyGroup:
        if group.value == val or val.startswith(group.value):
            return group
    return OccupancyGroup.A1_RESIDENTIAL


def _convert_dict_to_plan_facts(
    data: Dict[str, Any],
    source_page: int = 1,
) -> Optional[PlanFacts]:
    """Validate and convert extracted dictionary into a PlanFacts model."""
    try:
        plot_area = float(data.get("plot_area_sqm") or 0.0)
        built_up = float(data.get("built_up_area_sqm") or 0.0)
        ground_cov = float(data.get("ground_coverage_sqm") or 0.0)
        height = float(data.get("building_height_m") or 7.5)
        floors = int(data.get("number_of_floors") or 1)
        road_width = float(data.get("road_width_m") or 3.6)
        front_sb = float(data.get("front_setback_m") if data.get("front_setback_m") is not None else 3.0)
        rear_sb = float(data.get("rear_setback_m") if data.get("rear_setback_m") is not None else 1.5)
        side_sb1 = float(data.get("side_setback_1_m") if data.get("side_setback_1_m") is not None else 1.2)
        side_sb2 = float(data.get("side_setback_2_m") if data.get("side_setback_2_m") is not None else 1.0)
        parking = int(data.get("parking_slots_provided") or 0)

        # Enforce positive requirements for core parameters
        if plot_area <= 0 or built_up <= 0 or ground_cov <= 0:
            logger.warning(
                "Vision extraction missing positive area values: plot=%s, built_up=%s, coverage=%s",
                plot_area,
                built_up,
                ground_cov,
            )
            return None

        jurisdiction = _normalize_jurisdiction(data.get("jurisdiction"))
        occupancy = _normalize_occupancy(data.get("occupancy"))

        return PlanFacts(
            jurisdiction=jurisdiction,
            occupancy=occupancy,
            plot_area_sqm=plot_area,
            built_up_area_sqm=built_up,
            ground_coverage_sqm=ground_cov,
            building_height_m=height,
            number_of_floors=max(1, floors),
            road_width_m=road_width,
            front_setback_m=front_sb,
            rear_setback_m=rear_sb,
            side_setback_1_m=side_sb1,
            side_setback_2_m=side_sb2,
            parking_slots_provided=max(0, parking),
            source_pdf_page=source_page,
            bounding_boxes=data.get("bounding_boxes"),
        )
    except Exception as exc:
        logger.warning("Error constructing PlanFacts from vision data: %s", exc)
        return None


def extract_plan_facts_with_nemotron_vl(
    pdf_path: Path,
    page_num: int = 0,
    client: Optional[Any] = None,
) -> Optional[PlanFacts]:
    """Extract PlanFacts from architectural blueprint using Nemotron 3.5 Super VL.

    Renders the PDF page to image and queries the vision-language model.
    Falls back gracefully if credentials are unavailable or if extraction fails.
    """
    settings = get_settings()

    if client is None:
        has_nvidia = bool(
            os.getenv("NVIDIA_API_KEY")
            or os.getenv("NIM_API_KEY")
            or getattr(settings, "nvidia_api_key", None)
        )
        has_gemini = bool(
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or getattr(settings, "gemini_api_key", None)
        )

        if has_nvidia:
            from app.rag.llm import NimClient

            client = NimClient(model="nvidia/nemotron-3.5-super-vl-120b-a12b")
        elif has_gemini:
            from app.rag.llm import GeminiClient

            client = GeminiClient()
        else:
            logger.info("No vision LLM credentials configured. Skipping vision extraction.")
            return None

    try:
        img_bytes, mime_type = render_pdf_page_to_image(pdf_path, page_num=page_num)
        if not img_bytes:
            return None

        raw_response = client.complete_vision(
            system=NEMOTRON_VL_SYSTEM_PROMPT,
            prompt=NEMOTRON_VL_EXTRACTION_PROMPT,
            image_bytes=img_bytes,
            mime_type=mime_type,
        )

        data = _clean_json_text(raw_response)
        if not data:
            logger.warning("Vision model returned non-JSON content: %s", raw_response[:200])
            return None

        return _convert_dict_to_plan_facts(data, source_page=page_num + 1)
    except Exception as exc:
        logger.warning("Nemotron-VL vision extraction failed: %s", exc)
        return None
