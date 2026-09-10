"""Generates structured, traceable Proposed Functional Test Cases based on code gap analysis and BRD workflows."""

from __future__ import annotations

import re
from typing import Any

from app.domain.models.brd_models import BrdExtractionResult, BrdWorkflow
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
    """Transforms discovered codebase features, coverage gaps, and BRD business workflows into proposed test cases."""

    def __init__(
        self,
        analysis_data: dict[str, Any],
        brd_analysis: BrdExtractionResult | None = None,
    ) -> None:
        self.analysis = analysis_data
        self.brd_analysis = brd_analysis
        self.existing_coverage = analysis_data.get("existing_coverage", {})
        self.existing_methods = set(self.existing_coverage.get("methods", []))
        self.existing_classes = set(self.existing_coverage.get("classes", []))
        self.existing_scenarios = set(self.existing_coverage.get("scenarios", []))

    def generate(self) -> list[ProposedTestCase]:
        ai_proposals = self._generate_code_analysis_proposals()
        brd_proposals = self._generate_brd_proposals() if self.brd_analysis and not self.brd_analysis.error else []

        if not brd_proposals:
            # Fallback if no proposals were discovered anywhere
            if not ai_proposals:
                return [self._create_baseline_smoke_test("PTC-001")]
            return self._reindex_proposals(ai_proposals)

        # Merge & deduplicate AI and BRD test cases (proposed tests only include new AI/BRD tests)
        combined = self._merge_and_deduplicate(ai_proposals, brd_proposals)
        return self._reindex_proposals(combined)

    def _generate_existing_proposals(self) -> list[ProposedTestCase]:
        existing_list = self.analysis.get("existing_tests", [])
        proposals: list[ProposedTestCase] = []
        seen = set()
        for idx, t in enumerate(existing_list):
            name = (
                t.get("name")
                or t.get("test_name")
                or t.get("methodname")
                or t.get("method_name")
                or f"testCase{idx+1}"
            )
            suite = (
                t.get("suite")
                or t.get("classname")
                or t.get("class_name")
                or t.get("file")
                or "ExistingTestSuite"
            )
            if isinstance(suite, str) and ("\\" in suite or "/" in suite):
                suite = Path(suite).stem
            key = f"{suite}::{name}".lower()
            if key in seen:
                continue
            seen.add(key)
            test_type_str = str(t.get("type", "")).upper()
            prop_type = ProposedTestType.UI if "PLAYWRIGHT" in test_type_str or "SELENIUM" in test_type_str else (
                ProposedTestType.API if "API" in test_type_str or "REST" in test_type_str else ProposedTestType.UNIT
            )

            proposals.append(
                ProposedTestCase(
                    id=f"PTC-EXT-{idx+1:03d}",
                    title=f"Execute {suite}.{name}",
                    description=f"Existing repository test case '{name}' in suite '{suite}'.",
                    type=prop_type,
                    priority=ProposedTestPriority.HIGH,
                    source="Existing Repository",
                    reason=f"Existing test discovered in repository suite {suite}.",
                    preconditions=["Migrated application compiled and target environment ready"],
                    steps=[
                        f"Load existing test suite {suite}",
                        f"Execute test method {name} against migrated application",
                        "Verify assertion outcomes and execution status",
                    ],
                    expected_result="Test executes with 0 assertion failures",
                    status=ProposedTestStatus.PROPOSED,
                    generation_source="EXISTING",
                    unit_spec=UnitTestSpec(
                        target_class=str(suite),
                        target_method=str(name),
                    ),
                )
            )
        return proposals

    def _merge_and_deduplicate_existing(
        self,
        base_proposals: list[ProposedTestCase],
        existing_proposals: list[ProposedTestCase],
    ) -> list[ProposedTestCase]:
        merged = list(base_proposals)
        seen_titles = {p.title.lower() for p in base_proposals}
        for ep in existing_proposals:
            if ep.title.lower() not in seen_titles:
                seen_titles.add(ep.title.lower())
                merged.append(ep)
        return merged

    def _generate_code_analysis_proposals(self) -> list[ProposedTestCase]:
        proposals: list[ProposedTestCase] = []
        counter = 1
        seen_signatures: set[str] = set()

        # 1. Generate API Proposals from Endpoints
        endpoints = self.analysis.get("endpoints", [])
        for ep in endpoints:
            method = ep.get("method", "GET").upper()
            endpoint = ep.get("endpoint", "/")
            source_class = ep.get("class_name") or ep.get("source") or "Controller"

            sig = f"API:{method}:{endpoint.lower()}"
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)

            # Check if an existing test already covers this endpoint directly
            endpoint_slug = re.sub(r"[\/{}\-_]", "", endpoint).lower()
            is_covered = any(
                endpoint_slug in sc or f"{method.lower()}{endpoint_slug}" in sc
                for sc in self.existing_scenarios
            )

            if not is_covered:
                ptc_id = f"PTC-{counter:03d}"
                counter += 1
                title = f"Verify {method} {endpoint} returns success response"
                reason = f"REST endpoint '{method} {endpoint}' detected in {source_class} without direct existing API test coverage."
                priority = ProposedTestPriority.HIGH if any(k in endpoint.lower() for k in ["login", "auth", "user", "order", "payment"]) else ProposedTestPriority.MEDIUM

                proposals.append(
                    ProposedTestCase(
                        id=ptc_id,
                        title=title,
                        description=f"Validate that sending a valid {method} request to '{endpoint}' returns expected status code and response payload.",
                        type=ProposedTestType.API,
                        priority=priority,
                        source="LLM Generated",
                        reason=reason,
                        preconditions=[
                            "Application service is running and accessible",
                            "Database contains required test seed data",
                        ],
                        test_data={"method": method, "endpoint": endpoint, "headers": {"Content-Type": "application/json"}},
                        steps=[
                            f"Construct {method} request with valid headers and payload for {endpoint}",
                            "Send HTTP request to the API server",
                            "Inspect response status code and JSON response body",
                        ],
                        expected_result="HTTP status code is 200/201 and response payload matches schema",
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        api_spec=ApiTestSpec(
                            method=method,
                            endpoint=endpoint,
                            headers={"Content-Type": "application/json", "Accept": "application/json"},
                            request_body={"test": "sample_payload"} if method in ["POST", "PUT", "PATCH"] else None,
                            expected_status=201 if method == "POST" else 200,
                            expected_response={"status": "success"},
                            assertions=[f"status == {201 if method == 'POST' else 200}", "response.body != null"],
                        ),
                    )
                )

            # Propose negative validation test for POST/PUT endpoints
            if method in ["POST", "PUT"]:
                ptc_id = f"PTC-{counter:03d}"
                counter += 1
                neg_title = f"Validate {method} {endpoint} rejection on invalid payload"
                neg_reason = f"Endpoint '{method} {endpoint}' accepts request body; missing negative validation test for bad/empty input."

                proposals.append(
                    ProposedTestCase(
                        id=ptc_id,
                        title=neg_title,
                        description=f"Verify that sending an invalid/empty payload to '{endpoint}' is rejected with HTTP 400 Bad Request.",
                        type=ProposedTestType.API,
                        priority=ProposedTestPriority.MEDIUM,
                        source="LLM Generated",
                        reason=neg_reason,
                        preconditions=["Application service is running"],
                        test_data={"method": method, "endpoint": endpoint, "request_body": {}},
                        steps=[
                            f"Send malformed or empty JSON payload to {method} {endpoint}",
                            "Assert response status is 400 or 422 Unprocessable Entity",
                        ],
                        expected_result="HTTP 400 / 422 with meaningful error message in response body",
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        api_spec=ApiTestSpec(
                            method=method,
                            endpoint=endpoint,
                            headers={"Content-Type": "application/json"},
                            request_body={},
                            expected_status=400,
                            assertions=["status in [400, 422]", "response.error != null"],
                        ),
                    )
                )

        # 2. Generate UI Proposals from UI Workflows
        ui_workflows = self.analysis.get("ui_workflows", [])
        for ui in ui_workflows:
            ui_name = ui.get("name", "Page")
            ui_type = ui.get("type", "FORM")
            sig = f"UI:{ui_name}:{ui_type}"
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)

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

                proposals.append(
                    ProposedTestCase(
                        id=ptc_id,
                        title=title,
                        description=f"End-to-end browser test using Playwright against {ui_name} with automated screenshot & video recording.",
                        type=ProposedTestType.UI,
                        priority=priority,
                        source="LLM Generated",
                        reason=reason,
                        preconditions=[
                            "Frontend and backend servers are running",
                            "Browser is initialized in headless mode",
                        ],
                        test_data={"ui_view": ui_name, "route": f"/{ui_name.lower().replace('page', '')}"},
                        steps=steps,
                        expected_result=expected_result,
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        ui_spec=UiTestSpec(
                            target_route=f"/{ui_name.lower().replace('page', '')}",
                            input_fields=[{"name": "inputField", "type": "text"}],
                            actions=["navigate", "fill", "click", "screenshot"],
                            expected_elements=["[data-testid='main-container']", "header"],
                            assertions=["page.title().not.toBeEmpty()", "expect(page.locator('body')).toBeVisible()"],
                        ),
                    )
                )

        return proposals

    def _generate_brd_proposals(self) -> list[ProposedTestCase]:
        if not self.brd_analysis:
            return []

        proposals: list[ProposedTestCase] = []
        endpoints = self.analysis.get("endpoints", [])
        services = self.analysis.get("services", [])
        ui_workflows = self.analysis.get("ui_workflows", [])

        for idx, wf in enumerate(self.brd_analysis.workflows, 1):
            req_str = ", ".join(wf.requirements_covered) if wf.requirements_covered else "General Business Rule"
            title = f"BRD Workflow: {wf.name}"
            reason = f"Generated from '{wf.name}' (Requirement {req_str}) described in the uploaded BRD."
            priority = ProposedTestPriority.HIGH if wf.priority == "HIGH" else ProposedTestPriority.MEDIUM

            # Cross-reference with discovered application code
            matched_ep = self._match_workflow_to_endpoint(wf, endpoints)
            matched_svc = self._match_workflow_to_service(wf, services)
            matched_ui = self._match_workflow_to_ui(wf, ui_workflows)

            source_label = "Functional Testing Document Generated"
            test_type = ProposedTestType.API
            api_spec = None
            ui_spec = None
            unit_spec = None

            if matched_ep:
                test_type = ProposedTestType.API
                api_spec = ApiTestSpec(
                    method=matched_ep.get("method", "GET"),
                    endpoint=matched_ep.get("endpoint", "/"),
                    headers={"Content-Type": "application/json"},
                    expected_status=200 if not wf.is_negative else 400,
                    assertions=["status == 200" if not wf.is_negative else "status in [400, 422]"],
                )
            elif matched_ui or any(k in wf.name.lower() for k in ["ui", "screen", "page", "browser", "click", "form"]):
                test_type = ProposedTestType.UI
                ui_route = matched_ui.get("name", "/").lower() if matched_ui else f"/{wf.name.lower().replace(' ', '-')}"
                ui_spec = UiTestSpec(
                    target_route=ui_route,
                    actions=["navigate", "fill", "verify"],
                    assertions=["expect(page).toBeVisible()"],
                )
            elif matched_svc:
                svc_name = matched_svc.get('name', 'Service')
                test_type = ProposedTestType.API
                api_spec = ApiTestSpec(
                    method="POST" if wf.is_negative or "create" in wf.name.lower() or "save" in wf.name.lower() else "GET",
                    endpoint=f"/api/{svc_name.lower().replace('service', '')}",
                    headers={"Content-Type": "application/json"},
                    expected_status=200 if not wf.is_negative else 400,
                    assertions=["status == 200" if not wf.is_negative else "status in [400, 422]"],
                )
            else:
                # Default to API/Contract flow
                test_type = ProposedTestType.API
                api_spec = ApiTestSpec(
                    method="POST" if wf.is_negative or "create" in wf.name.lower() or "submit" in wf.name.lower() else "GET",
                    endpoint=f"/api/v1/{re.sub(r'[^a-zA-Z0-9]', '', wf.name.lower())[:16]}",
                    expected_status=200 if not wf.is_negative else 400,
                )

            proposals.append(
                ProposedTestCase(
                    id=f"PTC-BRD-{idx:03d}",
                    title=title,
                    description=wf.description or f"Validation of business requirement: {wf.name}",
                    type=test_type,
                    priority=priority,
                    source="Functional Testing Document Generated",
                    reason=reason,
                    preconditions=wf.preconditions or ["System services online"],
                    test_data={"workflow": wf.name, "negative": wf.is_negative},
                    steps=wf.steps or [f"Execute workflow for {wf.name}"],
                    expected_result=wf.expected_result or "Business constraints and validations satisfied",
                    status=ProposedTestStatus.PROPOSED,
                    generation_source="BRD_DOCUMENT",
                    api_spec=api_spec,
                    ui_spec=ui_spec,
                    unit_spec=unit_spec,
                )
            )

        return proposals

    def _merge_and_deduplicate(
        self,
        ai_proposals: list[ProposedTestCase],
        brd_proposals: list[ProposedTestCase],
    ) -> list[ProposedTestCase]:
        """Combines and deduplicates proposals from both sources."""
        merged: list[ProposedTestCase] = []
        used_brd_indices: set[int] = set()

        for ai_test in ai_proposals:
            matched_brd_idx: int | None = None

            for b_idx, brd_test in enumerate(brd_proposals):
                if b_idx in used_brd_indices:
                    continue

                if self._are_scenarios_equivalent(ai_test, brd_test):
                    matched_brd_idx = b_idx
                    break

            if matched_brd_idx is not None:
                used_brd_indices.add(matched_brd_idx)
                brd_match = brd_proposals[matched_brd_idx]

                # Merge both: enrich with BRD steps & traceability
                merged_reason = f"{ai_test.reason} | Cross-verified with BRD: {brd_match.reason}"
                merged_steps = brd_match.steps if len(brd_match.steps) >= len(ai_test.steps) else ai_test.steps

                merged.append(
                    ProposedTestCase(
                        id=ai_test.id,
                        title=ai_test.title,
                        description=f"{ai_test.description} (Aligned with BRD: {brd_match.title})",
                        type=ai_test.type,
                        priority=ai_test.priority if ai_test.priority == ProposedTestPriority.HIGH else brd_match.priority,
                        source="Functional Testing Document Generated",
                        reason=merged_reason,
                        preconditions=brd_match.preconditions or ai_test.preconditions,
                        test_data=ai_test.test_data or brd_match.test_data,
                        steps=merged_steps,
                        expected_result=ai_test.expected_result,
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="BRD_AND_AI",
                        api_spec=ai_test.api_spec or brd_match.api_spec,
                        unit_spec=ai_test.unit_spec or brd_match.unit_spec,
                        ui_spec=ai_test.ui_spec or brd_match.ui_spec,
                    )
                )
            else:
                merged.append(ai_test)

        # Append remaining unmatched BRD proposals
        for b_idx, brd_test in enumerate(brd_proposals):
            if b_idx not in used_brd_indices:
                merged.append(brd_test)

        return merged

    def _are_scenarios_equivalent(self, ai_test: ProposedTestCase, brd_test: ProposedTestCase) -> bool:
        """Determines if an AI-generated proposal and a BRD proposal target the same core workflow."""
        # 1. Check direct endpoint match
        if (
            ai_test.api_spec
            and brd_test.api_spec
            and ai_test.api_spec.endpoint.lower() == brd_test.api_spec.endpoint.lower()
            and ai_test.api_spec.method == brd_test.api_spec.method
        ):
            return True

        # 2. Check semantic keywords
        ai_tokens = set(re.findall(r"\w{3,}", f"{ai_test.title} {ai_test.source}".lower()))
        brd_tokens = set(re.findall(r"\w{3,}", f"{brd_test.title} {brd_test.description}".lower()))
        overlap = ai_tokens.intersection(brd_tokens)

        critical_keys = ["login", "auth", "checkout", "payment", "order", "register", "search", "user"]
        for k in critical_keys:
            if k in ai_tokens and k in brd_tokens:
                return True

        return len(overlap) >= 3

    def _match_workflow_to_endpoint(self, wf: BrdWorkflow, endpoints: list[dict[str, Any]]) -> dict[str, Any] | None:
        wf_name_lower = wf.name.lower()
        if wf.target_endpoint_hint:
            for ep in endpoints:
                if wf.target_endpoint_hint.lower() in ep.get("endpoint", "").lower():
                    return ep

        for ep in endpoints:
            ep_str = ep.get("endpoint", "").lower()
            tokens = [t for t in re.split(r"[/_\-]", ep_str) if len(t) > 3]
            if any(t in wf_name_lower for t in tokens):
                return ep
        return None

    def _match_workflow_to_service(self, wf: BrdWorkflow, services: list[dict[str, Any]]) -> dict[str, Any] | None:
        wf_name_lower = wf.name.lower()
        for svc in services:
            svc_name = svc.get("name", "").lower()
            if svc_name.replace("service", "") in wf_name_lower and len(svc_name) > 4:
                return svc
        return None

    def _match_workflow_to_ui(self, wf: BrdWorkflow, ui_workflows: list[dict[str, Any]]) -> dict[str, Any] | None:
        wf_name_lower = wf.name.lower()
        for ui in ui_workflows:
            ui_name = ui.get("name", "").lower()
            if ui_name in wf_name_lower or wf_name_lower in ui_name:
                return ui
        return None

    def _reindex_proposals(self, proposals: list[ProposedTestCase]) -> list[ProposedTestCase]:
        for idx, p in enumerate(proposals, 1):
            p.id = f"PTC-{idx:03d}"
        return proposals

    def _create_baseline_smoke_test(self, test_id: str) -> ProposedTestCase:
        return ProposedTestCase(
            id=test_id,
            title="Smoke Test: Application Health & Context Load",
            description="Verify that the migrated application context loads and core health/discovery endpoints respond correctly.",
            type=ProposedTestType.API,
            priority=ProposedTestPriority.HIGH,
            source="LLM Generated",
            reason="Baseline smoke test proposed to verify migrated application startup and health status.",
            preconditions=["Application server is running"],
            test_data={"endpoint": "/health"},
            steps=[
                "Send GET request to /health or /api/health",
                "Verify HTTP 200 status code",
            ],
            expected_result="HTTP status 200 OK with healthy service status",
            status=ProposedTestStatus.PROPOSED,
            generation_source="LLM Generated",
            api_spec=ApiTestSpec(
                method="GET",
                endpoint="/health",
                expected_status=200,
                assertions=["status == 200"],
            ),
        )
