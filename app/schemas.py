"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    documents: int = Field(..., description="Number of source files processed")
    chunks: int = Field(..., description="Number of chunks indexed")
    index_size: int = Field(..., description="Total vectors in the index")


class ComplianceRequest(BaseModel):
    """Text-based compliance request (extracted plan details as free text)."""

    plan_text: str = Field(
        ...,
        description="Building plan details as text (dimensions, setbacks, "
        "height, occupancy, plot area, etc.)",
        min_length=1,
    )
    top_k: Optional[int] = Field(
        default=None, description="Override number of rules to retrieve"
    )


class RuleReference(BaseModel):
    source: str
    rule_id: Optional[str] = None
    excerpt: str
    score: float


class Violation(BaseModel):
    rule_reference: str = Field(..., description="Which rule/section is implicated")
    severity: str = Field(..., description="high | medium | low | info")
    description: str = Field(..., description="What the potential violation is")
    plan_value: Optional[str] = Field(
        default=None, description="Relevant value found in the plan"
    )
    required_value: Optional[str] = Field(
        default=None, description="What the rule requires"
    )


class ComplianceResponse(BaseModel):
    extracted_facts: List[str]
    summary: str
    violations: List[Violation]
    retrieved_rules: List[RuleReference]


class HealthResponse(BaseModel):
    status: str
    index_size: int
    embeddings_ready: bool
    llm_ready: bool
