import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

async def verify():
    from app.infrastructure.persistence.mongodb import get_mongodb, mongodb_manager
    from app.infrastructure.persistence.mongodb_ownership_repository import record_mongo_owner
    from app.infrastructure.persistence.job_repository import JobRepository
    
    await mongodb_manager.connect()
    db = await get_mongodb()
    
    # 1. Create a job owner
    job_id = "job_test_mongo_update"
    user_id = "test_user_id"
    owner_name = "Test User"
    owner_email = "test@example.com"
    repo_name = "test/repo"
    
    # Simulate first creation (e.g., local project or connect report start)
    record_mongo_owner(
        job_id=job_id,
        user_id=user_id,
        owner_name=owner_name,
        owner_email=owner_email,
        repository_name=repo_name
    )
    logging.info("Created mongo owner")
    
    doc = await db.migration_job_owners.find_one({"job_id": job_id})
    logging.info(f"After creation: repository_name={doc.get('repository_name')}, last_updated={doc.get('last_updated')}")
    
    # 2. Simulate saving a report
    job_repo = JobRepository()
    # saving a dummy connect report
    report = {"owner": "test", "repoName": "repo", "createdAt": "2024-01-01T12:00:00Z"}
    job_repo.save_connect_report(job_id, report)
    logging.info("Saved connect report (which triggers sync_update_job_last_updated)")
    
    doc2 = await db.migration_job_owners.find_one({"job_id": job_id})
    logging.info(f"After update: repository_name={doc2.get('repository_name')}, last_updated={doc2.get('last_updated')}")
    
    # Check if last_updated changed
    if doc.get('last_updated') != doc2.get('last_updated'):
        logging.info("SUCCESS: last_updated changed on report save!")
    else:
        logging.info("FAIL: last_updated did not change")
        
    # Clean up
    await db.migration_job_owners.delete_one({"job_id": job_id})

if __name__ == "__main__":
    asyncio.run(verify())
