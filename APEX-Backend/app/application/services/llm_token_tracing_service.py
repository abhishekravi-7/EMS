"""LLM Token Tracing Service.

Wraps the ChatLLM to automatically track token usage, provider fallbacks,
and response metrics. Integrates with the LLM Token Tracing module and
stores records in the database.

This is the integration layer that connects the token_tracing module
to the Java APEX backend, automatically capturing metrics for every LLM
request without requiring changes to existing chatbot code.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from collections.abc import AsyncIterator

# Import token tracing module
import token_tracing as tt
from app.core.context import job_id_ctx, repository_url_ctx, user_id_ctx
from app.infrastructure.llm.chat_llm import ChatLLM

logger = logging.getLogger(__name__)


class LLMTokenTracingService:
    """Wraps ChatLLM to automatically track token usage and metrics.
    
    This service:
    - Intercepts all LLM chat requests
    - Records provider and model information
    - Tracks token counts (input, output, cached)
    - Records request duration and success/failure
    - Tracks fallback events (Ollama -> Groq)
    - Stores all metrics in the database
    - Estimates cost using the token_tracing module pricing
    
    It's designed to be transparent to existing code — just use it as a
    drop-in replacement for ChatLLM.stream_chat().
    """

    def __init__(
        self,
        chat_llm: ChatLLM,
        user_id: int | str | None = None,
        job_id: str | None = None,
        repository_url: str | None = None,
    ):
        """Initialize the tracing service.
        
        Args:
            chat_llm: The underlying ChatLLM instance to wrap
            user_id: ID of the user making the request (optional)
            job_id: Migration job ID if applicable (optional)
            repository_url: Repository being analyzed (optional)
        """
        self._chat_llm = chat_llm
        self._user_id = user_id
        self._job_id = job_id
        self._repository_url = repository_url

        self.last_provider: str | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat_llm, name)


class MongoDBTraceSink:
    """Implements token_tracing.TraceSink to store records in MongoDB."""

    def __init__(self):
        from app.infrastructure.persistence.mongodb import mongodb_manager
        self._manager = mongodb_manager

    def write(self, record: tt.LLMCallRecord) -> None:
        """Write a token usage record to MongoDB (synchronously)."""
        db = self._manager.get_sync_db()
        if db is None:
            return

        try:
            doc = {
                "request_id": f"tt_{uuid.uuid4().hex[:12]}",
                "user_id": user_id_ctx.get(),
                "job_id": job_id_ctx.get(),
                "provider": record.provider or "unknown",
                "model": record.model,
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "total_tokens": record.total_tokens,
                "cached_tokens": record.cached_tokens,
                "role": record.role,
                "endpoint": record.endpoint,
                "call_type": record.call_type,
                "duration_ms": record.duration_ms,
                "estimated_cost_usd": record.estimated_cost_usd,
                "status": "success" if record.error is None else "failure",
                "error_message": record.error,
                "attempt": record.attempt,
                "is_retry": record.is_retry,
                "repository_url": repository_url_ctx.get(),
                "created_at": datetime.now(timezone.utc)
            }
            db.llm_token_usage.insert_one(doc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[MongoDBTraceSink] Failed to write record: %s", exc)


class ChainedTraceSink:
    """Sink that forwards records to multiple downstream sinks."""

    def __init__(self, sinks: list[Any]) -> None:
        self.sinks = sinks

    def write(self, record: tt.LLMCallRecord) -> None:
        for sink in self.sinks:
            try:
                sink.write(record)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Trace sink %s failed: %s", type(sink).__name__, exc)
