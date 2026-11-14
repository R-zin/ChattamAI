"""Provider detection must ignore the 'none' placeholders infra templates inject."""

import pytest

from app import config

ALL_KEYS = [
    "LLM_PROVIDER",
    "EMBEDDING_PROVIDER",
    "NVIDIA_API_KEY",
    "NIM_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "OPENAI_API_KEY",
    "VERIFIER_API_KEY",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ALL_KEYS:
        monkeypatch.delenv(k, raising=False)


def test_placeholder_nvidia_key_does_not_select_nim(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "none")
    monkeypatch.setenv("GEMINI_API_KEY", "real-gemini-key")
    assert config._default_llm_provider() == "gemini"
    assert config._default_embedding_provider() == "openai"


def test_placeholder_provider_name_is_ignored(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "real")
    assert config._default_llm_provider() == "anthropic"


def test_real_nvidia_key_selects_nim(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-real")
    assert config._default_llm_provider() == "nim"
    assert config._default_embedding_provider() == "nim"


def test_key_falls_back_past_placeholder(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "none")
    monkeypatch.setenv("NIM_API_KEY", "nvapi-real")
    assert config.Settings().nvidia_api_key == "nvapi-real"


def test_placeholder_verifier_key_is_none(monkeypatch):
    monkeypatch.setenv("VERIFIER_API_KEY", "none")
    monkeypatch.setenv("OPENAI_API_KEY", "none")
    assert config.Settings().verifier_api_key is None
