from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.domain.models.build_result import BuildResult
from app.infrastructure.build.build_validator import BuildValidator
from app.infrastructure.github.branch_creator import BranchCreator
from app.infrastructure.github.repo_pusher import RepoPusher
from app.infrastructure.migration_engine.automated_migration_runner import AutomatedMigrationRunner
from app.shared.command_runner import CommandResult


def test_normalize_repo_url():
    assert RepoPusher._normalize_repo_url("https://github.com/owner/repo.git/") == "https://github.com/owner/repo"
    assert RepoPusher._normalize_repo_url("https://github.com/owner/repo///") == "https://github.com/owner/repo"
    assert RepoPusher._normalize_repo_url("https://github.com/owner/repo.git") == "https://github.com/owner/repo"
    assert RepoPusher._normalize_repo_url("https://github.com/owner/repo") == "https://github.com/owner/repo"


def test_build_auth_url():
    token = "ghp_secretToken12345"
    url = "https://github.com/Javaapex-owner/leave-management.git/"
    auth_url = RepoPusher._build_auth_url(url, token)
    assert auth_url == "https://x-access-token:ghp_secretToken12345@github.com/Javaapex-owner/leave-management.git"


def test_branch_creator_success(tmp_path: Path):
    creator = BranchCreator()
    repo_dir = tmp_path / "repo_success"
    repo_dir.mkdir()

    with patch("app.infrastructure.github.branch_creator.run_command") as mock_run:
        mock_run.return_value = CommandResult(
            command=["git", "push"],
            exit_code=0,
            stdout="Everything up-to-date",
            stderr="",
        )
        res = creator.push_branch(
            repo_dir,
            "https://github.com/owner/repo.git",
            "migration-branch",
            commit_message="Migrate branch",
            token="secret_valid_token",
        )
        assert res == "migration-branch"


def test_branch_creator_invalid_pat_401(tmp_path: Path):
    creator = BranchCreator()
    repo_dir = tmp_path / "repo_401"
    repo_dir.mkdir()

    with patch("app.infrastructure.github.branch_creator.run_command") as mock_run:
        mock_run.return_value = CommandResult(
            command=["git", "push"],
            exit_code=128,
            stdout="",
            stderr="fatal: Authentication failed for 'https://x-access-token:bad_token@github.com/owner/repo.git/': 401 Bad credentials",
        )
        with pytest.raises(Exception) as exc_info:
            creator.push_branch(
                repo_dir,
                "https://github.com/owner/repo.git",
                "migration-branch",
                commit_message="Migrate branch",
                token="bad_token",
            )
        err = str(exc_info.value)
        assert "bad_token" not in err
        assert "Invalid GitHub token. Please verify that your PAT is valid and has not expired." in err


def test_branch_creator_no_write_permission_403(tmp_path: Path):
    creator = BranchCreator()
    repo_dir = tmp_path / "repo_403"
    repo_dir.mkdir()

    with patch("app.infrastructure.github.branch_creator.run_command") as mock_run:
        mock_run.return_value = CommandResult(
            command=["git", "push"],
            exit_code=128,
            stdout="",
            stderr="fatal: remote: Permission to owner/repo.git denied to user.\nfatal: unable to access 'https://x-access-token:readonly_token@github.com/owner/repo.git/': The requested URL returned error: 403",
        )
        with pytest.raises(Exception) as exc_info:
            creator.push_branch(
                repo_dir,
                "https://github.com/owner/repo.git",
                "migration-branch",
                commit_message="Migrate branch",
                token="readonly_token",
            )
        err = str(exc_info.value)
        assert "readonly_token" not in err
        assert "Unable to push to the destination repository. Please verify that your PAT has write permission." in err


def test_branch_creator_repo_not_found_404(tmp_path: Path):
    creator = BranchCreator()
    repo_dir = tmp_path / "repo_404"
    repo_dir.mkdir()

    with patch("app.infrastructure.github.branch_creator.run_command") as mock_run:
        mock_run.return_value = CommandResult(
            command=["git", "push"],
            exit_code=128,
            stdout="",
            stderr="remote: Repository not found.\nfatal: repository 'https://x-access-token:token123@github.com/owner/repo.git/' not found",
        )
        with pytest.raises(Exception) as exc_info:
            creator.push_branch(
                repo_dir,
                "https://github.com/owner/repo.git",
                "migration-branch",
                commit_message="Migrate branch",
                token="token123",
            )
        err = str(exc_info.value)
        assert "token123" not in err
        assert "Unable to access the destination repository. Please verify that the repository exists and that your PAT has access." in err


def test_branch_creator_branch_already_exists(tmp_path: Path):
    creator = BranchCreator()
    repo_dir = tmp_path / "repo_conflict"
    repo_dir.mkdir()

    with patch("app.infrastructure.github.branch_creator.run_command") as mock_run:
        mock_run.return_value = CommandResult(
            command=["git", "push"],
            exit_code=1,
            stdout="",
            stderr="To https://github.com/owner/repo.git\n ! [rejected]        migration -> migration (fetch first)\nerror: failed to push some refs to 'https://github.com/owner/repo.git'",
        )
        with pytest.raises(Exception) as exc_info:
            creator.push_branch(
                repo_dir,
                "https://github.com/owner/repo.git",
                "migration",
                commit_message="Migrate branch",
                token="token123",
            )
        err = str(exc_info.value)
        assert "branch already exists on the destination repository or has conflicting commits." in err



def test_build_validator_finds_nested_pom(tmp_path: Path):
    # Setup nested project directory: repo_root/backend/pom.xml
    repo_root = tmp_path / "nested_repo"
    backend_dir = repo_root / "backend"
    backend_dir.mkdir(parents=True)
    pom_file = backend_dir / "pom.xml"
    pom_file.write_text("<project><modelVersion>4.0.0</modelVersion><groupId>com.example</groupId><artifactId>app</artifactId><version>1.0</version></project>")

    validator = BuildValidator()
    with patch("app.infrastructure.build.build_validator.resolve_executable", return_value="mvn"), \
         patch("app.infrastructure.build.build_validator.run_command") as mock_run:
        mock_run.return_value = CommandResult(
            command=["mvn", "compile"],
            exit_code=0,
            stdout="[INFO] BUILD SUCCESS",
            stderr="",
        )
        result = validator.validate(repo_root, "maven")
        assert result.success is True
        # Verify run_command was invoked with cwd=backend_dir
        mock_run.assert_called()
        call_kwargs = mock_run.call_args[1]
        actual_cwd = str(call_kwargs["cwd"]).replace("\\\\?\\", "").rstrip("\\/")
        expected_cwd = str(backend_dir).replace("\\\\?\\", "").rstrip("\\/")
        assert actual_cwd.lower() == expected_cwd.lower()


def test_migration_execution_pipeline_start():
    from app.application.pipelines.migration_execution_pipeline import MigrationExecutionPipeline
    mock_use_case = MagicMock()
    mock_use_case.prepare.return_value = {
        "jobId": "test-job-123",
        "status": "QUEUED",
        "progressPercent": 0,
        "sourceRepoUrl": "https://github.com/owner/repo.git",
        "sourceJavaVersion": "8",
        "targetJavaVersion": "17",
    }
    pipeline = MigrationExecutionPipeline(use_case=mock_use_case)
    result = pipeline.start("test-job-123", {"github_token": "ghp_xyz123", "target_java_version": "17"}, current_user_id=1)
    assert result is not None
    mock_use_case.prepare.assert_called_once_with("test-job-123", {"github_token": "ghp_xyz123", "target_java_version": "17"})


