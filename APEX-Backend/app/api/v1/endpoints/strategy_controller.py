"""Strategy chatbot (JavaApex Assistant) endpoints — mounted at ``/api``.

The Strategy chat widget calls these unversioned paths directly:
  * ``POST /api/strategy/query/stream`` — SSE stream (phase/chunk/final/error).
  * ``POST /api/strategy/query``        — non-streaming twin.
  * ``POST /api/strategy/index``        — build+upsert vectors for a job/repo.
  * ``POST /api/strategy/reindex``      — replace a repository's vectors.
  * ``GET  /api/strategy/repositories`` — list indexed repositories.

The SSE frame shape (``event:``/``data:`` JSON, ``\n\n``-separated) matches the
widget's ``flushEvent`` parser exactly — do not change it without updating the
frontend.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from app.api.deps import User, get_current_user
from app.application.use_cases.answer_repo_question import AnswerRepoQuestionUseCase, is_conversational_intent
from app.application.use_cases.index_repository import (
    IndexRepositoryUseCase,
    RepositoryNotFoundForIndexingError,
)
from app.core.config import settings
from app.core.exceptions import ChatLLMServiceError, RagDisabledError, RepositoryNotIndexedError, StrategyChatError
from app.infrastructure.llm.ollama_client import OllamaClient
from app.infrastructure.rag import vector_store
from app.schemas.strategy_schema import (
    IndexRequest,
    IndexResponse,
    RepositoriesResponse,
    StrategyAnswerResponse,
    StrategyQueryRequest,
)

logger = logging.getLogger("strategy")

router = APIRouter(prefix="/strategy", tags=["strategy"])

_answer_use_case = AnswerRepoQuestionUseCase()
_index_use_case = IndexRepositoryUseCase()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # Disable proxy buffering so events flush immediately.
    "X-Accel-Buffering": "no",
}


def _sse(event: str, payload: dict) -> str:
    """Format a single SSE frame the widget's parser understands."""
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


@router.post("/query/stream")
async def query_stream(
    payload: StrategyQueryRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> StreamingResponse:
    job_id = payload.job_id or "N/A"
    logger.info("[STRATEGY STREAM START] - UserID: %s - JobID: %s - Question: '%s'", current_user.id, job_id, payload.question[:60])
    async def event_stream() -> AsyncIterator[str]:
        try:
            # Skip RAG-related phase messages for simple greetings/thanks
            if not is_conversational_intent(payload.question):
                yield _sse("phase", {"message": "Reading strategy page"})

            history_dicts = [{"role": msg.role, "content": msg.content} for msg in payload.history] if payload.history else None
            prepared = await _answer_use_case.prepare(
                question=payload.question,
                repository_url=payload.repo_url,
                current_user=current_user,
                job_id=payload.job_id,
                history=history_dicts,
                page_context=payload.strategy_context,
            )

            # Stream references immediately to provide visual confirmation
            retrieved_chunks = getattr(prepared, "retrieved_chunks", [])
            if retrieved_chunks:
                sources = []
                seen_files = set()
                for hit in retrieved_chunks:
                    file_path = hit.get("file_path")
                    if file_path and file_path not in seen_files:
                        sources.append({
                            "title": file_path,
                            "url": "#",
                            "excerpt": hit.get("text")[:120] + "..." if hit.get("text") else None
                        })
                        seen_files.add(file_path)

                if sources:
                    yield _sse("references", {"sources": sources})
                    # Update status message to be more descriptive
                    chunk_count = len(retrieved_chunks)
                    file_count = len(seen_files)
                    yield _sse("phase", {"message": f"Analyzing {chunk_count} context chunks from {file_count} files..."})

            yield _sse("phase", {"message": "Preparing answer"})
            buffer: list[str] = []
            async for delta in _answer_use_case.stream(prepared):
                buffer.append(delta)
                yield _sse("chunk", {"chunk": delta})

            answer = "".join(buffer).strip()
            logger.info("[STRATEGY STREAM SUCCESS] - UserID: %s - JobID: %s - Provider: %s - Length: %d chars", current_user.id, job_id, prepared.chat.last_provider, len(answer))

            # Final source list using the standardized SourceReference format
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

            yield _sse(
                "final",
                {
                    "parsed": {
                        "answer": answer,
                        "rationale": [],
                    },
                    "sources": sources,
                    "details": {
                        "provider_used": prepared.chat.last_provider,
                        "repository": prepared.repository_metadata,
                        "retrieved_chunk_types": prepared.retrieved_chunk_types,
                    },
                },
            )
        except ChatLLMServiceError as exc:
            # Surface the specific LLM error (Groq failure, Ollama unavailable, etc.)
            error_msg = str(exc)
            # If it looks like a raw technical error, replace with a user-friendly version
            if "Local Ollama server could not be reached" in error_msg:
                error_msg = (
                    "The local AI service is currently unavailable. "
                    "Please make sure Ollama is running and the configured model is available. "
                    "Run: ollama serve"
                )
            yield _sse("error", {"message": error_msg, "status": "LLM_SERVICE_ERROR"})
        except StrategyChatError as exc:
            yield _sse("error", {"message": exc.message, "status": exc.status})
        except RepositoryNotIndexedError as exc:
            # Repository not indexed – advise client to index first
            yield _sse("error", {"message": str(exc), "status": "REPOSITORY_NOT_INDEXED"})
        except Exception as exc:  # noqa: BLE001 - surface a clean error, never a 500 stream
            logger.error("[STRATEGY STREAM ERROR] - UserID: %s - JobID: %s - Error: %s", current_user.id, job_id, exc)
            yield _sse(
                "error",
                {"message": "The assistant hit an unexpected error. Please try again.", "status": "INTERNAL_ERROR", "detail": str(exc)},
            )
    return StreamingResponse(
        event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS
    )


@router.post("/query", response_model=StrategyAnswerResponse)
async def query(
    payload: StrategyQueryRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    job_id = payload.job_id or "N/A"
    logger.info("[STRATEGY QUERY START] - UserID: %s - JobID: %s - Question: '%s'", current_user.id, job_id, payload.question[:60])
    try:
        history_dicts = [{"role": msg.role, "content": msg.content} for msg in payload.history] if payload.history else None
        result = await _answer_use_case.answer(
            question=payload.question,
            repository_url=payload.repo_url,
            current_user=current_user,
            job_id=payload.job_id,
            history=history_dicts,
            page_context=payload.strategy_context,
        )
    except StrategyChatError as exc:
        logger.warning("[STRATEGY QUERY CHAT ERROR] - JobID: %s - Status: %s - Message: %s", job_id, exc.status, exc.message)
        return JSONResponse(
            status_code=exc.http_status,
            content={"status": exc.status, "message": exc.message, "detail": exc.message},
        )
    except RepositoryNotIndexedError as exc:
        logger.warning("[STRATEGY QUERY UNINDEXED] - JobID: %s - Repo not indexed: %s", job_id, exc)
        # Repository not indexed yet – signal client to index first
        return JSONResponse(
            status_code=404,
            content={"status": "REPOSITORY_NOT_INDEXED", "message": str(exc), "detail": str(exc)},
        )
    except Exception as exc:
        logger.error("[STRATEGY QUERY FAILED] - JobID: %s - Error: %s", job_id, exc)
        return JSONResponse(
            status_code=500,
            content={"status": "INTERNAL_ERROR", "message": "An unexpected error occurred.", "detail": str(exc)},
        )
    logger.info("[STRATEGY QUERY SUCCESS] - UserID: %s - JobID: %s", current_user.id, job_id)
    return JSONResponse(status_code=200, content=result)



@router.post("/index", response_model=IndexResponse)
async def index(payload: IndexRequest) -> JSONResponse:
    return await _run_index(payload)


@router.post("/reindex", response_model=IndexResponse)
async def reindex(payload: IndexRequest) -> JSONResponse:
    # index_report already deletes existing points first, so reindex == index.
    return await _run_index(payload)


async def _run_index(payload: IndexRequest) -> JSONResponse:
    target = payload.job_id or payload.repo_url or "N/A"
    logger.info("[STRATEGY INDEX START] - Target: %s", target)
    if not settings.rag_enabled:
        exc = RagDisabledError()
        return JSONResponse(
            status_code=exc.http_status,
            content={"status": exc.status, "message": exc.message, "detail": exc.message},
        )
    try:
        if payload.job_id:
            outcome = await run_in_threadpool(_index_use_case.index_by_job_id, payload.job_id)
        elif payload.repo_url:
            outcome = await run_in_threadpool(_index_use_case.index_by_repo_url, payload.repo_url)
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "INVALID_REQUEST",
                    "message": "Provide either job_id or repo_url.",
                    "detail": "Provide either job_id or repo_url.",
                },
            )
    except RepositoryNotFoundForIndexingError:
        message = "Repository has not been analyzed yet. Run discovery for it first."
        logger.warning("[STRATEGY INDEX FAILED] - Target: %s - Not analyzed yet", target)
        return JSONResponse(
            status_code=404,
            content={"status": "REPOSITORY_NOT_FOUND", "message": message, "detail": message},
        )

    logger.info("[STRATEGY INDEX SUCCESS] - JobID: %s - Repo: %s - Chunks: %d", outcome.job_id, outcome.repository_url, outcome.chunk_count)
    return JSONResponse(
        status_code=200,
        content={
            "status": "INDEXED",
            "repository_url": outcome.repository_url,
            "repository_name": outcome.repository_name,
            "job_id": outcome.job_id,
            "chunk_count": outcome.chunk_count,
        },
    )


@router.get("/repositories", response_model=RepositoriesResponse)
async def repositories() -> JSONResponse:
    # Unlike the chat endpoints there is no StrategyChatError path here, so the
    # disabled case is handled directly: an empty list is the honest answer
    # (nothing is indexed) and keeps the widget rendering instead of 500ing on
    # a missing qdrant-client import.
    if not settings.rag_enabled:
        return JSONResponse(status_code=200, content={"repositories": []})
    repos = await run_in_threadpool(vector_store.list_repositories)
    return JSONResponse(status_code=200, content={"repositories": repos})


@router.get("/ollama/health")
async def ollama_health() -> JSONResponse:
    """Check whether the configured local Ollama server is reachable.

    Returns the server availability status and the configured model name.
    Does NOT expose internal credentials or sensitive configuration.
    """
    client = OllamaClient()
    result = await client.health_check()
    status_code = 200 if result.get("available") else 503
    # Strip the internal URL from the public response for safety
    safe_result = {
        "available": result.get("available", False),
        "model": result.get("model"),
        "model_installed": result.get("model_installed"),
        "installed_models": result.get("installed_models"),
        "message": result.get("message"),
    }
    return JSONResponse(status_code=status_code, content=safe_result)
