import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

async def get_job_owner_user_id(db: AsyncIOMotorDatabase, job_id: str) -> Optional[str]:
    """Retrieve the owner user ID for a given job ID from MongoDB."""
    doc = await db.migration_job_owners.find_one({"job_id": job_id})
    return doc["user_id"] if doc else None

async def record_job_owner(db: AsyncIOMotorDatabase, job_id: str, user_id: str):
    """Record the owner of a migration job in MongoDB."""
    await db.migration_job_owners.update_one(
        {"job_id": job_id},
        {"$set": {"user_id": user_id}},
        upsert=True
    )
