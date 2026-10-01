import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domain.models.proposed_test_models import ProposedTestCase, ProposedTestType

logger = logging.getLogger(__name__)

class PlaywrightTestGenerator:
    def __init__(self, job_dir: Path, api_base_url: str, ui_base_url: str):
        self.job_dir = job_dir
        self.api_base_url = api_base_url
        self.ui_base_url = ui_base_url
        self.pw_dir = job_dir / "proposed-tests" / "playwright-project"
        self.report_dir = job_dir / "proposed-tests" / "playwright-report"
        self.pw_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_project(self, tests: list[ProposedTestCase]) -> None:
        logger.info("Generating Playwright project...")
        config = f"""import {{ defineConfig }} from '@playwright/test';

export default defineConfig({{
  reporter: [
    ['html', {{
      outputFolder: '../playwright-report',
      open: 'never'
    }}],
    ['json', {{ outputFile: '../playwright-report/results.json' }}]
  ],
  use: {{
    trace: 'on',
    screenshot: 'on',
    video: 'on'
  }}
}});
"""
        (self.pw_dir / "playwright.config.ts").write_text(config, encoding="utf-8")
        
        tests_dir = self.pw_dir / "tests"
        if tests_dir.exists():
            shutil.rmtree(tests_dir)
        tests_dir.mkdir(parents=True, exist_ok=True)
        
        spec_content = "import { test, expect } from '@playwright/test';\n\n"
        
        for t in tests:
            title = t.title.replace("'", "\\'").replace("\n", " ")
            spec_content += f"test('{t.id} - {title}', async ({{ page, request }}) => {{\n"
            
            if t.type == ProposedTestType.API and t.api_spec:
                method = t.api_spec.method.lower()
                endpoint = t.api_spec.endpoint
                url = f"{self.api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
                headers = json.dumps(t.api_spec.headers or {})
                data = json.dumps(t.api_spec.request_body) if t.api_spec.request_body else "undefined"
                
                spec_content += f"  const response = await request.{method}('{url}', {{ headers: {headers}, data: {data} }});\n"
                spec_content += f"  expect(response.status()).toBe({t.api_spec.expected_status});\n"
            
            elif t.type == ProposedTestType.UI and t.ui_spec:
                url = f"{self.ui_base_url.rstrip('/')}/{t.ui_spec.target_route.lstrip('/')}"
                spec_content += f"  await page.goto('{url}');\n"
                for action in t.ui_spec.actions:
                    spec_content += f"  // Action: {action}\n"
                    # Simple fallback generator just as placeholder for actions
            
            spec_content += "});\n\n"
            
        (tests_dir / "generated.spec.ts").write_text(spec_content, encoding="utf-8")
        
        pkg = {
            "name": "playwright-tests",
            "version": "1.0.0",
            "devDependencies": {
                "@playwright/test": "^1.42.0"
            }
        }
        (self.pw_dir / "package.json").write_text(json.dumps(pkg, indent=2), encoding="utf-8")
        
    def run_tests(self) -> bool:
        """Executes the tests using Playwright CLI and returns True if generated successfully."""
        logger.info("Executing Playwright tests via npx playwright test...")
        try:
            subprocess.run(
                ["npm", "install"],
                cwd=str(self.pw_dir),
                check=True,
                capture_output=True,
                shell=True
            )
            # We don't check=True here because playwright test exits with 1 if tests fail!
            subprocess.run(
                ["npx", "playwright", "test", "--reporter=html"],
                cwd=str(self.pw_dir),
                capture_output=True,
                shell=True
            )
            return (self.report_dir / "index.html").exists()
        except Exception as e:
            logger.error(f"Failed to execute Playwright tests: {e}")
            return False

    def sync_results(self, tests: list[ProposedTestCase]) -> None:
        """Parses results.json and updates the status of the provided ProposedTestCase objects."""
        results_file = self.report_dir / "results.json"
        if not results_file.exists():
            return
            
        try:
            data = json.loads(results_file.read_text(encoding="utf-8"))
            status_map = {}
            for suite in data.get("suites", []):
                for spec in suite.get("specs", []):
                    title = spec.get("title", "")
                    if " - " in title:
                        test_id = title.split(" - ")[0]
                        # 'expected' or 'unexpected' or 'flaky'
                        ok = spec.get("ok", False)
                        status_map[test_id] = "PASSED" if ok else "FAILED"
                        
            for t in tests:
                if t.id in status_map:
                    from app.domain.models.proposed_test_models import ProposedTestStatus
                    status_str = status_map[t.id]
                    t.status = ProposedTestStatus.PASSED if status_str == "PASSED" else ProposedTestStatus.FAILED
                    # Ensure execution_result exists
                    if not t.execution_result:
                        from app.domain.models.proposed_test_models import ExecutionResult
                        t.execution_result = ExecutionResult()
                    t.execution_result.status = t.status
        except Exception as e:
            logger.error(f"Failed to sync Playwright results: {e}")
