"""Tests for NVIDIA NIM Nemotron Embedding Provider and Factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.rag.embeddings import (
    NvidiaEmbeddingProvider,
    get_embedding_provider,
)
from app.rag.vectorstore import RuleVectorStore
from app.config import get_settings
from tests.conftest import FakeEmbeddingProvider


def test_nim_embeddings_missing_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NIM_API_KEY", raising=False)
    get_settings.cache_clear()

    try:
        with pytest.raises(RuntimeError) as exc_info:
            NvidiaEmbeddingProvider(api_key=None)

        assert "No NVIDIA credentials found for embeddings" in str(exc_info.value)
    finally:
        get_settings.cache_clear()


def test_nim_embeddings_init_hosted():
    with patch("openai.OpenAI") as mock_client_cls:
        provider = NvidiaEmbeddingProvider(
            api_key="nvapi-test-key",
            model="nvidia/nemotron-3-embed-1b",
            dim=2048,
        )
        assert provider.model == "nvidia/nemotron-3-embed-1b"
        assert provider.dim == 2048
        assert provider.base_url == "https://integrate.api.nvidia.com/v1"
        mock_client_cls.assert_called_once()
        _, kwargs = mock_client_cls.call_args
        assert kwargs["api_key"] == "nvapi-test-key"
        assert kwargs["base_url"] == "https://integrate.api.nvidia.com/v1"


def test_nim_embeddings_self_hosted(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NIM_API_KEY", raising=False)
    get_settings.cache_clear()

    try:
        with patch("openai.OpenAI") as mock_client_cls:
            provider = NvidiaEmbeddingProvider(base_url="http://localhost:8000/v1")
            assert provider.base_url == "http://localhost:8000/v1"
            mock_client_cls.assert_called_once()
            _, kwargs = mock_client_cls.call_args
            assert kwargs["api_key"] == "not-used"
    finally:
        get_settings.cache_clear()


def test_nim_embeddings_batching():
    with patch("openai.OpenAI") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance

        # Return mock embeddings matching input length
        def fake_create(model, input):
            class _Datum:
                def __init__(self, i):
                    self.index = i
                    self.embedding = [0.1] * 2048

            class _Resp:
                def __init__(self, data):
                    self.data = data

            return _Resp([_Datum(i) for i in range(len(input))])

        mock_instance.embeddings.create.side_effect = fake_create

        provider = NvidiaEmbeddingProvider(
            api_key="nvapi-test-key",
            dim=2048,
            batch_size=2,
        )
        texts = ["chunk 1", "chunk 2", "chunk 3", "chunk 4", "chunk 5"]
        matrix = provider.embed(texts)

        # 5 texts with batch_size=2 should produce 3 create() calls: [2, 2, 1]
        assert mock_instance.embeddings.create.call_count == 3
        assert matrix.shape == (5, 2048)
        assert matrix.dtype == np.float32


def test_nim_embeddings_empty_input():
    with patch("openai.OpenAI"):
        provider = NvidiaEmbeddingProvider(api_key="nvapi-test-key", dim=2048)
        matrix = provider.embed([])
        assert matrix.shape == (0, 2048)


def test_get_embedding_provider_factory(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")
    with patch("openai.OpenAI"):
        for alias in ("nim", "nvidia", "nemotron"):
            provider = get_embedding_provider(alias)
            assert isinstance(provider, NvidiaEmbeddingProvider)
            assert provider.dim == 2048
            assert provider.model == "nvidia/nemotron-3-embed-1b"


def test_vectorstore_dimension_mismatch_triggers_recreate(tmp_path):
    # Create an initial store with dimension 256
    prov256 = FakeEmbeddingProvider(dim=256)
    store1 = RuleVectorStore(prov256, tmp_path / "index")
    store1.load_or_create()
    store1.add_texts(["sample text"], [{"source": "test.txt"}])
    assert store1.size == 1

    # Open store with a different dimension (e.g. 2048)
    prov2048 = FakeEmbeddingProvider(dim=2048)
    store2 = RuleVectorStore(prov2048, tmp_path / "index")
    store2.load_or_create()
    # Dimension mismatch detected, store cleanly resets
    assert store2.size == 0
    assert store2._index.d == 2048
