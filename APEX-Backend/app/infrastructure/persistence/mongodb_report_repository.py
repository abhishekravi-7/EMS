import logging
from datetime import datetime, timezone
from typing import Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.infrastructure.persistence.mongodb import mongodb_manager

logger = logging.getLogger(__name__)

async def save_report_to_db(db: Optional[AsyncIOMotorDatabase], job_id: str, report: dict[str, Any]):
    """Persist a migration report JSON to MongoDB asynchronously."""
    if db is None:
        db = mongodb_manager.db
    if db is None:
        save_report_to_db_sync(job_id, report)
        return
    await db.migration_reports.update_one(
        {"job_id": job_id},
        {
            "$set": {
                "status": report.get("status", "QUEUED"),
                "progress_percent": report.get("progressPercent", 0),
                "current_step": report.get("currentStep"),
                "report_json": report,
                "updated_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )

async def load_report_from_db(db: Optional[AsyncIOMotorDatabase], job_id: str) -> Optional[dict[str, Any]]:
    """Load the latest migration report for a job from MongoDB asynchronously."""
    if db is None:
        db = mongodb_manager.db
    if db is None:
        return load_report_from_db_sync(job_id)
    doc = await db.migration_reports.find_one({"job_id": job_id})
    return doc["report_json"] if doc else None

def save_report_to_db_sync(job_id: str, report: dict[str, Any]) -> None:
    """Synchronously persist a migration report JSON to MongoDB."""
    try:
        sync_db = mongodb_manager.get_sync_db()
        if sync_db is None:
            return
        sync_db.migration_reports.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": report.get("status", "QUEUED"),
                    "progress_percent": report.get("progressPercent", 0),
                    "current_step": report.get("currentStep"),
                    "report_json": report,
                    "updated_at": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )
    except Exception as exc:
        logger.debug("Non-fatal: failed to persist report to MongoDB synchronously: %s", exc)

def load_report_from_db_sync(job_id: str) -> Optional[dict[str, Any]]:
    """Synchronously load the latest migration report for a job from MongoDB."""
    try:
        sync_db = mongodb_manager.get_sync_db()
        if sync_db is None:
            return None
        doc = sync_db.migration_reports.find_one({"job_id": job_id})
        return doc["report_json"] if doc else None
    except Exception as exc:
        logger.debug("Non-fatal: failed to load report from MongoDB synchronously: %s", exc)
        return None

async def save_discovery_report(db: AsyncIOMotorDatabase, job_id: str, report: dict[str, Any]):
    """Persist a discovery report JSON to MongoDB."""
    if db is None:
        db = mongodb_manager.db
    if db is None:
        return
    await db.discovery_reports.update_one(
        {"job_id": job_id},
        {
            "$set": {
                "report_json": report,
                "updated_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )

async def load_discovery_report(db: AsyncIOMotorDatabase, job_id: str) -> Optional[dict[str, Any]]:
    """Load the discovery report for a job from MongoDB."""
    if db is None:
        db = mongodb_manager.db
    if db is None:
        return None
    doc = await db.discovery_reports.find_one({"job_id": job_id})
    return doc["report_json"] if doc else None
