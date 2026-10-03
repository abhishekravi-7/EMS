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
    def __init__(
        self,
        job_dir: Path,
        api_base_url: str,
        ui_base_url: str,
        data_resolver: Any | None = None,
        auth_manager: Any | None = None,
    ):
        self.job_dir = job_dir
        self.api_base_url = api_base_url
        self.ui_base_url = ui_base_url
        self.data_resolver = data_resolver
        self.auth_manager = auth_manager
        self.pw_dir = job_dir / "proposed-tests" / "playwright-project"
        self.report_dir = job_dir / "proposed-tests" / "playwright-report"
        self.pw_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def _esc(s: str) -> str:
        return str(s).replace("\\", "\\\\").replace("'", "\\'")

    @staticmethod
    def _build_selector(field: dict) -> str:
        """Selector priority: getByRole->getByLabel->getByText->data-testid->name->id->CSS."""
        e = PlaywrightTestGenerator._esc
        role = field.get("role", "")
        label = field.get("label", "")
        text = field.get("text", "")
        testid = field.get("data-testid", "")
        name = field.get("name", "")
        fid = field.get("id", "")
        css = field.get("css", "")
        if role:
            hint = label or name or ""
            opt = f", {{ name: '{e(hint)}' }}" if hint else ""
            return f"page.getByRole('{e(role)}'{opt})"
        if label:
            return f"page.getByLabel('{e(label)}')"
        if text:
            return f"page.getByText('{e(text)}')"
        if testid:
            return f"page.getByTestId('{e(testid)}')"
        if name:
            return "page.locator('[name=\"" + e(name) + "\"]')"
        if fid:
            return f"page.locator('#{e(fid)}')"
        if css:
            return f"page.locator('{e(css)}')"
        return ""

    @staticmethod
    def _dom_action(field: dict, sel: str) -> str:
        """DOM-type-driven action. Never fill() on checkboxes/radios/selects."""
        e = PlaywrightTestGenerator._esc
        ftype = (field.get("type", "") or "").lower()
        tag = (field.get("tag", "") or "").lower()
        value = field.get("value", "")
        if not sel:
            return ""
        if ftype == "checkbox" or tag == "checkbox":
            verb = "check" if value else "uncheck"
            return f"  await {sel}.{verb}();"
        if ftype == "radio" or tag == "radio":
            return f"  await {sel}.check();"
        if ftype == "select" or tag == "select":
            return f"  await {sel}.selectOption('{e(str(value))}');"
        if ftype == "file":
            return f"  await {sel}.setInputFiles('{e(str(value))}');"
        return f"  await {sel}.fill('{e(str(value))}');"

    @staticmethod
    def _action_to_ts(action: str) -> str:
        import re as _re
        e = PlaywrightTestGenerator._esc
        a = action.strip()
        m = _re.match(r"(?:click|press)\s+(.+)", a, _re.IGNORECASE)
        if m:
            return f"  await page.getByText('{e(m.group(1).strip())}').click();"
        m = _re.match(r"fill\s+(.+?)\s+with\s+(.+)", a, _re.IGNORECASE)
        if m:
            return f"  await page.getByLabel('{e(m.group(1).strip())}').fill('{e(m.group(2).strip())}');"
        m = _re.match(r"navigate\s+to\s+(.+)", a, _re.IGNORECASE)
        if m:
            return f"  await page.goto('{e(m.group(1).strip())}');"
        return f"  // TODO: manual verification required for action: {a}"

    def generate_project(self, tests: list[ProposedTestCase]) -> None:
        logger.info("Generating Playwright project (%d tests)...", len(tests))
        # Relative report folder from pw_dir to report_dir
        try:
            rel_report = os.path.relpath(self.report_dir, self.pw_dir).replace("\\", "/")
        except Exception:
            rel_report = "../playwright-report"

        config_lines = [
            "import { defineConfig } from '@playwright/test';",
            "",
            "export default defineConfig({",
            "  reporter: [",
            "    ['html', {",
            f"      outputFolder: '{rel_report}',",
            "      open: 'never'",
            "    }],",
            f"    ['json', {{ outputFile: '{rel_report}/results.json' }}]",
            "  ],",
            "  use: {",
            "    trace: 'retain-on-failure',",
            "    screenshot: 'only-on-failure',",
            "    video: 'retain-on-failure'",
            "  },",
            "  timeout: 30000,",
            "  retries: 0",
            "});",
            "",
        ]
        (self.pw_dir / "playwright.config.ts").write_text("\n".join(config_lines), encoding="utf-8")

        tests_dir = self.pw_dir / "tests"
        if tests_dir.exists():
            shutil.rmtree(tests_dir)
        tests_dir.mkdir(parents=True, exist_ok=True)

        spec_lines = ["import { test, expect } from '@playwright/test';", ""]

        for t in tests:
            safe_title = t.title.replace("'", "\\'").replace("\n", " ")[:120]
            spec_lines.append(f"test('{t.id} - {safe_title}', async ({{ page, request }}) => {{")

            # Check if test was already blocked or marked for review
            from app.domain.models.proposed_test_models import ProposedTestStatus
            if t.status in (ProposedTestStatus.BLOCKED, ProposedTestStatus.BLOCKED_AUTHENTICATION, ProposedTestStatus.REVIEW_REQUIRED):
                msg = t.execution_result.error if (t.execution_result and t.execution_result.error) else f"Skipped with status {t.status.value}"
                spec_lines.append(f"  test.skip(true, '{self._esc(msg)}');")
                spec_lines.append("});")
                spec_lines.append("")
                continue

            if t.type == ProposedTestType.API and t.api_spec:
                spec = t.api_spec
                method = spec.method.lower()
                endpoint = spec.endpoint

                # Dynamically resolve path parameters using DynamicDataResolver if provided
                if self.data_resolver:
                    resolved = self.data_resolver.resolve_endpoint(endpoint, test_data=spec.request_body, base_url=self.api_base_url)
                    endpoint = resolved.endpoint
                    if not resolved.is_resolved and ("{" in endpoint or "}" in endpoint):
                        t.status = ProposedTestStatus.REVIEW_REQUIRED
                        reason = resolved.issue or f"Unresolved path variable in {spec.endpoint}"
                        spec_lines.append(f"  test.skip(true, 'REVIEW_REQUIRED: {self._esc(reason)}');")
                        spec_lines.append("});")
                        spec_lines.append("")
                        continue

                url = f"{self.api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
                hdrs = json.dumps(spec.headers or {"Content-Type": "application/json", "Accept": "application/json"})
                src = getattr(spec, "expected_status_source", "not set")
                if spec.request_body:
                    spec_lines.append(f"  const response = await request.{method}('{url}', {{")
                    spec_lines.append(f"    headers: {hdrs},")
                    spec_lines.append(f"    data: {json.dumps(spec.request_body)}")
                    spec_lines.append("  });")
                else:
                    spec_lines.append(f"  const response = await request.{method}('{url}', {{ headers: {hdrs} }});")
                spec_lines.append(f"  expect(response.status()).toBe({spec.expected_status}); // source: {src}")
                for assertion in spec.assertions or []:
                    spec_lines.append(f"  // assertion: {assertion}")

            elif t.type == ProposedTestType.UI and t.ui_spec:
                spec = t.ui_spec
                url = f"{self.ui_base_url.rstrip('/')}/{spec.target_route.lstrip('/')}"
                # If app uses localStorage authentication, inject token
                spec_lines.append("  await page.addInitScript(() => { try { localStorage.setItem('isAuthenticated', 'true'); } catch (e) {} });")
                spec_lines.append(f"  await page.goto('{url}');")
                for field in spec.input_fields or []:
                    sel = self._build_selector(field)
                    if sel:
                        line = self._dom_action(field, sel)
                        if line:
                            spec_lines.append(line)
                    else:
                        spec_lines.append(f"  // REVIEW_REQUIRED: no selector evidence for field {field}")
                for action in spec.actions or []:
                    spec_lines.append(self._action_to_ts(action))
                for el in spec.expected_elements or []:
                    target = self._esc(el.split(",")[0].strip())
                    spec_lines.append(f"  await expect(page.locator('{target}')).toBeVisible({{ timeout: 5000 }});")

            else:
                spec_lines.append(f"  // UNIT test {t.id} — not executable via Playwright browser")
                spec_lines.append("  test.skip();")

            spec_lines.append("});")  
            spec_lines.append("")

        (tests_dir / "functional.generated.spec.ts").write_text("\n".join(spec_lines), encoding="utf-8")

        pkg = {
            "name": "playwright-functional-tests",
            "version": "1.0.0",
            "devDependencies": {"@playwright/test": "^1.42.0", "typescript": "^5.0.0"},
        }
        (self.pw_dir / "package.json").write_text(json.dumps(pkg, indent=2), encoding="utf-8")
        
    def run_tests(self, test_count: int = 10) -> bool:
        """Installs deps, ensures chromium is installed, then runs playwright test.
        Returns True only when playwright-report/index.html actually exists.
        Uses per-test timeout budget to avoid hanging the FastAPI thread.
        """
        # Budget: 20s per test, minimum 120s, maximum 600s
        budget_s = max(120, min(test_count * 20, 600))

        logger.info("npm install (playwright project, timeout=120s)...")
        try:
            subprocess.run(
                ["npm", "install"],
                cwd=str(self.pw_dir),
                check=True,
                capture_output=True,
                shell=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            logger.error("npm install timed out after 120s — aborting Playwright run")
            return False
        except subprocess.CalledProcessError as exc:
            logger.error("npm install failed: %s", (exc.stderr or b"").decode("utf-8", errors="ignore"))
            return False

        # Ensure Chromium is installed (first-run or CI environment)
        logger.info("npx playwright install chromium (timeout=120s)...")
        try:
            subprocess.run(
                ["npx", "playwright", "install", "chromium"],
                cwd=str(self.pw_dir),
                capture_output=True,
                shell=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            logger.warning("playwright install chromium timed out — will attempt test run anyway")
        except Exception as exc:
            logger.warning("playwright install chromium error (non-fatal): %s", exc)

        logger.info("npx playwright test --reporter=html (timeout=%ds for %d tests)...", budget_s, test_count)
        run_env = os.environ.copy()
        run_env["PLAYWRIGHT_HTML_REPORT"] = str(self.report_dir)
        run_env["PLAYWRIGHT_JSON_OUTPUT_NAME"] = str(self.report_dir / "results.json")
        run_env["PW_TEST_HTML_REPORT_OPEN"] = "never"
        run_env["CI"] = "1"
        try:
            # playwright exits 1 when tests fail — that is expected, do NOT use check=True
            res = subprocess.run(
                [
                    "npx", "playwright", "test",
                    "--reporter=html,json",
                    "--workers=2",          # cap parallelism so the host isn't overwhelmed
                    f"--timeout=15000",     # 15s per individual test step
                ],
                cwd=str(self.pw_dir),
                capture_output=True,
                stdin=subprocess.DEVNULL,
                shell=True,
                timeout=budget_s,
                env=run_env,
            )
            stdout = (res.stdout or b"").decode("utf-8", errors="ignore")
            stderr = (res.stderr or b"").decode("utf-8", errors="ignore")
            if stdout:
                logger.info("[PW] %s", stdout[:3000])
            if stderr and res.returncode not in (0, 1):
                logger.warning("[PW STDERR] %s", stderr[:2000])
        except subprocess.TimeoutExpired:
            logger.error(
                "npx playwright test timed out after %ds (%d tests). "
                "Partial report may still exist.",
                budget_s, test_count,
            )
            # Don't return False immediately — a partial report may have been written
        except Exception as exc:
            logger.error("Playwright run error: %s", exc)
            return False

        # Ensure report is synced to self.report_dir if it was generated in self.pw_dir / "playwright-report"
        inner_rep = self.pw_dir / "playwright-report"
        if inner_rep.is_dir() and not (self.report_dir / "index.html").is_file():
            try:
                self.report_dir.mkdir(parents=True, exist_ok=True)
                shutil.copytree(inner_rep, self.report_dir, dirs_exist_ok=True)
            except Exception as copy_exc:
                logger.warning("Error copying inner playwright-report to %s: %s", self.report_dir, copy_exc)

        # Also copy results.json if found in inner_rep or pw_dir
        for cand in [inner_rep / "results.json", self.pw_dir / "results.json"]:
            if cand.is_file() and not (self.report_dir / "results.json").is_file():
                try:
                    self.report_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(cand, self.report_dir / "results.json")
                except Exception:
                    pass

        report_index = self.report_dir / "index.html"
        if report_index.is_file():
            logger.info("Native Playwright HTML report: %s", report_index)
            return True
        logger.error("Playwright report NOT found at %s — check outputFolder in playwright.config.ts", report_index)
        return False

    def sync_results(self, tests: list[ProposedTestCase]) -> None:
        """Parses results.json and updates status from real Playwright outcomes.
        Never overwrites BLOCKED / BLOCKED_AUTHENTICATION / REVIEW_REQUIRED.
        """
        from app.domain.models.proposed_test_models import ExecutionResult, ProposedTestStatus

        results_file = self.report_dir / "results.json"
        if not results_file.exists():
            for alt in [self.pw_dir / "playwright-report" / "results.json", self.pw_dir / "results.json"]:
                if alt.exists():
                    results_file = alt
                    break

        if not results_file.exists():
            logger.warning("Playwright results.json not found — sync skipped.")
            return

        try:
            data = json.loads(results_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to parse results.json: %s", exc)
            return

        status_map: dict = {}
        duration_map: dict = {}

        def _walk(suites: list) -> None:
            for suite in suites:
                for spec in suite.get("specs", []):
                    title = spec.get("title", "")
                    if " - " in title:
                        tid = title.split(" - ")[0].strip()
                        status_map[tid] = spec.get("ok", False)
                        dur_ms: float = sum(
                            r.get("duration", 0)
                            for t_item in spec.get("tests", [])
                            for r in t_item.get("results", [])
                        )
                        duration_map[tid] = dur_ms / 1000.0
                _walk(suite.get("suites", []))

        _walk(data.get("suites", []))

        # Statuses that must NOT be overwritten by Playwright outcome
        blocked_statuses = {
            ProposedTestStatus.BLOCKED,
            ProposedTestStatus.BLOCKED_AUTHENTICATION,
            ProposedTestStatus.REVIEW_REQUIRED,
        }

        for t in tests:
            if t.id not in status_map or t.status in blocked_statuses:
                continue
            new_status = ProposedTestStatus.PASSED if status_map[t.id] else ProposedTestStatus.FAILED
            t.status = new_status
            if not t.execution_result:
                t.execution_result = ExecutionResult()
            t.execution_result.status = new_status
            t.execution_result.duration = f"{duration_map.get(t.id, 0):.2f}s"
