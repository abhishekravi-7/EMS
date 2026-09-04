"""Unit and Integration Tests for Proposed Test Cases Allure Reporting."""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.application.use_cases.proposed_tests.proposed_test_allure_reporter import (
    ProposedTestAllureReporter,
    sanitize_headers,
)
from app.application.use_cases.proposed_tests.proposed_test_executor import ProposedTestExecutor
from app.domain.models.proposed_test_models import (
    ApiTestSpec,
    ExecutionEvidence,
    ExecutionResult,
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
    UiTestSpec,
)


@pytest.fixture
def temp_job_environment(monkeypatch):
    """Creates an isolated temporary job directory environment for WorkspacePaths."""
    temp_dir = tempfile.mkdtemp()
    job_id = "test-allure-job-123"
    job_path = Path(temp_dir) / job_id
    job_path.mkdir(parents=True, exist_ok=True)

    class MockWorkspacePaths:
        def __init__(self, jid: str):
            self.job_id = jid
            self.job_dir = job_path
            self.migrated_repo_dir = job_path / "migrated"
            self.original_repo_dir = job_path / "original"

    monkeypatch.setattr(
        "app.application.use_cases.proposed_tests.proposed_test_allure_reporter.WorkspacePaths",
        MockWorkspacePaths,
    )
    monkeypatch.setattr(
        "app.application.use_cases.proposed_tests.proposed_test_service.WorkspacePaths",
        MockWorkspacePaths,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.proposed_test_controller.WorkspacePaths",
        MockWorkspacePaths,
    )

    yield job_id, job_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_sanitize_headers():
    """Verify sensitive headers are securely redacted from Allure report artifacts."""
    raw_headers = {
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret",
        "Cookie": "session_id=abcdef123456; theme=dark",
        "X-API-Key": "sk_live_987654321",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Custom-Token": "secret-value",
        "User-Agent": "Playwright/1.41.0",
    }
    sanitized = sanitize_headers(raw_headers)

    assert sanitized["Authorization"] == "[REDACTED]"
    assert sanitized["Cookie"] == "[REDACTED]"
    assert sanitized["X-API-Key"] == "[REDACTED]"
    assert sanitized["Custom-Token"] == "[REDACTED]"
    assert sanitized["Content-Type"] == "application/json"
    assert sanitized["Accept"] == "application/json"
    assert sanitized["User-Agent"] == "Playwright/1.41.0"


def test_proposed_test_executor_api_validation(temp_job_environment):
    """Verify ProposedTestExecutor accurately checks expected vs actual status codes and sanitizes headers."""
    job_id, job_path = temp_job_environment
    evidence_dir = job_path / "proposed-tests" / "evidence"
    executor = ProposedTestExecutor(job_id=job_id, evidence_dir=evidence_dir)

    # 1. Successful 200 API test
    passed_api_test = ProposedTestCase(
        id="PTC-API-001",
        title="Verify GET /api/attendance returns 200 success",
        description="Fetch attendance record list",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="AttendanceController",
        reason="Verify attendance query endpoint",
        expected_result="HTTP 200 with record array",
        status=ProposedTestStatus.READY,
        api_spec=ApiTestSpec(
            method="GET",
            endpoint="/api/attendance",
            expected_status=200,
            headers={"Authorization": "Bearer secret-token", "Accept": "application/json"},
            expected_response={"status": "success", "count": 5},
        ),
    )

    res_pass = executor.execute_test(passed_api_test)
    assert res_pass.status == ProposedTestStatus.PASSED
    assert res_pass.actual_status_code == 200
    assert res_pass.error is None
    assert (evidence_dir / "PTC-API-001" / "api_trace.json").exists()

    trace_data = json.loads((evidence_dir / "PTC-API-001" / "api_trace.json").read_text(encoding="utf-8"))
    assert trace_data["request_headers"]["Authorization"] == "[REDACTED]"
    assert trace_data["request_headers"]["Accept"] == "application/json"

    # 2. Failed API test (e.g. 500 error when 200 expected)
    failed_api_test = ProposedTestCase(
        id="PTC-API-002",
        title="Verify POST /api/attendance/mark returns 200",
        description="Mark attendance record",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="AttendanceController",
        reason="Verify attendance creation",
        expected_result="HTTP 200 OK",
        status=ProposedTestStatus.READY,
        api_spec=ApiTestSpec(
            method="POST",
            endpoint="/api/attendance/mark",
            expected_status=200,
            headers={"Authorization": "Bearer secret-token"},
            expected_response={"status": "success"},
        ),
    )
    # Inject actual status 500 into spec
    setattr(failed_api_test.api_spec, "actual_status", 500)

    res_fail = executor.execute_test(failed_api_test)
    assert res_fail.status == ProposedTestStatus.FAILED
    assert res_fail.actual_status_code == 500
    assert "status code mismatch" in res_fail.error.lower()


def test_proposed_test_executor_ui_evidence(temp_job_environment):
    """Verify ProposedTestExecutor generates visual screenshots, step logs, and video placeholders for UI tests."""
    job_id, job_path = temp_job_environment
    evidence_dir = job_path / "proposed-tests" / "evidence"
    executor = ProposedTestExecutor(job_id=job_id, evidence_dir=evidence_dir)

    ui_test = ProposedTestCase(
        id="PTC-UI-001",
        title="Verify user login page rendering and submission",
        description="Validate login form",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="AuthController",
        reason="Verify UI login flow",
        expected_result="Dashboard visible",
        status=ProposedTestStatus.READY,
        ui_spec=UiTestSpec(target_route="/login"),
    )

    res_ui = executor.execute_test(ui_test)
    assert res_ui.status == ProposedTestStatus.PASSED
    assert res_ui.evidence.screenshot_available is True
    assert (evidence_dir / "PTC-UI-001" / "screenshot.svg").exists()
    assert (evidence_dir / "PTC-UI-001" / "browser_steps.log").exists()
    assert (evidence_dir / "PTC-UI-001" / "video.webm").exists()


def test_allure_results_and_html_generation(temp_job_environment):
    """Verify Allure results (*-result.json) and standalone HTML report generation."""
    job_id, job_path = temp_job_environment
    reporter = ProposedTestAllureReporter(job_id)
    reporter.clean_results()

    # Create 3 executed tests (1 LLM API, 1 BRD UI, 1 BRD API failed)
    test_1 = ProposedTestCase(
        id="PTC-LLM-001",
        title="Test GET /api/users",
        description="Fetch users list",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="UserController",
        reason="Verify users API",
        expected_result="200 OK",
        status=ProposedTestStatus.PASSED,
        generation_source="AI_GENERATED",
        api_spec=ApiTestSpec(method="GET", endpoint="/api/users", expected_status=200),
        execution_result=ExecutionResult(
            status=ProposedTestStatus.PASSED,
            actual_status_code=200,
            duration="0.08s",
            evidence=ExecutionEvidence(),
        ),
    )

    evidence_ui_dir = job_path / "proposed-tests" / "evidence" / "PTC-BRD-UI-001"
    evidence_ui_dir.mkdir(parents=True, exist_ok=True)
    (evidence_ui_dir / "screenshot.svg").write_text("<svg>test screenshot</svg>", encoding="utf-8")
    (evidence_ui_dir / "browser_steps.log").write_text("Playwright logs", encoding="utf-8")

    test_2 = ProposedTestCase(
        id="PTC-BRD-UI-001",
        title="Verify Dashboard Page Navigation",
        description="Check dashboard elements",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.MEDIUM,
        source="BRD Document",
        reason="Verify BRD Req #4",
        expected_result="Dashboard visible",
        status=ProposedTestStatus.PASSED,
        generation_source="BRD_DOCUMENT",
        ui_spec=UiTestSpec(target_route="/dashboard"),
        execution_result=ExecutionResult(
            status=ProposedTestStatus.PASSED,
            duration="0.35s",
            evidence=ExecutionEvidence(
                screenshot_available=True,
                screenshot_url=f"/api/v1/migration/{job_id}/proposed-tests/evidence/PTC-BRD-UI-001/screenshot.svg",
            ),
        ),
    )

    test_3 = ProposedTestCase(
        id="PTC-BRD-API-002",
        title="Verify POST /api/payments/process",
        description="Process payment transaction",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="BRD Document",
        reason="Verify BRD Req #9",
        expected_result="200 Processed",
        status=ProposedTestStatus.FAILED,
        generation_source="BRD_DOCUMENT",
        api_spec=ApiTestSpec(method="POST", endpoint="/api/payments/process", expected_status=200),
        execution_result=ExecutionResult(
            status=ProposedTestStatus.FAILED,
            actual_status_code=500,
            duration="0.12s",
            error="HTTP status code mismatch: expected 200, received 500",
            stack_trace="AssertionError: HTTP status code mismatch",
            evidence=ExecutionEvidence(),
        ),
    )

    tests = [test_1, test_2, test_3]

    # Generate Allure 2 JSON files
    results_dir = reporter.generate_allure_results(tests, selected_sources=["LLM", "FUNCTIONAL_DOC"])
    assert results_dir.exists()

    result_files = list(results_dir.glob("*-result.json"))
    assert len(result_files) == 3

    # Check contents of result JSONs
    results_map = {}
    for rf in result_files:
        data = json.loads(rf.read_text(encoding="utf-8"))
        results_map[data["parameters"][0]["value"]] = data  # key by type or name

    # Generate Standalone Allure HTML Report
    report_dir = reporter.generate_html_report(tests, selected_sources=["LLM", "FUNCTIONAL_DOC"])
    index_file = report_dir / "index.html"
    assert index_file.exists()

    html_content = index_file.read_text(encoding="utf-8")
    assert "ALLURE REPORT" in html_content
    assert "PTC-LLM-001" in html_content
    assert "PTC-BRD-UI-001" in html_content
    assert "PTC-BRD-API-002" in html_content
    assert "67% Passed" in html_content  # 2 passed out of 3 total


def test_re_run_allure_isolation(temp_job_environment):
    """Verify re-running tests isolates and cleans previous Allure results."""
    job_id, job_path = temp_job_environment
    reporter = ProposedTestAllureReporter(job_id)

    # Run 1: 1 test
    t1 = ProposedTestCase(
        id="PTC-001",
        title="Test 1",
        description="Desc 1",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="API",
        reason="Reason 1",
        expected_result="200 OK",
        status=ProposedTestStatus.PASSED,
        generation_source="AI_GENERATED",
        execution_result=ExecutionResult(status=ProposedTestStatus.PASSED, duration="0.1s"),
    )
    reporter.clean_results()
    reporter.generate_allure_results([t1])
    assert len(list(reporter.results_dir.glob("*-result.json"))) == 1

    # Run 2: Fresh run with 2 different tests
    t2 = ProposedTestCase(
        id="PTC-002",
        title="Test 2",
        description="Desc 2",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="API",
        reason="Reason 2",
        expected_result="200 OK",
        status=ProposedTestStatus.PASSED,
        generation_source="AI_GENERATED",
        execution_result=ExecutionResult(status=ProposedTestStatus.PASSED, duration="0.1s"),
    )
    t3 = ProposedTestCase(
        id="PTC-003",
        title="Test 3",
        description="Desc 3",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="API",
        reason="Reason 3",
        expected_result="200 OK",
        status=ProposedTestStatus.PASSED,
        generation_source="AI_GENERATED",
        execution_result=ExecutionResult(status=ProposedTestStatus.PASSED, duration="0.1s"),
    )

    reporter.clean_results()
    reporter.generate_allure_results([t2, t3])

    current_files = list(reporter.results_dir.glob("*-result.json"))
    assert len(current_files) == 2

    # Make sure PTC-001 is NOT present in Run 2 results
    loaded_names = [json.loads(f.read_text(encoding="utf-8"))["name"] for f in current_files]
    assert any("PTC-002" in n for n in loaded_names)
    assert any("PTC-003" in n for n in loaded_names)
    assert not any("PTC-001" in n for n in loaded_names)
