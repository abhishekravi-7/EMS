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

    @staticmethod
    def clean_repo_name(repo_name: str | None) -> str:
        """Extracts the simple repository name if a full URL, git remote, or path was provided."""
        if not repo_name:
            return "repo"
        import re
        cleaned = str(repo_name).strip().rstrip("/\\")
        if cleaned.endswith(".git"):
            cleaned = cleaned[:-4]
        if "://" in cleaned:
            cleaned = cleaned.split("://", 1)[1]
        if ":" in cleaned and "/" not in cleaned.split(":", 1)[0]:
            cleaned = cleaned.split(":", 1)[1]
        if "/" in cleaned or "\\" in cleaned:
            parts = [p for p in re.split(r"[/\\]+", cleaned) if p]
            if parts:
                cleaned = parts[-1]
        cleaned = cleaned.strip()
        return cleaned or "repo"

    def create(
        self,
        repo_name: str,
        *,
        owner: str | None = None,
        host: str | None = None,
        token: str | None = None,
        private: bool = False,
        description: str = "Migrated with the Java APEX migration engine",
    ) -> CreatedRepo:
        effective_token = (
            (token or "").strip()
            or (settings.github_target_token or "").strip()
            or (settings.github_token or "").strip()
        )
        if not effective_token:
            raise PushFailedError(
                "DESTINATION_REPO_UNAUTHORIZED: No target GitHub token configured. Set GITHUB_TARGET_TOKEN or provide a PAT."
            )
        token = effective_token

        repo_name = self.clean_repo_name(repo_name)
        profile: TargetProfile = self._profiles.resolve(owner=owner, host=host, token=token)
        
        auth_user = None
        try:
            auth_user = self._github.get_authenticated_user_sync(token=token)
        except Exception:
            auth_user = None
        auth_login = auth_user.get("login", "") if isinstance(auth_user, dict) else ""

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

        # If org creation returned 404, fallback to user repo creation
        if response.status_code == 404 and profile.is_org:
            logger.info("Org creation returned 404 for %s; attempting user repository creation.", profile.owner)
            fallback_response = self._github.create_repository_sync(
                profile.owner,
                repo_name,
                token,
                is_org=False,
                private=private,
                description=description,
            )
            if fallback_response.status_code in (200, 201):
                response = fallback_response

        repo_created = False
        created_repo: CreatedRepo | None = None

        if response.status_code in (200, 201) and isinstance(response.data, dict):
            repo_created = True
            created_repo = self._created_repo_from_response(profile, repo_name, response.data)

        elif response.status_code == 422:
            gh_message = ""
            if isinstance(response.data, dict):
                gh_message = str(response.data.get("message", ""))
                for err in response.data.get("errors", []):
                    if isinstance(err, dict) and "already exists" in str(err.get("message", "")).lower():
                        gh_message = "already exists"
                        break
            if "already exists" in gh_message.lower():
                existing = self._github.get_repository_sync(profile.owner, repo_name, token)
                if existing.status_code == 200 and isinstance(existing.data, dict):
                    logger.info("Target repo %s/%s already exists; reusing it.", profile.owner, repo_name)
                    created_repo = self._created_repo_from_response(profile, repo_name, existing.data)
                elif existing.status_code == 401:
                    raise PushFailedError("DESTINATION_REPO_UNAUTHORIZED: Destination PAT is invalid or expired (HTTP 401).")
                elif existing.status_code == 403:
                    raise PushFailedError("DESTINATION_REPO_FORBIDDEN: Destination PAT lacks write permission to the existing repository (HTTP 403).")
                elif existing.status_code == 404:
                    raise PushFailedError(f"DESTINATION_REPO_NOT_FOUND: Target repo {profile.owner}/{repo_name} not found or token has no access (HTTP 404).")
                else:
                    logger.info(
                        "Target repo %s/%s already exists (GET returned %s); reusing with constructed URL.",
                        profile.owner, repo_name, existing.status_code,
                    )
                    created_repo = CreatedRepo(
                        owner=profile.owner,
                        name=repo_name,
                        html_url=f"https://{profile.host}/{profile.owner}/{repo_name}",
                        clone_url=f"https://{profile.host}/{profile.owner}/{repo_name}.git",
                    )
            else:
                raise PushFailedError(self._error_message(response.status_code, response.data, profile.owner))

        else:
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
            raise PushFailedError(self._error_message(response.status_code, response.data, profile.owner))

        # Immediately verify access using the SAME destination token
        access_check = self._github.get_repository_sync(created_repo.owner, created_repo.name, token)
        repo_accessible = access_check.status_code == 200

        if access_check.status_code == 401:
            logger.error(
                "[GITHUB DESTINATION]\nowner=%s\nrepo=%s\nauthenticated_user=%s\nrepository_access=false\nrepository_created=%s\npush_started=false\npush_result=failure",
                created_repo.owner,
                created_repo.name,
                auth_login or "<unknown>",
                "true" if repo_created else "false",
            )
            raise PushFailedError("DESTINATION_REPO_UNAUTHORIZED: Destination PAT is invalid or expired (HTTP 401).")
        elif access_check.status_code == 403:
            logger.error(
                "[GITHUB DESTINATION]\nowner=%s\nrepo=%s\nauthenticated_user=%s\nrepository_access=false\nrepository_created=%s\npush_started=false\npush_result=failure",
                created_repo.owner,
                created_repo.name,
                auth_login or "<unknown>",
                "true" if repo_created else "false",
            )
            raise PushFailedError("DESTINATION_REPO_FORBIDDEN: Destination PAT lacks permission to access the destination repository (HTTP 403).")
        elif access_check.status_code == 404:
            logger.error(
                "[GITHUB DESTINATION]\nowner=%s\nrepo=%s\nauthenticated_user=%s\nrepository_access=false\nrepository_created=%s\npush_started=false\npush_result=failure",
                created_repo.owner,
                created_repo.name,
                auth_login or "<unknown>",
                "true" if repo_created else "false",
            )
            raise PushFailedError(f"DESTINATION_REPO_NOT_FOUND: Unable to access destination repository {created_repo.owner}/{created_repo.name} (HTTP 404).")
        elif not repo_accessible:
            logger.error(
                "[GITHUB DESTINATION]\nowner=%s\nrepo=%s\nauthenticated_user=%s\nrepository_access=false\nrepository_created=%s\npush_started=false\npush_result=failure",
                created_repo.owner,
                created_repo.name,
                auth_login or "<unknown>",
                "true" if repo_created else "false",
            )
            raise PushFailedError(f"DESTINATION_REPO_CREATION_FAILED: Repository access verification returned HTTP {access_check.status_code}.")

        logger.info(
            "[GITHUB DESTINATION]\nowner=%s\nrepo=%s\nauthenticated_user=%s\nrepository_access=%s\nrepository_created=%s\npush_started=false\npush_result=pending",
            created_repo.owner,
            created_repo.name,
            auth_login or "<unknown>",
            "true" if repo_accessible else "false",
            "true" if repo_created else "false",
        )

        return created_repo

    @staticmethod
    def _created_repo_from_response(
        profile: TargetProfile,
        repo_name: str,
        data: dict,
    ) -> CreatedRepo:
        owner_val = profile.owner
        if isinstance(data.get("owner"), dict) and data["owner"].get("login"):
            owner_val = str(data["owner"]["login"])
        return CreatedRepo(
            owner=owner_val,
            name=str(data.get("name", repo_name)),
            html_url=str(data.get("html_url", f"https://{profile.host}/{owner_val}/{repo_name}")),
            clone_url=str(data.get("clone_url", f"https://{profile.host}/{owner_val}/{repo_name}.git")),
        )

    @staticmethod
    def _error_message(status_code: int, data: dict | None, target_owner: str = "JavaAPEX") -> str:
        detail = ""
        if isinstance(data, dict):
            detail = str(data.get("message", ""))
        if status_code == 401:
            return (
                "DESTINATION_REPO_UNAUTHORIZED: Target GitHub token is invalid or expired (HTTP 401). "
                "Regenerate your PAT at github.com/settings/tokens with 'repo' scope."
            )
        if status_code == 403:
            return (
                "DESTINATION_REPO_FORBIDDEN: Target token lacks permission to create repositories (HTTP 403). "
                "Ensure the token has 'repo' scope and — if the target owner is an organization — "
                "that the token is approved for third-party organization access."
            )
        if status_code == 404:
            return (
                f"DESTINATION_REPO_NOT_FOUND: Target owner '{target_owner}' not found, or the token cannot access it (HTTP 404). "
                f"Verify that the account/organization exists and your PAT has access."
            )
        if status_code == 422 and "already exists" in detail.lower():
            return "DESTINATION_REPO_CREATION_FAILED: A repository with this name already exists under the target owner."
        if detail:
            return f"DESTINATION_REPO_CREATION_FAILED: Could not create the target repository (HTTP {status_code}): {detail}"
        return f"DESTINATION_REPO_CREATION_FAILED: Could not create the target repository (HTTP {status_code})."
