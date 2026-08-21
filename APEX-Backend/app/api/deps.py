"""Shared FastAPI dependencies for the API layer.

Provides authentication resolvers (`get_current_user`), authorization checks
(`verify_job_ownership`), and header-extraction utilities
(`github_token_from_header`).
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.application.services.auth_service import AuthService
from app.core.config import settings
from app.core.context import user_id_ctx, job_id_ctx
from app.core.exceptions import NotAuthenticatedError
from app.infrastructure.auth.firebase_auth import verify_firebase_token
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.migration_ownership_repository import get_job_owner_user_id
from app.infrastructure.persistence.models import User

ACCESS_TOKEN_COOKIE_NAME = "access_token"
_BEARER_PREFIX = "bearer "


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the logged-in user.

    If Firebase Auth is enabled, it verifies the ID token from the
    `Authorization: Bearer <token>` header.

    Otherwise, it falls back to the legacy `access_token` HttpOnly cookie.
    """
    # 1. Try Firebase Authentication (Header-based)
    if settings.firebase_auth_enabled:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith(_BEARER_PREFIX):
            token = auth_header[len(_BEARER_PREFIX):].strip()
            return await verify_firebase_token(db, token)

        # If header is missing but Firebase is required, raise 401
        # (Unless we want to allow legacy cookie fallback during migration)
        # For a clean migration, we should require the header.
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide a valid Firebase ID token."
        )

    # 2. Legacy Cookie-based Authentication
    raw_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    try:
        user = AuthService(db).get_user_from_access_token(raw_token)
        user_id_ctx.set(user.id)
        return user
    except NotAuthenticatedError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc


def verify_job_ownership(db: Session, job_id: str, current_user: User) -> None:
    """Raise 403/404 unless `current_user` is the recorded owner of `job_id`.

    Ownership is recorded once, at job-creation time, in
    `POST /api/v1/connect` (see
    `app.infrastructure.persistence.migration_ownership_repository.record_job_owner`).
    A job with no ownership record at all (for example one created on disk
    before this feature existed) is treated as forbidden rather than
    silently allowed — the caller's identity is never inferred from
    anything the frontend sends, only from `get_current_user`.
    """
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
