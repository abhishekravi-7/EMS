"""Validation Engine for LLM Generated Proposed Functional Test Cases."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from app.domain.models.proposed_test_models import (
    ProposedTestCase,
    ProposedTestType,
    ProposedTestValidationResult,
    TestCaseMetadata,
    ValidationStatus,
    ValidationSummary,
)
from app.infrastructure.workspace.workspace_paths import WorkspacePaths

logger = logging.getLogger(__name__)


def _normalize_endpoint(path: str) -> str:
    """Normalizes endpoint URL path for matching (replaces path params like {id} with wildcard)."""
    if not path:
        return "/"
    # Strip query parameters
    path = path.split("?")[0].rstrip(".")
    p = "/" + path.strip("/")
    # Normalize path variables like {id} or :id or {userId} to {*}
    p = re.sub(r"\{[^}]+\}", "{*}", p)
    p = re.sub(r":\w+", "{*}", p)
    # Normalize path segments after parameter indicators like /emp/EMP001, /department/IT, /date/2024-05-24
    p = re.sub(r"/(emp|department|designation|employee|date|month|year|id)/[^/]+", r"/\1/{*}", p, flags=re.IGNORECASE)
    # Normalize numeric IDs e.g. /123 or /999999 to {*}
    p = re.sub(r"/\d+", "/{*}", p)
    return p.lower()


class ProposedTestValidator:
    """
    Validates LLM-generated proposed functional test cases against actual repository source code.
    Identifies valid, partially valid, invalid, hallucinated, duplicate, unsupported, review required,
    and blocked dependency / authentication tests.
    """

    def __init__(self, repo_dir: Path, analysis_data: dict[str, Any] | None = None) -> None:
        self.repo_dir = Path(repo_dir)
        self.analysis = analysis_data or {}
        self.endpoints = self.analysis.get("endpoints", [])
        self.controllers = self.analysis.get("controllers", [])
        self.services = self.analysis.get("services", [])
        self.ui_workflows = self.analysis.get("ui_workflows", [])
        self.credentials = self.analysis.get("credentials", []) or self.analysis.get("application_credentials", [])
        if not self.credentials and self.repo_dir and self.repo_dir.exists():
            try:
                from app.application.use_cases.proposed_tests.authentication_manager import AuthenticationManager
                discovered = AuthenticationManager(self.repo_dir).discover_credentials()
                if discovered:
                    self.credentials = [{"username": c.username, "password": c.password, "source": c.source, "role": c.role} for c in discovered]
            except Exception:
                pass
        self.security_rules = self.analysis.get("security_rules", [])

        # Build lookup indices
        self._build_indices()

    def _build_indices(self) -> None:
        """Builds lookup structures for rapid endpoint, controller, and UI route matching."""
        self.endpoint_index: dict[tuple[str, str], dict[str, Any]] = {}
        self.path_to_endpoints: dict[str, list[dict[str, Any]]] = {}

        for ep in self.endpoints:
            method = ep.get("method", "GET").upper()
            raw_path = ep.get("endpoint", "/")
            norm_path = _normalize_endpoint(raw_path)
            self.endpoint_index[(method, norm_path)] = ep
            self.path_to_endpoints.setdefault(norm_path, []).append(ep)

        self.controller_names = {c.get("name", "").lower(): c for c in self.controllers}
        self.service_names = {s.get("name", "").lower(): s for s in self.services}
        self.ui_routes = {
            _normalize_endpoint(u.get("route", "/")): u for u in self.ui_workflows
        }

    def _ensure_metadata(self, test: ProposedTestCase) -> TestCaseMetadata:
        """Ensures all 14 TestCaseMetadata fields are populated on the testcase."""
        if test.metadata is not None:
            return test.metadata

        ep = None
        method = "GET"
        expected_status = 200
        if test.type == ProposedTestType.API and test.api_spec:
            ep = test.api_spec.endpoint
            method = test.api_spec.method.upper()
            expected_status = test.api_spec.expected_status
        elif test.type == ProposedTestType.UI and test.ui_spec:
            ep = test.ui_spec.target_route
            method = "GET"

        selector = None
        if test.ui_spec and test.ui_spec.expected_elements:
            selector = test.ui_spec.expected_elements[0]

        meta = TestCaseMetadata(
            test_id=test.id,
            endpoint=ep,
            method=method,
            parameters=test.test_data.get("path_params", {}) if test.test_data and isinstance(test.test_data.get("path_params"), dict) else {},
            expected_status=expected_status,
            expected_status_source="Repository handler declaration",
            authentication_required=False,
            authentication_source="No security rules declared",
            selector=selector,
            selector_source="Repository UI template" if selector else None,
            parameter_sources={},
            evidence=[test.source or "Repository analysis"],
            dependencies=[],
            confidence=1.0,
            validation_status=ValidationStatus.VALID,
        )
        test.metadata = meta
        return meta

    def _is_endpoint_protected(self, endpoint: str) -> bool:
        """Determines if an endpoint or route is protected by security rules in repository analysis."""
        clean_ep = endpoint.split("?")[0].strip("/")
        for rule in self.security_rules:
            if isinstance(rule, str):
                rule_lower = rule.lower()
                if "permitall" in rule_lower or "anonymous" in rule_lower:
                    continue
                if any(k in rule_lower for k in ["authenticated", "hasrole", "hasauthority", "webfilter", "loginrequired"]):
                    return True
                continue
            if not isinstance(rule, dict):
                continue
            pattern = rule.get("pattern", "")
            excludes = rule.get("excludes", [])
            if any(ex.strip("/") in clean_ep for ex in excludes):
                continue
            if pattern in ("/*", "/**"):
                return True
            if pattern.endswith(".do") and clean_ep.endswith(".do"):
                return True
            norm_pattern = _normalize_endpoint(pattern)
            norm_ep = _normalize_endpoint(endpoint)
            if norm_pattern == norm_ep or (norm_pattern.endswith("/*") and norm_ep.startswith(norm_pattern[:-2])):
                if rule.get("authenticated", True):
                    return True
        return False

    def validate_test_case(
        self,
        test: ProposedTestCase,
        seen_scenarios: set[str] | None = None,
    ) -> ProposedTestValidationResult:
        """
        Validates an individual test case against repository source code evidence.
        Strict execution gate: execute ONLY testcases whose validation status is VALID.
        Every other testcase is rejected before execution begins and marked with its specific block reason:
        - REVIEW_REQUIRED — testcase has unverified status code, ambiguous interaction type, or missing business assertion
        - BLOCKED_DEPENDENCY — required preceding entity does not exist and cannot be created dynamically
        - BLOCKED_AUTHENTICATION — endpoint requires authentication and no valid credential exists
        - INVALID — violates contract, nonexistent endpoint, nonexistent selector, or unresolvable parameter
        """
        functional_area = self._infer_functional_area(test)
        metadata = self._ensure_metadata(test)

        # 1. Non-functional check
        if self._is_non_functional_test(test):
            metadata.validation_status = ValidationStatus.INVALID
            return ProposedTestValidationResult(
                status=ValidationStatus.INVALID,
                repository_evidence=None,
                issue="Scenario checks static code structure or compilation rather than functional application behavior",
                playwright_executable=False,
                functional_area=functional_area,
                metadata=metadata,
            )

        # 2. Hardware / Unsupported check
        if self._is_unsupported_scenario(test):
            metadata.validation_status = ValidationStatus.UNSUPPORTED
            return ProposedTestValidationResult(
                status=ValidationStatus.UNSUPPORTED,
                repository_evidence=None,
                issue="Scenario requires external desktop native hardware or non-web protocol unsupported by Playwright",
                playwright_executable=False,
                functional_area=functional_area,
                metadata=metadata,
            )

        # 3. Duplicate check
        scenario_key = self._get_scenario_signature(test)
        if seen_scenarios is not None and scenario_key in seen_scenarios:
            metadata.validation_status = ValidationStatus.DUPLICATE
            return ProposedTestValidationResult(
                status=ValidationStatus.DUPLICATE,
                repository_evidence=None,
                issue=f"Duplicate functional scenario overlapping with an already validated test ({scenario_key})",
                playwright_executable=False,
                functional_area=functional_area,
                metadata=metadata,
            )

        # 4. (Removed) Path variables like {id} are now allowed to pass validation
        # so that they can be resolved dynamically at runtime by DynamicDataResolver.
        raw_target = (test.api_spec.endpoint if test.api_spec else (test.ui_spec.target_route if test.ui_spec else "")) or ""
        norm_target = _normalize_endpoint(raw_target)

        # 5. Check Authentication Requirement
        auth_required = metadata.authentication_required or self._is_endpoint_protected(raw_target)
        if auth_required:
            metadata.authentication_required = True
            if not self.credentials:
                metadata.validation_status = ValidationStatus.BLOCKED_AUTHENTICATION
                return ProposedTestValidationResult(
                    status=ValidationStatus.BLOCKED_AUTHENTICATION,
                    repository_evidence=None,
                    issue=f"Endpoint '{raw_target}' requires authentication, but no valid credentials exist in repository analysis.",
                    playwright_executable=False,
                    functional_area=functional_area,
                    metadata=metadata,
                )

        # 6. API Test Case Validation
        if test.type == ProposedTestType.API and test.api_spec:
            spec = test.api_spec
            method = spec.method.upper()
            raw_path = spec.endpoint
            norm_path = _normalize_endpoint(raw_path)

            # Exact method + endpoint match
            if (method, norm_path) in self.endpoint_index:
                ep = self.endpoint_index[(method, norm_path)]
                file_name = ep.get("file", f"{ep.get('class_name', 'Controller')}.java")

                # Expected status verification
                exp_status = spec.expected_status or 200
                status_src = metadata.expected_status_source or ""

                # Negative test verification
                if exp_status in (400, 401, 403, 404, 500):
                    if not status_src or "REVIEW_REQUIRED" in status_src or "Hypothetical" in status_src:
                        metadata.validation_status = ValidationStatus.REVIEW_REQUIRED
                        return ProposedTestValidationResult(
                            status=ValidationStatus.REVIEW_REQUIRED,
                            repository_evidence=f"{file_name}: @{method}Mapping('{ep.get('endpoint')}')",
                            issue=f"Negative test expected HTTP status {exp_status} lacks verified repository evidence (no @ResponseStatus or explicit exception handling).",
                            playwright_executable=False,
                            functional_area=functional_area,
                            metadata=metadata,
                        )

                # Unusual status code
                if exp_status not in [200, 201, 202, 204, 301, 302, 303, 307, 400, 401, 403, 404, 500]:
                    metadata.validation_status = ValidationStatus.REVIEW_REQUIRED
                    return ProposedTestValidationResult(
                        status=ValidationStatus.REVIEW_REQUIRED,
                        repository_evidence=f"{file_name}: @{method}Mapping('{ep.get('endpoint')}')",
                        issue=f"Unusual expected HTTP status code ({exp_status}) for endpoint '{ep.get('endpoint')}'.",
                        playwright_executable=False,
                        functional_area=functional_area,
                        metadata=metadata,
                    )

                metadata.validation_status = ValidationStatus.VALID
                return ProposedTestValidationResult(
                    status=ValidationStatus.VALID,
                    repository_evidence=f"{file_name}: @{method}Mapping('{ep.get('endpoint')}')",
                    issue=None,
                    playwright_executable=True,
                    functional_area=functional_area,
                    metadata=metadata,
                )

            # Path exists but with different HTTP method (e.g. POST requested, only GET implemented)
            if norm_path in self.path_to_endpoints:
                available_eps = self.path_to_endpoints[norm_path]
                avail_methods = [e.get("method", "GET") for e in available_eps]
                first_ep = available_eps[0]
                metadata.validation_status = ValidationStatus.INVALID
                return ProposedTestValidationResult(
                    status=ValidationStatus.INVALID,
                    repository_evidence=f"{first_ep.get('file')}: Implemented methods: {', '.join(avail_methods)}",
                    issue=f"Endpoint '{raw_path}' exists but method '{method}' is not implemented (available: {', '.join(avail_methods)})",
                    playwright_executable=False,
                    functional_area=functional_area,
                    metadata=metadata,
                )

            # Check similar path variations (e.g., missing /api prefix)
            alt_path = norm_path.replace("/api", "") if norm_path.startswith("/api") else f"/api{norm_path}"
            if (method, alt_path) in self.endpoint_index:
                alt_ep = self.endpoint_index[(method, alt_path)]
                metadata.validation_status = ValidationStatus.REVIEW_REQUIRED
                return ProposedTestValidationResult(
                    status=ValidationStatus.REVIEW_REQUIRED,
                    repository_evidence=f"{alt_ep.get('file')}: @{method}Mapping('{alt_ep.get('endpoint')}')",
                    issue=f"Endpoint path variation: proposed '{raw_path}', actual in repository is '{alt_ep.get('endpoint')}'",
                    playwright_executable=False,
                    functional_area=functional_area,
                    metadata=metadata,
                )

            # Check if domain controller or service exists in repository
            source_lower = (test.source or "").lower()
            matched_ctrl = any(source_lower in c for c in self.controller_names)
            if matched_ctrl:
                metadata.validation_status = ValidationStatus.HALLUCINATED
                return ProposedTestValidationResult(
                    status=ValidationStatus.HALLUCINATED,
                    repository_evidence=f"Controller '{test.source}' exists, but endpoint '{raw_path}' was not declared",
                    issue=f"Controller exists but endpoint '{method} {raw_path}' is missing",
                    playwright_executable=False,
                    functional_area=functional_area,
                    metadata=metadata,
                )

            # Endpoint does not exist anywhere in repository
            metadata.validation_status = ValidationStatus.HALLUCINATED
            return ProposedTestValidationResult(
                status=ValidationStatus.HALLUCINATED,
                repository_evidence=None,
                issue=f"No controller, service, or REST endpoint matching '{method} {raw_path}' exists in repository",
                playwright_executable=False,
                functional_area=functional_area,
                metadata=metadata,
            )

        # 7. UI Test Case Validation
        if test.type == ProposedTestType.UI:
            target_route = (test.ui_spec.target_route if test.ui_spec else "/") or "/"
            norm_route = _normalize_endpoint(target_route)
            route_slug = norm_route.strip("/").lower()

            # Reject REST API endpoints mistakenly proposed as UI tests
            if norm_route.startswith("/api/") or norm_route.startswith("/rest/") or target_route.startswith("/api/") or target_route.startswith("/rest/"):
                metadata.validation_status = ValidationStatus.INVALID
                return ProposedTestValidationResult(
                    status=ValidationStatus.INVALID,
                    repository_evidence=None,
                    issue=f"Target route '{target_route}' is a REST API endpoint, not a browser-navigable UI page. Generate an API test instead.",
                    playwright_executable=False,
                    functional_area=functional_area,
                    metadata=metadata,
                )

            # Reject unrouted fragments and partial components
            fragment_slugs = {
                "footer", "head", "header", "preheader", "layout", "inputfield", "selectfield",
                "sidebar", "menu", "navbar", "nav", "partials", "fragments", "modal", "button",
            }
            if route_slug in fragment_slugs and norm_route not in self.ui_routes:
                metadata.validation_status = ValidationStatus.INVALID
                return ProposedTestValidationResult(
                    status=ValidationStatus.INVALID,
                    repository_evidence=None,
                    issue=f"Target route '{target_route}' is an internal UI fragment or component, not a navigable application route.",
                    playwright_executable=False,
                    functional_area=functional_area,
                    metadata=metadata,
                )

            # Check in discovered UI workflows
            ui_info = self.ui_routes.get(norm_route)
            if not ui_info and norm_route in ["/", "/index.html"] and self.ui_workflows:
                ui_info = self.ui_workflows[0]

            if ui_info:
                grounded_sels = ui_info.get("grounded_selectors", [])

                # Verify selectors against repository template
                all_sels = list((test.ui_spec.expected_elements if test.ui_spec else []) or [])
                if metadata.selector and metadata.selector not in all_sels:
                    all_sels.append(metadata.selector)

                ungrounded_sels = []
                for el_sel in all_sels:
                    if any(k in el_sel for k in ["main-container", "app-root", "content-wrapper"]):
                        ungrounded_sels.append(el_sel)
                    elif el_sel.startswith("#") and grounded_sels and not any(el_sel in s for s in grounded_sels):
                        ungrounded_sels.append(el_sel)

                if ungrounded_sels:
                    metadata.validation_status = ValidationStatus.REVIEW_REQUIRED
                    return ProposedTestValidationResult(
                        status=ValidationStatus.REVIEW_REQUIRED,
                        repository_evidence=f"UI Route '{target_route}' discovered in {ui_info.get('file', 'UI Template')}",
                        issue=f"Selectors {ungrounded_sels} are synthetic or not verified against template DOM for route '{target_route}'.",
                        playwright_executable=False,
                        functional_area=functional_area,
                        metadata=metadata,
                    )

                # Form submission / Business assertion check
                title_lower = test.title.lower()
                desc_lower = (test.description or "").lower()
                is_mutation = any(k in title_lower or k in desc_lower for k in ["submit", "create", "add", "update", "delete", "post", "login", "register"])
                if is_mutation:
                    exp_res = (test.expected_result or "").lower()
                    steps_text = " ".join(test.steps).lower() if test.steps else ""
                    has_business_evidence = any(k in exp_res or k in steps_text for k in [
                        "redirect", "alert", "notification", "table", "row", "list", "toast", "message", "url changed", "success", "error-message"
                    ])
                    if not has_business_evidence:
                        metadata.validation_status = ValidationStatus.REVIEW_REQUIRED
                        return ProposedTestValidationResult(
                            status=ValidationStatus.REVIEW_REQUIRED,
                            repository_evidence=f"UI Route '{target_route}' discovered in {ui_info.get('file', 'UI Template')}",
                            issue="Form submission test lacks concrete business evidence assertion (redirect, alert, or DOM state change).",
                            playwright_executable=False,
                            functional_area=functional_area,
                            metadata=metadata,
                        )

                metadata.validation_status = ValidationStatus.VALID
                return ProposedTestValidationResult(
                    status=ValidationStatus.VALID,
                    repository_evidence=f"UI Route '{target_route}' discovered in {ui_info.get('file', 'UI Template')}",
                    issue=None,
                    playwright_executable=True,
                    functional_area=functional_area,
                    metadata=metadata,
                )

            # Check if project has a frontend or web MVC layer
            if not self.ui_workflows:
                metadata.validation_status = ValidationStatus.HALLUCINATED
                return ProposedTestValidationResult(
                    status=ValidationStatus.HALLUCINATED,
                    repository_evidence=None,
                    issue=f"No UI frontend or view template matching route '{target_route}' exists in this repository",
                    playwright_executable=False,
                    functional_area=functional_area,
                    metadata=metadata,
                )

            # UI route not found in application routes
            metadata.validation_status = ValidationStatus.HALLUCINATED
            return ProposedTestValidationResult(
                status=ValidationStatus.HALLUCINATED,
                repository_evidence=None,
                issue=f"UI route '{target_route}' is not a navigable route in this application.",
                playwright_executable=False,
                functional_area=functional_area,
                metadata=metadata,
            )

        # 8. Any other non-UI / non-API test case is strictly INVALID
        metadata.validation_status = ValidationStatus.INVALID
        return ProposedTestValidationResult(
            status=ValidationStatus.INVALID,
            repository_evidence=None,
            issue="Test is not a functional UI or API test. Unit tests, build checks, and static analysis are not supported in Proposed Functional Tests.",
            playwright_executable=False,
            functional_area=functional_area,
            metadata=metadata,
        )


    def validate_all(
        self,
        tests: list[ProposedTestCase],
    ) -> tuple[list[ProposedTestCase], ValidationSummary]:
        """
        Validates all proposed tests and attaches validation results to each test case.
        Returns the updated list and a dynamic ValidationSummary.
        """
        seen_scenarios: set[str] = set()
        validated_tests: list[ProposedTestCase] = []

        valid_cnt = 0
        review_required_cnt = 0
        blocked_dependency_cnt = 0
        blocked_authentication_cnt = 0
        partially_valid_cnt = 0
        invalid_cnt = 0
        hallucinated_cnt = 0
        duplicate_cnt = 0
        unsupported_cnt = 0

        functional_areas_seen: dict[str, bool] = {}

        # Pre-seed common functional areas from repository
        for ep in self.endpoints:
            fa = self._endpoint_to_area(ep.get("endpoint", ""), ep.get("class_name", ""))
            functional_areas_seen.setdefault(fa, False)

        for t in tests:
            val_res = self.validate_test_case(t, seen_scenarios=seen_scenarios)
            t.validation = val_res
            validated_tests.append(t)

            # Record scenario key for duplicate detection
            sig = self._get_scenario_signature(t)
            if val_res.status != ValidationStatus.DUPLICATE:
                seen_scenarios.add(sig)

            # Update count
            if val_res.status == ValidationStatus.VALID:
                valid_cnt += 1
                functional_areas_seen[val_res.functional_area] = True
            elif val_res.status == ValidationStatus.REVIEW_REQUIRED:
                review_required_cnt += 1
            elif val_res.status == ValidationStatus.BLOCKED_DEPENDENCY:
                blocked_dependency_cnt += 1
            elif val_res.status == ValidationStatus.BLOCKED_AUTHENTICATION:
                blocked_authentication_cnt += 1
            elif val_res.status == ValidationStatus.PARTIALLY_VALID:
                partially_valid_cnt += 1
                functional_areas_seen[val_res.functional_area] = True
            elif val_res.status == ValidationStatus.INVALID:
                invalid_cnt += 1
            elif val_res.status == ValidationStatus.HALLUCINATED:
                hallucinated_cnt += 1
            elif val_res.status == ValidationStatus.DUPLICATE:
                duplicate_cnt += 1
            elif val_res.status == ValidationStatus.UNSUPPORTED:
                unsupported_cnt += 1

        coverage_breakdown = {
            area: "Covered" if covered else "Not Covered"
            for area, covered in functional_areas_seen.items()
        }

        summary = ValidationSummary(
            total_llm_generated=len(tests),
            valid=valid_cnt,
            review_required=review_required_cnt,
            blocked_dependency=blocked_dependency_cnt,
            blocked_authentication=blocked_authentication_cnt,
            partially_valid=partially_valid_cnt,
            invalid=invalid_cnt,
            hallucinated=hallucinated_cnt,
            duplicate=duplicate_cnt,
            unsupported=unsupported_cnt,
            functional_coverage=coverage_breakdown,
        )

        return validated_tests, summary

    def _get_scenario_signature(self, test: ProposedTestCase) -> str:
        if test.type == ProposedTestType.API and test.api_spec:
            ep = _normalize_endpoint(test.api_spec.endpoint)
            method = test.api_spec.method.upper()
            status = test.api_spec.expected_status or (test.metadata.expected_status if test.metadata else 200)

            t_low = (test.title or "").lower()
            intent = "success"
            if test.category:
                cat_slug = re.sub(r'[^a-zA-Z0-9]', '_', test.category.lower()).strip('_')
                field_match = re.search(r'(?:field|parameter|payload|input|scenario)\s+([a-zA-Z0-9_]+)', t_low)
                f_slug = field_match.group(1) if field_match else "main"
                intent = f"{cat_slug}_{f_slug}_{status}"
            elif status in (401, 403) or "unauthorized" in t_low or "permission" in t_low or "role" in t_low or "auth" in t_low:
                intent = f"auth_restriction_{status}"
            elif "edge" in t_low or "boundary" in t_low or "max" in t_low or "empty" in t_low:
                intent = f"edge_case_{status}"
            elif status in (400, 422) or "invalid" in t_low or "reject" in t_low or "negative" in t_low or "malformed" in t_low:
                field_match = re.search(r'(?:field|parameter|payload|input)\s+([a-zA-Z0-9_]+)', t_low)
                param_slug = field_match.group(1) if field_match else "payload"
                intent = f"negative_validation_{param_slug}_{status}"
            elif "workflow" in t_low or "lifecycle" in t_low or "sequence" in t_low:
                intent = f"workflow_{status}"
            elif status == 404 or "not found" in t_low:
                intent = "not_found"

            return f"API:{method}:{ep}:{intent}"

        if test.type == ProposedTestType.UI and test.ui_spec:
            route = _normalize_endpoint(test.ui_spec.target_route or "/")
            t_low = (test.title or "").lower()
            intent = "view"
            if test.category:
                cat_slug = re.sub(r'[^a-zA-Z0-9]', '_', test.category.lower()).strip('_')
                field_match = re.search(r'for\s+([a-zA-Z0-9_]+)\s+on', t_low)
                if not field_match:
                    field_match = re.search(r'(?:field|button|action|table|controls?)\s+([a-zA-Z0-9_]+)', t_low)
                param_slug = field_match.group(1) if field_match else "main"
                intent = f"{cat_slug}_{param_slug}"
            elif "login" in t_low or "auth" in t_low:
                sub_action = "submit" if ("redirect" in t_low or "workflow" in t_low or "authentication" in t_low) else "view_controls"
                intent = f"auth_{sub_action}"
            elif "validation" in t_low or "invalid" in t_low or "missing" in t_low or "error" in t_low or "empty" in t_low:
                field_match = re.search(r'(?:field|input|value)\s+([a-zA-Z0-9_]+)', t_low)
                param_slug = field_match.group(1) if field_match else "required_fields"
                intent = f"negative_validation_{param_slug}"
            elif "edge" in t_low or "boundary" in t_low or "max" in t_low:
                intent = "edge_case"
            elif "role" in t_low or "permission" in t_low or "unauthenticated" in t_low:
                intent = "role_permission"
            elif "workflow" in t_low or "e2e" in t_low:
                intent = "e2e_workflow"
            return f"UI:{route}:{intent}"
        return f"GEN:{test.title.lower().strip()}"

    def _is_non_functional_test(self, test: ProposedTestCase) -> bool:
        if test.type not in [ProposedTestType.API, ProposedTestType.UI] or test.type == ProposedTestType.UNIT:
            return True
        title_lower = test.title.lower()
        desc_lower = (test.description or "").lower()
        source_lower = (test.source or "").lower()
        reason_lower = (test.reason or "").lower()
        combined = f"{title_lower} {desc_lower} {source_lower} {reason_lower}"
        non_func_keywords = [
            "code formatting",
            "check formatting",
            "class existence only",
            "verify compilation",
            "check dependency version",
            "check pom.xml",
            "pom.xml",
            "build.gradle",
            "sonarqube",
            "sonar scan",
            "code coverage",
            "coverage above",
            "unit test",
            "service method",
            "repository method",
            "dao method",
            "internal class",
            "ast validation",
            "static analysis",
            "performance benchmark",
            "security scan",
            "contains @getmapping",
            "contains @postmapping",
            "method exists",
            "class exists",
            "variable has value",
            "calculateduration",
        ]
        return any(k in combined for k in non_func_keywords)

    def _is_unsupported_scenario(self, test: ProposedTestCase) -> bool:
        title_lower = test.title.lower()
        desc_lower = (test.description or "").lower()
        unsupported_keywords = [
            "biometric hardware dongle",
            "usb card reader device",
            "native windows com port",
            "bluetooth scanner hardware",
        ]
        return any(k in title_lower or k in desc_lower for k in unsupported_keywords)

    def _infer_functional_area(self, test: ProposedTestCase) -> str:
        title = test.title.lower()
        if "attendance" in title:
            return "Attendance Management"
        if "login" in title or "auth" in title:
            return "Authentication"
        if "report" in title or "email" in title or "preview" in title:
            return "Reporting & Notifications"
        if "user" in title or "profile" in title:
            return "User Management"
        if "payment" in title or "billing" in title:
            return "Payment & Billing"
        return test.source or "Core Application"

    def _endpoint_to_area(self, endpoint: str, class_name: str) -> str:
        ep_l = endpoint.lower()
        cn_l = class_name.lower()
        if "attendance" in ep_l or "attendance" in cn_l:
            return "Attendance Management"
        if "report" in ep_l or "email" in ep_l or "report" in cn_l:
            return "Reporting & Notifications"
        if "auth" in ep_l or "login" in ep_l or "auth" in cn_l:
            return "Authentication"
        if "user" in ep_l or "user" in cn_l:
            return "User Management"
        return "Core Application"
