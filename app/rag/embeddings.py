"""Embedding providers.

The system retrieves Kerala Building Rules by semantic similarity. Embeddings
are behind a small interface so the backend can be swapped without touching the
rest of the pipeline. The default implementation uses OpenAI's embedding API.
"""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import os
import threading
import time
from abc import ABC, abstractmethod
from typing import List, Optional

import numpy as np

# Default cache TTL (seconds) and capacity, overridable via env for tuning.
_DEFAULT_CACHE_TTL = float(os.getenv("EMBEDDING_CACHE_TTL", "300"))
_DEFAULT_CACHE_MAXSIZE = int(os.getenv("EMBEDDING_CACHE_MAXSIZE", "1024"))


def _default_batch_size() -> int:
    """Max texts per ``embeddings.create`` call (Settings.embedding_batch_size)."""
    try:
        from app.config import get_settings

        return int(get_settings().embedding_batch_size)
    except Exception:
        return 128


# Deprecated alias (kept for any external importers); prefer _default_batch_size().
_DEFAULT_BATCH_SIZE = _default_batch_size()


def _cache_key(text: str) -> str:
    """Stable content hash for a single text (cache lookup key)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """Return row-wise L2-normalized float32 vectors.

    Normalising turns inner product into cosine similarity, so the vector
    store can rank by true similarity (higher = more similar) instead of raw
    L2 distance. Zero vectors are left as-is (norm floored to avoid div-by-0).
    """
    matrix = np.asarray(matrix, dtype="float32")
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return matrix / norms


class EmbeddingProvider(ABC):
    """Turns text into fixed-size vectors."""

    dim: int

    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """Return a (len(texts), dim) float32 array."""
        raise NotImplementedError

    def embed_normalized(self, texts: List[str]) -> np.ndarray:
        """Return L2-normalized embeddings (unit length) for cosine search."""
        return l2_normalize(self.embed(texts))


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embeddings via the official SDK (reads OPENAI_API_KEY from env)."""

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dim: int = 1536,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        from openai import OpenAI

        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set — required for OpenAI embeddings. "
                "Set it in the environment or .env file."
            )
        self.model = model
        self.dim = dim
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype="float32")
        # Normalise whitespace; OpenAI rejects empty strings.
        cleaned = [t.strip() or " " for t in texts]
        resp = self._client.embeddings.create(model=self.model, input=cleaned)
        ordered = sorted(resp.data, key=lambda d: d.index)
        matrix = np.array([d.embedding for d in ordered], dtype="float32")
        return matrix

    def embed_batch(
        self, texts: List[str], batch_size: Optional[int] = None
    ) -> np.ndarray:
        """Embed many texts, chunking into multiple `embeddings.create` calls.

        Large ingest jobs can exceed the provider's max batch size; this splits
        ``texts`` into ``batch_size`` chunks, embeds each chunk, and concatenates
        the results back into a single (len(texts), dim) matrix in input order.
        """
        if not texts:
            return np.empty((0, self.dim), dtype="float32")
        size = batch_size or _default_batch_size()
        if size <= 0:
            size = _default_batch_size()
        chunks = [texts[i : i + size] for i in range(0, len(texts), size)]
        parts = [self.embed(chunk) for chunk in chunks]
        return np.concatenate(parts, axis=0)


class EmbeddingCache(EmbeddingProvider):
    """Caching wrapper that adds a small in-process TTL cache over a provider.

    Keys on the SHA-256 content hash of each input text so identical texts are
    only embedded once per TTL window. The wrapped provider may be any object
    exposing the ``embed(texts) -> np.ndarray`` interface, so this composes with
    ``OpenAIEmbeddingProvider.embed_batch`` as well. Thread-safe, no external
    store; hits/misses/expired entries are observable via ``stats()``.
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        ttl: float = _DEFAULT_CACHE_TTL,
        maxsize: int = _DEFAULT_CACHE_MAXSIZE,
    ) -> None:
        self.provider = provider
        self.dim = provider.dim
        self.ttl = ttl
        self.maxsize = max(1, maxsize)
        self._lock = threading.Lock()
        # key -> (vector, expiry_epoch)
        self._entries: OrderedDict = OrderedDict()
        self._hits = 0
        self._misses = 0

    def stats(self) -> dict:
        """Return cache observability counters (thread-safe snapshot)."""
        with self._lock:
            return {
                "size": len(self._entries),
                "hits": self._hits,
                "misses": self._misses,
                "maxsize": self.maxsize,
                "ttl": self.ttl,
            }

    def _prune_expired_locked(self, now: float) -> None:
        expired = [k for k, (_, exp) in self._entries.items() if exp <= now]
        for k in expired:
            del self._entries[k]

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype="float32")
        now = time.time()
        keys = [_cache_key(t) for t in texts]
        out: List[Optional[np.ndarray]] = [None] * len(texts)
        to_fetch_idx: List[int] = []
        to_fetch_txt: List[str] = []

        with self._lock:
            self._prune_expired_locked(now)
            for i, key in enumerate(keys):
                entry = self._entries.get(key)
                if entry is not None and entry[1] > now:
                    out[i] = entry[0]
                    self._hits += 1
                else:
                    self._misses += 1
                    to_fetch_idx.append(i)
                    to_fetch_txt.append(texts[i])

        # Embed misses outside the lock so concurrent callers aren't serialised
        # on a slow network round-trip.
        if to_fetch_txt:
            fresh = self.provider.embed(to_fetch_txt)
            with self._lock:
                insert_time = time.time()
                self._prune_expired_locked(insert_time)
                for i, vec in zip(to_fetch_idx, fresh):
                    key = keys[i]
                    if key in self._entries:
                        del self._entries[key]
                    self._entries[key] = (vec, insert_time + self.ttl)
                    while len(self._entries) > self.maxsize:
                        self._entries.popitem(last=False)
                    out[i] = vec

        matrix = np.array([v for v in out], dtype="float32")
        return matrix


class NvidiaEmbeddingProvider(EmbeddingProvider):
    """NVIDIA NIM embedding provider (via OpenAI SDK pointing to NVIDIA NIM).

    Defaults to the free `nvidia/nemotron-3-embed-1b` model (2048-dim) and
    the NVIDIA hosted API catalog (https://integrate.api.nvidia.com/v1).
    Batches large input lists into chunks of `batch_size` (default 64) to
    prevent request timeouts and payload limits.
    """

    DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
    DEFAULT_MODEL = "nvidia/nemotron-3-embed-1b"
    DEFAULT_DIM = 2048

    def __init__(
        self,
        model: Optional[str] = None,
        dim: Optional[int] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> None:
        from openai import OpenAI
        from app.config import get_settings

        settings = get_settings()
        resolved_base_url = (
            base_url
            or os.getenv("NVIDIA_BASE_URL")
            or os.getenv("NIM_BASE_URL")
            or os.getenv("NVIDIA_API_URL")
            or getattr(settings, "nvidia_base_url", None)
            or self.DEFAULT_BASE_URL
        )

        resolved_key = (
            api_key
            or os.getenv("NVIDIA_API_KEY")
            or os.getenv("NIM_API_KEY")
            or getattr(settings, "nvidia_api_key", None)
        )

        is_hosted = "nvidia.com" in resolved_base_url.lower()
        if not resolved_key:
            if is_hosted:
                raise RuntimeError(
                    "No NVIDIA credentials found for embeddings. Set NVIDIA_API_KEY "
                    "(or NIM_API_KEY) in the environment."
                )
            resolved_key = "not-used"

        chosen_model = (
            model
            or os.getenv("EMBEDDING_MODEL")
            or getattr(settings, "embedding_model", None)
            or self.DEFAULT_MODEL
        )
        if not chosen_model or "embedding-3" in chosen_model:
            chosen_model = self.DEFAULT_MODEL

        self.model = chosen_model
        self.dim = dim or getattr(settings, "embedding_dim", None) or self.DEFAULT_DIM
        self.batch_size = (
            batch_size or getattr(settings, "embedding_batch_size", None) or 64
        )
        self.base_url = resolved_base_url
        self._client = OpenAI(
            api_key=resolved_key,
            base_url=resolved_base_url,
            timeout=getattr(settings, "llm_timeout", 60.0),
            max_retries=getattr(settings, "llm_max_retries", 2),
        )

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype="float32")
        cleaned = [t.strip() or " " for t in texts]

        step = max(1, self.batch_size)
        batches = [cleaned[i : i + step] for i in range(0, len(cleaned), step)]
        parts = []
        for batch in batches:
            resp = self._client.embeddings.create(model=self.model, input=batch)
            ordered = sorted(resp.data, key=lambda d: d.index)
            part = np.array([d.embedding for d in ordered], dtype="float32")
            parts.append(part)

        return np.concatenate(parts, axis=0) if len(parts) > 1 else parts[0]


NvidiaNemoEmbeddingProvider = NvidiaEmbeddingProvider


def get_embedding_provider(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    dim: Optional[int] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> EmbeddingProvider:
    """Factory to instantiate the appropriate embedding provider based on config."""
    from app.config import get_settings

    settings = get_settings()
    active_provider = (
        (provider or getattr(settings, "embedding_provider", None) or "nim")
        .strip()
        .lower()
    )

    if active_provider in ("nim", "nvidia", "nemotron"):
        return NvidiaEmbeddingProvider(
            model=model,
            dim=dim,
            api_key=api_key,
            base_url=base_url,
        )
    elif active_provider == "openai":
        return OpenAIEmbeddingProvider(
            model=model or settings.embedding_model,
            dim=dim or settings.embedding_dim,
            api_key=api_key or settings.openai_api_key,
            base_url=base_url or settings.openai_base_url,
        )
    else:
        raise ValueError(
            f"Unsupported embedding provider: {active_provider}. Choose 'nim' or 'openai'."
        )
