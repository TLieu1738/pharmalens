"""Thin, typed wrapper around the Anthropic SDK used by the planner and synthesis agents.

Agents depend on the :class:`StructuredLLM` protocol so tests can substitute a fake without network access.
The LLM is only ever asked to plan or to write prose over evidence we retrieved — never to fetch data.
"""

from __future__ import annotations

import logging
import time
from typing import Protocol, TypeVar

import anthropic
from pydantic import BaseModel

from app.config import Settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(Exception):
    """The LLM could not produce a usable structured response."""


class LLMRefusalError(LLMError):
    def __init__(self, category: str | None) -> None:
        super().__init__(f"model declined the request (category={category or 'unspecified'})")
        self.category = category


class LLMNotConfiguredError(LLMError):
    pass


class StructuredLLM(Protocol):
    async def structured(
        self, *, system: str, prompt: str, output: type[T], effort: str = "medium", max_tokens: int = 16000
    ) -> T: ...


class AnthropicLLM:
    """Structured-output calls to the Anthropic API via `messages.parse`, with server-side refusal fallback."""

    def __init__(self, settings: Settings, client: anthropic.AsyncAnthropic | None = None) -> None:
        if client is None:
            if settings.anthropic_api_key is None:
                raise LLMNotConfiguredError("ANTHROPIC_API_KEY is not set")
            client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key.get_secret_value(), max_retries=2, timeout=180.0
            )
        if not settings.anthropic_model:
            raise LLMNotConfiguredError("ANTHROPIC_MODEL is not set")
        self._client = client
        self._model = settings.anthropic_model

    @property
    def model(self) -> str:
        return self._model

    async def structured(
        self, *, system: str, prompt: str, output: type[T], effort: str = "medium", max_tokens: int = 16000
    ) -> T:
        started = time.perf_counter()
        try:
            response = await self._client.beta.messages.parse(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=output,
                output_config={"effort": effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as exc:
            raise LLMError("Anthropic authentication failed — check ANTHROPIC_API_KEY") from exc
        except anthropic.NotFoundError as exc:
            raise LLMError(f"model '{self._model}' not available — check ANTHROPIC_MODEL") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("Anthropic rate limit reached after retries") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Anthropic API error (HTTP {exc.status_code})") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("could not reach the Anthropic API") from exc

        usage = response.usage
        logger.info(
            "llm_call schema=%s model=%s stop_reason=%s input_tokens=%s output_tokens=%s elapsed_ms=%d",
            output.__name__,
            response.model,
            response.stop_reason,
            usage.input_tokens,
            usage.output_tokens,
            int((time.perf_counter() - started) * 1000),
        )
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise LLMRefusalError(getattr(details, "category", None))
        if response.stop_reason == "max_tokens":
            raise LLMError("response truncated at max_tokens")
        parsed = response.parsed_output
        if parsed is None:
            raise LLMError("model response did not match the expected schema")
        return parsed
