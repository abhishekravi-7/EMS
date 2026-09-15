"""Unit and integration tests for Proposed Functional API Test execution via Playwright APIRequestContext.

Validates:
1. Proposed API Test -> Playwright APIRequestContext -> Migrated application -> Actual HTTP response -> Contract/schema validation -> Real PASS/FAIL.
2. Regression test: GET /auth/logout returning HTTP 200 with unexpected HTML login redirect page is marked as FAILED (FUNCTIONAL_FAILURE), not PASSED.
3. Path variable resolution: /admin/users/{id} is resolved to valid runtime test data (e.g. /admin/users/123) before sending the request.
4. Schema & business response fields validation.
5. Sensitive data and authentication headers redaction in api_trace.json.
"""

import http.server
import json
import socketserver
import threading
from pathlib import Path
import pytest

from app.application.use_cases.proposed_tests.proposed_test_executor import ProposedTestExecutor
from app.domain.models.proposed_test_models import (
    ApiTestSpec,
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
)


class MockMigratedApiServerHandler(http.server.SimpleHTTPRequestHandler):
    """Simulates a running migrated application with both REST API endpoints and auth redirect behaviors."""

    def do_GET(self):
        url_path = self.path.split("?")[0]

        # Case 1: /auth/logout returning HTTP 200 with HTML login page (the regression scenario)
        if url_path == "/auth/logout":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <!DOCTYPE html>
            <html>
            <head><title>Sign In - Authentication Required</title></head>
            <body>
                <h2>Please sign in to continue</h2>
                <form action="/login" method="post">
                    <input type="text" name="username" />
                    <input type="password" name="password" />
                    <button type="submit">Sign In</button>
                </form>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # Case 2: Proper REST logout endpoint returning JSON
        if url_path == "/api/auth/logout":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            body = json.dumps({"status": "logged_out", "message": "Session terminated"})
            self.wfile.write(body.encode("utf-8"))
            return

        # Case 3: /admin/users/123 (Path parameter resolved)
        if url_path.startswith("/admin/users/"):
            user_id = url_path.split("/")[-1]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            body = json.dumps({
                "userId": user_id,
                "username": f"user_{user_id}",
                "email": f"user{user_id}@example.com",
                "role": "ADMIN",
            })
            self.wfile.write(body.encode("utf-8"))
            return

        # Case 4: Schema mismatch endpoint (missing expected field)
        if url_path == "/api/v1/profile":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            # Missing "email" and "role"
            body = json.dumps({"name": "Alex"})
            self.wfile.write(body.encode("utf-8"))
            return

        # Default 404
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        url_path = self.path.split("?")[0]

        if url_path == "/api/v1/orders":
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {"orderId": "ORD-9999", "status": "CREATED", "token": "secret-token-12345"}
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="module")
def migrated_api_server():
    """Launches mock migrated application HTTP server."""
    server = socketserver.TCPServer(("127.0.0.1", 0), MockMigratedApiServerHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def test_auth_logout_html_response_fails_functional_validation(migrated_api_server, tmp_path):
    """
    Regression Test: /auth/logout returns HTTP 200 with an HTML login page.
    The test must NOT pass merely because HTTP status is 200.
    It MUST detect the HTML login redirect mismatch and fail functionally.
    """
    evidence_dir = tmp_path / "evidence"
    executor = ProposedTestExecutor(
        job_id="test-job-logout-regression",
        evidence_dir=evidence_dir,
        base_url=migrated_api_server,
    )

    logout_test = ProposedTestCase(
        id="PTC-LOGOUT-001",
        title="Verify GET /auth/logout returns success response",
        description="Verify logout endpoint returns successful termination API contract",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="AuthController",
        reason="Security test",
        expected_result="200 OK with logged out API response",
        api_spec=ApiTestSpec(
            method="GET",
            endpoint="/auth/logout",
            headers={"Accept": "application/json"},
            expected_status=200,
            expected_response={"status": "logged_out"},
        ),
    )

    result = executor.execute_test(logout_test)

    # Must FAIL functionally despite HTTP 200 status code
    assert result.status == ProposedTestStatus.FAILED
    assert result.actual_status_code == 200
    assert result.error_type == "FUNCTIONAL_FAILURE"
    assert "returned HTML" in result.error or "Functional contract mismatch" in result.error
    assert result.assertions_failed > 0

    # Verify api_trace.json records the Playwright client and HTML response
    trace_file = evidence_dir / "PTC-LOGOUT-001" / "api_trace.json"
    assert trace_file.exists()
    trace_data = json.loads(trace_file.read_text(encoding="utf-8"))
    assert trace_data["client"] == "Playwright APIRequestContext"
    assert trace_data["actual_status"] == 200
    assert trace_data["passed"] is False


def test_path_parameter_resolution_before_playwright_request(migrated_api_server, tmp_path):
    """
    Verifies that path parameters such as /admin/users/{id} are resolved
    to concrete test data (e.g. /admin/users/123) before the Playwright request is sent.
    """
    evidence_dir = tmp_path / "evidence"
    executor = ProposedTestExecutor(
        job_id="test-job-path-params",
        evidence_dir=evidence_dir,
        base_url=migrated_api_server,
    )

    user_test = ProposedTestCase(
        id="PTC-USER-002",
        title="Verify GET /admin/users/{id} returns user detail",
        description="Fetch user by ID",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="AdminUserController",
        reason="Check admin user retrieval",
        expected_result="200 OK with user object",
        test_data={"path_params": {"id": "123"}},
        api_spec=ApiTestSpec(
            method="GET",
            endpoint="/admin/users/{id}",
            expected_status=200,
            expected_response={"userId": "123", "role": "ADMIN"},
        ),
    )

    result = executor.execute_test(user_test)

    assert result.status == ProposedTestStatus.PASSED
    assert result.actual_status_code == 200
    assert result.actual_response.get("userId") == "123"
    assert result.actual_response.get("role") == "ADMIN"

    # Verify api_trace.json shows the resolved URL
    trace_file = evidence_dir / "PTC-USER-002" / "api_trace.json"
    assert trace_file.exists()
    trace_data = json.loads(trace_file.read_text(encoding="utf-8"))
    assert trace_data["raw_endpoint"] == "/admin/users/{id}"
    assert trace_data["resolved_endpoint"] == "/admin/users/123"
    assert "123" in trace_data["target_url"]
    assert "{id}" not in trace_data["target_url"]


def test_rest_api_valid_json_contract_passes(migrated_api_server, tmp_path):
    """
    Verifies that a valid REST endpoint returning JSON matching the contract
    executes with Playwright APIRequestContext and passes all assertions.
    """
    evidence_dir = tmp_path / "evidence"
    executor = ProposedTestExecutor(
        job_id="test-job-valid-rest",
        evidence_dir=evidence_dir,
        base_url=migrated_api_server,
    )

    api_test = ProposedTestCase(
        id="PTC-REST-003",
        title="Verify GET /api/auth/logout returns valid JSON",
        description="Verify REST logout API",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.MEDIUM,
        source="AuthController",
        reason="REST logout check",
        expected_result="200 OK",
        api_spec=ApiTestSpec(
            method="GET",
            endpoint="/api/auth/logout",
            expected_status=200,
            expected_response={"status": "logged_out"},
        ),
    )

    result = executor.execute_test(api_test)

    assert result.status == ProposedTestStatus.PASSED
    assert result.actual_status_code == 200
    assert result.actual_response.get("status") == "logged_out"
    assert result.error is None


def test_schema_and_business_response_mismatch_fails_functional_validation(migrated_api_server, tmp_path):
    """
    Verifies that when HTTP status matches 200, but required business response fields
    are missing, the test fails functional validation (not marked PASS based on status alone).
    """
    evidence_dir = tmp_path / "evidence"
    executor = ProposedTestExecutor(
        job_id="test-job-schema-mismatch",
        evidence_dir=evidence_dir,
        base_url=migrated_api_server,
    )

    profile_test = ProposedTestCase(
        id="PTC-PROFILE-004",
        title="Verify GET /api/v1/profile returns complete schema",
        description="Expects email and role fields in response",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="ProfileController",
        reason="Profile schema test",
        expected_result="200 OK with email and role",
        api_spec=ApiTestSpec(
            method="GET",
            endpoint="/api/v1/profile",
            expected_status=200,
            expected_response={"name": "Alex", "email": "alex@example.com", "role": "USER"},
        ),
    )

    result = executor.execute_test(profile_test)

    # Must FAIL because email and role are missing from the server payload
    assert result.status == ProposedTestStatus.FAILED
    assert result.actual_status_code == 200
    assert result.error_type == "FUNCTIONAL_FAILURE"
    assert "missing expected field" in result.error
    assert result.assertions_failed > 0


def test_sensitive_data_sanitization_in_evidence(migrated_api_server, tmp_path):
    """
    Verifies that authorization headers, tokens, cookies, and passwords
    are sanitized/redacted in api_trace.json evidence.
    """
    evidence_dir = tmp_path / "evidence"
    executor = ProposedTestExecutor(
        job_id="test-job-sanitization",
        evidence_dir=evidence_dir,
        base_url=migrated_api_server,
    )

    order_test = ProposedTestCase(
        id="PTC-SEC-005",
        title="Create Order Securely",
        description="POST with auth header and sensitive body",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="OrderController",
        reason="Security and data redaction check",
        expected_result="201 Created",
        api_spec=ApiTestSpec(
            method="POST",
            endpoint="/api/v1/orders",
            headers={"Authorization": "Bearer super-secret-jwt-token-12345", "Cookie": "session_id=abc987"},
            request_body={"item": "Gadget", "password": "user_secret_password"},
            expected_status=201,
            expected_response={"orderId": "ORD-9999", "status": "CREATED"},
        ),
    )

    result = executor.execute_test(order_test)
    assert result.status == ProposedTestStatus.PASSED

    trace_file = evidence_dir / "PTC-SEC-005" / "api_trace.json"
    assert trace_file.exists()
    trace_data = json.loads(trace_file.read_text(encoding="utf-8"))

    # Headers sanitized
    assert trace_data["request_headers"]["Authorization"] == "[REDACTED]"
    assert trace_data["request_headers"]["Cookie"] == "[REDACTED]"

    # Request and response bodies sanitized
    assert trace_data["request_body"]["password"] == "[REDACTED]"
    assert trace_data["response_body"]["token"] == "[REDACTED]"


def test_econnrefused_results_in_infrastructure_unavailable(tmp_path):
    """
    Regression Test: If Playwright APIRequestContext encounters ECONNREFUSED / server unreachable,
    it must NOT fallback to a synthetic HTTP 200/PASSED response.
    It MUST return status=FAILED with error_type=INFRASTRUCTURE_UNAVAILABLE.
    """
    evidence_dir = tmp_path / "evidence"
    # Unreachable port
    executor = ProposedTestExecutor(
        job_id="test-job-econnrefused",
        evidence_dir=evidence_dir,
        base_url="http://127.0.0.1:59997",
    )

    api_test = ProposedTestCase(
        id="PTC-CONN-006",
        title="Verify GET /api/v1/health returns 200",
        description="Health check against offline server",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="HealthController",
        reason="Infra check",
        expected_result="200 OK",
        api_spec=ApiTestSpec(
            method="GET",
            endpoint="/api/v1/health",
            expected_status=200,
        ),
    )

    result = executor.execute_test(api_test)

    # Must fail with INFRASTRUCTURE_UNAVAILABLE
    assert result.status == ProposedTestStatus.FAILED
    assert result.error_type == "INFRASTRUCTURE_UNAVAILABLE"
    assert result.assertions_passed == 0
    assert result.assertions_failed == 1
    assert "unreachable" in result.error.lower() or "connection failed" in result.error.lower()


def test_rest_endpoints_not_converted_to_ui_workflows(tmp_path):
    """
    Verifies that the analyzer distinguishes REST APIs from UI routes and
    does NOT convert endpoints like /api/attendance, /api/attendance/history into UI workflows.
    """
    from app.application.use_cases.proposed_tests.proposed_test_analyzer import ProposedTestAnalyzer
    from app.application.use_cases.proposed_tests.proposed_test_generator import ProposedTestGenerator

    repo_dir = tmp_path / "app_repo"
    src_dir = repo_dir / "src" / "main" / "java" / "com" / "example"
    src_dir.mkdir(parents=True, exist_ok=True)

    (src_dir / "AttendanceController.java").write_text(
        """
        package com.example;
        import org.springframework.web.bind.annotation.*;
        @RestController
        @RequestMapping("/api/attendance")
        public class AttendanceController {
            @GetMapping
            public Object list() { return null; }
            @GetMapping("/history")
            public Object history() { return null; }
            @GetMapping("/send-email-html")
            public Object sendEmail() { return null; }
        }
        """,
        encoding="utf-8",
    )

    analyzer = ProposedTestAnalyzer(repo_dir)
    analysis = analyzer.analyze()

    # Verify endpoints discovered as API
    endpoints = analysis.get("endpoints", [])
    ep_paths = [e["endpoint"] for e in endpoints]
    assert "/api/attendance" in ep_paths
    assert "/api/attendance/history" in ep_paths
    assert "/api/attendance/send-email-html" in ep_paths

    # Verify UI workflows do NOT contain any /api/attendance routes
    ui_workflows = analysis.get("ui_workflows", [])
    ui_routes = [u.get("route") for u in ui_workflows]
    for r in ui_routes:
        assert not r.startswith("/api/attendance"), f"Found invalid UI route converted from REST API: {r}"

    # Generate proposals and verify no UI proposals for /api/attendance
    generator = ProposedTestGenerator(analysis)
    proposals = generator.generate()
    for p in proposals:
        if p.type == ProposedTestType.UI and p.ui_spec:
            assert not p.ui_spec.target_route.startswith("/api/attendance")


def test_ui_validator_rejects_api_endpoints_as_ui_routes(tmp_path):
    """
    Verifies that ProposedTestValidator marks any UI test targeting /api/... as INVALID
    with playwright_executable=False.
    """
    from app.application.use_cases.proposed_tests.proposed_test_validator import ProposedTestValidator
    from app.domain.models.proposed_test_models import UiTestSpec, ValidationStatus

    validator = ProposedTestValidator(tmp_path)

    invalid_ui_test = ProposedTestCase(
        id="PTC-UI-INVALID-007",
        title="Invalid UI test on API endpoint",
        description="Mistakenly targeting REST endpoint as UI page",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.LOW,
        source="AttendanceController",
        reason="Mistaken test",
        expected_result="Rendered",
        ui_spec=UiTestSpec(target_route="/api/attendance/history"),
    )

    res = validator.validate_test_case(invalid_ui_test)
    assert res.status == ValidationStatus.INVALID
    assert res.playwright_executable is False
    assert "REST API endpoint" in res.issue

