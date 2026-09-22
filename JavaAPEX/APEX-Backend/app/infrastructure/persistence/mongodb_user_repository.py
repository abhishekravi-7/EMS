import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from app.core.security import hash_password

logger = logging.getLogger(__name__)

async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[dict]:
    return await db.users.find_one({"email": email.lower().strip()})

async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[dict]:
    return await db.users.find_one({"_id": user_id})


async def ensure_fallback_user(db: AsyncIOMotorDatabase, user: dict) -> None:
    """Persist a user reconstructed from a valid legacy access token."""
    try:
        await db.users.update_one(
            {"_id": str(user["_id"])},
            {"$setOnInsert": user},
            upsert=True,
        )
    except DuplicateKeyError:
        # A legacy fallback may already exist under the unique synthetic email.
        # Authentication can continue with the in-memory token identity.
        logger.info("Fallback user already exists for token user %s.", user["_id"])

async def create_user(
    db: AsyncIOMotorDatabase,
    *,
    full_name: str,
    email: str,
    password: Optional[str] = None,
    auth_provider: str = "local",
    provider_user_id: Optional[str] = None,
    role: str = "USER"
) -> dict:
    user_id = str(uuid4())
    now = datetime.now(timezone.utc)
    
    user_doc = {
        "_id": user_id,
        "full_name": full_name,
        "email": email.lower().strip(),
        "password_hash": hash_password(password) if password else None,
        "auth_provider": auth_provider,
        "auth_providers": [auth_provider],
        "provider_user_id": provider_user_id,
        "role": role,
        "is_active": True,
        "is_email_verified": False,
        "failed_login_attempts": 0,
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
    }
    
    await db.users.insert_one(user_doc)
    return user_doc

async def update_last_login(db: AsyncIOMotorDatabase, user_id: str):
    await db.users.update_one(
        {"_id": user_id},
        {"$set": {"last_login_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}}
    )

async def update_user(db: AsyncIOMotorDatabase, user_id: str, updates: dict[str, Any]):
    updates["updated_at"] = datetime.now(timezone.utc)
    await db.users.update_one({"_id": user_id}, {"$set": updates})

# --- Password Reset ---

async def create_password_reset_token(db: AsyncIOMotorDatabase, user_id: str, token: str, expires_at: datetime):
    await db.password_resets.insert_one({
        "user_id": user_id,
        "token": token,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc)
    })

async def get_password_reset_token(db: AsyncIOMotorDatabase, token: str) -> Optional[dict]:
    return await db.password_resets.find_one({"token": token})

async def delete_password_reset_token(db: AsyncIOMotorDatabase, token: str):
    await db.password_resets.delete_many({"token": token})

async def update_user_password(db: AsyncIOMotorDatabase, user_id: str, password_hash: str):
    await db.users.update_one(
        {"_id": user_id},
        {"$set": {"password_hash": password_hash, "updated_at": datetime.now(timezone.utc)}}
    )

# --- OAuth ---

async def get_oauth_account(db: AsyncIOMotorDatabase, provider: str, provider_user_id: str) -> Optional[dict]:
    pid = str(provider_user_id)
    account = await db.oauth_accounts.find_one({"provider": provider, "provider_user_id": pid})
    if not account:
        account = await db.oauth_accounts.find_one({"provider": provider, "provider_user_id": provider_user_id})
    return account

async def create_oauth_account(db: AsyncIOMotorDatabase, user_id: str, provider: str, provider_user_id: str, provider_email: Optional[str] = None):
    pid = str(provider_user_id)
    now = datetime.now(timezone.utc)
    await db.oauth_accounts.update_one(
        {"provider": provider, "provider_user_id": pid},
        {
            "$set": {
                "user_id": user_id,
                "provider": provider,
                "provider_user_id": pid,
                "provider_email": provider_email,
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now
            }
        },
        upsert=True
    )

async def create_oauth_user(
    db: AsyncIOMotorDatabase,
    *,
    full_name: str,
    email: str,
    auth_provider: str,
    provider_user_id: str,
    profile_image: Optional[str] = None,
    is_email_verified: bool = False
) -> dict:
    user_id = str(uuid4())
    now = datetime.now(timezone.utc)
    user_doc = {
        "_id": user_id,
        "full_name": full_name,
        "email": email.lower().strip(),
        "password_hash": None,
        "auth_provider": auth_provider,
        "auth_providers": [auth_provider],
        "provider_user_id": provider_user_id,
        "profile_image": profile_image,
        "role": "USER",
        "is_active": True,
        "is_email_verified": is_email_verified,
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
    }
    await db.users.insert_one(user_doc)
    return user_doc
