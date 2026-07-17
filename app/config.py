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

    # --- Retrieval ---
    top_k: int = int(os.getenv("TOP_K", "6"))

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

    model_config = {"arbitrary_types_allowed": True}

    def ensure_dirs(self) -> None:
        self.kbr_data_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
