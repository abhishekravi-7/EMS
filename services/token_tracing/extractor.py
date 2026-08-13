"""
Token extraction from OpenAI-compatible SDK response objects.

All supported providers (Groq, OpenAI, Together, DeepSeek, Anthropic, Gemini,
Ollama, Azure) go through the OpenAI chat-completions format, so the OpenAI SDK
already normalises usage to ``prompt_tokens`` / ``completion_tokens`` /
``total_tokens`` whenever a provider includes it.  Providers that omit usage
(e.g. Ollama) leave ``resp.usage`` as ``None``.

This module contains no provider- or application-specific logic — it just reads
token counts off a response/chunk object and normalises them into a single
:class:`token_tracing.core.TokenUsage` record.
"""

from __future__ import annotations

from typing import Any

from .core import TokenUsage


def extract_cached_tokens(usage: Any) -> int | None:
    """
    Prompt-cache hit tokens, if the provider's usage payload exposes them.

    OpenAI/Azure nest it under ``prompt_tokens_details.cached_tokens``;
    DeepSeek exposes it directly as ``prompt_cache_hit_tokens`` — a field
    outside the standard OpenAI schema, still readable because the SDK's
    BaseModel keeps unknown fields.  Returns ``None`` for providers that don't
    expose either (Groq, Together, Gemini, Ollama, Anthropic-via-compat).
    """
    if usage is None:
        return None
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        cached = getattr(details, "cached_tokens", None)
        if cached is not None:
            return cached
    return getattr(usage, "prompt_cache_hit_tokens", None)


def extract_usage(resp: Any) -> TokenUsage:
    """
    Pull ``(input_tokens, output_tokens, total_tokens, cached_tokens)`` from an
    OpenAI-SDK response or stream chunk.

    Handles both the standard ``prompt_tokens`` / ``completion_tokens`` /
    ``total_tokens`` names and the ``input_tokens`` / ``output_tokens`` aliases
    some providers use.  ``total_tokens`` is derived from the sum when a
    provider omits it.  Returns an all-``None`` record when no usage is present.
    """
    usage = getattr(resp, "usage", None)
    if usage is None:
        return TokenUsage(None, None, None, None)

    input_tokens = getattr(usage, "prompt_tokens", None)
    if input_tokens is None:
        input_tokens = getattr(usage, "input_tokens", None)

    output_tokens = getattr(usage, "completion_tokens", None)
    if output_tokens is None:
        output_tokens = getattr(usage, "output_tokens", None)

    total_tokens = getattr(usage, "total_tokens", None)
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    cached_tokens = extract_cached_tokens(usage)
    return TokenUsage(input_tokens, output_tokens, total_tokens, cached_tokens)
