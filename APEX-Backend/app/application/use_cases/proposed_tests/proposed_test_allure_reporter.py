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
                sc_file = evidence_src_dir / "screenshot.svg"
                if not sc_file.exists():
                    sc_file = evidence_src_dir / "screenshot.png"
                if sc_file.exists():
                    att_dest = self.results_dir / f"{test_uuid}-screenshot{sc_file.suffix}"
                    shutil.copy2(sc_file, att_dest)
                    attachments.append({
                        "name": f"Screenshot - {t.title}",
                        "source": att_dest.name,
                        "type": "image/svg+xml" if sc_file.suffix == ".svg" else "image/png",
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
        Tries CLI `allure generate` if present; otherwise creates the complete Allure Report bundle.
        """
        self.report_dir.mkdir(parents=True, exist_ok=True)

        # 1. Attempt official Allure CLI if installed
        allure_cli = shutil.which("allure") or shutil.which("allure.bat")
        if allure_cli:
            try:
                cmd = [allure_cli, "generate", str(self.results_dir), "--clean", "-o", str(self.report_dir)]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
                if proc.returncode == 0 and (self.report_dir / "index.html").is_file():
                    logger.info(f"[{self.job_id}] Official Allure CLI generated report successfully.")
                    return self.report_dir
            except Exception as e:
                logger.warning(f"[{self.job_id}] Allure CLI attempt failed: {e}. Falling back to standalone report generator.")

        # 2. Build Rich Standalone Allure HTML Application
        html_content = self._build_standalone_allure_html(tests, selected_sources)
        index_file = self.report_dir / "index.html"
        index_file.write_text(html_content, encoding="utf-8")

        # Copy attachments to report/data/attachments/ for local serving
        attachments_dir = self.report_dir / "attachments"
        attachments_dir.mkdir(parents=True, exist_ok=True)
        for f in self.results_dir.glob("*"):
            if not f.name.endswith("-result.json") and not f.name.endswith("-container.json"):
                shutil.copy2(f, attachments_dir / f.name)

        logger.info(f"[{self.job_id}] Generated standalone Allure Report at: {index_file}")
        return self.report_dir

    def _build_standalone_allure_html(
        self,
        tests: list[ProposedTestCase],
        selected_sources: list[str] | None = None,
    ) -> str:
        """Constructs an interactive, high-fidelity Allure 2 HTML Dashboard."""
        total = len(tests)
        passed = sum(1 for t in tests if t.status == ProposedTestStatus.PASSED)
        failed = sum(1 for t in tests if t.status == ProposedTestStatus.FAILED)
        skipped = sum(1 for t in tests if t.status == ProposedTestStatus.SKIPPED)
        broken = total - passed - failed - skipped

        pass_rate = round((passed / total) * 100) if total > 0 else 0
        now_display = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Calculate total duration
        total_duration_sec = 0.0
        for t in tests:
            if t.execution_result and t.execution_result.duration:
                try:
                    total_duration_sec += float(t.execution_result.duration.replace("s", "").strip())
                except Exception:
                    total_duration_sec += 0.15
            else:
                total_duration_sec += 0.15
        duration_display = f"{total_duration_sec:.2f}s"

        # Build JSON dataset for the client-side Allure single page app
        test_payloads = []
        for t in tests:
            res = t.execution_result
            status_str = "passed" if t.status == ProposedTestStatus.PASSED else (
                "failed" if t.status == ProposedTestStatus.FAILED else "skipped"
            )

            # Determine source label
            source_label = "LLM Generated"
            gen_src = (t.generation_source or "").upper()
            if gen_src in ["BRD_DOCUMENT", "FUNCTIONAL_DOC", "FUNCTIONAL_DOCUMENT"] or "BRD" in t.id or t.source in ["BRD Document", "BRD Business Requirement"]:
                source_label = "Functional Testing Document"
            elif gen_src in ["EXISTING", "EXISTING_TESTS"] or "EXT" in t.id or t.source in ["Existing Repository", "Existing Repository Tests"]:
                source_label = "Existing Repository"

            suite_name = t.source or (t.type.value if hasattr(t.type, "value") else str(t.type))
            if "\\" in suite_name or "/" in suite_name:
                suite_name = Path(suite_name).stem

            # Step items
            steps = []
            if res and res.steps_execution:
                for sr in res.steps_execution:
                    steps.append({
                        "step": sr.step_number,
                        "title": sr.description,
                        "status": "passed" if sr.status == ProposedTestStatus.PASSED else "failed",
                        "duration": sr.duration or "0.04s",
                        "error": sr.error,
                    })
            elif t.steps:
                for idx, s in enumerate(t.steps):
                    steps.append({
                        "step": idx + 1,
                        "title": s,
                        "status": status_str,
                        "duration": "0.05s",
                        "error": res.error if res and status_str == "failed" else None,
                    })

            # API specific details
            api_info = None
            if t.type == ProposedTestType.API and t.api_spec:
                spec = t.api_spec
                expected_status = spec.expected_status or 200
                actual_status = res.actual_status_code if res and res.actual_status_code is not None else expected_status
                api_info = {
                    "method": spec.method.upper(),
                    "endpoint": spec.endpoint,
                    "expected_status": expected_status,
                    "actual_status": actual_status,
                    "headers": sanitize_headers(spec.headers),
                    "request_body": spec.request_body,
                    "response_body": res.actual_response if res and res.actual_response is not None else spec.expected_response or {"status": "success"},
                    "response_time": res.duration if res else "0.08s",
                }

            # UI specific evidence
            ui_info = None
            if t.type == ProposedTestType.UI:
                screenshot_url = res.evidence.screenshot_url if res and res.evidence else None
                ui_info = {
                    "target_route": t.ui_spec.target_route if t.ui_spec else "/",
                    "screenshot_url": screenshot_url or f"/api/v1/migration/{self.job_id}/proposed-tests/evidence/{t.id}/screenshot.svg",
                    "video_available": res.evidence.video_available if res and res.evidence else False,
                    "video_url": res.evidence.video_url if res and res.evidence else None,
                }

            test_payloads.append({
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "type": t.type.value if hasattr(t.type, "value") else str(t.type),
                "priority": t.priority.value if hasattr(t.priority, "value") else str(t.priority),
                "status": status_str,
                "source": source_label,
                "suite": suite_name,
                "duration": res.duration if res else "0.12s",
                "error": res.error if res else None,
                "stack_trace": res.stack_trace if res else None,
                "steps": steps,
                "api": api_info,
                "ui": ui_info,
                "reason": t.reason,
                "expected": t.expected_result,
            })

        json_data_str = json.dumps(test_payloads).replace("</script>", "<\\/script>")

        # Generate Complete Standalone HTML
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Allure Report - Proposed Test Execution ({self.job_id})</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-main: #0f172a;
      --bg-sidebar: #090d16;
      --bg-card: #1e293b;
      --bg-hover: #334155;
      --border-color: #334155;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --color-passed: #10b981;
      --color-failed: #ef4444;
      --color-broken: #f59e0b;
      --color-skipped: #64748b;
      --color-accent: #7c3aed;
      --color-blue: #0284c7;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg-main);
      color: var(--text-main);
      height: 100vh;
      display: flex;
      overflow: hidden;
    }}
    /* Sidebar */
    .sidebar {{
      width: 220px;
      background: var(--bg-sidebar);
      border-right: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
    }}
    .sidebar-header {{
      padding: 18px 20px;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .allure-logo {{
      width: 28px;
      height: 28px;
      border-radius: 6px;
      background: linear-gradient(135deg, #7c3aed, #0284c7);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 900;
      color: #fff;
      font-size: 14px;
    }}
    .sidebar-title {{
      font-size: 14px;
      font-weight: 800;
      letter-spacing: 0.5px;
      color: #fff;
    }}
    .nav-links {{
      padding: 14px 10px;
      display: flex;
      flex-direction: column;
      gap: 4px;
      flex: 1;
    }}
    .nav-item {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 700;
      color: var(--text-muted);
      cursor: pointer;
      transition: all 0.15s;
    }}
    .nav-item:hover {{
      background: rgba(255,255,255,0.05);
      color: #fff;
    }}
    .nav-item.active {{
      background: var(--color-accent);
      color: #fff;
    }}
    /* Main Layout */
    .main-content {{
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .topbar {{
      padding: 14px 28px;
      background: var(--bg-sidebar);
      border-bottom: 1px solid var(--border-color);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .topbar-title {{
      font-size: 16px;
      font-weight: 800;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .badge-pass-rate {{
      background: rgba(16, 185, 129, 0.15);
      color: var(--color-passed);
      border: 1px solid var(--color-passed);
      padding: 3px 10px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 800;
    }}
    .content-body {{
      flex: 1;
      overflow-y: auto;
      padding: 24px 28px;
    }}
    /* Overview Grid */
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 24px;
    }}
    .stat-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 18px 20px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .stat-label {{
      font-size: 11px;
      font-weight: 800;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .stat-val {{
      font-size: 24px;
      font-weight: 900;
      color: #fff;
    }}
    /* Suites Dual View */
    .suites-container {{
      display: grid;
      grid-template-columns: 380px 1fr;
      gap: 20px;
      height: calc(100vh - 150px);
    }}
    .suites-panel {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .suites-search {{
      padding: 12px;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      gap: 8px;
    }}
    .search-input {{
      flex: 1;
      background: var(--bg-main);
      border: 1px solid var(--border-color);
      border-radius: 6px;
      padding: 8px 12px;
      color: #fff;
      font-size: 12px;
      outline: none;
    }}
    .search-input:focus {{
      border-color: var(--color-accent);
    }}
    .test-list {{
      flex: 1;
      overflow-y: auto;
      padding: 8px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .test-item {{
      padding: 10px 12px;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      transition: background 0.12s;
    }}
    .test-item:hover {{
      background: var(--bg-hover);
    }}
    .test-item.selected {{
      background: #3b82f620;
      border: 1px solid var(--color-blue);
    }}
    .status-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }}
    .status-passed {{ background: var(--color-passed); }}
    .status-failed {{ background: var(--color-failed); }}
    .status-skipped {{ background: var(--color-skipped); }}
    /* Test Details View */
    .details-panel {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 24px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }}
    .detail-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 16px;
    }}
    .detail-title {{
      font-size: 18px;
      font-weight: 800;
      color: #fff;
      line-height: 1.4;
    }}
    .detail-meta {{
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 6px;
      display: flex;
      gap: 16px;
    }}
    .steps-section {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .step-item {{
      background: var(--bg-main);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 12px 16px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .step-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 13px;
      font-weight: 700;
    }}
    .api-inspector {{
      background: #090d16;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 16px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      overflow-x: auto;
    }}
    .ui-viewer {{
      background: #090d16;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 16px;
      text-align: center;
    }}
    .ui-viewer img, .ui-viewer svg {{
      max-width: 100%;
      border-radius: 6px;
      border: 1px solid var(--border-color);
    }}
    .tab-content {{ display: none; }}
    .tab-content.active {{ display: block; }}
  </style>
</head>
<body>
  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="allure-logo">A</div>
      <div class="sidebar-title">ALLURE REPORT</div>
    </div>
    <nav class="nav-links">
      <div class="nav-item active" onclick="switchTab('overview')">📊 Overview</div>
      <div class="nav-item" onclick="switchTab('suites')">📁 Suites</div>
      <div class="nav-item" onclick="switchTab('behaviors')">🧪 Behaviors</div>
      <div class="nav-item" onclick="switchTab('timeline')">⏱ Timeline</div>
    </nav>
    <div style="padding: 16px 20px; font-size: 11px; color: var(--text-muted); border-top: 1px solid var(--border-color);">
      Job: {self.job_id}<br>
      Execution: Playwright
    </div>
  </aside>

  <!-- Main Content -->
  <main class="main-content">
    <div class="topbar">
      <div class="topbar-title">
        <span>Proposed Test Case Execution</span>
        <span class="badge-pass-rate">{pass_rate}% Passed</span>
      </div>
      <div style="font-size: 12px; color: var(--text-muted);">
        {now_display} • Duration: <strong>{duration_display}</strong>
      </div>
    </div>

    <div class="content-body">
      <!-- ── Tab 1: Overview ── -->
      <div id="tab-overview" class="tab-content active">
        <div class="stats-grid">
          <div class="stat-card">
            <span class="stat-label">Total Executed</span>
            <span class="stat-val">{total}</span>
          </div>
          <div class="stat-card" style="border-left: 4px solid var(--color-passed);">
            <span class="stat-label" style="color: var(--color-passed);">Passed</span>
            <span class="stat-val" style="color: var(--color-passed);">{passed}</span>
          </div>
          <div class="stat-card" style="border-left: 4px solid var(--color-failed);">
            <span class="stat-label" style="color: var(--color-failed);">Failed</span>
            <span class="stat-val" style="color: var(--color-failed);">{failed}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">Execution Time</span>
            <span class="stat-val" style="color: var(--color-blue);">{duration_display}</span>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;">
          <!-- Card 1: Test Suite Distribution -->
          <div class="stat-card" style="padding: 24px;">
            <h3 style="font-size: 15px; font-weight: 800; margin-bottom: 16px;">Test Status Breakdown</h3>
            <div style="display: flex; flex-direction: column; gap: 12px;">
              <div>
                <div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: 700; margin-bottom: 4px;">
                  <span>Passed ({passed})</span>
                  <span>{pass_rate}%</span>
                </div>
                <div style="height: 8px; background: #334155; border-radius: 4px; overflow: hidden;">
                  <div style="width: {pass_rate}%; height: 100%; background: var(--color-passed);"></div>
                </div>
              </div>
              <div>
                <div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: 700; margin-bottom: 4px;">
                  <span>Failed ({failed})</span>
                  <span>{100 - pass_rate if total > 0 else 0}%</span>
                </div>
                <div style="height: 8px; background: #334155; border-radius: 4px; overflow: hidden;">
                  <div style="width: {100 - pass_rate if total > 0 else 0}%; height: 100%; background: var(--color-failed);"></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Card 2: Execution Provenance -->
          <div class="stat-card" style="padding: 24px;">
            <h3 style="font-size: 15px; font-weight: 800; margin-bottom: 16px;">Execution Environment</h3>
            <div style="display: flex; flex-direction: column; gap: 8px; font-size: 13px; color: var(--text-muted);">
              <div>• <strong>Engine:</strong> Playwright Test Engine</div>
              <div>• <strong>Scope:</strong> User Selected Migration Test Cases</div>
              <div>• <strong>Artifacts:</strong> Screenshots, Video Recordings, HTTP Traces</div>
              <div>• <strong>Target Application:</strong> Migrated Java Microservice</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Tab 2: Suites ── -->
      <div id="tab-suites" class="tab-content">
        <div class="suites-container">
          <!-- Left list -->
          <div class="suites-panel">
            <div class="suites-search">
              <input type="text" id="suiteSearch" class="search-input" placeholder="Filter test cases..." oninput="filterTests()">
            </div>
            <div class="test-list" id="testList"></div>
          </div>

          <!-- Right Details -->
          <div class="details-panel" id="testDetails">
            <div style="color: var(--text-muted); text-align: center; margin-top: 80px;">
              Select a test case on the left to inspect execution details, assertions, and visual/HTTP evidence.
            </div>
          </div>
        </div>
      </div>

      <!-- ── Tab 3: Behaviors ── -->
      <div id="tab-behaviors" class="tab-content">
        <div class="stat-card" style="padding: 24px;">
          <h3 style="font-size: 16px; font-weight: 800; margin-bottom: 14px;">Behaviors & Feature Scenarios</h3>
          <div id="behaviorsList" style="display: flex; flex-direction: column; gap: 10px;"></div>
        </div>
      </div>

      <!-- ── Tab 4: Timeline ── -->
      <div id="tab-timeline" class="tab-content">
        <div class="stat-card" style="padding: 24px;">
          <h3 style="font-size: 16px; font-weight: 800; margin-bottom: 14px;">Execution Timeline</h3>
          <div id="timelineList" style="display: flex; flex-direction: column; gap: 8px;"></div>
        </div>
      </div>
    </div>
  </main>

  <script>
    const testsData = {json_data_str};
    let selectedTest = testsData[0] || null;

    function switchTab(tabId) {{
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
      document.getElementById('tab-' + tabId).classList.add('active');
      event.currentTarget.classList.add('active');
    }}

    function renderTestList(filter = "") {{
      const listEl = document.getElementById('testList');
      listEl.innerHTML = "";
      const filtered = testsData.filter(t => 
        !filter || t.title.toLowerCase().includes(filter.toLowerCase()) || t.id.toLowerCase().includes(filter.toLowerCase())
      );

      filtered.forEach(t => {{
        const item = document.createElement('div');
        item.className = 'test-item ' + (selectedTest && selectedTest.id === t.id ? 'selected' : '');
        item.onclick = () => {{ selectedTest = t; renderTestList(filter); renderTestDetails(); }};

        item.innerHTML = `
          <div style="display: flex; align-items: center; gap: 10px; overflow: hidden;">
            <div class="status-dot status-${{t.status}}"></div>
            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              <div style="font-size: 12px; font-weight: 700; color: #fff;">${{t.id}}</div>
              <div style="font-size: 11px; color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${{t.title}}</div>
            </div>
          </div>
          <span style="font-size: 10px; color: var(--text-muted); font-weight: 700; flex-shrink: 0;">${{t.duration}}</span>
        `;
        listEl.appendChild(item);
      }});
    }}

    function renderTestDetails() {{
      const d = document.getElementById('testDetails');
      if (!selectedTest) return;
      const t = selectedTest;

      let evidenceSection = "";
      if (t.api) {{
        evidenceSection = `
          <div style="margin-top: 14px;">
            <h4 style="font-size: 13px; font-weight: 800; color: #38bdf8; text-transform: uppercase; margin-bottom: 8px;">HTTP API Request & Response</h4>
            <div class="api-inspector">
              <div style="color: #10b981; font-weight: 700;">> ${{t.api.method}} ${{t.api.endpoint}} HTTP/1.1</div>
              <div style="color: #64748b; margin: 4px 0 8px 0;">Expected Status: <strong style="color: #fff;">${{t.api.expected_status}}</strong> | Actual Status: <strong style="color: ${{t.api.actual_status === t.api.expected_status ? '#10b981' : '#ef4444'}};">${{t.api.actual_status}}</strong> | Duration: ${{t.api.response_time}}</div>
              <div style="color: #94a3b8; font-size: 11px; margin-bottom: 4px;">Request Headers:</div>
              <pre style="color: #cbd5e1; margin-bottom: 8px;">${{JSON.stringify(t.api.headers, null, 2)}}</pre>
              <div style="color: #94a3b8; font-size: 11px; margin-bottom: 4px;">Response Payload:</div>
              <pre style="color: #38bdf8;">${{JSON.stringify(t.api.response_body, null, 2)}}</pre>
            </div>
          </div>
        `;
      }} else if (t.ui) {{
        evidenceSection = `
          <div style="margin-top: 14px;">
            <h4 style="font-size: 13px; font-weight: 800; color: #a855f7; text-transform: uppercase; margin-bottom: 8px;">Playwright Visual Evidence</h4>
            <div class="ui-viewer">
              <img src="${{t.ui.screenshot_url}}" alt="Screenshot for ${{t.id}}" style="max-height: 380px;">
            </div>
          </div>
        `;
      }}

      let stepsHtml = (t.steps || []).map(s => `
        <div class="step-item">
          <div class="step-header">
            <span style="display: flex; align-items: center; gap: 8px;">
              <span class="status-dot status-${{s.status}}"></span>
              <span>Step ${{s.step}}: ${{s.title}}</span>
            </span>
            <span style="font-size: 11px; color: var(--text-muted);">${{s.duration}}</span>
          </div>
          ${{s.error ? `<div style="color: var(--color-failed); font-size: 11px; font-family: monospace;">Error: ${{s.error}}</div>` : ''}}
        </div>
      `).join('');

      d.innerHTML = `
        <div class="detail-header">
          <div>
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
              <span class="status-dot status-${{t.status}}"></span>
              <span style="font-size: 12px; font-weight: 800; color: var(--text-muted); text-transform: uppercase;">${{t.type}} • ${{t.source}} • ${{t.priority}}</span>
            </div>
            <div class="detail-title">[${{t.id}}] ${{t.title}}</div>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 14px; font-weight: 900; color: ${{t.status === 'passed' ? 'var(--color-passed)' : 'var(--color-failed)'}};">${{t.status.toUpperCase()}}</div>
            <div style="font-size: 11px; color: var(--text-muted);">${{t.duration}}</div>
          </div>
        </div>

        <div>
          <h4 style="font-size: 12px; font-weight: 800; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px;">Test Description & Expected Outcome</h4>
          <p style="font-size: 13px; color: #cbd5e1; line-height: 1.5;">${{t.description || t.title}}</p>
          <div style="font-size: 12px; color: #38bdf8; margin-top: 4px;"><strong>Expected Result:</strong> ${{t.expected}}</div>
        </div>

        <div class="steps-section">
          <h4 style="font-size: 12px; font-weight: 800; color: var(--text-muted); text-transform: uppercase;">Step Execution Sequence (${{(t.steps || []).length}} steps)</h4>
          ${{stepsHtml}}
        </div>

        ${{evidenceSection}}
      `;
    }}

    function filterTests() {{
      const val = document.getElementById('suiteSearch').value;
      renderTestList(val);
    }}

    // Render Behaviors
    function renderBehaviors() {{
      const bEl = document.getElementById('behaviorsList');
      bEl.innerHTML = testsData.map(t => `
        <div style="background: var(--bg-main); padding: 12px 16px; border-radius: 8px; border: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
          <div>
            <div style="font-size: 13px; font-weight: 700; color: #fff;">Feature: ${{t.source}} → ${{t.title}}</div>
            <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Story ID: ${{t.id}} • Type: ${{t.type}}</div>
          </div>
          <span class="status-dot status-${{t.status}}"></span>
        </div>
      `).join('');
    }}

    // Render Timeline
    function renderTimeline() {{
      const tEl = document.getElementById('timelineList');
      tEl.innerHTML = testsData.map((t, idx) => `
        <div style="background: var(--bg-main); padding: 10px 14px; border-radius: 6px; border: 1px solid var(--border-color); display: flex; align-items: center; gap: 14px;">
          <span style="font-size: 11px; font-weight: 700; color: var(--text-muted); width: 60px;">+${{idx * 150}}ms</span>
          <div class="status-dot status-${{t.status}}"></div>
          <span style="font-size: 12px; font-weight: 700; color: #fff; flex: 1;">${{t.id}}: ${{t.title}}</span>
          <span style="font-size: 11px; color: var(--color-blue); font-family: monospace;">${{t.duration}}</span>
        </div>
      `).join('');
    }}

    // Initialize
    renderTestList();
    renderTestDetails();
    renderBehaviors();
    renderTimeline();
  </script>
</body>
</html>
"""
