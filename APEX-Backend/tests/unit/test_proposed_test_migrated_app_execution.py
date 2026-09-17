"""Unit tests for Proposed Test Case execution against Migrated Application."""

import http.server
import json
import shutil
import socketserver
import tempfile
import threading
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


class MigratedAppHandler(http.server.SimpleHTTPRequestHandler):
    """Simple HTTP server simulating a running migrated Spring Boot / React application."""

    def do_GET(self):
        if self.path.startswith("/api/attendance"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "records": [1, 2, 3]}')
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Migrated Application - Login</title></head>
        <body style="background:#0f172a; color:#fff; font-family:sans-serif; padding:40px;">
            <h1>Migrated Application Portal</h1>
            <div id="login-container">
                <form id="login-form">
                    <label>Username: <input type="text" name="username" id="username" value="admin" /></label><br/><br/>
                    <label>Password: <input type="password" name="password" id="password" value="secret" /></label><br/><br/>
                    <button type="submit" id="submit-btn" class="btn-primary">Sign In</button>
                </form>
            </div>
            <div id="dashboard" style="margin-top:20px;">
                <p>Welcome to the Migrated Dashboard</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Suppress console log noise during testing


@pytest.fixture(scope="module")
def running_migrated_server():
    """Starts a live HTTP server in a background thread to act as the migrated application."""
    server = socketserver.TCPServer(("127.0.0.1", 0), MigratedAppHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


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


def test_api_test_execution_against_migrated_app(running_migrated_server, tmp_path):
    """Verify that API tests execute against the resolved migrated base URL and record request/response trace."""
    executor = ProposedTestExecutor(
        job_id="mig-job-123",
        evidence_dir=tmp_path / "evidence",
        base_url=running_migrated_server,
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

    res = executor.execute_test(api_test)
    assert res.status == ProposedTestStatus.PASSED
    assert res.actual_status_code == 200

    # Verify api_trace.json contains target_url
    trace_file = tmp_path / "evidence" / "PTC-001" / "api_trace.json"
    assert trace_file.exists()
    trace_data = json.loads(trace_file.read_text(encoding="utf-8"))
    assert trace_data["target_url"] == f"{running_migrated_server}/api/attendance"
    assert trace_data["method"] == "GET"


def test_ui_test_execution_with_real_playwright_and_actual_png_screenshot(running_migrated_server, tmp_path):
    """Verify real Playwright Chromium browser execution against running migrated app captures real PNG screenshot."""
    evidence_dir = tmp_path / "evidence"
    executor = ProposedTestExecutor(
        job_id="mig-job-real-ui",
        evidence_dir=evidence_dir,
        base_url=running_migrated_server,
    )

    ui_test = ProposedTestCase(
        id="PTC-REAL-UI-001",
        title="Verify User Login Workflow",
        description="Login page test with real Playwright browser",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="AuthController",
        reason="Login validation",
        expected_result="Redirect to dashboard",
        status=ProposedTestStatus.PROPOSED,
        ui_spec=UiTestSpec(
            target_route="/login",
            input_fields=[{"name": "username", "type": "text"}, {"name": "password", "type": "password"}],
            actions=["click submit button"],
            expected_elements=["#login-container", "#dashboard"],
        ),
    )

    res = executor.execute_test(ui_test)
    assert res.status == ProposedTestStatus.PASSED
    assert res.error is None
    assert res.evidence.screenshot_available is True
    assert res.evidence.screenshot_url == f"/api/v1/migration/mig-job-real-ui/proposed-tests/evidence/{ui_test.id}/screenshot.png"

    # Verify actual PNG screenshot exists and has authentic PNG magic bytes (\x89PNG\r\n\x1a\n)
    screenshot_file = evidence_dir / ui_test.id / "screenshot.png"
    assert screenshot_file.exists()
    screenshot_bytes = screenshot_file.read_bytes()
    assert len(screenshot_bytes) > 1000  # Real image, not empty or synthetic
    assert screenshot_bytes[:8] == b"\x89PNG\r\n\x1a\n", "Evidence screenshot must be a real binary PNG file"

    # Verify browser steps log
    log_file = evidence_dir / ui_test.id / "browser_steps.log"
    assert log_file.exists()
    log_content = log_file.read_text(encoding="utf-8")
    assert running_migrated_server in log_content
    assert "page.goto" in log_content
    assert "Captured real full-page PNG screenshot" in log_content


def test_ui_test_execution_infrastructure_unavailable_when_server_is_down(tmp_path):
    """Verify that when the migrated application is unreachable, status is FAILED with INFRASTRUCTURE_UNAVAILABLE."""
    evidence_dir = tmp_path / "evidence"
    # Port 59999 is typically unused and unreachable
    unreachable_url = "http://127.0.0.1:59999"
    executor = ProposedTestExecutor(
        job_id="mig-job-infra-fail",
        evidence_dir=evidence_dir,
        base_url=unreachable_url,
    )

    ui_test = ProposedTestCase(
        id="PTC-INFRA-001",
        title="Verify Login with Unreachable Server",
        description="Expect infrastructure failure",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="AuthController",
        reason="Server downtime check",
        expected_result="Connection failure detected",
        status=ProposedTestStatus.PROPOSED,
        ui_spec=UiTestSpec(target_route="/login"),
    )

    res = executor.execute_test(ui_test)
    assert res.status == ProposedTestStatus.FAILED
    assert res.error_type == "INFRASTRUCTURE_UNAVAILABLE"
    assert "unreachable" in res.error.lower()
    assert res.evidence.screenshot_available is False


def test_ui_test_execution_fails_with_functional_failure_on_missing_element(running_migrated_server, tmp_path):
    """Verify that when the app is reachable but an expected DOM assertion fails, status is FAILED with FUNCTIONAL_FAILURE."""
    evidence_dir = tmp_path / "evidence"
    executor = ProposedTestExecutor(
        job_id="mig-job-func-fail",
        evidence_dir=evidence_dir,
        base_url=running_migrated_server,
    )

    ui_test = ProposedTestCase(
        id="PTC-FUNC-FAIL-001",
        title="Verify Missing Element Fails Assertion",
        description="Test checking for non-existent DOM element",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="AuthController",
        reason="Negative DOM assertion",
        expected_result="Element should exist",
        status=ProposedTestStatus.PROPOSED,
        ui_spec=UiTestSpec(
            target_route="/login",
            expected_elements=["#nonexistent-checkout-modal-element-xyz"],
        ),
    )

    res = executor.execute_test(ui_test)
    assert res.status == ProposedTestStatus.FAILED
    assert res.error_type == "FUNCTIONAL_FAILURE"
    assert "was not visible in page DOM" in res.error


def test_proposed_tests_persisted_without_auto_run_and_executed_on_demand(running_migrated_server, tmp_path, monkeypatch):
    """Verify that Proposed Tests remain stored in PROPOSED state and execute only on explicit on-demand call."""
    from unittest.mock import patch
    from app.application.use_cases.proposed_tests.proposed_test_service import ProposedTestService
    from app.infrastructure.workspace.workspace_paths import WorkspacePaths

    job_id = "job-on-demand-test"
    job_dir = tmp_path / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    class MockWorkspacePaths:
        def __init__(self, j_id):
            self.job_id = j_id
            self.job_dir = job_dir
            self.migrated_repo_dir = job_dir / "migrated_repo"
            self.original_repo_dir = job_dir / "original_repo"
            self.brd_dir = job_dir / "brd"
            self.migration_report_path = job_dir / "migration-report.json"

    monkeypatch.setattr("app.application.use_cases.proposed_tests.proposed_test_service.WorkspacePaths", MockWorkspacePaths)

    service = ProposedTestService()
    test_cases = [
        ProposedTestCase(
            id="PTC-ON-DEMAND-001",
            title="Verify GET /api/attendance",
            description="Attendance API endpoint",
            type=ProposedTestType.API,
            priority=ProposedTestPriority.HIGH,
            source="AttendanceController",
            reason="Verify attendance",
            expected_result="200 OK",
            status=ProposedTestStatus.PROPOSED,
            api_spec=ApiTestSpec(
                method="GET",
                endpoint="/api/attendance",
                expected_status=200,
            ),
        )
    ]
    service._save_proposals(job_id, test_cases)

    # 1. Verify tests are stored in PROPOSED status and status is IDLE before execution
    loaded_tests = service.get_proposed_tests(job_id)
    assert len(loaded_tests) == 1
    assert loaded_tests[0].status == ProposedTestStatus.PROPOSED

    status_data = service.get_status(job_id)
    assert len(status_data["proposals"]) == 1
    assert status_data["proposals"][0]["status"] == "PROPOSED"

    # 2. Trigger on-demand execution for selected test IDs
    with patch("app.application.use_cases.proposed_tests.proposed_test_executor.resolve_migrated_app_url", return_value=running_migrated_server):
        res = service.run_approved_tests(job_id, test_ids=["PTC-ON-DEMAND-001"])
        assert res["status"] == "RUNNING"
        assert res["total_approved"] == 1


