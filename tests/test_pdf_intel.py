"""Unit tests for the Architectural PDF Intelligence pipeline."""

import tempfile
from pathlib import Path
import fitz  # PyMuPDF
import pytest

from app.pdf_intel.area_statement_parser import parse_pdf_area_statement
from app.pdf_intel.drawing_extractor import classify_text_metadata, extract_title_block_info
from app.pdf_intel.normalizer import build_plan_facts_from_pdf
from app.rules.models import Jurisdiction, OccupancyGroup


@pytest.fixture
def sample_drawing_pdf(tmp_path: Path) -> Path:
    """Generate a clean synthetic architectural drawing PDF with an Area Statement."""
    pdf_path = tmp_path / "test_blueprint.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)  # A4 landscape

    # Draw Title Block
    page.insert_text(
        (50, 50),
        "PROPOSED RESIDENTIAL BUILDING IN EDAPPALLY GRAMA PANCHAYAT\n"
        "OWNER: ANAND MENON | DRAWING: GROUND & FIRST FLOOR PLAN\n"
        "SCALE: 1:100 | OCCUPANCY: GROUP A1 RESIDENTIAL\n",
        fontsize=12,
    )

    # Draw Area Statement Table
    table_text = (
        "SCHEDULE OF AREAS & COMPLIANCE\n"
        "-------------------------------\n"
        "Plot Area: 280.00 Sq.m (6.91 Cents)\n"
        "Ground Floor Area: 110.00 Sq.m\n"
        "First Floor Area: 95.00 Sq.m\n"
        "Total Built-up Area: 205.00 Sq.m\n"
        "Building Height: 7.80 m\n"
        "No. of Floors: 2 (G+1)\n"
        "Access Road Width: 4.20 m\n"
        "Front Setback: 3.40 m\n"
        "Rear Setback: 1.80 m\n"
        "Side Setback 1: 1.50 m\n"
        "Side Setback 2: 1.20 m\n"
        "Car Parking: 1 slot\n"
    )
    page.insert_text((50, 150), table_text, fontsize=10)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def small_plot_drawing_pdf(tmp_path: Path) -> Path:
    """Generate a synthetic PDF for a small plot (2.5 cents) with relaxed setbacks."""
    pdf_path = tmp_path / "small_plot.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)

    page.insert_text(
        (50, 50),
        "PROPOSED SINGLE FAMILY VILLA - KERALA PANCHAYAT BUILDING RULES\n"
        "LOCATION: CHERANELLORE PANCHAYAT\n",
        fontsize=12,
    )

    table_text = (
        "AREA STATEMENT\n"
        "Plot Area: 2.50 Cents\n"
        "Ground Floor Area: 62.00 Sq.m\n"
        "Total Built-up Area: 105.00 Sq.m\n"
        "Building Height: 6.80 m\n"
        "Road Width: 3.00 m\n"
        "Front Setback: 2.10 m\n"
        "Rear Setback: 1.20 m\n"
        "Side Setback 1: 1.00 m\n"
        "Side Setback 2: 0.80 m\n"
        "Car Parking: 0\n"
    )
    page.insert_text((50, 120), table_text, fontsize=10)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_parse_pdf_area_statement(sample_drawing_pdf: Path):
    """Verify regex-based table extraction from architectural PDF."""
    data = parse_pdf_area_statement(sample_drawing_pdf)
    assert data["plot_area_sqm"] == 280.00
    assert data["ground_coverage_sqm"] == 110.00
    assert data["built_up_area_sqm"] == 205.00
    assert data["building_height_m"] == 7.80
    assert data["number_of_floors"] == 2
    assert data["road_width_m"] == 4.20
    assert data["front_setback_m"] == 3.40
    assert data["rear_setback_m"] == 1.80
    assert data["side_setback_1_m"] == 1.50
    assert data["side_setback_2_m"] == 1.20
    assert data["parking_slots_provided"] == 1


def test_cent_conversion_in_small_plot(small_plot_drawing_pdf: Path):
    """Verify that '2.5 Cents' converts accurately to ~101.17 sq.m."""
    data = parse_pdf_area_statement(small_plot_drawing_pdf)
    assert "plot_area_sqm" in data
    # 2.5 * 40.4686 = 101.17 sqm
    assert pytest.approx(data["plot_area_sqm"], 0.1) == 101.17
    assert data["front_setback_m"] == 2.10


def test_title_block_classification(sample_drawing_pdf: Path):
    """Verify title block metadata classification."""
    meta = extract_title_block_info(sample_drawing_pdf)
    assert meta["jurisdiction"] == Jurisdiction.PANCHAYAT
    assert meta["occupancy"] == OccupancyGroup.A1_RESIDENTIAL
    assert meta["drawing_scale"] == "1:100"


def test_normalizer_build_plan_facts(sample_drawing_pdf: Path):
    """Verify building validated PlanFacts from PDF."""
    facts = build_plan_facts_from_pdf(sample_drawing_pdf)
    assert facts.jurisdiction == Jurisdiction.PANCHAYAT
    assert facts.occupancy == OccupancyGroup.A1_RESIDENTIAL
    assert facts.plot_area_sqm == 280.0
    assert facts.built_up_area_sqm == 205.0
    assert facts.front_setback_m == 3.40
