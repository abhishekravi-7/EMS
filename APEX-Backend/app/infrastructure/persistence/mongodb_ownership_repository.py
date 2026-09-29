import logging
from datetime import datetime, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

async def get_job_owner_user_id(db: AsyncIOMotorDatabase, job_id: str) -> Optional[str]:
    """Retrieve the owner user ID for a given job ID from MongoDB."""
    if db is None:
        return None
    doc = await db.migration_job_owners.find_one({"job_id": job_id})
    return doc["user_id"] if doc else None

async def record_job_owner(
    db: AsyncIOMotorDatabase, 
    job_id: str, 
    user_id: str, 
    owner_name: Optional[str] = None, 
    owner_email: Optional[str] = None,
    repository_name: Optional[str] = None,
):
    """Record the owner of a migration job in MongoDB."""
    if db is None:
        return
    update_doc = {"$set": {"user_id": str(user_id)}}
    
    set_on_insert = {
        "last_updated": datetime.now(timezone.utc)
    }
    if owner_name is not None:
        set_on_insert["owner_name"] = owner_name
    if owner_email is not None:
        set_on_insert["owner_email"] = owner_email
        
    if repository_name is not None:
        update_doc["$set"]["repository_name"] = repository_name
    else:
        set_on_insert["repository_name"] = None
        
    if set_on_insert:
        update_doc["$setOnInsert"] = set_on_insert

    await db.migration_job_owners.update_one(
        {"job_id": job_id},
        update_doc,
        upsert=True
    )

def sync_update_job_last_updated(job_id: str) -> None:
    """Synchronously update the last_updated timestamp for a migration job in MongoDB."""
    from app.infrastructure.persistence.mongodb import mongodb_manager
    try:
        db = mongodb_manager.get_sync_db()
        if db is not None:
            db.migration_job_owners.update_one(
                {"job_id": job_id},
                {"$set": {"last_updated": datetime.now(timezone.utc)}}
            )
    except Exception as exc:
        logger.debug("Non-fatal: could not update job last_updated in MongoDB for %s: %s", job_id, exc)
