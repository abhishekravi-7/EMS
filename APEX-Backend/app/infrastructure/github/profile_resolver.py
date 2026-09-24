"""Resolves the target GitHub owner (org vs user) for publishing."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.infrastructure.github.github_client import GithubClient


@dataclass(frozen=True)
class TargetProfile:
    owner: str
    is_org: bool
    host: str = "github.com"


class ProfileResolver:
    def __init__(self, github_client: GithubClient | None = None) -> None:
        self._github = github_client or GithubClient()

    def resolve(
        self,
        owner: str | None = None,
        host: str | None = None,
        token: str | None = None,
    ) -> TargetProfile:
        resolved_owner = (owner or settings.github_target_owner or "").strip()
        auth_user = None
        if token:
            try:
                auth_user = self._github.get_authenticated_user_sync(token=token)
            except Exception:
                auth_user = None

        auth_login = auth_user.get("login", "") if isinstance(auth_user, dict) else ""
        if not resolved_owner and auth_login:
            resolved_owner = auth_login

        if resolved_owner and auth_login and resolved_owner.lower() == auth_login.lower():
            # Matches authenticated user login directly -> personal user repository
            return TargetProfile(
                owner=resolved_owner,
                is_org=False,
                host=(host or "github.com"),
            )

        owner_type = self._github.get_owner_type_sync(
            resolved_owner, token=token or settings.github_target_token or None
        )
        is_org = owner_type == "Organization"
        return TargetProfile(
            owner=resolved_owner,
            is_org=is_org,
            host=(host or "github.com"),
        )
