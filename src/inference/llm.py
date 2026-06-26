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
        return self.complete_multiturn(system, [{"role": "user", "content": user}])

    def complete_multiturn(self, system: str, messages: list[dict]) -> str:
        """Send a conversation history and return the next assistant text.

        messages: alternating user/assistant dicts, e.g.
            [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
        The final message must have role "user".
        """
        if self.model == self.ANTHROPIC_MODEL:
            return self._complete_anthropic_multiturn(system, messages)
        return self._complete_openai_multiturn(system, messages)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _complete_anthropic_multiturn(self, system: str, messages: list[dict]) -> str:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=system,
            messages=messages,
        )
        return next(block.text for block in response.content if block.type == "text")

    def _complete_openai_multiturn(self, system: str, messages: list[dict]) -> str:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=self.model,
            temperature=0.1,
            top_p=0.95,
            max_completion_tokens=16384,
            messages=[{"role": "system", "content": system}] + messages,
        )
        return response.choices[0].message.content

    # kept for backwards compatibility
    def _complete_anthropic(self, system: str, user: str) -> str:
        return self._complete_anthropic_multiturn(system, [{"role": "user", "content": user}])

    def _complete_openai(self, system: str, user: str) -> str:
        return self._complete_openai_multiturn(system, [{"role": "user", "content": user}])
