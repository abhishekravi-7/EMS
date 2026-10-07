from __future__ import annotations

import logging
from typing import Any
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


async def get_all_settings(db: AsyncIOMotorDatabase) -> dict[str, str | None]:
    """Fetch all dynamic settings from MongoDB as a dictionary."""
    if db is None:
        return {}
    cursor = db.system_settings.find({})
    docs = await cursor.to_list(length=100)
    return {d["key"]: d.get("value") for d in docs if "key" in d}


async def get_setting_value(db: AsyncIOMotorDatabase, key: str) -> str | None:
    """Fetch a single setting value by key."""
    if db is None:
        return None
    doc = await db.system_settings.find_one({"key": key})
    return doc.get("value") if doc else None


async def upsert_setting(db: AsyncIOMotorDatabase, key: str, value: str | None) -> None:
    """Create or update a setting."""
    if db is None:
        return
    await db.system_settings.update_one(
        {"key": key},
        {"$set": {"key": key, "value": value}},
        upsert=True,
    )


async def batch_update_settings(db: AsyncIOMotorDatabase, settings: dict[str, str | None]) -> None:
    """Update multiple settings in MongoDB."""
    if db is None:
        return
    for key, value in settings.items():
        await upsert_setting(db, key, value)
