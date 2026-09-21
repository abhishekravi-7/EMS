"""Shared FastAPI dependencies for the API layer.

Provides authentication resolvers (`get_current_user`), authorization checks
(`verify_job_ownership`), and header-extraction utilities
(`github_token_from_header`).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import job_id_ctx, user_id_ctx, llm_values_ctx
from app.core.exceptions import NotAuthenticatedError
from app.infrastructure.persistence.database import get_db_optional
from app.infrastructure.persistence.models import User

logger = logging.getLogger(__name__)

ACCESS_TOKEN_COOKIE_NAME = "access_token"  # nosec B105
_BEARER_PREFIX = "bearer "


def _get_mock_user() -> User:
    """Helper to create a consistent mock user for database-less or auth-disabled modes."""
    fake_user = User()
    fake_user.id = 1  # Consistent ID for ownership logic
    fake_user.full_name = "Java APEX User"
    fake_user.email = "javaapex@gmail.com"
    fake_user.role = "USER"
    fake_user.is_active = True
    fake_user.is_email_verified = True
    fake_user.created_at = datetime.now(timezone.utc)
    fake_user.last_login_at = datetime.now(timezone.utc)
    user_id_ctx.set(fake_user.id)
    return fake_user


async def get_current_user(request: Request, db: Session | None = Depends(get_db_optional)) -> User:  # noqa: B008
    """Resolve the logged-in user via MongoDB authentication."""
    auth_header = request.headers.get("Authorization", "")
    bearer_token = ""  # nosec B105
    if auth_header and auth_header.lower().startswith(_BEARER_PREFIX):
        bearer_token = auth_header[len(_BEARER_PREFIX):].strip()

    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME, "").strip()
    raw_token = cookie_token or bearer_token

    # 1. MongoDB Provider
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

        # Map dict to an object that behaves like a User model
        class MongoUser:
            def __init__(self, data):
                self.id = str(data["_id"])
                self.email = data["email"]
                self.full_name = data.get("full_name", "")
                self.role = data.get("role", "USER")
                self.is_active = data.get("is_active", True)
                self.is_email_verified = data.get("is_email_verified", False)
                self.created_at = data.get("created_at") or datetime.now(timezone.utc)
                self.last_login_at = data.get("last_login_at")
                self.llm_values = data.get("llm_values", {})

        user = MongoUser(user_data)
        user_id_ctx.set(user.id)
        llm_values_ctx.set(user.llm_values)
        return user  # type: ignore
    except NotAuthenticatedError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc


async def verify_job_ownership(db: Session | None, job_id: str, current_user: User) -> None:
    """Raise 403/404 unless `current_user` is the recorded owner of `job_id`."""
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
                await record_mongo_owner(
                    mongo_db, 
                    job_id=job_id, 
                    user_id=str(current_user.id),
                    owner_name=current_user.full_name,
                    owner_email=current_user.email
                )
                owner_user_id = current_user.id
            except Exception as exc:  # noqa: BLE001
                logger.debug("Could not record job owner for job %s: %s", job_id, exc)

    if owner_user_id is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": "No migration job found for this id."},
        )

    if owner_user_id != current_user.id and current_user.id != 1:
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
    if normalized_token == "********" or normalized_token.startswith("****************"):
        from app.infrastructure.persistence.mongodb import get_mongodb
        mongo_db = await get_mongodb()
        user_doc = await mongo_db.users.find_one({"_id": str(current_user.id)}) or {}
        github_config = user_doc.get("github_config", {})
        return github_config.get("pat") or None
    return normalized_token
