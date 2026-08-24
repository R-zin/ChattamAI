"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    documents: int = Field(..., description="Number of source files processed")
    chunks: int = Field(..., description="Number of chunks newly indexed")
    index_size: int = Field(..., description="Total vectors in the index")
    skipped: int = Field(
        default=0,
        description="Chunks already present (content-hash dup) skipped during ingest",
    )


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
    totp_enabled: bool = False


# --- TOTP / 2FA models (additive) ------------------------------------------


class TotpSetupResponse(BaseModel):
    """Returned by ``POST /auth/totp/setup``. The user scans the QR (or enters
    ``secret`` manually) and then confirms with a first valid code."""

    otpauth_uri: str
    qr_png_data_uri: str  # "data:image/png;base64,...."
    secret: str  # base32 manual-entry fallback


class TotpEnableRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=8)


class TotpEnableResponse(BaseModel):
    enabled: bool
    # Plaintext codes shown ONCE; only their sha256 hashes are stored.
    recovery_codes: List[str]


class TotpDisableRequest(BaseModel):
    password: str
    code: str = Field(..., min_length=6, max_length=8)


class TotpStatusResponse(BaseModel):
    totp_enabled: bool
    totp_required: bool  # server-wide toggle, for UI messaging
    recovery_codes_remaining: int


class OtpRequiredResponse(BaseModel):
    """Returned by login in place of ``TokenResponse`` when the user must pass
    TOTP. ``otp_token`` is a short-lived, single-purpose challenge token (it is
    rejected as a session token by the purpose claim)."""

    otp_required: bool = True
    otp_setup_required: bool = False  # True => user must enrol before proceeding
    otp_token: str
    token_type: str = "totp-challenge"
    expires_in: int  # otp_challenge_ttl_seconds


class TotpVerifyRequest(BaseModel):
    otp_token: str
    code: str = Field(..., min_length=6, max_length=8)


class TotpRecoverRequest(BaseModel):
    otp_token: str
    recovery_code: str = Field(..., min_length=6)
