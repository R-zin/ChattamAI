"""API v2 routes: Deterministic compliance evaluation and statutory table queries."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from app.rag.multi_agent_graph import build_multi_agent_graph
from app.rules.evaluator import evaluate_plan_facts
from app.rules.models import (
    ComplianceEvaluation,
    Jurisdiction,
    OccupancyGroup,
    PlanFacts,
)
from app.rules.tables_far import TABLE_4_SPECS
from app.rules.tables_setbacks import calculate_required_setbacks
from app.services.pdf_report_v2 import generate_compliance_pdf_report_v2

router = APIRouter(prefix="/api/v2", tags=["symbolic-compliance-v2"])


class SetbackLookupRequest(BaseModel):
    building_height_m: float = Field(..., gt=0)
    road_width_m: float = Field(default=3.0, gt=0)
    occupancy: OccupancyGroup = Field(default=OccupancyGroup.A1_RESIDENTIAL)
    is_small_plot: bool = Field(default=False)


@router.post("/evaluate", response_model=ComplianceEvaluation)
def evaluate_compliance(facts: PlanFacts) -> ComplianceEvaluation:
    """Run deterministic statutory compliance inequalities against plan facts.

    Calculates exact coverage, FAR/FSI, setbacks, parking, and small-plot concessions
    per KMBR/KPBR 2019 without LLM hallucinations.
    """
    return evaluate_plan_facts(facts)


@router.post("/rules/setbacks-lookup")
def lookup_setbacks(req: SetbackLookupRequest) -> Dict[str, Any]:
    """Look up required statutory setbacks for given building parameters."""
    setbacks = calculate_required_setbacks(
        height_m=req.building_height_m,
        road_width_m=req.road_width_m,
        occupancy=req.occupancy,
        is_small_plot=req.is_small_plot,
    )
    return {
        "building_height_m": req.building_height_m,
        "road_width_m": req.road_width_m,
        "occupancy": req.occupancy.value,
        "is_small_plot": req.is_small_plot,
        "required_setbacks_m": setbacks,
        "statutory_citation": "KMBR/KPBR 2019 Rule 25 / Table 6",
    }


@router.get("/rules/tables")
def get_rule_tables() -> Dict[str, Any]:
    """Return compiled KMBR/KPBR 2019 statutory tables for reference."""
    tables_summary = {
        name.value: {
            "max_coverage_pct": spec["max_coverage"],
            "base_far": spec["base_far"],
            "max_far": spec["max_far"],
            "citation": spec["citation"],
        }
        for name, spec in TABLE_4_SPECS.items()
    }
    return {
        "table_4_coverage_far": tables_summary,
        "small_plot_threshold_sqm": 125.0,
        "small_plot_cents_approx": 3.08,
    }


@router.post("/check/pdf")
async def check_architectural_pdf(
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """Upload an architectural drawing PDF for automated compliance auditing.

    Extracts Area Statement schedule, title block metadata, runs deterministic
    symbolic rules, critiques statutory concessions, and provides remediations.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF document.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        graph = build_multi_agent_graph()
        result = await graph.ainvoke({"pdf_path": str(tmp_path)})
        
        facts: PlanFacts = result["plan_facts"]
        critic = result["critic_result"]
        
        return {
            "is_compliant": critic["is_compliant"],
            "verdict": "Compliant" if critic["is_compliant"] else "Non-Compliant",
            "executive_summary": result["executive_summary"],
            "plan_facts": facts.model_dump(),
            "violations": critic["active_violations"],
            "exonerated_violations": critic["exonerated_violations"],
            "applied_concessions": critic["applied_concessions"],
            "eligible_concessions": critic["eligible_concessions"],
            "remediations": result["remediations"],
            "telemetry": result.get("telemetry", {}),
        }
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@router.post("/check/pdf/export-report")
async def check_pdf_and_export_report(
    file: UploadFile = File(...),
) -> Response:
    """Upload an architectural PDF plan and immediately download the formal LSGD Audit Certificate PDF."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF document.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        graph = build_multi_agent_graph()
        result = await graph.ainvoke({"pdf_path": str(tmp_path)})
        facts: PlanFacts = result["plan_facts"]
        eval_dict = result["symbolic_result"]
        evaluation = ComplianceEvaluation(**eval_dict)
        evaluation.violations = [v for v in evaluation.violations if v.parameter in {x["parameter"] for x in result["critic_result"]["active_violations"]}]
        evaluation.is_compliant = result["critic_result"]["is_compliant"]
        evaluation.applied_concessions = result["critic_result"]["applied_concessions"]

        pdf_bytes = generate_compliance_pdf_report_v2(
            facts=facts,
            evaluation=evaluation,
            remediations=result.get("remediations"),
            document_title=file.filename,
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="LSGD_KBR_Audit_{Path(file.filename).stem}.pdf"',
                "Content-Type": "application/pdf",
            },
        )
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


class KSmartExportRequest(BaseModel):
    facts: PlanFacts
    evaluation: ComplianceEvaluation
    remediations: Optional[List[Dict[str, Any]]] = None


@router.post("/reports/ksmart")
def export_ksmart_payload(req: KSmartExportRequest) -> Dict[str, Any]:
    """Generate standardized Kerala LSGD K-Smart / Sanketham e-Governance payload."""
    f = req.facts
    ev = req.evaluation
    return {
        "ksmart_metadata": {
            "version": "1.0",
            "statutory_rules": "KPBR_2019" if f.jurisdiction == Jurisdiction.PANCHAYAT else "KMBR_2019",
            "jurisdiction_type": f.jurisdiction.value.upper(),
            "occupancy_classification": f"GROUP_{f.occupancy.value}",
        },
        "compliance_summary": {
            "overall_status": "APPROVED" if ev.is_compliant else "REVISION_REQUIRED",
            "total_violations_count": len(ev.violations),
            "ground_coverage_percent": ev.coverage_percent,
            "max_permissible_coverage_percent": ev.max_coverage_percent,
            "achieved_far": ev.fsi_actual,
            "max_permissible_far": ev.max_fsi_permitted,
            "parking_slots_required": ev.parking_required,
            "parking_slots_provided": ev.parking_slots_provided,
        },
        "violations_ledger": [
            {
                "rule_code": v.rule_reference,
                "parameter_name": v.parameter,
                "severity_level": v.severity.upper(),
                "actual_value": v.actual_value,
                "statutory_value": v.required_value,
                "deficit": v.deficit,
                "unit": v.unit,
                "legal_description": v.description,
            }
            for v in ev.violations
        ],
        "statutory_concessions": {
            "eligible_concessions": ev.concessions_eligible,
            "applied_concessions": ev.applied_concessions,
        },
        "remediation_actions": req.remediations or [],
    }


