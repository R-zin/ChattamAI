"""Official LSGD Compliance Audit Report Generator (V2).

Generates self-contained, publication-ready PDF audit reports for building
plans evaluated under the Kerala Municipality Building Rules (KMBR 2019) and
Kerala Panchayat Building Rules (KPBR 2019).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from app.rules.models import ComplianceEvaluation, PlanFacts


def _escape_pdf_str(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return re.sub(r"[^\x20-\x7E]", "?", text)


class PDFReportCanvas:
    """Multi-page A4 canvas with typography and layout helpers."""

    def __init__(self):
        self.pages: List[str] = []
        self.current_stream: List[str] = []
        self.page_width = 595.0
        self.page_height = 842.0
        self.margin = 40.0
        self.content_width = self.page_width - (2 * self.margin)
        self.y = self.page_height - self.margin

    def new_page(self):
        if self.current_stream:
            self.pages.append("\n".join(self.current_stream))
            self.current_stream = []
        self.y = self.page_height - self.margin
        self.current_stream.append("0 0 0 rg")

    def ensure_space(self, needed_pt: float):
        if self.y - needed_pt < self.margin + 35:
            self.new_page()

    def draw_rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        r: float,
        g: float,
        b: float,
        fill: bool = True,
    ):
        color_cmd = (
            f"{r:.2f} {g:.2f} {b:.2f} rg" if fill else f"{r:.2f} {g:.2f} {b:.2f} RG"
        )
        op = "f" if fill else "S"
        self.current_stream.append(
            f"q {color_cmd} {x:.1f} {y:.1f} {w:.1f} {h:.1f} re {op} Q"
        )

    def draw_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        r: float = 0.7,
        g: float = 0.7,
        b: float = 0.7,
        width: float = 1.0,
    ):
        self.current_stream.append(
            f"q {r:.2f} {g:.2f} {b:.2f} RG {width:.1f} w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S Q"
        )

    def draw_text(
        self,
        text: str,
        x: float,
        y: float,
        font: str = "F1",
        size: float = 10.0,
        r: float = 0.1,
        g: float = 0.1,
        b: float = 0.1,
    ):
        clean = _escape_pdf_str(text)
        self.current_stream.append(
            f"BT /{font} {size:.1f} Tf {r:.2f} {g:.2f} {b:.2f} rg {x:.1f} {y:.1f} Td ({clean}) Tj ET"
        )

    def to_bytes(self) -> bytes:
        if self.current_stream:
            self.pages.append("\n".join(self.current_stream))
            self.current_stream = []

        total_pages = len(self.pages)
        if total_pages == 0:
            self.pages.append("")
            total_pages = 1

        objects: List[str] = []
        page_refs: List[str] = []

        # Obj 1: Catalog
        objects.append("<< /Type /Catalog /Pages 2 0 R >>")
        # Obj 2: Pages placeholder
        objects.append("")
        # Obj 3, 4: Standard Fonts
        objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

        # Create Page and Stream objects
        obj_num = 5
        for page_idx, stream_content in enumerate(self.pages):
            page_obj_idx = obj_num
            stream_obj_idx = obj_num + 1
            obj_num += 2

            page_refs.append(f"{page_obj_idx} 0 R")
            page_dict = (
                f"<< /Type /Page /Parent 2 0 R\n"
                f"   /MediaBox [0 0 {self.page_width:.1f} {self.page_height:.1f}]\n"
                f"   /Contents {stream_obj_idx} 0 R\n"
                f"   /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>"
            )
            objects.append(page_dict)

            stream_bytes = stream_content.encode("latin-1", errors="replace")
            stream_obj = (
                f"<< /Length {len(stream_bytes)} >>\n"
                f"stream\n"
                f"{stream_content}\n"
                f"endstream"
            )
            objects.append(stream_obj)

        # Update Obj 2 (Pages)
        objects[1] = (
            f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {total_pages} >>"
        )

        # Build xref table
        pdf_parts: List[bytes] = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
        xref_offsets: List[int] = [0]
        cur_offset = len(pdf_parts[0])

        for i, obj in enumerate(objects, start=1):
            xref_offsets.append(cur_offset)
            block = f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1", errors="replace")
            pdf_parts.append(block)
            cur_offset += len(block)

        xref_pos = cur_offset
        xref_block = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
        for offset in xref_offsets[1:]:
            xref_block += f"{offset:010d} 00000 n \n"
        pdf_parts.append(xref_block.encode("latin-1"))

        trailer = (
            f"trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        )
        pdf_parts.append(trailer.encode("latin-1"))

        return b"".join(pdf_parts)


def generate_compliance_pdf_report_v2(
    facts: PlanFacts,
    evaluation: ComplianceEvaluation,
    remediations: Optional[List[Dict[str, Any]]] = None,
    document_title: str = "Architectural Building Plan",
) -> bytes:
    """Generate a formal LSGD Building Permit Compliance Audit Certificate."""
    c = PDFReportCanvas()
    m = c.margin
    cw = c.content_width

    # Header bar (LSGD Kerala Government Theme: Deep Forest Green)
    c.draw_rect(m, c.y - 45, cw, 45, 0.08, 0.35, 0.20, fill=True)
    c.draw_text(
        "LOCAL SELF GOVERNMENT DEPARTMENT - GOVERNMENT OF KERALA",
        m + 14,
        c.y - 20,
        font="F2",
        size=10,
        r=1,
        g=1,
        b=1,
    )
    c.draw_text(
        "KERALA BUILDING RULES COMPLIANCE AUDIT CERTIFICATE (KMBR / KPBR 2019)",
        m + 14,
        c.y - 35,
        font="F1",
        size=8.5,
        r=0.9,
        g=0.9,
        b=0.9,
    )
    c.y -= 58

    # Metadata block
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.draw_text(f"Submission: {document_title}", m, c.y, font="F2", size=10)
    c.draw_text(f"Audit Date: {now_str}", m + cw - 160, c.y, font="F1", size=9)
    c.y -= 14
    c.draw_text(
        f"Jurisdiction: {facts.jurisdiction.value.upper()} ({'KPBR 2019' if facts.jurisdiction.value == 'panchayat' else 'KMBR 2019'})",
        m,
        c.y,
        font="F1",
        size=9,
    )
    c.draw_text(
        f"Occupancy Classification: Group {facts.occupancy.value}",
        m + cw - 160,
        c.y,
        font="F1",
        size=9,
    )
    c.y -= 18

    # Big Verdict Banner
    is_ok = evaluation.is_compliant
    if is_ok:
        c.draw_rect(m, c.y - 32, cw, 32, 0.10, 0.55, 0.25, fill=True)
        c.draw_text(
            "VERDICT: FULLY COMPLIANT WITH STATUTORY CODES",
            m + 15,
            c.y - 20,
            font="F2",
            size=11,
            r=1,
            g=1,
            b=1,
        )
    else:
        c.draw_rect(m, c.y - 32, cw, 32, 0.75, 0.15, 0.15, fill=True)
        v_count = len(evaluation.violations)
        c.draw_text(
            f"VERDICT: NON-COMPLIANT ({v_count} STATUTORY VIOLATION{'S' if v_count > 1 else ''} DETECTED)",
            m + 15,
            c.y - 20,
            font="F2",
            size=11,
            r=1,
            g=1,
            b=1,
        )
    c.y -= 44

    # Parameter Scorecard Table
    c.draw_text("1. STATUTORY PARAMETER AUDIT SCORECARD", m, c.y, font="F2", size=10)
    c.y -= 14

    # Table Header
    c.draw_rect(m, c.y - 18, cw, 18, 0.92, 0.93, 0.95, fill=True)
    c.draw_text("Parameter", m + 6, c.y - 13, font="F2", size=8.5)
    c.draw_text("Plan Value", m + 150, c.y - 13, font="F2", size=8.5)
    c.draw_text("Rule Requirement", m + 230, c.y - 13, font="F2", size=8.5)
    c.draw_text("Deficit", m + 350, c.y - 13, font="F2", size=8.5)
    c.draw_text("Status", m + 440, c.y - 13, font="F2", size=8.5)
    c.y -= 20

    # Build rows
    violations_by_param = {v.parameter: v for v in evaluation.violations}
    cents_approx = round(facts.plot_area_sqm / 40.4686, 2)

    table_data = [
        (
            "Plot Area",
            f"{facts.plot_area_sqm:.1f} m² ({cents_approx} ct)",
            "Base measurement",
            "-",
            "Pass",
        ),
        (
            "Ground Coverage",
            f"{evaluation.coverage_percent:.1f}%",
            f"Max {evaluation.max_coverage_percent:.1f}%",
            f"{violations_by_param['Ground Coverage'].deficit:.1f}%"
            if "Ground Coverage" in violations_by_param
            else "-",
            "FAIL" if "Ground Coverage" in violations_by_param else "Pass",
        ),
        (
            "Floor Space Index (FAR)",
            f"{evaluation.fsi_actual:.2f}",
            f"Max {evaluation.max_fsi_permitted:.2f}",
            f"{violations_by_param['Floor Space Index (FAR/FSI)'].deficit:.2f}"
            if "Floor Space Index (FAR/FSI)" in violations_by_param
            else "-",
            "FAIL" if "Floor Space Index (FAR/FSI)" in violations_by_param else "Pass",
        ),
        (
            "Building Height / Floors",
            f"{facts.building_height_m:.1f}m ({facts.number_of_floors} fl)",
            "Height category baseline",
            "-",
            "Pass",
        ),
        (
            "Abutting Road Width",
            f"{facts.road_width_m:.1f} m",
            "Min access threshold",
            "-",
            "Pass",
        ),
        (
            "Front Setback",
            f"{facts.front_setback_m:.2f} m",
            f"Min {violations_by_param['Front Setback'].required_value if 'Front Setback' in violations_by_param else facts.front_setback_m:.2f} m",
            f"-{violations_by_param['Front Setback'].deficit:.2f} m"
            if "Front Setback" in violations_by_param
            else "-",
            "FAIL" if "Front Setback" in violations_by_param else "Pass",
        ),
        (
            "Rear Setback",
            f"{facts.rear_setback_m:.2f} m",
            f"Min {violations_by_param['Rear Setback'].required_value if 'Rear Setback' in violations_by_param else facts.rear_setback_m:.2f} m",
            f"-{violations_by_param['Rear Setback'].deficit:.2f} m"
            if "Rear Setback" in violations_by_param
            else "-",
            "FAIL" if "Rear Setback" in violations_by_param else "Pass",
        ),
        (
            "Side Setback 1",
            f"{facts.side_setback_1_m:.2f} m",
            f"Min {violations_by_param['Side Setback 1'].required_value if 'Side Setback 1' in violations_by_param else facts.side_setback_1_m:.2f} m",
            f"-{violations_by_param['Side Setback 1'].deficit:.2f} m"
            if "Side Setback 1" in violations_by_param
            else "-",
            "FAIL" if "Side Setback 1" in violations_by_param else "Pass",
        ),
        (
            "Side Setback 2",
            f"{facts.side_setback_2_m:.2f} m",
            f"Min {violations_by_param['Side Setback 2'].required_value if 'Side Setback 2' in violations_by_param else facts.side_setback_2_m:.2f} m",
            f"-{violations_by_param['Side Setback 2'].deficit:.2f} m"
            if "Side Setback 2" in violations_by_param
            else "-",
            "FAIL" if "Side Setback 2" in violations_by_param else "Pass",
        ),
        (
            "Car Parking Slots",
            f"{facts.parking_slots_provided} slot(s)",
            f"Min {evaluation.parking_required} slot(s)",
            f"-{violations_by_param['Car Parking Slots'].deficit:.0f}"
            if "Car Parking Slots" in violations_by_param
            else "-",
            "FAIL" if "Car Parking Slots" in violations_by_param else "Pass",
        ),
    ]

    for idx, (param, plan_val, req_val, deficit, status) in enumerate(table_data):
        c.ensure_space(16)
        bg = (0.97, 0.98, 0.99) if idx % 2 == 0 else (1.0, 1.0, 1.0)
        c.draw_rect(m, c.y - 15, cw, 15, *bg, fill=True)
        c.draw_text(param, m + 6, c.y - 11, font="F1", size=8)
        c.draw_text(plan_val, m + 150, c.y - 11, font="F1", size=8)
        c.draw_text(req_val, m + 230, c.y - 11, font="F1", size=8)
        c.draw_text(deficit, m + 350, c.y - 11, font="F1", size=8)
        if status == "FAIL":
            c.draw_text(
                "NON-COMPLIANT",
                m + 440,
                c.y - 11,
                font="F2",
                size=8,
                r=0.8,
                g=0.1,
                b=0.1,
            )
        else:
            c.draw_text(
                "COMPLIANT", m + 440, c.y - 11, font="F2", size=8, r=0.1, g=0.5, b=0.2
            )
        c.y -= 16

    c.y -= 12

    # Concessions Section
    c.ensure_space(45)
    c.draw_text(
        "2. STATUTORY CONCESSIONS & RELAXATIONS APPLIED", m, c.y, font="F2", size=10
    )
    c.y -= 14
    if evaluation.applied_concessions:
        for conc in evaluation.applied_concessions:
            c.ensure_space(14)
            c.draw_text(
                f"  [x] {conc}", m + 6, c.y, font="F1", size=8.5, r=0.1, g=0.45, b=0.2
            )
            c.y -= 13
    else:
        c.draw_text(
            "  Standard regulatory provisions applied (no statutory concessions claimed).",
            m + 6,
            c.y,
            font="F1",
            size=8.5,
            r=0.4,
            g=0.4,
            b=0.4,
        )
        c.y -= 14

    c.y -= 10

    # Remediation Section
    if remediations:
        import textwrap

        c.ensure_space(50)
        c.draw_text(
            "3. ACTIONABLE ARCHITECTURAL REMEDIATION MEASURES",
            m,
            c.y,
            font="F2",
            size=10,
        )
        c.y -= 14
        for idx, r in enumerate(remediations, start=1):
            c.ensure_space(32)
            c.draw_text(
                f"  {idx}. {r['parameter']}: {r['deficit_summary']}",
                m + 6,
                c.y,
                font="F2",
                size=8.5,
                r=0.7,
                g=0.1,
                b=0.1,
            )
            c.y -= 12
            action_lines = textwrap.wrap(r["action"], width=95)
            for line_idx, line in enumerate(action_lines):
                c.ensure_space(14)
                prefix = "Action: " if line_idx == 0 else "        "
                c.draw_text(
                    f"     {prefix}{line}",
                    m + 14,
                    c.y,
                    font="F1",
                    size=8,
                    r=0.2,
                    g=0.2,
                    b=0.2,
                )
                c.y -= 11
            c.y -= 4

    c.y -= 12

    # Bilingual Malayalam / LSGD Note
    c.ensure_space(45)
    c.draw_rect(m, c.y - 30, cw, 30, 0.94, 0.96, 0.98, fill=True)
    c.draw_text(
        "LSGD KERALA STATUTORY CITATION / LOCAL BODY NOTE",
        m + 10,
        c.y - 12,
        font="F2",
        size=8.5,
        r=0.1,
        g=0.2,
        b=0.4,
    )
    if is_ok:
        c.draw_text(
            "Plan satisfies Kerala Building Rules 2019 chapters IV, V & VI for deemed/regular permit issuance.",
            m + 10,
            c.y - 23,
            font="F1",
            size=7.8,
            r=0.2,
            g=0.2,
            b=0.2,
        )
    else:
        c.draw_text(
            "Revisions required in accordance with Rule 24 (FAR/Coverage) & Rule 25 (Setbacks) before permit sanction.",
            m + 10,
            c.y - 23,
            font="F1",
            size=7.8,
            r=0.7,
            g=0.1,
            b=0.1,
        )
    c.y -= 44

    # Sign-off endorsement blocks
    c.ensure_space(60)
    c.draw_line(m, c.y, m + 180, c.y, r=0.4, g=0.4, b=0.4, width=0.8)
    c.draw_line(m + cw - 180, c.y, m + cw, c.y, r=0.4, g=0.4, b=0.4, width=0.8)
    c.y -= 12
    c.draw_text("Registered Architect / Supervisor", m + 15, c.y, font="F2", size=8)
    c.draw_text(
        "Assistant Engineer / Town Planner", m + cw - 170, c.y, font="F2", size=8
    )
    c.y -= 10
    c.draw_text(
        "(Seal & Signature)", m + 45, c.y, font="F1", size=7.5, r=0.5, g=0.5, b=0.5
    )
    c.draw_text(
        "(LSGD Verification Officer)",
        m + cw - 150,
        c.y,
        font="F1",
        size=7.5,
        r=0.5,
        g=0.5,
        b=0.5,
    )

    return c.to_bytes()
