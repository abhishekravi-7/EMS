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
    ValidationStatus,
    ValidationSummary,
)
from app.infrastructure.workspace.workspace_paths import WorkspacePaths

logger = logging.getLogger(__name__)


def _normalize_endpoint(path: str) -> str:
    """Normalizes endpoint URL path for matching (replaces path params like {id} with wildcard)."""
    if not path:
        return "/"
    p = "/" + path.strip("/")
    # Normalize path variables like {id} or :id or {userId} to {*}
    p = re.sub(r"\{[^}]+\}", "{*}", p)
    p = re.sub(r":\w+", "{*}", p)
    return p.lower()


class ProposedTestValidator:
    """
    Validates LLM-generated proposed functional test cases against actual repository source code.
    Identifies valid, partially valid, invalid, hallucinated, duplicate, and unsupported tests.
    """

    def __init__(self, repo_dir: Path, analysis_data: dict[str, Any] | None = None) -> None:
        self.repo_dir = Path(repo_dir)
        self.analysis = analysis_data or {}
        self.endpoints = self.analysis.get("endpoints", [])
        self.controllers = self.analysis.get("controllers", [])
        self.services = self.analysis.get("services", [])
        self.ui_workflows = self.analysis.get("ui_workflows", [])
        self.entities = self.analysis.get("entities", [])

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

    def validate_test_case(
        self,
        test: ProposedTestCase,
        seen_scenarios: set[str] | None = None,
    ) -> ProposedTestValidationResult:
        """
        Validates an individual test case against the repository source code evidence.
        """
        functional_area = self._infer_functional_area(test)

        # 1. Non-functional check (e.g. testing compilation, linting, formatting without behavior)
        if self._is_non_functional_test(test):
            return ProposedTestValidationResult(
                status=ValidationStatus.INVALID,
                repository_evidence=None,
                issue="Scenario checks static code structure or compilation rather than functional application behavior",
                playwright_executable=False,
                functional_area=functional_area,
            )

        # 2. Hardware / Unsupported check
        if self._is_unsupported_scenario(test):
            return ProposedTestValidationResult(
                status=ValidationStatus.UNSUPPORTED,
                repository_evidence=None,
                issue="Scenario requires external desktop native hardware or non-web protocol unsupported by Playwright",
                playwright_executable=False,
                functional_area=functional_area,
            )

        # 3. Duplicate check
        scenario_key = self._get_scenario_signature(test)
        if seen_scenarios is not None and scenario_key in seen_scenarios:
            return ProposedTestValidationResult(
                status=ValidationStatus.DUPLICATE,
                repository_evidence=None,
                issue=f"Duplicate functional scenario overlapping with an already validated test ({scenario_key})",
                playwright_executable=False,
                functional_area=functional_area,
            )

        # 4. API Test Case Validation
        if test.type == ProposedTestType.API and test.api_spec:
            spec = test.api_spec
            method = spec.method.upper()
            raw_path = spec.endpoint
            norm_path = _normalize_endpoint(raw_path)

            # Exact method + endpoint match
            if (method, norm_path) in self.endpoint_index:
                ep = self.endpoint_index[(method, norm_path)]
                file_name = ep.get("file", f"{ep.get('class_name', 'Controller')}.java")

                # Check expected status
                if spec.expected_status and spec.expected_status not in [200, 201, 202, 204, 301, 302, 400, 401, 403, 404, 500]:
                    return ProposedTestValidationResult(
                        status=ValidationStatus.PARTIALLY_VALID,
                        repository_evidence=f"{file_name}: @{method}Mapping('{ep.get('endpoint')}')",
                        issue=f"Unusual expected HTTP status code ({spec.expected_status}) for endpoint '{ep.get('endpoint')}'",
                        playwright_executable=True,
                        functional_area=functional_area,
                    )

                return ProposedTestValidationResult(
                    status=ValidationStatus.VALID,
                    repository_evidence=f"{file_name}: @{method}Mapping('{ep.get('endpoint')}')",
                    issue=None,
                    playwright_executable=True,
                    functional_area=functional_area,
                )

            # Path exists but with different HTTP method (e.g. POST requested, only GET implemented)
            if norm_path in self.path_to_endpoints:
                available_eps = self.path_to_endpoints[norm_path]
                avail_methods = [e.get("method", "GET") for e in available_eps]
                first_ep = available_eps[0]
                return ProposedTestValidationResult(
                    status=ValidationStatus.PARTIALLY_VALID,
                    repository_evidence=f"{first_ep.get('file')}: Implemented methods: {', '.join(avail_methods)}",
                    issue=f"Endpoint '{raw_path}' exists but method '{method}' is not implemented (available: {', '.join(avail_methods)})",
                    playwright_executable=True,
                    functional_area=functional_area,
                )

            # Check similar path variations (e.g., missing /api prefix)
            alt_path = norm_path.replace("/api", "") if norm_path.startswith("/api") else f"/api{norm_path}"
            if (method, alt_path) in self.endpoint_index:
                alt_ep = self.endpoint_index[(method, alt_path)]
                return ProposedTestValidationResult(
                    status=ValidationStatus.PARTIALLY_VALID,
                    repository_evidence=f"{alt_ep.get('file')}: @{method}Mapping('{alt_ep.get('endpoint')}')",
                    issue=f"Endpoint path variation: proposed '{raw_path}', actual in repository is '{alt_ep.get('endpoint')}'",
                    playwright_executable=True,
                    functional_area=functional_area,
                )

            # Check if domain controller or service exists in repository
            source_lower = (test.source or "").lower()
            matched_ctrl = any(source_lower in c for c in self.controller_names)
            if matched_ctrl:
                return ProposedTestValidationResult(
                    status=ValidationStatus.PARTIALLY_VALID,
                    repository_evidence=f"Controller '{test.source}' exists, but endpoint '{raw_path}' was not declared",
                    issue=f"Controller exists but endpoint '{method} {raw_path}' is missing",
                    playwright_executable=False,
                    functional_area=functional_area,
                )

            # Endpoint does not exist anywhere in repository
            return ProposedTestValidationResult(
                status=ValidationStatus.HALLUCINATED,
                repository_evidence=None,
                issue=f"No controller, service, or REST endpoint matching '{method} {raw_path}' exists in repository",
                playwright_executable=False,
                functional_area=functional_area,
            )

        # 5. UI Test Case Validation
        if test.type == ProposedTestType.UI:
            target_route = (test.ui_spec.target_route if test.ui_spec else "/") or "/"
            norm_route = _normalize_endpoint(target_route)
            route_slug = norm_route.strip("/").lower()

            # Reject REST API endpoints mistakenly proposed as UI tests
            if norm_route.startswith("/api/") or norm_route.startswith("/rest/") or target_route.startswith("/api/") or target_route.startswith("/rest/"):
                return ProposedTestValidationResult(
                    status=ValidationStatus.INVALID,
                    repository_evidence=None,
                    issue=f"Target route '{target_route}' is a REST API endpoint, not a browser-navigable UI page. Generate an API test instead.",
                    playwright_executable=False,
                    functional_area=functional_area,
                )

            # Reject unrouted fragments and partial components (e.g. /footer, /head, /header, /preheader, /layout, /inputfield)
            fragment_slugs = {
                "footer",
                "head",
                "header",
                "preheader",
                "layout",
                "inputfield",
                "selectfield",
                "sidebar",
                "menu",
                "navbar",
                "nav",
                "partials",
                "fragments",
                "modal",
                "button",
            }
            if route_slug in fragment_slugs and norm_route not in self.ui_routes:
                return ProposedTestValidationResult(
                    status=ValidationStatus.INVALID,
                    repository_evidence=None,
                    issue=f"Target route '{target_route}' is an internal UI fragment or component, not a navigable application route.",
                    playwright_executable=False,
                    functional_area=functional_area,
                )

            # Check in discovered UI workflows
            if norm_route in self.ui_routes:
                ui_info = self.ui_routes[norm_route]
                grounded_sels = ui_info.get("grounded_selectors", [])

                # Verify that required selectors/elements exist in repository template
                if test.ui_spec and test.ui_spec.expected_elements:
                    ungrounded_sels = []
                    for el_sel in test.ui_spec.expected_elements:
                        # Flag synthetic or ungrounded selectors like [data-testid="main-container"]
                        if "main-container" in el_sel:
                            ungrounded_sels.append(el_sel)
                        elif el_sel.startswith("#") and grounded_sels and not any(el_sel in s for s in grounded_sels):
                            ungrounded_sels.append(el_sel)

                    if ungrounded_sels:
                        return ProposedTestValidationResult(
                            status=ValidationStatus.PARTIALLY_VALID,
                            repository_evidence=f"UI Route '{target_route}' discovered in {ui_info.get('file', 'UI Template')}",
                            issue=f"Selectors {ungrounded_sels} are not grounded in the template DOM for route '{target_route}'.",
                            playwright_executable=False,
                            functional_area=functional_area,
                        )

                return ProposedTestValidationResult(
                    status=ValidationStatus.VALID,
                    repository_evidence=f"UI Route '{target_route}' discovered in {ui_info.get('file', 'UI Template')}",
                    issue=None,
                    playwright_executable=True,
                    functional_area=functional_area,
                )

            # Check if root route / or /index.html is supported when ui_workflows exist
            if norm_route in ["/", "/index.html"] and self.ui_workflows:
                first_ui = self.ui_workflows[0]
                return ProposedTestValidationResult(
                    status=ValidationStatus.VALID,
                    repository_evidence=f"Root UI Route '/' matched with template {first_ui.get('file', 'UI Template')}",
                    issue=None,
                    playwright_executable=True,
                    functional_area=functional_area,
                )

            # Check if project has a frontend or web MVC layer
            if not self.ui_workflows:
                return ProposedTestValidationResult(
                    status=ValidationStatus.HALLUCINATED,
                    repository_evidence=None,
                    issue=f"No UI frontend or view template matching route '{target_route}' exists in this repository",
                    playwright_executable=False,
                    functional_area=functional_area,
                )

            # UI route not found in application routes
            return ProposedTestValidationResult(
                status=ValidationStatus.HALLUCINATED,
                repository_evidence=None,
                issue=f"UI route '{target_route}' is not a navigable route in this application.",
                playwright_executable=False,
                functional_area=functional_area,
            )

        # 6. Any other non-UI / non-API test case is strictly INVALID
        return ProposedTestValidationResult(
            status=ValidationStatus.INVALID,
            repository_evidence=None,
            issue="Test is not a functional UI or API test. Unit tests, build checks, and static analysis are not supported in Proposed Functional Tests.",
            playwright_executable=False,
            functional_area=functional_area,
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
            return f"API:{test.api_spec.method.upper()}:{_normalize_endpoint(test.api_spec.endpoint)}"
        if test.type == ProposedTestType.UI and test.ui_spec:
            return f"UI:{_normalize_endpoint(test.ui_spec.target_route or '/')}"
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
