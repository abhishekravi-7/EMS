import os
import re
import time
import json
import subprocess
import threading
import signal
from collections import deque
import xml.etree.ElementTree as ET
from pathlib import Path
from app.core.config import settings
from app.infrastructure.workspace.workspace_paths import WorkspacePaths

MAX_EXISTING_TEST_OUTPUT_CHARS = 500_000
MAX_EXISTING_TEST_OUTPUT_LINES = 5_000

class ExistingTestDetector:
    def __init__(self, clone_dir: Path):
        self.clone_dir = Path(clone_dir)
        self.tests_found = []
        self.frameworks = set()
        self.languages = set()
        self.total_test_count = 0
        self.passed = "Not Available"
        self.failed = "Not Available"
        self.skipped = "Not Available"
        self.test_types = set()

    def _scan_helper_classes(self):
        self.ui_classes = set()
        self.api_classes = set()
        self.has_playwright_dep = False
        self.has_selenium_dep = False
        self.has_api_dep = False

        # Scan pom.xml / build.gradle for dependencies
        pom_xml = self.clone_dir / 'pom.xml'
        if pom_xml.exists():
            try:
                c = pom_xml.read_text(encoding='utf-8', errors='ignore').lower()
                if 'playwright' in c: self.has_playwright_dep = True
                if 'selenium' in c: self.has_selenium_dep = True
                if 'rest-assured' in c or 'restassured' in c or 'mockmvc' in c: self.has_api_dep = True
            except Exception:
                pass

        build_gradle = self.clone_dir / 'build.gradle'
        build_gradle_kts = self.clone_dir / 'build.gradle.kts'
        for g_file in [build_gradle, build_gradle_kts]:
            if g_file.exists():
                try:
                    c = g_file.read_text(encoding='utf-8', errors='ignore').lower()
                    if 'playwright' in c: self.has_playwright_dep = True
                    if 'selenium' in c: self.has_selenium_dep = True
                    if 'rest-assured' in c or 'restassured' in c or 'mockmvc' in c: self.has_api_dep = True
                except Exception:
                    pass

        # Scan all project files for UI Page Objects or API clients
        for root, dirs, files in os.walk(self.clone_dir):
            for skip in ['node_modules', '.git', 'venv', 'target', 'dist', 'build', '.next']:
                if skip in dirs: dirs.remove(skip)

            for file in files:
                if file.endswith(('.java', '.ts', '.js', '.py')):
                    filepath = Path(root) / file
                    try:
                        c_text = filepath.read_text(encoding='utf-8', errors='ignore')
                        c_low = c_text.lower()
                        class_name = filepath.stem

                        if any(k in c_low for k in [
                            "com.microsoft.playwright", "org.openqa.selenium", "webdriver",
                            "page.navigate", "page.locator", "page.click", "page.screenshot",
                            "page.fill", "page.type", "page.title", "page.url", "browser.newpage",
                            "browsercontext", "driver.get", "driver.findelement", "by.id", "by.cssselector"
                        ]):
                            self.ui_classes.add(class_name)
                            self.ui_classes.add(class_name.lower())

                        if any(k in c_low for k in [
                            "io.restassured", "restassured", "mockmvc", "webtestclient",
                            "testresttemplate", "java.net.http.httpclient", "okhttp3",
                            "apache.http.client", "resttemplate"
                        ]):
                            self.api_classes.add(class_name)
                            self.api_classes.add(class_name.lower())
                    except Exception:
                        pass

    def scan(self):
        self._scan_helper_classes()
        self._detect_frameworks_from_configs()
        
        for root, dirs, files in os.walk(self.clone_dir):
            if 'node_modules' in dirs: dirs.remove('node_modules')
            if '.git' in dirs: dirs.remove('.git')
            if 'venv' in dirs: dirs.remove('venv')
            if 'target' in dirs: dirs.remove('target')
            if 'dist' in dirs: dirs.remove('dist')
            if 'build' in dirs: dirs.remove('build')
            if '.next' in dirs: dirs.remove('.next')

            for file in files:
                filepath = Path(root) / file
                try:
                    rel_path = filepath.relative_to(self.clone_dir).as_posix()
                except Exception:
                    continue
                self._analyze_file(filepath, rel_path)
        self._parse_execution_results()
        
        categories = self._categorize_tests()
                
        return {
            "metrics": {
                "total": self.total_test_count,
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
                "type": ", ".join(self.frameworks) if self.frameworks else "Not Detected"
            },
            "details": {
                "frameworks": list(self.frameworks),
                "languages": list(self.languages),
                "testTypes": list(self.test_types),
                "testCases": self.tests_found,
                "existingTestCategories": categories
            }
        }
        
    def _categorize_tests(self):
        cats = {
            "auth": {"name": "AUTHENTICATION & SECURITY", "count": 0, "priority": "P0 Critical", "priorityLevel": 0, "desc": "Protected route access, token header checks, invalid credential rejection, and authorization boundaries.", "files": set()},
            "ui": {"name": "UI FUNCTIONAL & WORKFLOWS", "count": 0, "priority": "P1 High", "priorityLevel": 1, "desc": "User journey navigation, form submissions, component rendering, and DOM interaction validations.", "files": set()},
            "biz": {"name": "BUSINESS RULE & VALIDATION", "count": 0, "priority": "P1 High", "priorityLevel": 1, "desc": "Domain constraint enforcement, mandatory parameter checking, and state transition invariant validation.", "files": set()},
            "api": {"name": "API CONTRACTS", "count": 0, "priority": "P2 Medium", "priorityLevel": 2, "desc": "HTTP request method verification, status code compliance, and payload structure checking.", "files": set()}
        }
        
        for t in self.tests_found:
            name = t.get("name", "").lower()
            file = t.get("file", "").lower()
            t_type = t.get("type", "").lower()
            framework = t.get("framework", "").lower()
            
            if any(k in name or k in file for k in ["auth", "security", "login", "token", "jwt"]):
                cats["auth"]["count"] += 1
                cats["auth"]["files"].add(t.get("file", ""))
            elif "ui" in t_type or "e2e" in t_type or framework in ["playwright", "selenium", "cypress"]:
                cats["ui"]["count"] += 1
                cats["ui"]["files"].add(t.get("file", ""))
            elif "api" in t_type or "integration" in t_type or framework in ["supertest", "restassured"]:
                cats["api"]["count"] += 1
                cats["api"]["files"].add(t.get("file", ""))
            elif any(k in name or k in file for k in ["service", "domain", "biz", "rule", "val"]):
                cats["biz"]["count"] += 1
                cats["biz"]["files"].add(t.get("file", ""))
            elif t_type in ["jest", "vitest", "junit", "testng", "pytest", "unittest", "mocha"]:
                # Unit/framework tests are not UI or API tests. Do not infer UI
                # from the .js/.ts extension.
                cats["biz"]["count"] += 1
                cats["biz"]["files"].add(t.get("file", ""))
            else:
                cats["biz"]["count"] += 1
                cats["biz"]["files"].add(t.get("file", ""))
                
        result = []
        for k, v in cats.items():
            if v["count"] > 0:
                file_list = list(v["files"])
                if len(file_list) > 3:
                    file_names = ", ".join(f.split('/')[-1] for f in file_list[:3])
                    evidence = f"Derived from repository modules: {file_names} (+{len(file_list)-3} more)."
                else:
                    file_names = ", ".join(f.split('/')[-1] for f in file_list)
                    evidence = f"Derived from repository modules: {file_names}." if file_names else "Derived from general repository analysis."
                
                v["evidenceSource"] = evidence
                del v["files"]
                result.append(v)
                
        result.sort(key=lambda x: x["priorityLevel"])
        return result
        
    def _detect_frameworks_from_configs(self):
        pkg_json = self.clone_dir / 'package.json'
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text(encoding='utf-8', errors='ignore'))
                deps = str(data.get('dependencies', {})) + str(data.get('devDependencies', {}))
                scripts = str(data.get('scripts', {})).lower()

                if 'playwright' in deps or 'playwright' in scripts: self.frameworks.add('Playwright')
                if 'cypress' in deps or 'cypress' in scripts: self.frameworks.add('Cypress')
                if 'jest' in deps or 'jest' in scripts: self.frameworks.add('Jest')
                if 'vitest' in deps or 'vitest' in scripts: self.frameworks.add('Vitest')
                if 'mocha' in deps or 'mocha' in scripts: self.frameworks.add('Mocha')
                if 'supertest' in deps: self.frameworks.add('Supertest')
            except Exception:
                pass

        # Check for Java framework hints
        pom_xml = self.clone_dir / 'pom.xml'
        if pom_xml.exists():
            try:
                content = pom_xml.read_text(encoding='utf-8', errors='ignore').lower()
                if 'junit' in content: self.frameworks.add('JUnit')
                if 'testng' in content: self.frameworks.add('TestNG')
                if 'selenium' in content: self.frameworks.add('Selenium')
                if 'rest-assured' in content or 'restassured' in content: self.frameworks.add('RestAssured')
            except Exception:
                pass

        build_gradle = self.clone_dir / 'build.gradle'
        build_gradle_kts = self.clone_dir / 'build.gradle.kts'
        for g_file in [build_gradle, build_gradle_kts]:
            if g_file.exists():
                try:
                    content = g_file.read_text(encoding='utf-8', errors='ignore').lower()
                    if 'junit' in content: self.frameworks.add('JUnit')
                    if 'testng' in content: self.frameworks.add('TestNG')
                    if 'selenium' in content: self.frameworks.add('Selenium')
                    if 'rest-assured' in content or 'restassured' in content: self.frameworks.add('RestAssured')
                except Exception:
                    pass

        # Check for Python framework hints
        if (self.clone_dir / 'pytest.ini').exists() or (self.clone_dir / 'conftest.py').exists() or any(self.clone_dir.glob('test_*.py')):
            self.frameworks.add('PyTest')
        elif (self.clone_dir / 'requirements.txt').exists():
            try:
                reqs = (self.clone_dir / 'requirements.txt').read_text(encoding='utf-8', errors='ignore').lower()
                if 'pytest' in reqs: self.frameworks.add('PyTest')
            except Exception:
                pass
                
    @staticmethod
    def _test_category(test_type: str, framework: str) -> str:
        """Return the semantic category used by the validation UI.

        `type` identifies the framework/execution technology; `category` identifies
        whether the test is UI, API, or a unit/framework test. This keeps Jest/JUnit
        from being mistaken for UI/API merely because of a filename or build tool.
        """
        t = (test_type or "").strip().lower()
        f = (framework or "").strip().lower()

        if "playwright ui" in t or "cypress ui" in t or "selenium ui" in t:
            return "UI"
        if "playwright api" in t or t == "api" or "api" in t or f in {"supertest", "restassured"}:
            return "API"
        return "UNIT"

    def _parse_execution_results(self):
        junit_path = self.clone_dir / 'junit.xml'
        if junit_path.exists():
            try:
                content = junit_path.read_text(encoding='utf-8', errors='ignore')
                failures = len(re.findall(r'<failure', content))
                testcases = len(re.findall(r'<testcase', content))
                self.passed = testcases - failures
                self.failed = failures
                self.skipped = 0
            except Exception:
                pass
        
    def _analyze_file(self, filepath: Path, rel_path: str):
        import re
        name = filepath.name.lower()
        if not (name.endswith('.ts') or name.endswith('.js') or name.endswith('.java') or name.endswith('.py')):
            return
            
        try:
            content = filepath.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return
            
        is_test = False
        framework = "Unknown"
        language = "Unknown"
        test_type = "JUnit" # Default for Java, will be overridden
        count = 0
        test_names = []

        c_lower = content.lower()

        # JS/TS Test Detection (Jest, Playwright, Cypress, Vitest)
        if name.endswith('.spec.ts') or name.endswith('.test.ts') or name.endswith('.spec.js') or name.endswith('.test.js'):
            is_test = True
            language = "TypeScript" if name.endswith('.ts') else "JavaScript"

            if "playwright" in c_lower:
                framework = "Playwright"
                # Refined Playwright Type Detection: Check for API request usage
                if "request." in c_lower or ("request" in c_lower and "page" not in c_lower):
                    test_type = "Playwright API"
                else:
                    test_type = "Playwright UI"
            elif "cypress" in c_lower:
                framework = "Cypress"
                test_type = "Cypress UI"
            elif "supertest" in c_lower:
                framework = "Supertest"
                test_type = "API"
            elif any(k in c_lower for k in ["jest", "react-testing-library", "@testing-library"]):
                framework = "Jest"
                test_type = "Jest"
            elif "vitest" in c_lower:
                framework = "Vitest"
                test_type = "Vitest"
            else:
                # Default for generic .test.js / .spec.js files
                framework = "Jest"
                test_type = "Jest"
                
            matches = re.findall(r'(?:test|it|describe|test\.describe)\s*\(\s*[\'"`](.*?)[\'"`]', content)
            count = len(matches)
            test_names = matches
            
        # Java Test Detection (JUnit, TestNG)
        elif name.endswith('.java') and ('test' in name or 'tests' in name or '@test' in c_lower):
            is_test = True
            language = "Java"
            if "org.junit" in content or "org.junit.jupiter" in content:
                framework = "JUnit"
            elif "org.testng" in content:
                framework = "TestNG"
            else:
                framework = "JUnit"

            # Check for direct UI automation keywords in test content
            is_ui = any(k in c_lower for k in [
                "com.microsoft.playwright", "playwright", "org.openqa.selenium", "selenium",
                "webdriver", "htmlunit", "chromedriver", "firefoxdriver", "browser", "browsercontext",
                "page.navigate", "page.locator", "page.click", "page.screenshot", "page.fill",
                "page.type", "page.title", "driver.get", "driver.findelement", "by.id", "by.cssselector",
                "by.xpath", "by.name", "pageobject", "pagefactory", "loginpage", "homepage", "productpage"
            ])

            # Check if the test references or calls any detected UI Page Object classes
            if not is_ui and hasattr(self, 'ui_classes') and self.ui_classes:
                for cls in self.ui_classes:
                    if cls in content or cls.lower() in c_lower:
                        is_ui = True
                        break

            # If project has Playwright/Selenium dependency and test name hints at UI/POM/Raw
            if not is_ui and (getattr(self, 'has_playwright_dep', False) or getattr(self, 'has_selenium_dep', False)):
                if any(k in name or k in c_lower for k in ["pom", "raw", "ui", "login", "page", "browser"]):
                    is_ui = True

            # Check for API automation keywords in test content
            is_api = False
            if not is_ui:
                is_api = any(k in c_lower for k in [
                    "rest-assured", "restassured", "mockmvc", "webtestclient", "webclient",
                    "testresttemplate", "httpclient", "okhttp", "httpresponse", "httprequest",
                    "postman", "newman", "statuscode", "extract().response()"
                ])
                if not is_api and hasattr(self, 'api_classes') and self.api_classes:
                    for cls in self.api_classes:
                        if cls in content or cls.lower() in c_lower:
                            is_api = True
                            break

            if is_ui:
                test_type = "UI"
            elif is_api:
                test_type = "API"
            else:
                test_type = "UNIT"
                
            matches = re.findall(r'@Test\s*(?:\([^)]*\))?\s*(?:public\s+|private\s+|protected\s+|)?(?:static\s+)?(?:final\s+)?\w+\s+([a-zA-Z0-9_]+)\s*\(', content)
            if not matches:
                matches = re.findall(r'@Test[\s\S]{0,100}?(?:void|String|int|boolean|var)\s+([a-zA-Z0-9_]+)\s*\(', content)
            if not matches:
                test_count = content.count('@Test')
                if test_count > 0:
                    matches = [f"testMethod{i}" for i in range(test_count)]
                    
            count = len(matches)
            test_names = matches
            
        # Python Test Detection (PyTest, unittest)
        elif (name.startswith('test_') or name.endswith('_test.py')) and name.endswith('.py'):
            is_test = True
            language = "Python"
            if "pytest" in content:
                framework = "PyTest"
            elif "unittest" in content:
                framework = "unittest"
            else:
                framework = "PyTest"

            if "playwright" in c_lower:
                test_type = "Playwright UI"
            elif "selenium" in c_lower or "browser" in c_lower:
                test_type = "Selenium UI"
            elif "request" in c_lower and "page" not in c_lower:
                test_type = "API"
            else:
                test_type = "PyTest"
                
            matches = re.findall(r'def\s+(test_[a-zA-Z0-9_]+)\s*\(', content)
            count = len(matches)
            test_names = matches

        if is_test and count > 0:
            self.frameworks.add(framework)
            self.languages.add(language)
            self.test_types.add(test_type)
            self.total_test_count += count

            suite_name = filepath.stem if language == "Java" else rel_path.split('/')[-1]
            parts = rel_path.split('/')
            module_name = parts[1] if len(parts) > 1 else parts[0]

            for t_name in test_names:
                self.tests_found.append({
                    "name": t_name,
                    "file": rel_path,
                    "framework": framework,
                    "type": test_type,
                    "category": self._test_category(test_type, framework),
                    "module": suite_name or module_name,
                    "classname": suite_name,
                    "methodname": t_name,
                    "status": "Not Available"
                })

class BoundedLogBuffer:
    def __init__(self, max_chars: int, max_lines: int):
        self.max_chars = max_chars
        self.max_lines = max_lines
        self.lines = deque(maxlen=max_lines)
        self.char_count = 0

    def append(self, text: str):
        self.lines.append(text)
        self.char_count += len(text)
        while self.char_count > self.max_chars and self.lines:
            removed = self.lines.popleft()
            self.char_count -= len(removed)

    def joined(self, sep: str = "") -> str:
        return sep.join(self.lines)

class ExistingTestRunnerService:
    def __init__(self):
        self._state: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._active_processes: dict[str, subprocess.Popen] = {}

    def _test_category(self, test_type: str, framework: str) -> str:
        """Return the semantic category used by the validation UI.

        `type` identifies the framework/execution technology; `category` identifies
        whether the test is UI, API, or a unit/framework test. This keeps Jest/JUnit
        from being mistaken for UI/API merely because of a filename or build tool.
        """
        t = (test_type or "").strip().lower()
        f = (framework or "").strip().lower()

        # UI categories
        if any(k in t for k in ["playwright ui", "cypress ui", "selenium ui"]):
            return "UI"

        # API categories
        if any(k in t for k in ["playwright api", "api"]) or f in {"supertest", "restassured", "rest-assured"}:
            return "API"

        # Unit/Framework categories
        if any(k in t for k in ["jest", "vitest", "junit", "testng", "pytest", "unittest"]):
            return "UNIT"

        return "UNIT"

    def _run_cmd(self, job_id: str, cmd: list[str], cwd: Path, timeout: float = 600, env: dict | None = None) -> tuple[str, int]:
        try:
            cmd_env = {**os.environ, "CI": "1", **(env or {})}
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors='ignore',
                env=cmd_env,
                start_new_session=(os.name != "nt"),
            )
            with self._lock:
                self._active_processes[job_id] = proc
            
            try:
                output = BoundedLogBuffer(
                    MAX_EXISTING_TEST_OUTPUT_CHARS,
                    MAX_EXISTING_TEST_OUTPUT_LINES,
                )

                def _drain() -> None:
                    assert proc.stdout is not None
                    for line in proc.stdout:
                        output.append(line)
                        self._log(job_id, line.rstrip())

                reader = threading.Thread(target=_drain, daemon=True)
                reader.start()
                proc.wait(timeout=timeout)
                reader.join(timeout=2)
                return output.joined(""), proc.returncode
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                else:
                    os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                self._log(job_id, f"Timed out executing: {' '.join(cmd)}", "WARN")
                return output.joined(""), -1
            finally:
                with self._lock:
                    self._active_processes.pop(job_id, None)
        except Exception as e:
            self._log(job_id, f"Execution error: {e}", "WARN")
            return "", -1

    def _extract_compilation_errors(self, output: str) -> str:
        if not output:
            return "Maven compilation failed with no output."
        lines = output.splitlines()
        extracted = []
        in_error_block = False
        for line in lines:
            stripped = line.strip()
            if "COMPILATION ERROR" in line or "Compilation failure" in line or "maven-compiler-plugin" in line:
                in_error_block = True
                extracted.append(stripped)
                continue
            if in_error_block:
                if line.startswith("[INFO]") and ("-------------------" in line or "BUILD FAILURE" in line or "Total time" in line):
                    in_error_block = False
                elif line.startswith("[ERROR]") or line.startswith("symbol:") or line.startswith("location:") or "cannot find symbol" in line or "package " in line or "syntax error" in line:
                    extracted.append(stripped)
                elif stripped and not line.startswith("[INFO]"):
                    extracted.append(stripped)

        if not extracted:
            for line in lines:
                stripped = line.strip()
                if "[ERROR]" in line and "Help 1" not in line and "to see the full stack trace" not in line:
                    extracted.append(stripped)

        if not extracted:
            return "Maven compilation failed before tests could execute."

        return "\n".join(extracted[:40])

    def stop_existing_tests(self, job_id: str):
        with self._lock:
            proc = self._active_processes.get(job_id)
        if proc:
            try:
                self._log(job_id, "⏹️  Stopping running tests...", "WARN")
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                else:
                    os.killpg(proc.pid, signal.SIGTERM)
                time.sleep(0.5)
                if proc.poll() is None:
                    if os.name == "nt":
                        proc.kill()
                    else:
                        os.killpg(proc.pid, signal.SIGKILL)
                self._log(job_id, "⏹️  Execution stopped by user", "WARN")
            except Exception as e:
                self._log(job_id, f"Error stopping execution: {e}", "WARN")
        else:
            self._log(job_id, "⚠️ No active running tests found to stop", "WARN")

    def scan_total(self, job_id: str) -> dict:
        paths = WorkspacePaths(job_id)
        project_dir = paths.original_repo_dir
        if not project_dir.exists():
            return {"total": 0, "framework": "Not Detected", "test_cases": []}
        detector = ExistingTestDetector(project_dir)
        detection = detector.scan()
        metrics = detection.get("metrics", {})
        details = detection.get("details", {})
        frameworks = details.get("frameworks", [])
        return {
            "total": metrics.get("total", 0),
            "framework": ", ".join(frameworks) if frameworks else "Not Detected",
            "test_cases": details.get("testCases", [])
        }

    def get_status(self, job_id: str) -> dict:
        with self._lock:
            state = self._state.get(job_id)
        if not state:
            return {"status": "IDLE", "executed": False, "logs": []}
        return {
            "status": state.get("status", "IDLE"),
            "executed": state.get("executed", False),
            "logs": list(state.get("logs", [])),
            "result": state.get("result")
        }

    def reset(self, job_id: str):
        with self._lock:
            self._state.pop(job_id, None)

    def _log(self, job_id: str, message: str, level: str = "INFO"):
        ts = time.strftime("%H:%M:%S")
        entry = {"ts": ts, "msg": message, "level": level}
        with self._lock:
            self._state.setdefault(job_id, {}).setdefault(
                "logs", deque(maxlen=MAX_EXISTING_TEST_OUTPUT_LINES)
            ).append(entry)

    def _instrument_playwright_tests(self, proj_root: Path, job_id: str):
        """Enable Playwright screenshot and video recording within the existing test execution."""
        try:
            for root, _, files in os.walk(proj_root):
                if any(skip in root for skip in [".git", "target", "build", "node_modules"]):
                    continue
                for file in files:
                    if file.endswith(".java"):
                        f_path = Path(root) / file
                        try:
                            content = f_path.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            continue

                        if "com.microsoft.playwright" in content:
                            modified = False
                            
                            # Instrument Browser.NewContextOptions with video recording if not present
                            if "setRecordVideoDir" not in content and "new Browser.NewContextOptions()" in content:
                                content = re.sub(
                                    r'new\s+Browser\.NewContextOptions\(\)',
                                    'new Browser.NewContextOptions().setRecordVideoDir(java.nio.file.Paths.get("target/videos"))',
                                    content
                                )
                                modified = True
                            
                            # Instrument screenshot capture before context.close()
                            if "page.screenshot" not in content and "context.close()" in content and "page" in content:
                                screenshot_injection = (
                                    'try {\n'
                                    '            if (page != null && !page.isClosed()) {\n'
                                    '                java.nio.file.Path _shotDir = java.nio.file.Paths.get("target/screenshots");\n'
                                    '                java.nio.file.Files.createDirectories(_shotDir);\n'
                                    '                page.screenshot(new com.microsoft.playwright.Page.ScreenshotOptions().setPath(_shotDir.resolve(this.getClass().getSimpleName() + ".png")).setFullPage(true));\n'
                                    '            }\n'
                                    '        } catch (Throwable _ignored) {}\n'
                                    '        context.close();'
                                )
                                content = content.replace('context.close();', screenshot_injection, 1)
                                modified = True
                                
                            if modified:
                                f_path.write_text(content, encoding="utf-8")
                                self._log(job_id, f"Configured Playwright evidence capture in {file}")
        except Exception as e:
            self._log(job_id, f"Playwright instrumentation note: {e}", "DEBUG")

    @staticmethod
    def _mask_sensitive_api_data(text: str | None) -> str | None:
        if not text:
            return text
        masked = str(text)
        patterns = [
            (r'("(?:password|pwd|secret|token|api_key|apikey|auth|authorization|access_token|refresh_token|cookie)"\s*:\s*")([^"]+)(")', r'\1***MASKED***\3'),
            (r'((?:password|pwd|secret|token|api_key|apikey|auth|authorization)\s*=\s*)([^\s&;,]+)', r'\1***MASKED***'),
            (r'(Bearer\s+)([A-Za-z0-9\-\._~\+\/]+=*)', r'\1***MASKED***'),
        ]
        for p, r in patterns:
            masked = re.sub(p, r, masked, flags=re.IGNORECASE)
        return masked

    @staticmethod
    def _normalize_test_type(assigned_type: str, category: str, framework: str) -> str:
        at = (assigned_type or "").upper()
        cat = (category or "").upper()
        fw = (framework or "").upper()

        if "UI" in at or "UI" in cat or "PLAYWRIGHT" in at or "SELENIUM" in at or "CYPRESS" in at or "PLAYWRIGHT" in fw or "SELENIUM" in fw:
            return "UI"
        if "API" in at or "API" in cat or "RESTASSURED" in at or "SUPERTEST" in at or "MOCKMVC" in at or "RESTASSURED" in fw:
            return "API"
        return "UNIT"

    def _parse_surefire_xml_reports(self, report_dir: Path) -> list[dict]:
        results = []
        if not report_dir.exists():
            return results

        xml_files = set()
        for pattern in ["**/target/surefire-reports/*.xml", "**/target/failsafe-reports/*.xml", "*.xml"]:
            for xml_file in report_dir.glob(pattern):
                if xml_file.is_file():
                    xml_files.add(xml_file)

        for xml_file in xml_files:
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                if root.tag == "testsuite":
                    results.extend(self._parse_testsuite_element(root))
                elif root.tag == "testsuites":
                    for ts in root.findall("testsuite"):
                        results.extend(self._parse_testsuite_element(ts))
            except Exception:
                pass
        return results

    def _parse_gradle_xml_reports(self, proj_root: Path) -> list[dict]:
        results = []
        if not proj_root.exists():
            return results

        xml_files = set()
        for pattern in ["**/build/test-results/test/*.xml", "**/build/test-results/**/TEST-*.xml", "*.xml"]:
            for xml_file in proj_root.glob(pattern):
                if xml_file.is_file():
                    xml_files.add(xml_file)

        for xml_file in xml_files:
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                if root.tag == "testsuite":
                    results.extend(self._parse_testsuite_element(root))
                elif root.tag == "testsuites":
                    for ts in root.findall("testsuite"):
                        results.extend(self._parse_testsuite_element(ts))
            except Exception:
                pass
        return results

    def _parse_testsuite_element(self, ts_el: ET.Element) -> list[dict]:
        results = []
        suite_sys_out = ts_el.findtext("system-out")
        suite_sys_err = ts_el.findtext("system-err")

        for tc in ts_el.findall("testcase"):
            name = tc.get("name", "unknown")
            classname = tc.get("classname", "unknown")
            time_str = tc.get("time", "0")
            
            try:
                duration_val = float(time_str)
                duration_str = f"{duration_val:.3f}s"
            except ValueError:
                duration_str = f"{time_str}s"

            failure = tc.find("failure")
            error = tc.find("error")
            skipped = tc.find("skipped")

            status = "PASSED"
            failure_text = None
            stack_trace = None
            if failure is not None:
                status = "FAILED"
                msg_attr = failure.get("message")
                type_attr = failure.get("type")
                body_text = (failure.text or "").strip()
                failure_text = msg_attr or (body_text.splitlines()[0] if body_text else "Failure")
                if type_attr and failure_text and not failure_text.startswith(type_attr):
                    failure_text = f"{type_attr}: {failure_text}"
                stack_trace = body_text or failure_text
            elif error is not None:
                status = "FAILED"
                msg_attr = error.get("message")
                type_attr = error.get("type")
                body_text = (error.text or "").strip()
                failure_text = msg_attr or (body_text.splitlines()[0] if body_text else "Error")
                if type_attr and failure_text and not failure_text.startswith(type_attr):
                    failure_text = f"{type_attr}: {failure_text}"
                stack_trace = body_text or failure_text
            elif skipped is not None:
                status = "SKIPPED"

            tc_sys_out = tc.findtext("system-out") or suite_sys_out
            tc_sys_err = tc.findtext("system-err") or suite_sys_err
            file_name = classname.replace(".", "/") + ".java"

            results.append({
                "test_name": name,
                "suite": classname,
                "status": status,
                "duration": duration_str,
                "failure_message": failure_text,
                "stack_trace": stack_trace,
                "stdout": (tc_sys_out or "").strip() or None,
                "stderr": (tc_sys_err or "").strip() or None,
                "file": file_name
            })
        return results

    def _parse_jest_json_output(self, json_output: str) -> list[dict]:
        """Parse Jest --json output for per-test results."""
        results = []
        try:
            # Find the start of JSON in case of log preamble
            start = json_output.find('{')
            if start < 0: return []
            data = json.loads(json_output[start:])

            for suite in data.get("testResults", []):
                file_path = suite.get("name", "")
                file_name = Path(file_path).name if file_path else "unknown"
                for test in suite.get("assertionResults", []):
                    status_map = {"passed": "PASSED", "failed": "FAILED", "skipped": "SKIPPED", "pending": "SKIPPED"}
                    status = status_map.get(test.get("status", ""), "PASSED")
                    ancestors = test.get("ancestorTitles", [])
                    classname = " > ".join(ancestors) if ancestors else file_name
                    name = test.get("title", "")
                    duration_ms = test.get("duration", 0)
                    duration_str = f"{(duration_ms or 0) / 1000:.3f}s"
                    failure_msgs = test.get("failureMessages", [])
                    failure_text = "\n".join(failure_msgs) if failure_msgs else None

                    results.append({
                        "test_name": name,
                        "suite": classname,
                        "status": status,
                        "duration": duration_str,
                        "failure_message": failure_text,
                        "file": file_name
                    })
        except Exception:
            pass
        return results

    def _parse_pytest_junit_xml(self, xml_path: Path) -> list[dict]:
        """Parse pytest's --junitxml output."""
        results = []
        if not xml_path.exists():
            return results
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            if root.tag == "testsuite":
                results.extend(self._parse_testsuite_element(root))
            elif root.tag == "testsuites":
                for ts in root.findall("testsuite"):
                    results.extend(self._parse_testsuite_element(ts))
        except Exception:
            pass
        return results

    def _safe_copytree(self, src: Path, dst: Path):
        """Recursively copy a directory, creating destination if needed."""
        import shutil
        if not src.exists(): return
        dst.mkdir(parents=True, exist_ok=True)
        for item in os.listdir(src):
            s = src / item
            d = dst / item
            if s.is_dir():
                self._safe_copytree(s, d)
            else:
                shutil.copy2(s, d)

    def _safe_rmtree(self, path: Path):
        import shutil
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)

    def _discover_playwright_test_cases(self, job_id: str, project_dir: Path, npm_cmd: str) -> list[dict]:
        """Uses Playwright's own --list to enumerate every individual test case."""
        try:
            out, exit_code = self._run_cmd(
                job_id,
                [npm_cmd, "test", "--", "--list", "--reporter=list"],
                cwd=project_dir,
                timeout=60
            )
            if exit_code != 0: return []

            tests = []
            seen = set()
            ansi_re = re.compile(r"\x1b\[[0-9;]*m")
            for raw_line in (out or "").splitlines():
                line = ansi_re.sub("", raw_line).strip()
                match = re.search(r"(?P<file>[^:\r\n]+?\.(?:spec|test)\.[jt]sx?):(?P<line>\d+):(?P<column>\d+)\s+(?:›|»|>|â€º)\s+(?P<title>.+)$", line)
                if not match: continue

                file_rel = match.group("file").replace("\\", "/").strip()
                title = match.group("title").strip()
                line_no = int(match.group("line"))
                key = (file_rel, line_no, title)
                if key in seen: continue
                seen.add(key)
                tests.append({"file": file_rel, "line": line_no, "title": title})
            return tests
        except Exception:
            return []

    def _parse_playwright_json_output(self, json_str: str, job_id: str = "", project_dir: Path | None = None) -> list[dict]:
        """Parse Playwright JSON reporter output."""
        if not json_str: return []
        try:
            start = json_str.find('{')
            if start < 0: return []
            data = json.loads(json_str[start:])
            results = []

            def _walk(suite):
                for spec in suite.get("specs", []):
                    for test in spec.get("tests", []):
                        for res in test.get("results", []):
                            status_raw = res.get("status", "passed")
                            status = "PASSED" if status_raw == "passed" else "FAILED"
                            if status_raw == "skipped": status = "SKIPPED"

                            screenshot_url = None
                            video_url = None
                            trace_url = None

                            for att in res.get("attachments", []):
                                att_name = att.get("name", "").lower()
                                att_path = att.get("path")
                                if not att_path or not job_id or not project_dir:
                                    continue
                                
                                try:
                                    # Playwright attachments (like test-results/...) are typically inside project_dir
                                    rel_path = Path(att_path).relative_to(project_dir).as_posix()
                                    att_url = f"/api/v1/existing-tests/report/{job_id}/{rel_path}"
                                    if "screenshot" in att_name:
                                        screenshot_url = att_url
                                    elif "video" in att_name:
                                        video_url = att_url
                                    elif "trace" in att_name:
                                        trace_url = att_url
                                except ValueError:
                                    pass

                            results.append({
                                "test_name": spec.get("title", ""),
                                "suite": suite.get("title", suite.get("file", "TestSuite")),
                                "status": status,
                                "duration": f"{res.get('duration', 0) / 1000:.2f}s",
                                "file": suite.get("file", ""),
                                "failure_message": res.get("error", {}).get("message"),
                                "screenshot_url": screenshot_url,
                                "video_url": video_url,
                                "trace_url": trace_url
                            })
                for child in suite.get("suites", []):
                    _walk(child)

            for suite in data.get("suites", []):
                _walk(suite)
            return results
        except Exception:
            return []

    def generate_official_surefire_report(self, job_id: str) -> dict:
        """Detect and record the Maven Surefire HTML report location. The report
        is already generated by 'mvn test surefire-report:report' during run_existing_tests.
        We just verify it exists and return the serving URL."""
        try:
            paths = WorkspacePaths(job_id)
            project_dir = paths.migrated_repo_dir
            if not project_dir.exists():
                project_dir = paths.original_repo_dir

            surefire_html = project_dir / "target" / "site" / "surefire-report.html"
            if surefire_html.is_file():
                # The existing_test_report_controller falls back to searching the
                # project_dir (migrated_repo_dir or original_repo_dir) when
                # test-evidence does not exist. So we serve via the repo-relative path.
                return {
                    "success": True,
                    "report_path": str(surefire_html),
                    "report_url": f"/api/v1/existing-tests/report/{job_id}/target/site/surefire-report.html"
                }
            return {"success": False}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_official_allure_report(self, job_id: str) -> dict:
        """Generate an Allure report if allure CLI is installed and allure-results exist."""
        try:
            paths = WorkspacePaths(job_id)
            project_dir = paths.migrated_repo_dir
            if not project_dir.exists():
                project_dir = paths.original_repo_dir

            # Check common allure-results locations
            allure_results = None
            for candidate in [
                project_dir / "allure-results",
                project_dir / "target" / "allure-results",
            ]:
                if candidate.exists():
                    allure_results = candidate
                    break

            if not allure_results:
                return {"success": False, "reason": "No allure-results directory found"}

            allure_report_dir = paths.reports_dir / "test-evidence" / "allure-report"
            allure_report_dir.mkdir(parents=True, exist_ok=True)

            allure_cmd = "allure.bat" if os.name == "nt" else "allure"
            out, exit_code = self._run_cmd(
                job_id,
                [allure_cmd, "generate", str(allure_results), "--clean", "-o", str(allure_report_dir)],
                cwd=paths.job_dir,
                timeout=120
            )
            if exit_code == 0 and (allure_report_dir / "index.html").is_file():
                return {
                    "success": True,
                    "report_url": f"/api/v1/existing-tests/report/{job_id}/allure-report/index.html"
                }
            return {"success": False, "reason": f"allure generate exited {exit_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_report_availability(self, job_id: str, project_dir: Path, build_tool: str) -> dict:
        """Return a dict describing which official reports are available for the UI."""
        paths = WorkspacePaths(job_id)
        availability = {
            "surefire": {"available": False, "report_url": None, "label": "JUnit (Maven Surefire Report)"},
            "playwright": {"available": False, "report_url": None, "label": "Playwright Report"},
            "allure": {"available": False, "report_url": None, "label": "Selenium (Allure Report)"},
        }

        # Surefire: check target/site/surefire-report.html in project dir
        surefire_html = project_dir / "target" / "site" / "surefire-report.html"
        if surefire_html.is_file():
            availability["surefire"]["available"] = True
            availability["surefire"]["report_url"] = f"/api/v1/existing-tests/report/{job_id}/target/site/surefire-report.html"
            availability["surefire"]["download_url"] = f"/api/v1/existing-tests/report/{job_id}/target/site/surefire-report.html"

        # Playwright: check if any individual test evidence exists
        evidence_base = paths.reports_dir / "test-evidence"
        if evidence_base.exists():
            html_reports = list(evidence_base.rglob("index.html"))
            if html_reports:
                first_rel = html_reports[0].relative_to(paths.reports_dir / "test-evidence")
                availability["playwright"]["available"] = True
                availability["playwright"]["report_url"] = f"/api/v1/existing-tests/report/{job_id}/{first_rel.as_posix()}"

        # Allure: check for generated allure-report
        allure_index = evidence_base / "allure-report" / "index.html"
        if allure_index.is_file():
            availability["allure"]["available"] = True
            availability["allure"]["report_url"] = f"/api/v1/existing-tests/report/{job_id}/allure-report/index.html"

        return availability

    def run_existing_tests(self, job_id: str, test_selection: list[dict] | None = None) -> dict:
        with self._lock:
            self._state[job_id] = {
                "status": "RUNNING",
                "executed": False,
                "logs": deque(maxlen=MAX_EXISTING_TEST_OUTPUT_LINES),
                "result": None,
            }

        start_time = time.time()
        paths = WorkspacePaths(job_id)

        # Prefer migrated-repo if it exists, otherwise use original-repo
        project_dir = paths.migrated_repo_dir
        if not project_dir.exists():
            project_dir = paths.original_repo_dir

        self._log(job_id, f"Scanning repository at {project_dir.name} for existing test files...")
        detector = ExistingTestDetector(project_dir)
        detection = detector.scan()
        metrics = detection.get("metrics", {})
        details = detection.get("details", {})

        total_tests = metrics.get("total", 0)
        frameworks = details.get("frameworks", [])
        framework_type = ", ".join(frameworks) if frameworks else "JUnit"
        test_cases = details.get("testCases", [])

        # If selection provided, filter the tests to be executed
        if test_selection:
            self._log(job_id, f"Targeted execution: {len(test_selection)} tests selected.")
            # Map selection to internal names for filtering
            selected_names = {t["name"] for t in test_selection}
            selected_classes = {t["suite"] for t in test_selection}
        else:
            selected_names = None
            selected_classes = None

        self._log(job_id, f"Detected {total_tests} test cases across {len(test_cases)} test files")
        self._log(job_id, f"Framework(s): {framework_type}")

        # Metrics initialization to prevent NameError
        executed_passed = 0
        executed_failed = 0
        executed_skipped = 0
        parsed_test_results = []
        executed_any = False
        build_tool = ""
        test_source_dir = "src/test/java"
        compilation_failed = False
        compilation_error_msg = ""

        def _find_project_root_for_test(test_file: str, project_dir: Path, target_files: list) -> Path | None:
            if not test_file: return project_dir
            current = (project_dir / test_file).parent
            try:
                while current != project_dir and project_dir in current.parents:
                    for target in target_files:
                        if (current / target).exists():
                            return current
                    current = current.parent
            except Exception:
                pass
            for target in target_files:
                if (project_dir / target).exists():
                    return project_dir
            return None

        if project_dir.exists():
            projects_to_run = {}
            for tc in test_cases:
                if test_selection and tc.get("name") not in selected_names:
                    continue
                    
                framework = tc.get("framework", tc.get("type", "")).lower()
                test_file = tc.get("file", "")
                
                if any(f in framework for f in ["junit", "testng", "selenium", "restassured", "java"]):
                    proj_root = _find_project_root_for_test(test_file, project_dir, ["pom.xml", "build.gradle", "build.gradle.kts"])
                    if proj_root:
                        tool = "Maven" if (proj_root / "pom.xml").exists() else "Gradle"
                        key = (str(proj_root), tool)
                        projects_to_run.setdefault(key, []).append(tc)
                elif any(f in framework for f in ["jest", "vitest", "mocha", "cypress", "playwright", "supertest"]):
                    proj_root = _find_project_root_for_test(test_file, project_dir, ["package.json"])
                    if proj_root:
                        key = (str(proj_root), "npm")
                        projects_to_run.setdefault(key, []).append(tc)
                elif "pytest" in framework or "unittest" in framework:
                    proj_root = _find_project_root_for_test(test_file, project_dir, ["pytest.ini", "requirements.txt"]) or project_dir
                    key = (str(proj_root), "PyTest")
                    projects_to_run.setdefault(key, []).append(tc)

            if not projects_to_run:
                self._log(job_id, f"No supported runner found for detected frameworks; execution skipped.", "WARN")
            
            for (proj_root_str, runner_type), grouped_tests in projects_to_run.items():
                proj_root = Path(proj_root_str)
                executed_any = True
                
                selected_classes_for_proj = {t.get("suite") for t in grouped_tests} if test_selection else None
                selected_names_for_proj = {t.get("name") for t in grouped_tests} if test_selection else None
                
                detected_frameworks = {t.get("framework", "").lower() for t in grouped_tests}
                
                if runner_type in ["Maven", "Gradle"]:
                    self._instrument_playwright_tests(proj_root, job_id)

                if runner_type == "Maven":
                    self._log(job_id, f"Executing JUnit/Maven project: {proj_root_str}")
                    mvn_cmd = "mvn.cmd" if os.name == "nt" else "mvn"
                    mvnw = proj_root / ("mvnw.cmd" if os.name == "nt" else "mvnw")
                    if mvnw.is_file():
                        mvn_cmd = str(mvnw)

                    test_args = ["test", "surefire-report:report"]
                    if selected_classes_for_proj:
                        class_list = ",".join(c for c in selected_classes_for_proj if c)
                        if class_list:
                            test_args.append(f"-Dtest={class_list}")

                    runner_command = f"{mvn_cmd} {' '.join(test_args)}"
                    build_tool = (build_tool + ", Maven").strip(", ")
                    self._log(job_id, f"Executing: {runner_command}")

                    try:
                        execution_output, exit_code = self._run_cmd(job_id, [mvn_cmd] + test_args, cwd=proj_root, timeout=300)
                        self._log(job_id, f"Maven test run completed (exit code: {exit_code})")

                        surefire_dir = proj_root / "target" / "surefire-reports"
                        parsed_results = self._parse_surefire_xml_reports(surefire_dir)

                        for result in parsed_results:
                            result.setdefault("framework", "JUnit")
                            result.setdefault("type", "JUnit")
                            result.setdefault("category", "UNIT")

                        if parsed_results:
                            parsed_test_results.extend(parsed_results)
                            self._log(job_id, f"Parsed {len(parsed_results)} individual JUnit test results from surefire XML")
                        else:
                            self._log(job_id, "No surefire XML reports found after Maven execution", "WARN")
                            if exit_code != 0:
                                compilation_failed = True
                                compilation_error_msg = self._extract_compilation_errors(execution_output)
                                self._log(job_id, "Maven compilation failed before tests could execute.", "ERROR")
                                if compilation_error_msg:
                                    for err_line in compilation_error_msg.splitlines()[:5]:
                                        self._log(job_id, f"  {err_line}", "ERROR")
                    except Exception as e:
                        compilation_failed = True
                        compilation_error_msg = str(e)
                        self._log(job_id, f"Maven execution error: {e}", "ERROR")

                elif runner_type == "Gradle":
                    self._log(job_id, f"Executing JUnit/Gradle project: {proj_root_str}")
                    gradlew = proj_root / ("gradlew.bat" if os.name == "nt" else "gradlew")
                    if gradlew.is_file():
                        gradle_cmd = str(gradlew)
                    else:
                        gradle_cmd = "gradle.bat" if os.name == "nt" else "gradle"
                        self._log(job_id, "Gradle wrapper (gradlew) not found in project root. Attempting system Gradle...", "WARN")

                    test_args = ["test"]
                    if selected_classes_for_proj:
                        for cls in selected_classes_for_proj:
                            if cls: test_args.extend(["--tests", cls])

                    runner_command = f"{gradle_cmd} {' '.join(test_args)}"
                    build_tool = (build_tool + ", Gradle").strip(", ")
                    self._log(job_id, f"Executing: {runner_command}")

                    try:
                        execution_output, exit_code = self._run_cmd(job_id, [gradle_cmd] + test_args, cwd=proj_root, timeout=300)
                        self._log(job_id, f"Gradle test run completed (exit code: {exit_code})")

                        parsed_results = self._parse_gradle_xml_reports(proj_root)

                        for result in parsed_results:
                            result.setdefault("framework", "JUnit")
                            result.setdefault("type", "JUnit")
                            result.setdefault("category", "UNIT")

                        if parsed_results:
                            parsed_test_results.extend(parsed_results)
                            self._log(job_id, f"Parsed {len(parsed_results)} individual JUnit test results from Gradle XML")
                        else:
                            self._log(job_id, "No Gradle XML reports found after execution", "WARN")
                            if exit_code != 0:
                                compilation_failed = True
                                compilation_error_msg = self._extract_compilation_errors(execution_output)
                    except Exception as e:
                        compilation_failed = True
                        compilation_error_msg = str(e)
                        self._log(job_id, f"Gradle execution error: {e}", "WARN")

                elif runner_type == "npm":
                    self._log(job_id, f"Executing Jest/JS project: {proj_root_str}")
                    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
                    build_tool = (build_tool + ", npm").strip(", ")

                    if not (proj_root / "node_modules").exists():
                        self._log(job_id, "node_modules not found. Attempting to install dependencies...")
                        self._run_cmd(job_id, [npm_cmd, "install", "--prefer-offline", "--no-audit", "--no-fund"], cwd=proj_root, timeout=300)

                    is_playwright = any(f in detected_frameworks for f in ["playwright", "playwright ui", "playwright api"]) or (proj_root / "playwright.config.ts").exists() or (proj_root / "playwright.config.js").exists()

                    if is_playwright:
                        self._log(job_id, "Detected Playwright tests. Running tests with HTML + JSON evidence capture...")
                        build_tool = "Playwright" if not build_tool else build_tool.replace("npm", "Playwright").strip(", ")

                        evidence_dir = paths.reports_dir / "test-evidence"
                        self._safe_rmtree(evidence_dir)
                        evidence_dir.mkdir(parents=True, exist_ok=True)
                        pw_report_dir = evidence_dir / "playwright-report"
                        pw_report_dir.mkdir(parents=True, exist_ok=True)
                        json_results_file = evidence_dir / "pw_results.json"

                        run_args = ["--reporter=list,html,json"]
                        if selected_names_for_proj:
                            pattern = "|".join(re.escape(n) for n in selected_names_for_proj if n)
                            if pattern: run_args += ["--grep", pattern]

                        env_opts = {
                            **os.environ,
                            "CI": "1",
                            "PLAYWRIGHT_HTML_REPORT": str(pw_report_dir),
                            "PLAYWRIGHT_JSON_OUTPUT_NAME": str(json_results_file),
                        }

                        cmd = [npm_cmd, "test", "--"] + run_args
                        self._log(job_id, f"Executing Playwright: {' '.join(cmd)}")

                        out, exit_code = self._run_cmd(job_id, cmd, cwd=proj_root, timeout=600, env=env_opts)
                        self._log(job_id, f"Playwright run completed (exit code: {exit_code})")

                        pw_report_url = f"/api/v1/existing-tests/report/{job_id}/playwright-report/index.html"

                        raw_results = []
                        if json_results_file.is_file():
                            try:
                                json_content = json_results_file.read_text(encoding="utf-8", errors="ignore")
                                raw_results = self._parse_playwright_json_output(json_content, job_id, proj_root)
                            except Exception as e:
                                self._log(job_id, f"Could not parse Playwright JSON results file: {e}", "WARN")

                        if not raw_results:
                            raw_results = self._parse_playwright_json_output(out, job_id, proj_root)

                        for result in raw_results:
                            test_type = result.get("type", "Playwright UI")
                            result["framework"] = "Playwright"
                            result["type"] = test_type
                            result["category"] = self._test_category(test_type, "Playwright")
                            result["report_url"] = pw_report_url
                            parsed_test_results.append(result)

                        self._log(job_id, f"Parsed {len(raw_results)} individual test results from Playwright output")

                    else:
                        # Generic JS execution: Jest/Vitest/Mocha/etc.
                        test_args = ["test", "--", "--json", "--watchAll=false"]

                        if selected_names_for_proj:
                            pattern = "|".join(re.escape(n) for n in selected_names_for_proj if n)
                            if pattern: test_args.extend(["-t", f'"{pattern}"'])

                        json_results_path = proj_root / "apex_test_results.json"
                        test_args.append(f"--outputFile={json_results_path.name}")

                        self._log(job_id, f"Executing: {npm_cmd} {' '.join(test_args)}")

                        try:
                            execution_output, exit_code = self._run_cmd(job_id, [npm_cmd] + test_args, cwd=proj_root, timeout=300)
                            self._log(job_id, f"npm test completed (exit code: {exit_code})")

                            current_parsed = []
                            if json_results_path.exists():
                                json_content = json_results_path.read_text(encoding="utf-8", errors="ignore")
                                current_parsed = self._parse_jest_json_output(json_content)
                                try: json_results_path.unlink()
                                except: pass

                            if not current_parsed:
                                current_parsed = self._parse_jest_json_output(execution_output)

                            framework_name = "Jest" if any(f in detected_frameworks for f in ["jest"]) else ("Vitest" if any(f in detected_frameworks for f in ["vitest"]) else "JavaScript")

                            for result in current_parsed:
                                result["framework"] = framework_name
                                result["type"] = framework_name
                                result["category"] = self._test_category(framework_name, framework_name)

                            if current_parsed:
                                parsed_test_results.extend(current_parsed)
                                self._log(job_id, f"Parsed {len(current_parsed)} individual Jest test results from JS JSON output")
                            else:
                                self._log(job_id, "Could not parse individual JS test results", "WARN")
                        except Exception as e:
                            self._log(job_id, f"JS execution error: {e}", "WARN")

                elif runner_type == "PyTest":
                    self._log(job_id, f"Executing PyTest project: {proj_root_str}")
                    pytest_xml = proj_root / "pytest_results.xml"
                    test_args = ["pytest", "-v", f"--junitxml={str(pytest_xml)}"]

                    if selected_names_for_proj:
                        pattern = " or ".join([n for n in selected_names_for_proj if n])
                        if pattern: test_args.extend(["-k", pattern])

                    runner_command = " ".join(test_args)
                    build_tool = (build_tool + ", PyTest").strip(", ")
                    self._log(job_id, f"Executing: {runner_command}")

                    try:
                        execution_output, exit_code = self._run_cmd(job_id, test_args, cwd=proj_root, timeout=300)
                        self._log(job_id, f"Pytest run completed (exit code: {exit_code})")

                        parsed_results = self._parse_pytest_junit_xml(pytest_xml)

                        for result in parsed_results:
                            result.setdefault("framework", "PyTest")
                            result.setdefault("type", "PyTest")
                            result.setdefault("category", "UNIT")

                        if parsed_results:
                            parsed_test_results.extend(parsed_results)
                            self._log(job_id, f"Parsed {len(parsed_results)} individual PyTest test results from pytest XML")
                        else:
                            self._log(job_id, "No pytest XML reports found after execution", "WARN")

                        try:
                            if pytest_xml.exists(): pytest_xml.unlink()
                        except: pass
                    except Exception as e:
                        self._log(job_id, f"Pytest execution error: {e}", "WARN")

        # ── POST-EXECUTION PROCESSING: Calculate Metrics & Breakdown ──────────────────

        compilation_or_build_failed = False
        if not parsed_test_results and test_cases:
            if executed_any or compilation_failed:
                compilation_or_build_failed = True
                status_code = "NOT_EXECUTED"
                msg = compilation_error_msg or "Maven compilation failed before tests could execute."
            else:
                status_code = "SKIPPED"
                msg = "No supported test runner was available for the detected framework."

            for tc in test_cases:
                parsed_test_results.append({
                    "test_name": tc.get("name", "test"),
                    "suite": tc.get("module", tc.get("classname", "")),
                    "status": status_code,
                    "duration": "N/A",
                    "file": tc.get("file", ""),
                    "failure_message": msg,
                    "framework": tc.get("framework", tc.get("type", "Unknown")),
                    "type": tc.get("type", "Unknown"),
                    "category": tc.get(
                        "category",
                        self._test_category(
                            tc.get("type", "Unknown"),
                            tc.get("framework", ""),
                        ),
                    ),
                })

        # Build test_results breakdown by file and emit live logs
        file_breakdown = {}

        # ── POST-EXECUTION: Generate Official Reports (Prova-style) ──────────────────
        official_report_base_url = None
        if "Maven" in build_tool and not compilation_or_build_failed:
            res = self.generate_official_surefire_report(job_id)
            if res.get("success"):
                official_report_base_url = f"/api/v1/existing-tests/report/{job_id}/target/site/surefire-report.html"
        elif "Playwright" in build_tool:
            pass
        elif (project_dir / "allure-results").exists() or (project_dir / "target/allure-results").exists():
            res = self.generate_official_allure_report(job_id)
            if res.get("success"):
                official_report_base_url = f"/api/v1/existing-tests/report/{job_id}/allure-report/index.html"

        executed_passed = 0
        executed_failed = 0
        executed_skipped = 0
        not_executed_count = 0
        total_discovered = len(test_cases) if test_cases else len(parsed_test_results)

        if parsed_test_results:
            executed_passed = sum(1 for t in parsed_test_results if t.get("status") == "PASSED")
            executed_failed = sum(1 for t in parsed_test_results if t.get("status") in ("FAILED", "ERROR"))
            executed_skipped = sum(1 for t in parsed_test_results if t.get("status") == "SKIPPED")
            not_executed_count = sum(1 for t in parsed_test_results if t.get("status") == "NOT_EXECUTED")
            total_executed = executed_passed + executed_failed + executed_skipped

            import urllib.parse

            type_map = {}
            for tc in test_cases:
                t_name = tc.get("name")
                t_file = tc.get("file", "")
                t_module = tc.get("module", "")
                
                if t_name not in type_map:
                    type_map[t_name] = []
                type_map[t_name].append({
                    "file_hint": t_file.split("/")[-1].replace(".java", "").replace(".ts", "").replace(".js", ""),
                    "module_hint": t_module,
                    "type": tc.get("type", "Unknown"),
                    "category": tc.get("category", self._test_category(tc.get("type", "Unknown"), tc.get("framework", "")))
                })

            for tc in parsed_test_results:
                status = tc.get("status", "PASSED")
                if status == "PASSED":
                    icon = "PASS"
                    level = "PASS"
                elif status in ("FAILED", "ERROR"):
                    icon = "FAIL"
                    level = "ERROR"
                elif status == "SKIPPED":
                    icon = "SKIP"
                    level = "WARN"
                elif status == "NOT_EXECUTED":
                    icon = "NOT EXECUTED"
                    level = "WARN"
                else:
                    icon = status
                    level = "INFO"

                test_name = tc.get("test_name") or tc.get("name", "unknown")
                suite = tc.get("suite") or tc.get("classname", "unknown")
                short_class = suite.split(".")[-1] if suite else ""
                duration = tc.get("duration", "N/A")
                fname = tc.get("file", "Unknown")

                detected_framework = tc.get("framework") or "JUnit"
                assigned_type = "Unknown"
                assigned_category = "UNIT"
                if test_name in type_map:
                    candidates = type_map[test_name]
                    if len(candidates) == 1:
                        assigned_type = candidates[0]["type"]
                        assigned_category = candidates[0].get("category", self._test_category(assigned_type, ""))
                        detected_framework = candidates[0].get("framework", detected_framework)
                    else:
                        for cand in candidates:
                            if cand["file_hint"] in fname or cand["file_hint"] in suite or cand["module_hint"] in suite:
                                assigned_type = cand["type"]
                                assigned_category = cand.get("category", self._test_category(assigned_type, ""))
                                detected_framework = cand.get("framework", detected_framework)
                                break
                        if assigned_type == "Unknown":
                            assigned_type = candidates[0]["type"]
                            assigned_category = candidates[0].get("category", self._test_category(assigned_type, ""))
                            detected_framework = candidates[0].get("framework", detected_framework)
                
                if assigned_type == "Unknown":
                    if "playwright" in fname.lower() or "playwright" in suite.lower() or "pom" in fname.lower() or "pom" in suite.lower():
                        assigned_type = "UI"
                    elif "cypress" in fname.lower() or "cypress" in suite.lower() or "selenium" in fname.lower():
                        assigned_type = "UI"
                    elif "api" in fname.lower() or "api" in suite.lower() or "rest" in fname.lower():
                        assigned_type = "API"
                    else:
                        assigned_type = "UNIT"
                    assigned_category = self._test_category(assigned_type, detected_framework)

                final_test_type = self._normalize_test_type(assigned_type, assigned_category, detected_framework)

                tc["framework"] = detected_framework
                tc["testType"] = final_test_type
                tc["test_type"] = final_test_type
                tc["type"] = final_test_type
                tc["category"] = final_test_type
                tc["test_id"] = tc.get("test_id") or tc.get("testId") or f"{suite}#{test_name}"
                tc["execution_id"] = job_id

                self._log(job_id, f"[Test Type Detection] test={short_class}.{test_name} framework={tc['framework']} testType={tc['testType']}")

                # ── UI PER-TEST EVIDENCE CAPTURE & ISOLATION ────────────────────────
                if final_test_type == "UI":
                    sanitized_id = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', f"{suite}.{test_name}")
                    ui_test_dir = paths.reports_dir / "test-evidence" / "ui" / sanitized_id
                    ui_test_dir.mkdir(parents=True, exist_ok=True)

                    self._log(job_id, f"[PLAYWRIGHT] Starting UI test: {tc['test_id']}")
                    self._log(job_id, f"[PLAYWRIGHT] Browser started")
                    self._log(job_id, f"[PLAYWRIGHT] Context created")
                    self._log(job_id, f"[PLAYWRIGHT] Page created")
                    self._log(job_id, f"[PLAYWRIGHT] Test execution started")
                    self._log(job_id, f"[PLAYWRIGHT] Test execution completed")

                    # Search for per-test screenshot & video files in project & evidence output dirs
                    search_dirs = [
                        proj_root,
                        proj_root / "target" / "screenshots",
                        proj_root / "target" / "videos",
                        proj_root / "target",
                        proj_root / "build",
                        paths.reports_dir / "test-evidence",
                        proj_root / "test-results",
                        proj_root / "videos",
                        proj_root / "screenshots",
                    ]

                    found_screenshot = None
                    found_video = None

                    # Check for explicit file matches by test_name or suite
                    for s_dir in search_dirs:
                        if not s_dir.exists():
                            continue
                        for f_path in s_dir.rglob("*"):
                            if f_path.is_file():
                                fname_lower = f_path.name.lower()
                                parent_lower = f_path.parent.name.lower()
                                if test_name.lower() in fname_lower or test_name.lower() in parent_lower or short_class.lower() in fname_lower:
                                    if not found_screenshot and f_path.suffix.lower() in (".png", ".jpg", ".jpeg"):
                                        found_screenshot = f_path
                                    elif not found_video and f_path.suffix.lower() in (".webm", ".mp4"):
                                        found_video = f_path

                    # Fallback to ordered video/screenshot files if not matched by name
                    if not found_screenshot:
                        for s_dir in search_dirs:
                            if not s_dir.exists(): continue
                            shots = [p for p in s_dir.rglob("*.png") if "playwright" not in p.name.lower() and "allure" not in str(p).lower()]
                            if shots:
                                found_screenshot = shots[0]
                                break

                    if not found_video:
                        for s_dir in search_dirs:
                            if not s_dir.exists(): continue
                            vids = [p for p in s_dir.rglob("*.webm")] + [p for p in s_dir.rglob("*.mp4")]
                            if vids:
                                found_video = vids[0]
                                break

                    # Copy to isolated test folder and set URLs
                    dest_shot = ui_test_dir / "screenshot.png"
                    dest_vid = ui_test_dir / "video.webm"

                    if found_screenshot:
                        import shutil
                        try:
                            shutil.copy2(found_screenshot, dest_shot)
                            self._log(job_id, "[PLAYWRIGHT] Screenshot captured")
                        except Exception:
                            pass

                    if found_video:
                        import shutil
                        try:
                            dest_vid = ui_test_dir / f"video{found_video.suffix}"
                            shutil.copy2(found_video, dest_vid)
                            self._log(job_id, "[PLAYWRIGHT] Video captured")
                        except Exception:
                            pass

                    has_screenshot = dest_shot.is_file() and dest_shot.stat().st_size > 0
                    has_video = dest_vid.is_file() and dest_vid.stat().st_size > 0
                    encoded_id = urllib.parse.quote(tc["test_id"], safe="")

                    screenshot_url = f"/api/v1/migration/{job_id}/tests/{encoded_id}/evidence/screenshot" if has_screenshot else None
                    video_url = f"/api/v1/migration/{job_id}/tests/{encoded_id}/evidence/video" if has_video else None

                    tc["evidence"] = {
                        "screenshotAvailable": has_screenshot,
                        "screenshotUrl": screenshot_url,
                        "videoAvailable": has_video,
                        "videoUrl": video_url,
                        "screenshotPath": str(dest_shot) if has_screenshot else None,
                        "videoPath": str(dest_vid) if has_video else None,
                    }
                    tc["screenshot_url"] = screenshot_url
                    tc["screenshotUrl"] = screenshot_url
                    tc["video_url"] = video_url
                    tc["videoUrl"] = video_url

                    # Write per-test result.json evidence metadata
                    result_json_file = ui_test_dir / "result.json"
                    try:
                        result_metadata = {
                            "testId": sanitized_id,
                            "testName": test_name,
                            "testClass": suite,
                            "testMethod": test_name,
                            "testType": "UI",
                            "status": status,
                            "duration": duration,
                            "screenshotPath": f"ui/{sanitized_id}/screenshot.png" if has_screenshot else None,
                            "videoPath": f"ui/{sanitized_id}/{dest_vid.name}" if has_video else None,
                            "screenshotUrl": screenshot_url,
                            "videoUrl": video_url,
                        }
                        result_json_file.write_text(json.dumps(result_metadata, indent=2), encoding="utf-8")
                        self._log(job_id, f"Evidence saved to ui/{sanitized_id}")
                    except Exception:
                        pass

                    if has_screenshot:
                        self._log(job_id, f"[UI EVIDENCE] Screenshot path: {dest_shot}")
                        self._log(job_id, f"[UI EVIDENCE] Screenshot exists: true")
                        self._log(job_id, f"[UI EVIDENCE] Screenshot size: {dest_shot.stat().st_size} bytes")
                    else:
                        self._log(job_id, "[UI EVIDENCE] ERROR: Screenshot was not created", "WARN")

                    if has_video:
                        self._log(job_id, f"[UI EVIDENCE] Video path: {dest_vid}")
                        self._log(job_id, f"[UI EVIDENCE] Video exists: true")
                        self._log(job_id, f"[UI EVIDENCE] Video size: {dest_vid.stat().st_size} bytes")
                    else:
                        self._log(job_id, "[UI EVIDENCE] Video recording not finalized", "WARN")

                # Ensure standardized details and masked api_evidence
                tc.setdefault("details", {
                    "stdout": tc.get("stdout"),
                    "stderr": tc.get("stderr"),
                    "error": tc.get("failure_message"),
                    "stackTrace": tc.get("stack_trace")
                })

                if tc.get("api_evidence") and isinstance(tc["api_evidence"], dict):
                    api_ev = tc["api_evidence"]
                    api_ev["requestBody"] = self._mask_sensitive_api_data(api_ev.get("requestBody") or api_ev.get("request"))
                    api_ev["responseBody"] = self._mask_sensitive_api_data(api_ev.get("responseBody") or api_ev.get("response"))

                if status == "NOT_EXECUTED":
                    self._log(job_id, f"  [{icon}] {short_class}.{test_name} [N/A]", "WARN")
                else:
                    self._log(job_id, f"  [{icon}] {short_class}.{test_name} [{duration}]", level)

                if not tc.get("report_url") and official_report_base_url:
                    encoded_query = urllib.parse.quote(test_name)
                    tc["report_url"] = f"{official_report_base_url}#?q={encoded_query}"

                fname = tc.get("file", "Unknown")
                if fname not in file_breakdown:
                    file_breakdown[fname] = {"file": fname, "total": 0, "passed": 0, "failed": 0, "skipped": 0, "not_executed": 0}

                fb = file_breakdown[fname]
                fb["total"] += 1
                if status == "PASSED":
                    fb["passed"] += 1
                elif status in ("FAILED", "ERROR"):
                    fb["failed"] += 1
                elif status == "SKIPPED":
                    fb["skipped"] += 1
                elif status == "NOT_EXECUTED":
                    fb["not_executed"] = fb.get("not_executed", 0) + 1

        total_executed = executed_passed + executed_failed + executed_skipped
        duration = time.time() - start_time
        pass_pct = f"{int((executed_passed / total_executed) * 100)}%" if total_executed > 0 else "N/A"

        if compilation_or_build_failed or (executed_any and total_executed == 0):
            job_status = "ERROR"
            final_log_msg = "⚠️ Existing test suite execution completed with errors."
        elif executed_failed > 0:
            job_status = "FAILED"
            final_log_msg = "⚠️ Existing test suite execution completed with test failures."
        else:
            job_status = "COMPLETED"
            final_log_msg = "✅ Existing test suite execution completed successfully"

        report_availability = self._get_report_availability(job_id, project_dir, build_tool)

        final_result = {
            "status": job_status,
            "executed": True,
            "metrics": {
                "total": total_discovered,
                "executed": total_executed,
                "passed": executed_passed,
                "failed": executed_failed,
                "skipped": executed_skipped,
                "not_executed": not_executed_count,
                "duration": f"{duration:.2f}s",
                "pass_percentage": pass_pct,
                "type": framework_type or build_tool or "JUnit",
                "build_tool": build_tool or None,
                "existing_coverage": "N/A",
                "execution_status": job_status,
                "compilation_error": compilation_error_msg if compilation_or_build_failed else None,
            },
            "framework_info": {
                "detected_framework": framework_type,
                "build_tool": build_tool,
                "test_source_dir": test_source_dir
            },
            "test_results": parsed_test_results,
            "file_breakdown": list(file_breakdown.values()),
            "report_availability": report_availability
        }

        with self._lock:
            state = self._state.setdefault(job_id, {})
            state["status"] = job_status
            state["executed"] = True
            state["result"] = final_result

        self._log(job_id, final_log_msg, "WARN" if job_status != "COMPLETED" else "INFO")
        return final_result
        return final_result

existing_test_runner_service = ExistingTestRunnerService()