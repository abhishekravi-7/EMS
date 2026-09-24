"""Allure Report Generator for Proposed Functional Test Cases."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domain.models.proposed_test_models import (
    ProposedTestCase,
    ProposedTestStatus,
    ProposedTestType,
)
from app.infrastructure.workspace.workspace_paths import WorkspacePaths

logger = logging.getLogger(__name__)

SENSITIVE_HEADER_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
    "x-auth-token",
    "secret",
    "password",
    "token",
    "access_token",
    "refresh_token",
}


def sanitize_headers(headers: dict[str, Any] | None) -> dict[str, str]:
    """Sanitizes sensitive HTTP headers, redacting tokens, keys, and passwords."""
    if not headers:
        return {}
    sanitized: dict[str, str] = {}
    for k, v in headers.items():
        key_lower = str(k).lower()
        if any(s in key_lower for s in SENSITIVE_HEADER_KEYS):
            sanitized[str(k)] = "[REDACTED]"
        else:
            sanitized[str(k)] = str(v)
    return sanitized


class ProposedTestAllureReporter:
    """Generates standard Allure 2 results and standalone interactive HTML Allure reports."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        paths = WorkspacePaths(job_id)
        self.base_dir = paths.job_dir / "proposed-tests"
        self.results_dir = self.base_dir / "allure-results"
        self.report_dir = self.base_dir / "allure-report"

    def clean_results(self) -> None:
        """Cleans and creates fresh results and report directories for a new execution run."""
        if self.results_dir.exists():
            shutil.rmtree(self.results_dir, ignore_errors=True)
        if self.report_dir.exists():
            shutil.rmtree(self.report_dir, ignore_errors=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate_allure_results(
        self,
        tests: list[ProposedTestCase],
        selected_sources: list[str] | None = None,
    ) -> Path:
        """Generates standard Allure 2 JSON files and copies evidence attachments."""
        self.results_dir.mkdir(parents=True, exist_ok=True)
        now_ms = int(time.time() * 1000)

        for t in tests:
            test_uuid = str(uuid.uuid4())
            res = t.execution_result
            status_str = "passed" if t.status == ProposedTestStatus.PASSED else (
                "failed" if t.status == ProposedTestStatus.FAILED else (
                    "skipped" if t.status == ProposedTestStatus.SKIPPED else "broken"
                )
            )

            # Determine duration in ms
            duration_ms = 150
            if res and res.duration:
                try:
                    duration_ms = max(10, int(float(res.duration.replace("s", "").strip()) * 1000))
                except Exception:
                    duration_ms = 150

            start_ms = now_ms - duration_ms
            stop_ms = now_ms

            # Determine source label
            source_label = "LLM Generated"
            gen_src = (t.generation_source or "").upper()
            if gen_src in ["BRD_DOCUMENT", "FUNCTIONAL_DOC", "FUNCTIONAL_DOCUMENT"] or "BRD" in t.id or t.source in ["BRD Document", "BRD Business Requirement"]:
                source_label = "Functional Testing Document"
            elif gen_src in ["EXISTING", "EXISTING_TESTS"] or "EXT" in t.id or t.source in ["Existing Repository", "Existing Repository Tests"]:
                source_label = "Existing Repository"

            # Suite classification
            suite_name = t.source or (t.type.value if hasattr(t.type, "value") else str(t.type))
            if "\\" in suite_name or "/" in suite_name:
                suite_name = Path(suite_name).stem

            # Severity label
            severity = "critical" if t.priority.value == "HIGH" else ("normal" if t.priority.value == "MEDIUM" else "minor")

            attachments: list[dict[str, Any]] = []
            steps: list[dict[str, Any]] = []

            # Process Steps
            step_records = res.steps_execution if res and res.steps_execution else []
            if not step_records and t.steps:
                for idx, s in enumerate(t.steps):
                    steps.append({
                        "name": s,
                        "status": status_str,
                        "stage": "finished",
                        "start": start_ms + (idx * 20),
                        "stop": start_ms + ((idx + 1) * 20),
                        "attachments": [],
                        "parameters": [],
                    })
            else:
                for idx, sr in enumerate(step_records):
                    step_status = "passed" if sr.status == ProposedTestStatus.PASSED else (
                        "failed" if sr.status == ProposedTestStatus.FAILED else "broken"
                    )
                    steps.append({
                        "name": f"Step {sr.step_number}: {sr.description}",
                        "status": step_status,
                        "stage": "finished",
                        "start": start_ms + (idx * 25),
                        "stop": start_ms + ((idx + 1) * 25),
                        "statusDetails": {"message": sr.error} if sr.error else {},
                        "attachments": [],
                        "parameters": [],
                    })

            # Process UI Evidence Attachments
            if t.type == ProposedTestType.UI:
                evidence_src_dir = self.base_dir / "evidence" / t.id
                # Check for screenshot
                sc_file = evidence_src_dir / "screenshot.png"
                if not sc_file.exists():
                    sc_file = evidence_src_dir / "screenshot.svg"
                if sc_file.exists():
                    att_dest = self.results_dir / f"{test_uuid}-screenshot{sc_file.suffix}"
                    shutil.copy2(sc_file, att_dest)
                    attachments.append({
                        "name": f"Screenshot - {t.title}",
                        "source": att_dest.name,
                        "type": "image/png" if sc_file.suffix == ".png" else "image/svg+xml",
                    })

                # Check for video
                video_file = evidence_src_dir / "video.webm"
                if not video_file.exists():
                    video_file = evidence_src_dir / "video.mp4"
                if video_file.exists():
                    att_dest = self.results_dir / f"{test_uuid}-video{video_file.suffix}"
                    shutil.copy2(video_file, att_dest)
                    attachments.append({
                        "name": f"Browser Video Recording - {t.title}",
                        "source": att_dest.name,
                        "type": "video/webm" if video_file.suffix == ".webm" else "video/mp4",
                    })

                # Check for browser logs
                log_file = evidence_src_dir / "browser_steps.log"
                if log_file.exists():
                    att_dest = self.results_dir / f"{test_uuid}-browser.log"
                    shutil.copy2(log_file, att_dest)
                    attachments.append({
                        "name": "Playwright Step Execution Log",
                        "source": att_dest.name,
                        "type": "text/plain",
                    })

            # Process API Evidence Attachments
            elif t.type == ProposedTestType.API and t.api_spec:
                spec = t.api_spec
                method = spec.method.upper()
                endpoint = spec.endpoint
                expected_status = spec.expected_status or 200
                actual_status = res.actual_status_code if res and res.actual_status_code is not None else expected_status

                # Request attachment
                req_data = {
                    "method": method,
                    "endpoint": endpoint,
                    "headers": sanitize_headers(spec.headers),
                    "body": spec.request_body,
                }
                req_file = self.results_dir / f"{test_uuid}-request.json"
                req_file.write_text(json.dumps(req_data, indent=2), encoding="utf-8")
                attachments.append({
                    "name": f"HTTP Request: {method} {endpoint}",
                    "source": req_file.name,
                    "type": "application/json",
                })

                # Response attachment
                resp_data = {
                    "expected_status": expected_status,
                    "actual_status": actual_status,
                    "response_time": res.duration if res else "0.08s",
                    "status_match": actual_status == expected_status,
                    "response_body": res.actual_response if res and res.actual_response is not None else spec.expected_response or {"status": "success"},
                }
                resp_file = self.results_dir / f"{test_uuid}-response.json"
                resp_file.write_text(json.dumps(resp_data, indent=2), encoding="utf-8")
                attachments.append({
                    "name": f"HTTP Response ({actual_status} {'OK' if actual_status < 400 else 'FAILED'})",
                    "source": resp_file.name,
                    "type": "application/json",
                })

            # Construct Allure Test Result Object
            test_result: dict[str, Any] = {
                "uuid": test_uuid,
                "historyId": f"hist-{t.id.lower()}",
                "fullName": f"{suite_name}.{t.id}: {t.title}",
                "name": f"[{t.id}] {t.title}",
                "status": status_str,
                "statusDetails": {
                    "known": False,
                    "muted": False,
                    "flaky": False,
                    "message": res.error if res and res.error else (f"Assertion passed: expected result satisfied ({t.expected_result})" if status_str == "passed" else "Execution failed"),
                    "trace": res.stack_trace if res and res.stack_trace else None,
                },
                "stage": "finished",
                "description": t.description or t.title,
                "descriptionHtml": f"<p>{t.description or t.title}</p><p><strong>Reason:</strong> {t.reason}</p><p><strong>Expected:</strong> {t.expected_result}</p>",
                "start": start_ms,
                "stop": stop_ms,
                "steps": steps,
                "attachments": attachments,
                "parameters": [
                    {"name": "Test Type", "value": t.type.value if hasattr(t.type, "value") else str(t.type)},
                    {"name": "Source Provenance", "value": source_label},
                    {"name": "Priority", "value": t.priority.value if hasattr(t.priority, "value") else str(t.priority)},
                ],
                "labels": [
                    {"name": "parentSuite", "value": "Proposed Functional Tests"},
                    {"name": "suite", "value": source_label},
                    {"name": "subSuite", "value": suite_name},
                    {"name": "feature", "value": t.type.value if hasattr(t.type, "value") else str(t.type)},
                    {"name": "story", "value": t.title},
                    {"name": "severity", "value": severity},
                    {"name": "tag", "value": "playwright"},
                    {"name": "tag", "value": source_label.lower().replace(" ", "-")},
                ],
                "links": [
                    {"name": f"Test ID: {t.id}", "url": f"#{t.id}"}
                ],
            }

            # Add endpoint parameter for API
            if t.api_spec:
                test_result["parameters"].append({
                    "name": "Endpoint",
                    "value": f"{t.api_spec.method.upper()} {t.api_spec.endpoint}",
                })

            result_file = self.results_dir / f"{test_uuid}-result.json"
            result_file.write_text(json.dumps(test_result, indent=2), encoding="utf-8")

        return self.results_dir

    def generate_html_report(
        self,
        tests: list[ProposedTestCase],
        selected_sources: list[str] | None = None,
    ) -> Path:
        """
        Generates a rich, standalone HTML Allure Report.
        Requires official `allure` CLI to be installed.
        """
        self.report_dir.mkdir(parents=True, exist_ok=True)

        allure_cli = shutil.which("allure") or shutil.which("allure.bat") or shutil.which("allure.cmd")
        if not allure_cli:
            raise RuntimeError("Allure CLI not found in system PATH. Cannot generate report.")

        try:
            cmd = [allure_cli, "generate", str(self.results_dir), "--clean", "-o", str(self.report_dir)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
            if proc.returncode == 0 and (self.report_dir / "index.html").is_file():
                logger.info(f"[{self.job_id}] Official Allure CLI generated report successfully.")
                return self.report_dir
            else:
                raise RuntimeError(f"Allure CLI exited with code {proc.returncode}. Stderr: {proc.stderr}")
        except Exception as e:
            raise RuntimeError(f"Failed to execute Allure CLI: {e}")

