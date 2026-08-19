"""Generates structured, traceable Proposed Functional Test Cases based on gap analysis."""

from __future__ import annotations

import re
from typing import Any

from app.domain.models.proposed_test_models import (
    ApiTestSpec,
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
    UiTestSpec,
    UnitTestSpec,
)


class ProposedTestGenerator:
    """Transforms discovered codebase features & coverage gaps into proposed functional test cases."""

    def __init__(self, analysis_data: dict[str, Any]) -> None:
        self.analysis = analysis_data
        self.existing_coverage = analysis_data.get("existing_coverage", {})
        self.existing_methods = set(self.existing_coverage.get("methods", []))
        self.existing_classes = set(self.existing_coverage.get("classes", []))
        self.existing_scenarios = set(self.existing_coverage.get("scenarios", []))

    def generate(self) -> list[ProposedTestCase]:
        proposals: list[ProposedTestCase] = []
        counter = 1
        seen_signatures: set[str] = set()

        # 1. Generate API Proposals from Endpoints
        endpoints = self.analysis.get("endpoints", [])
        for ep in endpoints:
            method = ep.get("method", "GET").upper()
            endpoint = ep.get("endpoint", "/")
            source_class = ep.get("class_name") or ep.get("source") or "Controller"

            # Canonical signature for deduplication
            sig = f"API:{method}:{endpoint.lower()}"
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)

            # Check if an existing test already covers this endpoint directly
            endpoint_slug = re.sub(r'[\/{}\-_]', '', endpoint).lower()
            is_covered = any(
                endpoint_slug in sc or f"{method.lower()}{endpoint_slug}" in sc
                for sc in self.existing_scenarios
            )

            # Propose happy path test if uncovered
            if not is_covered:
                ptc_id = f"PTC-{counter:03d}"
                counter += 1
                title = f"Verify {method} {endpoint} returns success response"
                reason = f"REST endpoint '{method} {endpoint}' detected in {source_class} without direct existing API test coverage."
                priority = ProposedTestPriority.HIGH if any(k in endpoint for k in ["login", "auth", "user", "order", "payment"]) else ProposedTestPriority.MEDIUM

                proposals.append(ProposedTestCase(
                    id=ptc_id,
                    title=title,
                    description=f"Validate that sending a valid {method} request to '{endpoint}' returns expected status code and response payload.",
                    type=ProposedTestType.API,
                    priority=priority,
                    source=source_class,
                    reason=reason,
                    preconditions=[
                        "Application service is running and accessible",
                        "Database contains required test seed data",
                    ],
                    steps=[
                        f"Construct {method} request with valid headers and payload for {endpoint}",
                        "Send HTTP request to the API server",
                        "Inspect response status code and JSON response body",
                    ],
                    expected_result="HTTP status code is 200/201 and response payload matches schema",
                    status=ProposedTestStatus.PROPOSED,
                    api_spec=ApiTestSpec(
                        method=method,
                        endpoint=endpoint,
                        headers={"Content-Type": "application/json", "Accept": "application/json"},
                        request_body={"test": "sample_payload"} if method in ["POST", "PUT", "PATCH"] else None,
                        expected_status=201 if method == "POST" else 200,
                        expected_response={"status": "success"},
                        assertions=[f"status == {201 if method == 'POST' else 200}", "response.body != null"],
                    ),
                ))

            # Propose negative / validation gap test for POST/PUT endpoints
            if method in ["POST", "PUT"]:
                ptc_id = f"PTC-{counter:03d}"
                counter += 1
                neg_title = f"Validate {method} {endpoint} rejection on invalid payload"
                neg_reason = f"Endpoint '{method} {endpoint}' accepts request body; missing negative validation test for bad/empty input."

                proposals.append(ProposedTestCase(
                    id=ptc_id,
                    title=neg_title,
                    description=f"Verify that sending an invalid/empty payload to '{endpoint}' is rejected with HTTP 400 Bad Request.",
                    type=ProposedTestType.API,
                    priority=ProposedTestPriority.MEDIUM,
                    source=source_class,
                    reason=neg_reason,
                    preconditions=["Application service is running"],
                    steps=[
                        f"Send malformed or empty JSON payload to {method} {endpoint}",
                        "Assert response status is 400 or 422 Unprocessable Entity",
                    ],
                    expected_result="HTTP 400 / 422 with meaningful error message in response body",
                    status=ProposedTestStatus.PROPOSED,
                    api_spec=ApiTestSpec(
                        method=method,
                        endpoint=endpoint,
                        headers={"Content-Type": "application/json"},
                        request_body={},
                        expected_status=400,
                        assertions=["status in [400, 422]", "response.error != null"],
                    ),
                ))

        # 2. Generate Unit Proposals from Services
        services = self.analysis.get("services", [])
        for svc in services:
            svc_name = svc.get("name", "Service")
            methods = svc.get("methods", [])

            for m in methods[:4]:  # Top public methods
                m_name = m.get("name", "execute")
                sig = f"UNIT:{svc_name}:{m_name.lower()}"
                if sig in seen_signatures:
                    continue
                seen_signatures.add(sig)

                # Check existing unit coverage
                is_covered = any(
                    m_name.lower() in em or f"test{m_name.lower()}" in em
                    for em in self.existing_methods
                )

                if not is_covered:
                    ptc_id = f"PTC-{counter:03d}"
                    counter += 1
                    title = f"Unit test for {svc_name}.{m_name}() business logic"
                    reason = f"Public business method '{m_name}' in {svc_name} has no matching unit test."
                    priority = ProposedTestPriority.HIGH if any(k in m_name.lower() for k in ["validate", "calculate", "process", "save", "auth"]) else ProposedTestPriority.MEDIUM

                    proposals.append(ProposedTestCase(
                        id=ptc_id,
                        title=title,
                        description=f"Execute {svc_name}.{m_name}() with mock inputs to ensure calculation/business rules execute correctly.",
                        type=ProposedTestType.UNIT,
                        priority=priority,
                        source=f"{svc_name}.java",
                        reason=reason,
                        preconditions=[
                            f"Instantiate {svc_name} with mocked dependencies",
                        ],
                        steps=[
                            f"Prepare mock input data for {m_name}()",
                            f"Call {svc_name}.{m_name}(args)",
                            "Assert return value and verify repository/collaborator interactions",
                        ],
                        expected_result="Method returns expected output without throwing unhandled exceptions",
                        status=ProposedTestStatus.PROPOSED,
                        unit_spec=UnitTestSpec(
                            target_class=svc_name,
                            target_method=m_name,
                            input_data={"mockParam": "sampleValue"},
                            mock_data={"repo": "MockRepository"},
                            expected_output={"result": "valid"},
                            assertions=[f"assertNotNull(result)", f"assertEquals(expected, result)"],
                        ),
                    ))

        # 3. Generate UI Proposals from UI Workflows
        ui_workflows = self.analysis.get("ui_workflows", [])
        for ui in ui_workflows:
            ui_name = ui.get("name", "Page")
            ui_type = ui.get("type", "FORM")
            sig = f"UI:{ui_name}:{ui_type}"
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)

            # Check if UI flow already covered
            is_covered = any(ui_name.lower() in ec for ec in self.existing_classes)

            if not is_covered:
                ptc_id = f"PTC-{counter:03d}"
                counter += 1

                if ui.get("has_login"):
                    title = f"Playwright UI: Verify User Authentication workflow on {ui_name}"
                    reason = f"Authentication view '{ui_name}' detected; Playwright end-to-end browser test proposed for login workflow."
                    priority = ProposedTestPriority.HIGH
                    steps = [
                        f"Navigate to {ui_name} route in browser",
                        "Locate username and password input fields",
                        "Enter valid credentials and submit form",
                        "Verify redirect to Dashboard and capture screenshot evidence",
                    ]
                    expected_result = "User is successfully authenticated and redirected to dashboard view"
                elif ui.get("has_form"):
                    title = f"Playwright UI: Validate form submission and feedback on {ui_name}"
                    reason = f"Interactive form detected in '{ui_name}'; Playwright browser test proposed for data entry and submission."
                    priority = ProposedTestPriority.MEDIUM
                    steps = [
                        f"Navigate to {ui_name} route in browser",
                        "Fill out required form inputs",
                        "Click submit button",
                        "Verify success notification/confirmation modal is rendered",
                    ]
                    expected_result = "Form submits successfully with visual confirmation displayed"
                else:
                    title = f"Playwright UI: Verify page rendering and navigation on {ui_name}"
                    reason = f"UI view '{ui_name}' detected; Playwright visual verification proposed."
                    priority = ProposedTestPriority.LOW
                    steps = [
                        f"Open browser and navigate to {ui_name}",
                        "Verify header, navigation links, and primary content container",
                        "Capture full-page screenshot",
                    ]
                    expected_result = "Page renders without layout breaks or JavaScript console errors"

                proposals.append(ProposedTestCase(
                    id=ptc_id,
                    title=title,
                    description=f"End-to-end browser test using Playwright against {ui_name} with automated screenshot & video recording.",
                    type=ProposedTestType.UI,
                    priority=priority,
                    source=f"{ui_name}",
                    reason=reason,
                    preconditions=[
                        "Frontend and backend servers are running",
                        "Browser is initialized in headless mode",
                    ],
                    steps=steps,
                    expected_result=expected_result,
                    status=ProposedTestStatus.PROPOSED,
                    ui_spec=UiTestSpec(
                        target_route=f"/{ui_name.lower().replace('page', '')}",
                        input_fields=[{"name": "inputField", "type": "text"}],
                        actions=["navigate", "fill", "click", "screenshot"],
                        expected_elements=["[data-testid='main-container']", "header"],
                        assertions=["page.title().not.toBeEmpty()", "expect(page.locator('body')).toBeVisible()"],
                    ),
                ))

        # Fallback if no proposals were discovered (e.g. minimal or custom project structure)
        if not proposals:
            proposals.append(ProposedTestCase(
                id="PTC-001",
                title="Smoke Test: Application Health & Context Load",
                description="Verify that the migrated application context loads and core health/discovery endpoints respond correctly.",
                type=ProposedTestType.API,
                priority=ProposedTestPriority.HIGH,
                source="ApplicationContext",
                reason="Baseline smoke test proposed to verify migrated application startup and health status.",
                preconditions=["Application server is running"],
                steps=[
                    "Send GET request to /health or /api/health",
                    "Verify HTTP 200 status code",
                ],
                expected_result="HTTP status 200 OK with healthy service status",
                status=ProposedTestStatus.PROPOSED,
                api_spec=ApiTestSpec(
                    method="GET",
                    endpoint="/health",
                    expected_status=200,
                    assertions=["status == 200"],
                ),
            ))

        return proposals
