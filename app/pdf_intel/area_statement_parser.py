"""Area Statement & Schedule of Areas parser for architectural PDFs.

Scans pages of architectural drawing PDFs (from AutoCAD, Revit, ArchiCAD, etc.)
and extracts certified building parameters:
- Plot area (with auto-conversion from cents/ares to m²)
- Ground coverage / Plinth area
- Total built-up area
- Building height & floor count
- Abutting access road width
- Setbacks (Front, Rear, Sides)
- Parking provisions
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import fitz  # PyMuPDF


# 1 cent = 40.4686 sq.m
SQM_PER_CENT = 40.4686
SQM_PER_ARE = 100.0

# Regex patterns for architectural parameters
_NUM_PATTERN = r"([0-9]+(?:\.[0-9]+)?)"

PATTERNS = {
    "plot_area_cents": re.compile(
        rf"(?:plot\s*area|site\s*area|total\s*extent|extent\s*of\s*plot)[^\d\n]*{_NUM_PATTERN}\s*(?:cents?|ct)\b",
        re.IGNORECASE,
    ),
    "plot_area_sqm": re.compile(
        rf"(?:plot\s*area|site\s*area|total\s*extent|extent\s*of\s*plot)[^\d\n]*{_NUM_PATTERN}\s*(?:sq\.?\s*m|m²|sqm|sq\s*mtrs?)\b",
        re.IGNORECASE,
    ),
    "plot_area_ares": re.compile(
        rf"(?:plot\s*area|site\s*area|total\s*extent)[^\d\n]*{_NUM_PATTERN}\s*(?:ares?)\b",
        re.IGNORECASE,
    ),
    "ground_coverage_sqm": re.compile(
        rf"(?:ground\s*floor(?:\s*area)?|plinth\s*area|ground\s*coverage|footprint)[^\d\n]*{_NUM_PATTERN}\s*(?:sq\.?\s*m|m²|sqm|sq\s*mtrs?|%?)",
        re.IGNORECASE,
    ),
    "built_up_area_sqm": re.compile(
        rf"(?:total\s*built[\s-]*up\s*area|total\s*floor\s*area|gross\s*built[\s-]*up|built[\s-]*up\s*area)[^\d\n]*{_NUM_PATTERN}\s*(?:sq\.?\s*m|m²|sqm|sq\s*mtrs?)",
        re.IGNORECASE,
    ),
    "building_height_m": re.compile(
        rf"(?:building\s*height|total\s*height|height\s*of\s*building|height)[^\d\n]*{_NUM_PATTERN}\s*(?:m|mtrs?|metres?|meters?)\b",
        re.IGNORECASE,
    ),
    "number_of_floors": re.compile(
        r"(?:(?:total\s*)?no\.?\s*of\s*floors?|number\s*of\s*floors?|total\s*floors?)\s*[:=]?\s*([0-9]+)\b|"
        r"\b([0-9]+)\s*(?:storeys?|floors?)\b",
        re.IGNORECASE,
    ),
    "g_plus_floors": re.compile(
        r"\bG\s*\+\s*([0-9]+)\b",
        re.IGNORECASE,
    ),
    "road_width_m": re.compile(
        rf"(?:road\s*width|access\s*road|width\s*of\s*road|street\s*width|access\s*width|access)[^\d\n]*{_NUM_PATTERN}\s*(?:m|mtrs?|metres?)\b",
        re.IGNORECASE,
    ),
    "front_setback_m": re.compile(
        rf"(?:front\s*setback|fsb|front\s*yard|front\s*open\s*space|front)[^\d\n:]*[:=]?[^\d\n]*{_NUM_PATTERN}\s*(?:m|mtrs?|metres?)\b",
        re.IGNORECASE,
    ),
    "rear_setback_m": re.compile(
        rf"(?:rear\s*setback|rsb|rear\s*yard|rear\s*open\s*space|rear)[^\d\n:]*[:=]?[^\d\n]*{_NUM_PATTERN}\s*(?:m|mtrs?|metres?)\b",
        re.IGNORECASE,
    ),
    "side_setback_1_m": re.compile(
        rf"(?:side\s*setback\s*1|side\s*1|ssb\s*1|side\s*yard\s*1|left\s*setback|left\s*side)[^\d\n:]*[:=]?[^\d\n]*{_NUM_PATTERN}\s*(?:m|mtrs?|metres?)\b",
        re.IGNORECASE,
    ),
    "side_setback_2_m": re.compile(
        rf"(?:side\s*setback\s*2|side\s*2|ssb\s*2|side\s*yard\s*2|right\s*setback|right\s*side)[^\d\n:]*[:=]?[^\d\n]*{_NUM_PATTERN}\s*(?:m|mtrs?|metres?)\b",
        re.IGNORECASE,
    ),
    "parking_slots": re.compile(
        r"(?:car\s*parking|parking\s*slots?|parking\s*provided|parking)[^\d\n]*([0-9]+)\s*(?:nos?|slots?|cars?)?\b",
        re.IGNORECASE,
    ),
}


def parse_pdf_area_statement(pdf_path: Path) -> Dict[str, Any]:
    """Scan all pages of a PDF document and extract architectural plan parameters."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    findings: Dict[str, Any] = {}
    best_page = 1

    try:
        # Step 1: Scan full text across all pages
        full_text_by_page = []
        for page_idx, page in enumerate(doc, start=1):
            text = page.get_text("text")
            full_text_by_page.append((page_idx, text))

        # Check if any page looks like an Area Statement sheet
        for page_idx, text in full_text_by_page:
            extracted_on_page = _extract_from_text(text)
            if len(extracted_on_page) > len(findings):
                findings = extracted_on_page
                best_page = page_idx

        # If partial, try aggregating across all pages
        if len(findings) < 6:
            aggregated_text = "\n".join(t for _, t in full_text_by_page)
            findings = _extract_from_text(aggregated_text)

        findings["source_pdf_page"] = best_page
        findings["total_pages_scanned"] = len(doc)
    finally:
        doc.close()

    return findings


def _extract_from_text(text: str) -> Dict[str, Any]:
    """Apply regex rules to text block and derive numerical parameters."""
    data: Dict[str, Any] = {}

    # Plot Area: check sqm first, then cents, then ares
    m = PATTERNS["plot_area_sqm"].search(text)
    if m:
        data["plot_area_sqm"] = float(m.group(1))
    else:
        m_cent = PATTERNS["plot_area_cents"].search(text)
        if m_cent:
            cents_val = float(m_cent.group(1))
            data["plot_area_sqm"] = round(cents_val * SQM_PER_CENT, 2)
            data["plot_area_cents"] = cents_val
        else:
            m_are = PATTERNS["plot_area_ares"].search(text)
            if m_are:
                ares_val = float(m_are.group(1))
                data["plot_area_sqm"] = round(ares_val * SQM_PER_ARE, 2)

    # Built-up Area
    m = PATTERNS["built_up_area_sqm"].search(text)
    if m:
        data["built_up_area_sqm"] = float(m.group(1))

    # Ground Coverage / Plinth
    m = PATTERNS["ground_coverage_sqm"].search(text)
    if m:
        data["ground_coverage_sqm"] = float(m.group(1))

    # Building Height
    m = PATTERNS["building_height_m"].search(text)
    if m:
        data["building_height_m"] = float(m.group(1))

    # Number of Floors
    m = PATTERNS["g_plus_floors"].search(text)
    if m:
        # G+1 means 2 floors, G+2 means 3 floors
        data["number_of_floors"] = 1 + int(m.group(1))
    else:
        m_f = PATTERNS["number_of_floors"].search(text)
        if m_f:
            floor_val = m_f.group(1) or m_f.group(2)
            if floor_val:
                data["number_of_floors"] = int(floor_val)

    # Road Width
    m = PATTERNS["road_width_m"].search(text)
    if m:
        data["road_width_m"] = float(m.group(1))

    # Setbacks
    m = PATTERNS["front_setback_m"].search(text)
    if m:
        data["front_setback_m"] = float(m.group(1))

    m = PATTERNS["rear_setback_m"].search(text)
    if m:
        data["rear_setback_m"] = float(m.group(1))

    m = PATTERNS["side_setback_1_m"].search(text)
    if m:
        data["side_setback_1_m"] = float(m.group(1))

    m = PATTERNS["side_setback_2_m"].search(text)
    if m:
        data["side_setback_2_m"] = float(m.group(1))

    # Parking Slots
    m = PATTERNS["parking_slots"].search(text)
    if m:
        data["parking_slots_provided"] = int(m.group(1))

    return data
