import pytest
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from motor.motor_asyncio import AsyncIOMotorClient
from app.infrastructure.persistence.mongodb_ownership_repository import record_job_owner

@pytest.fixture
async def mongo_db():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.apex_test_db
    yield db
    # Cleanup after test
    await db.migration_job_owners.drop()
    client.close()

@pytest.mark.asyncio
async def test_record_job_owner_new_jobs_save_respective_repository_names(mongo_db):
    await record_job_owner(mongo_db, "job1", "user1", repository_name="repo1")
    await record_job_owner(mongo_db, "job2", "user2", repository_name="repo2")
    
    doc1 = await mongo_db.migration_job_owners.find_one({"job_id": "job1"})
    doc2 = await mongo_db.migration_job_owners.find_one({"job_id": "job2"})
    
    assert doc1["repository_name"] == "repo1"
    assert doc2["repository_name"] == "repo2"

@pytest.mark.asyncio
async def test_repository_metadata_arriving_after_ownership_creation_populates_correctly(mongo_db):
    # Initial creation without repository_name
    await record_job_owner(mongo_db, "job3", "user3", owner_name="User Three")
    doc = await mongo_db.migration_job_owners.find_one({"job_id": "job3"})
    assert doc.get("repository_name") is None
    
    # Later update with repository_name
    await record_job_owner(mongo_db, "job3", "user3", repository_name="repo3")
    doc_updated = await mongo_db.migration_job_owners.find_one({"job_id": "job3"})
    assert doc_updated["repository_name"] == "repo3"
    assert doc_updated["owner_name"] == "User Three"

@pytest.mark.asyncio
async def test_later_updates_do_not_remove_saved_repository_name(mongo_db):
    # Initial creation with repository_name
    await record_job_owner(mongo_db, "job4", "user4", repository_name="repo4")
    
    # Later update without repository_name (e.g. from deps.py)
    await record_job_owner(mongo_db, "job4", "user4", owner_name="User Four")
    
    doc = await mongo_db.migration_job_owners.find_one({"job_id": "job4"})
    assert doc["repository_name"] == "repo4"

@pytest.mark.asyncio
async def test_repeated_operations_do_not_create_duplicates(mongo_db):
    await record_job_owner(mongo_db, "job5", "user5", repository_name="repo5")
    await record_job_owner(mongo_db, "job5", "user5", repository_name="repo5")
    
    count = await mongo_db.migration_job_owners.count_documents({"job_id": "job5"})
    assert count == 1

if __name__ == "__main__":
    async def run_tests():
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        db = client.apex_test_db
        await db.migration_job_owners.drop()
        try:
            print("test 1")
            await test_record_job_owner_new_jobs_save_respective_repository_names(db)
            print("test 2")
            await test_repository_metadata_arriving_after_ownership_creation_populates_correctly(db)
            print("test 3")
            await test_later_updates_do_not_remove_saved_repository_name(db)
            print("test 4")
            await test_repeated_operations_do_not_create_duplicates(db)
            print("ALL PASSED")
        finally:
            await db.migration_job_owners.drop()
            client.close()
            
    asyncio.run(run_tests())
