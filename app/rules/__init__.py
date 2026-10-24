"""Symbolic Compliance Engine for Kerala Building Rules (KMBR / KPBR 2019).

Deterministic mathematical and geometric rule evaluation core.
Provides exact calculation for Coverage, Floor Area Ratio (FAR/FSI), Setbacks,
Parking, and Statutory Concessions without LLM hallucinations.
"""

from app.rules.models import (
    ComplianceEvaluation,
    Jurisdiction,
    OccupancyGroup,
    PlanFacts,
    RuleViolation,
)
from app.rules.evaluator import evaluate_plan_facts

__all__ = [
    "ComplianceEvaluation",
    "Jurisdiction",
    "OccupancyGroup",
    "PlanFacts",
    "RuleViolation",
    "evaluate_plan_facts",
]
