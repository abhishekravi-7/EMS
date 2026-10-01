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
    TestCaseMetadata,
    UiTestSpec,
    UnitTestSpec,
    ValidationStatus,
)


class ProposedTestGenerator:
    """Transforms discovered codebase features, coverage gaps, and BRD business workflows into proposed test cases."""

    def __init__(
        self,
        analysis_data: dict[str, Any],
        brd_analysis: BrdExtractionResult | None = None,
        repo_dir: Path | None = None,
    ) -> None:
        self.analysis = analysis_data
        self.brd_analysis = brd_analysis
        self.repo_dir = repo_dir or (Path(analysis_data["repo_dir"]) if "repo_dir" in analysis_data else None)
        from app.application.use_cases.proposed_tests.dynamic_data_resolver import DynamicDataResolver
        self.data_resolver = DynamicDataResolver(self.repo_dir)
        self.existing_coverage = analysis_data.get("existing_coverage", {})
        self.existing_methods = set(self.existing_coverage.get("methods", []))
        self.existing_classes = set(self.existing_coverage.get("classes", []))
        self.existing_scenarios = set(self.existing_coverage.get("scenarios", []))

    def generate(self) -> list[ProposedTestCase]:
        ai_proposals = self._generate_code_analysis_proposals()
        brd_proposals = self._generate_brd_proposals() if self.brd_analysis and not self.brd_analysis.error else []
        prompt_proposals = self._generate_prompt_driven_proposals()

        combined = self._merge_and_deduplicate(ai_proposals, brd_proposals)
        combined = self._merge_and_deduplicate(combined, prompt_proposals)

        if not combined:
            return [self._create_baseline_smoke_test("PTC-001")]

        return self._reindex_proposals(combined)

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _build_request_body_from_endpoint(ep: dict[str, Any]) -> dict[str, Any] | None:
        """Constructs a realistic (non-hallucinated) request body from endpoint metadata.

        Priority order:
          1. request_body_sample  – extracted from @Entity / @RequestBody class fields
          2. A minimal skeleton derived from path param names (avoids fake 'sample_payload')
          3. None if there is no evidence of a request body at all
        """
        # 1. Use the pre-scanned entity field sample when available
        sample = ep.get("request_body_sample")
        if sample and isinstance(sample, dict) and sample:
            return sample

        # 2. Only synthesise a body if the endpoint is known to accept one
        has_body = ep.get("has_request_body", ep.get("method", "GET").upper() in ("POST", "PUT", "PATCH"))
        if not has_body:
            return None

        # 3. Derive field names from the endpoint path segments (not path params)
        #    e.g. /api/employees  ⇒  {"name": "test-name", "email": "test@example.com"}
        endpoint = ep.get("endpoint", "")
        segments = [s for s in endpoint.split("/") if s and not s.startswith("{")]
        resource = segments[-1] if segments else "item"
        resource_clean = re.sub(r"[^a-zA-Z]", "", resource).lower()

        # Build a minimal, plausible body from known common field patterns
        body: dict[str, Any] = {}
        common_fields: dict[str, dict[str, Any]] = {
            "user":     {"username": "testuser", "email": "test@example.com"},
            "employee": {"name": "Test Employee", "email": "emp@example.com"},
            "todo":     {"title": "Test Task", "completed": False},
            "item":     {"name": "Test Item", "description": "Sample description"},
            "product":  {"name": "Test Product", "price": 9.99},
            "order":    {"quantity": 1, "productId": 1},
            "pet":      {"name": "Test Pet", "species": "Dog"},
            "owner":    {"firstName": "John", "lastName": "Doe", "city": "Springfield"},
            "vet":      {"firstName": "Jane", "lastName": "Smith"},
            "task":     {"title": "New Task", "status": "PENDING"},
        }
        for key, fields in common_fields.items():
            if key in resource_clean:
                body = fields
                break

        # Fallback: build a one-field body from the resource name so it's still traceable
        if not body:
            body = {resource_clean if resource_clean else "data": "test-value"}

        return body

    def _resolve_endpoint_with_sample_ids(self, endpoint: str, path_params: list[str]) -> str:
        """Replaces {paramName} placeholders with realistic sample values discovered dynamically.

        Uses DynamicDataResolver to bind grounded IDs from SQL seeds or live collections.
        """
        resolved = self.data_resolver.resolve_endpoint(endpoint).endpoint
        return resolved

    @staticmethod
    def _infer_success_status(method: str, ep: dict[str, Any]) -> int:
        """Returns the most likely success HTTP status code for a given method.

        Rules (based on Spring / JAX-RS common practice):
          - DELETE → 204 or 200 (use 200 to be safe in assertions)
          - POST that appears to return void or ResponseEntity<Void> → 201
          - POST with evidence of body-returning handler → 200 or 201 (use 200 default)
          - PUT/PATCH → 200
          - GET → 200
        """
        m = method.upper()
        if m == "DELETE":
            return 200  # Some return 204; we use 200 as permissive lower bound
        if m == "POST":
            # POST endpoints that have a @RequestBody are usually 200 or 201.
            # We use 200 here because Spring REST controllers vary widely and
            # asserting 201 causes false failures when the actual response is 200.
            return 200
        return 200


    def _generate_prompt_driven_proposals(self) -> list[ProposedTestCase]:
        suggestions = self.analysis.get("functional_testing_suggestions") or []
        custom_prompt = self.analysis.get("functional_custom_prompt") or self.analysis.get("functional_testing_prompt") or ""
        proposals: list[ProposedTestCase] = []

        scenario_map = {
            "happy-path": ("Happy Path Testing", "Validate positive end-to-end scenarios covering main business workflows and expected outcomes."),
            "negative-testing": ("Negative & Validation Testing", "Validate negative scenarios with invalid/missing inputs and verify proper error handling."),
            "edge-case": ("Edge Case Testing", "Validate edge cases for boundary values, empty inputs, null payloads, and maximum thresholds."),
            "role-permission": ("Role & Permission Testing", "Validate functional test scenarios for user roles, permissions, and authorized access restrictions."),
            "e2e-workflow": ("End-to-End Workflow Testing", "Validate complete end-to-end functional test scenarios across realistic multi-step business workflows."),
        }

        counter = 1
        for sug_id in suggestions:
            if sug_id in scenario_map:
                title_prefix, desc_text = scenario_map[sug_id]
                ptc_id = f"PTC-PRM-{counter:03d}"
                counter += 1
                proposals.append(
                    ProposedTestCase(
                        id=ptc_id,
                        title=f"{title_prefix}: Functional execution validation",
                        description=desc_text,
                        type=ProposedTestType.API if "negative" in sug_id or "happy" in sug_id else ProposedTestType.UI,
                        priority=ProposedTestPriority.HIGH,
                        source="Prompt Scenario",
                        reason=f"Generated specifically based on user-selected prompt scenario suggestion '{title_prefix}'.",
                        preconditions=["Migrated application service is running", "Target test database initialized"],
                        steps=[
                            f"Initialize test context for prompt scenario: {title_prefix}",
                            "Execute functional request payload and observe system responses",
                            "Verify status codes, validation error messages, and state changes",
                        ],
                        expected_result=f"Application outcome satisfies '{title_prefix}' prompt requirement",
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="Prompt Scenario",
                    )
                )

        if custom_prompt and custom_prompt.strip():
            cp_clean = custom_prompt.strip()
            ptc_id = f"PTC-PRM-{counter:03d}"
            proposals.append(
                ProposedTestCase(
                    id=ptc_id,
                    title=f"Custom Functional Prompt: {cp_clean[:55]}...",
                    description=f"User Custom Prompt Scenario: {cp_clean}",
                    type=ProposedTestType.API,
                    priority=ProposedTestPriority.HIGH,
                    source="Custom Prompt",
                    reason=f"Generated directly from user custom functional prompt: '{cp_clean}'",
                    preconditions=["Application service ready"],
                    steps=[
                        f"Execute test workflow matching custom prompt criteria: {cp_clean}",
                        "Inspect response body and database state",
                    ],
                    expected_result="Test passes with expected outcomes specified in custom prompt",
                    status=ProposedTestStatus.PROPOSED,
                    generation_source="Custom Prompt",
                )
            )

        return proposals

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
                reason = f"Endpoint '{method} {endpoint}' detected in {source_class} without direct existing API test coverage."
                priority = ProposedTestPriority.HIGH if any(k in endpoint.lower() for k in ["login", "auth", "user", "order", "payment"]) else ProposedTestPriority.MEDIUM

                # ── Grounded parameter resolution without invented numeric IDs (Fix 1) ──
                path_params: list[str] = ep.get("path_params") or []
                res = self.data_resolver.resolve_endpoint(endpoint)
                resolved_endpoint = res.endpoint
                param_values = res.param_values
                param_sources = res.param_sources
                test_data: dict[str, Any] = {"method": method, "endpoint": resolved_endpoint}
                if param_values:
                    test_data["path_params"] = param_values

                request_body = self._build_request_body_from_endpoint(ep) if method in ("POST", "PUT", "PATCH") else None
                if request_body:
                    test_data["request_body"] = request_body

                # ── Grounded expected status and citation source (Fix 6) ─────────────
                expected_status = ep.get("expected_status") or self._infer_success_status(method, ep)
                expected_status_source = ep.get("expected_status_source") or f"{source_class}: {method} {endpoint} handler declaration"

                # ── Grounded authentication requirement and citation source (Fix 2, 7) ──
                auth_req = ep.get("authentication_required", False)
                auth_source = ep.get("authentication_source") or "No security configuration required"

                dependencies: list[str] = []
                if auth_req:
                    dependencies.append("AUTHENTICATE_SESSION")

                # Check for unresolved dependencies
                has_unresolved_dep = False
                for p in path_params:
                    val = param_values.get(p)
                    if val is None or "{" in str(val) or "}" in str(val):
                        has_unresolved_dep = True
                        ent_name = p.lower().replace("id", "").strip("_") or "entity"
                        dependencies.append(f"CREATE_ENTITY:{ent_name}")

                initial_val_status = ValidationStatus.VALID
                if has_unresolved_dep:
                    initial_val_status = ValidationStatus.BLOCKED_DEPENDENCY
                elif not expected_status_source:
                    initial_val_status = ValidationStatus.REVIEW_REQUIRED

                metadata = TestCaseMetadata(
                    test_id=ptc_id,
                    endpoint=resolved_endpoint,
                    method=method,
                    parameters=param_values,
                    expected_status=expected_status,
                    expected_status_source=expected_status_source,
                    authentication_required=auth_req,
                    authentication_source=auth_source,
                    selector=None,
                    selector_source=None,
                    parameter_sources=param_sources,
                    evidence=[ep.get("classification_source") or f"{source_class}: endpoint definition"],
                    dependencies=dependencies,
                    confidence=1.0 if initial_val_status == ValidationStatus.VALID else 0.7,
                    validation_status=initial_val_status,
                )

                assertions = [f"status == {expected_status}", "response.body != null"]

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
                            "Shared authentication context initialized" if auth_req else "Application environment ready",
                        ],
                        test_data=test_data,
                        steps=[
                            f"Construct {method} request with valid headers{' and payload' if request_body else ''} for {resolved_endpoint}",
                            "Send HTTP request to the API server using shared APIRequestContext",
                            "Inspect response status code and JSON response body",
                        ],
                        expected_result=f"HTTP status code is {expected_status} and response payload is valid",
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        metadata=metadata,
                        api_spec=ApiTestSpec(
                            method=method,
                            endpoint=resolved_endpoint,
                            headers={"Content-Type": "application/json", "Accept": "application/json"},
                            request_body=request_body,
                            expected_status=expected_status,
                            expected_response=None,
                            assertions=assertions,
                        ),
                    )
                )

            # Propose negative validation test ONLY for endpoints that genuinely accept a body
            has_body = ep.get("has_request_body", method in ("POST", "PUT"))
            if method in ["POST", "PUT"] and has_body:
                ptc_id = f"PTC-{counter:03d}"
                counter += 1
                neg_title = f"Validate {method} {endpoint} rejection on invalid payload"
                neg_reason = f"Endpoint '{method} {endpoint}' accepts a request body; negative validation test for bad/empty input is required."

                concrete_neg_ep = self.data_resolver.resolve_endpoint(endpoint).endpoint
                auth_req = ep.get("authentication_required", False)
                auth_source = ep.get("authentication_source") or "Public endpoint"

                neg_metadata = TestCaseMetadata(
                    test_id=ptc_id,
                    endpoint=concrete_neg_ep,
                    method=method,
                    parameters={},
                    expected_status=400,
                    expected_status_source="Controller request validation (REVIEW_REQUIRED)",
                    authentication_required=auth_req,
                    authentication_source=auth_source,
                    selector=None,
                    selector_source=None,
                    parameter_sources={},
                    evidence=[f"Request validation check on {method} {endpoint}"],
                    dependencies=["AUTHENTICATE_SESSION"] if auth_req else [],
                    confidence=0.8,
                    validation_status=ValidationStatus.REVIEW_REQUIRED,
                )

                proposals.append(
                    ProposedTestCase(
                        id=ptc_id,
                        title=neg_title,
                        description=f"Verify that sending an invalid/empty payload to '{endpoint}' is rejected with HTTP 400 or 422.",
                        type=ProposedTestType.API,
                        priority=ProposedTestPriority.MEDIUM,
                        source="LLM Generated",
                        reason=neg_reason,
                        preconditions=["Application service is running"],
                        test_data={"method": method, "endpoint": concrete_neg_ep, "request_body": {}},
                        steps=[
                            f"Send malformed or empty JSON payload to {method} {concrete_neg_ep}",
                            "Assert response status is 400 or 422 Unprocessable Entity",
                        ],
                        expected_result="HTTP 400 or 422 with meaningful error message in response body",
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        metadata=neg_metadata,
                        api_spec=ApiTestSpec(
                            method=method,
                            endpoint=concrete_neg_ep,
                            headers={"Content-Type": "application/json"},
                            request_body={},
                            expected_status=400,
                            assertions=["status in [400, 422]"],
                        ),
                    )
                )

        # 2. Generate UI Proposals from UI Workflows
        ui_workflows = self.analysis.get("ui_workflows", [])
        for ui in ui_workflows:
            if ui.get("is_fragment", False):
                continue

            ui_name = ui.get("name", "Page")
            ui_type = ui.get("type", "FORM")
            ui_route = ui.get("route") or f"/{ui_name.lower().replace('page', '')}"
            grounded_selectors = ui.get("grounded_selectors", [])
            grounded_inputs = ui.get("input_fields", [])
            grounded_actions = ui.get("actions", [])

            sig = f"UI:{ui_name}:{ui_route}"
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)

            is_covered = any(ui_name.lower() in ec for ec in self.existing_classes)
            if is_covered:
                continue

            # Select primary grounded selectors for assertion
            conditional_kws = ["done", "error", "success", "alert", "modal", "popup", "message", "warning", "loading", "spinner"]
            stable_selectors = [
                s for s in grounded_selectors
                if not s.startswith("input") and not any(k in s.lower() for k in conditional_kws)
            ]
            expected_elements = stable_selectors[:3]
            if not expected_elements:
                for fallback_sel in ["main", "table", "form", ".container", "nav", "h1", "h2", "body"]:
                    if any(fallback_sel in s for s in grounded_selectors):
                        expected_elements.append(fallback_sel)
                        break
            if not expected_elements:
                expected_elements = ["body"]

            submit_btn = ui.get("submit_button") or "Submit"
            tbl_headers = ui.get("table_headers", [])
            headings = ui.get("headings", [])
            fields_summary = ", ".join(f.get("label") or f.get("name") for f in grounded_inputs[:4]) if grounded_inputs else "form input fields"
            headers_summary = ", ".join(tbl_headers[:4]) if tbl_headers else "data columns"
            primary_sel = expected_elements[0] if expected_elements else "body"

            # ── Fix 9: Separate logically distinct authentication scenarios ──
            if ui.get("has_login") or ui.get("type") == "AUTH":
                # Scenario A: GET <page> while unauthenticated → verify the expected form/content
                ptc_id_a = f"PTC-{counter:03d}"
                counter += 1
                title_a = f"Playwright UI: Verify unauthenticated login view controls on {ui_name}"
                desc_a = f"Verify that navigating to '{ui_route}' as an unauthenticated visitor renders the login form and credentials controls."
                steps_a = [
                    f"Open browser and navigate to '{ui_route}' as unauthenticated visitor",
                    f"Verify login form container and credential input fields ({fields_summary}) are visible",
                    f"Verify submission action control ('{submit_btn}') is accessible",
                    "Capture full-page screenshot evidence",
                ]
                meta_a = TestCaseMetadata(
                    test_id=ptc_id_a,
                    endpoint=ui_route,
                    method="GET",
                    parameters={},
                    expected_status=200,
                    expected_status_source=f"{ui.get('file', 'login.html')}: unauthenticated login page view",
                    authentication_required=False,
                    authentication_source="Public login landing page",
                    selector=primary_sel,
                    selector_source=f"{ui.get('file')}: form element {primary_sel}",
                    parameter_sources={},
                    evidence=[f"{ui.get('file')}: Login UI controls definition"],
                    dependencies=[],
                    confidence=1.0,
                    validation_status=ValidationStatus.VALID,
                )
                proposals.append(
                    ProposedTestCase(
                        id=ptc_id_a,
                        title=title_a,
                        description=desc_a,
                        type=ProposedTestType.UI,
                        priority=ProposedTestPriority.HIGH,
                        source="LLM Generated",
                        reason=f"Login view detected in {ui.get('file')}; unauthenticated form render verification.",
                        preconditions=["Frontend and backend servers are running", "Browser session is unauthenticated"],
                        test_data={"ui_view": ui_name, "route": ui_route},
                        steps=steps_a,
                        expected_result="Login form and authentication controls render successfully for unauthenticated visitor",
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        metadata=meta_a,
                        ui_spec=UiTestSpec(
                            target_route=ui_route,
                            input_fields=grounded_inputs if grounded_inputs else [],
                            actions=["navigate", "screenshot"],
                            expected_elements=expected_elements,
                            assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                        ),
                    )
                )

                # Scenario B: Submit valid credentials → verify successful authentication → verify destination
                ptc_id_b = f"PTC-{counter:03d}"
                counter += 1
                title_b = f"Playwright UI: Verify user authentication workflow and redirect on {ui_name}"
                desc_b = f"Verify successful authentication workflow submission and redirection to authorized destination."
                steps_b = [
                    f"Navigate to '{ui_route}' in browser",
                    "Fill verified credentials discovered from repository evidence (Username, Password)",
                    f"Submit authentication form by clicking '{submit_btn}'",
                    "Verify successful authentication and redirect away from login view",
                    "Confirm authenticated destination view is reached",
                    "Capture full-page screenshot evidence",
                ]
                meta_b = TestCaseMetadata(
                    test_id=ptc_id_b,
                    endpoint=ui_route,
                    method="POST",
                    parameters={"username": "discovered_user", "password": "discovered_password"},
                    expected_status=302,
                    expected_status_source=f"{ui.get('file')}: successful authentication redirect",
                    authentication_required=True,
                    authentication_source="Authentication workflow with repository credentials",
                    selector=primary_sel,
                    selector_source=f"{ui.get('file')}: form element {primary_sel}",
                    parameter_sources={"username": "Repository credentials", "password": "Repository credentials"},
                    evidence=[f"{ui.get('file')}: Authentication workflow definition"],
                    dependencies=["AUTHENTICATE_CREDENTIALS"],
                    confidence=1.0,
                    validation_status=ValidationStatus.VALID,
                )
                proposals.append(
                    ProposedTestCase(
                        id=ptc_id_b,
                        title=title_b,
                        description=desc_b,
                        type=ProposedTestType.UI,
                        priority=ProposedTestPriority.HIGH,
                        source="LLM Generated",
                        reason=f"Authentication workflow detected in {ui.get('file')}; end-to-end credential submission and redirect verification.",
                        preconditions=["Frontend and backend servers are running", "Valid repository credentials available"],
                        test_data={"ui_view": ui_name, "route": ui_route},
                        steps=steps_b,
                        expected_result="User authentication succeeds, page navigates away from login view, and authenticated session is established",
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        metadata=meta_b,
                        ui_spec=UiTestSpec(
                            target_route=ui_route,
                            input_fields=grounded_inputs if grounded_inputs else [],
                            actions=[f"click button: {submit_btn}", "verify redirection"],
                            expected_elements=[".container, table, main, nav, .alert-success"],
                            assertions=["expect(page).not.toHaveURL(new RegExp('.*login.*'))"],
                        ),
                    )
                )

            elif ui.get("has_form") and not ui.get("has_table"):
                ptc_id = f"PTC-{counter:03d}"
                counter += 1
                title = f"Playwright UI: Validate form submission and feedback on {ui_name}"
                reason = f"Interactive form detected in '{ui_name}' at '{ui_route}'; Playwright browser test proposed for data entry and submission."
                priority = ProposedTestPriority.MEDIUM
                steps = [
                    f"Navigate to '{ui_route}' in browser",
                    f"Fill required form inputs ({fields_summary})",
                    f"Submit form by clicking '{submit_btn}'",
                    "Verify post-submission confirmation or redirection",
                    "Capture full-page screenshot evidence",
                ]
                expected_result = "Form inputs validate, submission completes, and feedback or redirection is displayed"

                meta = TestCaseMetadata(
                    test_id=ptc_id,
                    endpoint=ui_route,
                    method="GET",
                    parameters={},
                    expected_status=200,
                    expected_status_source=f"{ui.get('file')}: form view render",
                    authentication_required=True,
                    authentication_source=f"{ui.get('file')}: form view behind security filter",
                    selector=primary_sel,
                    selector_source=f"{ui.get('file')}: primary form selector {primary_sel}",
                    parameter_sources={},
                    evidence=[f"{ui.get('file')}: Form UI definition"],
                    dependencies=["AUTHENTICATE_SESSION"],
                    confidence=1.0,
                    validation_status=ValidationStatus.VALID,
                )

                proposals.append(
                    ProposedTestCase(
                        id=ptc_id,
                        title=title,
                        description=f"End-to-end browser test using Playwright against '{ui_route}' with automated screenshot & video recording.",
                        type=ProposedTestType.UI,
                        priority=priority,
                        source="LLM Generated",
                        reason=reason,
                        preconditions=["Frontend and backend servers are running", "Authenticated session active"],
                        test_data={"ui_view": ui_name, "route": ui_route},
                        steps=steps,
                        expected_result=expected_result,
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        metadata=meta,
                        ui_spec=UiTestSpec(
                            target_route=ui_route,
                            input_fields=grounded_inputs if grounded_inputs else [],
                            actions=grounded_actions if grounded_actions else ["navigate", "screenshot"],
                            expected_elements=expected_elements,
                            assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                        ),
                    )
                )

            elif ui.get("has_table") or ui.get("type") == "TABLE":
                ptc_id = f"PTC-{counter:03d}"
                counter += 1
                title = f"Playwright UI: Verify data table rendering and action triggers on {ui_name}"
                reason = f"Data table view detected in '{ui_name}' at '{ui_route}'; Playwright browser test proposed for tabular records and actions."
                priority = ProposedTestPriority.MEDIUM
                steps = [
                    f"Navigate to '{ui_route}' in browser",
                    f"Verify data table renders with column headers ({headers_summary})",
                    "Verify data records and action controls are active",
                    "Capture full-page screenshot evidence",
                ]
                expected_result = "Data table renders with valid columns, records, and action triggers"

                meta = TestCaseMetadata(
                    test_id=ptc_id,
                    endpoint=ui_route,
                    method="GET",
                    parameters={},
                    expected_status=200,
                    expected_status_source=f"{ui.get('file')}: data table view render",
                    authentication_required=True,
                    authentication_source=f"{ui.get('file')}: data view behind security filter",
                    selector=primary_sel,
                    selector_source=f"{ui.get('file')}: table selector {primary_sel}",
                    parameter_sources={},
                    evidence=[f"{ui.get('file')}: Tabular records view"],
                    dependencies=["AUTHENTICATE_SESSION"],
                    confidence=1.0,
                    validation_status=ValidationStatus.VALID,
                )

                proposals.append(
                    ProposedTestCase(
                        id=ptc_id,
                        title=title,
                        description=f"End-to-end browser test using Playwright against '{ui_route}' with automated screenshot & video recording.",
                        type=ProposedTestType.UI,
                        priority=priority,
                        source="LLM Generated",
                        reason=reason,
                        preconditions=["Frontend and backend servers are running", "Authenticated session active"],
                        test_data={"ui_view": ui_name, "route": ui_route},
                        steps=steps,
                        expected_result=expected_result,
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        metadata=meta,
                        ui_spec=UiTestSpec(
                            target_route=ui_route,
                            input_fields=grounded_inputs if grounded_inputs else [],
                            actions=grounded_actions if grounded_actions else ["navigate", "screenshot"],
                            expected_elements=expected_elements,
                            assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                        ),
                    )
                )

            elif ui.get("type") == "DASHBOARD" or "dashboard" in ui_name.lower():
                ptc_id = f"PTC-{counter:03d}"
                counter += 1
                heading_name = headings[0] if headings else "Dashboard Overview"
                title = f"Playwright UI: Verify overview metrics and statistics on {ui_name}"
                reason = f"Dashboard view detected in '{ui_name}' at '{ui_route}'; Playwright browser test proposed for overview metrics and stat cards."
                priority = ProposedTestPriority.MEDIUM
                steps = [
                    f"Navigate to '{ui_route}' in browser",
                    f"Verify dashboard overview heading ('{heading_name}')",
                    "Verify summary statistics metric cards render with populated data",
                    "Capture full-page screenshot evidence",
                ]
                expected_result = "Dashboard metrics, stat cards, and overview layout render successfully"

                meta = TestCaseMetadata(
                    test_id=ptc_id,
                    endpoint=ui_route,
                    method="GET",
                    parameters={},
                    expected_status=200,
                    expected_status_source=f"{ui.get('file')}: dashboard view render",
                    authentication_required=True,
                    authentication_source=f"{ui.get('file')}: dashboard view behind security filter",
                    selector=primary_sel,
                    selector_source=f"{ui.get('file')}: dashboard container {primary_sel}",
                    parameter_sources={},
                    evidence=[f"{ui.get('file')}: Dashboard overview view"],
                    dependencies=["AUTHENTICATE_SESSION"],
                    confidence=1.0,
                    validation_status=ValidationStatus.VALID,
                )

                proposals.append(
                    ProposedTestCase(
                        id=ptc_id,
                        title=title,
                        description=f"End-to-end browser test using Playwright against '{ui_route}' with automated screenshot & video recording.",
                        type=ProposedTestType.UI,
                        priority=priority,
                        source="LLM Generated",
                        reason=reason,
                        preconditions=["Frontend and backend servers are running", "Authenticated session active"],
                        test_data={"ui_view": ui_name, "route": ui_route},
                        steps=steps,
                        expected_result=expected_result,
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        metadata=meta,
                        ui_spec=UiTestSpec(
                            target_route=ui_route,
                            input_fields=grounded_inputs if grounded_inputs else [],
                            actions=grounded_actions if grounded_actions else ["navigate", "screenshot"],
                            expected_elements=expected_elements,
                            assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                        ),
                    )
                )

            else:
                ptc_id = f"PTC-{counter:03d}"
                counter += 1
                title = f"Playwright UI: Verify page rendering and navigation on {ui_name}"
                reason = f"UI view '{ui_name}' detected at '{ui_route}'; Playwright visual verification proposed."
                priority = ProposedTestPriority.LOW
                steps = [
                    f"Open browser and navigate to '{ui_route}'",
                    "Verify header, navigation links, and primary content container",
                    "Capture full-page screenshot evidence",
                ]
                expected_result = "Page renders without layout breaks or JavaScript console errors"

                meta = TestCaseMetadata(
                    test_id=ptc_id,
                    endpoint=ui_route,
                    method="GET",
                    parameters={},
                    expected_status=200,
                    expected_status_source=f"{ui.get('file')}: view render",
                    authentication_required=False,
                    authentication_source="Public application view",
                    selector=primary_sel,
                    selector_source=f"{ui.get('file')}: element {primary_sel}",
                    parameter_sources={},
                    evidence=[f"{ui.get('file')}: Visual navigation view"],
                    dependencies=[],
                    confidence=1.0,
                    validation_status=ValidationStatus.VALID,
                )

                proposals.append(
                    ProposedTestCase(
                        id=ptc_id,
                        title=title,
                        description=f"End-to-end browser test using Playwright against '{ui_route}' with automated screenshot & video recording.",
                        type=ProposedTestType.UI,
                        priority=priority,
                        source="LLM Generated",
                        reason=reason,
                        preconditions=[
                            "Frontend and backend servers are running",
                            "Browser is initialized in headless mode",
                        ],
                        test_data={"ui_view": ui_name, "route": ui_route},
                        steps=steps,
                        expected_result=expected_result,
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        metadata=meta,
                        ui_spec=UiTestSpec(
                            target_route=ui_route,
                            input_fields=grounded_inputs if grounded_inputs else [],
                            actions=grounded_actions if grounded_actions else ["navigate", "screenshot"],
                            expected_elements=expected_elements,
                            assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
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
            title = wf.name
            reason = f"Derived from Functional Testing Document scenario '{wf.name}' ({req_str})."
            priority = ProposedTestPriority.HIGH if wf.priority == "HIGH" else (ProposedTestPriority.LOW if wf.priority == "LOW" else ProposedTestPriority.MEDIUM)

            # Cross-reference with discovered application code
            matched_ep = self._match_workflow_to_endpoint(wf, endpoints)
            matched_svc = self._match_workflow_to_service(wf, services)
            matched_ui = self._match_workflow_to_ui(wf, ui_workflows)

            test_type = ProposedTestType.API
            api_spec = None
            ui_spec = None
            unit_spec = None

            if wf.target_endpoint_hint:
                test_type = ProposedTestType.API
                method = wf.target_method_hint or "GET"
                endpoint = wf.target_endpoint_hint
                if not endpoint.startswith("/"):
                    endpoint = f"/{endpoint}"
                expected_status = wf.expected_status_hint or (200 if not wf.is_negative else 400)
                # Build a realistic body from matched endpoint metadata (if found)
                matched_ep_for_hint = self._match_workflow_to_endpoint(wf, endpoints)
                body = None
                if method in ("POST", "PUT", "PATCH"):
                    if matched_ep_for_hint:
                        body = self._build_request_body_from_endpoint(matched_ep_for_hint)
                    if not body:
                        body = {}  # Empty dict is better than {"test": "sample_payload"}
                api_spec = ApiTestSpec(
                    method=method,
                    endpoint=endpoint,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    request_body=body,
                    expected_status=expected_status,
                    assertions=[f"status == {expected_status}"],
                )
            elif matched_ep:
                test_type = ProposedTestType.API
                method = wf.target_method_hint or matched_ep.get("method", "GET")
                endpoint = matched_ep.get("endpoint", "/")
                expected_status = wf.expected_status_hint or (200 if not wf.is_negative else 400)
                api_spec = ApiTestSpec(
                    method=method,
                    endpoint=endpoint,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    expected_status=expected_status,
                    assertions=[f"status == {expected_status}"],
                )
            elif matched_ui and not matched_ui.get("is_fragment", False) and not (matched_ui.get("route", "")).startswith("/api/"):
                test_type = ProposedTestType.UI
                ui_route = matched_ui.get("route") or f"/{matched_ui.get('name', '').lower()}"
                ui_sels = (matched_ui.get("grounded_selectors") or [])[:2] or ["h1, h2, form, table, nav, div"]
                ui_spec = UiTestSpec(
                    target_route=ui_route,
                    actions=matched_ui.get("actions") or ["navigate", "fill", "verify"],
                    input_fields=matched_ui.get("input_fields") or [],
                    expected_elements=ui_sels,
                    assertions=[f"expect(page.locator('{ui_sels[0]}')).toBeVisible()"],
                )
            elif any(k in wf.name.lower() or k in " ".join(wf.steps).lower() for k in ["build", "mvn", "gradle", "compile"]):
                test_type = ProposedTestType.UNIT
                unit_spec = UnitTestSpec(
                    target_class="ApplicationBuildValidation",
                    target_method="validateCleanBuild",
                )
            elif matched_svc:
                svc_name = matched_svc.get('name', 'Service')
                test_type = ProposedTestType.API
                api_spec = ApiTestSpec(
                    method=wf.target_method_hint or ("POST" if wf.is_negative or "create" in wf.name.lower() else "GET"),
                    endpoint=f"/api/{svc_name.lower().replace('service', '')}",
                    headers={"Content-Type": "application/json"},
                    expected_status=wf.expected_status_hint or (200 if not wf.is_negative else 400),
                    assertions=[f"status == {wf.expected_status_hint or 200}"],
                )
            else:
                test_type = ProposedTestType.API
                fallback_ep = endpoints[0].get("endpoint", "/api/employees") if endpoints else "/health"
                fallback_method = endpoints[0].get("method", "GET") if endpoints else "GET"
                api_spec = ApiTestSpec(
                    method=wf.target_method_hint or fallback_method,
                    endpoint=fallback_ep,
                    expected_status=200 if not wf.is_negative else 400,
                )

            proposals.append(
                ProposedTestCase(
                    id=f"PTC-BRD-{idx:03d}",
                    title=title,
                    description=wf.description or f"Validation of functional scenario: {wf.name}",
                    type=test_type,
                    priority=priority,
                    source="Functional Doc",
                    reason=reason,
                    preconditions=wf.preconditions or ["System services online"],
                    test_data={"workflow": wf.name, "negative": wf.is_negative},
                    steps=wf.steps or [f"Execute scenario: {wf.name}"],
                    expected_result=wf.expected_result or "Business constraints and validations satisfied",
                    status=ProposedTestStatus.PROPOSED,
                    generation_source="FUNCTIONAL_DOC",
                    document_id=self.brd_analysis.filename,
                    source_reference=wf.source_reference or f"{self.brd_analysis.filename}: [{req_str}] {title}",
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
        """Combines proposals preserving distinct source classification for LLM Generated and Functional Doc."""
        seen_brd: set[str] = set()
        deduped_brd: list[ProposedTestCase] = []
        for bp in brd_proposals:
            sig = f"{bp.source_reference or bp.title}:{bp.type.value}"
            if sig in seen_brd:
                continue
            seen_brd.add(sig)
            deduped_brd.append(bp)

        return list(ai_proposals) + deduped_brd

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
            norm_hint = re.sub(r"^(?:GET|POST|PUT|DELETE|PATCH)\s+", "", wf.target_endpoint_hint.strip(), flags=re.IGNORECASE).split("?")[0].rstrip(".")
            for ep in endpoints:
                ep_val = ep.get("endpoint", "")
                if norm_hint.lower() in ep_val.lower() or ep_val.lower() in norm_hint.lower():
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
            if p.metadata:
                p.metadata.test_id = p.id
            else:
                ep = (p.api_spec.endpoint if p.api_spec else (p.ui_spec.target_route if p.ui_spec else "/")) or "/"
                method = p.api_spec.method if p.api_spec else ("POST" if "post" in p.title.lower() or "submit" in p.title.lower() else "GET")
                expected_st = p.api_spec.expected_status if p.api_spec else 200
                primary_sel = p.ui_spec.expected_elements[0] if (p.ui_spec and p.ui_spec.expected_elements) else None
                p.metadata = TestCaseMetadata(
                    test_id=p.id,
                    endpoint=ep,
                    method=method,
                    parameters=p.test_data.get("path_params") or {} if p.test_data else {},
                    expected_status=expected_st,
                    expected_status_source=f"{p.source}: inferred expected status",
                    authentication_required=False,
                    authentication_source="Public or default access",
                    selector=primary_sel,
                    selector_source=f"DOM element {primary_sel}" if primary_sel else None,
                    parameter_sources={},
                    evidence=[f"{p.source}: {p.title}"],
                    dependencies=[],
                    confidence=1.0 if p.type in (ProposedTestType.API, ProposedTestType.UI) else 0.5,
                    validation_status=ValidationStatus.VALID,
                )
        return proposals

    def _create_baseline_smoke_test(self, test_id: str) -> ProposedTestCase:
        meta = TestCaseMetadata(
            test_id=test_id,
            endpoint="/health",
            method="GET",
            parameters={},
            expected_status=200,
            expected_status_source="Default health probe",
            authentication_required=False,
            authentication_source="Public health probe",
            selector=None,
            selector_source=None,
            parameter_sources={},
            evidence=["Baseline smoke test definition"],
            dependencies=[],
            confidence=1.0,
            validation_status=ValidationStatus.VALID,
        )
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
            metadata=meta,
            api_spec=ApiTestSpec(
                method="GET",
                endpoint="/health",
                expected_status=200,
                assertions=["status == 200"],
            ),
        )
