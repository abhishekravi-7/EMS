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

    def resolve(self, owner: str | None = None, host: str | None = None, token: str | None = None) -> TargetProfile:
        effective_token = (token or "").strip() or (settings.github_target_token or "").strip() or (settings.github_token or "").strip() or None

        auth_user = self._github.get_authenticated_user_sync(effective_token) if effective_token else None
        auth_login = auth_user.get("login") if auth_user else None

        resolved_owner = (owner or auth_login or settings.github_target_owner or "").strip()

        if auth_login and resolved_owner.lower() == auth_login.lower():
            return TargetProfile(
                owner=resolved_owner,
                is_org=False,
                host=(host or "github.com"),
            )

        owner_type = self._github.get_owner_type_sync(
            resolved_owner, token=effective_token
        )
        is_org = owner_type == "Organization"
        return TargetProfile(
            owner=resolved_owner,
            is_org=is_org,
            host=(host or "github.com"),
        )
