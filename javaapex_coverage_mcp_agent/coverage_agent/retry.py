"""Retry-with-backoff for transient LLM errors (HTTP 429 / 503).

Free-tier LLM APIs (Gemini, Groq, OpenRouter) throttle aggressively:
per-minute quotas return 429 RESOURCE_EXHAUSTED, and overloaded
backends return 503 UNAVAILABLE. Both are worth waiting out instead
of crashing the coverage run.

Behavior:
    * Retries only retryable errors (see ``is_retryable``).
    * Honors a server-suggested delay (``retryDelay: "12s"`` in the
      error payload) when present.
    * Otherwise exponential backoff: base * 2**attempt, capped, plus
      up to 25% jitter so concurrent agents don't stampede.

Env overrides:
    LLM_MAX_RETRIES      (default "6")
    LLM_RETRY_BASE_DELAY (default "5.0" seconds)
    LLM_RETRY_MAX_DELAY  (default "120.0" seconds)
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re

logger = logging.getLogger(__name__)

RETRYABLE_CODES = frozenset({429, 503})

RETRYABLE_STATUSES = frozenset({
    "RESOURCE_EXHAUSTED",
    "RATE_LIMIT_EXCEEDED",
    "TOO_MANY_REQUESTS",
    "UNAVAILABLE",
})

_RETRY_DELAY_RE = re.compile(r'retryDelay["\']?\s*:\s*["\']?([\d.]+)s', re.IGNORECASE)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def is_retryable(exc: BaseException) -> bool:
    """True if ``exc`` looks like a transient rate-limit/overload error."""
    code = getattr(exc, "code", None)
    if isinstance(code, int) and code in RETRYABLE_CODES:
        return True
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and status_code in RETRYABLE_CODES:
        return True
    status = getattr(exc, "status", None)
    if isinstance(status, str) and status.upper() in RETRYABLE_STATUSES:
        return True
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "429",
            "503",
            "rate limit",
            "rate-limit",
            "ratelimit",
            "resource_exhausted",
            "too many requests",
            "overloaded",
            "service unavailable",
        )
    )


def server_hint_delay(exc: BaseException) -> float | None:
    """Extract a server-suggested wait (seconds) from the error, if any."""
    match = _RETRY_DELAY_RE.search(str(exc))
    if match:
        try:
            return max(0.0, float(match.group(1)))
        except ValueError:
            return None
    return None


def backoff_delay(attempt: int, base: float, cap: float) -> float:
    """Exponential backoff with jitter for 0-based ``attempt``."""
    delay = min(base * (2.0**attempt), cap)
    return delay + random.uniform(0, delay * 0.25)


async def await_with_retries(
    fn,
    *,
    what: str = "LLM request",
    max_retries: int | None = None,
    base_delay: float | None = None,
    max_delay: float | None = None,
):
    """Await ``fn()``, retrying retryable errors with backoff.

    Non-retryable errors are raised immediately. After ``max_retries``
    failed retries the last error is re-raised.
    """
    if max_retries is None:
        max_retries = _env_int("LLM_MAX_RETRIES", 6)
    if base_delay is None:
        base_delay = _env_float("LLM_RETRY_BASE_DELAY", 5.0)
    if max_delay is None:
        max_delay = _env_float("LLM_RETRY_MAX_DELAY", 120.0)

    last_exc: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 - inspected, maybe re-raised
            last_exc = exc
            if not is_retryable(exc) or attempt >= max_retries:
                raise
            hint = server_hint_delay(exc)
            delay = hint if hint is not None else backoff_delay(attempt, base_delay, max_delay)
            logger.warning(
                "%s hit rate limit (%s). Waiting %.1fs before retry %d/%d.",
                what,
                str(exc)[:200],
                delay,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None  # for type checkers; loop always raises or returns
    raise last_exc
