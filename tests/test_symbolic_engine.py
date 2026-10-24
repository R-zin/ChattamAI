"""Unit tests for the Deterministic Symbolic Compliance Engine (KMBR / KPBR 2019)."""

from fastapi.testclient import TestClient
from app.main import app
from app.rules.concessions import evaluate_concessions
from app.rules.evaluator import evaluate_plan_facts
from app.rules.models import (
    Jurisdiction,
    OccupancyGroup,
    PlanFacts,
)
from app.rules.tables_far import get_coverage_and_far
from app.rules.tables_parking import calculate_required_parking
from app.rules.tables_setbacks import calculate_required_setbacks

client = TestClient(app)


def test_standard_compliant_residential_plan():
    """A standard compliant G+1 residential house in Kerala."""
    facts = PlanFacts(
        jurisdiction=Jurisdiction.PANCHAYAT,
        occupancy=OccupancyGroup.A1_RESIDENTIAL,
        plot_area_sqm=300.0,
        ground_coverage_sqm=120.0,  # 40% (max 70% in panchayat)
        built_up_area_sqm=220.0,  # FAR = 0.73 (max 2.75)
        building_height_m=7.5,
        number_of_floors=2,
        road_width_m=4.5,
        front_setback_m=3.5,  # req 3.0m
        rear_setback_m=2.0,  # req 1.5m
        side_setback_1_m=1.5,  # req 1.2m
        side_setback_2_m=1.2,  # req 1.0m
        parking_slots_provided=1,  # req 1 slot for 220 sqm
    )
    result = evaluate_plan_facts(facts)
    assert result.is_compliant is True
    assert len(result.violations) == 0
    assert "Fully Compliant" in result.summary_verdict
    assert result.coverage_percent == 40.0
    assert result.fsi_actual == 0.73
    assert result.parking_required == 1


def test_coverage_violation():
    """Plan where ground coverage exceeds permissible limit."""
    facts = PlanFacts(
        jurisdiction=Jurisdiction.MUNICIPALITY,  # Max 65% for municipality A1
        occupancy=OccupancyGroup.A1_RESIDENTIAL,
        plot_area_sqm=200.0,
        ground_coverage_sqm=150.0,  # 75% coverage -> exceeds 65%
        built_up_area_sqm=200.0,
        building_height_m=7.0,
        number_of_floors=2,
        road_width_m=5.0,
        front_setback_m=3.5,
        rear_setback_m=2.0,
        side_setback_1_m=1.5,
        side_setback_2_m=1.2,
        parking_slots_provided=1,
    )
    result = evaluate_plan_facts(facts)
    assert result.is_compliant is False
    cov_violations = [v for v in result.violations if v.parameter == "Ground Coverage"]
    assert len(cov_violations) == 1
    assert cov_violations[0].actual_value == 75.0
    assert cov_violations[0].required_value == 65.0
    assert cov_violations[0].deficit == 10.0


def test_far_limit_violation_and_road_width_constraint():
    """Plan exceeding permissible FAR, especially on narrow access roads."""
    # Narrow road (< 3.0m) restricts FAR to max 1.50
    max_cov, base_far, max_far, _ = get_coverage_and_far(
        OccupancyGroup.A1_RESIDENTIAL,
        road_width_m=2.5,
        jurisdiction=Jurisdiction.MUNICIPALITY,
    )
    assert max_far <= 1.50

    facts = PlanFacts(
        jurisdiction=Jurisdiction.MUNICIPALITY,
        occupancy=OccupancyGroup.A1_RESIDENTIAL,
        plot_area_sqm=200.0,
        ground_coverage_sqm=80.0,
        built_up_area_sqm=400.0,  # FAR = 2.0 (exceeds 1.50 limit for 2.5m road)
        building_height_m=9.0,
        number_of_floors=3,
        road_width_m=2.5,
        front_setback_m=3.2,
        rear_setback_m=1.8,
        side_setback_1_m=1.5,
        side_setback_2_m=1.2,
        parking_slots_provided=2,
    )
    result = evaluate_plan_facts(facts)
    assert result.is_compliant is False
    far_violations = [v for v in result.violations if "FAR" in v.parameter]
    assert len(far_violations) == 1
    assert far_violations[0].actual_value == 2.0
    assert far_violations[0].required_value == 1.5


def test_setback_scaling_by_height():
    """Verify height categories: <=10m, 10-16m, and high-rise >16m."""
    # Category 1: <= 10m
    s1 = calculate_required_setbacks(8.0, 5.0, OccupancyGroup.A1_RESIDENTIAL)
    assert s1["front"] == 3.00
    assert s1["rear"] == 1.50
    assert s1["side_1"] == 1.20
    assert s1["side_2"] == 1.00

    # Category 2: 10m - 16m
    s2 = calculate_required_setbacks(14.0, 5.0, OccupancyGroup.A1_RESIDENTIAL)
    assert s2["front"] == 4.00
    assert s2["rear"] == 2.00
    assert s2["side_1"] == 1.50
    assert s2["side_2"] == 1.50

    # Category 3: > 16m (e.g. 19m = 16m + 3m -> step adder 0.5m)
    s3 = calculate_required_setbacks(19.0, 7.0, OccupancyGroup.A1_RESIDENTIAL)
    assert s3["front"] == 5.50
    assert s3["rear"] == 3.50
    assert s3["side_1"] == 2.50
    assert s3["side_2"] == 2.50


def test_chapter_vi_small_plot_concession():
    """Small plots (<= 125 m² / ~3 cents) qualify for relaxed setbacks under Chapter VI / Rule 27."""
    facts = PlanFacts(
        jurisdiction=Jurisdiction.PANCHAYAT,
        occupancy=OccupancyGroup.A1_RESIDENTIAL,
        plot_area_sqm=100.0,  # <= 125 sqm triggers small-plot concession
        ground_coverage_sqm=65.0,  # 65% (within 75% small plot limit)
        built_up_area_sqm=110.0,  # <= 150 sqm -> 0 parking required
        building_height_m=6.5,
        number_of_floors=2,
        road_width_m=3.0,
        front_setback_m=2.0,  # Standard is 3.0m (would fail!), but concession is 1.8m -> PASSES!
        rear_setback_m=1.2,  # Standard is 1.5m (would fail!), but concession is 1.0m -> PASSES!
        side_setback_1_m=1.0,  # Concession is 0.9m -> PASSES!
        side_setback_2_m=0.7,  # Concession is 0.6m -> PASSES!
        parking_slots_provided=0,
    )
    eligible, applied = evaluate_concessions(facts)
    assert any("Small Plot" in c for c in eligible)
    assert any("Front Setback relaxed" in a for a in applied)
    assert any("Rear Setback relaxed" in a for a in applied)

    result = evaluate_plan_facts(facts)
    # The plan would have failed with standard rules, but passes cleanly with concessions!
    assert result.is_compliant is True
    assert len(result.violations) == 0
    assert len(result.applied_concessions) >= 2


def test_commercial_parking_rules():
    """Mercantile Group F requires 1 slot per 60 sqm."""
    # 240 sqm commercial requires 240 / 60 = 4 slots
    req = calculate_required_parking(OccupancyGroup.F_MERCANTILE, 240.0)
    assert req == 4

    facts = PlanFacts(
        jurisdiction=Jurisdiction.MUNICIPALITY,
        occupancy=OccupancyGroup.F_MERCANTILE,
        plot_area_sqm=500.0,
        ground_coverage_sqm=200.0,
        built_up_area_sqm=240.0,
        building_height_m=8.0,
        number_of_floors=2,
        road_width_m=7.0,
        front_setback_m=5.0,  # Commercial requires 4.5m
        rear_setback_m=2.5,
        side_setback_1_m=2.0,
        side_setback_2_m=2.0,
        parking_slots_provided=2,  # Provided 2, but requires 4!
    )
    result = evaluate_plan_facts(facts)
    assert result.is_compliant is False
    parking_violation = [
        v for v in result.violations if v.parameter == "Car Parking Slots"
    ]
    assert len(parking_violation) == 1
    assert parking_violation[0].actual_value == 2.0
    assert parking_violation[0].required_value == 4.0
    assert parking_violation[0].deficit == 2.0


def test_api_v2_evaluate_endpoint():
    """Test POST /api/v2/evaluate endpoint."""
    payload = {
        "jurisdiction": "panchayat",
        "occupancy": "A1",
        "plot_area_sqm": 250.0,
        "built_up_area_sqm": 180.0,
        "ground_coverage_sqm": 100.0,
        "building_height_m": 8.0,
        "number_of_floors": 2,
        "road_width_m": 4.0,
        "front_setback_m": 2.2,  # Deficit: req is 3.0m
        "rear_setback_m": 1.6,  # req is 1.5m -> OK
        "side_setback_1_m": 1.3,  # req is 1.2m -> OK
        "side_setback_2_m": 1.1,  # req is 1.0m -> OK
        "parking_slots_provided": 1,
    }
    resp = client.post("/api/v2/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_compliant"] is False
    assert len(data["violations"]) == 1
    assert data["violations"][0]["parameter"] == "Front Setback"
    assert data["violations"][0]["deficit"] == 0.8
    assert data["coverage_percent"] == 40.0


def test_api_v2_lookup_endpoints():
    """Test lookup endpoints for setbacks and statutory tables."""
    resp = client.post(
        "/api/v2/rules/setbacks-lookup",
        json={
            "building_height_m": 12.0,
            "road_width_m": 5.0,
            "occupancy": "A1",
            "is_small_plot": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["required_setbacks_m"]["front"] == 4.00
    assert data["required_setbacks_m"]["rear"] == 2.00

    tables_resp = client.get("/api/v2/rules/tables")
    assert tables_resp.status_code == 200
    tables = tables_resp.json()
    assert "table_4_coverage_far" in tables
    assert tables["table_4_coverage_far"]["A1"]["max_coverage_pct"] == 65.0


def test_api_v2_upload_size_limit_exceeded():
    """Verify that uploads exceeding 25MB return HTTP 413."""
    from app.routes.rag_v2 import MAX_UPLOAD_SIZE

    oversized = b"%" + b"0" * (MAX_UPLOAD_SIZE + 10)
    resp = client.post(
        "/api/v2/check/pdf",
        files={"file": ("huge_blueprint.pdf", oversized, "application/pdf")},
    )
    assert resp.status_code == 413
    assert "File too large" in resp.json()["detail"]


def test_api_v2_export_report_sanitizes_filename():
    """Verify filename sanitization prevents header injection in export endpoint."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 50),
        "PROPOSED RESIDENTIAL BUILDING IN KERALA PANCHAYAT\n"
        "Plot Area: 250.00 Sq.m\n"
        "Ground Floor Area: 100.00 Sq.m\n"
        "Total Built-up Area: 180.00 Sq.m\n"
        "Front Setback: 3.50 m\n",
    )
    valid_pdf_bytes = doc.tobytes()
    doc.close()

    malicious_filename = 'plan\r\nX-Injected-Header: evil\n"quote.pdf'
    resp = client.post(
        "/api/v2/check/pdf/export-report",
        files={"file": (malicious_filename, valid_pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "\r" not in cd
    assert "\n" not in cd
    assert '"quote' not in cd
    assert "LSGD_KBR_Audit_" in cd
    assert cd.endswith('.pdf"')


def test_api_v2_auth_enforced(monkeypatch):
    """When AUTH_REQUIRED is set, V2 routes require a bearer token."""
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    resp = client.post(
        "/api/v2/evaluate",
        json={
            "plot_area_sqm": 200.0,
            "built_up_area_sqm": 150.0,
            "ground_coverage_sqm": 80.0,
            "building_height_m": 7.0,
            "road_width_m": 4.0,
            "front_setback_m": 3.0,
            "rear_setback_m": 1.5,
            "side_setback_1_m": 1.2,
            "side_setback_2_m": 1.0,
        },
    )
    assert resp.status_code == 401


def test_api_v2_persists_report():
    """Evaluating compliance via /api/v2/evaluate persists to reports."""
    eval_resp = client.post(
        "/api/v2/evaluate",
        json={
            "plot_area_sqm": 200.0,
            "built_up_area_sqm": 150.0,
            "ground_coverage_sqm": 80.0,
            "building_height_m": 7.0,
            "road_width_m": 4.0,
            "front_setback_m": 3.0,
            "rear_setback_m": 1.5,
            "side_setback_1_m": 1.2,
            "side_setback_2_m": 1.0,
        },
    )
    assert eval_resp.status_code == 200
    reports_resp = client.get("/api/reports")
    assert reports_resp.status_code == 200
    data = reports_resp.json()
    assert len(data) > 0
    assert any(r["source"] == "evaluate_v2" for r in data)


def test_statutory_critic_side_setback_concession_distinction():
    """Verify that statutory critic does not falsely exonerate Side Setback 1 if < 0.9m."""
    from app.rag.agents.statutory_critic import critique_violations
    from app.rules.models import RuleViolation

    facts = PlanFacts(
        jurisdiction=Jurisdiction.PANCHAYAT,
        occupancy=OccupancyGroup.A1_RESIDENTIAL,
        plot_area_sqm=100.0,  # small plot
        ground_coverage_sqm=50.0,
        built_up_area_sqm=80.0,
        building_height_m=6.0,
        road_width_m=3.0,
        front_setback_m=2.0,
        rear_setback_m=1.2,
        side_setback_1_m=0.70,  # Below 0.90m concession threshold
        side_setback_2_m=0.70,  # Above 0.60m concession threshold
    )
    v1 = RuleViolation(
        rule_reference="Rule 25(3)",
        parameter="Side Setback 1",
        severity="medium",
        actual_value=0.70,
        required_value=1.20,
        unit="m",
        deficit=0.50,
        description="Side 1 is 0.7m",
        statutory_clause="Rule 25(3)",
    )
    v2 = RuleViolation(
        rule_reference="Rule 25(3)",
        parameter="Side Setback 2",
        severity="medium",
        actual_value=0.70,
        required_value=1.00,
        unit="m",
        deficit=0.30,
        description="Side 2 is 0.7m",
        statutory_clause="Rule 25(3)",
    )
    critic = critique_violations(facts, [v1, v2])
    # Side Setback 2 (0.7m >= 0.6m) is exonerated under Rule 27(3)
    # Side Setback 1 (0.7m < 0.9m) must remain active
    assert any(
        x["parameter"] == "Side Setback 2" for x in critic["exonerated_violations"]
    )
    assert any(v.parameter == "Side Setback 1" for v in critic["active_violations"])
