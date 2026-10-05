"""LLM client wrappers and factory for the analysis steps.

Supports Google Gemini (default, via the official `google-genai` SDK),
Anthropic Claude (via the `anthropic` SDK), and OpenRouter (via `openai`).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# Per-request timeout (seconds) and retry budget for the LLM/embeddings HTTP
# clients. Defaults come from Settings (LLM_TIMEOUT / LLM_MAX_RETRIES env vars)
# so operators can tune latency via config; passed to the SDK constructors.


class GeminiClient:
    """Google Gemini client wrapper for the compliance analysis steps.

    Uses the modern official `google-genai` SDK.
    Honours GEMINI_API_KEY (or GOOGLE_API_KEY) from the environment.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        from google import genai
        from google.genai import types

        settings = get_settings()
        if timeout is None:
            timeout = settings.llm_timeout
        if max_retries is None:
            max_retries = settings.llm_max_retries
        if max_tokens is None:
            max_tokens = settings.llm_max_tokens

        resolved_key = (
            api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or settings.gemini_api_key
        )
        if not resolved_key:
            raise RuntimeError(
                "No Gemini credentials found. Set GEMINI_API_KEY (or GOOGLE_API_KEY) "
                "in the environment."
            )

        # google-genai expects timeout in milliseconds
        http_options = types.HttpOptions(timeout=int(timeout * 1000))
        self._client = genai.Client(api_key=resolved_key, http_options=http_options)

        chosen_model = model or settings.llm_model
        if not chosen_model or chosen_model.startswith("claude-"):
            chosen_model = "gemini-2.5-flash"
        self.model = chosen_model
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.provider = "gemini"

    def complete(self, system: str, user: str) -> str:
        from google.genai import types

        config_kwargs = {
            "system_instruction": system,
            "max_output_tokens": self.max_tokens,
            "temperature": 0.0,
        }
        # If the system prompt requests strict/raw JSON (e.g. SYSTEM_ANALYZE or
        # SYSTEM_ANALYZE_REPAIR), ask for application/json to enforce valid syntax.
        if "JSON" in system:
            config_kwargs["response_mime_type"] = "application/json"

        config = types.GenerateContentConfig(**config_kwargs)

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=user,
                    config=config,
                )
                try:
                    text = response.text or ""
                except (AttributeError, ValueError):
                    text = ""
                return text
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Gemini complete() attempt %d/%d failed: %s",
                    attempt + 1,
                    self.max_retries + 1,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(1.0 * (attempt + 1))
                else:
                    raise last_exc
        return ""


class ClaudeClient:
    def __init__(
        self,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        from anthropic import Anthropic

        settings = get_settings()
        if timeout is None:
            timeout = settings.llm_timeout
        if max_retries is None:
            max_retries = settings.llm_max_retries
        token = (
            os.getenv("ANTHROPIC_AUTH_TOKEN")
            or os.getenv("ANTHROPIC_API_KEY")
            or settings.anthropic_api_key
        )
        if not token:
            raise RuntimeError(
                "No Anthropic credentials found. Set ANTHROPIC_AUTH_TOKEN "
                "(or ANTHROPIC_API_KEY) in the environment."
            )
        kwargs = {"timeout": timeout, "max_retries": max_retries}
        if settings.anthropic_base_url:
            kwargs["base_url"] = settings.anthropic_base_url
        if token:
            kwargs["auth_token"] = token
        self._client = Anthropic(**kwargs)

        chosen_model = settings.llm_model
        if not chosen_model or chosen_model.startswith("gemini-"):
            chosen_model = "claude-3-5-sonnet-20241022"
        self.model = chosen_model
        self.max_tokens = settings.llm_max_tokens
        self.provider = "anthropic"

    def complete(self, system: str, user: str) -> str:
        message = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            block.text
            for block in message.content
            if getattr(block, "type", "") == "text"
        )


class OpenRouter:
    def __init__(
        self,
        max_tokens: int,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        from openai import OpenAI

        settings = get_settings()
        if timeout is None:
            timeout = settings.llm_timeout
        if max_retries is None:
            max_retries = settings.llm_max_retries

        self._client = OpenAI(
            base_url=os.getenv("OPENROUTER_API_URL"),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            timeout=timeout,
            max_retries=max_retries,
        )
        self.max_tokens = max_tokens
        self.model = os.getenv("OPENROUTER_MODEL")
        self.provider = "openrouter"

    def complete(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""


def get_llm_client(
    provider: Optional[str] = None,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
) -> object:
    """Factory to instantiate the appropriate LLM client based on config or credentials."""
    settings = get_settings()
    active_provider = (provider or settings.llm_provider or "gemini").strip().lower()

    if active_provider == "gemini":
        return GeminiClient(timeout=timeout, max_retries=max_retries)
    elif active_provider in ("anthropic", "claude"):
        return ClaudeClient(timeout=timeout, max_retries=max_retries)
    elif active_provider == "openrouter":
        return OpenRouter(
            max_tokens=settings.llm_max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )
    else:
        raise ValueError(
            f"Unsupported LLM provider: {active_provider}. Choose 'gemini', 'anthropic', or 'openrouter'."
        )
