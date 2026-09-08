"""Database persistence for migration reports in PostgreSQL."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.persistence.database import engine
from app.infrastructure.persistence.models import PersistedMigrationReport

logger = logging.getLogger(__name__)


def save_report_to_db(job_id: str, report: dict[str, Any]) -> None:
    """Save or update the migration report in the database."""
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
