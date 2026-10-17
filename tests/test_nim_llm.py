"""Tests for NVIDIA NIM Nemotron LLM client and provider factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import get_settings
from app.rag.llm import NimClient, get_llm_client
from app.rag.prompts import SYSTEM_ANALYZE, SYSTEM_EXTRACT, SYSTEM_SUMMARY


def test_nim_client_missing_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NIM_API_KEY", raising=False)
    get_settings.cache_clear()

    try:
        with pytest.raises(RuntimeError) as exc_info:
            NimClient(api_key=None)

        assert "No NVIDIA credentials found" in str(exc_info.value)
        assert "NVIDIA_API_KEY" in str(exc_info.value)
    finally:
        get_settings.cache_clear()


def test_nim_client_init_hosted():
    with patch("openai.OpenAI") as mock_client_cls:
        client = NimClient(
            api_key="nvapi-test-key",
            model="nvidia/nemotron-3.5-super-vl-120b-a12b",
        )
        assert client.model == "nvidia/nemotron-3.5-super-vl-120b-a12b"
        assert client.provider == "nim"
        assert client.base_url == "https://integrate.api.nvidia.com/v1"
        mock_client_cls.assert_called_once()
        _, kwargs = mock_client_cls.call_args
        assert kwargs["api_key"] == "nvapi-test-key"
        assert kwargs["base_url"] == "https://integrate.api.nvidia.com/v1"


def test_nim_client_init_self_hosted(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NIM_API_KEY", raising=False)
    get_settings.cache_clear()

    try:
        with patch("openai.OpenAI") as mock_client_cls:
            # Self-hosted / local NIM container without an API key
            client = NimClient(base_url="http://localhost:8000/v1")
            assert client.base_url == "http://localhost:8000/v1"
            assert client.provider == "nim"
            mock_client_cls.assert_called_once()
            _, kwargs = mock_client_cls.call_args
            assert kwargs["api_key"] == "not-used"
    finally:
        get_settings.cache_clear()


def test_nim_client_complete_standard():
    with patch("openai.OpenAI") as mock_client_cls:
        mock_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [
            MagicMock(message=MagicMock(content="- plot area: 500 sq.m\n- height: 10m"))
        ]
        mock_instance.chat.completions.create.return_value = mock_resp
        mock_client_cls.return_value = mock_instance

        client = NimClient(api_key="nvapi-test-key")
        result = client.complete(system=SYSTEM_EXTRACT, user="Plan details...")

        assert result == "- plot area: 500 sq.m\n- height: 10m"
        mock_instance.chat.completions.create.assert_called_once()
        call_kwargs = mock_instance.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "nvidia/nemotron-3.5-super-vl-120b-a12b"
        assert call_kwargs["temperature"] == 0.0
        assert call_kwargs["messages"] == [
            {"role": "system", "content": SYSTEM_EXTRACT},
            {"role": "user", "content": "Plan details..."},
        ]
        assert "response_format" not in call_kwargs


def test_nim_client_complete_json_mode():
    with patch("openai.OpenAI") as mock_client_cls:
        mock_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content='{"violations": []}'))]
        mock_instance.chat.completions.create.return_value = mock_resp
        mock_client_cls.return_value = mock_instance

        client = NimClient(api_key="nvapi-test-key")
        result = client.complete(system=SYSTEM_ANALYZE, user="Rule excerpts...")

        assert result == '{"violations": []}'
        call_kwargs = mock_instance.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}


def test_nim_client_complete_json_fallback():
    with patch("openai.OpenAI") as mock_client_cls:
        mock_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content='{"violations": []}'))]
        # First call fails on response_format, second succeeds without it
        mock_instance.chat.completions.create.side_effect = [
            RuntimeError("Unsupported parameter: response_format"),
            mock_resp,
        ]
        mock_client_cls.return_value = mock_instance

        client = NimClient(api_key="nvapi-test-key")
        result = client.complete(system=SYSTEM_ANALYZE, user="Rule excerpts...")

        assert result == '{"violations": []}'
        assert mock_instance.chat.completions.create.call_count == 2
        # Second call should not have response_format
        second_call_kwargs = mock_instance.chat.completions.create.call_args_list[
            1
        ].kwargs
        assert "response_format" not in second_call_kwargs


def test_nim_client_retries_transient_failure():
    with patch("openai.OpenAI") as mock_client_cls, patch("time.sleep") as mock_sleep:
        mock_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content="Summary text"))]
        mock_instance.chat.completions.create.side_effect = [
            RuntimeError("Rate limit / 503 Service Unavailable"),
            mock_resp,
        ]
        mock_client_cls.return_value = mock_instance

        client = NimClient(api_key="nvapi-test-key", max_retries=2)
        result = client.complete(system=SYSTEM_SUMMARY, user="Facts and violations...")

        assert result == "Summary text"
        assert mock_instance.chat.completions.create.call_count == 2
        mock_sleep.assert_called_once()


def test_nim_client_exhausts_retries():
    with patch("openai.OpenAI") as mock_client_cls, patch("time.sleep"):
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.side_effect = RuntimeError(
            "Permanent failure"
        )
        mock_client_cls.return_value = mock_instance

        client = NimClient(api_key="nvapi-test-key", max_retries=1)
        with pytest.raises(RuntimeError) as exc_info:
            client.complete(system="test", user="test")

        assert "Permanent failure" in str(exc_info.value)
        assert mock_instance.chat.completions.create.call_count == 2


def test_get_llm_client_factory_nim(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")
    with patch("openai.OpenAI"):
        for alias in ("nim", "nvidia", "nemotron"):
            client = get_llm_client(alias)
            assert isinstance(client, NimClient)
            assert client.provider == "nim"
            assert client.model == "nvidia/nemotron-3.5-super-vl-120b-a12b"


def test_health_endpoint_reports_nim_provider(app_client):
    app_client.app.state.rag.llm_provider = "nim"
    app_client.app.state.rag.llm_model = "nvidia/nemotron-3.5-super-vl-120b-a12b"

    resp = app_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["llm_provider"] == "nim"
    assert data["llm_model"] == "nvidia/nemotron-3.5-super-vl-120b-a12b"
