"""Gemini-primary LLM with Ollama as ultimate fallback.

Policy (per user requirement):
  - Gemini is ALWAYS tried first.
  - Ollama is used ONLY when a Gemini request fails AND the required
    wait before retrying exceeds the fallback threshold (default 180s,
    i.e. the low end of "3-5 mins"). This avoids the ~50min/3-loop
    Ollama cost unless Gemini would force a long stall.
  - After falling back for one call, the next call tries Gemini again
    (no permanent stickiness).

Env overrides:
    GEMINI_MODEL / GEMINI_API_KEY / GEMINI_TEMP / GEMINI_THINKING
    OLLAMA_MODEL / OLLAMA_HOST / OLLAMA_TEMP / OLLAMA_NUM_CTX
    LLM_FALLBACK_DELAY_THRESHOLD (seconds, default "180")
        Fallback triggers when the server-hinted or backoff delay for
        the next Gemini retry is >= this value.
    LLM_GEMINI_BUDGET (seconds, default "300")
        Fallback triggers when cumulative time spent on Gemini attempts
        for a single generate() call exceeds this budget.
    LLM_MAX_RETRIES / LLM_RETRY_BASE_DELAY / LLM_RETRY_MAX_DELAY
        (Gemini retry behavior; see coverage_agent.retry)
"""

from __future__ import annotations

import logging
import os
import time

from .retry import (
    await_with_retries,
    backoff_delay,
    is_retryable,
    server_hint_delay,
    _env_float,
    _env_int,
)

logger = logging.getLogger(__name__)


def _fallback_threshold() -> float:
    return _env_float("LLM_FALLBACK_DELAY_THRESHOLD", 180.0)


def _gemini_budget() -> float:
    return _env_float("LLM_GEMINI_BUDGET", 300.0)


class GeminiWithOllamaFallback:
    """CoverageLLM: Gemini first, Ollama only on long-wait Gemini failure."""

    def __init__(
        self,
        gemini_model: str | None = None,
        ollama_model: str | None = None,
        fallback_threshold: float | None = None,
        gemini_budget: float | None = None,
        gemini_timeout: float = 300.0,
        ollama_timeout: float = 900.0,
    ):
        self.gemini_model = gemini_model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.ollama_model = ollama_model or os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")
        self.fallback_threshold = (
            fallback_threshold
            if fallback_threshold is not None
            else _fallback_threshold()
        )
        self.gemini_budget = (
            gemini_budget if gemini_budget is not None else _gemini_budget()
        )
        self.gemini_timeout = gemini_timeout
        self.ollama_timeout = ollama_timeout
        self._ollama = None
        self.fallbacks = 0  # observable counter for logs/tests

    def _gemini(self):
        from .gemini_llm import GeminiCoverageLLM

        return GeminiCoverageLLM(model=self.gemini_model, timeout=self.gemini_timeout)

    def _ollama_llm(self):
        if self._ollama is None:
            from .ollama_llm import OllamaCoverageLLM

            self._ollama = OllamaCoverageLLM(
                model=self.ollama_model, timeout=self.ollama_timeout
            )
        return self._ollama

    async def _gemini_generate_with_fallback_check(self, prompt: str) -> str:
        """Call Gemini with retries, but raise _FallbackNeeded instead of
        sleeping past the threshold."""
        from .gemini_llm import SYSTEM_PROMPT as GEMINI_SYSTEM
        from .retry import _env_float as _ef, _env_int as _ei

        max_retries = _ei("LLM_MAX_RETRIES", 6)
        base_delay = _ef("LLM_RETRY_BASE_DELAY", 5.0)
        max_delay = _ef("LLM_RETRY_MAX_DELAY", 120.0)

        # Build client lazily so missing key raises here (fail fast, no fallback
        # for misconfiguration — caller decides; we treat it as non-retryable).
        llm = self._gemini()
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=llm.api_key,
            http_options={"timeout": int(llm.timeout * 1000)},
        )
        config_kwargs: dict = {
            "system_instruction": GEMINI_SYSTEM,
            "response_mime_type": "application/json",
            "temperature": llm.temperature,
        }
        if llm.thinking_budget > 0:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=llm.thinking_budget
            )
        else:
            config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

        start = time.monotonic()
        last_exc: BaseException | None = None
        for attempt in range(max_retries + 1):
            try:
                response = await client.aio.models.generate_content(
                    model=llm.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_kwargs),
                )
                text = (response.text or "").strip()
                if not text:
                    raise RuntimeError("Gemini returned an empty response.")
                return text
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if not is_retryable(exc) or attempt >= max_retries:
                    raise
                hint = server_hint_delay(exc)
                delay = hint if hint is not None else backoff_delay(
                    attempt, base_delay, max_delay
                )
                elapsed = time.monotonic() - start
                if delay >= self.fallback_threshold or (
                    elapsed + delay
                ) >= self.gemini_budget:
                    logger.warning(
                        "Gemini %s hit %s; required wait %.1fs >= "
                        "fallback threshold %.1fs (elapsed %.1fs). "
                        "Falling back to Ollama %s for this call.",
                        llm.model,
                        str(exc)[:200],
                        delay,
                        self.fallback_threshold,
                        elapsed,
                        self.ollama_model,
                    )
                    raise _FallbackNeeded(str(exc), delay) from exc
                logger.warning(
                    "Gemini %s hit rate limit (%s). Waiting %.1fs "
                    "before retry %d/%d (below fallback threshold %.1fs).",
                    llm.model,
                    str(exc)[:200],
                    delay,
                    attempt + 1,
                    max_retries,
                    self.fallback_threshold,
                )
                import asyncio

                await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc

    async def generate(self, prompt: str) -> str:
        try:
            return await self._gemini_generate_with_fallback_check(prompt)
        except _FallbackNeeded as fb:
            self.fallbacks += 1
            logger.warning(
                "Using Ollama fallback (%s) after Gemini stall: %s",
                self.ollama_model,
                str(fb)[:200],
            )
            ollama = self._ollama_llm()
            return await await_with_retries(
                lambda: _ollama_chat(ollama, prompt),
                what=f"Ollama-fallback {self.ollama_model}",
            )
        except RuntimeError:
            # Non-retryable Gemini errors (bad key, empty response, missing
            # package): do NOT silently fallback — surface immediately so
            # misconfiguration is visible. Only long-wait stalls fallback.
            raise


async def _ollama_chat(ollama, prompt: str) -> str:
    from ollama import AsyncClient

    client = AsyncClient(host=ollama.host, timeout=ollama.timeout)
    from .ollama_llm import SYSTEM_PROMPT as OLLAMA_SYSTEM

    response = await client.chat(
        model=ollama.model,
        messages=[
            {"role": "system", "content": OLLAMA_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        format="json",
        options={"temperature": ollama.temperature, "num_ctx": ollama.num_ctx},
    )
    try:
        return response.message.content or "{}"
    except AttributeError:
        return response["message"]["content"]  # type: ignore[index]


class _FallbackNeeded(RuntimeError):
    def __init__(self, reason: str, delay: float):
        super().__init__(f"Gemini stall (wait {delay:.1f}s): {reason}")
        self.delay = delay
