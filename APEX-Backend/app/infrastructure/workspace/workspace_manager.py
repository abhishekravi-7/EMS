"""Manages the on-disk workspace folders for a job.

Creates the job's directory tree and provides a clean ``original-repo`` target
for cloning. It never touches ``reports/`` contents (owned by the persistence
layer) beyond ensuring the folder exists.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.shared import file_utils
from app.shared.command_runner import resolve_executable, run_command

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Prepares and cleans the per-job workspace folders."""

    def __init__(self, paths: WorkspacePaths) -> None:
        self._paths = paths

    def ensure_job_dirs(self) -> None:
        """Ensure reports/ and logs/ exist for the job."""
        self._paths.reports_dir.mkdir(parents=True, exist_ok=True)
        self._paths.logs_dir.mkdir(parents=True, exist_ok=True)

    def prepare_original_repo_target(self) -> None:
        """Ensure ``original-repo`` is absent and its parent exists.

        If a previous clone is present it is removed so the fresh clone starts
        from a clean slate. ``git clone`` requires the target directory not to
        already exist.
        """
        original = self._paths.original_repo_dir
        if original.exists():
            logger.info("Removing existing original-repo before re-clone: %s", original.name)
            file_utils.remove_tree(original)
            if original.exists():
                try:
                    original.rmdir()
                except OSError:
                    logger.warning("original-repo directory could not be completely removed: %s", original)
        original.parent.mkdir(parents=True, exist_ok=True)

    def prepare_migrated_repo(self) -> None:
        """Create a fresh ``migrated-repo`` as a copy of ``original-repo``.

        The copy excludes ``.git`` so the migration engine works on a clean working tree
        and the eventual push starts from a single fresh commit. ``original-repo``
        is never modified.
        """
        original = self._paths.original_repo_dir
        migrated = self._paths.migrated_repo_dir
        logger.info("Preparing migrated-repo from original-repo (excluding .git)")
        file_utils.copy_tree(original, migrated, exclude={".git"})
        self._init_git_boundary(migrated)

    @staticmethod
    def _init_git_boundary(migrated: Path) -> None:
        """Give ``migrated-repo`` its own ``.git`` and initial commit so it is a valid repository root with HEAD ref.

        This ensures build plugins like ``git-commit-id-maven-plugin`` can resolve HEAD ref.
        """
        git = resolve_executable("git")
        if not git:
            return
        run_command([git, "-c", "core.longpaths=true", "init", "-q"], cwd=migrated, timeout=30)
        run_command([git, "-c", "core.longpaths=true", "config", "core.longpaths", "true"], cwd=migrated, timeout=30)
        run_command([git, "config", "user.name", "APEXEngine"], cwd=migrated, timeout=30)
        run_command([git, "config", "user.email", "engine@apex.internal"], cwd=migrated, timeout=30)
        run_command([git, "add", "-A"], cwd=migrated, timeout=30)
        run_command([git, "commit", "-m", "Initial baseline commit", "--no-verify"], cwd=migrated, timeout=30)
