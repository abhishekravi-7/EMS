from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.core.exceptions import PushFailedError
from app.infrastructure.github.repo_pusher import RepoPusher
from app.application.use_cases.start_migration import StartMigrationUseCase
from app.shared.command_runner import CommandResult


def test_repo_pusher_successful_authenticated_git_push(tmp_path: Path):
    pusher = RepoPusher()
    repo_dir = tmp_path / "repo_push_success"
    repo_dir.mkdir()

    with patch("app.infrastructure.github.repo_pusher.run_command") as mock_run:
        mock_run.return_value = CommandResult(
            command=["git", "push"],
            exit_code=0,
            stdout="Everything up-to-date",
            stderr="",
        )
        branch = pusher.push(
            repo_dir,
            "https://github.com/qlikaccel/EMS-Migrated20260923181857.git",
            commit_message="Migrate to Java 17",
            token="ghp_destination_token_123",
        )
        assert branch == "main"
        
        # Verify remote add origin used destination token
        remote_add_call = [call for call in mock_run.call_args_list if "remote" in call[0][0] and "add" in call[0][0]]
        assert len(remote_add_call) == 1
        cmd = remote_add_call[0][0][0]
        assert "x-access-token:ghp_destination_token_123" in cmd[-1]


def test_repo_pusher_git_push_unauthorized_401(tmp_path: Path):
    pusher = RepoPusher()
    repo_dir = tmp_path / "repo_push_401"
    repo_dir.mkdir()

    with patch("app.infrastructure.github.repo_pusher.run_command") as mock_run:
        mock_run.return_value = CommandResult(
            command=["git", "push"],
            exit_code=128,
            stdout="",
            stderr="fatal: Authentication failed for 'https://x-access-token:bad_token@github.com/qlikaccel/repo.git/': 401 Bad credentials",
        )
        with pytest.raises(PushFailedError) as exc_info:
            pusher.push(
                repo_dir,
                "https://github.com/qlikaccel/repo.git",
                commit_message="Migrate to Java 17",
                token="bad_token",
            )
        err = str(exc_info.value)
        assert "DESTINATION_REPO_UNAUTHORIZED" in err
        assert "bad_token" not in err


def test_repo_pusher_git_push_forbidden_403(tmp_path: Path):
    pusher = RepoPusher()
    repo_dir = tmp_path / "repo_push_403"
    repo_dir.mkdir()

    with patch("app.infrastructure.github.repo_pusher.run_command") as mock_run:
        mock_run.return_value = CommandResult(
            command=["git", "push"],
            exit_code=128,
            stdout="",
            stderr="remote: Permission to qlikaccel/repo.git denied to user.\nfatal: unable to access: 403 Forbidden",
        )
        with pytest.raises(PushFailedError) as exc_info:
            pusher.push(
                repo_dir,
                "https://github.com/qlikaccel/repo.git",
                commit_message="Migrate to Java 17",
                token="ro_token",
            )
        err = str(exc_info.value)
        assert "DESTINATION_REPO_FORBIDDEN" in err


def test_repo_pusher_git_push_not_found_404(tmp_path: Path):
    pusher = RepoPusher()
    repo_dir = tmp_path / "repo_push_404"
    repo_dir.mkdir()

    with patch("app.infrastructure.github.repo_pusher.run_command") as mock_run:
        mock_run.return_value = CommandResult(
            command=["git", "push"],
            exit_code=128,
            stdout="",
            stderr="remote: Repository not found.\nfatal: repository 'https://github.com/qlikaccel/repo.git/' not found",
        )
        with pytest.raises(PushFailedError) as exc_info:
            pusher.push(
                repo_dir,
                "https://github.com/qlikaccel/repo.git",
                commit_message="Migrate to Java 17",
                token="some_token",
            )
        err = str(exc_info.value)
        assert "DESTINATION_REPO_NOT_FOUND" in err


def test_destination_push_uses_destination_pat_not_source():
    mock_creator = MagicMock()
    mock_pusher = MagicMock()
    mock_store = MagicMock()
    mock_paths = MagicMock()

    mock_creator.create.return_value = MagicMock(
        clone_url="https://github.com/qlikaccel/EMS-Migrated.git",
        html_url="https://github.com/qlikaccel/EMS-Migrated",
    )

    use_case = StartMigrationUseCase(repo_creator=mock_creator, repo_pusher=mock_pusher)
    
    report = {
        "jobId": "job-test-123",
        "sourceRepoUrl": "https://github.com/source_owner/source_repo.git",
        "destination": {
            "mode": "CREATE_NEW_REPO",
            "targetRepoName": "EMS-Migrated",
            "targetOwner": "qlikaccel",
            "targetHost": "github.com",
        }
    }

    # Pass destination token explicitly
    dest_pat = "ghp_destination_pat_999"
    with patch("app.application.use_cases.start_migration._fetch_user_github_pat", return_value=None):
        res = use_case._publish(
            mock_store,
            report,
            mock_paths,
            "17",
            github_token=dest_pat,
        )

    assert res == "https://github.com/qlikaccel/EMS-Migrated"
    # Verify mock_creator.create received dest_pat
    mock_creator.create.assert_called_once_with(
        "EMS-Migrated",
        owner="qlikaccel",
        host="github.com",
        token=dest_pat,
    )
    # Verify mock_pusher.push received dest_pat
    mock_pusher.push.assert_called_once_with(
        mock_paths.migrated_repo_dir,
        "https://github.com/qlikaccel/EMS-Migrated.git",
        commit_message="Migrate to Java 17",
        allow_force_update_existing=True,
        token=dest_pat,
    )
