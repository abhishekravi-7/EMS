import asyncio
import argparse
import logging
import sys
import os

# Set working directory to project root if running from scripts
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def run_backfill(dry_run: bool = False):
    from app.infrastructure.persistence.mongodb import get_mongodb, mongodb_manager
    from motor.motor_asyncio import AsyncIOMotorDatabase
    
    await mongodb_manager.connect()
    db: AsyncIOMotorDatabase = await get_mongodb()
    if db is None:
        logger.error("Could not connect to MongoDB.")
        sys.exit(1)
        
    cursor = db.migration_job_owners.find({
        "$or": [
            {"owner_name": {"$exists": False}},
            {"owner_email": {"$exists": False}}
        ]
    })
    
    total_found = 0
    updated_count = 0
    unmatched_count = 0
    
    async for doc in cursor:
        total_found += 1
        job_id = doc.get("job_id")
        user_id = doc.get("user_id")
        
        if not user_id:
            logger.warning(f"Record for job_id={job_id} has no user_id. Skipping.")
            unmatched_count += 1
            continue
            
        user = await db.users.find_one({"_id": user_id})
        if not user:
            logger.warning(f"No user found for user_id={user_id} on job_id={job_id}. Skipping.")
            unmatched_count += 1
            continue
            
        owner_name = user.get("full_name")
        owner_email = user.get("email")
        
        if dry_run:
            logger.info(f"[DRY-RUN] Would update job_id={job_id} with owner_name='{owner_name}' and owner_email='{owner_email}'")
            updated_count += 1
        else:
            result = await db.migration_job_owners.update_one(
                {"job_id": job_id},
                {"$set": {"owner_name": owner_name, "owner_email": owner_email}}
            )
            if result.modified_count > 0:
                logger.info(f"Updated job_id={job_id} with owner_name='{owner_name}' and owner_email='{owner_email}'")
                updated_count += 1
                
    logger.info("=== Backfill Summary ===")
    logger.info(f"Total missing records found: {total_found}")
    logger.info(f"Records updated (or would be updated): {updated_count}")
    logger.info(f"Records left unmatched/skipped: {unmatched_count}")
    
    if dry_run:
        logger.info("This was a DRY-RUN. No changes were applied to the database.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill owner_name and owner_email on migration_job_owners.")
    parser.add_argument("--dry-run", action="store_true", help="Report proposed changes without applying them.")
    args = parser.parse_args()
    
    asyncio.run(run_backfill(dry_run=args.dry_run))
