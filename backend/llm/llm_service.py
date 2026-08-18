"""
PHASE 4 - LLM service.

Wraps the OpenAI chat completions API.

WHAT THIS LAYER IS FOR:
Turning retrieved context into readable prose. It is the conversation layer,
never the source of truth. Every fact in an answer must have arrived through the
prompt from the knowledge base, the data layer, or the risk engine.

WHY TEMPERATURE IS LOW:
Grounded explanation, not creative writing. A low temperature keeps the model
close to the supplied context and reduces embellishment.

GRACEFUL DEGRADATION:
If no API key is configured the service reports unavailable rather than raising.
The pipeline still returns retrieved sources, so the system remains partially
usable and the failure is visible instead of silent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from backend.llm.prompts import SYSTEM_PROMPT

DEFAULT_MODEL = "gpt-4o-mini"


@dataclass
class LLMResponse:
    text: str
    model: str
    available: bool = True
    error: str | None = None
    usage: dict | None = None


class LLMService:
    """OpenAI chat completions wrapper."""

    def __init__(self) -> None:
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        self.model = os.getenv("LLM_MODEL") or DEFAULT_MODEL
        # Set LLM_BASE_URL to use an OpenAI-compatible provider such as
        # Gemini. Left blank, the client talks to OpenAI.
        self.base_url = os.getenv("LLM_BASE_URL") or None
        self.provider = os.getenv("LLM_PROVIDER") or "openai"
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1200"))
        self._client = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def status(self) -> dict:
        return {
            "connected": self.is_available(),
            "provider": self.provider,
            "model": self.model if self.is_available() else None,
            "message": (
                "LLM ready."
                if self.is_available()
                else "No API key. Set LLM_API_KEY in .env to enable answer "
                     "generation. Retrieval still works without it."
            ),
        }

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ImportError(
                    "openai package is not installed.\n"
                    "Install it with:  pip install openai"
                ) from exc
            self._client = OpenAI(api_key=self.api_key,
                                  base_url=self.base_url)
        return self._client

    def stream(self, user_prompt: str, system_prompt: str = SYSTEM_PROMPT):
        """
        Yield answer text chunk by chunk.

        Streaming is what makes TTFT measurable: without it the caller only
        learns the total round-trip time and cannot separate the time spent
        waiting for the first token from the time spent producing the rest.
        """
        if not self.is_available():
            raise RuntimeError("LLM not configured. Set LLM_API_KEY in .env.")

        client = self._get_client()
        stream = client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        for event in stream:
            if not event.choices:
                continue
            piece = event.choices[0].delta.content
            if piece:
                yield piece

    def generate(self, user_prompt: str,
                 system_prompt: str = SYSTEM_PROMPT) -> LLMResponse:
        """Generate a grounded answer. Never raises - errors come back on the object."""
        if not self.is_available():
            return LLMResponse(
                text="",
                model=self.model,
                available=False,
                error="LLM not configured. Set LLM_API_KEY in .env.",
            )

        try:
            client = self._get_client()
            completion = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            choice = completion.choices[0]
            usage = None
            if getattr(completion, "usage", None):
                usage = {
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens,
                }
            return LLMResponse(
                text=(choice.message.content or "").strip(),
                model=completion.model,
                available=True,
                usage=usage,
            )

        except Exception as exc:                      # noqa: BLE001
            # Surfaced to the caller rather than swallowed, so an investigator
            # never sees a blank answer with no explanation.
            return LLMResponse(
                text="",
                model=self.model,
                available=False,
                error=f"{type(exc).__name__}: {exc}",
            )


_service: LLMService | None = None


def get_llm_service() -> LLMService:
    global _service
    if _service is None:
        _service = LLMService()
    return _service
