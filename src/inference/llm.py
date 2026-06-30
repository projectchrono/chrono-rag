"""Backend-agnostic LLM wrapper for the BYOK answer path.

Supports three providers behind one `complete(system, user)` call:
  - `anthropic` : the Anthropic API (default model claude-opus-4-8).
  - `openai`    : the OpenAI API (default model gpt-4o-mini).
  - `local`     : any OpenAI-compatible local server (e.g. AMD Lemonade at
                  http://localhost:13305/v1), reusing the OpenAI client with a
                  base_url. Free and offline; no API key required.

Provider, model, base URL, and key resolve from explicit args first, then the
CHRONO_RAG_LLM_* env vars (see core.config), then per-provider defaults. SDKs
are imported lazily, so a local-only environment needs only the `openai`
client and a cloud-only environment needs only its own SDK.
"""
from __future__ import annotations

import os
from typing import Optional

from core import config


class LLM:
    """Unified LLM wrapper. Build with no args to resolve everything from the
    environment, or pass `provider` / `model` / `base_url` / `api_key` to override."""

    # Per-provider defaults.
    ANTHROPIC_MODEL = "claude-opus-4-8"
    OPENAI_MODEL = "gpt-4o-mini"
    LOCAL_MODEL = "Qwen2.5-Coder-7B-Instruct-GGUF"

    PROVIDERS = ("anthropic", "openai", "local")

    def __init__(
        self,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.base_url = base_url or config.llm_base_url()
        self.provider = self._resolve_provider(provider, model)
        if self.provider not in self.PROVIDERS:
            raise ValueError(
                f"Unsupported provider '{self.provider}'. Choose one of: {self.PROVIDERS}"
            )
        if self.provider == "local" and not self.base_url:
            raise ValueError(
                "provider 'local' requires a base URL. Set CHRONO_RAG_LLM_BASE_URL "
                "(e.g. http://localhost:13305/v1 for Lemonade) or pass base_url=."
            )
        self.model = model or config.llm_model() or self._default_model()
        self._api_key = api_key

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def _resolve_provider(self, provider: Optional[str], model: Optional[str]) -> str:
        """explicit arg > env > base_url (-> local) > model name > key > openai."""
        if provider:
            return provider.strip().lower()
        env = config.llm_provider()
        if env:
            return env
        if self.base_url:
            return "local"
        inferred = self._infer_provider_from_model(model)
        if inferred:
            return inferred
        if os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        return "openai"

    @staticmethod
    def _infer_provider_from_model(model: Optional[str]) -> Optional[str]:
        if not model:
            return None
        m = model.lower()
        if m.startswith(("gpt", "o1", "o3", "o4", "chatgpt")):
            return "openai"
        if m.startswith("claude"):
            return "anthropic"
        return None

    def _default_model(self) -> str:
        return {
            "anthropic": self.ANTHROPIC_MODEL,
            "openai": self.OPENAI_MODEL,
            "local": self.LOCAL_MODEL,
        }[self.provider]

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    def complete(self, system: str, user: str) -> str:
        """Send a system + user prompt and return the assistant text."""
        if self.provider == "anthropic":
            return self._complete_anthropic(system, user)
        return self._complete_openai(system, user)  # openai + local share the client

    def _complete_anthropic(self, system: str, user: str) -> str:
        import anthropic  # lazy: only needed on the Anthropic path

        key = self._api_key or config.llm_api_key() or os.getenv("ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=key)
        response = client.messages.create(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return next(block.text for block in response.content if block.type == "text")

    def _complete_openai(self, system: str, user: str) -> str:
        from openai import OpenAI  # lazy: openai + local

        key = self._api_key or config.llm_api_key() or os.getenv("OPENAI_API_KEY")
        if self.provider == "local" and not key:
            key = "local"  # local servers ignore the key; the SDK still wants one
        client = OpenAI(api_key=key, base_url=self.base_url or None)
        response = client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content
