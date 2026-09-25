"""Chat LLM facade with Groq (primary) -> Ollama (fallback) streaming.

Exposes a single ``stream_chat`` async generator that yields plain text deltas.
Groq is tried first when configured; if it fails *before emitting any token*
(not configured, transport error, HTTP error), streaming falls through to a
local Ollama server. A failure *after* tokens have already been streamed is
surfaced rather than silently retried, to avoid emitting duplicated content.

``last_provider`` records which provider actually produced the answer, for the
final event's details.

When all providers fail, the exception message is a compound of all individual
failures so users see a single, actionable error instead of only the last one.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator

import token_tracing as tt
from app.core.config import settings
from app.core.exceptions import ChatLLMNotConfiguredError, ChatLLMServiceError
from app.infrastructure.llm.groq_client import GroqClient, GroqPermanentError
from app.infrastructure.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class ChatLLM:
    def __init__(
        self,
        groq_client: GroqClient | None = None,
        ollama_client: OllamaClient | None = None,
    ) -> None:
        self._groq = groq_client or GroqClient()
        self._ollama = ollama_client or OllamaClient()
        self.last_provider: str | None = None

    @property
    def last_usage(self) -> tuple[int, int, int, int] | None:
        """Get the token usage of the last successful provider call."""
        if self.last_provider == "ollama":
            return self._ollama.last_usage
        if self.last_provider == "groq":
            return self._groq.last_usage
        return None

    async def stream_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        endpoint: str | None = None,
        first_token_timeout: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        # Require Groq to be configured in User Settings
        if not self._groq.is_configured:
            raise ChatLLMNotConfiguredError("LLM is not configured. Please setup your credentials in User Settings.")

        providers = [self._groq]
        if self._ollama.is_configured:
            providers.append(self._ollama)

        errors: list[tuple[str, Exception]] = []
        total_start = time.time()
        fallback_timeout = first_token_timeout or settings.chat_llm_fallback_timeout_seconds

        for i, provider in enumerate(providers):
            started = False
            provider_start = time.time()
            logger.info("[ChatLLM] Attempting %s (attempt %s/%s)", provider.provider, i + 1, len(providers))

            try:
                # If this is the primary provider and we have a fallback, enforce a fast timeout
                # for the FIRST chunk. If it's slow to start, we fallback to the next provider.
                gen = provider.stream_chat(system_prompt, user_prompt, max_tokens=max_tokens)

                if i < len(providers) - 1:
                    try:
                        # Wait for the first token
                        first_delta = await asyncio.wait_for(gen.__anext__(), timeout=fallback_timeout)
                        started = True
                        self.last_provider = provider.provider
                        logger.info("[ChatLLM] %s first token received in %.2fs", provider.provider, time.time() - provider_start)
                        yield first_delta
                    except (asyncio.TimeoutError, StopAsyncIteration) as exc:
                        logger.warning("[ChatLLM] %s timed out or empty before first token (%.2fs). Falling back.", provider.provider, time.time() - provider_start)
                        errors.append((provider.provider, exc))

                        # Record the timeout attempt
                        self._record_call(provider, i, provider_start, endpoint, "timeout_before_first_token")
                        continue

                async for delta in gen:
                    if not started:
                        started = True
                        self.last_provider = provider.provider
                        logger.info("[ChatLLM] %s first token received in %.2fs", provider.provider, time.time() - provider_start)
                    yield delta

                if not started:
                    self.last_provider = provider.provider

                logger.info("[ChatLLM] Request completed successfully using %s in %.2fs", provider.provider, time.time() - provider_start)
                logger.info("[ChatLLM] Total response time: %.2fs", time.time() - total_start)

                # Record success
                self._record_call(provider, i, provider_start, endpoint, None)
                return

            except GroqPermanentError as exc:
                self._record_call(provider, i, provider_start, endpoint, str(exc))
                raise
            except (ChatLLMNotConfiguredError, ChatLLMServiceError, Exception) as exc:
                errors.append((provider.provider, exc))

                # Record the error attempt
                self._record_call(provider, i, provider_start, endpoint, str(exc))

                if started:
                    # If we already yielded some tokens, we must NOT fall back
                    raise
                logger.warning(
                    "[ChatLLM] Provider '%s' failed in %.2fs, trying next. Reason: %s",
                    provider.provider,
                    time.time() - provider_start,
                    exc,
                )
                continue

        if errors:
            if len(errors) == 1:
                _, exc = errors[0]
                raise exc
            # Multiple providers failed — combine their messages.
            parts = [f"{name}: {exc}" for name, exc in errors]
            combined = "All configured LLM providers failed. " + " | ".join(parts)
            logger.error("[ChatLLM] All providers failed: %s", combined)
            raise ChatLLMServiceError(combined)

        raise ChatLLMNotConfiguredError()

    def _record_call(self, provider, index, start_time, endpoint, error):
        """Helper to record an LLM call attempt to token_tracing."""
        try:
            from app.core.context import llm_values_ctx
            ctx_vals = llm_values_ctx.get()
            model_to_use = ctx_vals.get("selected_model") or provider._model
            tracer = tt.get_token_tracer()
            # Capture usage from the provider if it stored it during streaming
            usage = getattr(provider, "last_usage", None) or (0, 0, 0, 0)

            tracer.record(
                role="chat",
                model=model_to_use,
                call_type="chat_stream",
                duration_ms=(time.time() - start_time) * 1000,
                usage=usage,
                attempt=index + 1,
                is_retry=index > 0,
                endpoint=endpoint or "chatbot_rag",
                provider=provider.provider,
                error=error,
            )
        except Exception as trace_exc:  # noqa: BLE001
            logger.warning("[ChatLLM] Token tracing failed: %s", type(trace_exc).__name__)
