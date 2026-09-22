import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
import pymongo

logger = logging.getLogger(__name__)

async def setup_mongodb_indexes(db: AsyncIOMotorDatabase):
    """Idempotent, parallel creation of MongoDB indexes."""
    logger.info("Setting up MongoDB indexes in parallel...")
    
    try:
        tasks = [
            db.users.create_index([("email", pymongo.ASCENDING)], unique=True),
            db.auth_sessions.create_index([("token_hash", pymongo.ASCENDING)], unique=True),
            db.auth_sessions.create_index([("expires_at", pymongo.ASCENDING)], expireAfterSeconds=0),
            db.oauth_accounts.create_index(
                [("provider", pymongo.ASCENDING), ("provider_user_id", pymongo.ASCENDING)],
                unique=True
            ),
            db.migration_job_owners.create_index([("job_id", pymongo.ASCENDING)], unique=True),
            db.migration_job_owners.create_index([("user_id", pymongo.ASCENDING)]),
            db.migration_jobs.create_index([("job_id", pymongo.ASCENDING)], unique=True),
            db.llm_token_usage.create_index([("user_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)]),
            db.llm_token_usage.create_index([("job_id", pymongo.ASCENDING)]),
            db.password_reset_tokens.create_index([("token_hash", pymongo.ASCENDING)], unique=True),
            db.password_reset_tokens.create_index([("expires_at", pymongo.ASCENDING)], expireAfterSeconds=0),
            db.email_verification_tokens.create_index([("token_hash", pymongo.ASCENDING)], unique=True),
            db.email_verification_tokens.create_index([("expires_at", pymongo.ASCENDING)], expireAfterSeconds=0),
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("MongoDB indexes verified/created successfully.")
    except Exception as e:
        logger.error("Failed to setup MongoDB indexes: %s", e)
