"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    documents: int = Field(..., description="Number of source files processed")
    chunks: int = Field(..., description="Number of chunks indexed")
    index_size: int = Field(..., description="Total vectors in the index")


class SetModelResponse(BaseModel):
    status: str


class SetModelRequest(BaseModel):
    model_provider: str


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


# --- Auth models (additive; existing RAG models above are unchanged) ---------


class RegisterRequest(BaseModel):
    """Payload for ``POST /auth/register``."""

    email: str = Field(..., description="Unique user email", min_length=3)
    password: str = Field(..., description="Plaintext password", min_length=8)


class LoginRequest(BaseModel):
    """Payload for ``POST /auth/login`` (JSON alternative to the OAuth2 form)."""

    email: str = Field(..., description="User email")
    password: str = Field(..., description="Plaintext password")


class TokenResponse(BaseModel):
    """JWT returned by ``POST /auth/login``."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token lifetime in seconds")


class UserResponse(BaseModel):
    """Public view of a registered user (never includes the password hash)."""

    user_id: str
    email: str
    created_at: Optional[str] = None
