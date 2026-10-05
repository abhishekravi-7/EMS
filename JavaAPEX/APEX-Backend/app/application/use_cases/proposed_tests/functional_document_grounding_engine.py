"""Functional Document Grounding Engine.

Converts an uploaded Functional Testing Document into grounded, executable testcases
verified against real repository evidence.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable

from app.domain.models.functional_document_models import (
    DuplicateSkippedItem,
    ExtractedScenario,
    FunctionalDocumentGroundingReport,
    GroundingStatus,
    MatchedScenarioItem,
    PartiallyMatchedScenarioItem,
    UnmatchedScenarioItem,
)
from app.domain.models.proposed_test_models import (
    ApiTestSpec,
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
    TestCaseMetadata,
    UiTestSpec,
    ValidationStatus,
)

logger = logging.getLogger(__name__)


def _normalize_path(path: str) -> str:
    """Normalizes an endpoint or route path for structural comparison."""
    if not path:
        return "/"
    p = path.strip().split("?")[0].rstrip(".")
    if not p.startswith("/"):
        p = "/" + p
    # Replace path parameters like {id}, {empId}, :id with wildcard
    p = re.sub(r"\{[^}]+\}", "{*}", p)
    p = re.sub(r":\w+", "{*}", p)
    # Replace known numeric segments
    p = re.sub(r"/\d+", "/{*}", p)
    return p.lower()


class FunctionalDocumentGroundingEngine:
    """Grounds functional scenarios extracted from testing documents against real repository evidence."""

    def __init__(self) -> None:
        pass

    # ═════════════════════════════════════════════════════════════════════
    # STAGE 1 — EXTRACT SCENARIOS FROM THE DOCUMENT (Dynamic, Not Hardcoded)
    # ═════════════════════════════════════════════════════════════════════

    def extract_scenarios(self, document_text: str) -> tuple[list[ExtractedScenario], list[str]]:
        """Parses document_text into discrete functional scenarios and identifies non-scenario content.

        Supports pipe tables, Gherkin Given/When/Then blocks, numbered testcases,
        and testable prose paragraphs. Excludes title pages, glossaries, overview,
        preconditions, and non-testable context.
        """
        scenarios: list[ExtractedScenario] = []
        non_scenario_content_excluded: list[str] = []

        if not document_text or not document_text.strip():
            return scenarios, non_scenario_content_excluded

        # 1. First, parse out any structured tables (pipe tables)
        table_scenarios, table_excluded, consumed_table_ranges = self._extract_table_scenarios(document_text)
        scenarios.extend(table_scenarios)
        non_scenario_content_excluded.extend(table_excluded)

        # 2. Parse text outside the consumed tables for Gherkin, numbered items, and prose scenarios
        remaining_text = self._strip_consumed_ranges(document_text, consumed_table_ranges)
        text_scenarios, text_excluded = self._extract_text_scenarios(remaining_text)
        scenarios.extend(text_scenarios)
        non_scenario_content_excluded.extend(text_excluded)

        return scenarios, non_scenario_content_excluded

    def _extract_table_scenarios(
        self, text: str
    ) -> tuple[list[ExtractedScenario], list[str], list[tuple[int, int]]]:
        scenarios: list[ExtractedScenario] = []
        excluded: list[str] = []
        ranges: list[tuple[int, int]] = []

        lines = text.splitlines(keepends=True)
        in_table = False
        tbl_lines: list[str] = []
        start_char = 0
        current_pos = 0
        pending_empty_pos = 0

        i = 0
        while i < len(lines):
            line = lines[i]
            line_len = len(line)
            stripped = line.strip()

            if stripped.startswith("|") and stripped.endswith("|"):
                if not in_table:
                    in_table = True
                    start_char = current_pos
                    tbl_lines = [stripped]
                else:
                    tbl_lines.append(stripped)
                current_pos += line_len
                i += 1
            elif not stripped:
                # Blank line: check if upcoming non-blank line continues the table
                next_non_blank = None
                for j in range(i + 1, min(i + 4, len(lines))):
                    if lines[j].strip():
                        next_non_blank = lines[j].strip()
                        break
                if in_table and next_non_blank and next_non_blank.startswith("|") and next_non_blank.endswith("|"):
                    # Blank line within a table block (e.g. from docx paragraph spacing), keep in_table
                    current_pos += line_len
                    i += 1
                else:
                    if in_table:
                        in_table = False
                        end_char = current_pos
                        ranges.append((start_char, end_char))
                        s_list, ex_list = self._process_table_block(tbl_lines)
                        scenarios.extend(s_list)
                        excluded.extend(ex_list)
                        tbl_lines = []
                    current_pos += line_len
                    i += 1
            else:
                if in_table:
                    in_table = False
                    end_char = current_pos
                    ranges.append((start_char, end_char))
                    s_list, ex_list = self._process_table_block(tbl_lines)
                    scenarios.extend(s_list)
                    excluded.extend(ex_list)
                    tbl_lines = []
                current_pos += line_len
                i += 1

        if in_table and tbl_lines:
            ranges.append((start_char, current_pos))
            s_list, ex_list = self._process_table_block(tbl_lines)
            scenarios.extend(s_list)
            excluded.extend(ex_list)

        return scenarios, excluded, ranges

    def _process_table_block(self, tbl_lines: list[str]) -> tuple[list[ExtractedScenario], list[str]]:
        scenarios: list[ExtractedScenario] = []
        excluded: list[str] = []

        rows: list[list[str]] = []
        for line in tbl_lines:
            if re.match(r"^\|[\s\-:|]+\|$", line):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if any(cells):
                rows.append(cells)

        if not rows or len(rows) < 2:
            if rows:
                excluded.append(" | ".join(rows[0]))
            return scenarios, excluded

        header = [c.lower().strip() for c in rows[0]]
        col_map: dict[str, int] = {}
        for idx, col in enumerate(header):
            if any(k in col for k in ["tc id", "test id", "case id", "id", "#", "no."]):
                col_map["id"] = idx
            elif any(k in col for k in ["module", "feature", "component", "area"]):
                col_map["module"] = idx
            elif any(k in col for k in ["scenario", "test scenario", "test case", "title", "name", "description"]):
                col_map["scenario"] = idx
            elif any(k in col for k in ["steps", "data", "input", "action", "procedure", "payload"]):
                col_map["steps"] = idx
            elif any(k in col for k in ["expected", "result", "outcome", "response"]):
                col_map["expected"] = idx
            elif any(k in col for k in ["priority", "severity"]):
                col_map["priority"] = idx
            elif any(k in col for k in ["endpoint", "url", "path", "route", "api"]):
                col_map["endpoint"] = idx
            elif any(k in col for k in ["method", "verb"]):
                col_map["method"] = idx

        # If the table doesn't look like a testcase/scenario table (e.g. execution flow, preconditions table)
        is_scenario_table = any(k in col_map for k in ["scenario", "steps", "expected", "endpoint"])
        if not is_scenario_table:
            excluded.append(f"Table with columns: {', '.join(rows[0])}")
            for r in rows[1:]:
                excluded.append(" | ".join(r))
            return scenarios, excluded

        for r_idx, row in enumerate(rows[1:], 1):
            if not any(row):
                continue

            tc_id = row[col_map["id"]].strip() if "id" in col_map and col_map["id"] < len(row) else f"FT-{r_idx:03d}"
            module = row[col_map["module"]].strip() if "module" in col_map and col_map["module"] < len(row) else ""
            scenario_text = row[col_map["scenario"]].strip() if "scenario" in col_map and col_map["scenario"] < len(row) else ""
            steps_text = row[col_map["steps"]].strip() if "steps" in col_map and col_map["steps"] < len(row) else ""
            expected_text = row[col_map["expected"]].strip() if "expected" in col_map and col_map["expected"] < len(row) else ""
            priority_val = row[col_map["priority"]].strip().upper() if "priority" in col_map and col_map["priority"] < len(row) else "MEDIUM"
            endpoint_val = row[col_map["endpoint"]].strip() if "endpoint" in col_map and col_map["endpoint"] < len(row) else ""
            method_val = row[col_map["method"]].strip().upper() if "method" in col_map and col_map["method"] < len(row) else ""

            # Check if this row is non-scenario content (e.g. a category separator row)
            combined_row = " ".join([c for c in row if c]).strip()
            if not scenario_text and not steps_text and not endpoint_val:
                excluded.append(combined_row)
                continue

            # Construct raw_description (verbatim, lightly cleaned)
            parts = []
            if tc_id and not tc_id.startswith("FT-"):
                parts.append(f"[{tc_id}]")
            if module:
                parts.append(f"{module}:")
            if scenario_text:
                parts.append(scenario_text)
            if steps_text and steps_text != scenario_text:
                parts.append(f"- Steps: {steps_text}")
            if expected_text:
                parts.append(f"- Expected: {expected_text}")
            raw_desc = " ".join(parts).strip() or combined_row

            # Infer implied_subject, implied_type, hints
            parsed = self._parse_scenario_details(
                raw_description=raw_desc,
                module=module,
                scenario_text=scenario_text,
                steps_text=steps_text,
                expected_text=expected_text,
                endpoint_col=endpoint_val,
                method_col=method_val,
                priority_col=priority_val,
                tc_id=tc_id,
            )
            scenarios.append(parsed)

        return scenarios, excluded

    def _strip_consumed_ranges(self, text: str, ranges: list[tuple[int, int]]) -> str:
        if not ranges:
            return text
        sorted_ranges = sorted(ranges, key=lambda x: x[0])
        pieces = []
        last_end = 0
        for start, end in sorted_ranges:
            pieces.append(text[last_end:start])
            last_end = end
        pieces.append(text[last_end:])
        return "".join(pieces)

    def _extract_text_scenarios(self, text: str) -> tuple[list[ExtractedScenario], list[str]]:
        scenarios: list[ExtractedScenario] = []
        excluded: list[str] = []

        blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]

        for block in blocks:
            # Detect Non-Scenario content (Headers, Scope, Overview, Preconditions)
            if self._is_non_scenario_block(block):
                excluded.append(block)
                continue

            # Check for Gherkin scenario block
            if re.search(r"^\s*(?:Scenario|Scenario Outline):", block, re.MULTILINE | re.IGNORECASE):
                gherkin_scenarios = self._parse_gherkin_block(block)
                if gherkin_scenarios:
                    scenarios.extend(gherkin_scenarios)
                    continue

            # Check for numbered list of test cases e.g. "1. Verify ...", "Scenario 1: ..."
            list_scenarios = self._parse_numbered_or_bullet_block(block)
            if list_scenarios:
                scenarios.extend(list_scenarios)
                continue

            # Check for testable prose paragraph
            if self._is_testable_prose(block):
                parsed = self._parse_scenario_details(raw_description=block, scenario_text=block)
                scenarios.append(parsed)
            else:
                excluded.append(block)

        return scenarios, excluded

    def _is_non_scenario_block(self, block: str) -> bool:
        lower = block.lower()
        first_line = block.splitlines()[0].strip().lower()

        # Document headers / title sections
        if "functional testing document" in lower and len(block) < 300:
            return True
        if lower.startswith("# ") and any(k in lower for k in ["overview", "scope", "precondition", "introduction", "glossary", "architecture"]):
            return True

        # Numbered non-scenario sections e.g. "1. Document Overview", "2. Scope", "3. Preconditions"
        header_patterns = [
            r"^\d+\.\s*(?:document\s+overview|scope|preconditions?|execution\s+flow|environment|glossary|assumptions|evidence)",
            r"^(?:overview|scope|preconditions?|execution\s+flow|environment|glossary|assumptions|out\s+of\s+scope):",
        ]
        for pat in header_patterns:
            if re.search(pat, first_line, re.IGNORECASE):
                return True

        # Installation / build instruction blocks
        if any(lower.startswith(k) for k in ["1. clone repository", "2. verify java", "3. start/configure mysql", "4. run mvn"]):
            return True

        return False

    def _parse_gherkin_block(self, block: str) -> list[ExtractedScenario]:
        scenarios: list[ExtractedScenario] = []
        raw_scenarios = re.split(r"\n\s*(?=(?:Scenario|Scenario Outline):)", block, flags=re.IGNORECASE)
        for s in raw_scenarios:
            s_clean = s.strip()
            if not s_clean:
                continue
            parsed = self._parse_scenario_details(raw_description=s_clean, scenario_text=s_clean)
            scenarios.append(parsed)
        return scenarios

    def _parse_numbered_or_bullet_block(self, block: str) -> list[ExtractedScenario] | None:
        lines = block.splitlines()
        candidate_items = []
        for line in lines:
            line_str = line.strip()
            m = re.match(r"^(?:\d+[\.\)]|[-*•]|(?:Test\s*Case|Scenario|TC)\s*#?\d+:?)\s+(.+)", line_str, re.IGNORECASE)
            if m:
                candidate_items.append(line_str)

        if len(candidate_items) >= 2 or (len(candidate_items) == 1 and self._is_testable_prose(candidate_items[0])):
            extracted = []
            for item in candidate_items:
                parsed = self._parse_scenario_details(raw_description=item, scenario_text=item)
                extracted.append(parsed)
            return extracted
        return None

    def _is_testable_prose(self, block: str) -> bool:
        lower = block.lower()
        test_indicators = [
            "verify ", "validate ", "check ", "test that ", "ensure ", "should return",
            "should display", "should reject", "user should see", "click ", "navigate to ",
            "send get", "send post", "send put", "send delete", "http status", "expected result",
        ]
        return any(ind in lower for ind in test_indicators)

    def _parse_scenario_details(
        self,
        raw_description: str,
        module: str = "",
        scenario_text: str = "",
        steps_text: str = "",
        expected_text: str = "",
        endpoint_col: str = "",
        method_col: str = "",
        priority_col: str = "",
        tc_id: str = "",
    ) -> ExtractedScenario:
        combined = f"{raw_description} {steps_text} {expected_text} {endpoint_col}"

        # 1. Identify HTTP Method
        method = method_col.upper() if method_col else None
        if not method:
            m_match = re.search(r"\b(GET|POST|PUT|DELETE|PATCH)\b", f"{endpoint_col} {steps_text} {raw_description}", re.IGNORECASE)
            if m_match:
                method = m_match.group(1).upper()

        # 2. Identify Endpoint Path
        endpoint = endpoint_col.strip() if endpoint_col else None
        if endpoint and re.match(r"^(?:GET|POST|PUT|DELETE|PATCH)\s+", endpoint, re.IGNORECASE):
            parts = endpoint.split(None, 1)
            if not method:
                method = parts[0].upper()
            endpoint = parts[1].strip()

        if not endpoint:
            # Look for explicit HTTP path preceded by method, navigation, or /api/ /rest/
            m_ep = (
                re.search(r"\b(?:GET|POST|PUT|DELETE|PATCH)\s+(/[a-zA-Z0-9_\-/{}.?&=%]+)", combined, re.IGNORECASE)
                or re.search(r"(/(?:api|rest)/[a-zA-Z0-9_\-/{}.?&=%]+)", combined)
                or re.search(r"(?:navigate to|on route|view|page)\s+(['\"`]?)(/[a-zA-Z0-9_\-/]+)(\1)", combined, re.IGNORECASE)
            )
            if m_ep:
                # Group might be 1 or 2 depending on regex
                matched_val = m_ep.group(2) if m_ep.lastindex and m_ep.lastindex >= 2 and m_ep.group(2) else m_ep.group(1)
                endpoint = matched_val.rstrip(".")

        # 3. Identify Route Hint (for UI)
        route_hint = None
        if endpoint and not endpoint.startswith("/api/") and not endpoint.startswith("/rest/"):
            route_hint = endpoint
        else:
            route_match = re.search(r"(?:navigate to|on route|view|page)\s+(['\"`]?)(/[a-zA-Z0-9_\-/]+)(\1)", combined, re.IGNORECASE)
            if route_match:
                route_hint = route_match.group(2)

        # 4. Infer implied_type ("API" or "UI") strictly from the document's own language
        ui_keywords = [
            "user should see", "user sees", "clicking", "click the", "click on",
            "navigate to", "browser", "screen", "button", "dropdown", "modal",
            "renders", "table view", "form", "dialog", "ui", "page layout",
        ]
        api_keywords = [
            "endpoint", "http", "status code", "payload", "json", "request body",
            "response code", "200 ok", "201 created", "400 bad request", "404 not found",
            "rest api", "header", "get /", "post /", "put /", "delete /", "patch /",
        ]
        ui_score = sum(1 for k in ui_keywords if k in combined.lower())
        api_score = sum(1 for k in api_keywords if k in combined.lower())
        if endpoint and (endpoint.startswith("/api/") or endpoint.startswith("/rest/")):
            api_score += 2

        implied_type = "UI" if ui_score > api_score else "API"

        # 5. Determine implied_subject (literally stated or clearly implied by document wording)
        implied_subject = ""
        if endpoint:
            implied_subject = endpoint
        elif route_hint:
            implied_subject = route_hint
        elif module:
            implied_subject = module
        else:
            # Extract primary entity or subject noun
            ent_match = re.search(r"\b([A-Z][a-zA-Z0-9]+(?:Controller|Service|Form|List|Page|View)?)\b", raw_description)
            if ent_match and ent_match.group(1) not in ("Verify", "Test", "Validate", "Should", "Check", "Given", "When", "Then"):
                implied_subject = ent_match.group(1)
            else:
                implied_subject = scenario_text[:50].strip() or "General Feature"

        # 6. Extract field names mentioned in steps or description (filtering out sample values like EMP001)
        fields_mentioned = []
        field_patterns = [
            r"field\s+['\"`]?([a-zA-Z][a-zA-Z0-9_]+)['\"`]?",
            r"input\s+['\"`]?([a-zA-Z][a-zA-Z0-9_]+)['\"`]?",
            r"parameters?\s+['\"`]?([a-zA-Z][a-zA-Z0-9_]+)['\"`]?",
        ]
        for fp in field_patterns:
            for match in re.finditer(fp, combined, re.IGNORECASE):
                val = match.group(1).strip()
                # Exclude purely uppercase sample codes or keywords
                if not (val.isupper() and any(c.isdigit() for c in val)):
                    fields_mentioned.append(val)

        # 7. Extract action buttons mentioned
        actions_mentioned = []
        btn_match = re.findall(r"(?:click|press|submit|trigger)\s+['\"`]?([a-zA-Z0-9_\-\s]+?)['\"`]?\s+(?:button|link|icon|action)", combined, re.IGNORECASE)
        if btn_match:
            actions_mentioned.extend([b.strip() for b in btn_match])

        # 8. Expected status / result
        status_match = re.search(r"\b([1-5]\d{2})\b", expected_text + " " + combined)
        status_code = int(status_match.group(1)) if status_match else (201 if method == "POST" else 200)

        is_neg = (
            (status_code >= 400)
            or any(k in combined.lower() for k in ["invalid", "reject", "fail", "error", "missing", "unauthorized", "duplicate", "404", "400"])
        )
        prio = "HIGH" if "HIGH" in priority_col.upper() else ("LOW" if "LOW" in priority_col.upper() else "MEDIUM")

        return ExtractedScenario(
            id=tc_id,
            raw_description=raw_description.strip(),
            implied_subject=implied_subject.strip(),
            implied_type=implied_type,
            method_hint=method,
            endpoint_hint=endpoint,
            route_hint=route_hint,
            fields_mentioned=list(set(fields_mentioned)),
            actions_mentioned=list(set(actions_mentioned)),
            expected_result=expected_text.strip() or "Operation completes with expected status code or visual feedback",
            expected_status_hint=status_code,
            is_negative=is_neg,
            priority=prio,
            raw_context={"module": module, "scenario": scenario_text, "steps": steps_text},
        )

    # ═════════════════════════════════════════════════════════════════════
    # STAGE 2 — GROUND EACH SCENARIO AGAINST REPOSITORY EVIDENCE
    # ═════════════════════════════════════════════════════════════════════

    def ground_scenario(
        self, scenario: ExtractedScenario, evidence: dict[str, Any]
    ) -> tuple[GroundingStatus, dict[str, Any]]:
        """Compares actual evidence content against scenario details.

        Returns:
          (MATCHED, {"matched_evidence": ..., "target": ...})
          (PARTIALLY_MATCHED, {"matched_evidence": ..., "missing_detail": ...})
          (UNMATCHED, {"reason": ...})
        """
        api_endpoints = evidence.get("endpoints", [])
        ui_routes = evidence.get("ui_workflows", [])
        entities = evidence.get("entities", [])
        controllers = evidence.get("controllers", [])
        services = evidence.get("services", [])

        if scenario.implied_type == "API":
            return self._ground_api_scenario(scenario, api_endpoints, entities, controllers, services)
        else:
            return self._ground_ui_scenario(scenario, ui_routes, entities)

    def _ground_api_scenario(
        self,
        scenario: ExtractedScenario,
        api_endpoints: list[dict[str, Any]],
        entities: list[dict[str, Any]],
        controllers: list[dict[str, Any]],
        services: list[dict[str, Any]],
    ) -> tuple[GroundingStatus, dict[str, Any]]:
        target_path = scenario.endpoint_hint or (scenario.implied_subject if scenario.implied_subject.startswith("/") else None)
        norm_target = _normalize_path(target_path) if target_path else None
        method = scenario.method_hint.upper() if scenario.method_hint else None

        # Build index of normalized endpoints in repository
        ep_by_norm: dict[str, list[dict[str, Any]]] = {}
        for ep in api_endpoints:
            ep_path = ep.get("endpoint", "")
            np = _normalize_path(ep_path)
            ep_by_norm.setdefault(np, []).append(ep)

        # 1. Exact or normalized endpoint path match
        matched_endpoints = ep_by_norm.get(norm_target, []) if norm_target else []

        if not matched_endpoints and norm_target:
            # Check parameterized match e.g. /api/employees/emp/{*} vs /api/employees/{*}
            for np, eps in ep_by_norm.items():
                if norm_target == np or norm_target.replace("{*}", "").rstrip("/") == np.replace("{*}", "").rstrip("/"):
                    matched_endpoints = eps
                    break

        if not matched_endpoints and target_path:
            # Check parameterized match by segment e.g. /api/employees/emp/EMP001 matching /api/employees/emp/{employeeId}
            d_segs = [s for s in target_path.strip("/").split("/") if s]
            for ep in api_endpoints:
                raw_ep = ep.get("endpoint", "")
                e_segs = [s for s in raw_ep.strip("/").split("/") if s]
                if len(d_segs) == len(e_segs):
                    seg_match = True
                    for d, e in zip(d_segs, e_segs):
                        if (e.startswith("{") and e.endswith("}")) or e == "{*}":
                            continue
                        if d.lower() != e.lower():
                            seg_match = False
                            break
                    if seg_match:
                        matched_endpoints.append(ep)

        if matched_endpoints:
            # Check HTTP Method
            if method:
                ep_with_method = next((e for e in matched_endpoints if e.get("method", "GET").upper() == method), None)
                if not ep_with_method:
                    avail_methods = [e.get("method", "GET").upper() for e in matched_endpoints]
                    ep_any = matched_endpoints[0]
                    return GroundingStatus.PARTIALLY_MATCHED, {
                        "matched_evidence": f"Endpoint '{ep_any.get('endpoint')}' in {ep_any.get('class_name', 'Controller')}",
                        "missing_detail": f"HTTP method '{method}' is not supported on endpoint '{ep_any.get('endpoint')}' (available: {', '.join(avail_methods)})",
                    }
                matched_ep = ep_with_method
            else:
                matched_ep = matched_endpoints[0]

            # Check specific fields mentioned in scenario
            missing_fields = self._check_missing_fields_for_endpoint(scenario.fields_mentioned, matched_ep, entities)
            if missing_fields:
                return GroundingStatus.PARTIALLY_MATCHED, {
                    "matched_evidence": f"Endpoint: {matched_ep.get('method', 'GET')} {matched_ep.get('endpoint')} in {matched_ep.get('class_name', 'Controller')}",
                    "missing_detail": f"Fields {missing_fields} mentioned in scenario are not declared on entity or endpoint parameters in repository evidence",
                }

            return GroundingStatus.MATCHED, {
                "matched_evidence": f"Endpoint: {matched_ep.get('method', 'GET')} {matched_ep.get('endpoint')} in {matched_ep.get('class_name', 'Controller')}",
                "target": matched_ep,
            }

        # 2. Path didn't match directly — check if the entity/subject exists in the repository
        subject_lower = scenario.implied_subject.lower()
        matched_entity = next((e for e in entities if e.get("name", "").lower() in subject_lower or subject_lower in e.get("name", "").lower()), None)
        matched_ctrl = next((c for c in controllers if c.get("name", "").lower() in subject_lower or subject_lower in c.get("name", "").lower()), None)
        matched_svc = next((s for s in services if s.get("name", "").lower() in subject_lower or subject_lower in s.get("name", "").lower()), None)

        if matched_entity or matched_ctrl or matched_svc:
            found_desc = (matched_ctrl or matched_svc or matched_entity).get("name")
            return GroundingStatus.PARTIALLY_MATCHED, {
                "matched_evidence": f"Entity / Controller '{found_desc}' exists in repository evidence",
                "missing_detail": f"Endpoint path '{target_path or scenario.implied_subject}' is not declared in repository code",
            }

        # 3. No matching endpoint, controller, service, or entity anywhere in repository
        return GroundingStatus.UNMATCHED, {
            "reason": f"No endpoint, controller, or entity matching '{target_path or scenario.implied_subject}' exists in repository evidence.",
        }

    def _ground_ui_scenario(
        self,
        scenario: ExtractedScenario,
        ui_routes: list[dict[str, Any]],
        entities: list[dict[str, Any]],
    ) -> tuple[GroundingStatus, dict[str, Any]]:
        target_route = scenario.route_hint or (scenario.implied_subject if scenario.implied_subject.startswith("/") else None)
        norm_route = _normalize_path(target_route) if target_route else None
        subject_lower = scenario.implied_subject.lower()

        # Find matching UI route in repository evidence
        matched_ui = None
        for ui in ui_routes:
            ui_r = ui.get("route", "")
            if norm_route and _normalize_path(ui_r) == norm_route:
                matched_ui = ui
                break
            ui_name = ui.get("name", "").lower()
            if ui_name and (ui_name in subject_lower or subject_lower in ui_name):
                matched_ui = ui
                break

        if matched_ui:
            grounded_sels = matched_ui.get("grounded_selectors", [])
            inp_fields = [f.get("name", "").lower() for f in matched_ui.get("input_fields", []) if f.get("name")]

            # Check specific fields mentioned in scenario
            missing_fields = []
            for f in scenario.fields_mentioned:
                f_clean = f.lower()
                if inp_fields and f_clean not in inp_fields and not any(f_clean in s.lower() for s in grounded_sels):
                    missing_fields.append(f)

            if missing_fields:
                return GroundingStatus.PARTIALLY_MATCHED, {
                    "matched_evidence": f"UI Route '{matched_ui.get('route')}' ({matched_ui.get('name')})",
                    "missing_detail": f"Input fields {missing_fields} not found on route '{matched_ui.get('route')}'",
                }

            # Check specific action buttons mentioned
            missing_actions = []
            for act in scenario.actions_mentioned:
                act_lower = act.lower()
                if grounded_sels and not any(act_lower in s.lower() for s in grounded_sels):
                    missing_actions.append(act)

            if missing_actions:
                return GroundingStatus.PARTIALLY_MATCHED, {
                    "matched_evidence": f"UI Route '{matched_ui.get('route')}' ({matched_ui.get('name')})",
                    "missing_detail": f"Action button / control {missing_actions} not found in selectors for route '{matched_ui.get('route')}'",
                }

            return GroundingStatus.MATCHED, {
                "matched_evidence": f"UI Route: {matched_ui.get('route')} in {matched_ui.get('file', matched_ui.get('name'))}",
                "target": matched_ui,
            }

        # Check if backend entity exists but UI route does not
        matched_ent = next((e for e in entities if e.get("name", "").lower() in subject_lower), None)
        if matched_ent:
            return GroundingStatus.PARTIALLY_MATCHED, {
                "matched_evidence": f"Backend entity '{matched_ent.get('name')}' exists in repository evidence",
                "missing_detail": f"No navigable frontend route exists for '{target_route or scenario.implied_subject}'",
            }

        return GroundingStatus.UNMATCHED, {
            "reason": f"No UI route, page component, or feature matching '{target_route or scenario.implied_subject}' exists in repository evidence.",
        }

    def _check_missing_fields_for_endpoint(
        self,
        fields_mentioned: list[str],
        endpoint: dict[str, Any],
        entities: list[dict[str, Any]],
    ) -> list[str]:
        if not fields_mentioned:
            return []

        known_fields: set[str] = set()
        # From request body sample
        req_sample = endpoint.get("request_body_sample")
        if isinstance(req_sample, dict):
            known_fields.update(k.lower() for k in req_sample.keys())

        # From parameters
        for p in endpoint.get("parameters", []):
            if isinstance(p, dict):
                pname = p.get("name") or p.get("parameter_name")
                if pname:
                    known_fields.add(pname.lower())
            elif isinstance(p, str):
                known_fields.add(p.lower())

        # From entities
        for ent in entities:
            for f in ent.get("fields", []):
                fname = f.get("name") if isinstance(f, dict) else str(f)
                if fname:
                    known_fields.add(fname.lower())

        if not known_fields:
            return []

        missing = []
        for f in fields_mentioned:
            if f.lower() not in known_fields and not any(f.lower() in k for k in known_fields):
                missing.append(f)
        return missing

    # ═════════════════════════════════════════════════════════════════════
    # STAGE 3 — DECIDE WHAT BECOMES AN EXECUTABLE TESTCASE & DEDUPLICATE
    # ═════════════════════════════════════════════════════════════════════

    def generate_grounded_testcase(
        self,
        scenario: ExtractedScenario,
        match_details: dict[str, Any],
        test_idx: int,
        document_id: str = "Functional_Testing_Document",
    ) -> ProposedTestCase:
        test_id = f"PTC-DOC-{test_idx:03d}"
        target = match_details.get("target", {})
        evidence_str = match_details.get("matched_evidence", "Repository evidence")

        priority_enum = (
            ProposedTestPriority.HIGH
            if scenario.priority == "HIGH"
            else (ProposedTestPriority.LOW if scenario.priority == "LOW" else ProposedTestPriority.MEDIUM)
        )

        if scenario.implied_type == "API":
            endpoint = target.get("endpoint", scenario.endpoint_hint or "/api")
            method = target.get("method", scenario.method_hint or "GET").upper()
            status_code = scenario.expected_status_hint or (201 if method == "POST" else 200)

            body = target.get("request_body_sample") if method in ("POST", "PUT", "PATCH") else None
            api_spec = ApiTestSpec(
                method=method,
                endpoint=endpoint,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                request_body=body or {},
                expected_status=status_code,
                assertions=[f"status == {status_code}"],
            )
            meta = TestCaseMetadata(
                test_id=test_id,
                endpoint=endpoint,
                method=method,
                parameters={},
                expected_status=status_code,
                expected_status_source=evidence_str,
                authentication_required=False,
                authentication_source="Default session or public",
                selector=None,
                selector_source=None,
                evidence=[evidence_str],
                dependencies=[],
                confidence=1.0,
                validation_status=ValidationStatus.VALID,
            )
            return ProposedTestCase(
                id=test_id,
                title=f"Verify {method} {endpoint} - {scenario.raw_description[:60]}",
                description=scenario.raw_description,
                type=ProposedTestType.API,
                priority=priority_enum,
                source="functional_testing_document",
                reason=f"Derived from grounded Functional Testing Document scenario matched to {evidence_str}.",
                preconditions=["Application is running and reachable"],
                test_data={"endpoint": endpoint, "method": method},
                steps=[f"Send {method} request to {endpoint}", f"Verify HTTP status {status_code}"],
                expected_result=scenario.expected_result,
                status=ProposedTestStatus.PROPOSED,
                generation_source="FUNCTIONAL_DOC",
                document_id=document_id,
                source_reference=f"{document_id}: {scenario.raw_description[:80]}",
                metadata=meta,
                api_spec=api_spec,
            )
        else:
            route = target.get("route", scenario.route_hint or "/")
            ui_sels = target.get("grounded_selectors", ["h1, h2, form, table, nav, div"])
            primary_sel = ui_sels[0] if ui_sels else "body"

            ui_spec = UiTestSpec(
                target_route=route,
                actions=target.get("actions", ["navigate", "screenshot"]),
                input_fields=target.get("input_fields", []),
                expected_elements=ui_sels[:2],
                assertions=[f"expect(page.locator('{primary_sel}')).toBeVisible()"],
            )
            meta = TestCaseMetadata(
                test_id=test_id,
                endpoint=route,
                method="GET",
                parameters={},
                expected_status=200,
                expected_status_source=evidence_str,
                authentication_required=False,
                authentication_source="Public or active session",
                selector=primary_sel,
                selector_source=f"{evidence_str}: primary selector {primary_sel}",
                evidence=[evidence_str],
                dependencies=[],
                confidence=1.0,
                validation_status=ValidationStatus.VALID,
            )
            return ProposedTestCase(
                id=test_id,
                title=f"Playwright UI: {scenario.raw_description[:60]}",
                description=scenario.raw_description,
                type=ProposedTestType.UI,
                priority=priority_enum,
                source="functional_testing_document",
                reason=f"Derived from grounded Functional Testing Document scenario matched to {evidence_str}.",
                preconditions=["Application and frontend are running"],
                test_data={"route": route},
                steps=[f"Navigate to '{route}' in browser", f"Assert '{primary_sel}' is visible", "Capture screenshot evidence"],
                expected_result=scenario.expected_result,
                status=ProposedTestStatus.PROPOSED,
                generation_source="FUNCTIONAL_DOC",
                document_id=document_id,
                source_reference=f"{document_id}: {scenario.raw_description[:80]}",
                metadata=meta,
                ui_spec=ui_spec,
            )

    def is_duplicate_of_existing(
        self,
        candidate: ProposedTestCase,
        existing_inventory: list[ProposedTestCase] | None,
    ) -> str | None:
        """Checks if an existing testcase in the inventory already exercises the same target + intent."""
        if not existing_inventory:
            return None

        c_meta = candidate.metadata
        if not c_meta:
            return None

        c_endpoint = _normalize_path(c_meta.endpoint)
        c_method = c_meta.method.upper()
        c_status = c_meta.expected_status

        for ex in existing_inventory:
            ex_meta = ex.metadata
            if not ex_meta:
                continue

            ex_endpoint = _normalize_path(ex_meta.endpoint)
            ex_method = ex_meta.method.upper()
            ex_status = ex_meta.expected_status

            if ex_endpoint == c_endpoint and ex_method == c_method and ex_status == c_status:
                return ex.id

        return None

    # ═════════════════════════════════════════════════════════════════════
    # ORCHESTRATOR
    # ═════════════════════════════════════════════════════════════════════

    def process(
        self,
        document_text: str,
        evidence: dict[str, Any],
        existing_inventory: list[ProposedTestCase] | None = None,
        document_name: str = "Functional_Testing_Document.docx",
        log_fn: Callable[[str], None] | None = None,
        _extraction_already_logged: bool = False,
    ) -> dict[str, Any]:
        """Executes Stage 1, Stage 2, and Stage 3, producing the standardized output report."""
        extracted_char_count = len(document_text) if document_text else 0

        if log_fn and not _extraction_already_logged:
            if extracted_char_count > 0:
                log_fn(f"[PROPOSED TESTS] Document text extraction: {extracted_char_count} characters extracted")
            else:
                log_fn("[PROPOSED TESTS] Document text extraction: 0 characters extracted (extraction failed or file is empty/unsupported)")

        # Stage 1: Extraction
        extracted_scenarios, non_scenario_content_excluded = self.extract_scenarios(document_text)
        scenario_count = len(extracted_scenarios)

        if log_fn:
            if scenario_count > 0:
                log_fn(f"[PROPOSED TESTS] Scenarios parsed from document: {scenario_count}")
            elif extracted_char_count == 0:
                log_fn("[PROPOSED TESTS] Scenarios parsed from document: 0 (extraction produced 0 characters)")
            else:
                log_fn("[PROPOSED TESTS] Scenarios parsed from document: 0 (characters were extracted but no scenario-like content was found within them)")

        # Stage 2: Repository evidence available for matching
        api_endpoint_count = len(evidence.get("endpoints", []))
        ui_route_count = len(evidence.get("ui_workflows", []))
        entity_count = len(evidence.get("entities", []))
        if log_fn:
            log_fn(
                f"[PROPOSED TESTS] Repository evidence available for matching: "
                f"{api_endpoint_count} API endpoints, {ui_route_count} UI routes, {entity_count} entities"
            )

        matched: list[dict[str, Any]] = []
        partially_matched: list[dict[str, Any]] = []
        unmatched: list[dict[str, Any]] = []
        skipped_as_duplicate_of_existing: list[dict[str, Any]] = []

        test_counter = 1

        # Stage 2 & 3: Grounding and Decision
        for sc in extracted_scenarios:
            status, details = self.ground_scenario(sc, evidence)

            if status == GroundingStatus.MATCHED:
                # Generate full testcase
                testcase = self.generate_grounded_testcase(sc, details, test_counter, document_id=document_name)
                # Deduplication check against existing inventory
                duplicate_id = self.is_duplicate_of_existing(testcase, existing_inventory)
                if duplicate_id:
                    skipped_as_duplicate_of_existing.append({
                        "raw_description": sc.raw_description,
                        "duplicate_of_id": duplicate_id,
                    })
                else:
                    matched.append({
                        "raw_description": sc.raw_description,
                        "generated_testcase": testcase.model_dump(),
                    })
                    test_counter += 1

            elif status == GroundingStatus.PARTIALLY_MATCHED:
                partially_matched.append({
                    "raw_description": sc.raw_description,
                    "matched_evidence": details.get("matched_evidence", ""),
                    "missing_detail": details.get("missing_detail", ""),
                })

            else:  # UNMATCHED
                unmatched.append({
                    "raw_description": sc.raw_description,
                    "reason": details.get("reason", "No corresponding evidence found in repository"),
                })

        if log_fn:
            log_fn(
                f"[PROPOSED TESTS] Scenario matching results: {len(matched)} matched, "
                f"{len(partially_matched)} partially matched, {len(unmatched)} unmatched, "
                f"{len(non_scenario_content_excluded)} excluded as non-scenario content"
            )

            # Log each UNMATCHED and PARTIALLY_MATCHED scenario with reason
            for pm in partially_matched:
                raw_desc = (pm.get("raw_description") or "").replace("\n", " ").strip()[:80]
                reason = pm.get("missing_detail") or pm.get("matched_evidence") or "partially matched with missing details"
                log_fn(f'[PROPOSED TESTS]   - "{raw_desc}" -> PARTIALLY_MATCHED: {reason}')

            for um in unmatched:
                raw_desc = (um.get("raw_description") or "").replace("\n", " ").strip()[:80]
                reason = um.get("reason") or "no corresponding evidence found in repository"
                log_fn(f'[PROPOSED TESTS]   - "{raw_desc}" -> UNMATCHED: {reason}')

        return {
            "scenarios_extracted": len(extracted_scenarios),
            "matched": matched,
            "partially_matched": partially_matched,
            "unmatched": unmatched,
            "non_scenario_content_excluded": non_scenario_content_excluded,
            "skipped_as_duplicate_of_existing": skipped_as_duplicate_of_existing,
        }

    def process_file(
        self,
        file_path: Path | str,
        evidence: dict[str, Any],
        existing_inventory: list[ProposedTestCase] | None = None,
        log_fn: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Extracts text from file and processes it against repository evidence."""
        p = Path(file_path)
        file_size_kb = round(p.stat().st_size / 1024, 1) if p.exists() else 0.0
        if log_fn:
            log_fn(f"[PROPOSED TESTS] Functional document detected: {p.name}, {file_size_kb} KB")

        from app.application.use_cases.proposed_tests.brd_analyzer import BrdAnalyzer
        analyzer = BrdAnalyzer(p)
        try:
            text = analyzer._extract_raw_text()
        except Exception as ext_err:
            logger.warning(f"Failed to extract text from {p.name}: {ext_err}")
            text = ""

        extracted_char_count = len(text) if text else 0
        if log_fn:
            if extracted_char_count > 0:
                log_fn(f"[PROPOSED TESTS] Document text extraction: {extracted_char_count} characters extracted")
            else:
                log_fn("[PROPOSED TESTS] Document text extraction: 0 characters extracted (extraction failed or file is empty/unsupported)")

        return self.process(
            document_text=text,
            evidence=evidence,
            existing_inventory=existing_inventory,
            document_name=p.name,
            log_fn=log_fn,
            _extraction_already_logged=True,
        )
