"""Unit tests for existing-test job lifecycle, multi-worker disk persistence, and ownership verification."""

from __future__ import annotations

import json
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException

from app.application.use_cases.existing_test_runner_service import ExistingTestRunnerService
from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.infrastructure.persistence.models import User
from app.api.deps import verify_job_ownership


def test_existing_test_runner_has_job_and_disk_persistence(tmp_path, monkeypatch):
    """Verify that job state written by one worker is retrieved by another worker from disk."""
    monkeypatch.setattr("app.core.config.settings.storage_dir", tmp_path)

    runner_worker1 = ExistingTestRunnerService()
    runner_worker2 = ExistingTestRunnerService()

    job_id = "job_test_lifecycle_123"

    # Initially neither worker knows about the job
    assert not runner_worker1.has_job(job_id)
    assert not runner_worker2.has_job(job_id)
    assert runner_worker2.get_status(job_id)["status"] == "IDLE"

    # Worker 1 starts the job and saves state to disk
    paths = WorkspacePaths(job_id, storage_dir=tmp_path)
    paths.reports_dir.mkdir(parents=True, exist_ok=True)

    with runner_worker1._lock:
        runner_worker1._state[job_id] = {
            "status": "RUNNING",
            "executed": False,
            "logs": [{"ts": "12:00:00", "msg": "Running tests...", "level": "INFO"}],
            "result": None,
        }
    runner_worker1._save_state_to_disk(job_id)

    # Worker 2 (clean in-memory state) checks has_job and get_status
    assert runner_worker2.has_job(job_id)
    status_w2 = runner_worker2.get_status(job_id)
    assert status_w2["status"] == "RUNNING"
    assert status_w2["executed"] is False
    assert len(status_w2["logs"]) == 1
    assert status_w2["logs"][0]["msg"] == "Running tests..."

    # Worker 1 completes the job
    final_result = {
        "status": "COMPLETED",
        "executed": True,
        "metrics": {"total": 5, "passed": 5, "failed": 0, "skipped": 0, "duration": "2.5s"},
        "test_results": [],
    }
    with runner_worker1._lock:
        runner_worker1._state[job_id]["status"] = "COMPLETED"
        runner_worker1._state[job_id]["executed"] = True
        runner_worker1._state[job_id]["result"] = final_result

    paths.existing_test_report_path.write_text(json.dumps(final_result), encoding="utf-8")
    runner_worker1._save_state_to_disk(job_id)

    # Worker 2 resets local cache to simulate separate process, reads completed state
    runner_worker2._state.clear()
    status_completed = runner_worker2.get_status(job_id)
    assert status_completed["status"] == "COMPLETED"
    assert status_completed["executed"] is True
    assert status_completed["result"]["metrics"]["passed"] == 5


def test_verify_job_ownership_allows_existing_test_job(tmp_path, monkeypatch):
    """Verify that verify_job_ownership accepts active existing-test jobs and rejects unknown jobs."""
    monkeypatch.setattr("app.core.config.settings.storage_dir", tmp_path)
    monkeypatch.setattr("app.core.config.settings.database_enabled", False)

    user = User(id=1, full_name="Test User", email="test@example.com")
    runner = ExistingTestRunnerService()
    monkeypatch.setattr("app.application.use_cases.existing_test_runner_service.existing_test_runner_service", runner)

    known_job = "job_c2e98492b5b5"
    unknown_job = "job_nonexistent_9999"

    # Simulate known job in memory / disk
    with runner._lock:
        runner._state[known_job] = {"status": "RUNNING", "executed": False, "logs": [], "result": None}

    # verify_job_ownership should succeed for known_job without raising HTTPException
    verify_job_ownership(None, known_job, user)

    # verify_job_ownership should raise 404 for unknown_job
    with pytest.raises(HTTPException) as exc_info:
        verify_job_ownership(None, unknown_job, user)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "JOB_NOT_FOUND"


def test_existing_test_runner_cleanup(tmp_path, monkeypatch):
    """Verify that reset cleans up state on disk and in memory."""
    monkeypatch.setattr("app.core.config.settings.storage_dir", tmp_path)
    runner = ExistingTestRunnerService()
    job_id = "job_to_clean_up"

    paths = WorkspacePaths(job_id, storage_dir=tmp_path)
    paths.reports_dir.mkdir(parents=True, exist_ok=True)

    with runner._lock:
        runner._state[job_id] = {"status": "COMPLETED", "executed": True, "logs": [], "result": {}}
    runner._save_state_to_disk(job_id)

    assert paths.existing_test_state_path.is_file()
    assert runner.has_job(job_id)

    runner.reset(job_id)

    assert not paths.existing_test_state_path.is_file()
    assert job_id not in runner._state


def test_concurrent_existing_test_jobs_isolation(tmp_path, monkeypatch):
    """Verify that concurrent existing-test jobs maintain independent state and do not overwrite each other."""
    monkeypatch.setattr("app.core.config.settings.storage_dir", tmp_path)
    runner = ExistingTestRunnerService()

    job_A = "job_AAA_111"
    job_B = "job_BBB_222"

    with runner._lock:
        runner._state[job_A] = {
            "status": "RUNNING",
            "executed": False,
            "logs": [{"ts": "10:00:00", "msg": "Job A running", "level": "INFO"}],
            "result": None,
        }
        runner._state[job_B] = {
            "status": "COMPLETED",
            "executed": True,
            "logs": [{"ts": "10:00:01", "msg": "Job B finished", "level": "INFO"}],
            "result": {"status": "COMPLETED", "metrics": {"passed": 10}},
        }

    runner._save_state_to_disk(job_A)
    runner._save_state_to_disk(job_B)

    # Verify both jobs are independently queried
    status_A = runner.get_status(job_A)
    status_B = runner.get_status(job_B)

    assert status_A["status"] == "RUNNING"
    assert status_A["executed"] is False
    assert status_A["logs"][0]["msg"] == "Job A running"

    assert status_B["status"] == "COMPLETED"
    assert status_B["executed"] is True
    assert status_B["result"]["metrics"]["passed"] == 10


def test_existing_test_database_persistence_recovery(tmp_path, monkeypatch):
    """Verify that a worker with no in-memory or disk state recovers job status from database."""
    monkeypatch.setattr("app.core.config.settings.storage_dir", tmp_path)

    job_id = "job_db_recovery_456"
    mock_db_state = {
        "status": "RUNNING",
        "executed": False,
        "logs": [{"ts": "11:00:00", "msg": "Running on worker A", "level": "INFO"}],
        "result": None,
    }

    runner = ExistingTestRunnerService()
    # Mock load_existing_test_state_from_db returning mock_db_state
    monkeypatch.setattr(
        "app.infrastructure.persistence.existing_test_repository.load_existing_test_state_from_db",
        lambda j_id: mock_db_state if j_id == job_id else None,
    )
    monkeypatch.setattr(
        "app.infrastructure.persistence.existing_test_repository.existing_test_state_exists_in_db",
        lambda j_id: j_id == job_id,
    )

    # Worker has no local memory or disk state
    assert job_id not in runner._state
    assert runner.has_job(job_id)

    status = runner.get_status(job_id)
    assert status["status"] == "RUNNING"
    assert status["executed"] is False
    assert status["logs"][0]["msg"] == "Running on worker A"

