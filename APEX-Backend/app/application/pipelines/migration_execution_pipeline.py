"""Migration Execution pipeline.

Orchestrates Start Migration: validates + queues the job, runs the long
migration in a background thread, and exposes read accessors for polling
(summary / detail / logs) built from the persisted report.
"""

from __future__ import annotations

import threading
from contextvars import copy_context
from typing import Any

from app.application.services import report_service
from app.application.services.status_service import MigrationReportStore
from app.application.use_cases.start_migration import StartMigrationUseCase
from app.core.exceptions import MigrationJobNotFoundError
from app.infrastructure.workspace.workspace_paths import WorkspacePaths


class MigrationExecutionPipeline:
    def __init__(self, use_case: StartMigrationUseCase | None = None) -> None:
        self._use_case = use_case or StartMigrationUseCase()

    def start(
        self,
        job_id: str,
        request: dict[str, Any] | None,
        *,
        current_user_id: int | None = None,
        github_token: str | None = None,
    ) -> dict[str, Any]:
        """Validate + queue, launch the background run, return the initial result."""
        report = self._use_case.prepare(job_id, request)
        context = copy_context()

        thread = threading.Thread(
            target=context.run,
            args=(self._use_case.run, job_id, current_user_id, github_token),
            name=f"migration-{job_id}",
            daemon=True,
        )
        thread.start()

        return report_service.build_result(report)

    def get_summary(self, job_id: str) -> dict[str, Any]:
        return report_service.build_summary(self._require_report(job_id))

    def get_detail(self, job_id: str) -> dict[str, Any]:
        return report_service.build_result(self._require_report(job_id))

    def get_logs(self, job_id: str) -> dict[str, Any]:
        return report_service.build_logs(self._require_report(job_id))

    def get_fossa(self, job_id: str) -> dict[str, Any]:
        return report_service.build_fossa(self._require_report(job_id))

    def get_report_details(self, job_id: str, detail_type: str) -> dict[str, Any]:
        return report_service.build_report_details(self._require_report(job_id), detail_type)

    # -- helpers ------------------------------------------------------------- #

    @staticmethod
    def _require_report(job_id: str) -> dict[str, Any]:
        store = MigrationReportStore(WorkspacePaths(job_id))
        report = store.read()
        if not report:
            raise MigrationJobNotFoundError()

        # If report is marked 'running' but the worker thread is dead (e.g. server reload/restart)
        if str(report.get("status", "")).lower() == "running":
            is_alive = any(
                t.name == f"migration-{job_id}" and t.is_alive()
                for t in threading.enumerate()
            )
            if not is_alive:
                store.update(
                    status="FAILED",
                    errorMessage="Migration was interrupted due to a backend server restart or process termination. Please start a new migration run.",
                )
                report = store.read() or report

        return report
