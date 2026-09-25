"""
Pricing: pluggable per-model rate lookup plus pure cost arithmetic.

The cost math lives here exactly once:

* :func:`compute_cost` — pure arithmetic given explicit per-1M rates (used by
  VOXA's Mongo-backed ``PricingService.estimate_call_cost_usd`` so the admin
  router and the usage log agree).
* :func:`estimate_cost_usd` — convenience wrapper that resolves rates via a
  :class:`PricingProvider` and stamps an estimate on a trace record.

Rates are resolved through the :class:`PricingProvider` protocol so each
application can plug in its own source (VOXA wires a Mongo-backed provider;
other apps can use the bundled :class:`StaticPricingProvider` or their own).

Cached (prompt-prefix) tokens are priced at the model's ``cached_input_cost``
when available.  Two lookup behaviours are deliberately preserved for parity
with the code this package replaced:

* :func:`estimate_cost_usd` prices cached tokens at the rate returned by the
  provider's ``rates_for`` (explicit per-model rate, or the provider-level
  fallback rate from :data:`token_tracing.config.PROVIDER_FALLBACK_PER_1M`).
* :func:`cached_input_rate` additionally applies the provider discount
  multiplier from :data:`token_tracing.config.CACHED_INPUT_PRICE_MULTIPLIER`
  when a model row has no explicit cached rate — the admin/display path.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from .config import (
    CACHED_INPUT_PRICE_MULTIPLIER,
    PROVIDER_FALLBACK_PER_1M,
    SEED_PRICING,
)

__all__ = [
    "ModelRates",
    "PricingProvider",
    "StaticPricingProvider",
    "ChainedPricingProvider",
    "compute_cost",
    "estimate_cost_usd",
    "cached_input_rate",
    "get_default_pricing_provider",
    "set_default_pricing_provider",
]


@dataclass(frozen=True)
class ModelRates:
    """Per-1M-token rates for one model, in USD."""

    input_per_1m: float
    output_per_1m: float
    cached_input_per_1m: float | None = None


class PricingProvider(Protocol):
    """Anything that can resolve a model name to per-1M USD rates."""

    def rates_for(self, model: str | None) -> ModelRates | None:
        """Return rates for ``model`` (case-insensitive) or ``None`` if unknown."""
        ...


class StaticPricingProvider:
    """
    Table-backed pricing: model lookup against the seed table, then a
    provider-level fallback for unknown model names (e.g. env-overridden
    models).  Mirrors the behaviour of VOXA's old ``_get_pricing_rates``.
    """

    def __init__(
        self,
        seed_pricing: list[dict] | None = None,
        provider_fallback: dict[str, tuple[float, float]] | None = None,
        default_provider: str | Callable[[], str] | None = None,
    ) -> None:
        self._default_provider = default_provider
        self._provider_fallback = dict(provider_fallback or PROVIDER_FALLBACK_PER_1M)
        self._by_lower: dict[str, ModelRates] = {}
        for row in seed_pricing if seed_pricing is not None else SEED_PRICING:
            cached = row.get("cached_input_cost")
            self._by_lower[row["model_id"].lower()] = ModelRates(
                float(row["input_cost"]),
                float(row["output_cost"]),
                float(cached) if cached is not None else None,
            )

    def _current_provider(self) -> str:
        provider = self._default_provider
        if callable(provider):
            provider = provider()
        return (provider or "").lower()

    def rates_for(self, model: str | None) -> ModelRates | None:
        if not model:
            return None
        rates = self._by_lower.get(model.lower())
        if rates is not None:
            return rates
        current = self._current_provider()
        if not current:
            return None
        fallback = self._provider_fallback.get(current)
        if fallback is None:
            return None
        multiplier = CACHED_INPUT_PRICE_MULTIPLIER.get(current)
        cached_rate = fallback[0] * multiplier if multiplier is not None else None
        return ModelRates(fallback[0], fallback[1], cached_rate)


class ChainedPricingProvider:
    """
    Try several providers in order, returning the first non-``None`` result.

    VOXA uses this to chain its live Mongo-backed provider ahead of the
    bundled static one, so admin price edits show up in the usage log without
    losing the offline fallback.
    """

    def __init__(self, *providers: PricingProvider) -> None:
        self._providers = list(providers)

    def rates_for(self, model: str | None) -> ModelRates | None:
        for provider in self._providers:
            rates = provider.rates_for(model)
            if rates is not None:
                return rates
        return None


# ── Pure arithmetic ─────────────────────────────────────────────────────────────

def compute_cost(
    input_per_1m: float,
    output_per_1m: float,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    cached_input_per_1m: float | None = None,
) -> float:
    """
    USD cost for one call given explicit per-1M rates.

    Cached tokens are priced at ``cached_input_per_1m`` when both it and
    ``cached_tokens`` are set; otherwise every input token is billed at the
    full input rate.  Returns an unrounded float (matches VOXA's admin cost
    display behaviour); callers that need rounding do it themselves.
    """
    if cached_tokens and cached_input_per_1m is not None:
        uncached = max(input_tokens - cached_tokens, 0)
        input_cost = (
            uncached / 1_000_000 * input_per_1m
            + cached_tokens / 1_000_000 * cached_input_per_1m
        )
    else:
        input_cost = input_tokens / 1_000_000 * input_per_1m
    return input_cost + output_tokens / 1_000_000 * output_per_1m


# ── Provider-aware helpers ──────────────────────────────────────────────────────

_default_pricing_provider: PricingProvider | None = None


def get_default_pricing_provider() -> PricingProvider:
    """The package-wide pricing provider (a :class:`StaticPricingProvider` by default)."""
    global _default_pricing_provider
    if _default_pricing_provider is None:
        _default_pricing_provider = StaticPricingProvider()
    return _default_pricing_provider


def set_default_pricing_provider(provider: PricingProvider) -> None:
    """Replace the package-wide default pricing provider."""
    global _default_pricing_provider
    _default_pricing_provider = provider


def cached_input_rate(
    model: str | None,
    provider: str | None = None,
    pricing_provider: PricingProvider | None = None,
) -> float | None:
    """
    Cached-input USD per 1M tokens for ``model``.

    Lookup order:
    1. Explicit ``cached_input_cost`` on the model's rate row.
    2. Provider-level discount multiplier (``CACHED_INPUT_PRICE_MULTIPLIER``)
       applied to the model's input rate.
    3. ``None`` — no discount known, price at full rate.
    """
    if not model:
        return None
    rates = (pricing_provider or get_default_pricing_provider()).rates_for(model)
    if rates is None:
        return None
    if rates.cached_input_per_1m is not None:
        return rates.cached_input_per_1m
    multiplier = CACHED_INPUT_PRICE_MULTIPLIER.get((provider or "").lower())
    if multiplier is not None:
        return rates.input_per_1m * multiplier
    return None


def estimate_cost_usd(
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_tokens: int | None = None,
    *,
    provider: str | None = None,
    pricing_provider: PricingProvider | None = None,
) -> float | None:
    """
    Estimated USD cost of one call, rounded to 6 decimal places.

    Returns ``None`` when token counts are missing or the model is unknown, so
    callers skip cost logging instead of silently recording $0.  Cached tokens
    are priced via :func:`cached_input_rate`.
    """
    if input_tokens is None or output_tokens is None:
        return None
    provider_obj = pricing_provider or get_default_pricing_provider()
    rates = provider_obj.rates_for(model)
    if rates is None:
        return None
    # Cached tokens are priced at the rate the provider resolved for this model
    # (explicit per-model rate, or the provider-fallback rate for unknown
    # models).  This mirrors VOXA's old client-side estimation exactly — the
    # provider-discount multiplier is applied by the admin/display path via
    # ``cached_input_rate`` instead, so the usage log and admin numbers match
    # what they matched before the extraction.
    return round(
        compute_cost(
            rates.input_per_1m,
            rates.output_per_1m,
            input_tokens,
            output_tokens,
            cached_tokens or 0,
            rates.cached_input_per_1m,
        ),
        6,
    )
