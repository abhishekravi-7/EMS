"""
Static configuration tables for the token-tracing package.

Everything here is plain data — the reusable component ships its own canonical
pricing seed table and provider behaviour flags so that applications do NOT
have to hand-copy pricing data.  Applications may override any of this at
runtime by supplying their own pricing provider (see ``token_tracing.pricing``);
the tables below are the offline default.

These tables are the extracted copies of what previously lived in VOXA's
``backend/config/pricing_config.py`` and ``backend/services/pricing_service.py``.
"""

from __future__ import annotations

# ── Streaming usage support ─────────────────────────────────────────────────────
# OpenAI-compatible providers whose streaming endpoint returns a final usage
# chunk when ``stream_options.include_usage`` is requested.  Anthropic / Gemini /
# Ollama compatibility layers don't reliably support it, so streaming usage is
# left unset for those instead of risking a request-shape error.
STREAM_USAGE_PROVIDERS: frozenset[str] = frozenset(
    {"groq", "openai", "azure", "together", "deepseek"}
)

# ── Prompt-cache discount multipliers ───────────────────────────────────────────
# Used when a model row has no explicit ``cached_input_cost``: the cached-input
# rate is ``input_cost * multiplier`` for these providers.
CACHED_INPUT_PRICE_MULTIPLIER: dict[str, float] = {
    "openai": 0.5,
    "azure": 0.5,
    "deepseek": 0.1,
}

# ── Provider-level fallback rates ───────────────────────────────────────────────
# USD per 1M tokens ``(input, output)`` used when a concrete model is unknown
# (e.g. an env-overridden model name that isn't in the seed table).  This was
# VOXA's ``_PROVIDER_FALLBACK_PER_1M`` in ``llm/client.py``.
PROVIDER_FALLBACK_PER_1M: dict[str, tuple[float, float]] = {
    "groq": (0.59, 0.79),
    "openai": (2.50, 10.00),
    "together": (0.88, 0.88),
    "deepseek": (0.27, 1.10),
    "anthropic": (3.00, 15.00),
    "gemini": (1.25, 5.00),
    "ollama": (0.0, 0.0),
    "azure": (2.50, 10.00),
}

# ── Canonical seed pricing table ────────────────────────────────────────────────
# USD per 1M tokens.  One row per model; ``cached_input_cost`` may be ``None``
# (meaning "no discount known — use provider multiplier or full price").  This
# is exactly the SEED_PRICING table VOXA used to maintain in
# ``services/pricing_service.py``.
SEED_PRICING: list[dict] = [
    # OpenAI
    {
        "model_id": "gpt-4o",
        "display_name": "GPT-4o",
        "provider": "openai",
        "input_cost": 2.50,
        "cached_input_cost": 1.25,    # 50% of input_cost
        "output_cost": 10.00,
        "notes": "OpenAI list price",
    },
    {
        "model_id": "gpt-4o-mini",
        "display_name": "GPT-4o Mini",
        "provider": "openai",
        "input_cost": 0.15,
        "cached_input_cost": 0.075,
        "output_cost": 0.60,
        "notes": "OpenAI list price",
    },
    # Groq — Llama
    {
        "model_id": "llama-3.3-70b-versatile",
        "display_name": "Llama 3.3 70B Versatile (Groq)",
        "provider": "groq",
        "input_cost": 0.59,
        "cached_input_cost": None,
        "output_cost": 0.79,
        "notes": "Groq list price",
    },
    {
        "model_id": "llama-3.1-8b-instant",
        "display_name": "Llama 3.1 8B Instant (Groq)",
        "provider": "groq",
        "input_cost": 0.05,
        "cached_input_cost": None,
        "output_cost": 0.08,
        "notes": "Groq list price",
    },
    # Together AI — Llama
    {
        "model_id": "meta-llama/llama-3.3-70b-instruct-turbo",
        "display_name": "Llama 3.3 70B Instruct Turbo (Together)",
        "provider": "together",
        "input_cost": 0.88,
        "cached_input_cost": None,
        "output_cost": 0.88,
        "notes": "Together list price",
    },
    {
        "model_id": "meta-llama/llama-3.1-8b-instruct-turbo",
        "display_name": "Llama 3.1 8B Instruct Turbo (Together)",
        "provider": "together",
        "input_cost": 0.18,
        "cached_input_cost": None,
        "output_cost": 0.18,
        "notes": "Together list price",
    },
    {
        "model_id": "meta-llama/llama-4-scout-17b-16e-instruct",
        "display_name": "Llama 4 Scout 17B (Together)",
        "provider": "together",
        "input_cost": 0.11,
        "cached_input_cost": None,
        "output_cost": 0.34,
        "notes": "Together list price",
    },
    # DeepSeek
    {
        "model_id": "deepseek-chat",
        "display_name": "DeepSeek Chat",
        "provider": "deepseek",
        "input_cost": 0.27,
        "cached_input_cost": 0.027,   # 10% of input_cost
        "output_cost": 1.10,
        "notes": "DeepSeek list price",
    },
    # Anthropic Claude
    {
        "model_id": "claude-3-5-sonnet-20241022",
        "display_name": "Claude 3.5 Sonnet",
        "provider": "anthropic",
        "input_cost": 3.00,
        "cached_input_cost": None,
        "output_cost": 15.00,
        "notes": "Anthropic list price",
    },
    {
        "model_id": "claude-3-haiku-20240307",
        "display_name": "Claude 3 Haiku",
        "provider": "anthropic",
        "input_cost": 0.25,
        "cached_input_cost": None,
        "output_cost": 1.25,
        "notes": "Anthropic list price",
    },
    {
        "model_id": "claude-haiku-4-5-20251001",
        "display_name": "Claude Haiku 4.5",
        "provider": "anthropic",
        "input_cost": 1.00,
        "cached_input_cost": None,
        "output_cost": 5.00,
        "notes": "Anthropic list price",
    },
    # Google Gemini
    {
        "model_id": "gemini-1.5-pro",
        "display_name": "Gemini 1.5 Pro",
        "provider": "gemini",
        "input_cost": 1.25,
        "cached_input_cost": None,
        "output_cost": 5.00,
        "notes": "Google list price",
    },
    {
        "model_id": "gemini-1.5-flash",
        "display_name": "Gemini 1.5 Flash",
        "provider": "gemini",
        "input_cost": 0.075,
        "cached_input_cost": None,
        "output_cost": 0.30,
        "notes": "Google list price",
    },
]

# Simple lookup table keyed by lowercase model_id, built once at import time.
# Values mirror the client-facing 3-tuple ``(input, output, cached | None)``.
PRICING_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    row["model_id"]: (float(row["input_cost"]), float(row["output_cost"]))
    for row in SEED_PRICING
}


def get_model_rates(model_name: str | None) -> tuple[float, float] | None:
    """Return ``(input_cost, output_cost)`` per 1M tokens for ``model_name``.

    Case-insensitive; returns ``None`` for unknown or missing model names so
    callers can flag the trace as cost-incomplete instead of silently pricing
    an unrecognized call at $0.  Retained for backwards compatibility with the
    old ``config.pricing_config.get_model_rates``.
    """
    if not model_name:
        return None
    return PRICING_PER_1M_TOKENS.get(str(model_name).lower())
