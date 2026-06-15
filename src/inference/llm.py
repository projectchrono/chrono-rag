from __future__ import annotations

import os

import anthropic
from openai import OpenAI


class LLM:
    """Unified LLM wrapper supporting OpenAI and Anthropic models."""

    OPENAI_MODEL = "gpt-4o-mini"
    ANTHROPIC_MODEL = "claude-opus-4-8"

    SUPPORTED_MODELS = (OPENAI_MODEL, ANTHROPIC_MODEL)

    def __init__(self, model: str = ANTHROPIC_MODEL) -> None:
        if model not in self.SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported model '{model}'. Choose one of: {self.SUPPORTED_MODELS}"
            )
        self.model = model

    def complete(self, system: str, user: str) -> str:
        """Send a system + user prompt and return the assistant text."""
        if self.model == self.ANTHROPIC_MODEL:
            return self._complete_anthropic(system, user)
        return self._complete_openai(system, user)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _complete_anthropic(self, system: str, user: str) -> str:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return next(block.text for block in response.content if block.type == "text")

    def _complete_openai(self, system: str, user: str) -> str:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content
