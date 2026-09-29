"""Repository for LLM token usage queries and statistics.

Provides methods to fetch token usage records, compute summary statistics,
and retrieve usage breakdowns by provider, model, and time period.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models import LLMTokenUsage


class LLMTokenRepository:
    """Queries and statistics for LLM token usage."""

    @staticmethod
    def create(db: Session, token_usage: LLMTokenUsage) -> LLMTokenUsage:
        """Create a new token usage record."""
        db.add(token_usage)
        db.commit()
        db.refresh(token_usage)
        return token_usage

    @staticmethod
    def get_by_request_id(db: Session, request_id: str) -> LLMTokenUsage | None:
        """Fetch a token usage record by request ID."""
        return db.query(LLMTokenUsage).filter(
            LLMTokenUsage.request_id == request_id
        ).first()

    @staticmethod
    def get_recent(
        db: Session,
        limit: int = 50,
        user_id: int | None = None,
        provider: str | None = None,
    ) -> list[LLMTokenUsage]:
        """Fetch recent token usage records.

        Args:
            db: Database session
            limit: Maximum number of records to return
            user_id: Filter by user (optional)
            provider: Filter by provider ("ollama" or "groq")
        """
        query = db.query(LLMTokenUsage).order_by(desc(LLMTokenUsage.created_at))

        if user_id is not None:
            query = query.filter(LLMTokenUsage.user_id == user_id)
        if provider is not None:
            query = query.filter(LLMTokenUsage.provider == provider)

        return query.limit(limit).all()

    @staticmethod
    def get_summary(
        db: Session,
        user_id: int | None = None,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get summary statistics for token usage.

        Returns statistics including totals for:
        - Total requests
        - Total input/output/total tokens
        - Ollama vs Groq breakdown
        - Successful vs failed requests
        - Fallback count
        - Average tokens per request
        - Total estimated cost
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = db.query(LLMTokenUsage).filter(
            LLMTokenUsage.created_at >= cutoff
        )

        if user_id is not None:
            query = query.filter(LLMTokenUsage.user_id == user_id)

        records = query.all()

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
                "total_estimated_cost_usd": 0,
                "period_days": days,
            }

        # Calculate statistics
        total_input = sum(r.input_tokens or 0 for r in records)
        total_output = sum(r.output_tokens or 0 for r in records)
        total_tokens = sum(r.total_tokens or 0 for r in records)

        ollama_count = sum(1 for r in records if r.provider == "ollama")
        groq_count = sum(1 for r in records if r.provider == "groq")
        successful = sum(1 for r in records if r.status == "success")
        failed = sum(1 for r in records if r.status == "failure")
        fallback_count = sum(1 for r in records if r.fallback_used)

        avg_tokens = total_tokens / len(records) if records else 0
        avg_duration = sum(r.duration_ms or 0 for r in records) / len(records) if records else 0
        total_cost = sum(r.estimated_cost_usd or 0 for r in records)

        return {
            "total_requests": len(records),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_tokens,
            "ollama_requests": ollama_count,
            "groq_requests": groq_count,
            "successful_requests": successful,
            "failed_requests": failed,
            "fallback_count": fallback_count,
            "average_tokens_per_request": round(avg_tokens, 2),
            "average_duration_ms": round(avg_duration, 2),
            "total_estimated_cost_usd": round(total_cost, 6),
            "period_days": days,
        }

    @staticmethod
    def get_by_provider(
        db: Session,
        provider: str,
        limit: int = 50,
    ) -> list[LLMTokenUsage]:
        """Fetch token usage records for a specific provider."""
        return db.query(LLMTokenUsage).filter(
            LLMTokenUsage.provider == provider
        ).order_by(desc(LLMTokenUsage.created_at)).limit(limit).all()

    @staticmethod
    def get_model_stats(
        db: Session,
        user_id: int | None = None,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Get token usage statistics grouped by model."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = db.query(
            LLMTokenUsage.model,
            func.count(LLMTokenUsage.id).label("request_count"),
            func.sum(LLMTokenUsage.input_tokens).label("total_input_tokens"),
            func.sum(LLMTokenUsage.output_tokens).label("total_output_tokens"),
            func.sum(LLMTokenUsage.total_tokens).label("total_tokens"),
            func.avg(LLMTokenUsage.duration_ms).label("avg_duration_ms"),
            func.sum(LLMTokenUsage.estimated_cost_usd).label("total_cost_usd"),
        ).filter(LLMTokenUsage.created_at >= cutoff)

        if user_id is not None:
            query = query.filter(LLMTokenUsage.user_id == user_id)

        query = query.group_by(LLMTokenUsage.model).order_by(
            desc(func.sum(LLMTokenUsage.total_tokens))
        )

        results = query.all()
        return [
            {
                "model": r[0],
                "request_count": r[1],
                "total_input_tokens": r[2] or 0,
                "total_output_tokens": r[3] or 0,
                "total_tokens": r[4] or 0,
                "avg_duration_ms": round(r[5] or 0, 2),
                "total_cost_usd": round(r[6] or 0, 6),
            }
            for r in results
        ]

    @staticmethod
    def get_hourly_stats(
        db: Session,
        user_id: int | None = None,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Get token usage statistics grouped by hour."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        # This is a simplified version — a production version would use
        # database-specific date/time functions for better performance
        query = db.query(LLMTokenUsage).filter(
            LLMTokenUsage.created_at >= cutoff
        )

        if user_id is not None:
            query = query.filter(LLMTokenUsage.user_id == user_id)

        records = query.order_by(LLMTokenUsage.created_at).all()

        # Group by hour
        hourly_stats: dict[str, dict[str, Any]] = {}
        for record in records:
            # Truncate to hour
            hour_key = record.created_at.replace(minute=0, second=0, microsecond=0).isoformat()

            if hour_key not in hourly_stats:
                hourly_stats[hour_key] = {
                    "timestamp": hour_key,
                    "request_count": 0,
                    "total_tokens": 0,
                    "total_cost_usd": 0,
                }

            hourly_stats[hour_key]["request_count"] += 1
            hourly_stats[hour_key]["total_tokens"] += record.total_tokens or 0
            hourly_stats[hour_key]["total_cost_usd"] += record.estimated_cost_usd or 0

        return sorted(hourly_stats.values(), key=lambda x: x["timestamp"])

    @staticmethod
    def get_fallback_stats(
        db: Session,
        user_id: int | None = None,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get statistics about fallback events (Ollama -> Groq)."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = db.query(LLMTokenUsage).filter(
            and_(
                LLMTokenUsage.created_at >= cutoff,
                LLMTokenUsage.fallback_used == True,  # noqa: E712
            )
        )

        if user_id is not None:
            query = query.filter(LLMTokenUsage.user_id == user_id)

        fallback_records = query.all()

        # Group fallbacks by reason
        fallback_reasons: dict[str, int] = {}
        for record in fallback_records:
            reason = record.fallback_reason or "unknown"
            fallback_reasons[reason] = fallback_reasons.get(reason, 0) + 1

        return {
            "total_fallback_events": len(fallback_records),
            "fallback_reasons": fallback_reasons,
            "total_tokens_via_fallback": sum(r.total_tokens or 0 for r in fallback_records),
            "total_cost_via_fallback": sum(r.estimated_cost_usd or 0 for r in fallback_records),
        }
