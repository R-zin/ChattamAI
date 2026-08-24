"""Anthropic Claude client wrapper for the analysis steps.

Uses the official SDK, which automatically honours ANTHROPIC_BASE_URL and
ANTHROPIC_AUTH_TOKEN from the environment (the local proxy in this project).
"""

from __future__ import annotations

import os
from typing import Optional

from app.config import get_settings

# Per-request timeout (seconds) and retry budget for the LLM/embeddings HTTP
# clients. Defaults come from Settings (LLM_TIMEOUT / LLM_MAX_RETRIES env vars)
# so operators can tune latency via config; passed to the SDK constructors
# (Anthropic / OpenAI both accept `timeout` and `max_retries`).


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
        if not (settings.anthropic_api_key or os.getenv("ANTHROPIC_AUTH_TOKEN")):
            raise RuntimeError(
                "No Anthropic credentials found. Set ANTHROPIC_AUTH_TOKEN "
                "(or ANTHROPIC_API_KEY) in the environment."
            )
        kwargs = {"timeout": timeout, "max_retries": max_retries}
        if settings.anthropic_base_url:
            kwargs["base_url"] = settings.anthropic_base_url
        # Prefer explicit token, fall back to SDK's own env handling.
        token = os.getenv("ANTHROPIC_AUTH_TOKEN") or settings.anthropic_api_key
        if token:
            kwargs["auth_token"] = token
        self._client = Anthropic(**kwargs)
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens

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

    def complete(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content
