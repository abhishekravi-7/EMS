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

from app.application.services.auth_service import AuthService
from app.core.config import settings
from app.core.context import job_id_ctx, user_id_ctx
from app.core.exceptions import NotAuthenticatedError
from app.infrastructure.auth.firebase_auth import is_firebase_token, verify_firebase_token
from app.infrastructure.persistence.database import get_db_optional
from app.infrastructure.persistence.migration_ownership_repository import get_job_owner_user_id
from app.infrastructure.persistence.models import User

logger = logging.getLogger(__name__)

ACCESS_TOKEN_COOKIE_NAME = "access_token"  # nosec B105
_BEARER_PREFIX = "bearer "

def _get_mock_user() -> User:
    """Helper to create a consistent mock user for database-less or auth-disabled modes."""
    fake_user = User()
    fake_user.id = 1 # Consistent ID for ownership logic
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
    """Resolve the logged-in user.

    Supports:
    1. Firebase ID token from `Authorization: Bearer <token>` (RS256 / Google JWKS).
    2. Legacy `access_token` HttpOnly cookie.
    3. Legacy HMAC access token from `Authorization: Bearer <token>`.
    4. PostgreSQL-enabled database user lookup / shadow record creation.
    5. PostgreSQL-disabled JWT signature validation & shadow user context.
    """
    auth_header = request.headers.get("Authorization", "")
    bearer_token = ""  # nosec B105
    if auth_header and auth_header.lower().startswith(_BEARER_PREFIX):
        bearer_token = auth_header[len(_BEARER_PREFIX):].strip()

    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME, "").strip()

    # 1. If bearer token is provided and matches Firebase ID token format or Firebase Auth is forced
    if bearer_token and (settings.firebase_auth_enabled or is_firebase_token(bearer_token)):
        if db is None and settings.firebase_auth_enabled and not is_firebase_token(bearer_token):
             raise HTTPException(status_code=503, detail="Database required for Firebase authentication.")
        return await verify_firebase_token(db, bearer_token)

    # 2. Development Bypass (when Firebase is disabled and not in production)
    if not settings.firebase_auth_enabled and not settings.is_production:
        return _get_mock_user()

    # 3. Legacy Extract access token from cookie or bearer header
    raw_token = cookie_token or bearer_token

    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing access token.")

    try:
        user = AuthService(db).get_user_from_access_token(raw_token) if db else None
        if user:
            user_id_ctx.set(user.id)
            return user
        return _get_mock_user()
    except NotAuthenticatedError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc


def verify_job_ownership(db: Session | None, job_id: str, current_user: User) -> None:
    """Raise 403/404 unless `current_user` is the recorded owner of `job_id`.

    When PostgreSQL is disabled, verifies that the job exists on filesystem storage, in report cache, or in active existing-test runner.
    """
    if db is None or not settings.database_enabled:
        from app.application.services.status_service import _REPORT_CACHE
        from app.application.use_cases.existing_test_runner_service import existing_test_runner_service
        from app.infrastructure.persistence.job_repository import JobRepository
        if (
            not JobRepository().job_exists(job_id)
            and job_id not in _REPORT_CACHE
            and not existing_test_runner_service.has_job(job_id)
        ):
            raise HTTPException(
                status_code=404,
                detail={"code": "JOB_NOT_FOUND", "message": "No migration job found for this id."},
            )
        job_id_ctx.set(job_id)
        return

    owner_user_id = get_job_owner_user_id(db, job_id)
    if owner_user_id is None:
        from app.application.services.status_service import _REPORT_CACHE
        from app.application.use_cases.existing_test_runner_service import existing_test_runner_service
        from app.infrastructure.persistence.existing_test_repository import existing_test_state_exists_in_db
        from app.infrastructure.persistence.job_repository import JobRepository
        from app.infrastructure.persistence.report_repository import load_report_from_db
        if (
            JobRepository().job_exists(job_id)
            or job_id in _REPORT_CACHE
            or load_report_from_db(job_id) is not None
            or existing_test_state_exists_in_db(job_id)
            or existing_test_runner_service.has_job(job_id)
        ):
            from app.infrastructure.persistence.migration_ownership_repository import record_job_owner
            try:
                record_job_owner(db, job_id=job_id, user_id=current_user.id)
                owner_user_id = current_user.id
            except Exception as exc:  # noqa: BLE001
                logger.debug("Could not record job owner for job %s: %s", job_id, exc)

    if owner_user_id is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": "No migration job found for this id."},
        )
        
    # Allow if the user matches OR if we are in mock-mode (ID 1)
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
