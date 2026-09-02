"""Analyzer and parser for Business Requirements Documents (BRD)."""

from __future__ import annotations

import logging
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.domain.models.brd_models import (
    BrdExtractionResult,
    BrdRequirement,
    BrdWorkflow,
    BrdWorkflowStep,
)

logger = logging.getLogger(__name__)


class BrdAnalyzer:
    """Extracts business requirements, user journeys, workflows, and testable criteria from BRD documents."""

    def __init__(self, file_path: Path, job_id: str = "") -> None:
        self.file_path = Path(file_path)
        self.job_id = job_id

    def extract(self) -> BrdExtractionResult:
        """Parses the document and extracts structured business workflows and requirements."""
        filename = self.file_path.name
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
                    error="BRD document appears empty or unreadable.",
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
            logger.warning(f"Failed to parse BRD document {filename}: {e}")
            return BrdExtractionResult(
                job_id=self.job_id,
                filename=filename,
                error=f"BRD parsing failed: {e}",
            )

    def _extract_raw_text(self) -> str:
        ext = self.file_path.suffix.lower()

        if ext in [".txt", ".md"]:
            return self.file_path.read_text(encoding="utf-8", errors="replace")

        if ext == ".docx":
            return self._extract_docx_text()

        if ext == ".pdf":
            return self._extract_pdf_text()

        # Fallback for plain text or unknown
        try:
            return self.file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return ""

    def _extract_docx_text(self) -> str:
        try:
            with zipfile.ZipFile(self.file_path, "r") as docx_zip:
                if "word/document.xml" not in docx_zip.namelist():
                    return ""
                xml_content = docx_zip.read("word/document.xml").decode("utf-8", errors="replace")

                # Extract text inside <w:t> elements and handle paragraphs <w:p>
                paragraphs = re.findall(r"<w:p\b[^>]*>(.*?)</w:p>", xml_content, re.DOTALL)
                extracted_lines = []
                for p in paragraphs:
                    text_parts = re.findall(r"<w:t\b[^>]*>([^<]*)</w:t>", p)
                    line = "".join(text_parts).strip()
                    if line:
                        extracted_lines.append(line)

                return "\n\n".join(extracted_lines)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to extract text from docx: {e}")
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
            return "\n\n".join(pages_text)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"pypdf extraction failed or not available: {e}")
            # Fallback regex extraction of text streams
            try:
                raw_bytes = self.file_path.read_bytes()
                matches = re.findall(rb"\(([\w\s.,!?;:/\-_#@%&*+=()]+)\)\s*Tj", raw_bytes)
                if matches:
                    return " ".join(m.decode("utf-8", errors="ignore") for m in matches)
            except Exception:  # noqa: BLE001, S110
                pass  # nosec B110
            return ""

    def _extract_requirements(self, text: str) -> list[BrdRequirement]:
        requirements: list[BrdRequirement] = []
        req_pattern = re.compile(
            r"(?:(?:\b(?:FR|BR|REQ|UC|CR|REQ-ID|BRD)-?(\d+)\b[:\s\-]+)|(?:Requirement\s*(\d+)[:\s\-]+))(.*?)(?=(?:\b(?:FR|BR|REQ|UC|CR|REQ-ID|BRD)-?\d+\b|Requirement\s*\d+|\Z))",
            re.IGNORECASE | re.DOTALL,
        )

        for match in req_pattern.finditer(text):
            req_num = match.group(1) or match.group(2) or "001"
            req_id = f"FR-{req_num.zfill(3)}" if not req_num.startswith("FR-") else req_num
            body = match.group(3).strip()

            lines = [l.strip() for l in body.splitlines() if l.strip()]
            title = lines[0] if lines else f"Requirement {req_id}"
            description = "\n".join(lines[:6]) if lines else title

            # Extract acceptance criteria if present
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

        # If no explicit FR-xxx IDs were found, extract from bullet points or numbered sections
        if not requirements:
            section_matches = re.findall(
                r"(?:^|\n)(?:###?\s*|\d+\.\s+)([A-Z][^\n]{4,80})\n((?:[^\n]+\n?){1,6})",
                text,
            )
            for idx, (title, body) in enumerate(section_matches[:12], 1):
                clean_title = title.strip()
                if any(skip in clean_title.lower() for skip in ["table of content", "overview", "introduction", "scope", "glossary"]):
                    continue
                req_id = f"FR-{idx:03d}"
                requirements.append(
                    BrdRequirement(
                        id=req_id,
                        title=clean_title,
                        description=body.strip()[:400],
                        category="BUSINESS_RULE",
                        acceptance_criteria=[l.strip() for l in body.splitlines() if l.strip()][:4],
                    )
                )

        return requirements

    def _extract_workflows(self, text: str, requirements: list[BrdRequirement]) -> list[BrdWorkflow]:
        workflows: list[BrdWorkflow] = []
        seen_names: set[str] = set()

        # 1. Identify explicit Workflow/Scenario/User Story headings
        workflow_headings = re.findall(
            r"(?:^|\n)(?:###?\s*(?:Workflow|Scenario|User Story|Process Flow|Use Case|User Journey|Business Flow)\b\s*\d*[:\-]?\s*|\b(?:Workflow|Scenario|User Story|Process Flow|Use Case|User Journey|Business Flow)\s*\d+[:\-]\s*)([A-Z][^\n]{3,80})",
            text,
        )

        for heading in workflow_headings:
            clean_name = heading.strip().rstrip(":")
            # Exclude top-level document structure headings
            if any(skip in clean_name.lower() for skip in ["executive summary", "overview", "introduction", "scope", "functional requirements", "business workflows", "glossary", "table of content", "architecture"]):
                continue
            if clean_name.lower() in seen_names or len(clean_name) < 4:
                continue
            seen_names.add(clean_name.lower())

            # Find the section text following this heading
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

            # Check hint endpoints/services
            ep_match = re.search(r"(?:POST|GET|PUT|DELETE|PATCH)\s+([/\w\-_]+)", sec_text, re.IGNORECASE)
            endpoint_hint = ep_match.group(1) if ep_match else None

            # Associated requirements
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

        # 2. Sequential Arrow Pattern (only executed if no explicit workflow headings were identified)
        if not workflows:
            arrow_flows = re.findall(r"([A-Za-z0-9\s]+(?:->|→|-->)[A-Za-z0-9\s\->→]+)", text)
            for arrow_str in arrow_flows:
                parts = [re.sub(r"^[0-9.\-\s]+", "", p).strip() for p in re.split(r"->|→|-->", arrow_str) if p.strip()]
                if len(parts) >= 2:
                    flow_name = f"{parts[0]} to {parts[-1]} End-to-End Flow"
                    if flow_name.lower() in seen_names:
                        continue
                    seen_names.add(flow_name.lower())

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

        # 3. If no workflows discovered, generate from requirements
        if not workflows and requirements:
            for req in requirements[:8]:
                wf_name = f"Validate {req.title}"
                if wf_name.lower() in seen_names:
                    continue
                seen_names.add(wf_name.lower())

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

        # 4. Fallback baseline workflow if document was freeform text
        if not workflows:
            workflows.append(
                BrdWorkflow(
                    name="Core Business Process Verification",
                    description="Verification of primary business rules extracted from BRD.",
                    steps=[
                        "Initialize test environment",
                        "Trigger core business process",
                        "Verify outcome and system persistence",
                    ],
                    structured_steps=[
                        BrdWorkflowStep(step_number=1, action="Initialize environment"),
                        BrdWorkflowStep(step_number=2, action="Trigger core business process"),
                        BrdWorkflowStep(step_number=3, action="Verify outcome and persistence"),
                    ],
                    actors=["User", "System"],
                    preconditions=["Application running"],
                    expected_result="Core business process completes successfully",
                    requirements_covered=["FR-001"],
                    priority="HIGH",
                )
            )

        return workflows

    def _extract_steps_from_text(self, text: str) -> list[str]:
        steps: list[str] = []
        # Look for numbered or bulleted lines
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
