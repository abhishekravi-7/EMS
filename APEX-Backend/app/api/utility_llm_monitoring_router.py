"""Token usage monitoring endpoints.

Provides REST APIs for querying LLM token usage statistics, including:
- Summary statistics (total tokens, providers, costs)
- Recent requests
- Provider-specific usage
- Model-specific stats
- Fallback statistics
- Hourly breakdowns
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.llm_token_repository import LLMTokenRepository
from app.infrastructure.persistence.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm-monitoring"])


@router.get("/token-usage/summary")
async def get_token_usage_summary(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get token usage summary statistics for the user.
    
    Returns:
    - Total requests
    - Total input/output/total tokens
    - Provider breakdown (Ollama vs Groq)
    - Success/failure counts
    - Fallback statistics
    - Average tokens per request
    - Total estimated cost
    - Average response duration
    """
    summary = LLMTokenRepository.get_summary(db, user_id=current_user.id, days=days)
    return {
        "period_days": days,
        **summary,
    }


@router.get("/token-usage/recent")
async def get_recent_token_usage(
    limit: int = 50,
    provider: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get recent token usage records for the user.
    
    Args:
        limit: Maximum number of records to return (default: 50)
        provider: Filter by provider ("ollama" or "groq", optional)
    
    Returns:
        List of token usage records with details
    """
    records = LLMTokenRepository.get_recent(
        db,
        limit=limit,
        user_id=current_user.id,
        provider=provider,
    )
    
    return [
        {
            "request_id": r.request_id,
            "timestamp": r.created_at.isoformat(),
            "provider": r.provider,
            "model": r.model,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "total_tokens": r.total_tokens,
            "cached_tokens": r.cached_tokens,
            "duration_ms": r.duration_ms,
            "estimated_cost_usd": r.estimated_cost_usd,
            "status": r.status,
            "error_message": r.error_message,
            "fallback_used": r.fallback_used,
            "fallback_reason": r.fallback_reason,
            "endpoint": r.endpoint,
            "question_preview": r.question_preview,
        }
        for r in records
    ]


@router.get("/token-usage/provider/{provider}")
async def get_provider_usage(
    provider: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get token usage records for a specific provider.
    
    Args:
        provider: Provider name ("ollama" or "groq")
        limit: Maximum number of records to return
    
    Returns:
        List of token usage records for the provider
    """
    # Validate provider
    if provider not in ("ollama", "groq"):
        return []
    
    records = LLMTokenRepository.get_by_provider(
        db,
        provider=provider,
        limit=limit,
    )
    
    # Filter by user
    user_records = [r for r in records if r.user_id == current_user.id]
    
    return [
        {
            "request_id": r.request_id,
            "timestamp": r.created_at.isoformat(),
            "provider": r.provider,
            "model": r.model,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "total_tokens": r.total_tokens,
            "duration_ms": r.duration_ms,
            "estimated_cost_usd": r.estimated_cost_usd,
            "status": r.status,
        }
        for r in user_records
    ]


@router.get("/token-usage/models")
async def get_model_statistics(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get token usage statistics grouped by model.
    
    Returns statistics for each model including:
    - Number of requests
    - Total tokens (input/output)
    - Average duration
    - Total estimated cost
    """
    stats = LLMTokenRepository.get_model_stats(
        db,
        user_id=current_user.id,
        days=days,
    )
    return stats


@router.get("/token-usage/hourly")
async def get_hourly_statistics(
    hours: int = 24,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get token usage statistics grouped by hour.
    
    Returns hourly breakdown showing:
    - Timestamp (hour)
    - Number of requests
    - Total tokens used
    - Total cost
    """
    stats = LLMTokenRepository.get_hourly_stats(
        db,
        user_id=current_user.id,
        hours=hours,
    )
    return stats


@router.get("/token-usage/fallbacks")
async def get_fallback_statistics(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get statistics about fallback events (Ollama -> Groq).
    
    Returns:
    - Total fallback events
    - Breakdown by fallback reason
    - Total tokens via fallback
    - Total cost via fallback
    """
    stats = LLMTokenRepository.get_fallback_stats(
        db,
        user_id=current_user.id,
        days=days,
    )
    return {
        "period_days": days,
        **stats,
    }


@router.get("/health/llm-providers")
async def check_llm_providers() -> dict[str, Any]:
    """Check the health and availability of configured LLM providers.
    
    Returns:
    - Ollama status (available, model installed)
    - Groq status (configured)
    """
    from app.infrastructure.llm.ollama_client import OllamaClient
    from app.infrastructure.llm.groq_client import GroqClient
    
    ollama = OllamaClient()
    groq = GroqClient()
    
    ollama_health = await ollama.health_check()
    
    return {
        "ollama": ollama_health,
        "groq": {
            "configured": groq.is_configured,
        },
        "primary_provider": "ollama" if ollama.is_configured else "groq",
        "fallback_provider": "groq" if ollama.is_configured else None,
    }
