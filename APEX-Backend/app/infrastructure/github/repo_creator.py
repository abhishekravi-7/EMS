"""Creates the target repository under the configured owner (JavaAPEX)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import settings
from app.core.exceptions import PushFailedError
from app.infrastructure.github.github_client import GithubClient
from app.infrastructure.github.profile_resolver import ProfileResolver, TargetProfile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CreatedRepo:
    owner: str
    name: str
    html_url: str
    clone_url: str


class RepoCreator:
    def __init__(
        self,
        github_client: GithubClient | None = None,
        profile_resolver: ProfileResolver | None = None,
    ) -> None:
        self._github = github_client or GithubClient()
        self._profiles = profile_resolver or ProfileResolver(self._github)

    def create(
        self,
        repo_name: str,
        *,
        owner: str | None = None,
        host: str | None = None,
        private: bool = False,
        description: str = "Migrated with the Java APEX migration engine",
    ) -> CreatedRepo:
        token = (settings.github_target_token or "").strip()
        if not token:
            raise PushFailedError(
                "No target GitHub token configured. Set GITHUB_TARGET_TOKEN."
            )

        profile: TargetProfile = self._profiles.resolve(owner=owner, host=host)
        logger.info(
            "Creating repo %s/%s (%s)",
            profile.owner,
            repo_name,
            "org" if profile.is_org else "user",
        )

        response = self._github.create_repository_sync(
            profile.owner,
            repo_name,
            token,
            is_org=profile.is_org,
            private=private,
            description=description,
        )

        if response.status_code in (200, 201) and isinstance(response.data, dict):
            return self._created_repo_from_response(profile, repo_name, response.data)

        if response.status_code == 422:
            gh_message = ""
            if isinstance(response.data, dict):
                gh_message = str(response.data.get("message", ""))
                for err in response.data.get("errors", []):
                    if isinstance(err, dict) and "already exists" in str(err.get("message", "")).lower():
                        gh_message = "already exists"
                        break
            if "already exists" in gh_message.lower():
                # Try fetching existing repo metadata; fall back to constructing URL directly.
                existing = self._github.get_repository_sync(profile.owner, repo_name, token)
                if existing.status_code == 200 and isinstance(existing.data, dict):
                    logger.info("Target repo %s/%s already exists; reusing it.", profile.owner, repo_name)
                    return self._created_repo_from_response(profile, repo_name, existing.data)
                # GET failed (private repo or token scope) — construct the URL directly.
                logger.info(
                    "Target repo %s/%s already exists (GET returned %s); reusing with constructed URL.",
                    profile.owner, repo_name, existing.status_code,
                )
                return CreatedRepo(
                    owner=profile.owner,
                    name=repo_name,
                    html_url=f"https://{profile.host}/{profile.owner}/{repo_name}",
                    clone_url=f"https://{profile.host}/{profile.owner}/{repo_name}.git",
                )

        # Log diagnostic info (never log the token value itself)
        gh_message = ""
        if isinstance(response.data, dict):
            gh_message = str(response.data.get("message", ""))
            errors = response.data.get("errors", [])
            if errors:
                gh_message += f" | errors: {errors}"
        logger.error(
            "GitHub repo creation failed | status=%s | owner=%s | repo=%s | is_org=%s "
            "| token_present=%s | token_len=%d | github_message=%r",
            response.status_code,
            profile.owner,
            repo_name,
            profile.is_org,
            bool(token),
            len(token),
            gh_message,
        )

        raise PushFailedError(self._error_message(response.status_code, response.data))

    @staticmethod
    def _created_repo_from_response(
        profile: TargetProfile,
        repo_name: str,
        data: dict,
    ) -> CreatedRepo:
        return CreatedRepo(
            owner=profile.owner,
            name=str(data.get("name", repo_name)),
            html_url=str(data.get("html_url", f"https://{profile.host}/{profile.owner}/{repo_name}")),
            clone_url=str(data.get("clone_url", f"https://{profile.host}/{profile.owner}/{repo_name}.git")),
        )

    @staticmethod
    def _error_message(status_code: int, data: dict | None) -> str:
        detail = ""
        if isinstance(data, dict):
            detail = str(data.get("message", ""))
        if status_code == 401:
            return (
                "Target GitHub token is invalid or expired (HTTP 401). "
                "Regenerate GITHUB_TARGET_TOKEN at github.com/settings/tokens "
                "with 'repo' scope, then restart the backend."
            )
        if status_code == 403:
            return (
                "Target token lacks permission to create repositories (HTTP 403). "
                "Ensure the token has 'repo' scope and — if JavaAPEX is an org — "
                "that the token is approved for that organization (SSO / third-party access)."
            )
        if status_code == 404:
            return (
                "Target owner not found, or the token cannot access it (HTTP 404). "
                f"Verify GITHUB_TARGET_OWNER='{data.get('message', 'JavaAPEX') if isinstance(data, dict) else 'JavaAPEX'}' "
                "exists and the token has access to it."
            )
        if status_code == 422 and "already exists" in detail.lower():
            return "A repository with this name already exists under the target owner."
        if detail:
            return f"Could not create the target repository (HTTP {status_code}): {detail}"
        return f"Could not create the target repository (HTTP {status_code})."
