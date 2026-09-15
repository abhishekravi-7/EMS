import logging
from datetime import datetime, timezone
from typing import Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

async def save_report_to_db(db: AsyncIOMotorDatabase, job_id: str, report: dict[str, Any]):
    """Persist a migration report JSON to MongoDB."""
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

async def load_report_from_db(db: AsyncIOMotorDatabase, job_id: str) -> Optional[dict[str, Any]]:
    """Load the latest migration report for a job from MongoDB."""
    doc = await db.migration_reports.find_one({"job_id": job_id})
    return doc["report_json"] if doc else None

async def save_discovery_report(db: AsyncIOMotorDatabase, job_id: str, report: dict[str, Any]):
    """Persist a discovery report JSON to MongoDB."""
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
    doc = await db.discovery_reports.find_one({"job_id": job_id})
    return doc["report_json"] if doc else None
