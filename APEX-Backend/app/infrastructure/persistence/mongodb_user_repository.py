import logging
from datetime import datetime, timezone
from typing import Any, Optional

import pymongo
from pymongo import ReturnDocument
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from app.core.security import hash_password

logger = logging.getLogger(__name__)


async def get_next_sequence_value(db: AsyncIOMotorDatabase, sequence_name: str = "users") -> int:
    """Atomically increment and return the next sequential integer ID.

    If counter document doesn't exist yet, it is created and the first sequence value is 1.
    """
    result = await db.counters.find_one_and_update(
        {"_id": sequence_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(result["seq"])


async def migrate_to_numeric_id(db: AsyncIOMotorDatabase) -> None:
    """Safely migrate MongoDB users collection so that _id itself is a sequential integer.

    1. Reads legacy users where _id is a string/UUID.
    2. Determines target integer _id (using existing numeric user_id if valid, or generating next sequence).
    3. Replaces document with numeric _id and removes separate user_id field.
    4. Updates references in dependent collections (auth_sessions, oauth_accounts, password_resets, etc.).
    5. Verifies replacement exists before deleting old document.
    6. Synchronizes counters sequence to max(_id).
    """
    try:
        cursor = db.users.find({"_id": {"$type": "string"}}).sort("created_at", pymongo.ASCENDING)
        legacy_users = await cursor.to_list(length=10000)

        if legacy_users:
            logger.info("Migrating %d legacy users with string _id to sequential integer _id...", len(legacy_users))

            # Identify already claimed numeric user IDs
            existing_numeric_docs = await db.users.find({"_id": {"$type": "number"}}, {"_id": 1}).to_list(length=10000)
            assigned_ids = {int(d["_id"]) for d in existing_numeric_docs if isinstance(d.get("_id"), (int, float))}
            for doc in legacy_users:
                uid = doc.get("user_id")
                if isinstance(uid, int) and uid > 0:
                    assigned_ids.add(uid)

            # Sync counter to at least the highest known ID so far
            if assigned_ids:
                await db.counters.update_one(
                    {"_id": "users"},
                    {"$max": {"seq": max(assigned_ids)}},
                    upsert=True,
                )

            for doc in legacy_users:
                old_uuid = doc["_id"]
                existing_user_id = doc.get("user_id")
                if isinstance(existing_user_id, int) and existing_user_id > 0:
                    target_id = existing_user_id
                else:
                    target_id = await get_next_sequence_value(db, "users")
                    while target_id in assigned_ids:
                        target_id = await get_next_sequence_value(db, "users")
                    assigned_ids.add(target_id)

                new_doc = dict(doc)
                new_doc["_id"] = target_id
                if "email" in new_doc and isinstance(new_doc["email"], str):
                    new_doc["email"] = new_doc["email"].strip().lower()
                new_doc.pop("user_id", None)

                temp_email = f"__migrating__{old_uuid}__{doc.get('email', '')}"
                await db.users.update_one({"_id": old_uuid}, {"$set": {"email": temp_email}})
                try:
                    # Upsert replacement document with integer _id
                    await db.users.replace_one({"_id": target_id}, new_doc, upsert=True)

                    # Update references in dependent collections
                    await db.auth_sessions.update_many(
                        {"$or": [{"user_id": old_uuid}, {"user_id": str(old_uuid)}]},
                        {"$set": {"user_id": target_id}},
                    )
                    await db.oauth_accounts.update_many(
                        {"$or": [{"user_id": old_uuid}, {"user_id": str(old_uuid)}]},
                        {"$set": {"user_id": target_id}},
                    )
                    await db.password_resets.update_many(
                        {"$or": [{"user_id": old_uuid}, {"user_id": str(old_uuid)}]},
                        {"$set": {"user_id": target_id}},
                    )
                    await db.migration_job_owners.update_many(
                        {"user_id": old_uuid},
                        {"$set": {"user_id": str(target_id)}},
                    )
                    await db.llm_token_usage.update_many(
                        {"user_id": old_uuid},
                        {"$set": {"user_id": str(target_id)}},
                    )

                    # Verify replacement exists before deleting old document
                    verified = await db.users.find_one({"_id": target_id})
                    if verified:
                        await db.users.delete_one({"_id": old_uuid})
                except Exception as exc:
                    logger.error("Failed to migrate user %s: %s", old_uuid, exc)
                    await db.users.update_one({"_id": old_uuid}, {"$set": {"email": doc.get("email", "")}})
                    raise

            logger.info("Successfully migrated legacy user documents to sequential integer _id.")

        # Clean up any residual 'user_id' fields on numeric _id documents
        await db.users.update_many({"user_id": {"$exists": True}}, {"$unset": {"user_id": ""}})

        # Synchronize oauth_accounts user_id references
        await sync_oauth_accounts_user_ids(db)

        # Synchronize counters collection to current max _id
        max_user = await db.users.find_one({"_id": {"$type": "number"}}, sort=[("_id", pymongo.DESCENDING)])
        if max_user and isinstance(max_user.get("_id"), (int, float)):
            current_max = int(max_user["_id"])
            await db.counters.update_one(
                {"_id": "users"},
                {"$max": {"seq": current_max}},
                upsert=True,
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed during migrate_to_numeric_id: %s", exc)


async def sync_oauth_accounts_user_ids(db: AsyncIOMotorDatabase) -> None:
    """Ensure oauth_accounts records have valid, synchronized integer user_id references."""
    try:
        oauth_docs = await db.oauth_accounts.find({}).to_list(length=10000)
        for doc in oauth_docs:
            p_email = doc.get("provider_email")
            if p_email and isinstance(p_email, str):
                norm_email = p_email.strip().lower()
                user = await db.users.find_one({"email": norm_email})
                if user and user.get("_id") != doc.get("user_id"):
                    logger.info(
                        "Syncing oauth_account for %s: user_id %s -> %s",
                        norm_email,
                        doc.get("user_id"),
                        user["_id"],
                    )
                    await db.oauth_accounts.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"user_id": user["_id"], "provider_email": norm_email}},
                    )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed during sync_oauth_accounts_user_ids: %s", exc)





async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[dict]:
    if not email or not isinstance(email, str):
        return None
    return await db.users.find_one({"email": email.strip().lower()})


def _get_query_id(user_id: Any) -> dict:
    if isinstance(user_id, dict):
        return user_id
    if user_id is None:
        return {}
    if isinstance(user_id, int):
        return {"$or": [{"_id": user_id}, {"_id": str(user_id)}]}
    s_uid = str(user_id).strip()
    if s_uid.isdigit():
        num_id = int(s_uid)
        return {"$or": [{"_id": num_id}, {"_id": s_uid}]}
    from bson import ObjectId
    if ObjectId.is_valid(s_uid):
        return {"$or": [{"_id": ObjectId(s_uid)}, {"_id": s_uid}]}
    if "@" in s_uid:
        return {"$or": [{"email": s_uid.lower()}, {"_id": s_uid}]}
    return {"_id": s_uid}


async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: Any) -> Optional[dict]:
    if db is None or user_id is None:
        return None
    if isinstance(user_id, int):
        doc = await db.users.find_one({"_id": user_id})
        if doc:
            return doc
    if isinstance(user_id, str):
        s_uid = user_id.strip()
        if s_uid.isdigit():
            doc = await db.users.find_one({"_id": int(s_uid)})
            if doc:
                return doc
        from bson import ObjectId
        if ObjectId.is_valid(s_uid):
            doc = await db.users.find_one({"_id": ObjectId(s_uid)})
            if doc:
                return doc
        doc = await db.users.find_one({"_id": s_uid})
        if doc:
            return doc
        if "@" in s_uid:
            doc = await db.users.find_one({"email": s_uid.lower()})
            if doc:
                return doc
    query = _get_query_id(user_id)
    return await db.users.find_one(query)



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

DEFAULT_SETTINGS_PERMISSIONS = {
    "llm_settings": True,
    "quality_checks": True,
    "unit_testing": True,
    "functional_testing": True,
    "brd_testing": True,
    "test_connection": True,
}

def normalize_permissions(raw_perms: Any) -> dict[str, bool]:
    perms = dict(DEFAULT_SETTINGS_PERMISSIONS)
    if not isinstance(raw_perms, dict):
        return perms

    key_mapping = {
        "llmsettings": "llm_settings",
        "llm_settings": "llm_settings",
        "qualitychecks": "quality_checks",
        "quality_checks": "quality_checks",
        "unittesting": "unit_testing",
        "unit_testing": "unit_testing",
        "functionaltesting": "functional_testing",
        "functional_testing": "functional_testing",
        "brdtesting": "brd_testing",
        "brd_testing": "brd_testing",
        "testconnection": "test_connection",
        "test_connection": "test_connection",
    }

    for k, v in raw_perms.items():
        norm_k = key_mapping.get(str(k).lower().replace("_", ""))
        if norm_k:
            perms[norm_k] = str(v).strip().lower() in {"1", "true", "yes", "on", "true"} if not isinstance(v, bool) else bool(v)

    return perms

async def get_all_users_sanitized(db: AsyncIOMotorDatabase) -> list[dict]:
    if db is None:
        return []
    cursor = db.users.find({}, {
        "password_hash": 0,
        "verification_code": 0,
        "reset_token": 0,
    }).sort("created_at", pymongo.DESCENDING)
    docs = await cursor.to_list(length=1000)
    sanitized = []
    for doc in docs:
        raw_id = doc.get("_id")
        user_id_val = raw_id if isinstance(raw_id, (int, float)) else str(raw_id)
        sanitized.append({
            "id": user_id_val,
            "_id": user_id_val,
            "full_name": doc.get("full_name") or doc.get("name") or (doc.get("email", "").split("@")[0] if doc.get("email") else "User"),
            "email": doc.get("email", ""),
            "role": doc.get("role", "USER"),
            "settings_permissions": normalize_permissions(doc.get("settings_permissions")),
            "created_at": doc.get("created_at").isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at"),
        })
    return sanitized

async def create_user(
    db: AsyncIOMotorDatabase,
    *,
    full_name: str,
    email: str,
    password: Optional[str] = None,
    password_hash: Optional[str] = None,
    auth_provider: str = "local",
    provider_user_id: Optional[str] = None,
    role: str = "USER",
    is_email_verified: bool = False,
) -> dict:
    numeric_id = await get_next_sequence_value(db, "users")
    now = datetime.now(timezone.utc)

    final_hash = password_hash if password_hash else (hash_password(password) if password else None)
    user_doc = {
        "_id": numeric_id,
        "full_name": full_name,
        "email": email.lower().strip(),
        "password_hash": final_hash,
        "auth_provider": auth_provider,
        "auth_providers": [auth_provider],
        "provider_user_id": provider_user_id,
        "role": role,
        "is_active": True,
        "is_email_verified": is_email_verified,
        "settings_permissions": dict(DEFAULT_SETTINGS_PERMISSIONS),
        "failed_login_attempts": 0,
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
    }

    await db.users.insert_one(user_doc)
    return user_doc


async def update_last_login(db: AsyncIOMotorDatabase, user_id: Any):
    target_id = int(user_id) if (isinstance(user_id, int) or (isinstance(user_id, str) and user_id.isdigit())) else user_id
    await db.users.update_one(
        {"_id": target_id},
        {"$set": {"last_login_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}},
    )


async def update_user(db: AsyncIOMotorDatabase, user_id: Any, updates: dict[str, Any]):
    if db is None or user_id is None:
        return
    updates["updated_at"] = datetime.now(timezone.utc)
    if isinstance(user_id, dict):
        query = user_id
    elif isinstance(user_id, (str, int)):
        query = _get_query_id(str(user_id))
    else:
        query = {"_id": user_id}
    await db.users.update_one(query, {"$set": updates})


# --- Password Reset ---

async def create_password_reset_token(db: AsyncIOMotorDatabase, user_id: Any, token: str, expires_at: datetime, email: Optional[str] = None):
    numeric_user_id = int(user_id) if (isinstance(user_id, int) or (isinstance(user_id, str) and user_id.isdigit())) else user_id
    await db.password_resets.insert_one({
        "user_id": numeric_user_id,
        "email": email,
        "token": token,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc),
    })


async def get_password_reset_token(db: AsyncIOMotorDatabase, token: str) -> Optional[dict]:
    return await db.password_resets.find_one({"token": token})


async def delete_password_reset_token(db: AsyncIOMotorDatabase, token: str):
    await db.password_resets.delete_many({"token": token})


async def update_user_password(db: AsyncIOMotorDatabase, user_id: Any, password_hash: str):
    target_id = int(user_id) if (isinstance(user_id, int) or (isinstance(user_id, str) and user_id.isdigit())) else user_id
    await db.users.update_one(
        {"_id": target_id},
        {"$set": {"password_hash": password_hash, "updated_at": datetime.now(timezone.utc)}},
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


async def create_oauth_account(db: AsyncIOMotorDatabase, user_id: Any, provider: str, provider_user_id: str, provider_email: Optional[str] = None):
    numeric_user_id = int(user_id) if (isinstance(user_id, int) or (isinstance(user_id, str) and user_id.isdigit())) else user_id
    await db.oauth_accounts.insert_one({
        "user_id": numeric_user_id,
        "provider": provider,
        "provider_user_id": provider_user_id,
        "provider_email": provider_email,
        "created_at": datetime.now(timezone.utc),
    })


async def create_oauth_user(
    db: AsyncIOMotorDatabase,
    *,
    full_name: str,
    email: str,
    auth_provider: str,
    provider_user_id: str,
    profile_image: Optional[str] = None,
    is_email_verified: bool = False,
    github_account: Optional[str] = None,
) -> dict:
    numeric_id = await get_next_sequence_value(db, "users")
    now = datetime.now(timezone.utc)
    user_doc = {
        "_id": numeric_id,
        "full_name": full_name,
        "email": email.lower().strip(),
        "password_hash": None,
        "auth_provider": auth_provider,
        "auth_providers": [auth_provider],
        "provider_user_id": provider_user_id,
        "profile_image": profile_image,
        "github_account": github_account,
        "role": "USER",
        "is_active": True,
        "is_email_verified": is_email_verified,
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
    }
    await db.users.insert_one(user_doc)
    return user_doc


# --- Email Verification ---

async def create_email_verification_code(
    db: AsyncIOMotorDatabase,
    user_id: Any,
    email: str,
    code_hash: str,
    expires_at: datetime,
) -> dict:
    numeric_user_id = int(user_id) if (isinstance(user_id, int) or (isinstance(user_id, str) and user_id.isdigit())) else user_id
    doc = {
        "user_id": numeric_user_id,
        "email": email.strip().lower(),
        "code_hash": code_hash,
        "token_hash": code_hash,  # for backwards compatibility
        "expires_at": expires_at,
        "attempts": 0,
        "max_attempts": 5,
        "created_at": datetime.now(timezone.utc),
        "used_at": None,
    }
    await db.email_verifications.insert_one(doc)
    return doc


async def get_latest_email_verification(db: AsyncIOMotorDatabase, email: str) -> Optional[dict]:
    """Retrieve the most recent email verification record for an email address."""
    return await db.email_verifications.find_one(
        {"email": email.strip().lower()},
        sort=[("created_at", pymongo.DESCENDING)],
    )


async def increment_verification_attempts(db: AsyncIOMotorDatabase, verification_id: Any) -> int:
    """Atomically increment failed attempts counter and return updated attempts."""
    result = await db.email_verifications.find_one_and_update(
        {"_id": verification_id},
        {"$inc": {"attempts": 1}},
        return_document=ReturnDocument.AFTER,
    )
    return int(result.get("attempts", 0)) if result else 0


async def mark_email_verification_used(db: AsyncIOMotorDatabase, verification_id: Any) -> None:
    """Mark verification record as used."""
    await db.email_verifications.update_one(
        {"_id": verification_id},
        {"$set": {"used_at": datetime.now(timezone.utc)}},
    )


async def invalidate_pending_email_verifications(db: AsyncIOMotorDatabase, email: str) -> None:
    """Invalidate all prior unused verification codes for this email."""
    await db.email_verifications.update_many(
        {"email": email.strip().lower(), "used_at": None},
        {"$set": {"used_at": datetime.now(timezone.utc)}},
    )


async def verify_user_email(db: AsyncIOMotorDatabase, user_id: Any) -> None:
    target_id = int(user_id) if (isinstance(user_id, int) or (isinstance(user_id, str) and user_id.isdigit())) else user_id
    await db.users.update_one(
        {"_id": target_id},
        {"$set": {"is_email_verified": True, "updated_at": datetime.now(timezone.utc)}},
    )


async def create_email_verification_token(
    db: AsyncIOMotorDatabase,
    user_id: Any,
    email: str,
    token_hash: str,
    expires_at: datetime,
) -> dict:
    return await create_email_verification_code(
        db, user_id=user_id, email=email, code_hash=token_hash, expires_at=expires_at
    )


async def get_email_verification_token(db: AsyncIOMotorDatabase, token_hash: str) -> Optional[dict]:
    return await db.email_verifications.find_one({"$or": [{"token_hash": token_hash}, {"code_hash": token_hash}]})


async def mark_email_verification_token_used(db: AsyncIOMotorDatabase, token_hash: str) -> None:
    await db.email_verifications.update_one(
        {"$or": [{"token_hash": token_hash}, {"code_hash": token_hash}]},
        {"$set": {"used_at": datetime.now(timezone.utc)}},
    )


# --- Pending Signups (Temporary Unverified Registrations) ---

async def create_or_update_pending_signup(
    db: AsyncIOMotorDatabase,
    *,
    email: str,
    password_hash: str,
    full_name: str,
    verification_code_hash: str,
    expires_at: datetime,
) -> dict:
    """Create or replace a temporary pending signup record until verification code is confirmed."""
    norm_email = email.strip().lower()
    now = datetime.now(timezone.utc)
    doc = {
        "email": norm_email,
        "password_hash": password_hash,
        "full_name": full_name.strip() if full_name else "User",
        "verification_code_hash": verification_code_hash,
        "expires_at": expires_at,
        "attempts": 0,
        "created_at": now,
        "updated_at": now,
    }
    await db.pending_signups.update_one(
        {"email": norm_email},
        {"$set": doc},
        upsert=True,
    )
    return doc


async def get_pending_signup(db: AsyncIOMotorDatabase, email: str) -> Optional[dict]:
    """Retrieve pending signup record by email."""
    if not email or not isinstance(email, str):
        return None
    return await db.pending_signups.find_one({"email": email.strip().lower()})


async def increment_pending_signup_attempts(db: AsyncIOMotorDatabase, email: str) -> int:
    """Atomically increment failed attempts for a pending signup."""
    if not email or not isinstance(email, str):
        return 0
    result = await db.pending_signups.find_one_and_update(
        {"email": email.strip().lower()},
        {"$inc": {"attempts": 1}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    return int(result.get("attempts", 0)) if result else 0


async def update_pending_signup_code(
    db: AsyncIOMotorDatabase,
    *,
    email: str,
    verification_code_hash: str,
    expires_at: datetime,
) -> None:
    """Update verification code and reset attempts for pending signup resend."""
    await db.pending_signups.update_one(
        {"email": email.strip().lower()},
        {
            "$set": {
                "verification_code_hash": verification_code_hash,
                "expires_at": expires_at,
                "attempts": 0,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )


async def delete_pending_signup(db: AsyncIOMotorDatabase, email: str) -> None:
    """Remove pending signup record once user account is created or invalidated."""
    if not email or not isinstance(email, str):
        return
    await db.pending_signups.delete_many({"email": email.strip().lower()})
