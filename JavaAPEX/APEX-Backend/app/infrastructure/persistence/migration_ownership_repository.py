"""Tracks which user owns each filesystem-stored migration job.

Migration job data itself is unchanged — it still lives on disk as JSON
reports under `storage/migration-jobs/<jobId>/` (see
`app.infrastructure.persistence.job_repository.JobRepository`). This
repository only answers "which user created job X", recorded once at job
creation time (`POST /api/v1/connect`) and checked by every job-scoped
endpoint afterward (see `app.api.deps.verify_job_ownership`).
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.persistence.models import MigrationJobOwner

logger = logging.getLogger(__name__)


def record_job_owner(db: Session | None, *, job_id: str, user_id: int | str) -> None:
    """Called once, immediately after a job is created in POST /connect."""
    if db is None or not settings.database_enabled:
        logger.info("[CONNECT] Database unavailable - continuing without persistence (job_id=%s)", job_id)
        return

    # If the user has switched to MongoDB persistence, this SQL repository should stay out of the way.
    if settings.persistence_backend == "mongodb":
        return

    # In hybrid mode (MongoDB Auth + PostgreSQL Persistence), user_id is a UUID string.
    # The SQL table migration_job_owners might still use an INTEGER column.
    try:
        # Try to ensure it's an int if possible, otherwise keep as string
        # (SQLAlchemy will handle the type mismatch if the column is String,
        # or fail at commit time if it's Integer).
        actual_user_id = int(user_id) if isinstance(user_id, str) and user_id.isdigit() else user_id
        owner = MigrationJobOwner(job_id=job_id, user_id=actual_user_id)
        db.add(owner)
        db.commit()
    except (SQLAlchemyError, ValueError, TypeError) as exc:
        db.rollback()
        # If it's a type error (e.g. UUID string into INT column), log it as warning
        # but don't crash the whole connect process in hybrid setups.
        if "InvalidTextRepresentation" in str(exc) or "integer" in str(exc).lower():
            logger.warning(
                "[CONNECT] Could not record job owner in PostgreSQL due to type mismatch (user_id=%s). "
                "This is expected if using MongoDB Auth with an unmigrated PostgreSQL schema.",
                user_id
            )
        else:
            logger.exception("Failed to record job owner (job_id=%s).", job_id)
            # Only re-raise if it's not a known hybrid-setup issue
            if not isinstance(user_id, str) or user_id.isdigit():
                raise


def get_job_owner_user_id(db: Session | None, job_id: str) -> int | None:
    """Returns the owning user's id, or None if the job has no owner record."""
    if db is None or not settings.database_enabled:
        return None
    statement = select(MigrationJobOwner.user_id).where(MigrationJobOwner.job_id == job_id)
    return db.execute(statement).scalar_one_or_none()
