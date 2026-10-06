"""Connect Repository use case.

Responsibilities:
  * Validate & parse the GitHub repository URL.
  * Delegate public/private/access detection to the access checker.
  * Create a unique job id.
  * Persist a ``connect-report.json`` for the job.

It performs NO cloning, migration, or discovery work — that belongs to later
stages of the pipeline.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.core.exceptions import InvalidRepositoryUrlError
from app.infrastructure.github.repo_access_checker import RepoAccessChecker
from app.infrastructure.persistence.job_repository import JobRepository

logger = logging.getLogger("connect")

# Accepts:
#   https://github.com/owner/repo        (with or without .git / trailing slash)
#   http://github.com/owner/repo
#   github.com/owner/repo
#   www.github.com/owner/repo
_GITHUB_URL_PATTERN = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/"
    r"(?P<owner>[^/\s]+)/(?P<repo>[^/\s?#]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedRepo:
    owner: str
    repo: str


@dataclass(frozen=True)
class ConnectResult:
    """What the use case returns to the pipeline/controller."""

    job_id: str
    repo_url: str
    owner: str
    repo_name: str
    repo_visibility: str
    access_status: str
    message: str
    created_at: str
    is_already_migrated: bool = False
    migration_state: dict | None = None


def parse_github_url(repo_url: str) -> ParsedRepo:
    """Extract ``owner`` and ``repo`` from a GitHub URL.

    Raises :class:`InvalidRepositoryUrlError` when the URL is not a recognizable
    GitHub repository reference.
    """
    if not repo_url or not repo_url.strip():
        raise InvalidRepositoryUrlError()

    match = _GITHUB_URL_PATTERN.match(repo_url.strip())
    if not match:
        raise InvalidRepositoryUrlError()

    owner = match.group("owner").strip()
    repo = match.group("repo").strip()
    # Strip a trailing ``.git`` suffix if present.
    if repo.lower().endswith(".git"):
        repo = repo[:-4]

    if not owner or not repo:
        raise InvalidRepositoryUrlError()

    return ParsedRepo(owner=owner, repo=repo)


class ConnectRepositoryUseCase:
    def __init__(
        self,
        access_checker: RepoAccessChecker | None = None,
        job_repository: JobRepository | None = None,
    ) -> None:
        self._access_checker = access_checker or RepoAccessChecker()
        self._job_repository = job_repository or JobRepository()

    @staticmethod
    def _new_job_id() -> str:
        return f"job_{uuid4().hex[:12]}"

    @staticmethod
    def _success_message(is_private: bool) -> str:
        if is_private:
            return "Private repository access verified successfully."
    async def execute(self, repo_url: str, github_token: str | None) -> ConnectResult:
        # 1. Validate + parse the URL (raises InvalidRepositoryUrlError).
        t_val = time.perf_counter()
        parsed = parse_github_url(repo_url)
        logger.info("[CONNECT VALIDATION] - Owner: %s - Repo: %s", parsed.owner, parsed.repo)

        # 2. Detect visibility / access (raises NotFound / AccessDenied / ServiceError).
        access = await self._access_checker.check(
            parsed.owner, parsed.repo, token=github_token
        )
        logger.info(
            "[CONNECT ACCESS CHECK] - Owner: %s - Repo: %s - Visibility: %s - Access: %s",
            access.owner,
            access.repo_name,
            access.visibility,
            access.access_status,
        )

        # 2.5 Check if it's already a migrated repository (Resume Flow)
        is_already_migrated = False
        migration_state = None
        try:
            from app.infrastructure.github.github_client import GithubClient
            gh_client = GithubClient()
            content_resp = await gh_client.get_contents(access.owner, access.repo_name, ".apex-migration-state.json", token=github_token)
            if content_resp.status_code == 200 and content_resp.data and isinstance(content_resp.data, dict):
                import base64
                import json
                content_b64 = content_resp.data.get("content", "")
                if content_b64:
                    decoded = base64.b64decode(content_b64).decode("utf-8")
                    migration_state = json.loads(decoded)
                    is_already_migrated = True
                    logger.info("[CONNECT] Detected already migrated repository: %s", migration_state.get("job_id"))
        except Exception as e:
            logger.debug("[CONNECT] No migration state marker found or failed to parse: %s", e)

        # 3. Create a unique job id (or reuse if already migrated).
        job_id = migration_state.get("job_id") if is_already_migrated and migration_state.get("job_id") else self._new_job_id()
        created_at = datetime.now(timezone.utc).isoformat()

        # 4. Persist the connect report locally.
        report = {
            "jobId": job_id,
            "repoUrl": repo_url,
            "owner": access.owner,
            "repoName": access.repo_name,
            "repoVisibility": access.visibility,
            "accessStatus": access.access_status,
            "createdAt": created_at,
            "isAlreadyMigrated": is_already_migrated,
            "migrationState": migration_state,
        }
        self._job_repository.save_connect_report(job_id, report)
        logger.info("[CONNECT REPORT PERSISTED] - JobID: %s", job_id)

        return ConnectResult(
            job_id=job_id,
            repo_url=repo_url,
            owner=access.owner,
            repo_name=access.repo_name,
            repo_visibility=access.visibility,
            access_status=access.access_status,
            message="Already Migrated Repository detected." if is_already_migrated else self._success_message(access.is_private),
            created_at=created_at,
            is_already_migrated=is_already_migrated,
            migration_state=migration_state,
        )
