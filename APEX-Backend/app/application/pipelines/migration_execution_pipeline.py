"""Migration Execution pipeline.

Orchestrates Start Migration: validates + queues the job, runs the long
migration in a background thread, and exposes read accessors for polling
(summary / detail / logs) built from the persisted report.
"""

from __future__ import annotations

import logging
import threading
from contextvars import copy_context
from typing import Any

from app.application.services import report_service
from app.application.services.status_service import MigrationReportStore
from app.application.use_cases.start_migration import StartMigrationUseCase
from app.core.exceptions import MigrationJobNotFoundError
from app.infrastructure.workspace.workspace_paths import WorkspacePaths

logger = logging.getLogger(__name__)


class MigrationExecutionPipeline:
    _active_jobs_lock = threading.Lock()
    _active_jobs: set[str] = set()

    def __init__(self, use_case: StartMigrationUseCase | None = None) -> None:
        self._use_case = use_case or StartMigrationUseCase()

    def is_job_running(self, job_id: str) -> bool:
        with self._active_jobs_lock:
            return job_id in self._active_jobs

    def start(
        self,
        job_id: str,
        request: dict[str, Any] | None,
        *,
        current_user_id: int | None = None,
        github_token: str | None = None,
    ) -> dict[str, Any]:
        """Validate + queue, launch the background run idempotently, return the initial result."""
        logger.info("[MIGRATION START] Request received for job %s", job_id)
        with self._active_jobs_lock:
            if job_id in self._active_jobs:
                logger.info("[MIGRATION START] Job %s is already active; returning current state", job_id)
                existing_report = MigrationReportStore(WorkspacePaths(job_id)).read()
                return report_service.build_result(existing_report or {"jobId": job_id, "status": "QUEUED"})

            self._active_jobs.add(job_id)

        try:
            report = self._use_case.prepare(job_id, request)
            logger.info("[MIGRATION START] Job %s accepted and prepared", job_id)
        except Exception:
            with self._active_jobs_lock:
                self._active_jobs.discard(job_id)
            raise

        def _worker_wrapper():
            logger.info("[MIGRATION WORKER] StartMigrationUseCase.run started for job %s", job_id)
            try:
                self._use_case.run(job_id, current_user_id, github_token)
                logger.info("[MIGRATION WORKER] StartMigrationUseCase.run completed for job %s", job_id)
            except Exception as exc:
                logger.exception("[MIGRATION WORKER] Fatal error in background migration worker for job %s: %s", job_id, exc)
                try:
                    store = MigrationReportStore(WorkspacePaths(job_id))
                    store.update(
                        status="FAILED",
                        currentStep="Migration worker failed",
                        errorMessage=str(exc),
                    )
                    store.append_logs([f"[FATAL] Background migration worker failed: {exc}"])
                except Exception:
                    pass
            finally:
                with self._active_jobs_lock:
                    self._active_jobs.discard(job_id)
                logger.info("[MIGRATION WORKER] Active worker lock released for job %s", job_id)

        context = copy_context()
        thread = threading.Thread(
            target=context.run,
            args=(_worker_wrapper,),
            name=f"migration-{job_id}",
            daemon=True,
        )
        logger.info("[MIGRATION START] Background worker created for job %s", job_id)
        thread.start()
        logger.info("[MIGRATION START] Background worker started for job %s", job_id)

        return report_service.build_result(report)

    def get_summary(self, job_id: str) -> dict[str, Any]:
        return report_service.build_summary(self._require_report(job_id))

    def get_detail(self, job_id: str) -> dict[str, Any]:
        return report_service.build_result(self._require_report(job_id))

    def get_logs(self, job_id: str) -> dict[str, Any]:
        return report_service.build_logs(self._require_report(job_id))

    def get_fossa(self, job_id: str) -> dict[str, Any]:
        return report_service.build_fossa(self._require_report(job_id))

    # -- helpers ------------------------------------------------------------- #

    @staticmethod
    def _require_report(job_id: str) -> dict[str, Any]:
        report = MigrationReportStore(WorkspacePaths(job_id)).read()
        if not report:
            raise MigrationJobNotFoundError()
        return report
