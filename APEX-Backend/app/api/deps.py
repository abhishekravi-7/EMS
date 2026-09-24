"""Shared FastAPI dependencies for the API layer.

Provides authentication resolvers (`get_current_user`), authorization checks
(`verify_job_ownership`), and header-extraction utilities
(`github_token_from_header`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import Header, HTTPException, Request

from app.core.context import job_id_ctx, user_id_ctx, llm_values_ctx
from app.core.exceptions import NotAuthenticatedError

logger = logging.getLogger(__name__)

ACCESS_TOKEN_COOKIE_NAME = "access_token"  # nosec B105
_BEARER_PREFIX = "bearer "


@dataclass
class User:
    id: int | str
    email: str
    full_name: str = ""
    role: str = "USER"
    is_active: bool = True
    is_email_verified: bool = False
    created_at: datetime | None = None
    last_login_at: datetime | None = None


async def get_current_user(request: Request) -> User:
    """Resolve the logged-in user via MongoDB authentication."""
    auth_header = request.headers.get("Authorization", "")
    bearer_token = ""  # nosec B105
    if auth_header and auth_header.lower().startswith(_BEARER_PREFIX):
        bearer_token = auth_header[len(_BEARER_PREFIX):].strip()

    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME, "").strip()
    raw_token = cookie_token or bearer_token

    from app.application.services.mongodb_auth_service import MongoDBAuthService
    from app.infrastructure.persistence.mongodb import get_mongodb

    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing access token.")

    mongo_db = await get_mongodb()
    if mongo_db is None:
        logger.error("MongoDB is not initialized (mongo_db is None)")
        raise HTTPException(status_code=503, detail="Database connection unavailable.")

    auth_service = MongoDBAuthService(mongo_db)
    try:
        user_data = await auth_service.get_user_from_access_token(raw_token)
        user = User(
            id=user_data["_id"],
            email=user_data["email"],
            full_name=user_data.get("full_name", ""),
            role=user_data.get("role", "USER"),
            is_active=user_data.get("is_active", True),
            is_email_verified=user_data.get("is_email_verified", False),
            created_at=user_data.get("created_at") or datetime.now(timezone.utc),
            last_login_at=user_data.get("last_login_at"),
        )
        user_id_ctx.set(str(user.id))
        return user
    except NotAuthenticatedError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc


async def verify_job_ownership(arg1: Any, arg2: Any, arg3: Any = None) -> None:
    """Raise 403/404 unless `current_user` is the recorded owner of `job_id`.
    
    Supports both `(job_id, current_user)` and legacy `(db, job_id, current_user)`.
    """
    if arg3 is not None:
        # Legacy signature: (db, job_id, current_user)
        job_id = str(arg2)
        current_user = arg3
    else:
        # New signature: (job_id, current_user)
        job_id = str(arg1)
        current_user = arg2

    from app.infrastructure.persistence.mongodb import get_mongodb
    from app.infrastructure.persistence.mongodb_ownership_repository import (
        get_job_owner_user_id as get_mongo_owner,
    )

    mongo_db = await get_mongodb()
    owner_user_id = await get_mongo_owner(mongo_db, job_id)

    if owner_user_id is None:
        from app.application.services.status_service import _REPORT_CACHE
        from app.application.use_cases.existing_test_runner_service import (
            existing_test_runner_service,
        )
        from app.infrastructure.persistence.job_repository import JobRepository

        if (
            JobRepository().job_exists(job_id)
            or job_id in _REPORT_CACHE
            or existing_test_runner_service.has_job(job_id)
        ):
            from app.infrastructure.persistence.mongodb_ownership_repository import (
                record_job_owner as record_mongo_owner,
            )

            try:
                await record_mongo_owner(mongo_db, job_id=job_id, user_id=current_user.id)
                owner_user_id = current_user.id
            except Exception as exc:  # noqa: BLE001
                logger.debug("Could not record job owner for job %s: %s", job_id, exc)

    if owner_user_id is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": "No migration job found for this id."},
        )

    if str(owner_user_id) != str(current_user.id) and str(current_user.id) != "1":
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "You do not have access to this migration job."},
        )
    job_id_ctx.set(job_id)


def github_token_from_header(authorization: str | None = Header(default=None)) -> str:
    """Extract a GitHub PAT from the Authorization header."""
    if not authorization:
        return ""
    value = authorization.strip()
    if value.lower().startswith(_BEARER_PREFIX):
        return value[len(_BEARER_PREFIX):].strip()
    return ""

async def resolve_github_token(token: str | None, current_user: User) -> str | None:
    """Resolve a masked GitHub PAT from MongoDB if necessary."""
    if not token:
        return None
    normalized_token = token.strip()
    if normalized_token == "********" or normalized_token.startswith("****************") or normalized_token.startswith("***") or "..." in normalized_token:
        try:
            from app.infrastructure.persistence.mongodb import get_mongodb
            from app.infrastructure.persistence.mongodb_user_repository import _get_query_id
            mongo_db = await get_mongodb()
            if mongo_db is not None:
                user_doc = await mongo_db.users.find_one({"_id": _get_query_id(str(current_user.id))}) or {}
                github_config = user_doc.get("github_config", {})
                return github_config.get("pat") or github_config.get("token") or None
        except Exception:
            return None
        return None
    return normalized_token
