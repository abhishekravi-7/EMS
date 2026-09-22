"""Database persistence for existing-test states and reports in PostgreSQL."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.persistence.database import engine
from app.infrastructure.persistence.models import PersistedExistingTestState

logger = logging.getLogger(__name__)


def save_existing_test_state_to_db(job_id: str, state: dict[str, Any], report: dict[str, Any] | None = None) -> None:
    """Save or update the existing-test state and report in PostgreSQL."""
    if not settings.database_enabled or not engine:
        return
    try:
        status = str(state.get("status") or "IDLE")
        state_str = json.dumps(state, ensure_ascii=False)
        report_str = json.dumps(report, ensure_ascii=False) if report else None

        with Session(engine) as session:
            existing = session.execute(
                select(PersistedExistingTestState).where(PersistedExistingTestState.job_id == job_id)
            ).scalar_one_or_none()
            if existing:
                existing.status = status
                existing.state_json = state_str
                if report_str:
                    existing.report_json = report_str
            else:
                session.add(
                    PersistedExistingTestState(
                        job_id=job_id,
                        status=status,
                        state_json=state_str,
                        report_json=report_str,
                    )
                )
            session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Non-fatal: could not persist existing test state to db for %s: %s", job_id, exc)


def load_existing_test_state_from_db(job_id: str) -> dict[str, Any] | None:
    """Load existing-test state from PostgreSQL."""
    if not settings.database_enabled or not engine:
        return None
    try:
        with Session(engine) as session:
            stmt = select(PersistedExistingTestState.state_json).where(
                PersistedExistingTestState.job_id == job_id
            )
            raw = session.execute(stmt).scalar_one_or_none()
            if raw:
                return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Non-fatal: could not load existing test state from db for %s: %s", job_id, exc)
    return None


def load_existing_test_report_from_db(job_id: str) -> dict[str, Any] | None:
    """Load existing-test final report from PostgreSQL."""
    if not settings.database_enabled or not engine:
        return None
    try:
        with Session(engine) as session:
            stmt = select(PersistedExistingTestState.report_json).where(
                PersistedExistingTestState.job_id == job_id
            )
            raw = session.execute(stmt).scalar_one_or_none()
            if raw:
                return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Non-fatal: could not load existing test report from db for %s: %s", job_id, exc)
    return None


def existing_test_state_exists_in_db(job_id: str) -> bool:
    """Check if existing-test state exists in PostgreSQL."""
    if not settings.database_enabled or not engine:
        return False
    try:
        with Session(engine) as session:
            stmt = select(PersistedExistingTestState.id).where(
                PersistedExistingTestState.job_id == job_id
            )
            return session.execute(stmt).scalar_one_or_none() is not None
    except Exception as exc:  # noqa: BLE001
        logger.debug("Non-fatal: could not check existing test state existence in db for %s: %s", job_id, exc)
    return False
