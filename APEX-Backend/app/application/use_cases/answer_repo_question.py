"""Answer a repository question with retrieval-augmented generation.

Orchestrates the RAG pipeline: retrieve the most relevant knowledge chunks for
the repository (indexing on demand if the repo was analyzed but never indexed),
build a grounded prompt, then stream the answer from the chat LLM (Groq ->
Ollama). Retrieval is CPU-bound and runs in a threadpool; generation is async.
"""

import re
import time
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.application.use_cases.index_repository import (
    IndexRepositoryUseCase,
    RepositoryNotFoundForIndexingError,
)
from app.core.exceptions import RepositoryNotIndexedError
from app.infrastructure.llm.chat_llm import ChatLLM
from app.application.services.llm_token_tracing_service import LLMTokenTracingService
from app.infrastructure.persistence.models import User
from app.infrastructure.rag import prompt_builder, retriever, repo_index_locator
from app.shared import branding

logger = logging.getLogger(__name__)


@dataclass
class PreparedAnswer:
    system_prompt: str
    user_prompt: str
    repository_metadata: dict[str, Any]
    db: Session  # Database session for token tracing
    user_id: int | None = None  # User ID for token tracing
    job_id: str | None = None  # Job ID for token tracing
    repository_url: str | None = None  # Repository URL for token tracing
    retrieved_chunk_types: list[str] = field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)
    chat: ChatLLM | LLMTokenTracingService = field(default_factory=ChatLLM)


class AnswerRepoQuestionUseCase:
    def __init__(self, indexer: IndexRepositoryUseCase | None = None) -> None:
        self._indexer = indexer or IndexRepositoryUseCase()

    async def prepare(
        self,
        *,
        question: str,
        repository_url: str | None,
        db: Session,
        current_user: User,
        job_id: str | None = None,
        history: list[dict[str, str]] | None = None,
        page_context: dict[str, Any] | None = None,
    ) -> PreparedAnswer:
        """Retrieve context (indexing on demand) and build grounded prompts."""
        start_time = time.time()
        logger.info("[AnswerUseCase] Query received: %s", (question[:50] + "...") if len(question) > 50 else question)

        repo_url = (repository_url or "").strip()
        
        # Enforce user/job isolation
        if not job_id and repo_url:
            report = repo_index_locator.find_latest_report_by_url(repo_url)
            if report:
                job_id = report.get("jobId")

        from app.api.deps import verify_job_ownership
        if job_id:
            verify_job_ownership(db, job_id, current_user)
        elif repo_url:
            raise RepositoryNotIndexedError("No migration job found for this repository.")

        if not repo_url:
            raise RepositoryNotIndexedError(
                "A repository URL is required to answer questions about it."
            )

        # Intent detection: skip RAG for simple greetings/thanks/farewells to save 300-800ms
        if is_conversational_intent(question):
            logger.info("[AnswerUseCase] Conversational intent detected, skipping RAG retrieval.")
            repository_metadata = _metadata_from([], page_context, repo_url)

            tracing_chat = LLMTokenTracingService(
                chat_llm=ChatLLM(),
                db=db,
                user_id=current_user.id,
                job_id=job_id,
                repository_url=repo_url,
            )

            # Simple prompt for greetings that doesn't require repository context
            return PreparedAnswer(
                system_prompt='You are "JavaApex Assistant", a helpful expert assistant for a Java migration platform. Greet the user politely, acknowledge their message, and offer to help with questions about their repository analysis or migration strategy. Be concise.',
                user_prompt=f"User says: {question.strip()}",
                repository_metadata=repository_metadata,
                db=db,
                user_id=current_user.id,
                job_id=job_id,
                repository_url=repo_url,
                retrieved_chunk_types=["intent:conversational"],
                chat=tracing_chat,
            )

        retrieval_start = time.time()
        result = await run_in_threadpool(retriever.retrieve, question, repo_url, job_id)
        logger.info("[AnswerUseCase] RAG retrieval completed in %.2fms", (time.time() - retrieval_start) * 1000)

        if result.is_empty:
            # Analyzed but never indexed? Index on demand, then retry once.
            logger.info("[AnswerUseCase] Context empty, attempting on-demand indexing.")
            try:
                if job_id:
                    await run_in_threadpool(self._indexer.index_by_job_id, job_id)
                else:
                    await run_in_threadpool(self._indexer.index_by_repo_url, repo_url)
            except RepositoryNotFoundForIndexingError as exc:
                raise RepositoryNotIndexedError() from exc

            retrieval_retry_start = time.time()
            result = await run_in_threadpool(retriever.retrieve, question, repo_url, job_id)
            logger.info("[AnswerUseCase] Post-indexing RAG retrieval completed in %.2fms", (time.time() - retrieval_retry_start) * 1000)

            if result.is_empty:
                raise RepositoryNotIndexedError()

        repository_metadata = _metadata_from(result.chunks, page_context, repo_url)

        prompt_start = time.time()
        user_prompt = prompt_builder.build_user_prompt(
            question=question,
            retrieved_context=result.context,
            repository_metadata=repository_metadata,
            page_context=page_context,
            history=history,
        )
        logger.info("[AnswerUseCase] Prompt construction completed in %.2fms", (time.time() - prompt_start) * 1000)

        logger.info("[AnswerUseCase] Total preparation completed in %.2fms", (time.time() - start_time) * 1000)

        tracing_chat = LLMTokenTracingService(
            chat_llm=ChatLLM(),
            db=db,
            user_id=current_user.id,
            job_id=job_id,
            repository_url=repo_url,
        )

        return PreparedAnswer(
            system_prompt=prompt_builder.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            repository_metadata=repository_metadata,
            db=db,
            user_id=current_user.id,
            job_id=job_id,
            repository_url=repo_url,
            retrieved_chunk_types=[str(c.get("chunk_type")) for c in result.chunks],
            retrieved_chunks=result.chunks,
            chat=tracing_chat,
        )

    async def stream(self, prepared: PreparedAnswer) -> AsyncIterator[str]:
        """Yield answer text deltas for a prepared question.

        Deltas are passed through the branding sanitizer as a final guard so no
        internal tooling / recipe identifier can reach the user even if the model
        echoes one from its own knowledge.
        """
        raw_deltas = prepared.chat.stream_chat(
            prepared.system_prompt,
            prepared.user_prompt,
            endpoint="chatbot_rag"
        )
        async for delta in branding.sanitize_stream(raw_deltas):
            yield delta

    async def answer(
        self,
        *,
        question: str,
        repository_url: str | None,
        db: Session,
        current_user: User,
        job_id: str | None = None,
        history: list[dict[str, str]] | None = None,
        page_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Non-streaming variant: collect the full answer and return it."""
        prepared = await self.prepare(
            question=question,
            repository_url=repository_url,
            db=db,
            current_user=current_user,
            job_id=job_id,
            history=history,
            page_context=page_context,
        )
        parts = [delta async for delta in self.stream(prepared)]
        
        sources = []
        seen_files = set()
        for hit in getattr(prepared, "retrieved_chunks", []):
            file_path = hit.get("file_path")
            if file_path and file_path not in seen_files:
                sources.append({
                    "title": file_path,
                    "url": "#",
                    "excerpt": hit.get("text")[:120] + "..." if hit.get("text") else None
                })
                seen_files.add(file_path)

        return {
            "answer": "".join(parts).strip(),
            "rationale": [],
            "sources": sources,
            "details": {
                "provider_used": prepared.chat.last_provider,
                "repository": prepared.repository_metadata,
                "retrieved_chunk_types": prepared.retrieved_chunk_types,
            },
        }


def is_conversational_intent(text: str) -> bool:
    """Check if the user input is a simple greeting, thank you, or farewell."""
    # Matches common greetings, thanks, and farewells.
    # Regex covers start/end boundaries and optional trailing punctuation.
    pattern = (
        r"^\s*(hi|hello|hey|howdy|greetings|good\s+(morning|afternoon|evening)|"
        r"how\s+are\s+you|what's\s+up|yo|thanks|thank\s+you|bye|goodbye)"
        r"(\s+there)?\s*[?.!]*\s*$"
    )
    return bool(re.match(pattern, text, re.IGNORECASE))


def _metadata_from(
    chunks: list[dict[str, Any]],
    page_context: dict[str, Any] | None,
    repo_url: str,
) -> dict[str, Any]:
    """Prefer indexed metadata; fall back to the live page context."""
    payload = chunks[0] if chunks else {}
    repo_ctx = (page_context or {}).get("repository") or {}
    return {
        "repository_url": payload.get("repository_url") or repo_ctx.get("url") or repo_url,
        "repository_name": payload.get("repository_name") or repo_ctx.get("name"),
        "project_type": payload.get("project_type"),
        "java_version": payload.get("java_version"),
        "framework": payload.get("framework") or repo_ctx.get("language"),
    }

