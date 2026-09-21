import asyncio
import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def run_backfill(dry_run: bool = False, target_job_id: str = None):
    from app.infrastructure.persistence.mongodb import get_mongodb, mongodb_manager
    from app.infrastructure.persistence.job_repository import JobRepository
    from motor.motor_asyncio import AsyncIOMotorDatabase
    
    await mongodb_manager.connect()
    db: AsyncIOMotorDatabase = await get_mongodb()
    if db is None:
        logger.error("Could not connect to MongoDB.")
        sys.exit(1)
        
    query = {
        "$or": [
            {"repository_name": {"$exists": False}},
            {"repository_name": None}
        ]
    }
    if target_job_id:
        query["job_id"] = target_job_id
        
    cursor = db.migration_job_owners.find(query)
    
    job_repo = JobRepository()
    
    total_found = 0
    updated_count = 0
    unresolved_count = 0
    
    async for doc in cursor:
        total_found += 1
        job_id = doc.get("job_id")
        
        # Read repository metadata from the authoritative stored job data
        connect_report = job_repo.read_connect_report(job_id)
        repository_name = None
        
        if connect_report:
            owner = connect_report.get("owner")
            repo_name = connect_report.get("repoName")
            if owner and owner != "local":
                repository_name = f"{owner}/{repo_name}"
            elif repo_name:
                repository_name = repo_name
                
        if not repository_name:
            # Maybe check discovery report if connect report doesn't have it
            discovery_db = await db.discovery_reports.find_one({"job_id": job_id})
            if discovery_db and discovery_db.get("project_name"):
                repository_name = discovery_db.get("project_name")
                
        if not repository_name:
            logger.warning(f"Could not determine repository_name for job_id={job_id}. Leaving unchanged.")
            unresolved_count += 1
            continue
            
        if dry_run:
            logger.info(f"[DRY-RUN] Would update job_id={job_id} with repository_name='{repository_name}'")
            updated_count += 1
        else:
            # Conditional update: only update if missing or null to prevent overwriting concurrent updates
            result = await db.migration_job_owners.update_one(
                {
                    "job_id": job_id,
                    "$or": [
                        {"repository_name": {"$exists": False}},
                        {"repository_name": None}
                    ]
                },
                {"$set": {"repository_name": repository_name}}
            )
            if result.modified_count > 0:
                logger.info(f"Updated job_id={job_id} with repository_name='{repository_name}'")
                updated_count += 1
            else:
                logger.warning(f"Failed to update job_id={job_id}. Might have been updated concurrently.")
                unresolved_count += 1
                
    logger.info("=== Backfill Summary ===")
    logger.info(f"Total missing records found: {total_found}")
    if dry_run:
        logger.info(f"Records repairable (would be updated): {updated_count}")
    else:
        logger.info(f"Records successfully updated: {updated_count}")
    logger.info(f"Records left unresolved (no metadata or skipped): {unresolved_count}")
    
    if dry_run:
        logger.info("This was a DRY-RUN. No changes were applied to the database.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill missing repository_name on migration_job_owners.")
    parser.add_argument("--dry-run", action="store_true", help="Report proposed changes without applying them.")
    parser.add_argument("--job-id", type=str, help="Optional job ID to filter backfill.")
    args = parser.parse_args()
    
    asyncio.run(run_backfill(dry_run=args.dry_run, target_job_id=args.job_id))
