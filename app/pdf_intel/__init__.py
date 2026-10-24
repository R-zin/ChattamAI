"""Deep Architectural PDF Intelligence Pipeline for Kerala Building Rules.

Extracts certified Area Statements, Title Block metadata, and dimension callouts
from vector and scanned architectural drawing PDFs using regex rules and
multimodal vision extraction with NVIDIA Nemotron 3.5 Super VL.
"""

from app.pdf_intel.area_statement_parser import parse_pdf_area_statement
from app.pdf_intel.drawing_extractor import extract_title_block_info
from app.pdf_intel.normalizer import build_plan_facts_from_pdf
from app.pdf_intel.vision_extractor import (
    extract_plan_facts_with_nemotron_vl,
    render_pdf_page_to_image,
)

__all__ = [
    "build_plan_facts_from_pdf",
    "extract_plan_facts_with_nemotron_vl",
    "extract_title_block_info",
    "parse_pdf_area_statement",
    "render_pdf_page_to_image",
]
