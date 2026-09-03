"""Offline tests for ``app.rag.embeddings``.

Covers the pure helpers (``l2_normalize``, ``_cache_key``), the thread-safe TTL
``EmbeddingCache`` wrapper (hits/misses, eviction, TTL expiry, out-of-order
input), and the ``OpenAIEmbeddingProvider`` credential guard + batching logic —
all without any network access. The OpenAI client is stubbed so no real API
call is ever made.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.rag.embeddings import (
    EmbeddingCache,
    OpenAIEmbeddingProvider,
    _cache_key,
    l2_normalize,
)
from tests.conftest import FakeEmbeddingProvider


# ---------------------------------------------------------------------------
# l2_normalize
# ---------------------------------------------------------------------------
def test_l2_normalize_produces_unit_rows():
    m = np.array([[3.0, 4.0], [0.0, 5.0], [1.0, 1.0]], dtype="float32")
    out = l2_normalize(m)
    norms = np.linalg.norm(out, axis=1)
    assert norms == pytest.approx(np.ones(3), rel=1e-6)
    assert out.dtype == np.float32


def test_l2_normalize_handles_1d_input():
    out = l2_normalize(np.array([3.0, 4.0], dtype="float32"))
    assert out.shape == (1, 2)
    assert np.linalg.norm(out[0]) == pytest.approx(1.0, rel=1e-6)


def test_l2_normalize_zero_vector_is_safe():
    # A zero row must not produce NaN/inf (norm floored).
    out = l2_normalize(np.array([[0.0, 0.0]], dtype="float32"))
    assert np.isfinite(out).all()
    assert out[0].tolist() == [0.0, 0.0]


def test_l2_normalize_inner_product_equals_cosine():
    # For unit vectors, inner product == cosine similarity in [-1, 1].
    a = l2_normalize(np.array([[1.0, 0.0]], dtype="float32"))
    b = l2_normalize(np.array([[1.0, 1.0]], dtype="float32"))
    cos = float((a @ b.T)[0, 0])
    assert -1.0 <= cos <= 1.0
    assert cos == pytest.approx(1.0 / np.sqrt(2.0), rel=1e-5)


# ---------------------------------------------------------------------------
# _cache_key
# ---------------------------------------------------------------------------
def test_cache_key_is_stable_and_content_based():
    k1 = _cache_key("hello world")
    k2 = _cache_key("hello world")
    k3 = _cache_key("different")
    assert k1 == k2
    assert k1 != k3
    # SHA-256 hex digest.
    assert len(k1) == 64 and all(c in "0123456789abcdef" for c in k1)


# ---------------------------------------------------------------------------
# EmbeddingCache
# ---------------------------------------------------------------------------
def test_cache_miss_then_hit_skips_provider():
    provider = FakeEmbeddingProvider()
    cache = EmbeddingCache(provider, ttl=300, maxsize=16)
    first = cache.embed(["alpha", "beta"])
    second = cache.embed(["alpha", "beta"])
    # The provider was called only once (the second call hit the cache).
    assert len(provider.calls) == 1
    np.testing.assert_allclose(first, second)
    stats = cache.stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 2


def test_cache_partial_hit_fetches_only_missing():
    provider = FakeEmbeddingProvider()
    cache = EmbeddingCache(provider, ttl=300, maxsize=16)
    cache.embed(["alpha", "beta"])
    # "alpha" is cached, "gamma" is new.
    cache.embed(["gamma", "alpha"])
    # Second provider call fetched ONLY the missing text.
    assert provider.calls[1] == ["gamma"]


def test_cache_preserves_input_order_with_mixed_hits():
    provider = FakeEmbeddingProvider(dim=32)
    cache = EmbeddingCache(provider, ttl=300, maxsize=16)
    cache.embed(["a", "b", "c"])
    out = cache.embed(["c", "a", "b"])
    fresh = provider.embed(["c", "a", "b"])
    np.testing.assert_allclose(out, fresh, rtol=1e-5)


def test_cache_empty_input_returns_empty_matrix():
    provider = FakeEmbeddingProvider()
    cache = EmbeddingCache(provider)
    out = cache.embed([])
    assert out.shape == (0, provider.dim)
    assert provider.calls == []


def test_cache_evicts_oldest_beyond_maxsize():
    provider = FakeEmbeddingProvider()
    cache = EmbeddingCache(provider, ttl=300, maxsize=2)
    cache.embed(["a", "b"])  # fills cache (size 2)
    cache.embed(["c"])  # forces eviction of the oldest ("a")
    # "a" was evicted, so re-embedding it misses the provider again.
    cache.embed(["a"])
    assert provider.calls[-1] == ["a"]


def test_cache_respects_ttl_expiry(monkeypatch):
    provider = FakeEmbeddingProvider()
    cache = EmbeddingCache(provider, ttl=100, maxsize=16)

    now = [1000.0]
    monkeypatch.setattr("app.rag.embeddings.time.time", lambda: now[0])

    cache.embed(["alpha"])
    assert len(provider.calls) == 1
    # Advance past the TTL: the entry expires and is re-fetched.
    now[0] += 200.0
    cache.embed(["alpha"])
    assert len(provider.calls) == 2


def test_cache_stats_shape():
    cache = EmbeddingCache(FakeEmbeddingProvider(), ttl=60, maxsize=4)
    stats = cache.stats()
    assert set(stats) == {"size", "hits", "misses", "maxsize", "ttl"}
    assert stats["maxsize"] == 4
    assert stats["ttl"] == 60


# ---------------------------------------------------------------------------
# OpenAIEmbeddingProvider (credential guard + batching, no network)
# ---------------------------------------------------------------------------
def test_openai_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIEmbeddingProvider()


class _StubEmbeddingsAPI:
    """Records each ``create`` call's input size; returns deterministic vectors."""

    def __init__(self, dim: int):
        self.dim = dim
        self.batch_sizes = []

    def create(self, model, input):  # noqa: A002 - mirrors the SDK signature
        self.batch_sizes.append(len(input))

        class _Datum:
            def __init__(self, i, dim):
                self.index = i
                self.embedding = [float(i)] * dim

        class _Resp:
            def __init__(self, data):
                self.data = data

        return _Resp([_Datum(i, self.dim) for i in range(len(input))])


def test_openai_embed_batch_splits_into_chunks(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    provider = OpenAIEmbeddingProvider(dim=8)
    stub = _StubEmbeddingsAPI(dim=8)
    # Replace the real client's embeddings endpoint with the stub.
    monkeypatch.setattr(provider._client, "embeddings", stub)

    texts = [f"text {i}" for i in range(5)]
    out = provider.embed_batch(texts, batch_size=2)
    # 5 texts in batches of 2 -> 3 create() calls of sizes 2, 2, 1.
    assert stub.batch_sizes == [2, 2, 1]
    assert out.shape == (5, 8)


def test_openai_embed_batch_empty_input(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    provider = OpenAIEmbeddingProvider(dim=8)
    out = provider.embed_batch([], batch_size=4)
    assert out.shape == (0, 8)
