"""Embedding providers.

The system retrieves Kerala Building Rules by semantic similarity. Embeddings
are behind a small interface so the backend can be swapped without touching the
rest of the pipeline. The default implementation uses OpenAI's embedding API.
"""

from __future__ import annotations

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
# Max texts sent per underlying `embeddings.create` call when batching.
_DEFAULT_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "128"))


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
        size = batch_size or _DEFAULT_BATCH_SIZE
        if size <= 0:
            size = _DEFAULT_BATCH_SIZE
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
        self._entries: dict = {}
        self._order: List[str] = []  # insertion order for eviction
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

    def _prune_locked(self, now: float) -> None:
        # Drop expired entries first.
        expired = [k for k in self._order if self._entries[k][1] <= now]
        for k in expired:
            self._entries.pop(k, None)
        # Then evict oldest until within capacity.
        while len(self._entries) >= self.maxsize and self._order:
            oldest = self._order.pop(0)
            self._entries.pop(oldest, None)

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype="float32")
        now = time.time()
        keys = [_cache_key(t) for t in texts]
        out: List[Optional[np.ndarray]] = [None] * len(texts)
        to_fetch_idx: List[int] = []
        to_fetch_txt: List[str] = []

        with self._lock:
            self._prune_locked(now)
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
                self._prune_locked(time.time())
                for i, vec in zip(to_fetch_idx, fresh):
                    key = keys[i]
                    self._entries[key] = (vec, time.time() + self.ttl)
                    if key not in self._order:
                        self._order.append(key)
                    out[i] = vec

        matrix = np.array([v for v in out], dtype="float32")
        return matrix


class NvidiaNemoEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dim: int = 1536):
        self.dim = dim
        self.model_name = os.getenv("NVIDIA_MODEL_NAME")
        from openai import OpenAI

        self._client = OpenAI(
            api_key=os.getenv("NVIDIA_API_KEY"), base_url=os.getenv("NVIDIA_API_URL")
        )

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype="float32")
        cleaned = [t.strip() or " " for t in texts]
        resp = self._client.embeddings.create(model=self.model_name, input=cleaned)
        ordered = sorted(resp.data, key=lambda d: d.index)
        matrix = np.array([d.embedding for d in ordered], dtype="float32")
        return matrix
