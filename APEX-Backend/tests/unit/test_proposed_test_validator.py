"""Unit tests for Proposed Test Cases Source Code Validation Engine."""

from pathlib import Path
import pytest

from app.application.use_cases.proposed_tests.proposed_test_validator import ProposedTestValidator
from app.domain.models.proposed_test_models import (
    ApiTestSpec,
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
    UiTestSpec,
    UnitTestSpec,
    ValidationStatus,
)


@pytest.fixture
def sample_analysis_data():
    """Mock repository analysis data simulating an attendance management microservice."""
    return {
        "controllers": [
            {
                "name": "AttendanceController",
                "file": "com/company/attendance/AttendanceController.java",
                "base_path": "/api/attendance",
                "endpoints": [
                    {
                        "method": "GET",
                        "endpoint": "/api/attendance",
                        "handler": "getAttendanceList",
                        "file": "com/company/attendance/AttendanceController.java",
                        "class_name": "AttendanceController",
                    },
                    {
                        "method": "POST",
                        "endpoint": "/api/attendance/mark",
                        "handler": "markAttendance",
                        "file": "com/company/attendance/AttendanceController.java",
                        "class_name": "AttendanceController",
                    },
                    {
                        "method": "GET",
                        "endpoint": "/api/attendance/summary/{userId}",
                        "handler": "getAttendanceSummary",
                        "file": "com/company/attendance/AttendanceController.java",
                        "class_name": "AttendanceController",
                    },
                ],
            },
            {
                "name": "AuthController",
                "file": "com/company/auth/AuthController.java",
                "base_path": "/api/auth",
                "endpoints": [
                    {
                        "method": "POST",
                        "endpoint": "/api/auth/login",
                        "handler": "login",
                        "file": "com/company/auth/AuthController.java",
                        "class_name": "AuthController",
                    }
                ],
            },
        ],
        "endpoints": [
            {
                "method": "GET",
                "endpoint": "/api/attendance",
                "handler": "getAttendanceList",
                "file": "com/company/attendance/AttendanceController.java",
                "class_name": "AttendanceController",
            },
            {
                "method": "POST",
                "endpoint": "/api/attendance/mark",
                "handler": "markAttendance",
                "file": "com/company/attendance/AttendanceController.java",
                "class_name": "AttendanceController",
            },
            {
                "method": "GET",
                "endpoint": "/api/attendance/summary/{userId}",
                "handler": "getAttendanceSummary",
                "file": "com/company/attendance/AttendanceController.java",
                "class_name": "AttendanceController",
            },
            {
                "method": "POST",
                "endpoint": "/api/auth/login",
                "handler": "login",
                "file": "com/company/auth/AuthController.java",
                "class_name": "AuthController",
            },
        ],
        "services": [
            {"name": "AttendanceService", "file": "com/company/attendance/AttendanceService.java"},
            {"name": "WeeklyReportService", "file": "com/company/attendance/WeeklyReportService.java"},
        ],
        "ui_workflows": [
            {"route": "/login", "file": "src/pages/Login.tsx"},
            {"route": "/attendance/dashboard", "file": "src/pages/Dashboard.tsx"},
        ],
    }


def test_existing_api_validation(sample_analysis_data):
    """Verify that an existing API endpoint is correctly classified as VALID with repository evidence."""
    validator = ProposedTestValidator(Path("."), analysis_data=sample_analysis_data)

    test = ProposedTestCase(
        id="PTC-001",
        title="Verify GET /api/attendance returns success response",
        description="Fetch list of attendance logs",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="AttendanceController",
        reason="Test attendance retrieval",
        expected_result="HTTP 200 OK",
        status=ProposedTestStatus.PROPOSED,
        api_spec=ApiTestSpec(method="GET", endpoint="/api/attendance", expected_status=200),
    )

    result = validator.validate_test_case(test)
    assert result.status == ValidationStatus.VALID
    assert result.playwright_executable is True
    assert "AttendanceController.java" in (result.repository_evidence or "")
    assert result.issue is None


def test_hallucinated_api_validation(sample_analysis_data):
    """Verify that a hallucinated endpoint (e.g. payments/shopping cart) is flagged as HALLUCINATED."""
    validator = ProposedTestValidator(Path("."), analysis_data=sample_analysis_data)

    test = ProposedTestCase(
        id="PTC-002",
        title="Verify POST /api/payment/checkout creates payment",
        description="Process credit card checkout",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="PaymentController",
        reason="Verify payments",
        expected_result="HTTP 201 Created",
        status=ProposedTestStatus.PROPOSED,
        api_spec=ApiTestSpec(method="POST", endpoint="/api/payment/checkout", expected_status=201),
    )

    result = validator.validate_test_case(test)
    assert result.status == ValidationStatus.HALLUCINATED
    assert result.playwright_executable is False
    assert "No controller, service, or REST endpoint matching" in (result.issue or "")


def test_partially_valid_api_method_mismatch(sample_analysis_data):
    """Verify that an endpoint with mismatched HTTP method is classified as PARTIALLY_VALID."""
    validator = ProposedTestValidator(Path("."), analysis_data=sample_analysis_data)

    # Endpoint exists as GET, but proposed test asks for DELETE
    test = ProposedTestCase(
        id="PTC-003",
        title="Verify DELETE /api/attendance removes record",
        description="Delete attendance",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.MEDIUM,
        source="AttendanceController",
        reason="Verify deletion",
        expected_result="HTTP 204 No Content",
        status=ProposedTestStatus.PROPOSED,
        api_spec=ApiTestSpec(method="DELETE", endpoint="/api/attendance", expected_status=204),
    )

    result = validator.validate_test_case(test)
    assert result.status == ValidationStatus.PARTIALLY_VALID
    assert "method 'DELETE' is not implemented" in (result.issue or "")


def test_existing_ui_workflow_validation(sample_analysis_data):
    """Verify that an existing UI route is classified as VALID with UI evidence."""
    validator = ProposedTestValidator(Path("."), analysis_data=sample_analysis_data)

    test = ProposedTestCase(
        id="PTC-004",
        title="Verify user login page interaction",
        description="Submit login form",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="AuthController",
        reason="Verify UI login",
        expected_result="User redirected to dashboard",
        status=ProposedTestStatus.PROPOSED,
        ui_spec=UiTestSpec(target_route="/login"),
    )

    result = validator.validate_test_case(test)
    assert result.status == ValidationStatus.VALID
    assert result.playwright_executable is True
    assert "Login.tsx" in (result.repository_evidence or "")


def test_hallucinated_ui_workflow_validation(sample_analysis_data):
    """Verify that a non-existent UI page (e.g. /cart) is classified as PARTIALLY_VALID/HALLUCINATED."""
    validator = ProposedTestValidator(Path("."), analysis_data=sample_analysis_data)

    test = ProposedTestCase(
        id="PTC-005",
        title="Verify Shopping Cart checkout page",
        description="View shopping cart items",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="CartController",
        reason="Verify shopping cart",
        expected_result="Cart items displayed",
        status=ProposedTestStatus.PROPOSED,
        ui_spec=UiTestSpec(target_route="/cart/view"),
    )

    result = validator.validate_test_case(test)
    assert result.status in [ValidationStatus.PARTIALLY_VALID, ValidationStatus.HALLUCINATED]


def test_duplicate_scenario_detection(sample_analysis_data):
    """Verify that duplicate tests covering the same endpoint/scenario are flagged as DUPLICATE."""
    validator = ProposedTestValidator(Path("."), analysis_data=sample_analysis_data)

    t1 = ProposedTestCase(
        id="PTC-006",
        title="Verify GET /api/attendance returns success",
        description="Check attendance list",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="AttendanceController",
        reason="Check attendance",
        expected_result="200 OK",
        status=ProposedTestStatus.PROPOSED,
        api_spec=ApiTestSpec(method="GET", endpoint="/api/attendance", expected_status=200),
    )

    t2 = ProposedTestCase(
        id="PTC-007",
        title="Verify attendance API is accessible via GET",
        description="Duplicate check of attendance list",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="AttendanceController",
        reason="Duplicate check",
        expected_result="200 OK",
        status=ProposedTestStatus.PROPOSED,
        api_spec=ApiTestSpec(method="GET", endpoint="/api/attendance", expected_status=200),
    )

    validated, summary = validator.validate_all([t1, t2])
    assert validated[0].validation.status == ValidationStatus.VALID
    assert validated[1].validation.status == ValidationStatus.DUPLICATE
    assert validated[1].validation.playwright_executable is False
    assert summary.duplicate == 1


def test_non_functional_and_unsupported_detection(sample_analysis_data):
    """Verify that non-functional code checks are INVALID and hardware tests are UNSUPPORTED."""
    validator = ProposedTestValidator(Path("."), analysis_data=sample_analysis_data)

    # 1. Non functional
    non_func = ProposedTestCase(
        id="PTC-008",
        title="Verify code formatting and check pom.xml syntax",
        description="Static check of pom.xml",
        type=ProposedTestType.UNIT,
        priority=ProposedTestPriority.LOW,
        source="Build",
        reason="Check formatting",
        expected_result="Format ok",
        status=ProposedTestStatus.PROPOSED,
    )

    # 2. Hardware unsupported
    hw_test = ProposedTestCase(
        id="PTC-009",
        title="Verify biometric hardware dongle device scan",
        description="Connect USB hardware scanner",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="BiometricDevice",
        reason="Hardware test",
        expected_result="Device connected",
        status=ProposedTestStatus.PROPOSED,
    )

    validated, summary = validator.validate_all([non_func, hw_test])
    assert validated[0].validation.status == ValidationStatus.INVALID
    assert validated[1].validation.status == ValidationStatus.UNSUPPORTED
    assert summary.invalid == 1
    assert summary.unsupported == 1


def test_unit_and_service_test_rejection(sample_analysis_data):
    """Verify that UNIT tests and service implementation checks are strictly classified as INVALID."""
    validator = ProposedTestValidator(Path("."), analysis_data=sample_analysis_data)

    # Unit test
    unit_test = ProposedTestCase(
        id="PTC-UNIT-01",
        title="Verify AttendanceService.calculateDuration() method output",
        description="Check method return value with mocks",
        type=ProposedTestType.UNIT,
        priority=ProposedTestPriority.HIGH,
        source="AttendanceService.java",
        reason="Unit test for service",
        expected_result="Method returns 8.0",
        status=ProposedTestStatus.PROPOSED,
    )

    # Service implementation test disguised as API but without endpoint
    svc_test = ProposedTestCase(
        id="PTC-SVC-01",
        title="Verify repository method saves entity",
        description="Check internal DAO method call",
        type=ProposedTestType.UNIT,
        priority=ProposedTestPriority.MEDIUM,
        source="AttendanceRepository",
        reason="Verify repository save",
        expected_result="Entity persisted",
        status=ProposedTestStatus.PROPOSED,
    )

    # Static analysis / class existence
    static_test = ProposedTestCase(
        id="PTC-STATIC-01",
        title="Verify Java class contains @GetMapping annotation",
        description="AST check for Spring annotation",
        type=ProposedTestType.UNIT,
        priority=ProposedTestPriority.LOW,
        source="AttendanceController.java",
        reason="Static AST check",
        expected_result="Annotation exists",
        status=ProposedTestStatus.PROPOSED,
    )

    for t in [unit_test, svc_test, static_test]:
        res = validator.validate_test_case(t)
        assert res.status == ValidationStatus.INVALID
        assert res.playwright_executable is False


def test_missing_ui_route_hallucinated(sample_analysis_data):
    """Verify that a non-existent UI route in a backend/attendance app is flagged as HALLUCINATED."""
    empty_ui_data = {**sample_analysis_data, "ui_workflows": []}
    validator = ProposedTestValidator(Path("."), analysis_data=empty_ui_data)

    ui_test = ProposedTestCase(
        id="PTC-UI-HALLUCINATED",
        title="Verify shopping cart checkout workflow",
        description="Navigate to shopping cart page",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="CartPage",
        reason="Checkout flow",
        expected_result="Cart page loaded",
        status=ProposedTestStatus.PROPOSED,
        ui_spec=UiTestSpec(target_route="/shopping-cart/checkout"),
    )

    res = validator.validate_test_case(ui_test)
    assert res.status == ValidationStatus.HALLUCINATED
    assert res.playwright_executable is False


def test_full_validation_summary_and_coverage(sample_analysis_data):
    """Verify that validate_all produces consistent counts and functional area coverage mapping."""
    validator = ProposedTestValidator(Path("."), analysis_data=sample_analysis_data)

    tests = [
        # Valid API
        ProposedTestCase(
            id="PTC-010",
            title="Verify GET /api/attendance",
            description="Attendance",
            type=ProposedTestType.API,
            priority=ProposedTestPriority.HIGH,
            source="AttendanceController",
            reason="Query",
            expected_result="200",
            status=ProposedTestStatus.PROPOSED,
            api_spec=ApiTestSpec(method="GET", endpoint="/api/attendance"),
        ),
        # Valid UI
        ProposedTestCase(
            id="PTC-011",
            title="Verify user login",
            description="Login",
            type=ProposedTestType.UI,
            priority=ProposedTestPriority.HIGH,
            source="AuthController",
            reason="Auth",
            expected_result="OK",
            status=ProposedTestStatus.PROPOSED,
            ui_spec=UiTestSpec(target_route="/login"),
        ),
        # Hallucinated API
        ProposedTestCase(
            id="PTC-012",
            title="Verify POST /api/payment",
            description="Payment",
            type=ProposedTestType.API,
            priority=ProposedTestPriority.HIGH,
            source="Payment",
            reason="Payment",
            expected_result="200",
            status=ProposedTestStatus.PROPOSED,
            api_spec=ApiTestSpec(method="POST", endpoint="/api/payment"),
        ),
        # Invalid Unit test
        ProposedTestCase(
            id="PTC-013",
            title="Verify service calculateDuration logic",
            description="Unit check",
            type=ProposedTestType.UNIT,
            priority=ProposedTestPriority.LOW,
            source="AttendanceService",
            reason="Unit",
            expected_result="OK",
            status=ProposedTestStatus.PROPOSED,
        ),
    ]

    validated, summary = validator.validate_all(tests)
    assert summary.total_llm_generated == 4
    assert summary.valid == 2
    assert summary.hallucinated == 1
    assert summary.invalid == 1
    assert summary.valid + summary.partially_valid + summary.invalid + summary.hallucinated + summary.duplicate + summary.unsupported == summary.total_llm_generated

    # Check coverage mapping
    assert "Attendance Management" in summary.functional_coverage
    assert summary.functional_coverage["Attendance Management"] == "Covered"
    assert "Authentication" in summary.functional_coverage
    assert summary.functional_coverage["Authentication"] == "Covered"
