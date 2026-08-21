"""Reads/writes the migration job's state (`migration-report.json`).

Single source of truth for a running migration's status. Persisted to disk
and mirrored to in-memory cache and database so it survives container restarts,
multi-instance routing in DigitalOcean, and background thread write contention.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from app.infrastructure.persistence.report_repository import load_report_from_db, save_report_to_db
from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.shared import json_utils
from app.shared import migration_log_sanitizer

logger = logging.getLogger(__name__)

# In-memory fallback cache across threads in the same process
_REPORT_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_LOCK = threading.Lock()


class MigrationReportStore:
    def __init__(self, paths: WorkspacePaths) -> None:
        self._paths = paths
        self._job_id = paths.job_id

    def read(self) -> dict[str, Any] | None:
        # 1. Read from disk (primary source)
        report = json_utils.read_json(self._paths.migration_report_path)
        if report:
            with _CACHE_LOCK:
                _REPORT_CACHE[self._job_id] = report
            return report

        # 2. Check in-memory cache (handles write-race conditions)
        with _CACHE_LOCK:
            cached = _REPORT_CACHE.get(self._job_id)
            if cached:
                return cached

        # 3. Check database (handles multi-container routing & container recreation in DigitalOcean)
        db_report = load_report_from_db(self._job_id)
        if db_report:
            with _CACHE_LOCK:
                _REPORT_CACHE[self._job_id] = db_report
            try:
                # Restore to disk
                json_utils.write_json(self._paths.migration_report_path, db_report)
            except Exception:
                pass
            return db_report

        return None

    def write(self, report: dict[str, Any]) -> None:
        with _CACHE_LOCK:
            _REPORT_CACHE[self._job_id] = report
        json_utils.write_json(self._paths.migration_report_path, report)
        save_report_to_db(self._job_id, report)

    def update(self, **fields: Any) -> dict[str, Any]:
        report = self.read() or {}
        report.update(fields)
        report["updatedAt"] = datetime.now(timezone.utc).isoformat()
        self.write(report)
        return report

    def append_logs(self, lines: list[str]) -> None:
        """Persist ``lines`` for this job's log stream.

        The *raw*, unmodified lines are mirrored to the human-readable
        ``migration.log`` file on disk for developer/backend troubleshooting
        (never served by any API). Only the sanitized, user-facing versions
        (see ``migration_log_sanitizer``) are stored in ``logLines`` -- the
        field every polling/API/report consumer reads from -- so raw
        migration-engine/Maven/Gradle internals never reach the Migration Log UI.
        """
        if not lines:
            return

        try:
            self._paths.logs_dir.mkdir(parents=True, exist_ok=True)
            with self._paths.migration_log_path.open("a", encoding="utf-8") as handle:
                for line in lines:
                    handle.write(line + "\n")
        except Exception:
            pass

        sanitized = migration_log_sanitizer.sanitize_lines(lines)
        if not sanitized:
            return
        report = self.read() or {}
        existing = report.get("logLines") or []
        report["logLines"] = existing + [line for line in sanitized if line not in existing]
        self.write(report)
