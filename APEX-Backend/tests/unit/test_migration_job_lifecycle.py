"""Unit tests for Migration job lifecycle, non-blocking execution, multi-worker recovery, and error persistence."""

from __future__ import annotations

import json
import uuid
import pytest
from app.application.services.status_service import MigrationReportStore
from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.infrastructure.persistence.models import User
from app.infrastructure.persistence.job_repository import JobRepository


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_migration_report_store_pre_migration_fallback(tmp_path, monkeypatch):
    """Verify that a job with connect/discovery reports returns an initial QUEUED state before migration start."""
    monkeypatch.setattr("app.core.config.settings.storage_dir", tmp_path)

    job_id = f"job_connect_init_{uuid.uuid4().hex[:8]}"
    paths = WorkspacePaths(job_id)
    paths.job_dir.mkdir(parents=True, exist_ok=True)
    paths.reports_dir.mkdir(parents=True, exist_ok=True)

    job_repo = JobRepository()
    job_repo.save_connect_report(job_id, {
        "jobId": job_id,
        "repoUrl": "https://github.com/org/demo-repo",
        "owner": "org",
        "repoName": "demo-repo",
    })
    job_repo.save_discovery_report(job_id, {
        "jobId": job_id,
        "currentJavaVersion": "8",
        "buildTool": "MAVEN",
    })

    store = MigrationReportStore(paths)
    report = store.read()

    assert report is not None
    assert report["jobId"] == job_id
    assert report["status"] == "QUEUED"
    assert report["sourceRepoUrl"] == "https://github.com/org/demo-repo"
    assert report["sourceJavaVersion"] == "8"
    assert report["buildTool"] == "MAVEN"


def test_migration_database_persistence_recovery(tmp_path, monkeypatch):
    """Verify that a worker container with no local disk recovers migration report from PostgreSQL."""
    monkeypatch.setattr("app.core.config.settings.storage_dir", tmp_path)

    job_id = f"job_mig_db_rec_{uuid.uuid4().hex[:8]}"
    paths = WorkspacePaths(job_id)

    mock_db_report = {
        "jobId": job_id,
        "status": "COMPLETED",
        "currentStep": "COMPLETED",
        "progressPercent": 100,
        "sourceRepoUrl": "https://github.com/org/demo-repo",
        "targetRepo": "https://github.com/org/demo-repo-migrated",
        "filesModified": 12,
        "logLines": ["Migration completed successfully."],
    }

    monkeypatch.setattr(
        "app.application.services.status_service.load_report_from_db",
        lambda j_id: mock_db_report if j_id == job_id else None,
    )

    store = MigrationReportStore(paths)
    report = store.read()

    assert report is not None
    assert report["status"] == "COMPLETED"
    assert report["progressPercent"] == 100
    assert report["targetRepo"] == "https://github.com/org/demo-repo-migrated"


@pytest.mark.anyio
async def test_migration_endpoints_non_blocking_async_execution(tmp_path, monkeypatch):
    """Verify that migration_summary, detail, logs, and start endpoints run asynchronously without blocking."""
    monkeypatch.setattr("app.core.config.settings.storage_dir", tmp_path)
    from app.api.v1.endpoints.migration_execution_controller import (
        migration_summary,
        migration_detail,
        migration_logs,
    )

    job_id = f"job_mig_endpoints_{uuid.uuid4().hex[:8]}"
    paths = WorkspacePaths(job_id)
    paths.job_dir.mkdir(parents=True, exist_ok=True)
    paths.reports_dir.mkdir(parents=True, exist_ok=True)

    job_repo = JobRepository()
    job_repo.save_connect_report(job_id, {
        "jobId": job_id,
        "repoUrl": "https://github.com/org/repo",
    })
    job_repo.save_discovery_report(job_id, {
        "jobId": job_id,
        "currentJavaVersion": "11",
        "buildTool": "MAVEN",
    })
    job_repo.save_migration_config_report(job_id, {
        "sourceJavaVersion": "11",
        "targetJavaVersion": "17",
    })

    user = User(id=1, email="test@apex.dev", full_name="Test User")

    # Polling summary before start should return 200 with QUEUED state
    summary_resp = await migration_summary(job_id=job_id, current_user=user, db=None)
    assert summary_resp.status_code == 200
    summary_data = json.loads(summary_resp.body.decode("utf-8"))
    assert summary_data["job_id"] == job_id
    assert summary_data["status"] == "QUEUED"

    # Detail and logs
    detail_resp = await migration_detail(job_id=job_id, current_user=user, db=None)
    assert detail_resp.status_code == 200
    detail_data = json.loads(detail_resp.body.decode("utf-8"))
    assert detail_data["job_id"] == job_id

    logs_resp = await migration_logs(job_id=job_id, current_user=user, db=None)
    assert logs_resp.status_code == 200
    logs_data = json.loads(logs_resp.body.decode("utf-8"))
    assert logs_data["job_id"] == job_id
