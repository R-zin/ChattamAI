"""Tests for building plan content validation."""

from __future__ import annotations

import io
import pytest

from app.rag.validation import is_building_plan_text, validate_building_plan_text
from app.schemas import ComplianceResponse

NON_PLAN_TEXTS = [
    "",
    "   \n\t  ",
    "short string",
    "Recipe for Chocolate Cake: 2 cups flour, 1 cup sugar, 2 eggs, 1 cup milk, bake at 350F for 30 minutes.",
    "def hello_world():\n    import sys\n    print('Hello World')\n    sys.exit(0)",
    "John Doe - Senior Software Engineer. Proficient in Python, React, PostgreSQL, Docker, and Kubernetes.",
    "INVOICE #9821 Date: 2026-03-15 Total: $1,250.00 Terms: Net 30 days. Remit payment to accounting@example.com.",
]

VALID_PLAN_TEXTS = [
    "3 floor building, 12m tall, 1m front setback",
    "Single family residential building under Group A1 in Category-II Village Panchayat with total built-up area of 90 sq. metres, 2 storeys. The proposed front distance from the street boundary is 1.0 metre and side distance is 50 centimetres. Plot area 240 sq m.",
    "Commercial building under Group F Occupancy on a plot of 850 sq. metres. Abutting public street width is 6.5 metres. Proposed building height is 16 metres with 4 storeys. Front open space provided is 2.5 metres, rear setback 2.0 metres, and side setbacks 1.5 metres.",
    "Proposed small shed structure in residential plot. Details on height and exact setbacks pending surveyor measurements.",
]


def test_is_building_plan_text_rejects_non_plans():
    for text in NON_PLAN_TEXTS:
        assert not is_building_plan_text(text), f"Expected false for: {text[:40]}"


def test_is_building_plan_text_accepts_valid_plans():
    for text in VALID_PLAN_TEXTS:
        assert is_building_plan_text(text), f"Expected true for: {text[:40]}"


def test_validate_building_plan_text_raises_value_error():
    for text in NON_PLAN_TEXTS:
        with pytest.raises(
            ValueError, match="The content of the file is not a building plan."
        ):
            validate_building_plan_text(text)


def test_validate_building_plan_text_passes_valid_plans():
    for text in VALID_PLAN_TEXTS:
        validate_building_plan_text(text)


def test_api_check_rejects_non_building_plan_text(app_client):
    for text in NON_PLAN_TEXTS:
        if not text.strip():
            # FastAPI schema requires min_length=1 on plan_text, which raises 422
            continue
        resp = app_client.post("/api/check", json={"plan_text": text})
        assert resp.status_code == 400
        assert (
            resp.json()["detail"] == "The content of the file is not a building plan."
        )


def test_api_check_upload_rejects_non_building_plan_file(app_client):
    for text in NON_PLAN_TEXTS:
        files = {
            "file": ("document.txt", io.BytesIO(text.encode("utf-8")), "text/plain")
        }
        resp = app_client.post("/api/check/upload", files=files)
        assert resp.status_code == 400
        assert (
            resp.json()["detail"] == "The content of the file is not a building plan."
        )


def test_api_check_upload_accepts_valid_building_plan_file(app_client):
    plan_text = VALID_PLAN_TEXTS[0]
    files = {"file": ("plan.txt", io.BytesIO(plan_text.encode("utf-8")), "text/plain")}
    resp = app_client.post("/api/check/upload", files=files)
    assert resp.status_code == 200
    body = ComplianceResponse(**resp.json())
    assert body.violations
