"""Anthropic Claude client wrapper for the analysis steps.

Uses the official SDK, which automatically honours ANTHROPIC_BASE_URL and
ANTHROPIC_AUTH_TOKEN from the environment (the local proxy in this project).
"""

from __future__ import annotations

import os

from app.config import get_settings


class ClaudeClient:
    def __init__(self) -> None:
        from anthropic import Anthropic

        settings = get_settings()
        if not (settings.anthropic_api_key or os.getenv("ANTHROPIC_AUTH_TOKEN")):
            raise RuntimeError(
                "No Anthropic credentials found. Set ANTHROPIC_AUTH_TOKEN "
                "(or ANTHROPIC_API_KEY) in the environment."
            )
        kwargs = {}
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
    def __init__(self,max_tokens: int) -> None:
        from openai import OpenAI
        self._client = OpenAI(base_url=os.getenv("OPENROUTER_API_URL"),api_key=os.getenv("OPENROUTER_API_KEY"))
        self.max_tokens = max_tokens
        self.model = os.getenv("OPENROUTER_MODEL")
    def complete(self, system: str, user: str) -> str:
        resp = self._client.completions.create(
            model=self.model, )
