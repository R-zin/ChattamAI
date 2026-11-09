"""Tests for OpenAICompatibleClient and verifier LLM factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import get_settings
from app.rag.llm import OpenAICompatibleClient, get_llm_client, get_verifier_client
from app.rag.prompts import SYSTEM_ANALYZE, SYSTEM_EXTRACT, SYSTEM_SUMMARY


def test_openai_compatible_client_missing_key_hosted(monkeypatch):
    """Hosted provider without API key should raise RuntimeError."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()

    try:
        with pytest.raises(RuntimeError) as exc_info:
            OpenAICompatibleClient(api_key=None, provider_name="openai")
        assert "No API key provided for hosted OpenAI-compatible provider" in str(
            exc_info.value
        )
    finally:
        get_settings.cache_clear()


def test_openai_compatible_client_init_hosted():
    """Hosted client initialization sets expected properties and passes to OpenAI."""
    with patch("openai.OpenAI") as mock_openai_cls:
        client = OpenAICompatibleClient(
            api_key="sk-test-key-12345",
            model="gpt-4o-mini",
            provider_name="openai",
        )
        assert client.model == "gpt-4o-mini"
        assert client.provider == "openai"
        mock_openai_cls.assert_called_once()
        _, kwargs = mock_openai_cls.call_args
        assert kwargs["api_key"] == "sk-test-key-12345"
        assert kwargs["timeout"] == 60.0


def test_openai_compatible_client_init_self_hosted(monkeypatch):
    """Self-hosted endpoint without an API key should fallback to 'not-used'."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()

    try:
        with patch("openai.OpenAI") as mock_openai_cls:
            client = OpenAICompatibleClient(
                base_url="http://localhost:11434/v1",
                model="llama3",
                provider_name="ollama",
            )
            assert client.base_url == "http://localhost:11434/v1"
            assert client.model == "llama3"
            assert client.provider == "ollama"
            mock_openai_cls.assert_called_once()
            _, kwargs = mock_openai_cls.call_args
            assert kwargs["api_key"] == "not-used"
            assert kwargs["base_url"] == "http://localhost:11434/v1"
    finally:
        get_settings.cache_clear()


def test_openai_compatible_client_complete_standard():
    """Test text completion without JSON format."""
    with patch("openai.OpenAI") as mock_openai_cls:
        mock_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [
            MagicMock(
                message=MagicMock(content="- plot area: 450 sq.m\n- height: 8.5m")
            )
        ]
        mock_instance.chat.completions.create.return_value = mock_resp
        mock_openai_cls.return_value = mock_instance

        client = OpenAICompatibleClient(api_key="sk-test")
        result = client.complete(system=SYSTEM_EXTRACT, user="Plan details...")

        assert result == "- plot area: 450 sq.m\n- height: 8.5m"
        mock_instance.chat.completions.create.assert_called_once()
        call_kwargs = mock_instance.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["temperature"] == 0.0
        assert "response_format" not in call_kwargs


def test_openai_compatible_client_complete_json_mode():
    """Test completion requesting JSON format when system prompt contains json."""
    with patch("openai.OpenAI") as mock_openai_cls:
        mock_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content='{"violations": []}'))]
        mock_instance.chat.completions.create.return_value = mock_resp
        mock_openai_cls.return_value = mock_instance

        client = OpenAICompatibleClient(api_key="sk-test")
        result = client.complete(system=SYSTEM_ANALYZE, user="Rule excerpts...")

        assert result == '{"violations": []}'
        call_kwargs = mock_instance.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}


def test_openai_compatible_client_json_fallback_on_rejection():
    """When endpoint rejects response_format, client should retry without it."""
    with patch("openai.OpenAI") as mock_openai_cls:
        mock_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content='{"violations": []}'))]
        # First call fails on response_format, second succeeds without it
        mock_instance.chat.completions.create.side_effect = [
            RuntimeError(
                "400 BadRequest: response_format is not supported by this engine"
            ),
            mock_resp,
        ]
        mock_openai_cls.return_value = mock_instance

        client = OpenAICompatibleClient(api_key="sk-test")
        result = client.complete(system=SYSTEM_ANALYZE, user="Rule excerpts...")

        assert result == '{"violations": []}'
        assert mock_instance.chat.completions.create.call_count == 2
        second_call_kwargs = mock_instance.chat.completions.create.call_args_list[
            1
        ].kwargs
        assert "response_format" not in second_call_kwargs


def test_openai_compatible_client_retries_transient_failure():
    """Test exponential backoff retries on transient errors."""
    with patch("openai.OpenAI") as mock_openai_cls, patch("time.sleep") as mock_sleep:
        mock_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content="Summary text"))]
        mock_instance.chat.completions.create.side_effect = [
            RuntimeError("503 Service Unavailable"),
            mock_resp,
        ]
        mock_openai_cls.return_value = mock_instance

        client = OpenAICompatibleClient(api_key="sk-test", max_retries=2)
        result = client.complete(system=SYSTEM_SUMMARY, user="Facts...")

        assert result == "Summary text"
        assert mock_instance.chat.completions.create.call_count == 2
        mock_sleep.assert_called_once()


def test_openai_compatible_client_exhausts_retries():
    """Test failure raised when retry budget is exhausted."""
    with patch("openai.OpenAI") as mock_openai_cls, patch("time.sleep"):
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.side_effect = RuntimeError(
            "Fatal network error"
        )
        mock_openai_cls.return_value = mock_instance

        client = OpenAICompatibleClient(api_key="sk-test", max_retries=1)
        with pytest.raises(RuntimeError) as exc_info:
            client.complete(system="test", user="test")

        assert "Fatal network error" in str(exc_info.value)
        assert mock_instance.chat.completions.create.call_count == 2


def test_get_llm_client_factory_openai(monkeypatch):
    """Test factory resolution for openai and openai_compatible."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-factory-test")
    get_settings.cache_clear()

    try:
        with patch("openai.OpenAI"):
            for provider_name in ("openai", "openai_compatible"):
                client = get_llm_client(provider_name)
                assert isinstance(client, OpenAICompatibleClient)
                assert client.provider == provider_name
    finally:
        get_settings.cache_clear()


def test_get_verifier_client_disabled(monkeypatch):
    """When VERIFIER_ENABLED is false (default), get_verifier_client returns None."""
    monkeypatch.delenv("VERIFIER_ENABLED", raising=False)
    get_settings.cache_clear()

    try:
        assert get_verifier_client() is None
    finally:
        get_settings.cache_clear()


def test_get_verifier_client_enabled(monkeypatch):
    """When VERIFIER_ENABLED is true, get_verifier_client returns configured client."""
    monkeypatch.setenv("VERIFIER_ENABLED", "true")
    monkeypatch.setenv("VERIFIER_PROVIDER", "groq")
    monkeypatch.setenv("VERIFIER_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("VERIFIER_API_KEY", "gsk-mock-key")
    monkeypatch.setenv("VERIFIER_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setenv("VERIFIER_TEMPERATURE", "0.2")
    monkeypatch.setenv("VERIFIER_TIMEOUT", "30.0")
    monkeypatch.setenv("VERIFIER_MAX_RETRIES", "3")
    monkeypatch.setenv("VERIFIER_MAX_TOKENS", "1024")
    get_settings.cache_clear()

    try:
        with patch("openai.OpenAI") as mock_openai_cls:
            client = get_verifier_client()
            assert client is not None
            assert isinstance(client, OpenAICompatibleClient)
            assert client.provider == "groq"
            assert client.base_url == "https://api.groq.com/openai/v1"
            assert client.model == "llama-3.3-70b-versatile"
            assert client.temperature == 0.2
            assert client.timeout == 30.0
            assert client.max_retries == 3
            assert client.max_tokens == 1024

            mock_openai_cls.assert_called_once()
            _, kwargs = mock_openai_cls.call_args
            assert kwargs["api_key"] == "gsk-mock-key"
            assert kwargs["base_url"] == "https://api.groq.com/openai/v1"
    finally:
        get_settings.cache_clear()
