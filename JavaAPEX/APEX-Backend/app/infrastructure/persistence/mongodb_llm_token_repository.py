import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


async def record_llm_usage(db: AsyncIOMotorDatabase, usage_data: dict[str, Any]):
    """Record LLM token usage in MongoDB."""
    if db is None:
        return
    data = dict(usage_data)
    if "created_at" not in data:
        data["created_at"] = datetime.now(timezone.utc)
    elif isinstance(data["created_at"], str):
        try:
            data["created_at"] = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        except Exception:
            data["created_at"] = datetime.now(timezone.utc)
    await db.llm_token_usage.insert_one(data)


async def get_recent_usage(
    db: AsyncIOMotorDatabase,
    limit: int = 50,
    user_id: Optional[str] = None,
    provider: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Fetch recent token usage records from MongoDB."""
    if db is None:
        return []
    query: dict[str, Any] = {}
    if user_id:
        query["user_id"] = str(user_id)
    if provider:
        query["provider"] = provider

    cursor = db.llm_token_usage.find(query).sort("created_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs


async def get_dashboard_records(
    db: AsyncIOMotorDatabase,
    *,
    user_id: Optional[str] = None,
    days: int = 7,
    model: Optional[str] = None,
    endpoint: Optional[str] = None,
    provider: Optional[str] = None,
    error_only: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Fetch dashboard records from MongoDB."""
    if db is None:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(days, 1))
    query: dict[str, Any] = {"created_at": {"$gte": cutoff}}
    if user_id:
        query["user_id"] = str(user_id)
    if model:
        query["model"] = model
    if endpoint:
        query["endpoint"] = endpoint
    if provider:
        query["provider"] = provider
    if error_only:
        query["error_message"] = {"$ne": None}

    cursor = db.llm_token_usage.find(query).sort("created_at", -1).limit(limit)
    records = await cursor.to_list(length=limit)
    result = []
    for row in records:
        ts = row.get("created_at")
        if isinstance(ts, datetime):
            iso_ts = ts.isoformat()
        else:
            iso_ts = str(ts) if ts else datetime.now(timezone.utc).isoformat()

        rec = {
            "request_id": row.get("request_id", "(unknown)"),
            "timestamp": iso_ts,
            "provider": row.get("provider", "(unknown)"),
            "model": row.get("model", "(unknown)"),
            "endpoint": row.get("endpoint"),
            "input_tokens": row.get("input_tokens", 0) or 0,
            "output_tokens": row.get("output_tokens", 0) or 0,
            "total_tokens": row.get("total_tokens", 0) or 0,
            "cached_tokens": row.get("cached_tokens", 0) or 0,
            "estimated_cost_usd": row.get("estimated_cost_usd", 0.0) or 0.0,
            "duration_ms": row.get("duration_ms"),
            "error": row.get("error_message"),
            "is_retry": row.get("is_retry", False),
            "fallback_used": row.get("fallback_used", False),
            "fallback_reason": row.get("fallback_reason"),
            "question_preview": row.get("question_preview"),
            "status": row.get("status", "success"),
        }
        cached = rec.get("cached_tokens") or 0
        rec["prompt_cache_hit"] = bool(cached > 0)
        result.append(rec)
    return result


async def get_summary_stats(
    db: AsyncIOMotorDatabase,
    user_id: Optional[str] = None,
    days: int = 7,
) -> dict[str, Any]:
    """Get summary statistics for token usage from MongoDB."""
    if db is None:
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
            "total_estimated_cost_usd": 0.0,
            "period_days": days,
        }

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query: dict[str, Any] = {"created_at": {"$gte": cutoff}}
    if user_id:
        query["user_id"] = str(user_id)

    cursor = db.llm_token_usage.find(query)
    records = await cursor.to_list(length=5000)

    if not records:
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
            "total_estimated_cost_usd": 0.0,
            "period_days": days,
        }

    total_requests = len(records)
    total_input = sum(r.get("input_tokens", 0) for r in records)
    total_output = sum(r.get("output_tokens", 0) for r in records)
    total_tokens = sum(r.get("total_tokens", 0) for r in records)
    total_cost = sum(r.get("estimated_cost_usd", 0.0) for r in records)
    total_duration = sum(r.get("duration_ms", 0.0) for r in records)

    ollama_count = sum(1 for r in records if r.get("provider") == "ollama")
    groq_count = sum(1 for r in records if r.get("provider") == "groq")
    success_count = sum(1 for r in records if r.get("status") == "success")
    failed_count = sum(1 for r in records if r.get("status") in ("error", "failure"))
    fallback_count = sum(1 for r in records if r.get("fallback_used"))

    return {
        "total_requests": total_requests,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "ollama_requests": ollama_count,
        "groq_requests": groq_count,
        "successful_requests": success_count,
        "failed_requests": failed_count,
        "fallback_count": fallback_count,
        "average_tokens_per_request": round(total_tokens / total_requests, 1) if total_requests else 0,
        "average_duration_ms": round(total_duration / total_requests, 1) if total_requests else 0,
        "total_estimated_cost_usd": round(total_cost, 6),
        "period_days": days,
    }


async def get_model_stats(
    db: AsyncIOMotorDatabase,
    user_id: Optional[str] = None,
    days: int = 7,
) -> list[dict[str, Any]]:
    """Get stats grouped by model."""
    if db is None:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query: dict[str, Any] = {"created_at": {"$gte": cutoff}}
    if user_id:
        query["user_id"] = str(user_id)

    records = await db.llm_token_usage.find(query).to_list(length=5000)
    by_model: dict[str, dict[str, Any]] = {}
    for r in records:
        m = r.get("model") or "unknown"
        row = by_model.setdefault(m, {"model": m, "total_requests": 0, "total_tokens": 0, "total_cost_usd": 0.0})
        row["total_requests"] += 1
        row["total_tokens"] += r.get("total_tokens", 0) or 0
        row["total_cost_usd"] += r.get("estimated_cost_usd", 0.0) or 0.0
    return list(by_model.values())


async def get_hourly_stats(
    db: AsyncIOMotorDatabase,
    user_id: Optional[str] = None,
    hours: int = 24,
) -> list[dict[str, Any]]:
    """Get stats grouped by hour."""
    if db is None:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    query: dict[str, Any] = {"created_at": {"$gte": cutoff}}
    if user_id:
        query["user_id"] = str(user_id)

    records = await db.llm_token_usage.find(query).to_list(length=5000)
    by_hour: dict[str, dict[str, Any]] = {}
    for r in records:
        ts = r.get("created_at")
        hour_str = ts.strftime("%Y-%m-%d %H:00") if isinstance(ts, datetime) else "unknown"
        row = by_hour.setdefault(hour_str, {"hour": hour_str, "requests": 0, "tokens": 0, "cost_usd": 0.0})
        row["requests"] += 1
        row["tokens"] += r.get("total_tokens", 0) or 0
        row["cost_usd"] += r.get("estimated_cost_usd", 0.0) or 0.0
    return list(by_hour.values())


async def get_fallback_stats(
    db: AsyncIOMotorDatabase,
    user_id: Optional[str] = None,
    days: int = 7,
) -> dict[str, Any]:
    """Get fallback statistics."""
    if db is None:
        return {"total_fallback_events": 0, "fallback_reasons": {}, "total_tokens_via_fallback": 0, "total_cost_via_fallback": 0}
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query: dict[str, Any] = {"created_at": {"$gte": cutoff}, "fallback_used": True}
    if user_id:
        query["user_id"] = str(user_id)

    records = await db.llm_token_usage.find(query).to_list(length=5000)
    reasons: dict[str, int] = {}
    tokens = 0
    cost = 0.0
    for r in records:
        reason = r.get("fallback_reason") or "unknown"
        reasons[reason] = reasons.get(reason, 0) + 1
        tokens += r.get("total_tokens", 0) or 0
        cost += r.get("estimated_cost_usd", 0.0) or 0.0

    return {
        "total_fallback_events": len(records),
        "fallback_reasons": reasons,
        "total_tokens_via_fallback": tokens,
        "total_cost_via_fallback": round(cost, 6),
    }
