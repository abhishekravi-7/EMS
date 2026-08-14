"""
TokenTracer — the one-stop component that extracts, prices and persists a
single LLM call, using pluggable pricing and sink implementations.

This is the "interceptor" described in the refactor plan: an application wires
``TokenTracer(sink=..., pricing_provider=...)`` at its client boundary, then
hands the tracer a token count / error / latency tuple after each provider
call.  The tracer stamps an ISO timestamp and an estimated USD cost, and hands
the finished :class:`LLMCallRecord` to the sink.  No monkey-patching of
provider SDKs is involved — the application calls ``record(...)`` itself.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .core import LLMCallRecord, TokenUsage, utc_now_iso
from .pricing import (
    PricingProvider,
    estimate_cost_usd,
    get_default_pricing_provider,
)
from .sinks import NullTraceSink, TraceSink

__all__ = ["TokenTracer"]


def _normalize_usage(usage: Any) -> TokenUsage:
    """Accept either a :class:`TokenUsage` or a plain 4-sequence tuple."""
    if usage is None:
        return TokenUsage(None, None, None, None)
    if isinstance(usage, TokenUsage):
        return usage
    if isinstance(usage, Sequence) and not isinstance(usage, str | bytes):
        seq = tuple(usage)
        if len(seq) == 4:
            return TokenUsage(seq[0], seq[1], seq[2], seq[3])
    raise TypeError(
        "usage must be a TokenUsage or a 4-tuple "
        "(input_tokens, output_tokens, total_tokens, cached_tokens)"
    )


class TokenTracer:
    """
    Records one LLM call: normalises usage, prices it, persists it.

    Parameters
    ----------
    sink
        Destination for finished records (default: :class:`NullTraceSink`).
    pricing_provider
        Rate source for cost estimation (default: the package-wide default,
        a :class:`~token_tracing.pricing.StaticPricingProvider`).
    provider
        Default ``provider`` string stamped on every record (e.g. ``"groq"``);
        may be overridden per call.
    """

    def __init__(
        self,
        *,
        sink: TraceSink | None = None,
        pricing_provider: PricingProvider | None = None,
        provider: str | None = None,
    ) -> None:
        self.sink = sink or NullTraceSink()
        self.pricing_provider = pricing_provider or get_default_pricing_provider()
        self.provider = provider

    # ── Recording ──────────────────────────────────────────────────────────────

    def record(
        self,
        *,
        role: str,
        model: str,
        call_type: str,
        duration_ms: float,
        usage: TokenUsage | Sequence,
        attempt: int,
        is_retry: bool,
        endpoint: str | None = None,
        max_tokens: int | None = None,
        truncated: bool = False,
        error: str | None = None,
        provider: str | None = None,
        cache_hit: bool = False,
    ) -> LLMCallRecord:
        """
        Build and persist a single-call record, returning it for inspection.

        ``usage`` is a ``TokenUsage`` or a 4-sequence
        ``(input_tokens, output_tokens, total_tokens, cached_tokens)`` — the
        same shape VOXA's ``LLMClient`` already unpacked, so call sites stay
        unchanged.  A cost estimate is stamped via :func:`estimate_cost_usd`
        using this tracer's pricing provider.
        """
        tokens = _normalize_usage(usage)
        record = LLMCallRecord(
            provider=provider or self.provider,
            model=model,
            role=role,
            call_type=call_type,
            endpoint=endpoint,
            input_tokens=tokens.input_tokens,
            output_tokens=tokens.output_tokens,
            total_tokens=tokens.total_tokens,
            cached_tokens=tokens.cached_tokens,
            duration_ms=duration_ms,
            max_tokens=max_tokens,
            truncated=truncated,
            error=error,
            attempt=attempt,
            is_retry=is_retry,
            cache_hit=cache_hit,
            timestamp=utc_now_iso(),
            estimated_cost_usd=estimate_cost_usd(
                model,
                tokens.input_tokens,
                tokens.output_tokens,
                tokens.cached_tokens,
                provider=provider or self.provider,
                pricing_provider=self.pricing_provider,
            ),
        )
        self.sink.write(record)
        return record

    def record_from_response(
        self,
        *,
        resp: Any,
        role: str,
        model: str,
        call_type: str,
        duration_ms: float,
        attempt: int,
        is_retry: bool,
        endpoint: str | None = None,
        max_tokens: int | None = None,
        truncated: bool = False,
        provider: str | None = None,
    ) -> LLMCallRecord:
        """
        Convenience wrapper that extracts usage straight from an OpenAI-SDK
        response/chunk object before delegating to :meth:`record`.
        """
        from .extractor import extract_usage

        return self.record(
            role=role,
            model=model,
            call_type=call_type,
            duration_ms=duration_ms,
            usage=extract_usage(resp),
            attempt=attempt,
            is_retry=is_retry,
            endpoint=endpoint,
            max_tokens=max_tokens,
            truncated=truncated,
            provider=provider,
        )
