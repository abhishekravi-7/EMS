from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from app.core.exceptions import PushFailedError
from app.infrastructure.github.github_client import GithubClient, GithubRepoResponse
from app.infrastructure.github.profile_resolver import ProfileResolver, TargetProfile
from app.infrastructure.github.repo_creator import RepoCreator, CreatedRepo


def test_clean_repo_name():
    assert RepoCreator.clean_repo_name("https://github.com/qlikaccel/EMS-Migrated20260923181857.git") == "EMS-Migrated20260923181857"
    assert RepoCreator.clean_repo_name("git@github.com:qlikaccel/my-repo.git") == "my-repo"
    assert RepoCreator.clean_repo_name("my-repo") == "my-repo"
    assert RepoCreator.clean_repo_name("") == "repo"


def test_repo_creator_success_new_repo():
    mock_gh = MagicMock(spec=GithubClient)
    mock_resolver = MagicMock(spec=ProfileResolver)

    mock_resolver.resolve.return_value = TargetProfile(owner="qlikaccel", is_org=False, host="github.com")
    mock_gh.get_authenticated_user_sync.return_value = {"login": "qlikaccel"}
    mock_gh.create_repository_sync.return_value = GithubRepoResponse(
        status_code=201,
        data={
            "name": "EMS-Migrated20260923181857",
            "owner": {"login": "qlikaccel"},
            "html_url": "https://github.com/qlikaccel/EMS-Migrated20260923181857",
            "clone_url": "https://github.com/qlikaccel/EMS-Migrated20260923181857.git",
        },
    )
    # Post-creation access verification
    mock_gh.get_repository_sync.return_value = GithubRepoResponse(
        status_code=200,
        data={"name": "EMS-Migrated20260923181857", "owner": {"login": "qlikaccel"}},
    )

    creator = RepoCreator(github_client=mock_gh, profile_resolver=mock_resolver)
    result = creator.create(
        "EMS-Migrated20260923181857",
        owner="qlikaccel",
        token="ghp_dest_token_123",
    )

    assert isinstance(result, CreatedRepo)
    assert result.owner == "qlikaccel"
    assert result.name == "EMS-Migrated20260923181857"
    assert result.clone_url == "https://github.com/qlikaccel/EMS-Migrated20260923181857.git"
    assert result.html_url == "https://github.com/qlikaccel/EMS-Migrated20260923181857"

    mock_resolver.resolve.assert_called_once_with(owner="qlikaccel", host=None, token="ghp_dest_token_123")
    mock_gh.create_repository_sync.assert_called_once_with(
        "qlikaccel", "EMS-Migrated20260923181857", "ghp_dest_token_123", is_org=False, private=False, description="Migrated with the Java APEX migration engine"
    )
    mock_gh.get_repository_sync.assert_called_once_with("qlikaccel", "EMS-Migrated20260923181857", "ghp_dest_token_123")


def test_repo_creator_fallback_from_org_to_user_on_404():
    mock_gh = MagicMock(spec=GithubClient)
    mock_resolver = MagicMock(spec=ProfileResolver)

    mock_resolver.resolve.return_value = TargetProfile(owner="qlikaccel", is_org=True, host="github.com")
    mock_gh.get_authenticated_user_sync.return_value = {"login": "qlikaccel"}
    
    # Org creation returns 404, fallback to user creation returns 201
    mock_gh.create_repository_sync.side_effect = [
        GithubRepoResponse(status_code=404, data={"message": "Not Found"}),
        GithubRepoResponse(
            status_code=201,
            data={
                "name": "EMS-Migrated20260923181857",
                "owner": {"login": "qlikaccel"},
                "html_url": "https://github.com/qlikaccel/EMS-Migrated20260923181857",
                "clone_url": "https://github.com/qlikaccel/EMS-Migrated20260923181857.git",
            },
        ),
    ]
    mock_gh.get_repository_sync.return_value = GithubRepoResponse(
        status_code=200,
        data={"name": "EMS-Migrated20260923181857", "owner": {"login": "qlikaccel"}},
    )

    creator = RepoCreator(github_client=mock_gh, profile_resolver=mock_resolver)
    result = creator.create(
        "EMS-Migrated20260923181857",
        owner="qlikaccel",
        token="ghp_dest_token_123",
    )

    assert result.name == "EMS-Migrated20260923181857"
    assert mock_gh.create_repository_sync.call_count == 2


def test_repo_creator_existing_repo_accessible():
    mock_gh = MagicMock(spec=GithubClient)
    mock_resolver = MagicMock(spec=ProfileResolver)

    mock_resolver.resolve.return_value = TargetProfile(owner="qlikaccel", is_org=False, host="github.com")
    mock_gh.get_authenticated_user_sync.return_value = {"login": "qlikaccel"}
    mock_gh.create_repository_sync.return_value = GithubRepoResponse(
        status_code=422,
        data={"message": "Repository creation failed.", "errors": [{"message": "name already exists on this account"}]},
    )
    mock_gh.get_repository_sync.return_value = GithubRepoResponse(
        status_code=200,
        data={
            "name": "EMS-Migrated20260923181857",
            "owner": {"login": "qlikaccel"},
            "html_url": "https://github.com/qlikaccel/EMS-Migrated20260923181857",
            "clone_url": "https://github.com/qlikaccel/EMS-Migrated20260923181857.git",
        },
    )

    creator = RepoCreator(github_client=mock_gh, profile_resolver=mock_resolver)
    result = creator.create("EMS-Migrated20260923181857", owner="qlikaccel", token="ghp_dest_token_123")

    assert result.name == "EMS-Migrated20260923181857"
    assert result.owner == "qlikaccel"


def test_repo_creator_invalid_pat_401():
    mock_gh = MagicMock(spec=GithubClient)
    mock_resolver = MagicMock(spec=ProfileResolver)

    mock_resolver.resolve.return_value = TargetProfile(owner="qlikaccel", is_org=False, host="github.com")
    mock_gh.get_authenticated_user_sync.return_value = None
    mock_gh.create_repository_sync.return_value = GithubRepoResponse(
        status_code=401,
        data={"message": "Bad credentials"},
    )

    creator = RepoCreator(github_client=mock_gh, profile_resolver=mock_resolver)
    with pytest.raises(PushFailedError) as exc_info:
        creator.create("EMS-Migrated20260923181857", owner="qlikaccel", token="bad_token")

    assert "DESTINATION_REPO_UNAUTHORIZED" in str(exc_info.value)
    assert "bad_token" not in str(exc_info.value)


def test_repo_creator_forbidden_pat_403():
    mock_gh = MagicMock(spec=GithubClient)
    mock_resolver = MagicMock(spec=ProfileResolver)

    mock_resolver.resolve.return_value = TargetProfile(owner="qlikaccel", is_org=False, host="github.com")
    mock_gh.get_authenticated_user_sync.return_value = {"login": "user"}
    mock_gh.create_repository_sync.return_value = GithubRepoResponse(
        status_code=403,
        data={"message": "Resource not accessible by personal access token"},
    )

    creator = RepoCreator(github_client=mock_gh, profile_resolver=mock_resolver)
    with pytest.raises(PushFailedError) as exc_info:
        creator.create("EMS-Migrated20260923181857", owner="qlikaccel", token="token_without_permission")

    assert "DESTINATION_REPO_FORBIDDEN" in str(exc_info.value)


def test_repo_creator_destination_not_found_404():
    mock_gh = MagicMock(spec=GithubClient)
    mock_resolver = MagicMock(spec=ProfileResolver)

    mock_resolver.resolve.return_value = TargetProfile(owner="nonexistent_org", is_org=False, host="github.com")
    mock_gh.get_authenticated_user_sync.return_value = {"login": "user"}
    mock_gh.create_repository_sync.return_value = GithubRepoResponse(
        status_code=404,
        data={"message": "Not Found"},
    )

    creator = RepoCreator(github_client=mock_gh, profile_resolver=mock_resolver)
    with pytest.raises(PushFailedError) as exc_info:
        creator.create("EMS-Migrated20260923181857", owner="nonexistent_org", token="valid_token")

    assert "DESTINATION_REPO_NOT_FOUND" in str(exc_info.value)


def test_repo_creator_access_verification_failed():
    mock_gh = MagicMock(spec=GithubClient)
    mock_resolver = MagicMock(spec=ProfileResolver)

    mock_resolver.resolve.return_value = TargetProfile(owner="qlikaccel", is_org=False, host="github.com")
    mock_gh.get_authenticated_user_sync.return_value = {"login": "qlikaccel"}
    mock_gh.create_repository_sync.return_value = GithubRepoResponse(
        status_code=201,
        data={
            "name": "EMS-Migrated20260923181857",
            "owner": {"login": "qlikaccel"},
            "html_url": "https://github.com/qlikaccel/EMS-Migrated20260923181857",
            "clone_url": "https://github.com/qlikaccel/EMS-Migrated20260923181857.git",
        },
    )
    # Verification check returns 404 (e.g. token lacks read/repo scope or repo creation was blocked)
    mock_gh.get_repository_sync.return_value = GithubRepoResponse(
        status_code=404,
        data={"message": "Not Found"},
    )

    creator = RepoCreator(github_client=mock_gh, profile_resolver=mock_resolver)
    with pytest.raises(PushFailedError) as exc_info:
        creator.create("EMS-Migrated20260923181857", owner="qlikaccel", token="limited_token")

    assert "DESTINATION_REPO_NOT_FOUND" in str(exc_info.value)
