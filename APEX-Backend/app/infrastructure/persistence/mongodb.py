import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import pymongo
from app.core.config import settings

logger = logging.getLogger(__name__)

class MongoDBManager:
    def __init__(self):
        self.client = None
        self.db = None
        self._sync_client = None
        self._sync_db = None

    async def connect(self):
        if not settings.mongodb_enabled or not settings.mongodb_uri:
            logger.info("MongoDB is disabled or URI is missing.")
            return

        try:
            self.client = AsyncIOMotorClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=3000,
                connectTimeoutMS=5000,
            )
            self.db = self.client[settings.mongodb_database]

            # Setup sync client
            self._sync_client = pymongo.MongoClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=3000,
                connectTimeoutMS=5000,
            )
            self._sync_db = self._sync_client[settings.mongodb_database]

            # Fast ping verification
            await self.client.admin.command("ping")
            logger.info("MongoDB client initialized and pinged successfully for database: %s", settings.mongodb_database)

            # Fire index setup as background task so startup isn't blocked
            from app.infrastructure.persistence.mongodb_indexes import setup_mongodb_indexes
            asyncio.create_task(setup_mongodb_indexes(self.db))
        except Exception as e:
            logger.error("Failed to initialize MongoDB client: %s", e)

    def get_sync_db(self):
        return self._sync_db

    def get_async_db(self):
        return self.db

    def close(self):
        if self.client:
            self.client.close()
        if self._sync_client:
            self._sync_client.close()
        logger.info("MongoDB connection closed.")

mongodb_manager = MongoDBManager()

async def get_mongodb():
    return mongodb_manager.db
