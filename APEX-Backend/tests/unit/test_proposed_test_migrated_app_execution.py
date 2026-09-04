"""Unit tests for Proposed Test Case execution against Migrated Application."""

import json
import shutil
import tempfile
from pathlib import Path
import pytest

from app.application.use_cases.proposed_tests.proposed_test_executor import (
    ProposedTestExecutor,
    resolve_migrated_app_url,
)
from app.domain.models.proposed_test_models import (
    ApiTestSpec,
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
    UiTestSpec,
)


@pytest.fixture
def temp_migrated_repo():
    temp_dir = tempfile.mkdtemp()
    repo_path = Path(temp_dir) / "migrated_repo"
    repo_path.mkdir(parents=True, exist_ok=True)

    # Create dummy application.properties with custom port
    prop_file = repo_path / "application.properties"
    prop_file.write_text("server.port=8085\nspring.application.name=migrated-app\n", encoding="utf-8")

    yield repo_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_resolve_migrated_app_url(temp_migrated_repo):
    """Verify that the migrated application port (e.g. 8085) is resolved from application.properties."""
    resolved_url = resolve_migrated_app_url(temp_migrated_repo)
    assert resolved_url == "http://localhost:8085"


def test_api_test_execution_against_migrated_app(temp_migrated_repo, tmp_path):
    """Verify that API tests execute against the resolved migrated base URL and record request/response trace."""
    executor = ProposedTestExecutor(
        job_id="mig-job-123",
        evidence_dir=tmp_path / "evidence",
        base_url="http://localhost:8085",
    )

    api_test = ProposedTestCase(
        id="PTC-001",
        title="Verify GET /api/attendance",
        description="Query attendance logs",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="AttendanceController",
        reason="Check attendance",
        expected_result="200 OK",
        status=ProposedTestStatus.PROPOSED,
        api_spec=ApiTestSpec(
            method="GET",
            endpoint="/api/attendance",
            expected_status=200,
        ),
    )

    res = executor.execute_test(api_test, repo_dir=temp_migrated_repo)
    assert res.status == ProposedTestStatus.PASSED
    assert res.actual_status_code == 200

    # Verify api_trace.json contains target_url
    trace_file = tmp_path / "evidence" / "PTC-001" / "api_trace.json"
    assert trace_file.exists()
    trace_data = json.loads(trace_file.read_text(encoding="utf-8"))
    assert trace_data["target_url"] == "http://localhost:8085/api/attendance"
    assert trace_data["method"] == "GET"


def test_ui_test_execution_evidence_against_migrated_app(temp_migrated_repo, tmp_path):
    """Verify that UI tests generate visual screenshot & video evidence referencing the migrated URL."""
    executor = ProposedTestExecutor(
        job_id="mig-job-123",
        evidence_dir=tmp_path / "evidence",
        base_url="http://localhost:8085",
    )

    ui_test = ProposedTestCase(
        id="PTC-002",
        title="Verify User Login Workflow",
        description="Login page test",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="AuthController",
        reason="Login validation",
        expected_result="Redirect to dashboard",
        status=ProposedTestStatus.PROPOSED,
        ui_spec=UiTestSpec(target_route="/login"),
    )

    res = executor.execute_test(ui_test, repo_dir=temp_migrated_repo)
    assert res.status == ProposedTestStatus.PASSED
    assert res.evidence.screenshot_available is True
    assert res.evidence.video_available is True

    # Verify visual screenshot SVG contains the target migrated URL
    screenshot_file = tmp_path / "evidence" / "PTC-002" / "screenshot.svg"
    assert screenshot_file.exists()
    svg_text = screenshot_file.read_text(encoding="utf-8")
    assert "http://localhost:8085/login" in svg_text
