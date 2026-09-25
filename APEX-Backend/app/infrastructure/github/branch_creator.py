"""Pushes the migrated code as a new branch to an existing repository.

Minimal support for the EXISTING_REPO_BRANCH destination mode. Best-effort:
requires the target token to have write access to the target repo.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import PushFailedError
from app.infrastructure.github.repo_pusher import RepoPusher
from app.shared.command_runner import resolve_executable, run_command

logger = logging.getLogger(__name__)


class BranchCreator:
    def __init__(self, pusher: RepoPusher | None = None) -> None:
        self._pusher = pusher or RepoPusher()

    def push_branch(
        self,
        repo_dir: Path,
        repo_https_url: str,
        branch: str,
        *,
        commit_message: str,
        token: str | None = None,
    ) -> str:
        """Commit ``repo_dir`` and push it as ``branch`` to an existing repo."""
        effective_token = (
            (token or "").strip()
            or (settings.github_token or "").strip()
            or (settings.github_target_token or "").strip()
        )
        if not effective_token:
            raise PushFailedError(
                "Unable to push to the destination repository. Please verify that the repository exists and that your PAT has write access."
            )

        git = resolve_executable("git") or "git"
        auth_url = self._pusher._build_auth_url(repo_https_url, effective_token)

        # Remove heavy build outputs before staging
        self._pusher._cleanup_build_artifacts(repo_dir)

        try:
            for args in (
                ["init", "-q"],
                ["config", "core.longpaths", "true"],
                ["config", "http.postBuffer", "524288000"],
                ["config", "http.version", "HTTP/1.1"],
                ["symbolic-ref", "HEAD", f"refs/heads/{branch}"],
                ["config", "user.name", settings.migration_commit_author_name],
                ["config", "user.email", settings.migration_commit_author_email],
                ["add", "-A"],
                ["commit", "-q", "-m", commit_message],
                ["remote", "add", "origin", auth_url],
                ["push", "-u", "origin", branch],
            ):
                cmd = [
                    git,
                    "-c",
                    "core.longpaths=true",
                    "-c",
                    "http.postBuffer=524288000",
                    "-c",
                    "http.version=HTTP/1.1",
                    *args,
                ]
                result = run_command(cmd, cwd=repo_dir, timeout=settings.git_clone_timeout_seconds)
                if not result.succeeded:
                    stderr = self._pusher._mask(result.stderr.strip())
                    logger.warning("git %s failed during branch push: %s", args[0], stderr)
                    lowered_err = stderr.lower()
                    if "filename too long" in lowered_err or "path too long" in lowered_err or "unable to index file" in lowered_err:
                        raise PushFailedError(
                            "Failed to push the migration branch because one or more file paths exceed the Windows path length limit. "
                            "Ensure Git long-path support is enabled ('git config --system core.longpaths true') or publish from a long-path supported environment."
                        )
                    if "401" in lowered_err or "bad credentials" in lowered_err or "invalid username or password" in lowered_err:
                        raise PushFailedError(
                            "Invalid GitHub token. Please verify that your PAT is valid and has not expired."
                        )
                    if "permission" in lowered_err or "403" in lowered_err or "access denied" in lowered_err or "write access" in lowered_err:
                        raise PushFailedError(
                            "Unable to push to the destination repository. Please verify that your PAT has write permission."
                        )
                    if "repository not found" in lowered_err or "not found" in lowered_err or "does not exist" in lowered_err:
                        raise PushFailedError(
                            "Unable to access the destination repository. Please verify that the repository exists and that your PAT has access."
                        )
                    if self._pusher._is_non_fast_forward(lowered_err):
                        raise PushFailedError(
                            "Failed to push branch: the branch already exists on the destination repository or has conflicting commits."
                        )
                    if "rpc failed" in lowered_err or "http 408" in lowered_err or "send-pack" in lowered_err or "curl 22" in lowered_err:
                        raise PushFailedError(
                            "Failed to push the migration branch due to network payload timeout (HTTP 408 send-pack). "
                            "The Git push payload exceeded buffer limits. Heavy build artifacts have been stripped for retries."
                        )
                    raise PushFailedError(
                        "Unable to access the destination repository. Please verify the repository URL and PAT permissions."
                    )
            return branch
        finally:
            try:
                run_command([git, "remote", "remove", "origin"], cwd=repo_dir, timeout=10)
            except Exception:
                pass
