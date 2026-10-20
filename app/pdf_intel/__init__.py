"""Deep Architectural PDF Intelligence Pipeline for Kerala Building Rules.

Extracts certified Area Statements, Title Block metadata, and dimension callouts
from vector and scanned architectural drawing PDFs.
"""

from app.pdf_intel.area_statement_parser import parse_pdf_area_statement
from app.pdf_intel.drawing_extractor import extract_title_block_info
from app.pdf_intel.normalizer import build_plan_facts_from_pdf

__all__ = [
    "build_plan_facts_from_pdf",
    "extract_title_block_info",
    "parse_pdf_area_statement",
]
