"""Tests for Google Gemini LLM client and provider factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.rag.llm import ClaudeClient, GeminiClient, get_llm_client
from app.rag.prompts import SYSTEM_ANALYZE, SYSTEM_EXTRACT, SYSTEM_SUMMARY


def test_gemini_client_missing_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        GeminiClient(api_key=None)

    assert "No Gemini credentials found" in str(exc_info.value)
    assert "GEMINI_API_KEY" in str(exc_info.value)


def test_gemini_client_init_with_key():
    with patch("google.genai.Client") as mock_client_cls:
        client = GeminiClient(api_key="test-api-key", model="gemini-2.5-flash")
        assert client.model == "gemini-2.5-flash"
        assert client.provider == "gemini"
        mock_client_cls.assert_called_once()
        _, kwargs = mock_client_cls.call_args
        assert kwargs["api_key"] == "test-api-key"
        assert kwargs["http_options"].timeout == 60000  # 60s in ms


def test_gemini_client_complete_standard():
    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "- plot area: 500 sq.m\n- height: 10m"
        mock_instance.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_instance

        client = GeminiClient(api_key="test-api-key")
        result = client.complete(system=SYSTEM_EXTRACT, user="Plan details...")

        assert result == "- plot area: 500 sq.m\n- height: 10m"
        mock_instance.models.generate_content.assert_called_once()
        call_kwargs = mock_instance.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-2.5-flash"
        assert call_kwargs["contents"] == "Plan details..."
        # Extract prompt does not contain "JSON", so response_mime_type is not JSON
        assert getattr(call_kwargs["config"], "response_mime_type", None) is None


def test_gemini_client_complete_json_mode():
    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"violations": []}'
        mock_instance.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_instance

        client = GeminiClient(api_key="test-api-key")
        result = client.complete(system=SYSTEM_ANALYZE, user="Rule excerpts...")

        assert result == '{"violations": []}'
        call_kwargs = mock_instance.models.generate_content.call_args.kwargs
        assert call_kwargs["config"].response_mime_type == "application/json"


def test_gemini_client_retries_on_failure():
    with (
        patch("google.genai.Client") as mock_client_cls,
        patch("time.sleep") as mock_sleep,
    ):
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Summary text"
        # First call fails, second call succeeds
        mock_instance.models.generate_content.side_effect = [
            RuntimeError("Rate limit / transient error"),
            mock_response,
        ]
        mock_client_cls.return_value = mock_instance

        client = GeminiClient(api_key="test-api-key", max_retries=2)
        result = client.complete(system=SYSTEM_SUMMARY, user="Facts and violations...")

        assert result == "Summary text"
        assert mock_instance.models.generate_content.call_count == 2
        mock_sleep.assert_called_once()


def test_gemini_client_exhausts_retries():
    with patch("google.genai.Client") as mock_client_cls, patch("time.sleep"):
        mock_instance = MagicMock()
        mock_instance.models.generate_content.side_effect = RuntimeError(
            "Permanent failure"
        )
        mock_client_cls.return_value = mock_instance

        client = GeminiClient(api_key="test-api-key", max_retries=1)
        with pytest.raises(RuntimeError) as exc_info:
            client.complete(system="test", user="test")

        assert "Permanent failure" in str(exc_info.value)
        assert mock_instance.models.generate_content.call_count == 2


def test_get_llm_client_factory(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    with patch("google.genai.Client"):
        client = get_llm_client("gemini")
        assert isinstance(client, GeminiClient)
        assert client.provider == "gemini"

    monkeypatch.setenv("ANTHROPIC_API_KEY", "claude-key")
    with patch("anthropic.Anthropic"):
        client = get_llm_client("anthropic")
        assert isinstance(client, ClaudeClient)
        assert client.provider == "anthropic"

    with pytest.raises(ValueError) as exc:
        get_llm_client("unknown-provider")
    assert "Unsupported LLM provider" in str(exc.value)


def test_health_endpoint_reports_gemini_model(app_client):
    resp = app_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "llm_provider" in data
    assert "llm_model" in data
