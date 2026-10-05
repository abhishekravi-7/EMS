"""
token_tracing — reusable, plug-and-play LLM token tracing + dynamic pricing.

A small, dependency-free component that extracts token usage from OpenAI-
compatible responses, estimates USD cost with pluggable pricing, and persists
a flat per-call record through a pluggable sink.  It is deliberately
application-agnostic: it never imports application modules, never monkey-patches
the OpenAI SDK, and never edits per-call-site code.  Applications wire it once
at their LLM client boundary and call ``TokenTracer.record(...)``.

Quick start
-----------
.. code-block:: python

    import token_tracing as tt

    tt.init_token_tracing(
        sink=tt.JsonlTraceSink("logs/llm_usage.jsonl"),
        pricing_provider=tt.ChainedPricingProvider(
            my_live_provider,            # optional: Mongo/DB-backed rates
            tt.StaticPricingProvider(),  # bundled seed-table fallback
        ),
        provider="groq",
    )
    tracer = tt.get_token_tracer()

    # ...after each provider call...
    tracer.record(
        role="chat", model="llama-3.3-70b-versatile", call_type="chat",
        duration_ms=142.3, usage=tt.extract_usage(response),
        attempt=1, is_retry=False, endpoint="intent_classification",
    )

Public API
----------
* :class:`token_tracing.TokenTracer` — one-stop record() interceptor.
* :func:`token_tracing.init_token_tracing` / :func:`token_tracing.get_token_tracer`
* :func:`token_tracing.extract_usage` / :func:`token_tracing.extract_cached_tokens`
* :func:`token_tracing.estimate_cost_usd` / :func:`token_tracing.compute_cost`
* :class:`token_tracing.StaticPricingProvider` / :class:`token_tracing.ChainedPricingProvider`
* :class:`token_tracing.JsonlTraceSink` / :class:`token_tracing.NullTraceSink` /
  :class:`token_tracing.ListTraceSink`
* :class:`token_tracing.LLMCallRecord` / :class:`token_tracing.TokenUsage`
* :data:`token_tracing.SEED_PRICING` / :data:`token_tracing.STREAM_USAGE_PROVIDERS`
"""

from __future__ import annotations

from .config import (
    CACHED_INPUT_PRICE_MULTIPLIER,
    PRICING_PER_1M_TOKENS,
    PROVIDER_FALLBACK_PER_1M,
    SEED_PRICING,
    STREAM_USAGE_PROVIDERS,
    get_model_rates,
)
from .core import LLMCallRecord, TokenUsage
from .extractor import extract_cached_tokens, extract_usage
from .pricing import (
    ChainedPricingProvider,
    ModelRates,
    PricingProvider,
    StaticPricingProvider,
    cached_input_rate,
    compute_cost,
    estimate_cost_usd,
    get_default_pricing_provider,
    set_default_pricing_provider,
)
from .sinks import JsonlTraceSink, ListTraceSink, NullTraceSink, TraceSink
from .tracer import TokenTracer

__version__ = "1.0.0"

__all__ = [
    # Core model
    "LLMCallRecord",
    "TokenUsage",
    # Config tables
    "SEED_PRICING",
    "PRICING_PER_1M_TOKENS",
    "PROVIDER_FALLBACK_PER_1M",
    "CACHED_INPUT_PRICE_MULTIPLIER",
    "STREAM_USAGE_PROVIDERS",
    "get_model_rates",
    # Extraction
    "extract_usage",
    "extract_cached_tokens",
    # Pricing
    "ModelRates",
    "PricingProvider",
    "StaticPricingProvider",
    "ChainedPricingProvider",
    "compute_cost",
    "estimate_cost_usd",
    "cached_input_rate",
    "get_default_pricing_provider",
    "set_default_pricing_provider",
    # Sinks
    "TraceSink",
    "JsonlTraceSink",
    "ListTraceSink",
    "NullTraceSink",
    # Tracer
    "TokenTracer",
    # Module-level wiring
    "init_token_tracing",
    "get_token_tracer",
]

_default_tracer: TokenTracer | None = None


def init_token_tracing(
    *,
    sink: TraceSink | None = None,
    pricing_provider: PricingProvider | None = None,
    provider: str | None = None,
) -> TokenTracer:
    """
    Configure the package-wide :class:`TokenTracer` used by :func:`get_token_tracer`.

    Call this once at application startup (VOXA does it at its LLM client
    boundary).  Any argument left as ``None`` keeps the default: a
    :class:`NullTraceSink` and the bundled :class:`StaticPricingProvider`.
    Calling it again replaces the global tracer (e.g. swapping the sink in
    tests).
    """
    global _default_tracer
    _default_tracer = TokenTracer(
        sink=sink, pricing_provider=pricing_provider, provider=provider
    )
    return _default_tracer


def get_token_tracer() -> TokenTracer:
    """
    The package-wide :class:`TokenTracer`, creating a default one on first use.

    The default tracer records nothing (null sink) and prices with the bundled
    static tables — applications that want persistence must call
    :func:`init_token_tracing` (or pass their own tracer to their client).
    """
    global _default_tracer
    if _default_tracer is None:
        _default_tracer = TokenTracer()
    return _default_tracer
