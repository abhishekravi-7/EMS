import pytest
from app.infrastructure.persistence.mongodb import mongodb_manager
from app.core.config import settings

@pytest.mark.asyncio
async def test_mongodb_connection_lifecycle():
    # Setup - ensure settings are valid for test
    if not settings.mongodb_uri:
        pytest.skip("MONGODB_URI not configured")

    try:
        # Test connection
        await mongodb_manager.connect()
        assert mongodb_manager.client is not None
        assert mongodb_manager.db is not None

        # Ping
        await mongodb_manager.client.admin.command("ping")

        # Check if users collection exists (or will be created)
        collections = await mongodb_manager.db.list_collection_names()
        assert isinstance(collections, list)

    finally:
        mongodb_manager.close()

def test_mongodb_manager_instance():
    from app.infrastructure.persistence.mongodb import MongoDBManager
    manager = MongoDBManager()
    assert manager.client is None
    assert manager.db is None
