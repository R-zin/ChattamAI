"""Central configuration loaded from environment variables.

All settings have sensible defaults so the app can boot for inspection even
before every credential is provided. Endpoints that need a missing credential
raise a clear error at request time rather than crashing at import.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel

# Load a local .env file if present (no-op in production where real env is set).
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseModel):
    """Runtime configuration for the RAG system."""

    # --- Data / storage locations ---
    kbr_data_dir: Path = Path(os.getenv("KBR_DATA_DIR", str(BASE_DIR / "data" / "kbr")))
    index_dir: Path = Path(os.getenv("INDEX_DIR", str(BASE_DIR / "data" / "index")))

    # --- Chunking ---
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1000"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "150"))

    # --- Latency / cost caches (single source of truth; env aliases below) ---
    embedding_cache_ttl: float = float(os.getenv("EMBEDDING_CACHE_TTL", "300"))
    embedding_cache_maxsize: int = int(os.getenv("EMBEDDING_CACHE_MAXSIZE", "1024"))
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "128"))
    embedding_cache_enabled: bool = os.getenv("EMBEDDING_CACHE_ENABLED", "1") not in (
        "0",
        "false",
    )
    analysis_cache_ttl: float = float(os.getenv("ANALYSIS_CACHE_TTL", "300"))
    analysis_cache_maxsize: int = int(os.getenv("ANALYSIS_CACHE_MAXSIZE", "512"))

    # --- Retrieval ---
    top_k: int = int(os.getenv("TOP_K", "6"))
    # Minimum cosine-similarity for a retrieved rule chunk to be used.
    # Scores are higher=better; 0.0 keeps everything (off).
    min_score: float = float(os.getenv("MIN_SCORE", "0.0"))

    # --- OCR (image / image-PDF plans; plan.md Phase 3) ---
    # Opt-in feature flag, OFF by default so a box without the Tesseract binary
    # and the Pillow/pytesseract/PyMuPDF deps still boots and serves text/PDF
    # plans unchanged. OCR deps are lazily imported only when this is on; see
    # app/rag/ocr.py. Requires the system `tesseract` binary at runtime.
    ocr_enabled: bool = os.getenv("OCR_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    # --- Embeddings (OpenAI) ---
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_base_url: Optional[str] = os.getenv("OPENAI_BASE_URL")  # optional proxy
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "1536"))

    # --- LLM (Anthropic Claude, works with the local proxy) ---
    anthropic_api_key: Optional[str] = os.getenv(
        "ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_AUTH_TOKEN")
    )
    anthropic_base_url: Optional[str] = os.getenv("ANTHROPIC_BASE_URL")
    llm_model: str = os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "60"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "2"))

    # --- Auth (see app/services/dbmodel.py + app/routes/auth.py) ---
    # SECRET_KEY must be overridden in production (the default is insecure).
    secret_key: str = os.getenv("SECRET_KEY", "chattamai-insecure-dev-secret-change-me")
    auth_algorithm: str = os.getenv("AUTH_ALGORITHM", "HS256")
    admin_key: Optional[str] = os.getenv("ADMIN_KEY")
    # Opt-in protection of mutating/paid routes; OFF by default so the
    # credential-less CI smoke test on /api/health keeps passing.
    auth_required: bool = os.getenv("AUTH_REQUIRED", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    # --- Auth / DB scaffolding (unused by the RAG app today; see DEVELOPMENT.md §7) ---
    # --- TOTP / 2FA (opt-in per user; TOTP_REQUIRED forces enrolment server-wide) ---
    # See app/routes/auth.py + app/services/totp.py. OFF by default keeps the
    # credential-less smoke test and existing tests green.
    totp_required: bool = os.getenv("TOTP_REQUIRED", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    totp_issuer: str = os.getenv("TOTP_ISSUER", "ChattamAI")
    # Seconds the pre-auth TOTP challenge token (``otp_token``) stays valid.
    otp_challenge_ttl_seconds: int = int(os.getenv("OTP_CHALLENGE_TTL", "300"))
    # Recovery codes issued (once) at enable-time; each is single-use.
    totp_recovery_count: int = int(os.getenv("TOTP_RECOVERY_COUNT", "8"))

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./chattamai.db")
    session_timeout_seconds: int = int(os.getenv("TIME_OUT", "3600"))

    model_config = {"arbitrary_types_allowed": True}

    def ensure_dirs(self) -> None:
        self.kbr_data_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
