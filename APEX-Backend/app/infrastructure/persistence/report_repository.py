"""Database persistence for migration reports in PostgreSQL."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.persistence.database import engine
from app.infrastructure.persistence.models import PersistedMigrationReport
from app.infrastructure.persistence.mongodb import mongodb_manager

logger = logging.getLogger(__name__)


def save_report_to_db(job_id: str, report: dict[str, Any]) -> None:
    """Save or update the migration report in the database."""
    if settings.persistence_backend == "mongodb":
        try:
            db = mongodb_manager.get_sync_db()
            if db is not None:
                db.migration_reports.update_one(
                    {"job_id": job_id},
                    {
                        "$set": {
                            "status": report.get("status", "QUEUED"),
                            "progress_percent": report.get("progressPercent", 0),
                            "current_step": report.get("currentStep"),
                            "report_json": report,
                            "updated_at": datetime.now(timezone.utc)
                        }
                    },
                    upsert=True
                )
                return
        except Exception as exc: # noqa: BLE001
            logger.debug("Non-fatal: could not persist report to MongoDB for %s: %s", job_id, exc)

    if not settings.database_enabled or not engine:
        return
    try:
        status = str(report.get("status") or "QUEUED")
        percent = int(report.get("progressPercent") or 0)
        step = str(report.get("currentStep") or "")
        report_str = json.dumps(report, ensure_ascii=False)

        with Session(engine) as session:
            existing = session.execute(
                select(PersistedMigrationReport).where(PersistedMigrationReport.job_id == job_id)
            ).scalar_one_or_none()
            if existing:
                existing.status = status
                existing.progress_percent = percent
                existing.current_step = step
                existing.report_json = report_str
            else:
                session.add(
                    PersistedMigrationReport(
                        job_id=job_id,
                        status=status,
                        progress_percent=percent,
                        current_step=step,
                        report_json=report_str,
                    )
                )
            session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Non-fatal: could not persist migration report to db for %s: %s", job_id, exc)


def load_report_from_db(job_id: str) -> dict[str, Any] | None:
    """Load the migration report from the database if present."""
    if settings.persistence_backend == "mongodb":
        try:
            db = mongodb_manager.get_sync_db()
            if db is not None:
                doc = db.migration_reports.find_one({"job_id": job_id})
                return doc["report_json"] if doc else None
        except Exception as exc: # noqa: BLE001
            logger.debug("Non-fatal: could not load report from MongoDB for %s: %s", job_id, exc)

    if not settings.database_enabled or not engine:
        return None
    try:
        with Session(engine) as session:
            stmt = select(PersistedMigrationReport.report_json).where(
                PersistedMigrationReport.job_id == job_id
            )
            raw = session.execute(stmt).scalar_one_or_none()
            if raw:
                return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Non-fatal: could not load report from db for %s: %s", job_id, exc)
    return None
