"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import List, Optional

import re

from pydantic import BaseModel, Field, field_validator


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


class DiscrepancyItem(BaseModel):
    rule_reference: str = Field(..., description="Which rule/section is implicated")
    type: str = Field(
        ...,
        description="Type of discrepancy: false_positive | hallucination | missed_violation | value_mismatch",
    )
    description: str = Field(..., description="Detailed description of the discrepancy")
    primary_finding: Optional[str] = Field(
        default=None, description="What the primary LLM found or asserted"
    )
    verifier_finding: Optional[str] = Field(
        default=None, description="What the secondary verifier found or resolved"
    )


class VerificationResult(BaseModel):
    status: str = Field(
        ...,
        description="Verification outcome: confirmed | flagged_discrepancy | adjusted | skipped | error",
    )
    verified_by_model: Optional[str] = Field(
        default=None, description="Name or identifier of the verifying LLM model"
    )
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Verifier confidence score between 0.0 and 1.0",
    )
    cross_check_notes: Optional[str] = Field(
        default=None, description="Auditor synthesis and justification notes"
    )
    discrepancies: List[DiscrepancyItem] = Field(
        default_factory=list, description="List of detected discrepancies"
    )
    primary_violations_count: int = Field(
        default=0, description="Count of violations flagged by primary LLM"
    )
    final_violations_count: int = Field(
        default=0, description="Count of violations accepted after verification"
    )


class ComplianceResponse(BaseModel):
    extracted_facts: List[str]
    summary: str
    violations: List[Violation]
    retrieved_rules: List[RuleReference]
    report_id: Optional[int] = Field(
        default=None, description="Persisted assessment report ID"
    )
    verification: Optional[VerificationResult] = Field(
        default=None, description="Audit and double-check results from secondary LLM"
    )


class HealthResponse(BaseModel):
    status: str
    index_size: int
    embeddings_ready: bool
    llm_ready: bool
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    verifier_enabled: bool = Field(
        default=False, description="Whether secondary dual-LLM verification is enabled"
    )
    verifier_provider: Optional[str] = Field(
        default=None, description="Secondary verifier provider"
    )
    verifier_model: Optional[str] = Field(
        default=None, description="Secondary verifier model"
    )
    verifier_ready: bool = Field(
        default=False, description="Whether secondary verifier client is ready"
    )
    database_ready: bool = Field(
        default=True, description="Whether the database answered a probe query"
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Human-readable reasons the service is not fully ready",
    )


# --- Auth models (additive; existing RAG models above are unchanged) ---------


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    """Payload for ``POST /auth/register``.

    The email is trimmed, lower-cased and shape-checked so ``A@x.com`` and
    ``a@x.com`` cannot become two accounts. The password must be 8+ characters
    with a letter and a digit, and at most 72 bytes (bcrypt ignores the rest).
    """

    email: str = Field(..., description="Unique user email", min_length=3)
    password: str = Field(..., description="Plaintext password", min_length=8)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) > 254 or not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("Password must contain at least one letter and one digit")
        return v


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
    auth_provider: Optional[str] = "local"


# --- Google OAuth models (additive) ---------------------------------------


class GoogleAuthUrlResponse(BaseModel):
    """Response returned by ``GET /auth/google/url``."""

    url: str
    state: str
    client_id: Optional[str] = None


class GoogleCallbackRequest(BaseModel):
    """Payload for ``POST /auth/google/callback``."""

    code: str = Field(..., description="Google authorization code", min_length=1)
    state: str = Field(..., description="CSRF state token", min_length=1)
    redirect_uri: Optional[str] = Field(
        default=None, description="Optional custom redirect_uri"
    )


class GoogleTokenVerifyRequest(BaseModel):
    """Payload for ``POST /auth/google/token`` (Google One-Tap / GIS credential)."""

    credential: str = Field(..., description="Google ID Token JWT", min_length=10)


# --- TOTP / 2FA models (additive) ------------------------------------------


class TotpSetupResponse(BaseModel):
    """Returned by ``POST /auth/totp/setup``. The user scans the QR (or enters
    ``secret`` manually) and then confirms with a first valid code."""

    otpauth_uri: str
    qr_png_data_uri: str  # "data:image/png;base64,...."
    secret: str  # base32 manual-entry fallback


class TotpEnableRequest(BaseModel):
    password: str
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
