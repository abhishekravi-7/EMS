"""Unit and Integration Tests for Functional Testing Framework Selection and Execution Gate."""

import json
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi import HTTPException

from app.application.use_cases.proposed_tests.proposed_test_service import ProposedTestService
from app.domain.models.proposed_test_models import (
    ApiTestSpec,
    ExecutionResult,
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
    ProposedTestValidationResult,
    UiTestSpec,
    ValidationStatus,
)


@pytest.fixture
def temp_job_environment(monkeypatch):
    """Creates isolated temporary job storage."""
    temp_dir = tempfile.mkdtemp()
    job_id = "test-fw-job-123"
    job_path = Path(temp_dir) / job_id
    job_path.mkdir(parents=True, exist_ok=True)

    class MockWorkspacePaths:
        def __init__(self, jid: str):
            self.job_id = jid
            self.job_dir = job_path
            self.migrated_repo_dir = job_path / "migrated"
            self.original_repo_dir = job_path / "original"
            self.brd_dir = job_path / "brd"

    monkeypatch.setattr(
        "app.application.use_cases.proposed_tests.proposed_test_service.WorkspacePaths",
        MockWorkspacePaths,
    )
    monkeypatch.setattr(
        "app.application.use_cases.proposed_tests.proposed_test_allure_reporter.WorkspacePaths",
        MockWorkspacePaths,
    )

    yield job_id, job_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_framework_selection_playwright_enabled(temp_job_environment):
    """Verify that Playwright framework execution is enabled and starts."""
    job_id, job_path = temp_job_environment
    service = ProposedTestService()
    service._get_job_dir = lambda j: job_path

    # Save a valid test
    test = ProposedTestCase(
        id="PTC-001",
        title="Verify GET /api/attendance",
        description="Fetch attendance",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="AttendanceController",
        reason="Query",
        expected_result="200 OK",
        status=ProposedTestStatus.PROPOSED,
        generation_source="AI_GENERATED",
        api_spec=ApiTestSpec(method="GET", endpoint="/api/attendance"),
        validation=ProposedTestValidationResult(
            status=ValidationStatus.VALID,
            playwright_executable=True,
        ),
    )
    service._save_proposals(job_id, [test])

    res = service.run_approved_tests(job_id, sources=["LLM"], framework="PLAYWRIGHT")
    assert res["status"] == "RUNNING"
    assert res["total_approved"] == 1


def test_framework_selection_selenium_coming_soon(temp_job_environment):
    """Verify that attempting to execute with Selenium raises 'Selenium support is coming soon.'."""
    job_id, job_path = temp_job_environment
    service = ProposedTestService()
    service._get_job_dir = lambda j: job_path

    with pytest.raises(ValueError, match="Selenium support is coming soon."):
        service.run_approved_tests(job_id, sources=["LLM"], framework="SELENIUM")


def test_framework_selection_cypress_coming_soon(temp_job_environment):
    """Verify that attempting to execute with Cypress raises 'Cypress support is coming soon.'."""
    job_id, job_path = temp_job_environment
    service = ProposedTestService()
    service._get_job_dir = lambda j: job_path

    with pytest.raises(ValueError, match="Cypress support is coming soon."):
        service.run_approved_tests(job_id, sources=["LLM"], framework="CYPRESS")


def test_functional_classification_and_validation_gate(temp_job_environment):
    """Verify that LLM & Functional Doc tests are classified as functional, and hallucinated tests are blocked."""
    job_id, job_path = temp_job_environment
    service = ProposedTestService()
    service._get_job_dir = lambda j: job_path

    # 1. Valid LLM API test -> should run
    valid_llm_api = ProposedTestCase(
        id="PTC-LLM-API",
        title="Verify GET /api/attendance",
        description="Valid API",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="AttendanceController",
        reason="Query",
        expected_result="200 OK",
        status=ProposedTestStatus.PROPOSED,
        generation_source="AI_GENERATED",
        api_spec=ApiTestSpec(method="GET", endpoint="/api/attendance"),
        validation=ProposedTestValidationResult(status=ValidationStatus.VALID, playwright_executable=True),
    )

    # 2. Valid Functional Doc UI test -> should run
    valid_doc_ui = ProposedTestCase(
        id="PTC-BRD-UI",
        title="Verify Login Page Workflow",
        description="Valid UI",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="BRD Document",
        reason="Auth Req",
        expected_result="Dashboard visible",
        status=ProposedTestStatus.PROPOSED,
        generation_source="BRD_DOCUMENT",
        ui_spec=UiTestSpec(target_route="/login"),
        validation=ProposedTestValidationResult(status=ValidationStatus.VALID, playwright_executable=True),
    )

    # 3. Hallucinated LLM test (Payment) -> should be blocked by validation gate
    hallucinated_llm = ProposedTestCase(
        id="PTC-LLM-HALLUCINATED",
        title="Verify POST /api/payment/checkout",
        description="Non-existent payment API",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="PaymentController",
        reason="Hallucinated",
        expected_result="200 OK",
        status=ProposedTestStatus.PROPOSED,
        generation_source="AI_GENERATED",
        api_spec=ApiTestSpec(method="POST", endpoint="/api/payment/checkout"),
        validation=ProposedTestValidationResult(
            status=ValidationStatus.HALLUCINATED,
            playwright_executable=False,
            issue="No controller or endpoint in repository",
        ),
    )

    # 4. Non-functional invalid test -> should be blocked
    invalid_test = ProposedTestCase(
        id="PTC-INVALID",
        title="Verify code formatting pom.xml",
        description="Static check",
        type=ProposedTestType.UNIT,
        priority=ProposedTestPriority.LOW,
        source="Build",
        reason="Non-functional",
        expected_result="OK",
        status=ProposedTestStatus.PROPOSED,
        generation_source="AI_GENERATED",
        validation=ProposedTestValidationResult(
            status=ValidationStatus.INVALID,
            playwright_executable=False,
        ),
    )

    service._save_proposals(job_id, [valid_llm_api, valid_doc_ui, hallucinated_llm, invalid_test])

    # Run with LLM + Functional Doc selected
    res = service.run_approved_tests(job_id, sources=["LLM", "FUNCTIONAL_DOC"], framework="PLAYWRIGHT")
    assert res["status"] == "RUNNING"
    # Only the 2 valid functional tests (valid_llm_api, valid_doc_ui) should be passed to Playwright
    assert res["total_approved"] == 2
