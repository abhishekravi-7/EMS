"""Reads/writes the migration job's state (`migration-report.json`).

Single source of truth for a running migration's status. Persisted to disk
and mirrored to in-memory cache and database so it survives container restarts,
multi-instance routing in DigitalOcean, and background thread write contention.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from app.infrastructure.persistence.report_repository import load_report_from_db, save_report_to_db
from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.shared import json_utils
from app.shared import migration_log_sanitizer

logger = logging.getLogger(__name__)

# In-memory fallback cache across threads in the same process
_REPORT_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_LOCK = threading.RLock()
_LAST_DB_FLUSH: dict[str, float] = {}


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

        # 4. Fallback: synthesize initial report if connect or discovery report exists
        try:
            from app.infrastructure.persistence.job_repository import JobRepository
            job_repo = JobRepository()
            connect = job_repo.read_connect_report(self._job_id)
            discovery = job_repo.read_discovery_report(self._job_id)
            if connect or discovery:
                initial_report = {
                    "jobId": self._job_id,
                    "status": "QUEUED",
                    "currentStep": "QUEUED",
                    "progressPercent": 0,
                    "sourceRepoUrl": (connect or {}).get("repoUrl") or (discovery or {}).get("repoUrl") or "",
                    "sourceJavaVersion": (discovery or {}).get("currentJavaVersion") or "",
                    "targetJavaVersion": "",
                    "buildTool": ((discovery or {}).get("buildTool") or "").upper(),
                    "conversionTypes": [],
                    "options": {},
                    "runSonar": False,
                    "runFossa": False,
                    "runTests": False,
                    "destination": {},
                    "targetRepo": None,
                    "startedAt": datetime.now(timezone.utc).isoformat(),
                    "completedAt": None,
                    "errorMessage": None,
                    "filesModified": 0,
                    "recipes": [],
                    "usedFallback": False,
                    "logLines": ["Job initialized. Waiting for migration start..."],
                }
                with _CACHE_LOCK:
                    _REPORT_CACHE[self._job_id] = initial_report
                return initial_report
        except Exception:
            pass

        return None

    def write(self, report: dict[str, Any], force_db: bool = False) -> None:
        with _CACHE_LOCK:
            _REPORT_CACHE[self._job_id] = report
        try:
            json_utils.write_json(self._paths.migration_report_path, report)
        except Exception as err:
            logger.debug("Non-fatal: failed writing migration report to disk for %s: %s", self._job_id, err)

        # Flush to database when terminal or force_db or throttled >= 1.5s
        status = report.get("status")
        is_terminal = status in ("COMPLETED", "FAILED", "ERROR")
        now = time.time()
        last_db = _LAST_DB_FLUSH.get(self._job_id, 0.0)
        if force_db or is_terminal or (now - last_db) >= 1.5:
            _LAST_DB_FLUSH[self._job_id] = now
            try:
                save_report_to_db(self._job_id, report)
            except Exception as db_err:
                logger.debug("Non-fatal: failed saving report to db for %s: %s", self._job_id, db_err)

    def update(self, **fields: Any) -> dict[str, Any]:
        report = self.read() or {}
        report.update(fields)
        report["updatedAt"] = datetime.now(timezone.utc).isoformat()
        self.write(report, force_db=("status" in fields or "currentStep" in fields))
        return report

    def append_logs(self, lines: list[str]) -> None:
        """Persist ``lines`` for this job's log stream."""
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
        self.write(report, force_db=False)

