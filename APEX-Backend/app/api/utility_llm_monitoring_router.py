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

from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.llm_token_repository import LLMTokenRepository
from app.infrastructure.persistence.models import LLMTokenUsage, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm-monitoring"])

_DASHBOARD_MAX_LIMIT = 1000
_DASHBOARD_HTML_PATH = Path(__file__).resolve().parents[2] / "token_tracing" / "dashboard.html"


@router.get("/token-usage/summary")
async def get_token_usage_summary(
    request: Request,
    days: int = 7,
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
    current_user = get_current_user(request, db)
    summary = LLMTokenRepository.get_summary(db, user_id=current_user.id, days=days)
    return {
        "period_days": days,
        **summary,
    }


@router.get("/token-usage/dashboard")
async def get_token_usage_dashboard() -> HTMLResponse:
    """Serve the token-usage dashboard page from the backend origin."""
    html = _load_dashboard_html()
    injection = '<script>window.TOKEN_TRACING_API = "/api/llm/token-usage/dashboard";</script>\n'
    marker = '<script>\n"use strict";\n'
    if marker in html:
        html = html.replace(marker, injection + marker, 1)
    else:
        html = html.replace("</head>", f"{injection}</head>", 1)
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})


@router.get("/token-usage/dashboard/summary")
async def get_token_usage_dashboard_summary(
    request: Request,
    days: int = 7,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return dashboard-shaped summary data for the authenticated user."""
    current_user = get_current_user(request, db)
    records = _fetch_dashboard_records(db, user_id=current_user.id, days=days)
    return _build_dashboard_summary(records)


@router.get("/token-usage/dashboard/records")
async def get_token_usage_dashboard_records(
    request: Request,
    days: int = 7,
    limit: int = 100,
    model: str | None = None,
    endpoint: str | None = None,
    provider: str | None = None,
    error: str = "",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return dashboard-shaped recent records for the authenticated user."""
    error_only = error.lower() in {"1", "true", "yes"}
    current_user = get_current_user(request, db)
    records = _fetch_dashboard_records(
        db,
        user_id=current_user.id,
        days=days,
        model=model,
        endpoint=endpoint,
        provider=provider,
        error_only=error_only,
        limit=limit,
    )
    return {
        "count": len(records),
        "records": records,
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


def _load_dashboard_html() -> str:
    try:
        return _DASHBOARD_HTML_PATH.read_text(encoding="utf-8")
    except OSError:
        return (
            "<!doctype html><html><body><h1>dashboard.html not found</h1>"
            "<p>The dashboard page could not be loaded from the backend package.</p>"
            "</body></html>"
        )


def _fetch_dashboard_records(
    db: Session,
    *,
    user_id: int,
    days: int,
    model: str | None = None,
    endpoint: str | None = None,
    provider: str | None = None,
    error_only: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(days, 1))
    capped_limit = max(0, min(int(limit), _DASHBOARD_MAX_LIMIT))

    query = db.query(LLMTokenUsage).filter(
        LLMTokenUsage.user_id == user_id,
        LLMTokenUsage.created_at >= cutoff,
    )
    if model:
        query = query.filter(LLMTokenUsage.model == model)
    if endpoint:
        query = query.filter(LLMTokenUsage.endpoint == endpoint)
    if provider:
        query = query.filter(LLMTokenUsage.provider == provider)
    if error_only:
        query = query.filter(LLMTokenUsage.error_message.isnot(None))

    rows = query.order_by(desc(LLMTokenUsage.created_at)).limit(capped_limit).all()
    return [
        {
            "request_id": row.request_id,
            "timestamp": row.created_at.isoformat(),
            "provider": row.provider,
            "model": row.model,
            "endpoint": row.endpoint,
            "input_tokens": row.input_tokens or 0,
            "output_tokens": row.output_tokens or 0,
            "total_tokens": row.total_tokens or 0,
            "cached_tokens": row.cached_tokens or 0,
            "estimated_cost_usd": row.estimated_cost_usd or 0.0,
            "duration_ms": row.duration_ms,
            "error": row.error_message,
            "is_retry": row.is_retry,
            "fallback_used": row.fallback_used,
            "fallback_reason": row.fallback_reason,
            "question_preview": row.question_preview,
            "status": row.status,
            "prompt_cache_hit": bool(row.cached_tokens and row.cached_tokens > 0),
        }
        for row in rows
    ]


def _build_dashboard_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    total_input = total_output = total_cached = 0
    total_cost = 0.0
    error_calls = 0
    cached_calls = 0
    durations: list[float] = []
    last_ts: str | None = None
    buckets: dict[str, dict[str, dict[str, Any]]] = {
        "model": {},
        "endpoint": {},
        "provider": {},
    }

    for rec in records:
        total_input += rec.get("input_tokens") or 0
        total_output += rec.get("output_tokens") or 0
        total_cached += rec.get("cached_tokens") or 0
        total_cost += rec.get("estimated_cost_usd") or 0.0
        if rec.get("error"):
            error_calls += 1
        if rec.get("prompt_cache_hit") or (rec.get("cached_tokens") or 0) > 0:
            cached_calls += 1
        duration = rec.get("duration_ms")
        if duration is not None:
            durations.append(float(duration))
        ts = rec.get("timestamp")
        if ts:
            last_ts = max(last_ts or "", ts)
        for key, bucket in buckets.items():
            row = bucket.setdefault(
                rec.get(key) or "(unknown)",
                {"calls": 0, "total_tokens": 0, "cost_usd": 0.0, "errors": 0},
            )
            row["calls"] += 1
            row["total_tokens"] += rec.get("total_tokens") or 0
            row["cost_usd"] += rec.get("estimated_cost_usd") or 0.0
            if rec.get("error"):
                row["errors"] += 1

    def _sorted(bucket: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            ({"name": name, **row} for name, row in bucket.items()),
            key=lambda r: (r["cost_usd"], r["calls"]),
            reverse=True,
        )

    durations.sort()
    p95 = None
    if durations:
        p95 = durations[max(0, int((len(durations) * 0.95) - 1))]

    n = len(records)
    return {
        "total_calls": n,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "total_cached_tokens": total_cached,
        "total_cost_usd": round(total_cost, 6),
        "error_calls": error_calls,
        "error_rate": round(error_calls / n, 4) if n else 0.0,
        "cache_hit_rate": round(cached_calls / n, 4) if n else 0.0,
        "avg_duration_ms": round(sum(durations) / len(durations), 1) if durations else None,
        "p95_duration_ms": round(p95, 1) if p95 is not None else None,
        "last_record_at": last_ts,
        "per_model": _sorted(buckets["model"]),
        "per_endpoint": _sorted(buckets["endpoint"]),
        "per_provider": _sorted(buckets["provider"]),
    }
