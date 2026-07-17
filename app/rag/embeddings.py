"""Embedding providers.

The system retrieves Kerala Building Rules by semantic similarity. Embeddings
are behind a small interface so the backend can be swapped without touching the
rest of the pipeline. The default implementation uses OpenAI's embedding API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import numpy as np


class EmbeddingProvider(ABC):
    """Turns text into fixed-size vectors."""

    dim: int

    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """Return a (len(texts), dim) float32 array."""
        raise NotImplementedError


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
            import os

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
