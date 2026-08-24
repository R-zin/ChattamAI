"""Pydantic read-models for persisted /api/check reports (T1.1).

Kept separate from ``app/schemas.py`` (which this task must not edit) per the
dispatch file layout. Mirrors :class:`app.services.report_model.Report` for a
future ``GET /api/reports`` endpoint. All fields are Optional so a partial row
(one with only some JSON columns filled) still validates.

Python 3.9 compatible: ``from __future__ import annotations`` and no PEP 604
``X | None`` unions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ReportOut(BaseModel):
    """Public view of a persisted check report."""

    report_id: int
    created_at: Optional[datetime] = None
    plan_text: Optional[str] = None
    source: Optional[str] = None
    summary: Optional[str] = None
    extracted_facts: Optional[List[str]] = None
    violations: Optional[List[Dict[str, Any]]] = None
    retrieved_rules: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None
    user_id: Optional[str] = None

    class Config:
        orm_mode = True


__all__ = ["ReportOut"]
