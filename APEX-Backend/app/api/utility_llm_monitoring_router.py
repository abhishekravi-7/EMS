"""Token usage monitoring endpoints.

Provides REST APIs for querying LLM token usage statistics from MongoDB:
- Summary statistics (total tokens, providers, costs)
- Recent requests
- Provider-specific usage
- Model-specific stats
- Fallback statistics
- Hourly breakdowns
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.api.deps import get_current_user
from app.infrastructure.persistence.mongodb import get_mongodb
from app.infrastructure.persistence import mongodb_llm_token_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm-monitoring"])

_DASHBOARD_HTML_PATH = Path(__file__).resolve().parents[2] / "token_tracing" / "dashboard.html"


@router.get("/token-usage/summary")
async def get_token_usage_summary(
    request: Request,
    days: int = 7,
) -> dict[str, Any]:
    """Get token usage summary statistics for the user."""
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return {
            "total_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "ollama_requests": 0,
            "groq_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "fallback_count": 0,
            "average_tokens_per_request": 0,
            "average_duration_ms": 0,
            "total_estimated_cost_usd": 0,
            "period_days": days,
            "database_disabled": True,
        }
    
    current_user = await get_current_user(request)
    summary = await mongodb_llm_token_repository.get_summary_stats(mongo_db, user_id=str(current_user.id), days=days)
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
) -> dict[str, Any]:
    """Return dashboard-shaped summary data for the authenticated user."""
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return _build_dashboard_summary([])

    current_user = await get_current_user(request)
    records = await mongodb_llm_token_repository.get_dashboard_records(
        mongo_db,
        user_id=str(current_user.id),
        days=days,
        limit=1000,
    )
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
) -> dict[str, Any]:
    """Return dashboard-shaped recent records for the authenticated user."""
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return {"count": 0, "records": []}

    error_only = error.lower() in {"1", "true", "yes"}
    current_user = await get_current_user(request)
    records = await mongodb_llm_token_repository.get_dashboard_records(
        mongo_db,
        user_id=str(current_user.id),
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
    request: Request,
    limit: int = 50,
    provider: str | None = None,
) -> list[dict[str, Any]]:
    """Get recent token usage records for the user."""
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return []

    current_user = await get_current_user(request)
    records = await mongodb_llm_token_repository.get_recent_usage(
        mongo_db,
        limit=limit,
        user_id=str(current_user.id),
        provider=provider,
    )
    return records


@router.get("/token-usage/provider/{provider}")
async def get_provider_usage(
    request: Request,
    provider: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get token usage records for a specific provider."""
    mongo_db = await get_mongodb()
    if mongo_db is None or provider not in ("ollama", "groq"):
        return []

    current_user = await get_current_user(request)
    records = await mongodb_llm_token_repository.get_recent_usage(
        mongo_db,
        limit=limit,
        user_id=str(current_user.id),
        provider=provider,
    )
    return records


@router.get("/token-usage/models")
async def get_model_statistics(
    request: Request,
    days: int = 7,
) -> list[dict[str, Any]]:
    """Get token usage statistics grouped by model."""
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return []

    current_user = await get_current_user(request)
    return await mongodb_llm_token_repository.get_model_stats(
        mongo_db,
        user_id=str(current_user.id),
        days=days,
    )


@router.get("/token-usage/hourly")
async def get_hourly_statistics(
    request: Request,
    hours: int = 24,
) -> list[dict[str, Any]]:
    """Get token usage statistics grouped by hour."""
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return []

    current_user = await get_current_user(request)
    return await mongodb_llm_token_repository.get_hourly_stats(
        mongo_db,
        user_id=str(current_user.id),
        hours=hours,
    )


@router.get("/token-usage/fallbacks")
async def get_fallback_statistics(
    request: Request,
    days: int = 7,
) -> dict[str, Any]:
    """Get statistics about fallback events (Ollama -> Groq)."""
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return {
            "total_fallback_events": 0,
            "fallback_reasons": {},
            "total_tokens_via_fallback": 0,
            "total_cost_via_fallback": 0,
        }

    current_user = await get_current_user(request)
    stats = await mongodb_llm_token_repository.get_fallback_stats(
        mongo_db,
        user_id=str(current_user.id),
        days=days,
    )
    return {
        "period_days": days,
        **stats,
    }


@router.get("/health/llm-providers")
async def check_llm_providers() -> dict[str, Any]:
    """Check the health and availability of configured LLM providers."""
    from app.infrastructure.llm.groq_client import GroqClient
    from app.infrastructure.llm.ollama_client import OllamaClient
    
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
