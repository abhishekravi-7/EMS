"""Shared FastAPI dependencies for the API layer.

Provides authentication resolvers (`get_current_user`), authorization checks
(`verify_job_ownership`), and header-extraction utilities
(`github_token_from_header`).
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.application.services.auth_service import AuthService
from app.core import security
from app.core.config import settings
from app.core.context import user_id_ctx, job_id_ctx
from app.core.exceptions import NotAuthenticatedError
from app.infrastructure.persistence.database import get_db, get_db_optional
from app.infrastructure.persistence.migration_ownership_repository import get_job_owner_user_id
from app.infrastructure.persistence.models import User

ACCESS_TOKEN_COOKIE_NAME = "access_token"
_BEARER_PREFIX = "bearer "


def get_current_user(request: Request, db: Session | None = Depends(get_db_optional)) -> User:
    """Resolve the logged-in user from the `access_token` HttpOnly cookie or Authorization header.

    When PostgreSQL is enabled, validates the user in the database.
    When PostgreSQL is disabled, validates the JWT signature and extracts the user context without requiring database queries.
    """
    raw_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if not raw_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            raw_token = auth_header[7:].strip()

    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing access token.")

    try:
        user_id = security.decode_token(raw_token, expected_type="access")
    except security.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if db is None or not settings.database_enabled:
        from datetime import datetime, timezone
        fake_user = User()
        fake_user.id = user_id or 0
        fake_user.full_name = "Java APEX"
        fake_user.email = "javaapex@gmail.com"
        fake_user.role = "USER"
        fake_user.is_active = True
        fake_user.is_email_verified = True
        fake_user.created_at = datetime.now(timezone.utc)
        fake_user.last_login_at = datetime.now(timezone.utc)
        user_id_ctx.set(fake_user.id)
        return fake_user

    try:
        user = AuthService(db).get_user_from_access_token(raw_token)
        user_id_ctx.set(user.id)
        return user
    except NotAuthenticatedError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc


def verify_job_ownership(db: Session | None, job_id: str, current_user: User) -> None:
    """Raise 403/404 unless `current_user` is the recorded owner of `job_id`.

    When PostgreSQL is disabled, verifies that the job directory exists on filesystem storage.
    """
    if db is None or not settings.database_enabled:
        from app.infrastructure.persistence.job_repository import JobRepository
        if not JobRepository().job_exists(job_id):
            raise HTTPException(
                status_code=404,
                detail={"code": "JOB_NOT_FOUND", "message": "No migration job found for this id."},
            )
        job_id_ctx.set(job_id)
        return

    owner_user_id = get_job_owner_user_id(db, job_id)
    if owner_user_id is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": "No migration job found for this id."},
        )
    if owner_user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "You do not have access to this migration job."},
        )
    job_id_ctx.set(job_id)


def github_token_from_header(authorization: str | None = Header(default=None)) -> str:
    """Extract a GitHub PAT from the ``Authorization: Bearer <token>`` header.

    The token is passed as a header (never in the URL query string) so it never
    leaks through browser history, server logs, proxies, or referrers. Returns an
    empty string when the header is absent or malformed, preserving the previous
    "optional token" behavior for public repositories.
    """
    if not authorization:
        return ""
    value = authorization.strip()
    if value.lower().startswith(_BEARER_PREFIX):
        return value[len(_BEARER_PREFIX):].strip()
    return ""
