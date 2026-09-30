"""Playwright HTML Report Generator for Proposed Functional Test Cases."""

from __future__ import annotations

import json
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from app.domain.models.proposed_test_models import (
    ProposedTestCase,
    ProposedTestStatus,
    ProposedTestType,
)
from app.infrastructure.workspace.workspace_paths import WorkspacePaths

logger = logging.getLogger(__name__)


class ProposedTestPlaywrightReporter:
    """Generates a standalone Playwright-style HTML report for test executions."""

    def __init__(self, job_id: str, report_dir: Path | None = None) -> None:
        self.job_id = job_id
        paths = WorkspacePaths(job_id)
        self.base_dir = paths.job_dir / "proposed-tests"
        self.report_dir = Path(report_dir) if report_dir else self.base_dir / "playwright-report"

    def clean_results(self) -> None:
        """Cleans and creates fresh report directory."""
        if self.report_dir.exists():
            shutil.rmtree(self.report_dir, ignore_errors=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate_html_report(
        self,
        tests: list[ProposedTestCase],
        selected_sources: list[str] | None = None,
    ) -> Path:
        """Generates a rich, standalone Playwright HTML Report."""
        self.report_dir.mkdir(parents=True, exist_ok=True)

        html_content = self._build_standalone_playwright_html(tests, selected_sources)
        index_file = self.report_dir / "index.html"
        index_file.write_text(html_content, encoding="utf-8")

        # Copy attachments to data directory for local serving
        data_dir = self.report_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        for t in tests:
            if t.type == ProposedTestType.UI:
                evidence_src_dir = self.base_dir / "evidence" / t.id
                
                sc_file = evidence_src_dir / "screenshot.png"
                if sc_file.exists():
                    shutil.copy2(sc_file, data_dir / f"{t.id}-screenshot.png")
                    
                video_file = evidence_src_dir / "video.webm"
                if video_file.exists():
                    shutil.copy2(video_file, data_dir / f"{t.id}-video.webm")
                    
                log_file = evidence_src_dir / "browser_steps.log"
                if log_file.exists():
                    shutil.copy2(log_file, data_dir / f"{t.id}-browser.log")

                trace_file = evidence_src_dir / "trace.zip"
                if trace_file.exists():
                    shutil.copy2(trace_file, data_dir / f"{t.id}-trace.zip")

        logger.info(f"[{self.job_id}] Generated standalone Playwright Report at: {index_file}")
        return self.report_dir

    def _build_standalone_playwright_html(
        self,
        tests: list[ProposedTestCase],
        selected_sources: list[str] | None = None,
    ) -> str:
        """Constructs an interactive Playwright HTML Report."""
        total = len(tests)
        passed = sum(1 for t in tests if t.status == ProposedTestStatus.PASSED)
        failed = sum(1 for t in tests if t.status == ProposedTestStatus.FAILED)
        skipped = sum(1 for t in tests if t.status == ProposedTestStatus.SKIPPED)

        total_duration_sec = sum(
            float(t.execution_result.duration.replace("s", "").strip()) 
            if t.execution_result and t.execution_result.duration else 0.15 
            for t in tests
        )
        duration_display = f"{total_duration_sec:.2f}s"
        now_display = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        test_payloads = []
        for t in tests:
            res = t.execution_result
            status_str = "passed" if t.status == ProposedTestStatus.PASSED else (
                "failed" if t.status == ProposedTestStatus.FAILED else "skipped"
            )

            steps = []
            if res and res.steps_execution:
                for sr in res.steps_execution:
                    steps.append({
                        "title": sr.description,
                        "status": "passed" if sr.status == ProposedTestStatus.PASSED else "failed",
                        "duration": sr.duration or "0.04s",
                        "error": sr.error,
                    })

            has_screenshot = False
            has_video = False
            has_trace = False
            
            if t.type == ProposedTestType.UI:
                evidence_src_dir = self.base_dir / "evidence" / t.id
                if (evidence_src_dir / "screenshot.png").exists():
                    has_screenshot = True
                if (evidence_src_dir / "video.webm").exists():
                    has_video = True
                if (evidence_src_dir / "trace.zip").exists():
                    has_trace = True

            test_payloads.append({
                "id": t.id,
                "title": t.title,
                "status": status_str,
                "duration": res.duration if res else "0.0s",
                "error": res.error if res else None,
                "steps": steps,
                "has_screenshot": has_screenshot,
                "has_video": has_video,
                "has_trace": has_trace,
            })

        tests_json = json.dumps(test_payloads).replace("</script>", "<\\/script>")

        return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Playwright HTML Report ({self.job_id})</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #ffffff;
            --text-color: #24292f;
            --border-color: #d0d7de;
            --header-bg: #f6f8fa;
            --pass-color: #2da44e;
            --fail-color: #cf222e;
            --skip-color: #8c959f;
        }}
        body {{
            font-family: 'Inter', -apple-system, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 0;
        }}
        .header {{
            background: var(--header-bg);
            border-bottom: 1px solid var(--border-color);
            padding: 20px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{ margin: 0; font-size: 20px; }}
        .stats {{ display: flex; gap: 20px; font-size: 14px; font-weight: 500; }}
        .stat-badge {{ padding: 4px 8px; border-radius: 12px; border: 1px solid var(--border-color); display: flex; align-items: center; gap: 6px; }}
        .stat-passed {{ color: var(--pass-color); border-color: var(--pass-color); background: rgba(45, 164, 78, 0.1); }}
        .stat-failed {{ color: var(--fail-color); border-color: var(--fail-color); background: rgba(207, 34, 46, 0.1); }}
        
        .container {{ padding: 40px; max-width: 1200px; margin: 0 auto; }}
        .test-list {{ list-style: none; padding: 0; margin: 0; }}
        .test-item {{
            border: 1px solid var(--border-color);
            border-radius: 6px;
            margin-bottom: 12px;
            overflow: hidden;
        }}
        .test-header {{
            padding: 16px 20px;
            background: var(--header-bg);
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
        }}
        .test-title {{ font-weight: 600; font-size: 15px; display: flex; align-items: center; gap: 10px; }}
        .status-indicator {{ width: 10px; height: 10px; border-radius: 50%; }}
        .status-passed {{ background: var(--pass-color); }}
        .status-failed {{ background: var(--fail-color); }}
        .test-body {{
            padding: 20px;
            border-top: 1px solid var(--border-color);
            display: none;
        }}
        .test-item.expanded .test-body {{ display: block; }}
        
        .step {{
            padding: 8px 0;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            font-size: 13px;
        }}
        .step:last-child {{ border-bottom: none; }}
        
        .error-box {{
            background: rgba(207, 34, 46, 0.05);
            border-left: 4px solid var(--fail-color);
            padding: 12px;
            margin: 16px 0;
            font-family: monospace;
            white-space: pre-wrap;
            font-size: 12px;
            color: var(--fail-color);
        }}
        
        .media-container {{
            margin-top: 20px;
            display: flex;
            gap: 20px;
            overflow-x: auto;
        }}
        .media-box {{
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 8px;
            background: var(--header-bg);
        }}
        .media-box h4 {{ margin: 0 0 8px 0; font-size: 13px; }}
        .media-box img, .media-box video {{ max-width: 400px; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Playwright HTML Report</h1>
        <div class="stats">
            <div>Duration: <strong>{duration_display}</strong></div>
            <div class="stat-badge stat-passed">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--pass-color);"></span>
                {passed} passed
            </div>
            <div class="stat-badge stat-failed">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--fail-color);"></span>
                {failed} failed
            </div>
            <div class="stat-badge">{skipped} skipped</div>
        </div>
    </div>
    
    <div class="container">
        <ul class="test-list" id="test-list"></ul>
    </div>

    <script>
        const tests = {tests_json};
        const list = document.getElementById('test-list');
        
        tests.forEach(t => {{
            const li = document.createElement('li');
            li.className = 'test-item';
            
            let stepsHtml = '';
            t.steps.forEach(s => {{
                stepsHtml += `
                    <div class="step">
                        <span>${{s.title}}</span>
                        <span style="color: #6e7781">${{s.duration}}</span>
                    </div>
                `;
            }});
            
            let errorHtml = '';
            if (t.error) {{
                errorHtml = `<div class="error-box">${{t.error}}</div>`;
            }}
            
            let mediaHtml = '';
            if (t.has_screenshot || t.has_video || t.has_trace) {{
                mediaHtml += '<div class="media-container">';
                if (t.has_screenshot) {{
                    mediaHtml += `
                        <div class="media-box">
                            <h4>Screenshot</h4>
                            <a href="data/${{t.id}}-screenshot.png" target="_blank">
                                <img src="data/${{t.id}}-screenshot.png" alt="Screenshot" loading="lazy">
                            </a>
                        </div>
                    `;
                }}
                if (t.has_video) {{
                    mediaHtml += `
                        <div class="media-box">
                            <h4>Video</h4>
                            <video src="data/${{t.id}}-video.webm" controls style="max-width:400px"></video>
                        </div>
                    `;
                }}
                if (t.has_trace) {{
                    mediaHtml += `
                        <div class="media-box" style="display:flex; flex-direction:column; justify-content:center; align-items:center; min-width:200px; padding:16px;">
                            <h4>Playwright Trace</h4>
                            <a href="data/${{t.id}}-trace.zip" download="${{t.id}}-trace.zip" style="display:inline-block; padding:8px 14px; background:#0969da; color:#fff; text-decoration:none; border-radius:6px; font-size:13px; font-weight:600; margin-top:8px;">
                                Download Trace (.zip)
                            </a>
                            <span style="font-size:11px; color:#57606a; margin-top:8px;">View with: trace.playwright.dev</span>
                        </div>
                    `;
                }}
                mediaHtml += '</div>';
            }}
            
            li.innerHTML = `
                <div class="test-header" onclick="this.parentElement.classList.toggle('expanded')">
                    <div class="test-title">
                        <div class="status-indicator status-${{t.status}}"></div>
                        ${{t.title}}
                    </div>
                    <div style="color: #6e7781; font-size: 13px;">${{t.duration}}</div>
                </div>
                <div class="test-body">
                    <div style="font-weight: 600; margin-bottom: 12px; font-size: 14px;">Test Steps</div>
                    ${{stepsHtml}}
                    ${{errorHtml}}
                    ${{mediaHtml}}
                </div>
            `;
            
            list.appendChild(li);
        }});
    </script>
</body>
</html>"""
