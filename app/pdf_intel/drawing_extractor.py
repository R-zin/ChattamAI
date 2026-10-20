"""Title block metadata extractor for architectural PDFs.

Identifies:
- Statutory Jurisdiction (Grama Panchayat -> KPBR vs Municipality/Corporation -> KMBR)
- Occupancy Group (Residential A1, Commercial F, Educational B, etc.)
- Drawing Scale & Project Title
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict
import fitz  # PyMuPDF
from app.rules.models import Jurisdiction, OccupancyGroup


def extract_title_block_info(pdf_path: Path) -> Dict[str, Any]:
    """Scan PDF for title block metadata."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    aggregated_text = ""
    try:
        # Check first page and last page (where title blocks typically reside)
        pages_to_check = [0]
        if len(doc) > 1:
            pages_to_check.append(len(doc) - 1)
        for idx in pages_to_check:
            aggregated_text += " " + doc[idx].get_text("text")
    finally:
        doc.close()

    return classify_text_metadata(aggregated_text)


def _has_word(keywords: list[str], text: str) -> bool:
    """Check if any keyword appears as a whole word in text."""
    for kw in keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
            return True
    return False


def classify_text_metadata(text: str) -> Dict[str, Any]:
    """Extract jurisdiction and occupancy from text."""
    lower = text.lower()

    # 1. Jurisdiction detection
    jurisdiction = Jurisdiction.PANCHAYAT  # Default
    if _has_word(["corporation", "municipality", "kmbr", "municipal"], lower):
        jurisdiction = Jurisdiction.MUNICIPALITY
    elif _has_word(["panchayat", "grama panchayat", "kpbr"], lower):
        jurisdiction = Jurisdiction.PANCHAYAT

    # 2. Occupancy Classification (checked with word boundaries)
    occupancy = OccupancyGroup.A1_RESIDENTIAL  # Default
    if _has_word(["commercial", "mercantile", "shops", "shop", "mall", "shopping", "group f"], lower):
        occupancy = OccupancyGroup.F_MERCANTILE
    elif _has_word(["office", "administrative", "commercial office", "group e"], lower):
        occupancy = OccupancyGroup.E_OFFICE
    elif _has_word(["school", "college", "educational", "kindergarten", "group b"], lower):
        occupancy = OccupancyGroup.B_EDUCATIONAL
    elif _has_word(["hospital", "clinic", "nursing home", "dispensary", "group c"], lower):
        occupancy = OccupancyGroup.C_MEDICAL
    elif _has_word(["auditorium", "assembly", "theatre", "hall", "group d"], lower):
        occupancy = OccupancyGroup.D_ASSEMBLY
    elif _has_word(["warehouse", "godown", "storage", "group h"], lower):
        occupancy = OccupancyGroup.H_STORAGE
    elif _has_word(["industrial", "factory", "workshop", "group g"], lower):
        occupancy = OccupancyGroup.G1_INDUSTRIAL_NON_HAZARDOUS
    elif _has_word(["hostel", "boarding", "dormitory", "group a2"], lower):
        occupancy = OccupancyGroup.A2_SPECIAL_RESIDENTIAL
    elif _has_word(["residential", "residence", "villa", "dwelling", "house", "group a1", "group a"], lower):
        occupancy = OccupancyGroup.A1_RESIDENTIAL

    # 3. Drawing Scale
    scale_match = re.search(r"scale\s*[:=]?\s*([0-9]+\s*:\s*[0-9]+)", text, re.IGNORECASE)
    scale = scale_match.group(1).replace(" ", "") if scale_match else "1:100"

    return {
        "jurisdiction": jurisdiction,
        "occupancy": occupancy,
        "drawing_scale": scale,
    }
