import logging
from datetime import datetime, timezone
from typing import Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

async def save_existing_test_state(db: AsyncIOMotorDatabase, job_id: str, status: str, state: dict[str, Any]):
    """Persist existing test execution state to MongoDB."""
    await db.existing_test_states.update_one(
        {"job_id": job_id},
        {
            "$set": {
                "status": status,
                "state_json": state,
                "updated_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )

async def load_existing_test_state(db: AsyncIOMotorDatabase, job_id: str) -> Optional[dict[str, Any]]:
    """Load existing test state for a job from MongoDB."""
    doc = await db.existing_test_states.find_one({"job_id": job_id})
    return doc if doc else None

async def save_existing_test_report(db: AsyncIOMotorDatabase, job_id: str, report: dict[str, Any]):
    """Persist existing test report JSON to MongoDB."""
    await db.existing_test_states.update_one(
        {"job_id": job_id},
        {"$set": {"report_json": report, "updated_at": datetime.now(timezone.utc)}}
    )
