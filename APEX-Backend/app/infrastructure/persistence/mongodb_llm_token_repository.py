import logging
from datetime import datetime, timezone
from typing import Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

async def record_llm_usage(db: AsyncIOMotorDatabase, usage_data: dict[str, Any]):
    """Record LLM token usage in MongoDB."""
    if "created_at" not in usage_data:
        usage_data["created_at"] = datetime.now(timezone.utc)
    await db.llm_token_usage.insert_one(usage_data)

async def get_user_usage_summary(db: AsyncIOMotorDatabase, user_id: str) -> dict[str, Any]:
    """Retrieve aggregate usage stats for a user from MongoDB."""
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": None,
            "total_tokens": {"$sum": "$total_tokens"},
            "total_cost": {"$sum": "$estimated_cost_usd"},
            "request_count": {"$sum": 1}
        }}
    ]
    cursor = db.llm_token_usage.aggregate(pipeline)
    result = await cursor.to_list(length=1)
    return result[0] if result else {"total_tokens": 0, "total_cost": 0.0, "request_count": 0}
