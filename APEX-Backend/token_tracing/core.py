"""
Core data model for the reusable token-tracing component.

This module is deliberately free of any application- or provider-specific
knowledge. It defines the one flat record that every LLM call trace is
serialised into, so a single schema flows through extraction -> pricing ->
storage regardless of which application (VOXA or another) is using it.

Schema
------
``LLMCallRecord`` is intentionally flat: every field maps straight onto a JSON
key / Mongo document field with no pre-processing, mirroring the schema that
VOXA's ``backend/logs/llm_usage.jsonl`` already used before this package was
extracted. ``to_dict()`` derives ``prompt_cache_hit`` from ``cached_tokens``
so the stored value can never disagree with the raw token counts.
"""

from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

# Field order is ``(input_tokens, output_tokens, total_tokens, cached_tokens)``
# — the same 4-tuple shape VOXA's LLMClient already used internally, kept as a
# plain ``namedtuple`` so existing unpacking code keeps working unchanged.
TokenUsage = namedtuple("TokenUsage", "input_tokens output_tokens total_tokens cached_tokens")


def utc_now_iso() -> str:
    """ISO-8601 timestamp (UTC, with tzinfo) used for trace records."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LLMCallRecord:
    """
    A single recorded LLM call.

    ``timestamp`` and ``estimated_cost_usd`` are normally filled in by
    :class:`token_tracing.TokenTracer` at record time; callers only need to
    provide the token counts plus any identifying metadata they have.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    provider: str | None = None          # e.g. "groq", "openai", "azure"
    model: str | None = None             # actual model string served
    role: str = "chat"                   # "chat" | "vision" | custom
    call_type: str = "chat"              # "chat" | "chat_stream" | custom
    endpoint: str | None = None          # optional task label, e.g. "intent_classification"

    # ── Tokens ────────────────────────────────────────────────────────────────
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None     # provider prompt-prefix cache hits

    # ── Timing / limits ───────────────────────────────────────────────────────
    duration_ms: float | None = None
    max_tokens: int | None = None        # the requested output ceiling
    truncated: bool = False              # True when finish_reason == "length"

    # ── Outcome ───────────────────────────────────────────────────────────────
    error: str | None = None
    attempt: int = 1                     # 1-based attempt number
    is_retry: bool = False
    cache_hit: bool = False              # application-level cache hit (not prompt caching)

    # ── Stamped by TokenTracer ────────────────────────────────────────────────
    timestamp: str | None = None
    estimated_cost_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Flat dict ready for JSON serialisation or a document store."""
        return {
            "timestamp": self.timestamp,
            "provider": self.provider,
            "role": self.role,
            "model": self.model,
            "call_type": self.call_type,
            "endpoint": self.endpoint,
            "duration_ms": round(self.duration_ms, 1) if self.duration_ms is not None else None,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cached_tokens": self.cached_tokens,
            "prompt_cache_hit": bool(self.cached_tokens),
            "estimated_cost_usd": self.estimated_cost_usd,
            "attempt": self.attempt,
            "is_retry": self.is_retry,
            "cache_hit": self.cache_hit,
            "max_tokens": self.max_tokens,
            "truncated": self.truncated,
            "error": self.error,
        }
