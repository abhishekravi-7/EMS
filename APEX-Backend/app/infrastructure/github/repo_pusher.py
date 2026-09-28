"""Pushes the migrated-repo to a target repository as a fresh single commit.

The token is embedded in the remote URL only for the push and is always masked
in logs. No source git history is carried over.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import PushFailedError
from app.shared.command_runner import CommandResult, resolve_executable, run_command

logger = logging.getLogger(__name__)

_TOKEN_MASK = "***"  # nosec B105


class RepoPusher:
    def push(
        self,
        repo_dir: Path,
        clone_url: str,
        *,
        commit_message: str,
        branch: str = "main",
        token: str | None = None,
        allow_force_update_existing: bool = False,
    ) -> str:
        """Init, commit, and push ``repo_dir`` to ``clone_url``. Returns the branch."""
        effective_token = (
            (token or "").strip()
            or (settings.github_token or "").strip()
            or (settings.github_target_token or "").strip()
        )
        if not effective_token:
            raise PushFailedError(
                "Unable to push to the destination repository. Please verify that the repository exists and that your PAT has write access."
            )

        auth_url = self._build_auth_url(clone_url, effective_token)

        # Extract owner/repo cleanly for structured diagnostic logging
        owner = ""
        repo = ""
        try:
            norm = self._normalize_repo_url(clone_url)
            parts = norm.split("/")
            if len(parts) >= 2:
                owner = parts[-2].split(":")[-1]
                repo = parts[-1]
        except Exception:
            pass

        # 1. Clean up heavy build output binaries to prevent bloated git push payloads
        self._cleanup_build_artifacts(repo_dir)

        try:
            # 2. Init fresh repo and configure git HTTP buffers
            self._git(repo_dir, ["init", "-q"])
            self._git(repo_dir, ["config", "core.longpaths", "true"])
            self._git(repo_dir, ["config", "http.postBuffer", "524288000"])
            self._git(repo_dir, ["config", "http.version", "HTTP/1.1"])
            self._git(repo_dir, ["symbolic-ref", "HEAD", f"refs/heads/{branch}"])
            self._git(repo_dir, ["config", "user.name", settings.migration_commit_author_name])
            self._git(repo_dir, ["config", "user.email", settings.migration_commit_author_email])
            self._git(repo_dir, ["add", "-A"])
            self._git(repo_dir, ["commit", "-q", "-m", commit_message])
            self._git(repo_dir, ["remote", "add", "origin", auth_url], sensitive=True)
            logger.info("Pushing migrated repo to %s", self._mask(clone_url))
            logger.info(
                "[GITHUB DESTINATION]\nowner=%s\nrepo=%s\nrepository_access=true\npush_started=true\npush_result=in_progress",
                owner,
                repo,
            )
            push_result = self._run_git(repo_dir, ["push", "-u", "origin", branch])
            if push_result.succeeded:
                logger.info(
                    "[GITHUB DESTINATION]\nowner=%s\nrepo=%s\nrepository_access=true\npush_started=true\npush_result=success",
                    owner,
                    repo,
                )
                return branch

            if allow_force_update_existing and self._is_non_fast_forward(push_result.stderr):
                logger.warning(
                    "Remote %s already has %s; retrying with --force-with-lease.",
                    self._mask(clone_url),
                    branch,
                )
                self._run_git(
                    repo_dir,
                    ["fetch", "origin", f"{branch}:refs/remotes/origin/{branch}", "--depth=1"],
                )
                force_result = self._run_git(
                    repo_dir,
                    ["push", "--force-with-lease", "-u", "origin", branch],
                )
                if force_result.succeeded:
                    logger.info(
                        "[GITHUB DESTINATION]\nowner=%s\nrepo=%s\nrepository_access=true\npush_started=true\npush_result=success",
                        owner,
                        repo,
                    )
                    return branch
                logger.error(
                    "[GITHUB DESTINATION]\nowner=%s\nrepo=%s\nrepository_access=true\npush_started=true\npush_result=failure",
                    owner,
                    repo,
                )
                self._raise_git_failure(force_result, action="push")

            logger.error(
                "[GITHUB DESTINATION]\nowner=%s\nrepo=%s\nrepository_access=true\npush_started=true\npush_result=failure",
                owner,
                repo,
            )
            self._raise_git_failure(push_result, action="push")
            return branch
        finally:
            try:
                self._run_git(repo_dir, ["remote", "remove", "origin"])
            except Exception:
                pass

    # -- helpers ------------------------------------------------------------- #

    def _cleanup_build_artifacts(self, repo_dir: Path) -> None:
        """Remove heavy compiled build outputs before git staging to keep push payload small."""
        dirs_to_remove = ["target", "build", ".gradle", ".idea", ".settings", "bin", "out"]
        for dir_name in dirs_to_remove:
            target_path = repo_dir / dir_name
            if target_path.exists():
                try:
                    if target_path.is_dir():
                        shutil.rmtree(target_path, ignore_errors=True)
                    else:
                        target_path.unlink(missing_ok=True)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not remove build directory %s before push: %s", target_path, exc)

    def _git(self, cwd: Path, args: list[str], *, sensitive: bool = False) -> CommandResult:
        result = self._run_git(cwd, args)
        if not result.succeeded:
            self._raise_git_failure(result, action="push" if sensitive else " ".join(args[:1]))
        return result

    def _run_git(self, cwd: Path, args: list[str]) -> CommandResult:
        git = resolve_executable("git") or "git"
        # Always inject longpaths and 500MB HTTP postBuffer flags
        command = [
            git,
            "-c",
            "core.longpaths=true",
            "-c",
            "http.postBuffer=524288000",
            "-c",
            "http.version=HTTP/1.1",
            *args,
        ]
        return run_command(command, cwd=cwd, timeout=settings.git_clone_timeout_seconds)

    def _raise_git_failure(self, result: CommandResult, *, action: str) -> None:
        stderr = self._mask(result.stderr.strip())
        logger.warning("git %s failed: %s", action, stderr)
        lowered_err = stderr.lower()
        if "filename too long" in lowered_err or "path too long" in lowered_err or "unable to index file" in lowered_err:
            raise PushFailedError(
                "DESTINATION_REPO_PUSH_FAILED: Failed to publish the migrated repository because one or more file paths exceed the Windows path length limit. "
                "Ensure Git long-path support is enabled ('git config --system core.longpaths true') or publish from a long-path supported environment."
            )
        if "401" in lowered_err or "bad credentials" in lowered_err or "invalid username or password" in lowered_err:
            raise PushFailedError(
                "DESTINATION_REPO_UNAUTHORIZED: Invalid GitHub token. Please verify that your PAT is valid and has not expired."
            )
        if "permission" in lowered_err or "403" in lowered_err or "access denied" in lowered_err or "write access" in lowered_err:
            raise PushFailedError(
                "DESTINATION_REPO_FORBIDDEN: Unable to push to the destination repository. Please verify that your PAT has write permission."
            )
        if "repository not found" in lowered_err or "not found" in lowered_err or "does not exist" in lowered_err:
            raise PushFailedError(
                "DESTINATION_REPO_NOT_FOUND: Unable to access the destination repository. Please verify that the repository exists and that your PAT has access."
            )
        if self._is_non_fast_forward(lowered_err):
            raise PushFailedError(
                "DESTINATION_REPO_PUSH_FAILED: Failed to push: the branch already exists on the destination repository or has conflicting commits."
            )
        if "rpc failed" in lowered_err or "http 408" in lowered_err or "send-pack" in lowered_err or "curl 22" in lowered_err:
            raise PushFailedError(
                "DESTINATION_REPO_PUSH_FAILED: Failed to publish the migrated repository due to network payload timeout (HTTP 408 send-pack). "
                "The Git push payload exceeded buffer limits. Heavy build artifacts have been stripped for retries."
            )
        raise PushFailedError(
            "DESTINATION_REPO_PUSH_FAILED: Unable to access the destination repository. Please verify the repository URL and PAT permissions."
        )

    @staticmethod
    def _is_non_fast_forward(stderr: str) -> bool:
        lowered = (stderr or "").lower()
        return "fetch first" in lowered or "non-fast-forward" in lowered or "[rejected]" in lowered

    @staticmethod
    def _normalize_repo_url(url: str) -> str:
        """Strip trailing slashes, spaces, and duplicate .git suffixes cleanly."""
        cleaned = (url or "").strip().rstrip("/\\")
        if cleaned.endswith(".git"):
            cleaned = cleaned[:-4].rstrip("/\\")
        return cleaned

    @staticmethod
    def _build_auth_url(https_url: str, token: str | None = None) -> str:
        base_url = RepoPusher._normalize_repo_url(https_url)
        git_url = f"{base_url}.git"
        if token and token.strip():
            tok = token.strip()
            if git_url.startswith("https://"):
                return git_url.replace("https://", f"https://x-access-token:{tok}@", 1)
            if git_url.startswith("http://"):
                return git_url.replace("http://", f"http://x-access-token:{tok}@", 1)
        return git_url

    @staticmethod
    def _mask(text: str) -> str:
        if not text:
            return text
        return re.sub(r"(https?://)[^@/\s]+@", rf"\1{_TOKEN_MASK}@", text)
