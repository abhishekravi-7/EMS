"""Determines repository existence, visibility, and access.

This is the decision engine for the Connect stage. It uses the low-level
:class:`GithubClient` and turns HTTP results into a clean
:class:`RepoAccessResult` — or raises a domain error with a user-friendly
message.

Flow (per product spec):
  1. Parse the URL into owner/repo (done by the caller / value object).
  2. Try GitHub without a token.
       - 200            -> repo exists; read visibility from ``private`` flag.
       - 404 + no token -> ambiguous (private or missing); ask for a token.
       - 404 + token    -> retry with the token below.
  3. If a token is provided, retry.
       - 200 -> access granted; visibility from ``private`` flag.
       - 401 -> token is invalid.
       - 404 -> not found or the token lacks access.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import (
    GithubServiceError,
    RepositoryAccessDeniedError,
    RepositoryNotFoundError,
)
from app.infrastructure.github.github_client import GithubClient

VISIBILITY_PUBLIC = "PUBLIC"
VISIBILITY_PRIVATE = "PRIVATE"
ACCESS_GRANTED = "ACCESS_GRANTED"


@dataclass(frozen=True)
class RepoAccessResult:
    """Outcome of a successful access check."""

    owner: str
    repo_name: str
    visibility: str  # VISIBILITY_PUBLIC | VISIBILITY_PRIVATE
    access_status: str  # ACCESS_GRANTED

    @property
    def is_private(self) -> bool:
        return self.visibility == VISIBILITY_PRIVATE


class RepoAccessChecker:
    """Detects public/private/access for a GitHub repository."""

    def __init__(self, github_client: GithubClient | None = None) -> None:
        self._github = github_client or GithubClient()

    async def check(
        self,
        owner: str,
        repo: str,
        token: str | None = None,
    ) -> RepoAccessResult:
        normalized_token = (token or "").strip() or None

        # Step 0: verify if the GitHub user or organization exists.
        owner_status = await self._github.get_user_or_org(owner, token=normalized_token)
        if owner_status == 404:
            raise RepositoryNotFoundError(
                f"Repository not found. The GitHub user or organization '{owner}' does not exist."
            )
        if owner_status == 401 and normalized_token:
            raise RepositoryAccessDeniedError(
                "Invalid GitHub personal access token."
            )

        # Step 1: if a token is provided, verify repository access directly.
        if normalized_token is not None:
            authenticated = await self._github.get_repository(owner, repo, token=normalized_token)

            if authenticated.status_code == 200:
                return self._granted(owner, repo, authenticated.data)

            if self._is_rate_limited(authenticated):
                raise GithubServiceError(
                    "GitHub's API rate limit was reached. Please wait a minute and try again."
                )

            if authenticated.status_code == 401:
                raise RepositoryAccessDeniedError(
                    "Invalid GitHub personal access token."
                )

            if authenticated.status_code in (403, 404):
                raise RepositoryNotFoundError(
                    "Repository not found, or your token does not have access. "
                    "Please check the URL and the token's permissions."
                )

            raise GithubServiceError()

        # Step 2: anonymous check when no token was provided.
        anonymous = await self._github.get_repository(owner, repo, token=None)

        if anonymous.status_code == 200:
            return self._granted(owner, repo, anonymous.data)

        # A rate-limit 403 is a transient condition — NOT a private repo.
        if self._is_rate_limited(anonymous):
            raise GithubServiceError(
                "GitHub's API rate limit was reached. Please wait a minute and "
                "try again. Adding a GitHub token raises the limit."
            )

        if anonymous.status_code in (401, 403, 404):
            raise RepositoryAccessDeniedError(
                "Repository is private or was not found. "
                "Please provide a valid GitHub personal access token (PAT) with repo scope, or check the URL."
            )

        raise GithubServiceError()

    @staticmethod
    def _is_rate_limited(response) -> bool:
        """True when a 403 is caused by GitHub API rate limiting."""
        if response.status_code != 403:
            return False
        message = ""
        if isinstance(response.data, dict):
            message = str(response.data.get("message", ""))
        return "rate limit" in message.lower()

    def _granted(self, owner: str, repo: str, data: dict | None) -> RepoAccessResult:
        is_private = bool(data.get("private")) if isinstance(data, dict) else False
        # Prefer the canonical owner/name from GitHub when available.
        resolved_owner = owner
        resolved_repo = repo
        if isinstance(data, dict):
            owner_block = data.get("owner")
            if isinstance(owner_block, dict) and owner_block.get("login"):
                resolved_owner = str(owner_block["login"])
            if data.get("name"):
                resolved_repo = str(data["name"])

        return RepoAccessResult(
            owner=resolved_owner,
            repo_name=resolved_repo,
            visibility=VISIBILITY_PRIVATE if is_private else VISIBILITY_PUBLIC,
            access_status=ACCESS_GRANTED,
        )
