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
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session

# Import token tracing module
import token_tracing as tt
from app.core.context import job_id_ctx, repository_url_ctx, user_id_ctx
from app.infrastructure.llm.chat_llm import ChatLLM
from app.infrastructure.persistence.llm_token_repository import LLMTokenRepository
from app.infrastructure.persistence.models import LLMTokenUsage

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
        db: Session | None = None,
        user_id: int | None = None,
        job_id: str | None = None,
        repository_url: str | None = None,
    ):
        """Initialize the tracing service.
        
        Args:
            chat_llm: The underlying ChatLLM instance to wrap
            db: Database session (optional, context vars preferred)
            user_id: ID of the user making the request (optional)
            job_id: Migration job ID if applicable (optional)
            repository_url: Repository being analyzed (optional)
        """
        self._chat_llm = chat_llm
        self._db = db
        self._user_id = user_id
        self._job_id = job_id
        self._repository_url = repository_url

        self.last_provider: str | None = None

    async def stream_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        endpoint: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat response while tracking tokens via context."""
        user_token = None
        job_token = None
        repo_token = None

        if self._user_id:
            user_token = user_id_ctx.set(self._user_id)
        if self._job_id:
            job_token = job_id_ctx.set(self._job_id)
        if self._repository_url:
            repo_token = repository_url_ctx.set(self._repository_url)

        try:
            async for delta in self._chat_llm.stream_chat(
                system_prompt, user_prompt, endpoint=endpoint
            ):
                yield delta
            self.last_provider = self._chat_llm.last_provider
        finally:
            if user_token:
                user_id_ctx.reset(user_token)
            if job_token:
                job_id_ctx.reset(job_token)
            if repo_token:
                repository_url_ctx.reset(repo_token)

    def record_call(self, *args, **kwargs):
        """Deprecated: The global tracer now handles DB recording via context vars."""


class ChainedTraceSink:
    """Combines multiple sinks into one."""

    def __init__(self, sinks: list[tt.TraceSink]):
        self.sinks = sinks

    def write(self, record: tt.LLMCallRecord) -> None:
        for sink in self.sinks:
            try:
                sink.write(record)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[ChainedTraceSink] Sink failed: %s", exc)


class DatabaseTraceSink:
    """Implements token_tracing.TraceSink to store records in the database."""

    def __init__(self, db: Session | None = None):
        """Initialize with an optional database session.

        If no session is provided, it will attempt to use context vars and a fresh session.
        """
        self.db = db

    def write(self, record: tt.LLMCallRecord) -> None:
        """Write a token usage record to the database."""
        db = self.db
        should_close = False
        
        if db is None:
            try:
                from app.infrastructure.persistence.database import SessionLocal
                db = SessionLocal()
                should_close = True
            except Exception:  # noqa: BLE001
                return

        try:
            # Create an LLMTokenUsage record from the token_tracing record
            db_record = LLMTokenUsage(
                request_id=f"tt_{uuid.uuid4().hex[:12]}",
                user_id=user_id_ctx.get(),
                job_id=job_id_ctx.get(),
                provider=record.provider or "unknown",
                model=record.model,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                total_tokens=record.total_tokens,
                cached_tokens=record.cached_tokens,
                role=record.role,
                endpoint=record.endpoint,
                call_type=record.call_type,
                duration_ms=record.duration_ms,
                estimated_cost_usd=record.estimated_cost_usd,
                status="success" if record.error is None else "failure",
                error_message=record.error,
                attempt=record.attempt,
                is_retry=record.is_retry,
                repository_url=repository_url_ctx.get(),
            )
            LLMTokenRepository.create(db, db_record)
            if should_close:
                db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[DatabaseTraceSink] Failed to write record: %s",
                exc,
            )
        finally:
            if should_close and db:
                db.close()
