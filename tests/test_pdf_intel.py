"""Unit tests for the Architectural PDF Intelligence pipeline."""

import os
from pathlib import Path
import fitz  # PyMuPDF
import pytest

from app.pdf_intel.area_statement_parser import parse_pdf_area_statement
from app.pdf_intel.drawing_extractor import extract_title_block_info
from app.pdf_intel.normalizer import build_plan_facts_from_pdf
from app.pdf_intel.vision_extractor import (
    extract_plan_facts_with_nemotron_vl,
    render_pdf_page_to_image,
)
from app.rules.models import Jurisdiction, OccupancyGroup, PlanFacts


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


def test_normalizer_raises_error_on_missing_mandatory_params(
    tmp_path: Path, monkeypatch
):
    """Ensure silent dummy fallbacks are eliminated; unparseable PDF raises ValueError."""
    empty_pdf = tmp_path / "empty_blueprint.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(empty_pdf))
    doc.close()

    import app.pdf_intel.vision_extractor as ve

    monkeypatch.setattr(
        ve, "extract_plan_facts_with_nemotron_vl", lambda *a, **kw: None
    )

    with pytest.raises(ValueError, match="Failed to extract mandatory parameters"):
        build_plan_facts_from_pdf(empty_pdf)


def test_render_pdf_page_to_image(sample_drawing_pdf: Path):
    """Verify rendering PDF sheet to JPEG bytes."""
    img_bytes, mime = render_pdf_page_to_image(sample_drawing_pdf, page_num=0)
    assert mime == "image/jpeg"
    assert len(img_bytes) > 1000
    assert img_bytes[:2] == b"\xff\xd8"  # JPEG magic bytes


def test_extract_plan_facts_with_nemotron_vl_mock(
    sample_drawing_pdf: Path, monkeypatch
):
    """Verify vision extraction parses LLM multimodal response into PlanFacts."""

    class MockVisionClient:
        def complete_vision(
            self,
            system: str,
            prompt: str,
            image_bytes: bytes,
            mime_type: str = "image/png",
        ) -> str:
            assert len(image_bytes) > 0
            assert mime_type == "image/jpeg"
            assert "JSON" in system
            return """```json
            {
                "jurisdiction": "panchayat",
                "occupancy": "A1",
                "plot_area_sqm": 350.0,
                "ground_coverage_sqm": 140.0,
                "built_up_area_sqm": 260.0,
                "building_height_m": 8.2,
                "number_of_floors": 2,
                "road_width_m": 5.0,
                "front_setback_m": 4.0,
                "rear_setback_m": 2.0,
                "side_setback_1_m": 1.8,
                "side_setback_2_m": 1.5,
                "parking_slots_provided": 2
            }
            ```"""

    facts = extract_plan_facts_with_nemotron_vl(
        sample_drawing_pdf,
        client=MockVisionClient(),
    )
    assert facts is not None
    assert facts.jurisdiction == Jurisdiction.PANCHAYAT
    assert facts.occupancy == OccupancyGroup.A1_RESIDENTIAL
    assert facts.plot_area_sqm == 350.0
    assert facts.ground_coverage_sqm == 140.0
    assert facts.built_up_area_sqm == 260.0
    assert facts.building_height_m == 8.2
    assert facts.number_of_floors == 2
    assert facts.road_width_m == 5.0
    assert facts.front_setback_m == 4.0
    assert facts.rear_setback_m == 2.0
    assert facts.side_setback_1_m == 1.8
    assert facts.side_setback_2_m == 1.5
    assert facts.parking_slots_provided == 2


def test_extract_plan_facts_with_nemotron_vl_invalid_json(sample_drawing_pdf: Path):
    """Ensure invalid or corrupted LLM output returns None gracefully."""

    class BadClient:
        def complete_vision(
            self,
            system: str,
            prompt: str,
            image_bytes: bytes,
            mime_type: str = "image/png",
        ) -> str:
            return "Sorry, I am unable to read this blueprint image."

    facts = extract_plan_facts_with_nemotron_vl(sample_drawing_pdf, client=BadClient())
    assert facts is None


def test_extract_plan_facts_no_credentials_returns_none(
    sample_drawing_pdf: Path, monkeypatch
):
    """When no API credentials exist, vision extractor returns None without raising."""
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NIM_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "nvidia_api_key", None)
    monkeypatch.setattr(settings, "gemini_api_key", None)

    facts = extract_plan_facts_with_nemotron_vl(sample_drawing_pdf, client=None)
    assert facts is None


def test_normalizer_falls_back_to_vision_extractor(tmp_path: Path, monkeypatch):
    """Ensure build_plan_facts_from_pdf calls vision extractor when text parsing misses fields."""
    blank_pdf = tmp_path / "raster_blueprint.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((50, 50), "SCANNED RASTER DRAWING - NO TEXT TABLES", fontsize=14)
    doc.save(str(blank_pdf))
    doc.close()

    mock_facts = PlanFacts(
        jurisdiction=Jurisdiction.MUNICIPALITY,
        occupancy=OccupancyGroup.A1_RESIDENTIAL,
        plot_area_sqm=300.0,
        ground_coverage_sqm=120.0,
        built_up_area_sqm=210.0,
        building_height_m=7.0,
        number_of_floors=2,
        road_width_m=4.5,
        front_setback_m=3.5,
        rear_setback_m=2.0,
        side_setback_1_m=1.5,
        side_setback_2_m=1.2,
        parking_slots_provided=1,
    )

    import app.pdf_intel.vision_extractor as ve

    monkeypatch.setattr(
        ve,
        "extract_plan_facts_with_nemotron_vl",
        lambda pdf_path, **kwargs: mock_facts,
    )

    facts = build_plan_facts_from_pdf(blank_pdf)
    assert facts.plot_area_sqm == 300.0
    assert facts.ground_coverage_sqm == 120.0
    assert facts.built_up_area_sqm == 210.0
    assert facts.front_setback_m == 3.5
    assert facts.jurisdiction == Jurisdiction.MUNICIPALITY


@pytest.mark.live_nvidia
@pytest.mark.skipif(
    not os.getenv("NVIDIA_API_KEY")
    or os.getenv("NVIDIA_API_KEY", "").startswith(("nvapi-test", "sk-test", "mock")),
    reason="Live NVIDIA_API_KEY secret not available in environment",
)
def test_live_nemotron_vl_blueprint_parsing(sample_drawing_pdf: Path):
    """Live verification against NVIDIA NIM Nemotron-3.5-VL using Git Secret."""
    facts = extract_plan_facts_with_nemotron_vl(sample_drawing_pdf)
    assert facts is not None
    assert facts.plot_area_sqm > 0
    assert facts.ground_coverage_sqm > 0
    assert facts.built_up_area_sqm > 0
    assert facts.front_setback_m > 0
