import asyncio
import argparse
import logging
import sys
import os
from datetime import datetime, timezone

# Set working directory to project root if running from scripts
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def run_backfill(dry_run: bool = False):
    from app.infrastructure.persistence.mongodb import get_mongodb, mongodb_manager
    from motor.motor_asyncio import AsyncIOMotorDatabase
    from app.infrastructure.persistence.job_repository import JobRepository
    
    await mongodb_manager.connect()
    db: AsyncIOMotorDatabase = await get_mongodb()
    if db is None:
        logger.error("Could not connect to MongoDB.")
        sys.exit(1)
        
    job_repo = JobRepository()
    
    cursor = db.migration_job_owners.find({
        "$or": [
            {"repository_name": {"$exists": False}},
            {"last_updated": {"$exists": False}}
        ]
    })
    
    total_found = 0
    updated_count = 0
    
    async for doc in cursor:
        total_found += 1
        job_id = doc.get("job_id")
        
        # 1. Determine repository_name
        repository_name = None
        connect_report = job_repo.read_connect_report(job_id)
        if connect_report:
            owner = connect_report.get("owner")
            repo_name = connect_report.get("repoName")
            if owner and owner != "local":
                repository_name = f"{owner}/{repo_name}"
            elif repo_name:
                repository_name = repo_name
        
        # 2. Determine last_updated
        timestamps = []
        if connect_report and connect_report.get("createdAt"):
            try:
                # Handle isoformat like "2024-01-01T12:00:00+00:00"
                dt = datetime.fromisoformat(connect_report["createdAt"].replace('Z', '+00:00'))
                timestamps.append(dt)
            except Exception:
                pass
                
        # Check DB reports
        discovery_db = await db.discovery_reports.find_one({"job_id": job_id})
        if discovery_db and discovery_db.get("updated_at"):
            timestamps.append(discovery_db["updated_at"])
            
        migration_db = await db.migration_reports.find_one({"job_id": job_id})
        if migration_db and migration_db.get("updated_at"):
            timestamps.append(migration_db["updated_at"])
            
        # Add creation time from the object ID as fallback
        timestamps.append(doc["_id"].generation_time)
        
        # Make all timestamps offset-aware (assuming DB times are UTC)
        aware_timestamps = []
        for ts in timestamps:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            aware_timestamps.append(ts)
            
        last_updated = max(aware_timestamps)
        
        if dry_run:
            logger.info(f"[DRY-RUN] Would update job_id={job_id} with repository_name='{repository_name}' and last_updated='{last_updated}'")
            updated_count += 1
        else:
            update_data = {"last_updated": last_updated}
            if repository_name:
                update_data["repository_name"] = repository_name
                
            result = await db.migration_job_owners.update_one(
                {"job_id": job_id},
                {"$set": update_data}
            )
            if result.modified_count > 0:
                logger.info(f"Updated job_id={job_id} with repository_name='{repository_name}' and last_updated='{last_updated}'")
                updated_count += 1
                
    logger.info("=== Backfill Summary ===")
    logger.info(f"Total missing records found: {total_found}")
    logger.info(f"Records updated (or would be updated): {updated_count}")
    
    if dry_run:
        logger.info("This was a DRY-RUN. No changes were applied to the database.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill repository_name and last_updated on migration_job_owners.")
    parser.add_argument("--dry-run", action="store_true", help="Report proposed changes without applying them.")
    args = parser.parse_args()
    
    asyncio.run(run_backfill(dry_run=args.dry_run))
