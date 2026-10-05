"""Analyzer and parser for Business Requirements Documents (BRD) and Functional Testing Documents."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domain.models.brd_models import (
    BrdExtractionResult,
    BrdRequirement,
    BrdWorkflow,
    BrdWorkflowStep,
)

logger = logging.getLogger(__name__)


class BrdAnalyzer:
    """Extracts business requirements, user journeys, workflows, and testable criteria from BRD and Functional Testing documents."""

    def __init__(self, file_path: Path, job_id: str = "") -> None:
        self.file_path = Path(file_path)
        self.job_id = job_id
        self.structured_tables: list[list[list[str]]] = []

    def extract(self) -> BrdExtractionResult:
        """Parses the document and extracts structured business workflows and requirements."""
        filename = self.file_path.name
        self.structured_tables = []
        if not self.file_path.exists():
            return BrdExtractionResult(
                job_id=self.job_id,
                filename=filename,
                error=f"File not found: {self.file_path}",
            )

        try:
            raw_text = self._extract_raw_text()
            if not raw_text.strip():
                return BrdExtractionResult(
                    job_id=self.job_id,
                    filename=filename,
                    error="BRD or Functional Testing document appears empty or unreadable.",
                )

            requirements = self._extract_requirements(raw_text)
            workflows = self._extract_workflows(raw_text, requirements)

            return BrdExtractionResult(
                job_id=self.job_id,
                filename=filename,
                raw_text_length=len(raw_text),
                workflows=workflows,
                requirements=requirements,
                parsed_at=datetime.now(timezone.utc).isoformat(),
            )

        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to parse document {filename}: {e}")
            return BrdExtractionResult(
                job_id=self.job_id,
                filename=filename,
                error=f"Document parsing failed: {e}",
            )

    def _extract_raw_text(self) -> str:
        ext = self.file_path.suffix.lower()

        if ext in [".txt", ".md"]:
            content = self.file_path.read_text(encoding="utf-8", errors="replace")
            self._parse_markdown_tables(content)
            return content

        if ext == ".docx":
            return self._extract_docx_text()

        if ext == ".xlsx":
            return self._extract_xlsx_text()

        if ext == ".xls":
            return self._extract_xls_text()

        if ext == ".pdf":
            return self._extract_pdf_text()

        # Fallback for plain text or unknown
        try:
            content = self.file_path.read_text(encoding="utf-8", errors="replace")
            self._parse_markdown_tables(content)
            return content
        except Exception:  # noqa: BLE001
            return ""

    def _parse_markdown_tables(self, text: str) -> None:
        """Parses any markdown pipe tables in text into structured_tables."""
        lines = [l.strip() for l in text.splitlines()]
        current_tbl: list[list[str]] = []
        for line in lines:
            if line.startswith("|") and line.endswith("|"):
                # Skip markdown separator row like |---|---|
                if re.match(r"^\|[\s\-:|]+\|$", line):
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                if any(cells):
                    current_tbl.append(cells)
            else:
                if len(current_tbl) >= 2:
                    self.structured_tables.append(current_tbl)
                current_tbl = []
        if len(current_tbl) >= 2:
            self.structured_tables.append(current_tbl)

    def _extract_docx_text(self) -> str:
        """Extracts complete text and tabular structures from a DOCX file in document order."""
        try:
            with zipfile.ZipFile(self.file_path, "r") as docx_zip:
                if "word/document.xml" not in docx_zip.namelist():
                    return ""
                xml_bytes = docx_zip.read("word/document.xml")

                try:
                    import defusedxml.ElementTree as ET
                    tree = ET.fromstring(xml_bytes)
                except Exception:  # noqa: BLE001
                    import xml.etree.ElementTree as ET
                    tree = ET.fromstring(xml_bytes)

                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                body = tree.find("w:body", ns)
                if body is None:
                    body = next((c for c in tree.iter() if c.tag.endswith("body")), None)

                if body is None:
                    xml_content = xml_bytes.decode("utf-8", errors="replace")
                    paragraphs = re.findall(r"<w:p\b[^>]*>(.*?)</w:p>", xml_content, re.DOTALL)
                    lines = ["".join(re.findall(r"<w:t\b[^>]*>([^<]*)</w:t>", p)).strip() for p in paragraphs]
                    return "\n\n".join([l for l in lines if l])

                extracted_lines: list[str] = []
                for child in body:
                    tag = child.tag.split("}")[-1]
                    if tag == "p":
                        text_parts = [t.text for t in child.iter() if t.tag.endswith("t") and t.text]
                        line = "".join(text_parts).strip()
                        if line:
                            extracted_lines.append(line)
                    elif tag == "tbl":
                        tbl_rows: list[list[str]] = []
                        for r in child.iter():
                            if not r.tag.endswith("tr"):
                                continue
                            row_cells: list[str] = []
                            for c in r.iter():
                                if not c.tag.endswith("tc"):
                                    continue
                                text_parts = [t.text for t in c.iter() if t.tag.endswith("t") and t.text]
                                cell_val = " ".join("".join(text_parts).split()).strip()
                                row_cells.append(cell_val)
                            if any(row_cells):
                                tbl_rows.append(row_cells)

                        if tbl_rows:
                            self.structured_tables.append(tbl_rows)
                            header_row = tbl_rows[0]
                            extracted_lines.append("| " + " | ".join(header_row) + " |")
                            extracted_lines.append("| " + " | ".join(["---"] * len(header_row)) + " |")
                            for r in tbl_rows[1:]:
                                extracted_lines.append("| " + " | ".join(r) + " |")

                return "\n\n".join(extracted_lines)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to extract text from docx: {e}")
            return ""

    def _extract_xlsx_text(self) -> str:
        try:
            with zipfile.ZipFile(self.file_path, "r") as xlsx_zip:
                namelist = set(xlsx_zip.namelist())

                # 1. Parse shared strings table (xl/sharedStrings.xml)
                shared_strings: list[str] = []
                if "xl/sharedStrings.xml" in namelist:
                    try:
                        import defusedxml.ElementTree as ET
                        ss_tree = ET.fromstring(xlsx_zip.read("xl/sharedStrings.xml"))
                        for si in ss_tree:
                            text_pieces = []
                            for el in si.iter():
                                if el.tag.endswith("t") and el.text:
                                    text_pieces.append(el.text)
                            shared_strings.append("".join(text_pieces))
                    except Exception as ss_err:  # noqa: BLE001
                        logger.warning(f"Error parsing sharedStrings.xml: {ss_err}")

                # 2. Parse workbook structure to map sheet IDs to names (xl/workbook.xml)
                sheet_names: dict[str, str] = {}
                if "xl/workbook.xml" in namelist:
                    try:
                        import defusedxml.ElementTree as ET
                        wb_tree = ET.fromstring(xlsx_zip.read("xl/workbook.xml"))
                        for sheet_el in wb_tree.iter():
                            if sheet_el.tag.endswith("sheet"):
                                s_name = sheet_el.get("name", "")
                                s_id = sheet_el.get("sheetId", "")
                                r_id = sheet_el.get(
                                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id",
                                    "",
                                )
                                if s_name:
                                    if s_id:
                                        sheet_names[f"sheet{s_id}"] = s_name
                                    if r_id:
                                        sheet_names[r_id] = s_name
                    except Exception as wb_err:  # noqa: BLE001
                        logger.warning(f"Error parsing workbook.xml: {wb_err}")

                # 3. Find and sort all worksheet files (xl/worksheets/sheet*.xml)
                sheet_files = [
                    f
                    for f in xlsx_zip.namelist()
                    if f.startswith("xl/worksheets/sheet") and f.endswith(".xml")
                ]

                def _sheet_sort_key(name: str) -> int:
                    m = re.search(r"sheet(\d+)\.xml", name)
                    return int(m.group(1)) if m else 999

                sheet_files.sort(key=_sheet_sort_key)
                extracted_sections: list[str] = []

                for sheet_file in sheet_files:
                    try:
                        import defusedxml.ElementTree as ET
                        sheet_stem = Path(sheet_file).stem
                        display_name = sheet_names.get(sheet_stem, sheet_stem.capitalize())

                        sheet_tree = ET.fromstring(xlsx_zip.read(sheet_file))
                        sheet_rows: list[str] = []
                        sheet_rows_raw: list[list[str]] = []

                        for row_el in sheet_tree.iter():
                            if not row_el.tag.endswith("row"):
                                continue

                            row_cells: list[str] = []
                            for c_el in row_el.iter():
                                if not c_el.tag.endswith("c"):
                                    continue

                                cell_type = c_el.get("t", "")
                                val = ""

                                if cell_type == "s":
                                    v_el = next((x for x in c_el if x.tag.endswith("v")), None)
                                    if v_el is not None and v_el.text and v_el.text.isdigit():
                                        idx = int(v_el.text)
                                        if 0 <= idx < len(shared_strings):
                                            val = shared_strings[idx]
                                elif cell_type == "inlineStr":
                                    val = "".join(
                                        x.text or "" for x in c_el.iter() if x.tag.endswith("t")
                                    )
                                else:
                                    v_el = next((x for x in c_el if x.tag.endswith("v")), None)
                                    if v_el is not None and v_el.text:
                                        val = v_el.text

                                clean_val = val.strip()
                                row_cells.append(clean_val)

                            if any(row_cells):
                                sheet_rows.append(" | ".join(row_cells))
                                sheet_rows_raw.append(row_cells)

                        if sheet_rows_raw:
                            self.structured_tables.append(sheet_rows_raw)

                        if sheet_rows:
                            sheet_content = f"### Sheet: {display_name}\n" + "\n".join(sheet_rows)
                            extracted_sections.append(sheet_content)
                    except Exception as s_err:  # noqa: BLE001
                        logger.warning(f"Error parsing worksheet {sheet_file}: {s_err}")

                return "\n\n".join(extracted_sections)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to extract text from xlsx: {e}")
            return ""

    def _extract_xls_text(self) -> str:
        try:
            raw_bytes = self.file_path.read_bytes()
            if b"<?xml" in raw_bytes[:100] or b"<Workbook" in raw_bytes[:500]:
                text_content = raw_bytes.decode("utf-8", errors="replace")
                import defusedxml.ElementTree as ET

                wb_tree = ET.fromstring(text_content)
                sheets_extracted: list[str] = []
                for ws in wb_tree.iter():
                    if ws.tag.endswith("Worksheet"):
                        s_name = ws.get(
                            "{urn:schemas-microsoft-com:office:spreadsheet}Name", "Sheet"
                        )
                        rows_list = []
                        sheet_rows_raw: list[list[str]] = []
                        for row in ws.iter():
                            if row.tag.endswith("Row"):
                                cells = []
                                for cell in row.iter():
                                    if cell.tag.endswith("Data") and cell.text:
                                        cells.append(cell.text.strip())
                                if any(cells):
                                    rows_list.append(" | ".join(cells))
                                    sheet_rows_raw.append(cells)
                        if sheet_rows_raw:
                            self.structured_tables.append(sheet_rows_raw)
                        if rows_list:
                            sheets_extracted.append(f"### Sheet: {s_name}\n" + "\n".join(rows_list))
                if sheets_extracted:
                    return "\n\n".join(sheets_extracted)

            ascii_strings = re.findall(rb"[\x20-\x7E\t\r\n]{4,}", raw_bytes)
            decoded_lines = []
            for s in ascii_strings:
                try:
                    dec = s.decode("utf-8", errors="ignore").strip()
                    if (
                        dec
                        and len(dec) >= 3
                        and not dec.startswith("Font")
                        and not dec.startswith("Style")
                    ):
                        decoded_lines.append(dec)
                except Exception:  # noqa: BLE001
                    pass  # nosec B110

            return "\n\n".join(decoded_lines)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to extract text from xls: {e}")
            return ""

    def _extract_pdf_text(self) -> str:
        try:
            import pypdf
            reader = pypdf.PdfReader(str(self.file_path))
            pages_text = []
            for _idx, page in enumerate(reader.pages):
                txt = page.extract_text() or ""
                if txt.strip():
                    pages_text.append(txt.strip())
                    self._parse_markdown_tables(txt)
            return "\n\n".join(pages_text)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"pypdf extraction failed or not available: {e}")
            try:
                raw_bytes = self.file_path.read_bytes()
                matches = re.findall(rb"\(([\w\s.,!?;:/\-_#@%&*+=()]+)\)\s*Tj", raw_bytes)
                if matches:
                    return " ".join(m.decode("utf-8", errors="ignore") for m in matches)
            except Exception:  # noqa: BLE001
                pass  # nosec B110
            return ""

    @staticmethod
    def _normalize_endpoint_path(ep: str | None) -> str:
        if not ep:
            return ""
        ep = re.sub(r"^(?:GET|POST|PUT|DELETE|PATCH)\s+", "", ep.strip(), flags=re.IGNORECASE)
        ep = ep.split("?")[0].rstrip(".")
        ep = re.sub(r"\{[^}]+\}", "{var}", ep)
        ep = re.sub(r"/(emp|department|designation|employee|date|month|year|id)/[^/]+", r"/\1/{var}", ep, flags=re.IGNORECASE)
        ep = re.sub(r"/\d+", "/{var}", ep)
        return ep.lower().rstrip("/")

    def _extract_scenarios_from_tables(self) -> list[BrdWorkflow]:
        """Extracts functional test scenarios from structured tables with column awareness."""
        workflows: list[BrdWorkflow] = []
        seen_names: set[str] = set()

        scenario_tables: list[list[list[str]]] = []
        endpoint_tables: list[list[list[str]]] = []

        for tbl in self.structured_tables:
            if len(tbl) < 2:
                continue
            header = [c.lower().strip() for c in tbl[0]]
            has_scenario = any(
                k in col
                for col in header
                for k in ["scenario", "test scenario", "test case", "testcase", "tc id", "test id", "case id"]
            )
            if has_scenario:
                scenario_tables.append(tbl)
            else:
                has_ep = any(k in col for col in header for k in ["endpoint", "url", "path", "route", "api"])
                if has_ep:
                    endpoint_tables.append(tbl)
                elif len(tbl[0]) >= 3:
                    scenario_tables.append(tbl)

        # 1. Process explicit scenario tables
        for tbl_idx, tbl in enumerate(scenario_tables):
            header = [c.lower().strip() for c in tbl[0]]
            col_map: dict[str, int] = {}
            for i, col in enumerate(header):
                if any(k == col or k in col for k in ["tc id", "test id", "case id", "tc_id", "test_id", "id", "#", "test case id", "testcase id", "no."]):
                    col_map["id"] = i
                elif any(k == col or k in col for k in ["module", "feature", "component", "category", "domain", "service"]):
                    col_map["module"] = i
                elif any(k == col or k in col for k in ["scenario", "test scenario", "test case", "title", "name", "test name", "description", "testcase", "use case"]):
                    col_map["scenario"] = i
                elif any(k == col or k in col for k in ["steps / data", "steps", "test steps", "data", "input", "action", "procedure", "payload"]):
                    col_map["steps"] = i
                elif any(k == col or k in col for k in ["expected result", "expected", "expected output", "outcome", "result", "response"]):
                    col_map["expected"] = i
                elif any(k == col or k in col for k in ["priority", "severity"]):
                    col_map["priority"] = i
                elif any(k == col or k in col for k in ["endpoint", "url", "path", "route", "api"]):
                    col_map["endpoint"] = i
                elif any(k == col or k in col for k in ["method", "http method", "verb"]):
                    col_map["method"] = i

            for r_idx, row in enumerate(tbl[1:], 1):
                if not any(row):
                    continue

                tc_id = row[col_map["id"]].strip() if "id" in col_map and col_map["id"] < len(row) and row[col_map["id"]].strip() else f"FT-{tbl_idx+1}-{r_idx:03d}"
                module = row[col_map["module"]].strip() if "module" in col_map and col_map["module"] < len(row) else ""
                scenario = row[col_map["scenario"]].strip() if "scenario" in col_map and col_map["scenario"] < len(row) else ""
                steps_text = row[col_map["steps"]].strip() if "steps" in col_map and col_map["steps"] < len(row) else ""
                expected_text = row[col_map["expected"]].strip() if "expected" in col_map and col_map["expected"] < len(row) else ""
                priority_val = row[col_map["priority"]].strip().upper() if "priority" in col_map and col_map["priority"] < len(row) else "HIGH"
                endpoint_col = row[col_map["endpoint"]].strip() if "endpoint" in col_map and col_map["endpoint"] < len(row) else ""
                method_col = row[col_map["method"]].strip().upper() if "method" in col_map and col_map["method"] < len(row) else ""

                method = method_col if method_col else None
                if not method:
                    m_match = re.search(r"\b(GET|POST|PUT|DELETE|PATCH)\b", f"{steps_text} {scenario} {endpoint_col}", re.IGNORECASE)
                    method = m_match.group(1).upper() if m_match else None

                endpoint = endpoint_col if endpoint_col else None
                if not endpoint:
                    ep_match = re.search(r"(/[a-zA-Z0-9_\-/{}.?&=%]+)", steps_text) or re.search(r"(/[a-zA-Z0-9_\-/{}.?&=%]+)", scenario)
                    endpoint = ep_match.group(1).rstrip(".") if ep_match else None

                if endpoint and re.match(r"^(?:GET|POST|PUT|DELETE|PATCH)\s+", endpoint, re.IGNORECASE):
                    parts = endpoint.split(None, 1)
                    if not method:
                        method = parts[0].upper()
                    endpoint = parts[1].strip()

                # Infer endpoint from module/steps if still missing
                if not endpoint and module:
                    mod_lower = module.lower()
                    combined_txt = f"{scenario} {steps_text}".lower()
                    if "emp" in mod_lower or "employee" in combined_txt:
                        endpoint = "/api/employees"
                    elif "att" in mod_lower or "attendance" in combined_txt:
                        endpoint = "/api/attendance"
                    elif "sal" in mod_lower or "salary" in combined_txt:
                        endpoint = "/api/salary"

                if not method:
                    combined_txt = f"{scenario} {steps_text}".lower()
                    if any(k in combined_txt for k in ["create", "add", "send invalid json", "omit required"]):
                        method = "POST"
                    elif any(k in combined_txt for k in ["update", "change", "modify"]):
                        method = "PUT"
                    elif any(k in combined_txt for k in ["delete", "remove"]):
                        method = "DELETE"
                    elif endpoint:
                        method = "GET"

                status_match = re.search(r"\b([1-5]\d{2})\b", expected_text)
                status_code = int(status_match.group(1)) if status_match else None

                is_negative = (
                    (status_code is not None and status_code >= 400)
                    or any(k in f"{scenario} {steps_text} {expected_text}".lower() for k in [
                        "invalid", "error", "reject", "fail", "duplicate", "unknown", "404", "400", "4xx", "500", "malformed", "missing", "unauthorized", "nonexistent"
                    ])
                )
                priority = "HIGH" if any(k in priority_val for k in ["HIGH", "CRITICAL", "P0", "P1"]) else ("LOW" if any(k in priority_val for k in ["LOW", "P3"]) else "MEDIUM")

                name = f"{module} - {scenario}" if module and scenario and module.lower() not in scenario.lower() else (scenario or f"Validate {endpoint or tc_id}")
                if name.lower() in seen_names:
                    name = f"{name} ({tc_id})"
                seen_names.add(name.lower())

                wf = BrdWorkflow(
                    name=name,
                    description=f"{steps_text} Expected: {expected_text}".strip() or f"Functional verification for {name}",
                    steps=[steps_text] if steps_text else [f"Execute scenario: {name}"],
                    structured_steps=[BrdWorkflowStep(step_number=1, action=steps_text or name, expected_outcome=expected_text or "Expected assertion outcome")],
                    actors=["User", "System"],
                    preconditions=["Application services online", "Required test data pre-configured"],
                    expected_result=expected_text or "Status code and response body conform to specification",
                    requirements_covered=[tc_id],
                    is_negative=is_negative,
                    priority=priority,
                    target_endpoint_hint=endpoint,
                    target_method_hint=method,
                    expected_status_hint=status_code,
                    source_reference=f"{self.file_path.name} [{tc_id}] {name}",
                )
                workflows.append(wf)

        # 2. Process Endpoint tables for uncovered endpoints
        existing_endpoints = {self._normalize_endpoint_path(w.target_endpoint_hint) for w in workflows if w.target_endpoint_hint}
        for ep_tbl in endpoint_tables:
            header = [c.lower().strip() for c in ep_tbl[0]]
            ep_col = next((i for i, col in enumerate(header) if any(k in col for k in ["endpoint", "url", "path", "route", "api"])), 0)
            method_col = next((i for i, col in enumerate(header) if any(k in col for k in ["method", "verb"])), None)
            purpose_col = next((i for i, col in enumerate(header) if any(k in col for k in ["purpose", "description", "action", "scenario"])), None)
            expected_col = next((i for i, col in enumerate(header) if any(k in col for k in ["expected", "response", "result"])), None)

            for r_idx, row in enumerate(ep_tbl[1:], 1):
                if not any(row):
                    continue
                raw_ep = row[ep_col].strip() if ep_col < len(row) else ""
                if not raw_ep:
                    continue

                method = row[method_col].strip().upper() if method_col is not None and method_col < len(row) else None
                endpoint = raw_ep
                if re.match(r"^(?:GET|POST|PUT|DELETE|PATCH)\s+", raw_ep, re.IGNORECASE):
                    parts = raw_ep.split(None, 1)
                    if not method:
                        method = parts[0].upper()
                    endpoint = parts[1].strip()

                if not method:
                    m_match = re.search(r"\b(GET|POST|PUT|DELETE|PATCH)\b", raw_ep, re.IGNORECASE)
                    method = m_match.group(1).upper() if m_match else "GET"

                norm_ep = self._normalize_endpoint_path(endpoint)
                if norm_ep in existing_endpoints and scenario_tables:
                    continue
                existing_endpoints.add(norm_ep)

                purpose = row[purpose_col].strip() if purpose_col is not None and purpose_col < len(row) else ""
                expected = row[expected_col].strip() if expected_col is not None and expected_col < len(row) else "200 OK"
                status_match = re.search(r"\b([1-5]\d{2})\b", expected)
                status_code = int(status_match.group(1)) if status_match else (201 if method == "POST" else (204 if method == "DELETE" else 200))

                tc_id = f"FT-EP-{len(workflows)+1:03d}"
                name = f"{method} {endpoint} - {purpose}" if purpose else f"Verify {method} {endpoint}"
                if name.lower() in seen_names:
                    name = f"{name} ({tc_id})"
                seen_names.add(name.lower())

                wf = BrdWorkflow(
                    name=name,
                    description=f"{purpose}. Endpoint: {method} {endpoint}. Expected: {expected}",
                    steps=[f"Send {method} request to {endpoint}", f"Verify HTTP {status_code} status"],
                    structured_steps=[
                        BrdWorkflowStep(step_number=1, action=f"Send {method} {endpoint}"),
                        BrdWorkflowStep(step_number=2, action=f"Verify status {status_code}"),
                    ],
                    actors=["User", "System"],
                    preconditions=["Application services online"],
                    expected_result=expected,
                    requirements_covered=[tc_id],
                    is_negative=status_code >= 400,
                    priority="HIGH",
                    target_endpoint_hint=endpoint,
                    target_method_hint=method,
                    expected_status_hint=status_code,
                    source_reference=f"{self.file_path.name} [{tc_id}] {name}",
                )
                workflows.append(wf)

        return workflows

    def _extract_scenarios_with_llm(self, text: str) -> list[BrdWorkflow]:
        """Dynamically queries configured LLM to extract all test cases into batch JSON."""
        try:
            from app.infrastructure.llm.chat_llm import ChatLLM
            llm = ChatLLM()
        except Exception:  # noqa: BLE001
            return []

        max_chunk_size = 10000
        chunks: list[str] = []
        if len(text) <= max_chunk_size:
            chunks = [text]
        else:
            paragraphs = text.split("\n\n")
            current_chunk: list[str] = []
            curr_len = 0
            for p in paragraphs:
                if curr_len + len(p) > max_chunk_size and current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = [p]
                    curr_len = len(p)
                else:
                    current_chunk.append(p)
                    curr_len += len(p)
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))

        all_llm_workflows: list[BrdWorkflow] = []
        system_prompt = (
            "You are an expert functional test engineer. Extract ALL functional test scenarios "
            "from the provided document. Output ONLY a valid JSON object in this exact format:\n"
            "{\n"
            '  "test_cases": [\n'
            "    {\n"
            '      "id": "FT-001",\n'
            '      "title": "Module - Scenario Title",\n'
            '      "description": "Scenario description",\n'
            '      "method": "POST",\n'
            '      "endpoint": "/api/endpoint",\n'
            '      "expected_status": 201,\n'
            '      "expected_result": "Expected response or persistence outcome",\n'
            '      "priority": "HIGH",\n'
            '      "is_negative": false,\n'
            '      "steps": ["Step 1", "Step 2"]\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Extract every single scenario found in tables, lists, and text. Do not truncate or limit the output."
        )

        for chunk in chunks:
            user_msg = f"Document content:\n\n{chunk}\n\nExtract all test scenarios now in JSON format."
            try:
                async def _stream_call(sp: str, um: str) -> str:
                    deltas = []
                    async for d in llm.stream_chat(sp, um, endpoint="brd_test_extraction"):
                        deltas.append(d)
                    return "".join(deltas)

                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    raw_resp = executor.submit(asyncio.run, _stream_call(system_prompt, user_msg)).result()

                clean_resp = raw_resp.strip()
                if "```json" in clean_resp:
                    clean_resp = clean_resp.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_resp:
                    clean_resp = clean_resp.split("```")[1].split("```")[0].strip()

                parsed_data = json.loads(clean_resp)
                tc_list = []
                if isinstance(parsed_data, dict):
                    tc_list = parsed_data.get("test_cases") or parsed_data.get("tests") or parsed_data.get("scenarios") or []
                elif isinstance(parsed_data, list):
                    tc_list = parsed_data

                for tc in tc_list:
                    if not isinstance(tc, dict):
                        continue
                    tc_id = tc.get("id") or f"FT-LLM-{len(all_llm_workflows)+1:03d}"
                    title = tc.get("title") or tc.get("name") or tc.get("scenario") or f"Test {tc_id}"
                    desc = tc.get("description") or title
                    method = tc.get("method") or "GET"
                    endpoint = tc.get("endpoint") or None
                    exp_status = tc.get("expected_status") or (200 if not tc.get("is_negative") else 400)
                    exp_result = tc.get("expected_result") or "Success"
                    prio = str(tc.get("priority", "HIGH")).upper()
                    is_neg = bool(tc.get("is_negative", False))
                    steps = tc.get("steps") or [f"Execute {title}"]

                    all_llm_workflows.append(
                        BrdWorkflow(
                            name=title,
                            description=desc,
                            steps=steps if isinstance(steps, list) else [str(steps)],
                            structured_steps=[BrdWorkflowStep(step_number=i+1, action=s) for i, s in enumerate(steps if isinstance(steps, list) else [str(steps)])],
                            actors=["User", "System"],
                            preconditions=["Application running"],
                            expected_result=exp_result,
                            requirements_covered=[tc_id],
                            is_negative=is_neg,
                            priority="HIGH" if "HIGH" in prio else ("LOW" if "LOW" in prio else "MEDIUM"),
                            target_endpoint_hint=endpoint,
                            target_method_hint=method,
                            expected_status_hint=exp_status if isinstance(exp_status, int) else None,
                            source_reference=f"{self.file_path.name}: {tc_id} ({title})",
                        )
                    )
            except Exception as llm_err:  # noqa: BLE001
                logger.info(f"LLM extraction skipped or unavailable: {llm_err}")
                break

        return all_llm_workflows

    def _extract_scenarios_from_text(self, text: str) -> list[BrdWorkflow]:
        """Extracts bulleted or numbered functional scenarios from text sections."""
        workflows: list[BrdWorkflow] = []
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for l in lines:
            m = re.match(
                r"^(?:(?:[-*•]|\d+[\.\)])\s*)?(?:(?:TC|FT|Scenario|Test Case)[\s\-:]+([A-Za-z0-9\-]+)[:\s\-]+)?([A-Z][^\n]{6,100})",
                l,
                re.IGNORECASE,
            )
            if not m:
                continue
            tc_id = m.group(1) or f"FT-TXT-{len(workflows)+1:03d}"
            scenario_body = m.group(2).strip()

            ep_match = re.search(r"(/[a-zA-Z0-9_\-/{}.?&=%]+)", scenario_body)
            if not ep_match and not any(k in scenario_body.lower() for k in ["verify", "test", "validate", "endpoint", "api"]):
                continue

            method_match = re.search(r"\b(GET|POST|PUT|DELETE|PATCH)\b", scenario_body, re.IGNORECASE)
            method = method_match.group(1).upper() if method_match else "GET"
            endpoint = ep_match.group(1).rstrip(".") if ep_match else None
            is_neg = any(k in scenario_body.lower() for k in ["invalid", "error", "fail", "reject", "duplicate", "boundary"])

            workflows.append(
                BrdWorkflow(
                    name=scenario_body[:80],
                    description=scenario_body,
                    steps=[scenario_body],
                    structured_steps=[BrdWorkflowStep(step_number=1, action=scenario_body)],
                    actors=["User", "System"],
                    preconditions=["Application running"],
                    expected_result="Operation completes as specified",
                    requirements_covered=[tc_id],
                    is_negative=is_neg,
                    priority="HIGH",
                    target_endpoint_hint=endpoint,
                    target_method_hint=method,
                    source_reference=f"{self.file_path.name} [{tc_id}] {scenario_body[:60]}",
                )
            )

        return workflows

    def _extract_requirements(self, text: str) -> list[BrdRequirement]:
        requirements: list[BrdRequirement] = []
        req_pattern = re.compile(
            r"(?:(?:\b(?:FR|BR|REQ|UC|CR|REQ-ID|BRD|FT|TC|TEST|SCEN)-?([A-Za-z0-9\-]+)\b[:\s\-]+)|(?:Requirement|Test Case|Scenario)\s*([A-Za-z0-9\-]+)[:\s\-]+)(.*?)(?=(?:\b(?:FR|BR|REQ|UC|CR|REQ-ID|BRD|FT|TC|TEST|SCEN)-?[A-Za-z0-9\-]+\b|(?:Requirement|Test Case|Scenario)\s*[A-Za-z0-9\-]+|\Z))",
            re.IGNORECASE | re.DOTALL,
        )

        for match in req_pattern.finditer(text):
            req_num = match.group(1) or match.group(2) or "001"
            req_id = req_num if any(req_num.upper().startswith(p) for p in ["FR-", "BR-", "REQ-", "FT-", "TC-"]) else f"FR-{req_num.zfill(3)}"
            body = match.group(3).strip()

            lines = [l.strip() for l in body.splitlines() if l.strip()]
            title = lines[0] if lines else f"Requirement {req_id}"
            description = "\n".join(lines[:6]) if lines else title

            ac_list = []
            for l in lines:
                if re.search(r"^(?:[-*•]|\d+\.|\bAcceptance Criteria\b|\bAC:|\bCriteria:)", l, re.IGNORECASE):
                    cleaned = re.sub(r"^(?:[-*•]|\d+\.|\bAcceptance Criteria\b|\bAC:|\bCriteria:)\s*", "", l, flags=re.IGNORECASE).strip()
                    if cleaned:
                        ac_list.append(cleaned)

            requirements.append(
                BrdRequirement(
                    id=req_id,
                    title=title[:120],
                    description=description[:500],
                    category="FUNCTIONAL",
                    acceptance_criteria=ac_list[:5],
                )
            )

        # If no explicit requirements extracted from text, check table scenarios
        if not requirements and self.structured_tables:
            for tbl in self.structured_tables:
                if len(tbl) < 2:
                    continue
                header = [c.lower().strip() for c in tbl[0]]
                id_col = next((i for i, c in enumerate(header) if any(k in c for k in ["tc id", "test id", "case id", "id", "#"])), None)
                scen_col = next((i for i, c in enumerate(header) if any(k in c for k in ["scenario", "title", "name", "description"])), None)
                if scen_col is not None:
                    for r_idx, r in enumerate(tbl[1:], 1):
                        r_id = r[id_col].strip() if id_col is not None and id_col < len(r) and r[id_col].strip() else f"FT-{r_idx:03d}"
                        scen = r[scen_col].strip() if scen_col < len(r) else f"Scenario {r_id}"
                        requirements.append(
                            BrdRequirement(
                                id=r_id,
                                title=scen[:120],
                                description=f"Functional requirement {r_id}: {scen}",
                                category="FUNCTIONAL",
                            )
                        )

        return requirements

    def _extract_workflows(self, text: str, requirements: list[BrdRequirement]) -> list[BrdWorkflow]:
        workflows: list[BrdWorkflow] = []
        seen_keys: set[str] = set()

        # 1. Extract from all structured tables (DOCX, XLSX, XLS, Markdown)
        table_workflows = self._extract_scenarios_from_tables()
        for wf in table_workflows:
            key = f"{wf.target_method_hint or ''}:{wf.target_endpoint_hint or ''}:{wf.name.lower()}".strip(":")
            if key and key in seen_keys:
                continue
            seen_keys.add(key)
            workflows.append(wf)

        # 2. Extract using configured LLM if available (only if no structured table workflows found)
        if not workflows:
            llm_workflows = self._extract_scenarios_with_llm(text)
            for wf in llm_workflows:
                key = f"{wf.target_method_hint or ''}:{wf.target_endpoint_hint or ''}:{wf.name.lower()}".strip(":")
                if key and key in seen_keys:
                    continue
                seen_keys.add(key)
                workflows.append(wf)

        # 3. Extract text-based scenarios (only if no workflows found yet)
        if not workflows:
            text_workflows = self._extract_scenarios_from_text(text)
            for wf in text_workflows:
                key = f"{wf.target_method_hint or ''}:{wf.target_endpoint_hint or ''}:{wf.name.lower()}".strip(":")
                if key and key in seen_keys:
                    continue
                seen_keys.add(key)
                workflows.append(wf)

        # 4. Identify explicit Workflow/Scenario headings (only if no workflows found yet)
        if not workflows:
            workflow_headings = re.findall(
                r"(?:^|\n)(?:###?\s*(?:Workflow|Scenario|User Story|Process Flow|Use Case|User Journey|Business Flow)\b\s*\d*[:\-]?\s*|\b(?:Workflow|Scenario|User Story|Process Flow|Use Case|User Journey|Business Flow)\s*\d+[:\-]\s*)([A-Z][^\n]{3,80})",
                text,
            )

            for heading in workflow_headings:
                clean_name = heading.strip().rstrip(":")
                if any(skip in clean_name.lower() for skip in ["executive summary", "overview", "introduction", "scope", "functional requirements", "business workflows", "glossary", "table of content", "architecture"]):
                    continue
                if clean_name.lower() in seen_keys or len(clean_name) < 4:
                    continue
                seen_keys.add(clean_name.lower())

                sec_pattern = re.escape(heading) + r"(.*?)(?=(?:###?|\b(?:Workflow|Scenario|User Story|Process Flow|Use Case|User Journey|Business Flow)\s*\d*|\Z))"
                sec_match = re.search(sec_pattern, text, re.DOTALL)
                sec_text = sec_match.group(1) if sec_match else ""

                steps = self._extract_steps_from_text(sec_text)
                if not steps:
                    steps = [
                        f"User initiates '{clean_name}' workflow",
                        f"System processes '{clean_name}' input parameters",
                        f"System verifies business constraints for '{clean_name}'",
                        "Workflow completes successfully with expected confirmation",
                    ]

                is_neg = any(k in clean_name.lower() or k in sec_text.lower() for k in ["invalid", "fail", "reject", "unauthorized", "boundary", "error", "exception"])
                priority = "HIGH" if any(k in clean_name.lower() for k in ["login", "auth", "checkout", "order", "payment", "critical", "p0"]) else "MEDIUM"
                ep_match = re.search(r"(?:POST|GET|PUT|DELETE|PATCH)\s+([/\w\-_]+)", sec_text, re.IGNORECASE)
                endpoint_hint = ep_match.group(1) if ep_match else None
                req_refs = [r.id for r in requirements if r.title.lower() in clean_name.lower() or r.id.lower() in sec_text.lower()]

                workflows.append(
                    BrdWorkflow(
                        name=clean_name,
                        description=sec_text.strip()[:300] or f"Workflow for {clean_name}",
                        steps=steps,
                        structured_steps=[
                            BrdWorkflowStep(step_number=idx + 1, action=s, expected_outcome=f"Step {idx + 1} satisfied")
                            for idx, s in enumerate(steps)
                        ],
                        actors=self._extract_actors(sec_text),
                        preconditions=[
                            "System services are online and accessible",
                            "Prerequisite test entities exist in system",
                        ],
                        expected_result="Workflow completes successfully with expected business state update" if not is_neg else "System rejects invalid inputs with appropriate business validation error",
                        requirements_covered=req_refs or ([requirements[0].id] if requirements else ["FR-001"]),
                        is_negative=is_neg,
                        priority=priority,
                        target_endpoint_hint=endpoint_hint,
                    )
                )

        # 5. Sequential Arrow Pattern
        if not workflows:
            arrow_flows = re.findall(r"([A-Za-z0-9\s]+(?:->|→|-->)[A-Za-z0-9\s\->→]+)", text)
            for arrow_str in arrow_flows:
                parts = [re.sub(r"^[0-9.\-\s]+", "", p).strip() for p in re.split(r"->|→|-->", arrow_str) if p.strip()]
                if len(parts) >= 2:
                    flow_name = f"{parts[0]} to {parts[-1]} End-to-End Flow"
                    if flow_name.lower() in seen_keys:
                        continue
                    seen_keys.add(flow_name.lower())

                    flow_steps = [f"Step {i+1}: {step_action}" for i, step_action in enumerate(parts)]
                    workflows.append(
                        BrdWorkflow(
                            name=flow_name,
                            description=f"End-to-end business journey traversing: {' → '.join(parts)}",
                            steps=flow_steps,
                            structured_steps=[
                                BrdWorkflowStep(step_number=i + 1, action=p, expected_outcome=f"Proceed to {parts[min(i + 1, len(parts) - 1)]}")
                                for i, p in enumerate(parts)
                            ],
                            actors=["User", "System"],
                            preconditions=["Application context initialized"],
                            expected_result=f"Complete traversal through {parts[-1]} achieved",
                            requirements_covered=[requirements[0].id] if requirements else ["FR-001"],
                            is_negative=False,
                            priority="HIGH",
                        )
                    )

        # 6. If no workflows discovered yet, generate from requirements
        if not workflows and requirements:
            for req in requirements:
                wf_name = f"Validate {req.title}"
                if wf_name.lower() in seen_keys:
                    continue
                seen_keys.add(wf_name.lower())

                steps = [
                    f"Prepare inputs for requirement {req.id}",
                    f"Execute business action: {req.title}",
                    f"Validate acceptance criteria: {', '.join(req.acceptance_criteria) if req.acceptance_criteria else 'Expected business result'}",
                ]
                workflows.append(
                    BrdWorkflow(
                        name=wf_name,
                        description=req.description,
                        steps=steps,
                        structured_steps=[
                            BrdWorkflowStep(step_number=i + 1, action=s, expected_outcome="Success")
                            for i, s in enumerate(steps)
                        ],
                        actors=["User", "System"],
                        preconditions=["Application running in test environment"],
                        expected_result="All acceptance criteria satisfied",
                        requirements_covered=[req.id],
                        priority="HIGH" if "critical" in req.title.lower() or "auth" in req.title.lower() else "MEDIUM",
                    )
                )

        return workflows

    def _extract_steps_from_text(self, text: str) -> list[str]:
        steps: list[str] = []
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for l in lines:
            if re.match(r"^(?:\d+[\.\)]|Step\s*\d+[:\-]|[-*•])\s*", l, re.IGNORECASE):
                cleaned = re.sub(r"^(?:\d+[\.\)]|Step\s*\d+[:\-]|[-*•])\s*", "", l, flags=re.IGNORECASE).strip()
                if len(cleaned) > 3:
                    steps.append(cleaned)
        return steps[:8]

    def _extract_actors(self, text: str) -> list[str]:
        actors = set()
        common_actors = ["User", "Admin", "Customer", "Manager", "Guest", "Client", "System", "Operator"]
        for a in common_actors:
            if re.search(rf"\b{a}\b", text, re.IGNORECASE):
                actors.add(a)
        return list(actors) if actors else ["User", "System"]
