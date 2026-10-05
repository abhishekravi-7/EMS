import pytest
import asyncio
from app.core.config import settings


@pytest.fixture
async def mongodb_client():
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except ImportError:
        pytest.skip("motor not installed")
    if not settings.mongodb_uri:
        pytest.skip("MONGODB_URI not configured")

    client = AsyncIOMotorClient(settings.mongodb_uri)
    yield client
    client.close()

@pytest.fixture
async def mongodb_db(mongodb_client):
    # Use a test database
    db_name = settings.mongodb_database + "_test"
    db = mongodb_client[db_name]

    # Setup indexes
    from app.infrastructure.persistence.mongodb_indexes import setup_mongodb_indexes
    await setup_mongodb_indexes(db)

    yield db

    # Cleanup after test
    await mongodb_client.drop_database(db_name)
