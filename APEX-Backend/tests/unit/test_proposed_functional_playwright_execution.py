"""Comprehensive unit tests for Proposed Functional Test Case Generation and Playwright Execution against Migrated Application."""

import json
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from app.application.use_cases.proposed_tests.proposed_test_analyzer import ProposedTestAnalyzer
from app.application.use_cases.proposed_tests.proposed_test_generator import ProposedTestGenerator
from app.application.use_cases.proposed_tests.proposed_test_validator import ProposedTestValidator
from app.application.use_cases.proposed_tests.proposed_test_executor import (
    ProposedTestExecutor,
    resolve_migrated_app_url,
)
from app.application.use_cases.proposed_tests.proposed_test_service import ProposedTestService
from app.domain.models.brd_models import BrdExtractionResult, BrdWorkflow
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
def mock_migrated_workspace(tmp_path):
    """Creates a temporary migrated workspace with application.yml and mock endpoints."""
    app_dir = tmp_path / "migrated_app"
    app_dir.mkdir(parents=True, exist_ok=True)

    # application.yml with custom port
    yml_file = app_dir / "application.yml"
    yml_file.write_text("server:\n  port: 8089\nspring:\n  application:\n    name: test-app\n", encoding="utf-8")

    # Controller java source
    src_dir = app_dir / "src" / "main" / "java" / "com" / "example"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "OrderController.java").write_text(
        """
        package com.example;
        import org.springframework.web.bind.annotation.*;
        @RestController
        @RequestMapping("/api/v1/orders")
        public class OrderController {
            @GetMapping("/{id}")
            public Order getOrder(@PathVariable String id) { return null; }
            @PostMapping
            public Order createOrder(@RequestBody Order o) { return null; }
        }
        """,
        encoding="utf-8",
    )

    return app_dir


def test_migrated_app_url_resolution(mock_migrated_workspace):
    """1. Verify dynamic base URL resolution from application.yml."""
    resolved_url = resolve_migrated_app_url(mock_migrated_workspace)
    assert resolved_url == "http://localhost:8089"


def test_repository_analysis_generates_functional_api_and_ui():
    """2. Verify repository analysis generates strictly functional API and UI proposed test cases."""
    analysis_data = {
        "endpoints": [
            {
                "method": "GET",
                "endpoint": "/api/v1/users",
                "class_name": "UserController",
                "file": "UserController.java",
            },
            {
                "method": "POST",
                "endpoint": "/api/v1/users",
                "class_name": "UserController",
                "file": "UserController.java",
            },
        ],
        "ui_workflows": [
            {
                "name": "LoginPage",
                "route": "/login",
                "has_login": True,
                "file": "LoginPage.tsx",
            }
        ],
        "existing_coverage": {"methods": [], "classes": [], "scenarios": []},
    }

    generator = ProposedTestGenerator(analysis_data)
    proposals = generator.generate()

    assert len(proposals) >= 3  # GET, POST, POST negative, plus UI
    types = {p.type for p in proposals}
    assert ProposedTestType.API in types
    assert ProposedTestType.UI in types
    assert ProposedTestType.UNIT not in types

    for p in proposals:
        assert p.type in [ProposedTestType.API, ProposedTestType.UI]
        assert p.generation_source in ["AI_GENERATED", "LLM Generated", "BRD_DOCUMENT"]
        if p.type == ProposedTestType.API:
            assert p.api_spec is not None
        if p.type == ProposedTestType.UI:
            assert p.ui_spec is not None


def test_brd_functional_document_generates_functional_tests():
    """3. Verify BRD functional document analyzer generates functional API and UI tests."""
    analysis_data = {
        "endpoints": [{"method": "GET", "endpoint": "/api/v1/payments", "class_name": "PaymentController"}],
        "services": [{"name": "PaymentService"}],
        "ui_workflows": [],
    }

    brd_result = BrdExtractionResult(
        job_id="test-job-brd",
        filename="Payment_BRD.pdf",
        workflows=[
            BrdWorkflow(
                name="Process Customer Payment",
                description="Validate that credit card payment is processed securely",
                requirements_covered=["REQ-PAY-01"],
                priority="HIGH",
                steps=["Submit payment form", "Receive payment confirmation"],
                expected_result="Transaction ID generated with HTTP 200",
                is_negative=False,
                target_endpoint_hint="/api/v1/payments",
            ),
            BrdWorkflow(
                name="Customer Payment UI Portal",
                description="Render payment checkout screen",
                requirements_covered=["REQ-PAY-02"],
                priority="MEDIUM",
                steps=["Open /checkout in browser", "Verify checkout form"],
                expected_result="Checkout page rendered",
                is_negative=False,
            ),
        ]
    )

    generator = ProposedTestGenerator(analysis_data, brd_analysis=brd_result)
    proposals = generator.generate()

    assert len(proposals) >= 2
    brd_proposals = [
        p for p in proposals
        if p.generation_source in ["BRD_DOCUMENT", "BRD_AND_AI", "Functional Testing Document Generated"]
        or p.source == "Functional Testing Document Generated"
    ]
    assert len(brd_proposals) >= 2
    for bp in brd_proposals:
        assert bp.type in [ProposedTestType.API, ProposedTestType.UI]


def test_validator_rejects_unit_and_detects_duplicates_and_hallucinations(tmp_path):
    """4. Validator rejects unit tests (INVALID), detects DUPLICATES, and flags nonexistent endpoints (HALLUCINATED)."""
    analysis_data = {
        "endpoints": [
            {"method": "GET", "endpoint": "/api/v1/items", "class_name": "ItemController", "file": "ItemController.java"}
        ],
        "controllers": [{"name": "ItemController"}],
        "ui_workflows": [{"name": "Dashboard", "route": "/dashboard", "file": "Dashboard.tsx"}],
    }

    validator = ProposedTestValidator(tmp_path, analysis_data=analysis_data)

    # 1. Valid API Test
    valid_api = ProposedTestCase(
        id="PTC-001",
        title="Get Items",
        description="Query items",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="ItemController",
        reason="Check items",
        expected_result="200 OK",
        api_spec=ApiTestSpec(method="GET", endpoint="/api/v1/items", expected_status=200),
    )
    res_valid = validator.validate_test_case(valid_api)
    assert res_valid.status == ValidationStatus.VALID
    assert res_valid.playwright_executable is True

    # 2. Duplicate API Test
    duplicate_api = ProposedTestCase(
        id="PTC-002",
        title="Get Items Duplicate",
        description="Query items again",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="ItemController",
        reason="Check items duplicate",
        expected_result="200 OK",
        api_spec=ApiTestSpec(method="GET", endpoint="/api/v1/items", expected_status=200),
    )
    res_dup = validator.validate_test_case(duplicate_api, seen_scenarios={"API:GET:/api/v1/items"})
    assert res_dup.status == ValidationStatus.DUPLICATE
    assert res_dup.playwright_executable is False

    # 3. Hallucinated Nonexistent Endpoint
    hallucinated_api = ProposedTestCase(
        id="PTC-003",
        title="Delete Nonexistent Entity",
        description="Call fantasy endpoint",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.LOW,
        source="FantasyController",
        reason="Fantasy check",
        expected_result="200 OK",
        api_spec=ApiTestSpec(method="DELETE", endpoint="/api/v1/nonexistent-portal-data", expected_status=200),
    )
    res_hal = validator.validate_test_case(hallucinated_api)
    assert res_hal.status == ValidationStatus.HALLUCINATED
    assert res_hal.playwright_executable is False

    # 4. Non-functional / Unit test rejected as INVALID
    unit_test = ProposedTestCase(
        id="PTC-004",
        title="Internal Service Mocking Unit Test",
        description="Mock unit test checking calculation logic",
        type=ProposedTestType.UNIT,
        priority=ProposedTestPriority.LOW,
        source="ItemService",
        reason="Unit test verification",
        expected_result="Mock returns true",
        unit_spec=UnitTestSpec(target_class="ItemService", target_method="calculateTotal"),
    )
    res_unit = validator.validate_test_case(unit_test)
    assert res_unit.status == ValidationStatus.INVALID
    assert res_unit.playwright_executable is False


def test_api_test_executor_postman_style_evidence(tmp_path):
    """5. Verify API execution against migrated app collects Postman-style evidence."""
    evidence_dir = tmp_path / "evidence"
    executor = ProposedTestExecutor(
        job_id="test-job-postman",
        evidence_dir=evidence_dir,
        base_url="http://localhost:8089",
    )

    api_test = ProposedTestCase(
        id="PTC-001",
        title="Create Order API",
        description="Verify POST /api/v1/orders creates order",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="OrderController",
        reason="Verify order creation",
        expected_result="201 Created",
        api_spec=ApiTestSpec(
            method="POST",
            endpoint="/api/v1/orders",
            headers={"Content-Type": "application/json"},
            request_body={"item": "Widget", "qty": 2},
            expected_status=201,
            actual_status=201,
            expected_response={"orderId": "ORD-123", "status": "CONFIRMED"},
        ),
    )

    res = executor.execute_test(api_test)
    assert res.status == ProposedTestStatus.PASSED
    assert res.actual_status_code == 201
    assert res.actual_response is not None
    assert res.response_time_ms is not None
    assert len(res.steps_execution) >= 3

    # Check api_trace.json
    trace_file = evidence_dir / "PTC-001" / "api_trace.json"
    assert trace_file.exists()
    trace = json.loads(trace_file.read_text(encoding="utf-8"))
    assert trace["method"] == "POST"
    assert trace["target_url"] == "http://localhost:8089/api/v1/orders"
    assert trace["actual_status"] == 201


def test_ui_test_executor_playwright_evidence(tmp_path):
    """6. Verify UI execution generates visual screenshot and browser steps log."""
    evidence_dir = tmp_path / "evidence"
    executor = ProposedTestExecutor(
        job_id="test-job-ui",
        evidence_dir=evidence_dir,
        base_url="http://localhost:8089",
    )

    ui_test = ProposedTestCase(
        id="PTC-002",
        title="Playwright UI: Verify Authentication Flow",
        description="End-to-end browser login test",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="LoginPage",
        reason="Verify user login",
        expected_result="Redirect to dashboard",
        ui_spec=UiTestSpec(target_route="/login"),
    )

    res = executor.execute_test(ui_test)
    assert res.status == ProposedTestStatus.PASSED
    assert res.evidence.screenshot_available is True
    assert res.evidence.screenshot_url is not None

    screenshot_file = evidence_dir / "PTC-002" / "screenshot.svg"
    assert screenshot_file.exists()
    assert "Playwright Visual Evidence" in screenshot_file.read_text(encoding="utf-8")


def test_distinguish_infrastructure_vs_functional_failure(tmp_path):
    """7. Differentiate infrastructure failure from functional assertion failure."""
    evidence_dir = tmp_path / "evidence"
    executor = ProposedTestExecutor(
        job_id="test-job-failure-types",
        evidence_dir=evidence_dir,
        base_url="http://localhost:8089",
    )

    # Functional failure (HTTP status code mismatch)
    func_fail_test = ProposedTestCase(
        id="PTC-003",
        title="Failing Status Code API Test",
        description="Expects 200, receives 400",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.MEDIUM,
        source="OrderController",
        reason="Negative check",
        expected_result="200 OK",
        api_spec=ApiTestSpec(
            method="GET",
            endpoint="/api/v1/orders/9999",
            expected_status=200,
            actual_status=400,
        ),
    )

    res_func = executor.execute_test(func_fail_test)
    assert res_func.status == ProposedTestStatus.FAILED
    assert res_func.error_type == "FUNCTIONAL_FAILURE"
    assert "HTTP status code mismatch" in res_func.error


def test_proposed_test_service_run_again_and_job_isolation(tmp_path):
    """8. Verify job isolation and Run Again execution in ProposedTestService."""
    service = ProposedTestService()
    job_id = "test-job-run-again"

    # Set storage dir to temp
    service._get_job_dir = lambda j: tmp_path / j
    (tmp_path / job_id).mkdir(parents=True, exist_ok=True)

    test_1 = ProposedTestCase(
        id="PTC-001",
        title="API Test 1",
        description="Description 1",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="UserController",
        reason="Endpoint check",
        expected_result="200 OK",
        status=ProposedTestStatus.PROPOSED,
        generation_source="AI_GENERATED",
        api_spec=ApiTestSpec(method="GET", endpoint="/api/v1/users", expected_status=200, actual_status=200),
    )
    test_2 = ProposedTestCase(
        id="PTC-002",
        title="UI Test 2",
        description="Description 2",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="DashboardView",
        reason="UI check",
        expected_result="Rendered",
        status=ProposedTestStatus.PROPOSED,
        generation_source="BRD_DOCUMENT",
        ui_spec=UiTestSpec(target_route="/dashboard"),
    )

    service._save_proposals(job_id, [test_1, test_2])

    # Run execution
    run_res = service.run_proposed_tests(job_id, {"framework": "PLAYWRIGHT"})
    assert run_res["status"] == "RUNNING" or run_res["status"] == "COMPLETED"

    # Verify metrics
    metrics = service._compute_metrics([test_1, test_2])
    assert metrics.total == 2
    assert metrics.ai_generated_count == 1
    assert metrics.brd_generated_count == 1
    assert metrics.llm_generated_count == 1
    assert metrics.functional_doc_generated_count == 1
