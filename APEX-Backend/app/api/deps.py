"""Shared FastAPI dependencies for the API layer.

Provides authentication resolvers (`get_current_user`), authorization checks
(`verify_job_ownership`), and header-extraction utilities
(`github_token_from_header`).
"""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.application.services.auth_service import AuthService
from app.core import security
from app.core.config import settings
from app.core.context import user_id_ctx, job_id_ctx
from app.core.exceptions import NotAuthenticatedError
from app.infrastructure.auth.firebase_auth import verify_firebase_token
from app.infrastructure.persistence.database import get_db, get_db_optional
from app.infrastructure.persistence.migration_ownership_repository import get_job_owner_user_id
from app.infrastructure.persistence.models import User

ACCESS_TOKEN_COOKIE_NAME = "access_token"
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

async def get_current_user(request: Request, db: Session | None = Depends(get_db_optional)) -> User:
    """Resolve the logged-in user.

    If Firebase Auth is enabled, it verifies the ID token from the
    `Authorization: Bearer <token>` header.

    If Firebase is disabled, it falls back to mock user in development or legacy cookies.
    """
    # 1. Try Firebase Authentication (Header-based)
    if settings.firebase_auth_enabled:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith(_BEARER_PREFIX):
            token = auth_header[len(_BEARER_PREFIX):].strip()
            if db is None:
                 raise HTTPException(status_code=503, detail="Database required for Firebase authentication.")
            return await verify_firebase_token(db, token)

        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide a valid Firebase ID token."
        )

    # 2. Development Bypass (when Firebase is disabled)
    if not settings.is_production:
        return _get_mock_user()

    # 3. Legacy Cookie-based Authentication
    raw_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if not raw_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            raw_token = auth_header[7:].strip()

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
    """Raise 403/404 unless `current_user` is the recorded owner of `job_id`."""
    if not settings.database_enabled or db is None:
        # In DB-less mode, we just verify the job exists on disk
        from app.infrastructure.persistence.job_repository import JobRepository
        if not JobRepository().job_exists(job_id):
            raise HTTPException(status_code=404, detail="Job not found.")
        job_id_ctx.set(job_id)
        return

    owner_user_id = get_job_owner_user_id(db, job_id)
    if owner_user_id is None:
        raise HTTPException(status_code=404, detail="Job ownership record not found.")

    # Allow if the user matches OR if we are in mock-mode (ID 1)
    if owner_user_id != current_user.id and current_user.id != 1:
        raise HTTPException(status_code=403, detail="Access denied to this job.")

    job_id_ctx.set(job_id)


def github_token_from_header(authorization: str | None = Header(default=None)) -> str:
    """Extract a GitHub PAT from the Authorization header."""
    if not authorization:
        return ""
    value = authorization.strip()
    if value.lower().startswith(_BEARER_PREFIX):
        return value[len(_BEARER_PREFIX):].strip()
    return ""
