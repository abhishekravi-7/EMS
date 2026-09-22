"""Configures file-watcher exclusions for Uvicorn and WatchFiles.

Ensures that when running with ``uvicorn --reload`` (even without explicit
``--reload-dir app`` or ``--reload-exclude`` CLI flags), generated repository
files under ``storage/migration-jobs/...`` never trigger development server reloads.
Application source code files (e.g. ``app/**/*.py``) continue to trigger normal reloads.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

EXCLUDED_DIR_NAMES = {
    "storage",
    "migration-jobs",
    "support-tickets",
    "original-repo",
    "migrated-repo",
    "reports",
    "workspace",
    "logs",
    ".gradle-cache",
    "frontend-dist",
}


def is_path_excluded(path: Path | str) -> bool:
    """Return True if path should be ignored by the file watcher."""
    try:
        p = Path(path) if isinstance(path, str) else path
        p_str = str(p).replace("\\", "/").lower()
        parts = {part.lower() for part in p.parts}
        if bool(parts.intersection(EXCLUDED_DIR_NAMES)):
            return True
        if "/storage/" in p_str or p_str.startswith("storage/") or "/logs/" in p_str:
            return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Error checking path exclusion for %s: %s", path, exc)
    return False


def configure_watcher_exclusions() -> None:
    """Install exclusions in watchfiles and uvicorn reloader subsystems."""
    # 1. Patch watchfiles DefaultFilter directory exclusions if watchfiles is installed
    try:
        import watchfiles.filters as wf

        if hasattr(wf, "DefaultFilter"):
            current_ignore_dirs = tuple(getattr(wf.DefaultFilter, "ignore_dirs", ()))
            new_dirs = tuple(EXCLUDED_DIR_NAMES.union(current_ignore_dirs))
            wf.DefaultFilter.ignore_dirs = new_dirs

            orig_default_call = wf.DefaultFilter.__call__

            def safe_default_call(self: wf.DefaultFilter, change: wf.Change, raw_path: str) -> bool:
                if is_path_excluded(raw_path):
                    return False
                return orig_default_call(self, change, raw_path)

            wf.DefaultFilter.__call__ = safe_default_call  # type: ignore[method-assign]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Error configuring watchfiles exclusions: %s", exc)

    # 2. Patch Uvicorn's WatchFilesReload FileFilter
    try:
        from uvicorn.supervisors.watchfilesreload import FileFilter

        orig_file_filter_call = FileFilter.__call__

        def safe_file_filter_call(self: FileFilter, path: Path) -> bool:
            if is_path_excluded(path):
                return False
            return orig_file_filter_call(self, path)

        FileFilter.__call__ = safe_file_filter_call  # type: ignore[method-assign]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Error configuring uvicorn file filter: %s", exc)

    # 3. Patch Uvicorn's StatReload iter_py_files fallback
    try:
        from uvicorn.supervisors.statreload import StatReload

        orig_iter_py = StatReload.iter_py_files

        def safe_iter_py(self: StatReload):  # type: ignore[no-untyped-def]
            for p in orig_iter_py(self):
                if not is_path_excluded(p):
                    yield p

        StatReload.iter_py_files = safe_iter_py  # type: ignore[method-assign]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Error configuring uvicorn stat reload: %s", exc)


# Automatically configure watcher exclusions upon import
configure_watcher_exclusions()
