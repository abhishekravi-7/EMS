"""Unit tests for Pre-migration Proposed Test Case execution and Baseline vs Migrated Comparison."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.application.use_cases.proposed_tests.proposed_test_service import ProposedTestService
from app.domain.models.proposed_test_models import (
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
    ExecutionResult,
)
from app.domain.models.build_result import BuildResult
from app.infrastructure.build.app_launcher import AppLaunchResult
from app.infrastructure.build.app_readiness_checker import AppReadinessResult
from app.infrastructure.workspace.workspace_paths import WorkspacePaths


@pytest.fixture
def mock_repo_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    job_id = "job-baseline-test-123"
    job_dir = tmp_path / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    original_repo = tmp_path / "repos" / "original"
    original_repo.mkdir(parents=True, exist_ok=True)
    migrated_repo = tmp_path / "repos" / "migrated"
    migrated_repo.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(WorkspacePaths, "job_dir", job_dir)
    monkeypatch.setattr(WorkspacePaths, "original_repo_dir", original_repo)
    monkeypatch.setattr(WorkspacePaths, "migrated_repo_dir", migrated_repo)

    return {
        "job_id": job_id,
        "job_dir": job_dir,
        "original_repo": original_repo,
        "migrated_repo": migrated_repo,
    }


def test_run_source_baseline_build_failure(mock_repo_paths):
    """When source build fails, baseline execution stops gracefully without crashing migration."""
    service = ProposedTestService()
    job_id = mock_repo_paths["job_id"]

    # Mock build validator failure
    with patch("app.infrastructure.build.build_validator.BuildValidator.validate") as mock_build:
        mock_build.return_value = BuildResult(
            success=False,
            tool="maven",
            error_lines=["[ERROR] Compilation error in source repo"],
        )

        res = service.run_source_baseline(job_id, build_tool="MAVEN")

        assert res["source_build_success"] is False
        assert res["source_startup_status"] == "NOT_STARTED"
        assert res["source_readiness_status"] == "NOT_STARTED"
        assert res["metrics"]["executed"] == 0


def test_run_source_baseline_startup_failure(mock_repo_paths):
    """When source application process fails to start, baseline captures error and marks tests NOT_EXECUTED."""
    service = ProposedTestService()
    job_id = mock_repo_paths["job_id"]

    dummy_tests = [
        ProposedTestCase(
            id="PROP-001",
            title="Verify GET /api/attendance",
            description="Fetch attendance",
            source="LLM Generated",
            reason="Coverage",
            expected_result="200 OK",
            type=ProposedTestType.API,
            priority=ProposedTestPriority.HIGH,
            status=ProposedTestStatus.PROPOSED,
        ),
    ]

    with patch("app.infrastructure.build.build_validator.BuildValidator.validate") as mock_build, \
         patch("app.infrastructure.build.app_launcher.MigratedAppLauncher.launch") as mock_launch, \
         patch.object(service, "get_proposed_tests", return_value=dummy_tests):

        mock_build.return_value = BuildResult(success=True, tool="maven", log_lines=["BUILD SUCCESS"])
        mock_launch.return_value = AppLaunchResult(
            success=False,
            pid=1234,
            exit_code=1,
            error="Database connection failure: Application failed to establish database connectivity.",
            failure_category="DATABASE",
        )

        res = service.run_source_baseline(job_id, build_tool="MAVEN")

        assert res["source_build_success"] is True
        assert res["source_startup_status"] == "STARTUP_FAILED"
        assert res["source_readiness_status"] == "APPLICATION_UNAVAILABLE"
        assert "Database connection failure" in res["source_readiness_error"]
        assert res["metrics"]["executed"] == 0
        assert res["test_cases"][0]["baseline_execution_result"]["status"] == "NOT_EXECUTED"


def test_run_source_baseline_success(mock_repo_paths):
    """When source build and startup succeed, baseline executes Playwright tests against source app."""
    service = ProposedTestService()
    job_id = mock_repo_paths["job_id"]
    pt_dir = mock_repo_paths["job_dir"] / "proposed-tests"

    dummy_tests = [
        ProposedTestCase(
            id="PROP-001",
            title="Verify GET /api/attendance",
            description="Fetch attendance",
            source="LLM Generated",
            reason="Coverage",
            expected_result="200 OK",
            type=ProposedTestType.API,
            priority=ProposedTestPriority.HIGH,
            status=ProposedTestStatus.PROPOSED,
        ),
        ProposedTestCase(
            id="PROP-002",
            title="Verify POST /api/attendance/send-email",
            description="Send email",
            source="BRD Document",
            reason="Requirement",
            expected_result="200 OK",
            type=ProposedTestType.API,
            priority=ProposedTestPriority.MEDIUM,
            status=ProposedTestStatus.PROPOSED,
        ),
    ]

    with patch("app.infrastructure.build.build_validator.BuildValidator.validate") as mock_build, \
         patch("app.infrastructure.build.app_launcher.MigratedAppLauncher.launch") as mock_launch, \
         patch("app.infrastructure.build.app_launcher.MigratedAppLauncher.stop") as mock_stop, \
         patch("app.infrastructure.build.app_readiness_checker.AppReadinessChecker.wait_for_ready") as mock_ready, \
         patch.object(service, "get_proposed_tests", return_value=dummy_tests), \
         patch("app.application.use_cases.proposed_tests.proposed_test_executor.ProposedTestExecutor.execute_test") as mock_exec, \
         patch("app.application.use_cases.proposed_tests.proposed_test_allure_reporter.ProposedTestAllureReporter.generate_allure_results"), \
         patch("app.application.use_cases.proposed_tests.proposed_test_allure_reporter.ProposedTestAllureReporter.generate_html_report"):

        mock_build.return_value = BuildResult(success=True, tool="maven", log_lines=["BUILD SUCCESS"])
        mock_launch.return_value = AppLaunchResult(success=True, port=8081, pid=18012, startup_detected=True)
        mock_ready.return_value = AppReadinessResult(ready=True, port=8081, base_url="http://localhost:8081", http_status=200, health_endpoint="/")

        # First test passes, second test fails in baseline
        mock_exec.side_effect = [
            ExecutionResult(status=ProposedTestStatus.PASSED, duration="0.45s", stdout="200 OK"),
            ExecutionResult(status=ProposedTestStatus.FAILED, duration="0.80s", error="500 Internal Error"),
        ]

        res = service.run_source_baseline(job_id, build_tool="MAVEN")

        assert res["source_build_success"] is True
        assert res["source_startup_status"] == "STARTED"
        assert res["source_readiness_status"] == "READY"
        assert res["metrics"]["executed"] == 2
        assert res["metrics"]["passed"] == 1
        assert res["metrics"]["failed"] == 1

        # Verify proposals.json master suite was saved
        proposals_file = pt_dir / "proposals.json"
        assert proposals_file.exists()
        saved_data = json.loads(proposals_file.read_text(encoding="utf-8"))
        assert len(saved_data) == 2
        assert saved_data[0]["baseline_execution_result"]["status"] == "PASSED"
        assert saved_data[1]["baseline_execution_result"]["status"] == "FAILED"


def test_get_comparison(mock_repo_paths):
    """Verify parity rate, regressions, and improvements calculation."""
    service = ProposedTestService()
    job_id = mock_repo_paths["job_id"]
    pt_dir = mock_repo_paths["job_dir"] / "proposed-tests"
    pt_dir.mkdir(parents=True, exist_ok=True)

    # Write proposals.json with baseline and migrated results
    proposals_data = [
        {
            "id": "PROP-001",
            "title": "Verify GET /api/attendance",
            "description": "Fetch attendance",
            "source": "LLM Generated",
            "reason": "Coverage",
            "expected_result": "200 OK",
            "type": "API",
            "priority": "HIGH",
            "status": "PASSED",
            "baseline_execution_result": {"status": "PASSED", "duration": "0.3s"},
            "execution_result": {"status": "PASSED", "duration": "0.25s"},
        },
        {
            "id": "PROP-002",
            "title": "Verify POST /api/attendance/send-email",
            "description": "Send email",
            "source": "BRD Document",
            "reason": "Requirement",
            "expected_result": "200 OK",
            "type": "API",
            "priority": "MEDIUM",
            "status": "FAILED",
            "baseline_execution_result": {"status": "PASSED", "duration": "0.4s"},
            "execution_result": {"status": "FAILED", "duration": "0.5s", "error": "404 Not Found"},
        },
        {
            "id": "PROP-003",
            "title": "Verify GET /api/users",
            "description": "Get users",
            "source": "Existing",
            "reason": "Existing",
            "expected_result": "200 OK",
            "type": "API",
            "priority": "LOW",
            "status": "PASSED",
            "baseline_execution_result": {"status": "FAILED", "duration": "0.6s", "error": "500"},
            "execution_result": {"status": "PASSED", "duration": "0.3s"},
        },
    ]

    proposals_file = pt_dir / "proposals.json"
    proposals_file.write_text(json.dumps(proposals_data), encoding="utf-8")

    comparison = service.get_comparison(job_id)

    assert comparison.baseline_available is True
    assert comparison.target_available is True
    assert comparison.baseline_metrics.passed == 2
    assert comparison.baseline_metrics.failed == 1
    assert comparison.target_metrics.passed == 2
    assert comparison.target_metrics.failed == 1
    assert comparison.regressions_count == 1   # PROP-002 (passed -> failed)
    assert comparison.improvements_count == 1  # PROP-003 (failed -> passed)
    assert comparison.preserved_passed_count == 1     # PROP-001 (passed -> passed)
    assert comparison.parity_percentage == "50.0%"   # 1 preserved / 2 baseline passed = 50.0%
    assert len(comparison.test_comparisons) == 3
