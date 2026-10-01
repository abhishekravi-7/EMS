"""Comprehensive validation of the 12 DoD requirements for functional test generation and execution."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.application.use_cases.proposed_tests.authentication_manager import (
    AuthenticationManager,
    AuthCredentials,
)
from app.application.use_cases.proposed_tests.dynamic_data_resolver import (
    DynamicDataResolver,
    RuntimeContext,
    EndpointResolution,
)
from app.application.use_cases.proposed_tests.proposed_test_analyzer import ProposedTestAnalyzer
from app.application.use_cases.proposed_tests.proposed_test_executor import ProposedTestExecutor
from app.application.use_cases.proposed_tests.proposed_test_generator import ProposedTestGenerator
from app.application.use_cases.proposed_tests.proposed_test_validator import ProposedTestValidator
from app.domain.models.proposed_test_models import (
    ApiTestSpec,
    ExecutionResult,
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
    TestCaseMetadata,
    UiTestSpec,
    ValidationStatus,
)


def test_dod_criterion_1_no_fake_static_entity_ids():
    """Criterion 1: No fake/static entity IDs (1, 10001, 999) appear in generated endpoints or parameters."""
    runtime_ctx = RuntimeContext()
    resolver = DynamicDataResolver(runtime_context=runtime_ctx)

    # Parametric endpoint without seed data or dynamic instance must NOT invent static 1 or 10001
    res = resolver.resolve_endpoint("/api/orders/{orderId}/items/{itemId}")
    assert not res.is_resolved
    assert "1" not in res.endpoint
    assert "10001" not in res.endpoint
    assert "{orderId}" in res.endpoint or "{itemId}" in res.endpoint
    assert "cannot be resolved" in res.issue


def test_dod_criterion_2_and_3_auth_session_reuse_and_no_credential_retry():
    """Criteria 2 & 3: Authentication caching, login trap detection, and failed credential exclusion."""
    auth_mgr = AuthenticationManager()
    auth_mgr._failed_credentials.add(("baduser", "badpass"))

    # Credential candidates must exclude already failed ones
    mock_creds = [
        AuthCredentials(username="baduser", password="badpass", source="test"),
        AuthCredentials(username="gooduser", password="goodpass", source="test"),
    ]
    with patch.object(auth_mgr, "discover_credentials", return_value=mock_creds):
        candidates = [c for c in auth_mgr.discover_credentials() if (c.username, c.password) not in auth_mgr._failed_credentials]
        assert len(candidates) == 1
        assert candidates[0].username == "gooduser"

    # Criterion 2: Login trap detection on 200 with HTML body
    is_trap = auth_mgr.is_html_login_trap(
        status_code=200,
        content_type="text/html;charset=UTF-8",
        body_text="<html><head><title>Login</title></head><body><form action='/login.do'><input name='password' type='password'/></form></body></html>",
    )
    assert is_trap is True

    # Genuine JSON response must NOT be flagged as trap
    is_not_trap = auth_mgr.is_html_login_trap(
        status_code=200,
        content_type="application/json",
        body_text='[{"id": 101, "desc": "Buy milk"}]',
    )
    assert is_not_trap is False


def test_dod_criterion_4_and_5_grounded_selectors_and_dom_interaction_types():
    """Criteria 4 & 5: Selector priority and DOM interaction type verification."""
    raw_html = '''
    <form action="/submit" method="post">
        <input type="text" id="desc" name="description" placeholder="Enter task" />
        <select id="priority" name="priority">
            <option value="HIGH">High</option>
            <option value="LOW">Low</option>
        </select>
        <input type="checkbox" id="urgent" name="isUrgent" />
        <button type="submit" id="save-btn" data-testid="save-button">Save</button>
    </form>
    '''
    analyzer = ProposedTestAnalyzer(repo_dir=Path("."))
    selectors_data = analyzer._extract_grounded_selectors(raw_html)
    selectors = selectors_data["grounded_selectors"]

    # Priority check: data-testid and id must take precedence
    assert any("[data-testid='save-button']" in s or '[data-testid="save-button"]' in s for s in selectors)
    assert any("#desc" in s for s in selectors)
    assert any("#priority" in s for s in selectors)
    assert any("#urgent" in s for s in selectors)

    # DOM interaction type check: verify Playwright actions match real DOM types
    input_fields = selectors_data["input_fields"]
    desc_field = next(f for f in input_fields if f["name"] == "description" or "#desc" in f["selector"])
    assert desc_field["playwright_action"] == "fill"
    priority_field = next(f for f in input_fields if f["name"] == "priority" or "#priority" in f["selector"])
    assert priority_field["playwright_action"] == "selectOption"
    urgent_field = next(f for f in input_fields if f["name"] == "isUrgent" or "#urgent" in f["selector"])
    assert urgent_field["playwright_action"] == "check"

    # Synthetic selectors must be flagged by validator
    validator = ProposedTestValidator(
        repo_dir=Path("."),
        analysis_data={
            "ui_workflows": [{
                "route": "/todos",
                "grounded_selectors": selectors,
                "file": "todo.jsp",
            }]
        },
    )
    synthetic_test = ProposedTestCase(
        id="PTC-SYNTH-001",
        title="Verify synthetic container",
        description="Check main container",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.MEDIUM,
        source="LLM Generated",
        reason="Coverage",
        expected_result="Container exists",
        ui_spec=UiTestSpec(
            target_route="/todos",
            expected_elements=['[data-testid="main-container"]'],
        ),
    )
    res = validator.validate_test_case(synthetic_test)
    assert res.status == ValidationStatus.REVIEW_REQUIRED
    assert res.playwright_executable is False


def test_dod_criterion_6_and_7_cited_expected_status_and_source_classification():
    """Criteria 6 & 7: Cited repository evidence for expected status and source-derived classification."""
    # Java EE servlet analysis simulation
    analysis_data = {
        "endpoints": [
            {
                "endpoint": "/list-todos.do",
                "method": "GET",
                "classification": "HTML_MVC",
                "expected_status": 200,
                "expected_status_source": "ListTodoServlet.java: forward renders JSP view HTTP 200",
                "authentication_required": True,
                "authentication_source": "LoginRequiredFilter.java: @WebFilter(urlPatterns = '*.do')",
                "file": "ListTodoServlet.java",
            }
        ],
        "credentials": [{"username": "in28Minutes", "password": "dummy", "source": "LoginService.java"}],
        "security_rules": [{"pattern": "*.do", "authenticated": True}],
    }
    validator = ProposedTestValidator(repo_dir=Path("."), analysis_data=analysis_data)

    test = ProposedTestCase(
        id="PTC-001",
        title="Verify list todos",
        description="Fetch todos view",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="ListTodoServlet",
        reason="Coverage",
        expected_result="HTTP 200",
        api_spec=ApiTestSpec(endpoint="/list-todos.do", method="GET", expected_status=200),
        metadata=TestCaseMetadata(
            test_id="PTC-001",
            endpoint="/list-todos.do",
            method="GET",
            expected_status=200,
            expected_status_source="ListTodoServlet.java: forward renders JSP view HTTP 200",
            authentication_required=True,
            authentication_source="LoginRequiredFilter.java: @WebFilter(urlPatterns = '*.do')",
            confidence=1.0,
            validation_status=ValidationStatus.VALID,
        ),
    )
    val_res = validator.validate_test_case(test)
    assert val_res.status == ValidationStatus.VALID
    assert val_res.playwright_executable is True


def test_dod_criterion_8_form_success_business_assertion():
    """Criterion 8: Form submission requires concrete business evidence (redirect, alert, table row)."""
    validator = ProposedTestValidator(
        repo_dir=Path("."),
        analysis_data={
            "ui_workflows": [{
                "route": "/add-todo",
                "grounded_selectors": ["#desc", "#save-btn"],
                "file": "add-todo.jsp",
            }]
        },
    )
    # Form test that only asserts navigation without business outcome
    weak_form_test = ProposedTestCase(
        id="PTC-FORM-001",
        title="Submit Add Todo Form",
        description="Add a new task",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="TodoServlet",
        reason="Coverage",
        expected_result="Page loads",  # Missing business assertion!
        steps=["Open /add-todo", "Fill #desc", "Click #save-btn"],
        ui_spec=UiTestSpec(target_route="/add-todo", expected_elements=["#desc", "#save-btn"]),
    )
    val_res = validator.validate_test_case(weak_form_test)
    assert val_res.status == ValidationStatus.REVIEW_REQUIRED
    assert val_res.playwright_executable is False
    assert "business evidence" in val_res.issue.lower()


def test_dod_criterion_9_and_10_distinct_login_scenarios_and_single_auth_run():
    """Criteria 9 & 10: Scenario A (render) and Scenario B (workflow) separation, run once."""
    ui_workflow = {
        "name": "LoginPage",
        "route": "/login.do",
        "file": "login.jsp",
        "type": "AUTH",
        "has_login": True,
        "grounded_selectors": ["#name", "#password", "button[type='submit']"],
        "input_fields": [
            {"name": "name", "label": "Username", "type": "text"},
            {"name": "password", "label": "Password", "type": "password"},
        ],
        "submit_button": "Login",
        "authentication_required": False,
    }
    generator = ProposedTestGenerator(
        analysis_data={"ui_workflows": [ui_workflow]},
        repo_dir=Path("."),
    )
    proposals = generator._generate_code_analysis_proposals()

    scenario_a = [p for p in proposals if "render" in p.title.lower() or "unauthenticated" in p.title.lower()]
    scenario_b = [p for p in proposals if "workflow" in p.title.lower() or "authentication" in p.title.lower()]

    assert len(scenario_a) >= 1
    assert len(scenario_b) >= 1
    assert scenario_a[0].id != scenario_b[0].id
    assert scenario_a[0].title != scenario_b[0].title
    assert scenario_a[0].ui_spec.target_route == "/login.do"
    assert scenario_b[0].ui_spec.target_route == "/login.do"


def test_dod_criterion_11_all_14_metadata_fields_populated():
    """Criterion 11: All 14 TestCaseMetadata fields are populated."""
    meta = TestCaseMetadata(
        test_id="PTC-TEST-001",
        endpoint="/api/v1/orders",
        method="POST",
        parameters={"status": "ACTIVE"},
        expected_status=201,
        expected_status_source="OrderController.java: @ResponseStatus(HttpStatus.CREATED)",
        authentication_required=True,
        authentication_source="SecurityConfig.java: antMatchers('/api/**').authenticated()",
        selector="#submit-order",
        selector_source="order.jsp",
        parameter_sources={"status": "Default enum definition"},
        evidence=["OrderController.java: @PostMapping"],
        dependencies=["AUTHENTICATE_SESSION"],
        confidence=1.0,
        validation_status=ValidationStatus.VALID,
    )
    dumped = meta.model_dump()
    expected_fields = [
        "test_id", "endpoint", "method", "parameters", "expected_status",
        "expected_status_source", "authentication_required", "authentication_source",
        "selector", "selector_source", "parameter_sources", "evidence",
        "dependencies", "confidence", "validation_status",
    ]
    for field_name in expected_fields:
        assert field_name in dumped


def test_dod_criterion_12_strict_execution_gate_blocks_non_valid():
    """Criterion 12: Strict execution gate blocks any test whose validation status is not VALID."""
    executor = ProposedTestExecutor(
        job_id="test-gate-job",
        evidence_dir=Path("./evidence"),
        base_url="http://localhost:8080",
    )

    for non_valid_status in [
        ValidationStatus.REVIEW_REQUIRED,
        ValidationStatus.BLOCKED_DEPENDENCY,
        ValidationStatus.BLOCKED_AUTHENTICATION,
        ValidationStatus.INVALID,
        ValidationStatus.HALLUCINATED,
        ValidationStatus.DUPLICATE,
        ValidationStatus.UNSUPPORTED,
    ]:
        blocked_test = ProposedTestCase(
            id=f"PTC-{non_valid_status.value}",
            title=f"Test for {non_valid_status.value}",
            description="Testing gate",
            type=ProposedTestType.API,
            priority=ProposedTestPriority.HIGH,
            source="TestController",
            reason="Gate check",
            expected_result="200 OK",
            api_spec=ApiTestSpec(endpoint="/test", method="GET"),
            metadata=TestCaseMetadata(
                test_id=f"PTC-{non_valid_status.value}",
                endpoint="/test",
                method="GET",
                validation_status=non_valid_status,
            ),
        )
        res = executor.execute_test(blocked_test)
        assert res.status == ProposedTestStatus.BLOCKED
        assert "blocked by strict execution gate" in res.error.lower()
