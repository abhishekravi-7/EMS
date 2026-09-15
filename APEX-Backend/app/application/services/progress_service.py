"""Small helper to advance a migration's phase and structured stage (status + step + progress)."""

from __future__ import annotations

import logging
from typing import Any

from app.application.services.status_service import MigrationReportStore

logger = logging.getLogger(__name__)


def set_phase(
    store: MigrationReportStore,
    *,
    status: str,
    step: str,
    percent: int,
    stage_id: str | None = None,
    stage_name: str | None = None,
    log_message: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Update status/current-step/progress (plus any extra fields) in one write."""
    if log_message:
        store.append_logs([log_message])
    updates: dict[str, Any] = {
        "status": status,
        "currentStep": step,
        "progressPercent": percent,
        **extra,
    }
    if stage_id:
        updates["currentStage"] = stage_id
    if stage_name:
        updates["currentStageName"] = stage_name
    logger.info("[MIGRATION PROGRESS] status=%s step=%s stage=%s percent=%d%%", status, step, stage_id or step, percent)
    return store.update(**updates)


def set_stage(
    store: MigrationReportStore,
    *,
    stage_id: str,
    stage_name: str,
    percent: int,
    status: str = "running",
    log_message: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Updates structured migration stage, progress percentage, status, and appends log."""
    return set_phase(
        store,
        status=status,
        step=stage_name,
        percent=percent,
        stage_id=stage_id,
        stage_name=stage_name,
        log_message=log_message,
        **extra,
    )

