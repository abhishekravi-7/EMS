import asyncio
import pytest
from datetime import datetime, timezone

from app.api.deps import User, get_current_user
from app.application.services.mongodb_auth_service import MongoDBAuthService
from app.infrastructure.persistence.mongodb_user_repository import (
    create_oauth_user,
    create_user,
    get_next_sequence_value,
    get_user_by_email,
    get_user_by_id,
    migrate_to_numeric_id,
)
from app.schemas.auth_schema import UserResponse


@pytest.mark.asyncio
async def test_get_next_sequence_value_starts_at_one(mongodb_db):
    """Sequence starts at 1 and increments sequentially."""
    seq1 = await get_next_sequence_value(mongodb_db, "users")
    assert seq1 == 1

    seq2 = await get_next_sequence_value(mongodb_db, "users")
    assert seq2 == 2

    seq3 = await get_next_sequence_value(mongodb_db, "users")
    assert seq3 == 3


@pytest.mark.asyncio
async def test_create_user_uses_numeric_id(mongodb_db):
    """create_user assigns sequential integer _id directly with no user_id field."""
    u1 = await create_user(mongodb_db, full_name="User One", email="u1@example.com", password="Password@123")
    assert u1["_id"] == 1
    assert isinstance(u1["_id"], int)
    assert "user_id" not in u1

    u2 = await create_user(mongodb_db, full_name="User Two", email="u2@example.com", password="Password@123")
    assert u2["_id"] == 2
    assert isinstance(u2["_id"], int)
    assert "user_id" not in u2

    # Query by numeric _id
    found1 = await get_user_by_id(mongodb_db, 1)
    assert found1 is not None
    assert found1["email"] == "u1@example.com"
    assert found1["_id"] == 1

    # Query by string numeric _id (as decoded from JWT sub)
    found_str = await get_user_by_id(mongodb_db, "1")
    assert found_str is not None
    assert found_str["_id"] == 1


@pytest.mark.asyncio
async def test_create_oauth_user_uses_numeric_id(mongodb_db):
    """create_oauth_user assigns sequential integer _id."""
    u = await create_oauth_user(
        mongodb_db,
        full_name="OAuth User",
        email="oauth@example.com",
        auth_provider="google",
        provider_user_id="google_12345",
    )
    assert u["_id"] == 1
    assert isinstance(u["_id"], int)
    assert "user_id" not in u
    assert u["auth_provider"] == "google"


@pytest.mark.asyncio
async def test_migrate_to_numeric_id_existing_users(mongodb_db):
    """Existing users with UUID _id are safely migrated to numeric _id and dependencies updated."""
    now = datetime.now(timezone.utc)
    # Insert 2 legacy users with UUID _id
    await mongodb_db.users.insert_many([
        {"_id": "legacy-uuid-1", "user_id": 1, "email": "legacy1@example.com", "full_name": "Legacy One", "created_at": now},
        {"_id": "legacy-uuid-2", "email": "legacy2@example.com", "full_name": "Legacy Two", "created_at": now},
    ])

    # Insert dependent records referencing old UUIDs
    await mongodb_db.auth_sessions.insert_one({"user_id": "legacy-uuid-1", "token_hash": "hash1"})
    await mongodb_db.oauth_accounts.insert_one({"user_id": "legacy-uuid-1", "provider": "google", "provider_user_id": "p1"})
    await mongodb_db.password_resets.insert_one({"user_id": "legacy-uuid-1", "token": "tok1"})
    await mongodb_db.migration_job_owners.insert_one({"job_id": "job1", "user_id": "legacy-uuid-1"})

    # Run migration
    await migrate_to_numeric_id(mongodb_db)

    # 1. Old UUID documents should be gone
    assert await mongodb_db.users.find_one({"_id": "legacy-uuid-1"}) is None
    assert await mongodb_db.users.find_one({"_id": "legacy-uuid-2"}) is None

    # 2. Replacement documents with integer _id must exist
    u1 = await mongodb_db.users.find_one({"_id": 1})
    u2 = await mongodb_db.users.find_one({"_id": 2})

    assert u1 is not None
    assert u1["email"] == "legacy1@example.com"
    assert u1["_id"] == 1
    assert "user_id" not in u1

    assert u2 is not None
    assert u2["email"] == "legacy2@example.com"
    assert u2["_id"] == 2
    assert "user_id" not in u2

    # 3. Dependent collection references must be updated
    session = await mongodb_db.auth_sessions.find_one({"token_hash": "hash1"})
    assert session["user_id"] == 1

    oauth = await mongodb_db.oauth_accounts.find_one({"provider_user_id": "p1"})
    assert oauth["user_id"] == 1

    reset = await mongodb_db.password_resets.find_one({"token": "tok1"})
    assert reset["user_id"] == 1

    owner = await mongodb_db.migration_job_owners.find_one({"job_id": "job1"})
    assert owner["user_id"] == "1"

    # 4. Counter must be at 2
    counter = await mongodb_db.counters.find_one({"_id": "users"})
    assert counter["seq"] == 2

    # 5. Next created user must receive _id = 3
    u3 = await create_user(mongodb_db, full_name="User Three", email="u3@example.com", password="Password@123")
    assert u3["_id"] == 3


@pytest.mark.asyncio
async def test_concurrent_registrations_receive_distinct_sequential_numeric_ids(mongodb_db):
    """Concurrent user creations all receive distinct integer sequence values as _id."""
    tasks = [
        create_user(mongodb_db, full_name=f"User {i}", email=f"concurrent{i}@example.com", password="Password@123")
        for i in range(10)
    ]
    created_users = await asyncio.gather(*tasks)
    ids = [u["_id"] for u in created_users]

    # All _id values must be unique integers from 1 to 10
    assert len(ids) == 10
    assert len(set(ids)) == 10
    assert set(ids) == set(range(1, 11))


def test_user_response_schema_serialization():
    """UserResponse schema serializes integer id and userId properly."""
    now = datetime.now(timezone.utc)
    user_dict = {
        "id": 42,
        "fullName": "Javaapex",
        "email": "javaapex@example.com",
        "role": "USER",
        "isActive": True,
        "isEmailVerified": False,
        "createdAt": now,
        "lastLoginAt": None,
    }
    model = UserResponse.model_validate(user_dict)
    assert model.id == 42
    assert model.userId == 42

    dumped = model.model_dump(by_alias=True, mode="json")
    assert dumped["id"] == 42
    assert dumped["userId"] == 42
    assert dumped["fullName"] == "Javaapex"
    assert dumped["email"] == "javaapex@example.com"
