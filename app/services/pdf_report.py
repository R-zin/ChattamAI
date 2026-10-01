"""PDF and HTML generator for Kerala Building Rules (KBR) compliance assessment reports.

Generates self-contained, official-style compliance certificates and reports
compatible with LSGD engineering review workflows. Completely offline-safe and
requires no external native C dependencies.
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any, List


def _escape_pdf_str(text: str) -> str:
    """Escape parentheses and backslashes for PDF string literals."""
    if not text:
        return ""
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    # Replace non-ascii chars with closest ascii or '?'
    return re.sub(r"[^\x20-\x7E]", "?", text)


class SimplePDFCanvas:
    """Minimal multi-page PDF builder for A4 pages (595 x 842 points)."""

    def __init__(self):
        self.pages: List[str] = []
        self.current_stream: List[str] = []
        self.page_width = 595.0
        self.page_height = 842.0
        self.margin = 45.0
        self.content_width = self.page_width - (2 * self.margin)
        self.y = self.page_height - self.margin

    def new_page(self):
        if self.current_stream:
            self.pages.append("\n".join(self.current_stream))
            self.current_stream = []
        self.y = self.page_height - self.margin
        # Reset color
        self.current_stream.append("0 0 0 rg")

    def ensure_space(self, needed_pt: float):
        if self.y - needed_pt < self.margin + 30:
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
            "BT /{font} {size:.1f} Tf {r:.2f} {g:.2f} {b:.2f} rg {x:.1f} {y:.1f} Td ({clean}) Tj ET".format(
                font=font, size=size, r=r, g=g, b=b, x=x, y=y, clean=clean
            )
        )

    def add_wrapped_text(
        self,
        text: str,
        font: str = "F1",
        size: float = 9.5,
        max_chars: int = 85,
        line_height: float = 13.0,
        r: float = 0.15,
        g: float = 0.15,
        b: float = 0.15,
    ):
        words = text.split()
        lines = []
        cur = []
        cur_len = 0
        for w in words:
            if cur_len + len(w) + (1 if cur else 0) > max_chars:
                lines.append(" ".join(cur))
                cur = [w]
                cur_len = len(w)
            else:
                cur.append(w)
                cur_len += len(w) + (1 if cur else 0)
        if cur:
            lines.append(" ".join(cur))

        for line in lines:
            self.ensure_space(line_height)
            self.draw_text(
                line, self.margin, self.y, font=font, size=size, r=r, g=g, b=b
            )
            self.y -= line_height

    def compile(self) -> bytes:
        if self.current_stream:
            self.pages.append("\n".join(self.current_stream))

        if not self.pages:
            self.new_page()
            self.pages.append("\n".join(self.current_stream))

        out = bytearray(b"%PDF-1.4\n")
        offsets = []

        total_pages = len(self.pages)
        # We need:
        # 1: Catalog
        # 2: Pages
        # 3 .. 3 + total_pages - 1: Page objects
        # Next total_pages objects: Content stream objects
        # Next 2 objects: F1 (Helvetica), F2 (Helvetica-Bold)

        page_obj_start = 3
        stream_obj_start = page_obj_start + total_pages
        font1_obj_id = stream_obj_start + total_pages
        font2_obj_id = font1_obj_id + 1

        # Obj 1: Catalog
        offsets.append(len(out))
        out.extend(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

        # Obj 2: Pages
        kids = " ".join(f"{page_obj_start + i} 0 R" for i in range(total_pages))
        offsets.append(len(out))
        out.extend(
            f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {total_pages} >>\nendobj\n".encode(
                "ascii"
            )
        )

        # Page objects
        for i in range(total_pages):
            offsets.append(len(out))
            stream_id = stream_obj_start + i
            out.extend(
                f"{page_obj_start + i} 0 obj\n"
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Contents {stream_id} 0 R /Resources << /Font << /F1 {font1_obj_id} 0 R /F2 {font2_obj_id} 0 R >> >> >>\n"
                f"endobj\n".encode("ascii")
            )

        # Content streams
        for i, page_content in enumerate(self.pages):
            # Add page footer to stream
            footer = f"BT /F1 8 Tf 0.5 0.5 0.5 rg {self.margin} 25 Td (ChattamAI Kerala Building Rules Assessment Report  |  Page {i + 1} of {total_pages}) Tj ET"
            full_stream = (page_content + "\n" + footer).encode("utf-8")
            offsets.append(len(out))
            out.extend(
                f"{stream_obj_start + i} 0 obj\n<< /Length {len(full_stream)} >>\nstream\n".encode(
                    "ascii"
                )
            )
            out.extend(full_stream)
            out.extend(b"\nendstream\nendobj\n")

        # Fonts
        offsets.append(len(out))
        out.extend(
            f"{font1_obj_id} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n".encode(
                "ascii"
            )
        )

        offsets.append(len(out))
        out.extend(
            f"{font2_obj_id} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n".encode(
                "ascii"
            )
        )

        # Xref
        xref_offset = len(out)
        total_objects = font2_obj_id
        out.extend(
            f"xref\n0 {total_objects + 1}\n0000000000 65535 f \n".encode("ascii")
        )
        for off in offsets:
            out.extend(f"{off:010d} 00000 n \n".encode("ascii"))

        out.extend(
            f"trailer\n<< /Size {total_objects + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
        )
        return bytes(out)


def generate_compliance_pdf(report: Any) -> bytes:
    """Generate a clean, official PDF compliance assessment report."""
    canvas = SimplePDFCanvas()

    # --- Header Banner ---
    canvas.draw_rect(0, 772, 595, 70, 0.08, 0.12, 0.18, fill=True)
    canvas.draw_text(
        "LOCAL SELF-GOVERNMENT DEPARTMENT · GOVERNMENT OF KERALA",
        canvas.margin,
        810,
        font="F2",
        size=8.5,
        r=0.13,
        g=0.82,
        b=0.93,
    )
    canvas.draw_text(
        "BUILDING RULES COMPLIANCE ASSESSMENT REPORT",
        canvas.margin,
        788,
        font="F2",
        size=14,
        r=1.0,
        g=1.0,
        b=1.0,
    )
    canvas.y = 750

    # Report Identification Box
    rep_id = getattr(report, "report_id", 1)
    status = (getattr(report, "status", None) or "review").lower()
    created_at = getattr(report, "created_at", None)
    date_str = (
        created_at.strftime("%d %B %Y, %H:%M UTC")
        if isinstance(created_at, datetime)
        else "Recent Assessment"
    )
    source = getattr(report, "source", "check") or "check"
    user_id = getattr(report, "user_id", None) or "LSGD Engineer / System"

    # Status color
    if status == "fail":
        badge_label = "STATUS: VIOLATION DETECTED"
        br, bg, bb = 0.93, 0.27, 0.27
    elif status == "warning":
        badge_label = "STATUS: REVIEW REQUIRED"
        br, bg, bb = 0.96, 0.62, 0.04
    elif status == "insufficient":
        badge_label = "STATUS: INSUFFICIENT EVIDENCE"
        br, bg, bb = 0.5, 0.5, 0.5
    else:
        badge_label = "STATUS: COMPLIANT"
        br, bg, bb = 0.06, 0.72, 0.51

    canvas.ensure_space(60)
    # Draw status badge box
    canvas.draw_rect(canvas.margin, canvas.y - 12, 190, 22, br, bg, bb, fill=True)
    canvas.draw_text(
        badge_label,
        canvas.margin + 8,
        canvas.y - 6,
        font="F2",
        size=9,
        r=1.0,
        g=1.0,
        b=1.0,
    )

    # Reference numbers
    canvas.draw_text(
        f"Ref: CHATTAM-REP-{rep_id:06d}",
        320,
        canvas.y - 4,
        font="F2",
        size=9.5,
        r=0.2,
        g=0.2,
        b=0.2,
    )
    canvas.draw_text(
        f"Date: {date_str}",
        320,
        canvas.y - 18,
        font="F1",
        size=8.5,
        r=0.4,
        g=0.4,
        b=0.4,
    )
    canvas.draw_text(
        f"Source: {source.upper()}  |  Reviewer: {user_id}",
        320,
        canvas.y - 30,
        font="F1",
        size=8.5,
        r=0.4,
        g=0.4,
        b=0.4,
    )
    canvas.y -= 45

    canvas.draw_line(
        canvas.margin, canvas.y, 550, canvas.y, r=0.8, g=0.8, b=0.8, width=0.8
    )
    canvas.y -= 18

    # --- Section: Executive Summary ---
    summary = (
        getattr(report, "summary", None)
        or "Compliance analysis performed against the Kerala Building Rules (KBR)."
    )
    canvas.ensure_space(30)
    canvas.draw_text(
        "1. EXECUTIVE SUMMARY",
        canvas.margin,
        canvas.y,
        font="F2",
        size=10.5,
        r=0.1,
        g=0.2,
        b=0.3,
    )
    canvas.y -= 14
    canvas.add_wrapped_text(summary, font="F1", size=9, max_chars=88)
    canvas.y -= 12

    # --- Section: Extracted Building Facts ---
    facts = getattr(report, "extracted_facts", None) or []
    if facts:
        canvas.ensure_space(30)
        canvas.draw_text(
            "2. EXTRACTED PLAN SPECIFICATIONS",
            canvas.margin,
            canvas.y,
            font="F2",
            size=10.5,
            r=0.1,
            g=0.2,
            b=0.3,
        )
        canvas.y -= 14
        for f in facts[:10]:
            canvas.ensure_space(14)
            canvas.draw_text(
                "• " + str(f).lstrip("- "),
                canvas.margin + 8,
                canvas.y,
                font="F1",
                size=8.5,
                r=0.2,
                g=0.2,
                b=0.2,
            )
            canvas.y -= 13
        canvas.y -= 10

    # --- Section: Identified Violations / Compliance Issues ---
    violations = getattr(report, "violations", None) or []
    canvas.ensure_space(30)
    canvas.draw_text(
        f"3. REGULATORY FINDINGS & VIOLATIONS ({len(violations)} ITEMS)",
        canvas.margin,
        canvas.y,
        font="F2",
        size=10.5,
        r=0.1,
        g=0.2,
        b=0.3,
    )
    canvas.y -= 16

    if not violations:
        canvas.draw_text(
            "No building rule violations detected based on the supplied plan parameters.",
            canvas.margin + 8,
            canvas.y,
            font="F1",
            size=9,
            r=0.1,
            g=0.6,
            b=0.3,
        )
        canvas.y -= 20
    else:
        for idx, v in enumerate(violations, 1):
            if not isinstance(v, dict):
                continue
            canvas.ensure_space(50)
            rule_ref = v.get("rule_reference") or "KBR Clause"
            sev = (v.get("severity") or "warning").upper()
            desc = v.get("description") or ""
            plan_val = v.get("plan_value")
            req_val = v.get("required_value")

            # Severity badge pill
            sr, sg, sb = (
                (0.9, 0.2, 0.2)
                if sev == "HIGH"
                else (0.9, 0.6, 0.1)
                if sev in ("MEDIUM", "LOW")
                else (0.3, 0.6, 0.8)
            )
            canvas.draw_rect(
                canvas.margin + 8, canvas.y - 2, 45, 12, sr, sg, sb, fill=True
            )
            canvas.draw_text(
                sev,
                canvas.margin + 12,
                canvas.y + 1,
                font="F2",
                size=7,
                r=1.0,
                g=1.0,
                b=1.0,
            )
            canvas.draw_text(
                f"Finding #{idx}: {rule_ref}",
                canvas.margin + 60,
                canvas.y + 1,
                font="F2",
                size=9,
                r=0.1,
                g=0.1,
                b=0.1,
            )
            canvas.y -= 13

            if desc:
                canvas.add_wrapped_text(desc, font="F1", size=8.5, max_chars=84)
            if plan_val or req_val:
                vals = f"Observed in Plan: {plan_val or 'N/A'}  |  Statutory Requirement: {req_val or 'N/A'}"
                canvas.ensure_space(14)
                canvas.draw_text(
                    vals,
                    canvas.margin + 15,
                    canvas.y,
                    font="F2",
                    size=8,
                    r=0.3,
                    g=0.3,
                    b=0.4,
                )
                canvas.y -= 13
            canvas.y -= 6

    # --- Section: Statutory Citations ---
    rules = getattr(report, "retrieved_rules", None) or []
    if rules:
        canvas.ensure_space(35)
        canvas.draw_text(
            "4. STATUTORY KBR CITATIONS",
            canvas.margin,
            canvas.y,
            font="F2",
            size=10.5,
            r=0.1,
            g=0.2,
            b=0.3,
        )
        canvas.y -= 15
        for r in rules[:4]:
            if not isinstance(r, dict):
                continue
            r_id = r.get("rule_id") or r.get("source") or "Rule Clause"
            excerpt = (r.get("excerpt") or "").strip()
            score = r.get("score")
            score_txt = (
                f" (cosine score: {score:.3f})"
                if isinstance(score, (int, float))
                else ""
            )
            canvas.ensure_space(30)
            canvas.draw_text(
                f"Clause: {r_id}{score_txt}",
                canvas.margin + 8,
                canvas.y,
                font="F2",
                size=8.5,
                r=0.2,
                g=0.3,
                b=0.5,
            )
            canvas.y -= 12
            if excerpt:
                canvas.add_wrapped_text(
                    excerpt[:240] + ("…" if len(excerpt) > 240 else ""),
                    font="F1",
                    size=7.5,
                    max_chars=95,
                )
            canvas.y -= 6

    # --- Section: Engineering Verification & Sign-off ---
    canvas.ensure_space(80)
    canvas.draw_line(
        canvas.margin, canvas.y, 550, canvas.y, r=0.8, g=0.8, b=0.8, width=0.8
    )
    canvas.y -= 16
    canvas.draw_text(
        "5. VERIFICATION & SIGN-OFF",
        canvas.margin,
        canvas.y,
        font="F2",
        size=10,
        r=0.1,
        g=0.2,
        b=0.3,
    )
    canvas.y -= 16
    canvas.draw_text(
        "Reviewing Assistant: ChattamAI Compliance Engine v1.0",
        canvas.margin,
        canvas.y,
        font="F1",
        size=8.5,
        r=0.3,
        g=0.3,
        b=0.3,
    )
    canvas.draw_text(
        "Reviewing Engineer Signature: ____________________________",
        300,
        canvas.y,
        font="F1",
        size=8.5,
        r=0.3,
        g=0.3,
        b=0.3,
    )
    canvas.y -= 16
    canvas.draw_text(
        "LSGD Field Office: _____________________________________",
        300,
        canvas.y,
        font="F1",
        size=8.5,
        r=0.3,
        g=0.3,
        b=0.3,
    )
    canvas.y -= 16

    return canvas.compile()


def generate_compliance_html(report: Any) -> str:
    """Generate a clean, print-ready HTML compliance report."""
    rep_id = getattr(report, "report_id", 1)
    status = (getattr(report, "status", None) or "review").lower()
    created_at = getattr(report, "created_at", None)
    date_str = (
        created_at.strftime("%d %B %Y, %H:%M UTC")
        if isinstance(created_at, datetime)
        else "Recent Assessment"
    )
    summary = html.escape(getattr(report, "summary", "") or "No summary provided.")
    facts = getattr(report, "extracted_facts", None) or []
    violations = getattr(report, "violations", None) or []

    status_pill = {
        "pass": ("#065f46", "#d1fae5", "COMPLIANT"),
        "compliant": ("#065f46", "#d1fae5", "COMPLIANT"),
        "warning": ("#92400e", "#fef3c7", "REVIEW REQUIRED"),
        "fail": ("#991b1b", "#fee2e2", "VIOLATION DETECTED"),
        "insufficient": ("#374151", "#f3f4f6", "INSUFFICIENT EVIDENCE"),
    }.get(status, ("#92400e", "#fef3c7", "REVIEW REQUIRED"))

    violations_html = ""
    if not violations:
        violations_html = "<p style='color:#059669;font-weight:600;'>No statutory violations identified.</p>"
    else:
        for idx, v in enumerate(violations, 1):
            if not isinstance(v, dict):
                continue
            r_ref = html.escape(str(v.get("rule_reference") or "KBR Clause"))
            sev = html.escape(str(v.get("severity") or "warning").upper())
            desc = html.escape(str(v.get("description") or ""))
            p_val = html.escape(str(v.get("plan_value") or "N/A"))
            req_val = html.escape(str(v.get("required_value") or "N/A"))
            violations_html += f"""
            <div style="border:1px solid #e5e7eb;border-radius:6px;padding:12px;margin-bottom:12px;background:#f9fafb;">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                <span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;">{sev}</span>
                <strong style="color:#111827;">#{idx} {r_ref}</strong>
              </div>
              <p style="margin:4px 0 8px 0;color:#374151;font-size:13px;">{desc}</p>
              <div style="font-size:12px;color:#4b5563;background:#fff;padding:6px 10px;border-radius:4px;border:1px solid #e5e7eb;">
                <strong>Plan Value:</strong> {p_val} &nbsp;|&nbsp; <strong>Required:</strong> {req_val}
              </div>
            </div>
            """

    facts_html = "".join(f"<li>{html.escape(str(f))}</li>" for f in facts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>KBR Compliance Report #{rep_id}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px auto; max-width: 800px; color: #1f2937; line-height: 1.5; }}
    .header {{ border-bottom: 2px solid #0891b2; padding-bottom: 15px; margin-bottom: 25px; }}
    .badge {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; font-weight: 700; font-size: 13px; }}
    @media print {{ body {{ margin: 0; }} }}
  </style>
</head>
<body>
  <div class="header">
    <div style="font-size:11px;font-weight:700;letter-spacing:1px;color:#0891b2;text-transform:uppercase;">Government of Kerala · LSGD</div>
    <h1 style="margin:4px 0;font-size:22px;color:#0f172a;">Building Rules Compliance Assessment Report</h1>
    <div style="font-size:12px;color:#64748b;">Report Ref: CHATTAM-REP-{rep_id:06d} · Generated: {date_str}</div>
  </div>

  <div style="margin-bottom:20px;">
    <span class="badge" style="color:{status_pill[0]};background-color:{status_pill[1]};">{status_pill[2]}</span>
  </div>

  <section style="margin-bottom:25px;">
    <h2 style="font-size:15px;color:#0f172a;border-bottom:1px solid #e2e8f0;padding-bottom:6px;">1. Executive Summary</h2>
    <p style="font-size:14px;color:#334155;">{summary}</p>
  </section>

  <section style="margin-bottom:25px;">
    <h2 style="font-size:15px;color:#0f172a;border-bottom:1px solid #e2e8f0;padding-bottom:6px;">2. Extracted Plan Specifications</h2>
    <ul style="font-size:13px;color:#334155;padding-left:20px;">
      {facts_html or "<li>No parameter facts recorded</li>"}
    </ul>
  </section>

  <section style="margin-bottom:25px;">
    <h2 style="font-size:15px;color:#0f172a;border-bottom:1px solid #e2e8f0;padding-bottom:6px;">3. Compliance Findings</h2>
    {violations_html}
  </section>

  <footer style="margin-top:40px;padding-top:20px;border-top:1px solid #e2e8f0;font-size:12px;color:#64748b;display:flex;justify-content:space-between;">
    <div>Generated by ChattamAI RAG Compliance Engine</div>
    <div>Reviewing Engineer Sign-off: _______________________</div>
  </footer>
</body>
</html>
"""
