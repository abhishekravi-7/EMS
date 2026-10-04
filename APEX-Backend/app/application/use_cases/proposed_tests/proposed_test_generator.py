"""Generates structured, traceable Proposed Functional Test Cases based on code gap analysis and BRD workflows."""

from __future__ import annotations

import re
from pathlib import Path
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

PLATFORM_CATEGORIES: dict[str, dict[str, str]] = {
    "happy-path": {
        "id": "happy-path",
        "name": "Happy Path Testing",
        "definition": "Generate positive end-to-end scenarios covering the main business workflows of the application. Verify that valid user inputs result in the expected outcomes.",
    },
    "negative-testing": {
        "id": "negative-testing",
        "name": "Negative & Validation Testing",
        "definition": "Generate negative test scenarios by providing invalid, missing, or unexpected inputs. Verify that the application displays appropriate validation messages and handles errors correctly.",
    },
    "edge-case": {
        "id": "edge-case",
        "name": "Edge Case Testing",
        "definition": "Generate edge-case scenarios for boundary values, empty inputs, maximum and minimum values, unusual combinations of inputs, and other conditions that could expose unexpected application behavior.",
    },
    "role-permission": {
        "id": "role-permission",
        "name": "Role & Permission Testing",
        "definition": "Generate functional test scenarios for different user roles and permissions. Verify that each role can access only the features and actions they are authorized to use, and that unauthorized operations are properly restricted.",
    },
    "e2e-workflow": {
        "id": "e2e-workflow",
        "name": "End-to-End Workflow Testing",
        "definition": "Generate complete end-to-end functional test scenarios that follow realistic business workflows across multiple pages or features. Validate the data and expected outcome at each important step.",
    },
}


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
        self.built_prompt: str | None = None
        self.generation_summary: dict[str, Any] = {}

    def _parse_directives(self) -> dict[str, Any]:
        raw_sug = self.analysis.get("functional_testing_suggestions")
        if isinstance(raw_sug, list) and len(raw_sug) > 0:
            enabled_cat_ids = set(raw_sug)
        else:
            enabled_cat_ids = set(PLATFORM_CATEGORIES.keys())

        custom_prompt = (
            self.analysis.get("functional_custom_prompt")
            or self.analysis.get("functional_testing_prompt")
            or ""
        ).strip()

        api_target: int | None = None
        ui_target: int | None = None
        total_target: int | None = None

        if custom_prompt:
            p = custom_prompt.strip()

            # 1. Match UI target: e.g. "50 ui testcase", "50 ui test cases", "generate 50 ui tests", "50 ui"
            m_ui = re.search(
                r"(?:generate|create|build|run|produce|want|need)?\s*(\d+)\s*(?:ui|frontend|browser|playwright|e2e)\s*(?:functional\s+)?(?:testcases?|tests?|cases?)?",
                p,
                re.IGNORECASE,
            )
            if m_ui:
                ui_target = int(m_ui.group(1))

            # 2. Match API target: e.g. "30 api testcases", "30 api tests", "generate 30 api"
            m_api = re.search(
                r"(?:generate|create|build|run|produce|want|need)?\s*(\d+)\s*(?:api|backend|rest|endpoint)\s*(?:functional\s+)?(?:testcases?|tests?|cases?)?",
                p,
                re.IGNORECASE,
            )
            if m_api:
                api_target = int(m_api.group(1))

            # 3. Match Total target: e.g. "50 testcases", "generate 50 functional testcases", "50 test cases", "50 tests"
            m_tot = re.search(
                r"(?:generate|create|build|run|produce|want|need)?\s*(\d+)\s*(?:functional\s+)?(?:testcases?|tests?|cases?)",
                p,
                re.IGNORECASE,
            )
            if m_tot:
                val = int(m_tot.group(1))
                is_ui_num = (ui_target == val) and bool(re.search(rf"{val}\s*(?:ui|frontend|browser|playwright)", p, re.IGNORECASE))
                is_api_num = (api_target == val) and bool(re.search(rf"{val}\s*(?:api|backend|rest)", p, re.IGNORECASE))
                if not is_ui_num and not is_api_num:
                    total_target = val

            # CRITICAL DYNAMIC DIRECTIVE ENFORCEMENT:
            # If the user specifically prompted for UI testcases without requesting API testcases:
            if ui_target is not None and api_target is None and total_target is None:
                if not re.search(r"\b(?:api|backend|rest|endpoint)\b", p, re.IGNORECASE):
                    api_target = 0

            # If the user specifically prompted for API testcases without requesting UI testcases:
            if api_target is not None and ui_target is None and total_target is None:
                if not re.search(r"\b(?:ui|frontend|browser|playwright)\b", p, re.IGNORECASE):
                    ui_target = 0

        no_duplicates = True
        if custom_prompt and re.search(r"allow\s+duplicate", custom_prompt, re.IGNORECASE):
            no_duplicates = False

        return {
            "enabled_cat_ids": enabled_cat_ids,
            "custom_prompt": custom_prompt,
            "api_target": api_target,
            "ui_target": ui_target,
            "total_target": total_target,
            "no_duplicates": no_duplicates,
        }

    def build_prompt(self, directives: dict[str, Any]) -> str:
        from app.infrastructure.llm.prompt_templates import build_functional_test_generator_prompt

        enabled_ids = directives["enabled_cat_ids"]
        enabled_cat_lines = [
            f"- {PLATFORM_CATEGORIES[cid]['name']} (id: {cid})"
            for cid in enabled_ids
            if cid in PLATFORM_CATEGORIES
        ]
        enabled_categories_str = "\n".join(enabled_cat_lines) if enabled_cat_lines else "All categories enabled"

        category_def_blocks = [
            f"### {PLATFORM_CATEGORIES[cid]['name']}\n{PLATFORM_CATEGORIES[cid]['definition']}"
            for cid in enabled_ids
            if cid in PLATFORM_CATEGORIES
        ]
        category_definitions_str = "\n\n".join(category_def_blocks) if category_def_blocks else "Standard platform category definitions."

        endpoints = self.analysis.get("endpoints", [])
        ep_summary = f"{len(endpoints)} REST API endpoints discovered: " + ", ".join(
            f"{ep.get('method')} {ep.get('endpoint')}" for ep in endpoints[:15]
        )
        if len(endpoints) > 15:
            ep_summary += f" ... (+{len(endpoints) - 15} more)"

        ui_wfs = self.analysis.get("ui_workflows", [])
        ui_summary = f"{len(ui_wfs)} UI routes/pages discovered: " + ", ".join(
            f"{ui.get('route')} ({ui.get('name')})" for ui in ui_wfs[:10]
        )

        entities = self.analysis.get("entities", []) or self.analysis.get("services", [])
        ent_summary = ", ".join(e.get("name", "") for e in entities[:10]) if entities else "Discovered repository domain entities and controllers"

        existing_tests = self.analysis.get("existing_tests", [])
        existing_summary = f"{len(existing_tests)} existing tests detected in repository test suites"

        prompt = build_functional_test_generator_prompt(
            enabled_categories=enabled_categories_str,
            category_definitions=category_definitions_str,
            custom_prompt_text=directives["custom_prompt"] or "(No custom prompt specified)",
            discovered_api_endpoints=ep_summary,
            discovered_ui_routes=ui_summary,
            discovered_entities_and_rules=ent_summary,
            existing_test_inventory=existing_summary,
        )
        return prompt

    def generate(self) -> list[ProposedTestCase]:
        directives = self._parse_directives()
        self.built_prompt = self.build_prompt(directives)

        api_proposals = self._generate_api_proposals(directives)
        ui_proposals = self._generate_ui_proposals(directives)
        brd_proposals = self._generate_brd_proposals() if self.brd_analysis and not self.brd_analysis.error else []

        combined = self._enforce_targets_and_deduplicate(api_proposals, ui_proposals, brd_proposals, directives)

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

        NOTE: This is a HEURISTIC DEFAULT. When this method is used, callers must
        mark expected_status_source as 'heuristic-default' so the executor and
        downstream reporting can distinguish evidence-backed expectations from defaults.
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

    @staticmethod
    def _infer_success_status_source(method: str, ep: dict[str, Any]) -> str:
        """Returns the source label for the inferred status (always a heuristic when called)."""
        return "heuristic-default (no explicit @ResponseStatus / ResponseEntity annotation found in controller source)"


    def _generate_prompt_driven_proposals(self) -> list[ProposedTestCase]:
        """Deprecated placeholder generator replaced by category-driven dynamic generation."""
        return []

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

    def _distribute_by_category(self, proposals: list[ProposedTestCase], target_count: int | None) -> list[ProposedTestCase]:
        if target_count is not None and target_count <= 0:
            return []
        if target_count is None or len(proposals) <= target_count:
            return proposals

        by_cat: dict[str, list[ProposedTestCase]] = {}
        for p in proposals:
            cat = p.category or "General"
            by_cat.setdefault(cat, []).append(p)

        selected: list[ProposedTestCase] = []
        cat_keys = list(by_cat.keys())
        indices = {k: 0 for k in cat_keys}

        while len(selected) < target_count:
            added_in_round = False
            for k in cat_keys:
                if len(selected) >= target_count:
                    break
                idx = indices[k]
                if idx < len(by_cat[k]):
                    selected.append(by_cat[k][idx])
                    indices[k] += 1
                    added_in_round = True
            if not added_in_round:
                break
        return selected

    def _expand_ui_proposals_to_target(
        self,
        existing_ui: list[ProposedTestCase],
        target_count: int,
    ) -> list[ProposedTestCase]:
        if len(existing_ui) >= target_count:
            return existing_ui

        expanded = list(existing_ui)
        ui_workflows = self.analysis.get("ui_workflows", [])
        if not ui_workflows:
            return expanded

        # 1. Responsive Viewport Scenarios (Mobile & Tablet)
        viewports = [
            ("Mobile Viewport", 375, 667, "mobile layout responsiveness"),
            ("Tablet Viewport", 768, 1024, "tablet layout responsiveness"),
        ]
        for ui in ui_workflows:
            if len(expanded) >= target_count:
                break
            ui_name = ui.get("name", "Page")
            ui_route = ui.get("route") or f"/{ui_name.lower().replace('page', '')}"
            primary_sel = (ui.get("grounded_selectors") or ["body"])[0]

            for vp_label, w, h, desc in viewports:
                if len(expanded) >= target_count:
                    break
                meta = TestCaseMetadata(
                    test_id="",
                    endpoint=ui_route,
                    method="GET",
                    parameters={"viewport": f"{w}x{h}"},
                    expected_status=200,
                    expected_status_source=f"{ui.get('file', 'UI')}: responsive layout render",
                    authentication_required=False,
                    authentication_source="Public or active session viewport",
                    selector=primary_sel,
                    selector_source=f"{ui.get('file', 'UI')}: primary container {primary_sel}",
                    evidence=[f"{ui.get('file', 'UI')}: {vp_label} layout"],
                    dependencies=[],
                    confidence=1.0,
                    validation_status=ValidationStatus.VALID,
                )
                expanded.append(
                    ProposedTestCase(
                        id="",
                        title=f"Playwright UI: Verify {vp_label} ({w}x{h}) responsiveness on {ui_name}",
                        description=f"Validate {desc} at route '{ui_route}' using Playwright browser emulation.",
                        type=ProposedTestType.UI,
                        priority=ProposedTestPriority.LOW,
                        source="LLM Generated",
                        reason=f"Responsive layout verification on '{ui_route}' at {w}x{h} viewport.",
                        preconditions=["Frontend and backend servers are running"],
                        test_data={"route": ui_route, "viewport": {"width": w, "height": h}},
                        steps=[
                            f"Set viewport size to {w}x{h}",
                            f"Navigate to '{ui_route}'",
                            f"Verify container element ('{primary_sel}') is visible",
                            "Capture full-page screenshot evidence",
                        ],
                        expected_result=f"Page renders correctly in {vp_label} without overflow",
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        metadata=meta,
                        category="Edge Case Testing",
                        custom_instruction_note=f"Responsive {vp_label} verification",
                        ui_spec=UiTestSpec(
                            target_route=ui_route,
                            actions=["navigate", "screenshot"],
                            expected_elements=[primary_sel],
                            assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                        ),
                    )
                )

        # 2. Input Field Validation Scenarios
        for ui in ui_workflows:
            if len(expanded) >= target_count:
                break
            ui_name = ui.get("name", "Page")
            ui_route = ui.get("route") or f"/{ui_name.lower().replace('page', '')}"
            inputs = ui.get("input_fields", [])
            primary_sel = (ui.get("grounded_selectors") or ["body"])[0]

            for inp in inputs:
                if len(expanded) >= target_count:
                    break
                fname = inp.get("name") or inp.get("label") or "input"
                meta = TestCaseMetadata(
                    test_id="",
                    endpoint=ui_route,
                    method="POST",
                    parameters={"field": fname},
                    expected_status=200,
                    expected_status_source=f"{ui.get('file', 'UI')}: input constraint validation",
                    authentication_required=False,
                    authentication_source="Public or active session view",
                    selector=inp.get("selector") or primary_sel,
                    selector_source=f"{ui.get('file', 'UI')}: input field {fname}",
                    evidence=[f"{ui.get('file', 'UI')}: field validation {fname}"],
                    dependencies=[],
                    confidence=1.0,
                    validation_status=ValidationStatus.VALID,
                )
                expanded.append(
                    ProposedTestCase(
                        id="",
                        title=f"Playwright UI: Verify input boundary length handling for {fname} on {ui_name}",
                        description=f"Validate that field '{fname}' handles boundary length inputs correctly on '{ui_route}'.",
                        type=ProposedTestType.UI,
                        priority=ProposedTestPriority.MEDIUM,
                        source="LLM Generated",
                        reason=f"Boundary testing on input '{fname}' in '{ui_name}'.",
                        preconditions=["Frontend and backend servers are running"],
                        test_data={"route": ui_route, "field": fname},
                        steps=[
                            f"Navigate to '{ui_route}'",
                            f"Fill field '{fname}' with boundary input data",
                            "Verify input accepts valid boundary value without error",
                            "Capture full-page screenshot evidence",
                        ],
                        expected_result=f"Field '{fname}' accepts boundary input gracefully",
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        metadata=meta,
                        category="Edge Case Testing",
                        custom_instruction_note="Input boundary length verification",
                        ui_spec=UiTestSpec(
                            target_route=ui_route,
                            input_fields=[inp],
                            actions=["navigate", "screenshot"],
                            expected_elements=[primary_sel],
                            assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                        ),
                    )
                )

        # 3. Keyboard accessibility navigation scenarios
        for ui in ui_workflows:
            if len(expanded) >= target_count:
                break
            ui_name = ui.get("name", "Page")
            ui_route = ui.get("route") or f"/{ui_name.lower().replace('page', '')}"
            primary_sel = (ui.get("grounded_selectors") or ["body"])[0]

            meta = TestCaseMetadata(
                test_id="",
                endpoint=ui_route,
                method="GET",
                parameters={},
                expected_status=200,
                expected_status_source=f"{ui.get('file', 'UI')}: keyboard navigation accessibility",
                authentication_required=False,
                authentication_source="Public or active session view",
                selector=primary_sel,
                selector_source=f"{ui.get('file', 'UI')}: interactive view {primary_sel}",
                evidence=[f"{ui.get('file', 'UI')}: accessibility check"],
                dependencies=[],
                confidence=1.0,
                validation_status=ValidationStatus.VALID,
            )
            expanded.append(
                ProposedTestCase(
                    id="",
                    title=f"Playwright UI: Verify keyboard accessibility navigation on {ui_name}",
                    description=f"Validate that route '{ui_route}' supports keyboard Tab focus navigation without focus traps.",
                    type=ProposedTestType.UI,
                    priority=ProposedTestPriority.LOW,
                    source="LLM Generated",
                    reason=f"Keyboard accessibility audit on '{ui_route}'.",
                    preconditions=["Frontend and backend servers are running"],
                    test_data={"route": ui_route},
                    steps=[
                        f"Navigate to '{ui_route}'",
                        "Press 'Tab' key to cycle focus through interactive elements",
                        f"Verify container element ('{primary_sel}') remains visible",
                        "Capture full-page screenshot evidence",
                    ],
                    expected_result="Focus traverses interactive elements smoothly without errors",
                    status=ProposedTestStatus.PROPOSED,
                    generation_source="LLM Generated",
                    metadata=meta,
                    category="Edge Case Testing",
                    custom_instruction_note="Keyboard accessibility verification",
                    ui_spec=UiTestSpec(
                        target_route=ui_route,
                        actions=["navigate", "screenshot"],
                        expected_elements=[primary_sel],
                        assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                    ),
                )
            )

        return expanded[:target_count]

    def _enforce_targets_and_deduplicate(
        self,
        api_proposals: list[ProposedTestCase],
        ui_proposals: list[ProposedTestCase],
        brd_proposals: list[ProposedTestCase],
        directives: dict[str, Any],
    ) -> list[ProposedTestCase]:
        api_target = directives.get("api_target")
        ui_target = directives.get("ui_target")
        total_target = directives.get("total_target")

        seen_api: set[str] = set()
        deduped_api: list[ProposedTestCase] = []
        for p in api_proposals:
            sig = f"{p.metadata.endpoint}:{p.metadata.method}:{p.category}:{p.metadata.expected_status}" if p.metadata else p.title
            if sig not in seen_api:
                seen_api.add(sig)
                deduped_api.append(p)

        seen_ui: set[str] = set()
        deduped_ui: list[ProposedTestCase] = []
        for p in ui_proposals:
            field = p.test_data.get("field", "") if p.test_data else ""
            sig = f"{p.metadata.endpoint}:{p.category}:{field}:{p.title}" if p.metadata else p.title
            if sig not in seen_ui:
                seen_ui.add(sig)
                deduped_ui.append(p)

        if total_target and api_target is None and ui_target is None:
            if not deduped_api and deduped_ui:
                ui_target = total_target
                api_target = 0
            elif deduped_api and not deduped_ui:
                api_target = total_target
                ui_target = 0
            else:
                api_target = total_target // 2
                ui_target = total_target - api_target

        # If UI target was specified and we have fewer proposals, expand dynamically
        if ui_target is not None and ui_target > 0 and len(deduped_ui) < ui_target:
            deduped_ui = self._expand_ui_proposals_to_target(deduped_ui, ui_target)

        selected_api = self._distribute_by_category(deduped_api, api_target)
        selected_ui = self._distribute_by_category(deduped_ui, ui_target)

        combined = selected_api + selected_ui

        if brd_proposals:
            if api_target == 0:
                brd_proposals = [p for p in brd_proposals if p.type == ProposedTestType.UI]
            elif ui_target == 0:
                brd_proposals = [p for p in brd_proposals if p.type == ProposedTestType.API]
            combined = self._merge_and_deduplicate(combined, brd_proposals)
            if total_target is not None and len(combined) > total_target:
                combined = combined[:total_target]
            elif ui_target is not None and api_target == 0 and len(combined) > ui_target:
                combined = combined[:ui_target]
            elif api_target is not None and ui_target == 0 and len(combined) > api_target:
                combined = combined[:api_target]

        cat_counts: dict[str, int] = {}
        for p in combined:
            cat = p.category or "General"
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        shortfall_notes: list[str] = []
        if api_target is not None and len(selected_api) < api_target:
            shortfall_notes.append(f"Target was {api_target} API tests, but repository evidence supports {len(selected_api)} distinct valid API tests.")
        if ui_target is not None and len(selected_ui) < ui_target:
            shortfall_notes.append(f"Target was {ui_target} UI tests, but repository evidence supports {len(selected_ui)} distinct valid UI tests.")

        serializable_directives = {
            k: (list(v) if isinstance(v, set) else v)
            for k, v in directives.items()
        }
        self.generation_summary = {
            "counts_per_category": cat_counts,
            "total_generated": len(combined),
            "api_count": len([p for p in combined if p.type == ProposedTestType.API]),
            "ui_count": len([p for p in combined if p.type == ProposedTestType.UI]),
            "unit_count": len([p for p in combined if p.type == ProposedTestType.UNIT]),
            "custom_prompt_directives": serializable_directives,
            "shortfall_notes": shortfall_notes,
        }

        return combined

    def _generate_code_analysis_proposals(self) -> list[ProposedTestCase]:
        directives = self._parse_directives()
        raw = self._generate_api_proposals(directives) + self._generate_ui_proposals(directives)
        return self._reindex_proposals(raw)

    def _generate_api_proposals(self, directives: dict[str, Any]) -> list[ProposedTestCase]:
        enabled_cat_ids = directives.get("enabled_cat_ids", set(PLATFORM_CATEGORIES.keys()))
        endpoints = self.analysis.get("endpoints", [])
        proposals: list[ProposedTestCase] = []

        # 1. Happy Path Testing for API
        if "happy-path" in enabled_cat_ids:
            for ep in endpoints:
                method = ep.get("method", "GET").upper()
                raw_ep = ep.get("endpoint", "/")
                source_class = ep.get("class_name") or ep.get("source") or "Controller"

                endpoint_slug = re.sub(r"[\/{}\-_]", "", raw_ep).lower()
                is_covered = any(
                    endpoint_slug in sc or f"{method.lower()}{endpoint_slug}" in sc
                    for sc in self.existing_scenarios
                )
                if is_covered:
                    continue

                res = self.data_resolver.resolve_endpoint(raw_ep)
                resolved_endpoint = res.endpoint
                param_values = res.param_values
                param_sources = res.param_sources
                test_data: dict[str, Any] = {"method": method, "endpoint": resolved_endpoint}
                if param_values:
                    test_data["path_params"] = param_values

                request_body = self._build_request_body_from_endpoint(ep) if method in ("POST", "PUT", "PATCH") else None
                if request_body:
                    test_data["request_body"] = request_body

                expected_status = ep.get("expected_status") or self._infer_success_status(method, ep)
                expected_status_source = (
                    ep.get("expected_status_source")
                    or (
                        f"{source_class}: {method} {raw_ep} handler declaration HTTP {expected_status}"
                        if ep.get("expected_status")
                        else self._infer_success_status_source(method, ep)
                    )
                )

                auth_req = ep.get("authentication_required", False)
                auth_source = ep.get("authentication_source") or "No security configuration required"
                dependencies: list[str] = ["AUTHENTICATE_SESSION"] if auth_req else []

                meta = TestCaseMetadata(
                    test_id="",
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
                    confidence=1.0,
                    validation_status=ValidationStatus.VALID,
                )

                proposals.append(
                    ProposedTestCase(
                        id="",
                        title=f"Verify {method} {raw_ep} returns success response",
                        description=f"Validate that sending a valid {method} request to '{raw_ep}' returns expected status code and response payload.",
                        type=ProposedTestType.API,
                        priority=ProposedTestPriority.HIGH if any(k in raw_ep.lower() for k in ["login", "auth", "user", "order", "payment"]) else ProposedTestPriority.MEDIUM,
                        source="LLM Generated",
                        reason=f"Endpoint '{method} {raw_ep}' detected in {source_class} without direct existing API test coverage.",
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
                        metadata=meta,
                        category="Happy Path Testing",
                        custom_instruction_note="Grounded happy path testcase",
                        api_spec=ApiTestSpec(
                            method=method,
                            endpoint=resolved_endpoint,
                            headers={"Content-Type": "application/json", "Accept": "application/json"},
                            request_body=request_body,
                            expected_status=expected_status,
                            assertions=[f"status == {expected_status}", "response.body != null"],
                        ),
                    )
                )

        # 2. Negative & Validation Testing for API
        if "negative-testing" in enabled_cat_ids:
            body_eps = [ep for ep in endpoints if ep.get("method") in ("POST", "PUT", "PATCH") and ep.get("has_request_body", True)]
            for ep in body_eps:
                method = ep.get("method")
                raw_ep = ep.get("endpoint")
                resolved_ep = self.data_resolver.resolve_endpoint(raw_ep).endpoint
                source_class = ep.get("class_name", "Controller")
                auth_req = ep.get("authentication_required", False)
                auth_source = ep.get("authentication_source") or "Controller security barrier"

                meta = TestCaseMetadata(
                    test_id="",
                    endpoint=resolved_ep,
                    method=method,
                    parameters={},
                    expected_status=400,
                    expected_status_source=f"{source_class}: request payload validation constraint rejects empty body HTTP 400",
                    authentication_required=auth_req,
                    authentication_source=auth_source,
                    evidence=[f"Validation constraint on {method} {raw_ep}"],
                    dependencies=["AUTHENTICATE_SESSION"] if auth_req else [],
                    confidence=1.0,
                    validation_status=ValidationStatus.VALID,
                )
                proposals.append(
                    ProposedTestCase(
                        id="",
                        title=f"Validate {method} {raw_ep} rejection on invalid empty payload",
                        description=f"Verify that sending an empty/malformed payload to '{raw_ep}' is rejected with HTTP 400 Bad Request.",
                        type=ProposedTestType.API,
                        priority=ProposedTestPriority.HIGH,
                        source="LLM Generated",
                        reason=f"Endpoint '{method} {raw_ep}' accepts request body; validation test for empty payload required.",
                        preconditions=["Application service is running"],
                        test_data={"method": method, "endpoint": resolved_ep, "request_body": {}},
                        steps=[
                            f"Send malformed empty JSON payload {{}} to {method} {resolved_ep}",
                            "Assert response status code is 400 Bad Request",
                            "Verify validation error details in response body",
                        ],
                        expected_result="HTTP status 400 Bad Request with validation error message",
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        metadata=meta,
                        category="Negative & Validation Testing",
                        custom_instruction_note="Negative validation constraint on request body",
                        api_spec=ApiTestSpec(
                            method=method,
                            endpoint=resolved_ep,
                            headers={"Content-Type": "application/json"},
                            request_body={},
                            expected_status=400,
                            assertions=["status == 400"],
                        ),
                    )
                )

        # 3. Edge Case Testing for API
        if "edge-case" in enabled_cat_ids:
            path_eps = [ep for ep in endpoints if ep.get("path_params")]
            for ep in path_eps:
                method = ep.get("method")
                raw_ep = ep.get("endpoint")
                edge_ep = raw_ep
                for p in ep.get("path_params", []):
                    edge_ep = edge_ep.replace(f"{{{p}}}", "999999")
                source_class = ep.get("class_name", "Controller")
                auth_req = ep.get("authentication_required", False)
                auth_source = ep.get("authentication_source") or "Public/domain access"

                meta = TestCaseMetadata(
                    test_id="",
                    endpoint=edge_ep,
                    method=method,
                    parameters={p: 999999 for p in ep.get("path_params", [])},
                    expected_status=404,
                    expected_status_source=f"{source_class}: entity lookup boundary returns HTTP 404 for missing resource",
                    authentication_required=auth_req,
                    authentication_source=auth_source,
                    evidence=[f"{source_class}: entity lookup boundary on {raw_ep}"],
                    dependencies=["AUTHENTICATE_SESSION"] if auth_req else [],
                    confidence=1.0,
                    validation_status=ValidationStatus.VALID,
                )
                proposals.append(
                    ProposedTestCase(
                        id="",
                        title=f"Verify {method} {raw_ep} edge-case boundary on non-existent identifier",
                        description=f"Verify that requesting boundary non-existent ID 999999 at '{raw_ep}' yields HTTP 404 Not Found.",
                        type=ProposedTestType.API,
                        priority=ProposedTestPriority.MEDIUM,
                        source="LLM Generated",
                        reason=f"Edge case boundary test on '{raw_ep}'.",
                        preconditions=["Application service is running"],
                        test_data={"method": method, "endpoint": edge_ep},
                        steps=[
                            f"Send {method} request to {edge_ep} with boundary ID 999999",
                            "Assert response status code is 404 Not Found",
                        ],
                        expected_result="HTTP status 404 Not Found",
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        metadata=meta,
                        category="Edge Case Testing",
                        custom_instruction_note="Edge case boundary parameter testing",
                        api_spec=ApiTestSpec(
                            method=method,
                            endpoint=edge_ep,
                            headers={"Accept": "application/json"},
                            expected_status=404,
                            assertions=["status == 404"],
                        ),
                    )
                )

        # 4. Role & Permission Testing for API
        if "role-permission" in enabled_cat_ids:
            for ep in endpoints:
                method = ep.get("method")
                raw_ep = ep.get("endpoint")
                source_class = ep.get("class_name", "Controller")
                resolved_ep = self.data_resolver.resolve_endpoint(raw_ep).endpoint

                meta = TestCaseMetadata(
                    test_id="",
                    endpoint=resolved_ep,
                    method=method,
                    parameters={},
                    expected_status=401,
                    expected_status_source=f"{source_class}: Spring Security filter chain rejects unauthenticated request HTTP 401",
                    authentication_required=False,
                    authentication_source="Testing unauthenticated access",
                    evidence=[f"Security barrier check on {method} {raw_ep}"],
                    dependencies=[],
                    confidence=1.0,
                    validation_status=ValidationStatus.VALID,
                )
                proposals.append(
                    ProposedTestCase(
                        id="",
                        title=f"Verify {method} {raw_ep} role-permission barrier rejects unauthenticated request",
                        description=f"Verify that sending {method} request to '{raw_ep}' without authorization token returns HTTP 401 Unauthorized.",
                        type=ProposedTestType.API,
                        priority=ProposedTestPriority.HIGH,
                        source="LLM Generated",
                        reason=f"Role & Permission barrier verification for '{raw_ep}'.",
                        preconditions=["Application service is running", "No authentication credentials provided"],
                        test_data={"method": method, "endpoint": resolved_ep},
                        steps=[
                            f"Send {method} request to {resolved_ep} without Authorization header",
                            "Assert response status code is 401 Unauthorized",
                        ],
                        expected_result="HTTP status 401 Unauthorized",
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        metadata=meta,
                        category="Role & Permission Testing",
                        custom_instruction_note="Role & permission barrier verification",
                        api_spec=ApiTestSpec(
                            method=method,
                            endpoint=resolved_ep,
                            headers={"Accept": "application/json"},
                            expected_status=401,
                            assertions=["status == 401"],
                        ),
                    )
                )

        # 5. End-to-End Workflow Testing for API
        if "e2e-workflow" in enabled_cat_ids:
            get_eps = [ep for ep in endpoints if ep.get("method") == "GET" and not ep.get("path_params")]
            for ep in get_eps:
                method = "GET"
                raw_ep = ep.get("endpoint")
                source_class = ep.get("class_name", "Controller")
                resolved_ep = self.data_resolver.resolve_endpoint(raw_ep).endpoint
                auth_req = ep.get("authentication_required", False)
                auth_source = ep.get("authentication_source") or "Domain access"

                meta = TestCaseMetadata(
                    test_id="",
                    endpoint=resolved_ep,
                    method=method,
                    parameters={},
                    expected_status=200,
                    expected_status_source=f"{source_class}: end-to-end data lifecycle query returns HTTP 200",
                    authentication_required=auth_req,
                    authentication_source=auth_source,
                    evidence=[f"{source_class}: collection query verification"],
                    dependencies=["AUTHENTICATE_SESSION"] if auth_req else [],
                    confidence=1.0,
                    validation_status=ValidationStatus.VALID,
                )
                proposals.append(
                    ProposedTestCase(
                        id="",
                        title=f"Verify GET {raw_ep} end-to-end data lifecycle query",
                        description=f"Validate end-to-end collection query response for '{raw_ep}'.",
                        type=ProposedTestType.API,
                        priority=ProposedTestPriority.HIGH,
                        source="LLM Generated",
                        reason=f"End-to-end data lifecycle query on '{raw_ep}'.",
                        preconditions=["Application service is running"],
                        test_data={"method": method, "endpoint": resolved_ep},
                        steps=[
                            f"Send GET request to {resolved_ep}",
                            "Assert response status code is 200 OK",
                            "Verify response body structure and data fields",
                        ],
                        expected_result="HTTP status 200 OK with valid domain collection payload",
                        status=ProposedTestStatus.PROPOSED,
                        generation_source="LLM Generated",
                        metadata=meta,
                        category="End-to-End Workflow Testing",
                        custom_instruction_note="End-to-end data lifecycle query",
                        api_spec=ApiTestSpec(
                            method=method,
                            endpoint=resolved_ep,
                            headers={"Accept": "application/json"},
                            expected_status=200,
                            assertions=["status == 200"],
                        ),
                    )
                )

        return proposals

    def _generate_ui_proposals(self, directives: dict[str, Any]) -> list[ProposedTestCase]:
        enabled_cat_ids = directives.get("enabled_cat_ids", set(PLATFORM_CATEGORIES.keys()))
        ui_workflows = self.analysis.get("ui_workflows", [])
        proposals: list[ProposedTestCase] = []

        for ui in ui_workflows:
            if ui.get("is_fragment", False):
                continue

            ui_name = ui.get("name", "Page")
            ui_type = ui.get("type", "FORM")
            ui_route = ui.get("route") or f"/{ui_name.lower().replace('page', '')}"
            inputs = ui.get("input_fields", [])
            submit_btn = ui.get("submit_button") or "Submit"
            grounded_selectors = ui.get("grounded_selectors", [])
            has_login = ui.get("has_login") or ui.get("type") == "AUTH" or ui_name.lower() == "login"
            has_form = len(inputs) > 0 or ui.get("has_form", False)
            has_table = ui.get("has_table", False) or ui.get("type") == "TABLE" or "list" in ui_name.lower()
            tbl_headers = ui.get("table_headers", [])
            headings = ui.get("headings", [])
            fields_summary = ", ".join(f.get("label") or f.get("name") for f in inputs[:4]) if inputs else "form input fields"
            headers_summary = ", ".join(tbl_headers[:4]) if tbl_headers else "data columns"

            import copy
            filled_inputs = copy.deepcopy(inputs)
            for inp in filled_inputs:
                if not inp.get("value"):
                    name = (inp.get("name") or inp.get("label") or "test").lower()
                    if "email" in name: inp["value"] = "test@example.com"
                    elif "phone" in name: inp["value"] = "1234567890"
                    elif "date" in name or "dob" in name: inp["value"] = "2023-01-01"
                    elif "id" in name: inp["value"] = "1001"
                    elif "status" in name: inp["value"] = "ACTIVE"
                    elif "gender" in name: inp["value"] = "MALE"
                    elif "type" in name: inp["value"] = "ANNUAL"
                    else: inp["value"] = "test-value"

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
            primary_sel = expected_elements[0]

            # 1. Happy Path Testing for UI
            if "happy-path" in enabled_cat_ids:
                if has_login:
                    meta_a = TestCaseMetadata(
                        test_id="",
                        endpoint=ui_route,
                        method="GET",
                        parameters={},
                        expected_status=200,
                        expected_status_source=f"{ui.get('file', 'login.html')}: unauthenticated login page view",
                        authentication_required=False,
                        authentication_source="Public login landing page",
                        selector=primary_sel,
                        selector_source=f"{ui.get('file')}: form element {primary_sel}",
                        evidence=[f"{ui.get('file')}: Login UI controls definition"],
                        dependencies=[],
                        confidence=1.0,
                        validation_status=ValidationStatus.VALID,
                    )
                    proposals.append(
                        ProposedTestCase(
                            id="",
                            title=f"Playwright UI: Verify unauthenticated login view controls on {ui_name}",
                            description=f"Verify that navigating to '{ui_route}' as an unauthenticated visitor renders the login form and credentials controls.",
                            type=ProposedTestType.UI,
                            priority=ProposedTestPriority.HIGH,
                            source="LLM Generated",
                            reason=f"Login view detected in {ui.get('file')}; unauthenticated form render verification.",
                            preconditions=["Frontend and backend servers are running", "Browser session is unauthenticated"],
                            test_data={"ui_view": ui_name, "route": ui_route},
                            steps=[
                                f"Open browser and navigate to '{ui_route}' as unauthenticated visitor",
                                f"Verify login form container and credential input fields ({fields_summary}) are visible",
                                f"Verify submission action control ('{submit_btn}') is accessible",
                                "Capture full-page screenshot evidence",
                            ],
                            expected_result="Login form and authentication controls render successfully for unauthenticated visitor",
                            status=ProposedTestStatus.PROPOSED,
                            generation_source="LLM Generated",
                            metadata=meta_a,
                            category="Happy Path Testing",
                            custom_instruction_note="Login view unauthenticated controls verification",
                            ui_spec=UiTestSpec(
                                target_route=ui_route,
                                input_fields=filled_inputs,
                                actions=["navigate", "click " + submit_btn, "screenshot"],
                                expected_elements=expected_elements,
                                assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                            ),
                        )
                    )

                    meta_b = TestCaseMetadata(
                        test_id="",
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
                            id="",
                            title=f"Playwright UI: Verify user authentication workflow and redirect on {ui_name}",
                            description="Verify successful authentication workflow submission and redirection to authorized destination.",
                            type=ProposedTestType.UI,
                            priority=ProposedTestPriority.HIGH,
                            source="LLM Generated",
                            reason=f"Authentication workflow detected in {ui.get('file')}; end-to-end credential submission and redirect verification.",
                            preconditions=["Frontend and backend servers are running", "Valid repository credentials available"],
                            test_data={"ui_view": ui_name, "route": ui_route},
                            steps=[
                                f"Navigate to '{ui_route}' in browser",
                                "Fill verified credentials discovered from repository evidence (Username, Password)",
                                f"Submit authentication form by clicking '{submit_btn}'",
                                "Verify successful authentication and redirect away from login view",
                                "Confirm authenticated destination view is reached",
                                "Capture full-page screenshot evidence",
                            ],
                            expected_result="User authentication succeeds, page navigates away from login view, and authenticated session is established",
                            status=ProposedTestStatus.PROPOSED,
                            generation_source="LLM Generated",
                            metadata=meta_b,
                            category="Happy Path Testing",
                            custom_instruction_note="User authentication workflow and redirect verification",
                            ui_spec=UiTestSpec(
                                target_route=ui_route,
                                input_fields=inputs,
                                actions=[f"click button: {submit_btn}", "verify redirection"],
                                expected_elements=[".container, table, main, nav, .alert-success"],
                                assertions=["expect(page).not.toHaveURL(new RegExp('.*login.*'))"],
                            ),
                        )
                    )
                elif has_form and not has_table:
                    meta = TestCaseMetadata(
                        test_id="",
                        endpoint=ui_route,
                        method="GET",
                        parameters={},
                        expected_status=200,
                        expected_status_source=f"{ui.get('file')}: form view render",
                        authentication_required=True,
                        authentication_source=f"{ui.get('file')}: form view behind security filter",
                        selector=primary_sel,
                        selector_source=f"{ui.get('file')}: primary form selector {primary_sel}",
                        evidence=[f"{ui.get('file')}: Form UI definition"],
                        dependencies=["AUTHENTICATE_SESSION"],
                        confidence=1.0,
                        validation_status=ValidationStatus.VALID,
                    )
                    proposals.append(
                        ProposedTestCase(
                            id="",
                            title=f"Playwright UI: Validate form submission and feedback on {ui_name}",
                            description=f"End-to-end browser test using Playwright against '{ui_route}' with automated screenshot & video recording.",
                            type=ProposedTestType.UI,
                            priority=ProposedTestPriority.MEDIUM,
                            source="LLM Generated",
                            reason=f"Interactive form detected in '{ui_name}' at '{ui_route}'; Playwright browser test proposed for data entry and submission.",
                            preconditions=["Frontend and backend servers are running", "Authenticated session active"],
                            test_data={"ui_view": ui_name, "route": ui_route},
                            steps=[
                                f"Navigate to '{ui_route}' in browser",
                                f"Fill required form inputs ({fields_summary})",
                                f"Submit form by clicking '{submit_btn}'",
                                "Verify post-submission confirmation or redirection",
                                "Capture full-page screenshot evidence",
                            ],
                            expected_result="Form inputs validate, submission completes, and feedback or redirection is displayed",
                            status=ProposedTestStatus.PROPOSED,
                            generation_source="LLM Generated",
                            metadata=meta,
                            category="Happy Path Testing",
                            custom_instruction_note="Interactive form submission and feedback",
                            ui_spec=UiTestSpec(
                                target_route=ui_route,
                                input_fields=filled_inputs,
                                actions=["navigate", "click " + submit_btn, "screenshot"],
                                expected_elements=expected_elements,
                                assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                            ),
                        )
                    )
                elif has_table or ui_type == "TABLE":
                    meta = TestCaseMetadata(
                        test_id="",
                        endpoint=ui_route,
                        method="GET",
                        parameters={},
                        expected_status=200,
                        expected_status_source=f"{ui.get('file')}: data table view render",
                        authentication_required=True,
                        authentication_source=f"{ui.get('file')}: data view behind security filter",
                        selector=primary_sel,
                        selector_source=f"{ui.get('file')}: table selector {primary_sel}",
                        evidence=[f"{ui.get('file')}: Tabular records view"],
                        dependencies=["AUTHENTICATE_SESSION"],
                        confidence=1.0,
                        validation_status=ValidationStatus.VALID,
                    )
                    proposals.append(
                        ProposedTestCase(
                            id="",
                            title=f"Playwright UI: Verify data table rendering and action triggers on {ui_name}",
                            description=f"End-to-end browser test using Playwright against '{ui_route}' with automated screenshot & video recording.",
                            type=ProposedTestType.UI,
                            priority=ProposedTestPriority.MEDIUM,
                            source="LLM Generated",
                            reason=f"Data table view detected in '{ui_name}' at '{ui_route}'; Playwright browser test proposed for tabular records and actions.",
                            preconditions=["Frontend and backend servers are running", "Authenticated session active"],
                            test_data={"ui_view": ui_name, "route": ui_route},
                            steps=[
                                f"Navigate to '{ui_route}' in browser",
                                f"Verify data table renders with column headers ({headers_summary})",
                                "Verify data records and action controls are active",
                                "Capture full-page screenshot evidence",
                            ],
                            expected_result="Data table renders with valid columns, records, and action triggers",
                            status=ProposedTestStatus.PROPOSED,
                            generation_source="LLM Generated",
                            metadata=meta,
                            category="Happy Path Testing",
                            custom_instruction_note="Data table rendering and records display",
                            ui_spec=UiTestSpec(
                                target_route=ui_route,
                                input_fields=[],
                                actions=["navigate", "screenshot"],
                                expected_elements=expected_elements,
                                assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                            ),
                        )
                    )
                elif ui_type == "DASHBOARD" or "dashboard" in ui_name.lower():
                    heading_name = headings[0] if headings else "Dashboard Overview"
                    meta = TestCaseMetadata(
                        test_id="",
                        endpoint=ui_route,
                        method="GET",
                        parameters={},
                        expected_status=200,
                        expected_status_source=f"{ui.get('file')}: dashboard view render",
                        authentication_required=True,
                        authentication_source=f"{ui.get('file')}: dashboard view behind security filter",
                        selector=primary_sel,
                        selector_source=f"{ui.get('file')}: dashboard container {primary_sel}",
                        evidence=[f"{ui.get('file')}: Dashboard overview view"],
                        dependencies=["AUTHENTICATE_SESSION"],
                        confidence=1.0,
                        validation_status=ValidationStatus.VALID,
                    )
                    proposals.append(
                        ProposedTestCase(
                            id="",
                            title=f"Playwright UI: Verify overview metrics and statistics on {ui_name}",
                            description=f"End-to-end browser test using Playwright against '{ui_route}' with automated screenshot & video recording.",
                            type=ProposedTestType.UI,
                            priority=ProposedTestPriority.MEDIUM,
                            source="LLM Generated",
                            reason=f"Dashboard view detected in '{ui_name}' at '{ui_route}'; Playwright browser test proposed for overview metrics and stat cards.",
                            preconditions=["Frontend and backend servers are running", "Authenticated session active"],
                            test_data={"ui_view": ui_name, "route": ui_route},
                            steps=[
                                f"Navigate to '{ui_route}' in browser",
                                f"Verify dashboard overview heading ('{heading_name}')",
                                "Verify summary statistics metric cards render with populated data",
                                "Capture full-page screenshot evidence",
                            ],
                            expected_result="Dashboard metrics, stat cards, and overview layout render successfully",
                            status=ProposedTestStatus.PROPOSED,
                            generation_source="LLM Generated",
                            metadata=meta,
                            category="Happy Path Testing",
                            custom_instruction_note="Dashboard metrics and overview layout",
                            ui_spec=UiTestSpec(
                                target_route=ui_route,
                                input_fields=[],
                                actions=["navigate", "screenshot"],
                                expected_elements=[".stat-card, .stat-value"],
                                assertions=["expect(page.locator('[data-testid*=\"stat\" i], [data-testid*=\"metric\" i], [id*=\"stat\" i], [id*=\"metric\" i], .stat-card, .stat-value, .metric-card, .card:has(.stat-icon), [role=\"status\"]').first()).toBeVisible()"],
                                authentication_required=True,
                            ),
                        )
                    )
                else:
                    meta = TestCaseMetadata(
                        test_id="",
                        endpoint=ui_route,
                        method="GET",
                        parameters={},
                        expected_status=200,
                        expected_status_source=f"{ui.get('file')}: view render",
                        authentication_required=False,
                        authentication_source="Public application view",
                        selector=primary_sel,
                        selector_source=f"{ui.get('file')}: element {primary_sel}",
                        evidence=[f"{ui.get('file')}: Visual navigation view"],
                        dependencies=[],
                        confidence=1.0,
                        validation_status=ValidationStatus.VALID,
                    )
                    proposals.append(
                        ProposedTestCase(
                            id="",
                            title=f"Playwright UI: Verify page rendering and navigation on {ui_name}",
                            description=f"End-to-end browser test using Playwright against '{ui_route}' with automated screenshot & video recording.",
                            type=ProposedTestType.UI,
                            priority=ProposedTestPriority.LOW,
                            source="LLM Generated",
                            reason=f"UI view '{ui_name}' detected at '{ui_route}'; Playwright visual verification proposed.",
                            preconditions=["Frontend and backend servers are running", "Browser is initialized in headless mode"],
                            test_data={"ui_view": ui_name, "route": ui_route},
                            steps=[
                                f"Open browser and navigate to '{ui_route}'",
                                "Verify header, navigation links, and primary content container",
                                "Capture full-page screenshot evidence",
                            ],
                            expected_result="Page renders without layout breaks or JavaScript console errors",
                            status=ProposedTestStatus.PROPOSED,
                            generation_source="LLM Generated",
                            metadata=meta,
                            category="Happy Path Testing",
                            custom_instruction_note="Page rendering and navigation verification",
                            ui_spec=UiTestSpec(
                                target_route=ui_route,
                                input_fields=[],
                                actions=["navigate", "screenshot"],
                                expected_elements=expected_elements,
                                assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                            ),
                        )
                    )

            # 2. Negative & Validation Testing for UI
            if "negative-testing" in enabled_cat_ids:
                if has_login:
                    meta = TestCaseMetadata(
                        test_id="",
                        endpoint=ui_route,
                        method="POST",
                        parameters={"username": "invalid_user", "password": "wrong_password"},
                        expected_status=200,
                        expected_status_source=f"{ui.get('file', 'Login.tsx')}: invalid login error handling renders error alert",
                        authentication_required=False,
                        authentication_source="Public login page negative test",
                        selector=primary_sel,
                        selector_source=f"{ui.get('file')}: form element {primary_sel}",
                        evidence=[f"{ui.get('file')}: Authentication error handler"],
                        confidence=1.0,
                        validation_status=ValidationStatus.VALID,
                    )
                    proposals.append(
                        ProposedTestCase(
                            id="",
                            title=f"Playwright UI: Verify login rejection and error notification with invalid credentials",
                            description="Verify that submitting invalid credentials displays error notification and prevents unauthorized session.",
                            type=ProposedTestType.UI,
                            priority=ProposedTestPriority.HIGH,
                            source="LLM Generated",
                            reason="Negative authentication validation test for invalid credentials.",
                            preconditions=["Browser session is unauthenticated"],
                            test_data={"ui_view": ui_name, "route": ui_route},
                            steps=[
                                f"Navigate to '{ui_route}' in browser",
                                "Fill input fields with invalid credentials (invalid_user / wrong_password)",
                                f"Click '{submit_btn}' action button",
                                "Assert error notification alert is displayed in DOM",
                                "Confirm browser stays on login page",
                                "Capture screenshot evidence",
                            ],
                            expected_result="Application displays error alert message and prevents access to authenticated view",
                            status=ProposedTestStatus.PROPOSED,
                            generation_source="LLM Generated",
                            metadata=meta,
                            category="Negative & Validation Testing",
                            custom_instruction_note="Negative validation constraint on authentication credentials",
                            ui_spec=UiTestSpec(
                                target_route=ui_route,
                                input_fields=inputs,
                                actions=["navigate", "fill", "click", "screenshot"],
                                expected_elements=[primary_sel],
                                assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                            ),
                        )
                    )
                elif has_form and inputs:
                    field_names = ", ".join(f.get("name") for f in inputs[:3])
                    meta = TestCaseMetadata(
                        test_id="",
                        endpoint=ui_route,
                        method="POST",
                        parameters={},
                        expected_status=200,
                        expected_status_source=f"{ui.get('file')}: form client validation blocks submit and renders error notification",
                        authentication_required=True,
                        authentication_source="Authenticated session form test",
                        selector=primary_sel,
                        selector_source=f"{ui.get('file')}: form element {primary_sel}",
                        evidence=[f"{ui.get('file')}: Required field constraints ({field_names})"],
                        dependencies=["AUTHENTICATE_SESSION"],
                        confidence=1.0,
                        validation_status=ValidationStatus.VALID,
                    )
                    proposals.append(
                        ProposedTestCase(
                            id="",
                            title=f"Playwright UI: Verify validation error alerts on submitting empty {ui_name}",
                            description=f"Verify that clicking submit on '{ui_route}' without required fields displays validation error messages.",
                            type=ProposedTestType.UI,
                            priority=ProposedTestPriority.HIGH,
                            source="LLM Generated",
                            reason=f"Negative validation test: form on {ui_route} must require mandatory inputs.",
                            preconditions=["Application is running", "Authenticated session active"],
                            test_data={"ui_view": ui_name, "route": ui_route},
                            steps=[
                                f"Navigate to '{ui_route}' in browser",
                                f"Click '{submit_btn}' without filling required fields ({field_names})",
                                "Assert validation error message or browser validation tooltip is displayed",
                                "Confirm form submission is prevented and page does not navigate away",
                                "Capture screenshot evidence",
                            ],
                            expected_result="Form displays validation error alerts and blocks invalid submission",
                            status=ProposedTestStatus.PROPOSED,
                            generation_source="LLM Generated",
                            metadata=meta,
                            category="Negative & Validation Testing",
                            custom_instruction_note="Mandatory field validation check",
                            ui_spec=UiTestSpec(
                                target_route=ui_route,
                                input_fields=[],
                                actions=["navigate", "click " + submit_btn, "screenshot"],
                                expected_elements=["input:invalid, .validation-error-alert, .alert-danger"],
                                assertions=["expect(page.locator('input:invalid, select:invalid, textarea:invalid, .validation-error-alert, .alert-danger, [role=\"alert\"], .invalid-feedback, .error-message').first()).toBeVisible()"],
                                authentication_required=True,
                            ),
                        )
                    )

                    for f in inputs[:5]:
                        f_name = f.get("name")
                        meta_f = TestCaseMetadata(
                            test_id="",
                            endpoint=ui_route,
                            method="POST",
                            parameters={f_name: "invalid_test_val"},
                            expected_status=200,
                            expected_status_source=f"{ui.get('file')}: field {f_name} format validation renders error notification",
                            authentication_required=True,
                            authentication_source="Authenticated session form test",
                            selector=primary_sel,
                            selector_source=f"{ui.get('file')}: field {f_name}",
                            evidence=[f"{ui.get('file')}: Validation format check on {f_name}"],
                            dependencies=["AUTHENTICATE_SESSION"],
                            confidence=1.0,
                            validation_status=ValidationStatus.VALID,
                        )
                        proposals.append(
                            ProposedTestCase(
                                id="",
                                title=f"Playwright UI: Verify input format constraint validation for {f_name} on {ui_name}",
                                description=f"Verify that entering malformed format for '{f_name}' on '{ui_route}' triggers validation error.",
                                type=ProposedTestType.UI,
                                priority=ProposedTestPriority.MEDIUM,
                                source="LLM Generated",
                                reason=f"Field format validation verification on {ui_route}.",
                                preconditions=["Application is running", "Authenticated session active"],
                                test_data={"ui_view": ui_name, "route": ui_route, "field": f_name},
                                steps=[
                                    f"Navigate to '{ui_route}' in browser",
                                    f"Fill '{f_name}' with malformed invalid format value",
                                    f"Trigger validation check by clicking '{submit_btn}'",
                                    "Assert format validation error message is displayed",
                                    "Capture screenshot evidence",
                                ],
                                expected_result="Field validation error message is displayed for invalid format",
                                status=ProposedTestStatus.PROPOSED,
                                generation_source="LLM Generated",
                                metadata=meta_f,
                                category="Negative & Validation Testing",
                                custom_instruction_note=f"Format constraint validation for field {f_name}",
                                ui_spec=UiTestSpec(
                                    target_route=ui_route,
                                    input_fields=[f],
                                    actions=["navigate", "fill", "screenshot"],
                                    expected_elements=[primary_sel],
                                    assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                                ),
                            )
                        )

            # 3. Edge Case Testing for UI
            if "edge-case" in enabled_cat_ids:
                if has_table:
                    meta = TestCaseMetadata(
                        test_id="",
                        endpoint=ui_route,
                        method="GET",
                        parameters={"search": "__NON_MATCHING_QUERY__"},
                        expected_status=200,
                        expected_status_source=f"{ui.get('file')}: table filter empty state verification",
                        authentication_required=True,
                        authentication_source="Authenticated session table view",
                        selector=primary_sel,
                        selector_source=f"{ui.get('file')}: table element {primary_sel}",
                        evidence=[f"{ui.get('file')}: Table search filter boundary check"],
                        dependencies=["AUTHENTICATE_SESSION"],
                        confidence=1.0,
                        validation_status=ValidationStatus.VALID,
                    )
                    proposals.append(
                        ProposedTestCase(
                            id="",
                            title=f"Playwright UI: Verify search filter boundary with non-existent query on {ui_name}",
                            description=f"Verify that filtering '{ui_route}' table with a non-existent search term handles boundary gracefully.",
                            type=ProposedTestType.UI,
                            priority=ProposedTestPriority.MEDIUM,
                            source="LLM Generated",
                            reason=f"Edge case testing for table search boundary on {ui_route}.",
                            preconditions=["Application is running", "Authenticated session active"],
                            test_data={"ui_view": ui_name, "route": ui_route},
                            steps=[
                                f"Navigate to '{ui_route}' in browser",
                                "Enter non-existent query '__NON_MATCHING_XYZ__' into filter search box",
                                "Assert table displays empty state notification or 0 matching rows",
                                "Capture screenshot evidence",
                            ],
                            expected_result="Table view updates to display empty state notification without UI failure",
                            status=ProposedTestStatus.PROPOSED,
                            generation_source="LLM Generated",
                            metadata=meta,
                            category="Edge Case Testing",
                            custom_instruction_note="Table search boundary with non-existent query",
                            ui_spec=UiTestSpec(
                                target_route=ui_route,
                                input_fields=[],
                                actions=["navigate", "search '__NON_MATCHING_QUERY__'", "screenshot"],
                                expected_elements=[".no-data-msg, .empty-state, table tbody tr"],
                                assertions=["expect(page.locator('.no-data-msg, .empty-state, [data-testid*=\"empty\" i], [data-testid*=\"no-data\" i], td:has-text(\"No matching\"), td:has-text(\"No records\"), td:has-text(\"No data\"), table tbody tr').first()).toBeVisible()"],
                                authentication_required=True,
                            ),
                        )
                    )
                if has_form and inputs:
                    meta = TestCaseMetadata(
                        test_id="",
                        endpoint=ui_route,
                        method="POST",
                        parameters={},
                        expected_status=200,
                        expected_status_source=f"{ui.get('file')}: input length boundary handling",
                        authentication_required=True,
                        authentication_source="Authenticated session form test",
                        selector=primary_sel,
                        selector_source=f"{ui.get('file')}: form element {primary_sel}",
                        evidence=[f"{ui.get('file')}: Maximum field length boundary test"],
                        dependencies=["AUTHENTICATE_SESSION"],
                        confidence=1.0,
                        validation_status=ValidationStatus.VALID,
                    )
                    proposals.append(
                        ProposedTestCase(
                            id="",
                            title=f"Playwright UI: Verify input field boundary length handling on {ui_name}",
                            description=f"Verify that entering boundary length strings into form fields on '{ui_route}' is handled safely.",
                            type=ProposedTestType.UI,
                            priority=ProposedTestPriority.LOW,
                            source="LLM Generated",
                            reason=f"Edge case test for maximum input string lengths on {ui_route}.",
                            preconditions=["Application is running", "Authenticated session active"],
                            test_data={"ui_view": ui_name, "route": ui_route},
                            steps=[
                                f"Navigate to '{ui_route}' in browser",
                                "Populate text input fields with 255-character boundary length test strings",
                                f"Click '{submit_btn}' action button",
                                "Assert application handles boundary string safely with appropriate feedback message",
                                "Capture screenshot evidence",
                            ],
                            expected_result="Form handles boundary lengths cleanly with validation or toast message",
                            status=ProposedTestStatus.PROPOSED,
                            generation_source="LLM Generated",
                            metadata=meta,
                            category="Edge Case Testing",
                            custom_instruction_note="Boundary input string length handling",
                            ui_spec=UiTestSpec(
                                target_route=ui_route,
                                input_fields=inputs,
                                actions=["navigate", "fill", "click", "screenshot"],
                                expected_elements=[primary_sel],
                                assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                            ),
                        )
                    )

            # 4. Role & Permission Testing for UI
            if "role-permission" in enabled_cat_ids:
                if not has_login and ui_route != "/":
                    meta = TestCaseMetadata(
                        test_id="",
                        endpoint=ui_route,
                        method="GET",
                        parameters={},
                        expected_status=200,
                        expected_status_source=f"{ui.get('file')}: auth guard redirects unauthenticated visitor to login view",
                        authentication_required=False,
                        authentication_source="Unauthenticated access test",
                        selector=primary_sel,
                        selector_source=f"{ui.get('file')}: protected route {ui_route}",
                        evidence=[f"Authentication guard check on protected route '{ui_route}'"],
                        confidence=1.0,
                        validation_status=ValidationStatus.VALID,
                    )
                    proposals.append(
                        ProposedTestCase(
                            id="",
                            title=f"Playwright UI: Verify unauthenticated navigation to {ui_route} redirects to login view",
                            description=f"Verify that directly navigating to protected route '{ui_route}' without active session redirects to login view.",
                            type=ProposedTestType.UI,
                            priority=ProposedTestPriority.HIGH,
                            source="LLM Generated",
                            reason=f"Role & Permission test: protected route '{ui_route}' must require active authentication.",
                            preconditions=["Browser session storage is cleared and unauthenticated"],
                            test_data={"ui_view": ui_name, "route": ui_route},
                            steps=[
                                "Clear localStorage and browser session cookies",
                                f"Navigate directly to protected route '{ui_route}'",
                                "Verify browser is redirected to '/login' or root authentication view",
                                "Assert login form controls are presented",
                                "Capture screenshot evidence",
                            ],
                            expected_result="Protected route redirects unauthenticated visitor to login landing view with redirect notification",
                            status=ProposedTestStatus.PROPOSED,
                            generation_source="LLM Generated",
                            metadata=meta,
                            category="Role & Permission Testing",
                            custom_instruction_note="Protected route unauthenticated access redirection",
                            ui_spec=UiTestSpec(
                                target_route=ui_route,
                                actions=["navigate", "screenshot"],
                                expected_elements=[],
                                assertions=["expect(page).toHaveURL(/.*(login|auth|\\/$).*/)"],
                                authentication_required=False,
                            ),
                        )
                    )

            # 5. End-to-End Workflow Testing for UI
            if "e2e-workflow" in enabled_cat_ids:
                if has_form and inputs:
                    dest_route = ui_route.replace("/new", "")
                    meta = TestCaseMetadata(
                        test_id="",
                        endpoint=ui_route,
                        method="POST",
                        parameters={},
                        expected_status=200,
                        expected_status_source=f"{ui.get('file')}: successful form creation workflow redirects and updates table",
                        authentication_required=True,
                        authentication_source="Authenticated session form test",
                        selector=primary_sel,
                        selector_source=f"{ui.get('file')}: form element {primary_sel}",
                        evidence=[f"{ui.get('file')}: Complete business workflow creation for {ui_name}"],
                        dependencies=["AUTHENTICATE_SESSION"],
                        confidence=1.0,
                        validation_status=ValidationStatus.VALID,
                    )
                    proposals.append(
                        ProposedTestCase(
                            id="",
                            title=f"Playwright UI: End-to-end multi-step workflow submission and list update on {ui_name}",
                            description=f"Verify full business creation workflow on '{ui_route}', redirection, and presence in record table.",
                            type=ProposedTestType.UI,
                            priority=ProposedTestPriority.HIGH,
                            source="LLM Generated",
                            reason=f"End-to-end multi-step workflow test for {ui_name}.",
                            preconditions=["Application is running", "Authenticated session active"],
                            test_data={"ui_view": ui_name, "route": ui_route},
                            steps=[
                                f"Navigate to '{ui_route}' in browser",
                                f"Fill all form fields with valid realistic test data ({fields_summary})",
                                f"Click '{submit_btn}' action button",
                                f"Verify redirection to '{dest_route}' or success notification toast",
                                "Assert updated record appears in table list view",
                                "Capture screenshot evidence",
                            ],
                            expected_result="Workflow completes successfully with toast notification and record listed in table",
                            status=ProposedTestStatus.PROPOSED,
                            generation_source="LLM Generated",
                            metadata=meta,
                            category="End-to-End Workflow Testing",
                            custom_instruction_note="End-to-end multi-step form workflow",
                            ui_spec=UiTestSpec(
                                target_route=ui_route,
                                input_fields=inputs,
                                actions=["navigate", "fill", "click", "screenshot"],
                                expected_elements=[primary_sel],
                                assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
                            ),
                        )
                    )
                elif has_table or ui_route == "/":
                    meta = TestCaseMetadata(
                        test_id="",
                        endpoint=ui_route,
                        method="GET",
                        parameters={},
                        expected_status=200,
                        expected_status_source=f"{ui.get('file')}: application navigation workflow renders table and layout",
                        authentication_required=True,
                        authentication_source="Authenticated session view",
                        selector=primary_sel,
                        selector_source=f"{ui.get('file')}: view element {primary_sel}",
                        evidence=[f"{ui.get('file')}: Navigation workflow verification"],
                        dependencies=["AUTHENTICATE_SESSION"],
                        confidence=1.0,
                        validation_status=ValidationStatus.VALID,
                    )
                    proposals.append(
                        ProposedTestCase(
                            id="",
                            title=f"Playwright UI: Multi-step navigation and table data verification on {ui_name}",
                            description=f"Verify navigating to '{ui_route}', verifying headers, and checking table data rows.",
                            type=ProposedTestType.UI,
                            priority=ProposedTestPriority.MEDIUM,
                            source="LLM Generated",
                            reason=f"End-to-end navigation and table verification for {ui_name}.",
                            preconditions=["Application is running", "Authenticated session active"],
                            test_data={"ui_view": ui_name, "route": ui_route},
                            steps=[
                                f"Navigate to '{ui_route}' in browser",
                                "Verify page heading and layout containers are rendered",
                                "Assert data table headers and record rows are displayed",
                                "Capture screenshot evidence",
                            ],
                            expected_result="Module view and record table render with intact data layout",
                            status=ProposedTestStatus.PROPOSED,
                            generation_source="LLM Generated",
                            metadata=meta,
                            category="End-to-End Workflow Testing",
                            custom_instruction_note="Navigation and table layout verification",
                            ui_spec=UiTestSpec(
                                target_route=ui_route,
                                actions=["navigate", "click nav a:not([href='/'])", "screenshot"] if ui_route in ("/", "") else ["navigate", "screenshot"],
                                expected_elements=["table, .table-responsive, table tbody tr"],
                                assertions=["expect(page.locator('table, .table-responsive, table tbody tr').first()).toBeVisible()"],
                                authentication_required=True,
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
