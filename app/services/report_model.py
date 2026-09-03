"""SQLAlchemy model for persisting /api/check results (T1.1).

Each compliance check is stored as one ``report`` row so the UI can list past
verdicts without re-running the RAG pipeline. Persistence is best-effort: the
route writes a row inside a try/except and never lets a DB failure break the
check response (see :func:`app.routes.rag.check`).

Python 3.9 compatible: ``from __future__ import annotations`` and no PEP 604
``X | None`` unions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text

from app.services.database import Base

# Severity ordering for status derivation — highest severity across the
# violations wins. ``info``/``low``/``medium`` map to ``warning``; ``high``
# maps to ``fail``. An empty violations list maps to ``pass``.
_SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3}


def derive_status(violations: Optional[List[Dict[str, Any]]]) -> str:
    """Collapse the violation list into a single status string.

    Rules: empty/None -> ``"pass"``; any ``high`` -> ``"fail"``; otherwise at
    least one lower-severity violation -> ``"warning"``. Unknown severities are
    treated as ``warning`` so an unrecognised value never silently reports a
    pass.
    """
    if not violations:
        return "pass"
    worst = 0
    seen_unknown = False
    for v in violations:
        sev = str((v or {}).get("severity", "")).lower()
        if sev in _SEVERITY_RANK:
            worst = max(worst, _SEVERITY_RANK[sev])
        else:
            seen_unknown = True
    if worst >= _SEVERITY_RANK["high"]:
        return "fail"
    if worst > 0 or seen_unknown:
        return "warning"
    return "pass"


class Report(Base):
    """One persisted /api/check result."""

    __tablename__ = "report"

    report_id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    plan_text = Column(Text, nullable=True)
    source = Column(String, nullable=True)  # e.g. "check" | "upload" | "ocr"
    summary = Column(Text, nullable=True)
    extracted_facts = Column(JSON, nullable=True)
    violations = Column(JSON, nullable=True)
    retrieved_rules = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default="pass")
    # Nullable so unauthenticated checks (AUTH_REQUIRED off) still persist.
    user_id = Column(String, ForeignKey("user.user_id"), nullable=True, index=True)


__all__ = ["Report", "derive_status"]
