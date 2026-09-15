import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
import pymongo

logger = logging.getLogger(__name__)

async def setup_mongodb_indexes(db: AsyncIOMotorDatabase):
    """Idempotent creation of MongoDB indexes."""
    logger.info("Setting up MongoDB indexes...")
    
    try:
        # 1. Users
        await db.users.create_index([("email", pymongo.ASCENDING)], unique=True)
        
        # 2. Auth Sessions / Refresh Tokens
        await db.auth_sessions.create_index([("token_hash", pymongo.ASCENDING)], unique=True)
        # TTL index for expired sessions (example: expire after 7 days if revoked or naturally)
        # Using "expires_at" as a background TTL field
        await db.auth_sessions.create_index([("expires_at", pymongo.ASCENDING)], expireAfterSeconds=0)
        
        # 3. OAuth Accounts
        await db.oauth_accounts.create_index(
            [("provider", pymongo.ASCENDING), ("provider_user_id", pymongo.ASCENDING)],
            unique=True
        )
        
        # 4. Migration Job Owners
        await db.migration_job_owners.create_index(
            [("job_id", pymongo.ASCENDING)],
            unique=True
        )
        await db.migration_job_owners.create_index([("user_id", pymongo.ASCENDING)])
        
        # 5. Migration Jobs
        await db.migration_jobs.create_index([("job_id", pymongo.ASCENDING)], unique=True)
        
        # 6. LLM Token Usage
        await db.llm_token_usage.create_index([("user_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)])
        await db.llm_token_usage.create_index([("job_id", pymongo.ASCENDING)])
        
        # 7. Password Reset / Email Verification Tokens
        await db.password_reset_tokens.create_index([("token_hash", pymongo.ASCENDING)], unique=True)
        await db.password_reset_tokens.create_index([("expires_at", pymongo.ASCENDING)], expireAfterSeconds=0)
        
        await db.email_verification_tokens.create_index([("token_hash", pymongo.ASCENDING)], unique=True)
        await db.email_verification_tokens.create_index([("expires_at", pymongo.ASCENDING)], expireAfterSeconds=0)

        logger.info("MongoDB indexes verified/created successfully.")
    except Exception as e:
        logger.error("Failed to setup MongoDB indexes: %s", e)
        # Not strictly fatal for startup if they already exist or connectivity is flaky,
        # but important for production consistency.
