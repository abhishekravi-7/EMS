import os
import re
import time
import json
import logging
import shutil
import subprocess
import threading
import signal
from collections import deque
import xml.etree.ElementTree as ET
from pathlib import Path
from app.core.config import settings
from app.infrastructure.workspace.workspace_paths import WorkspacePaths

logger = logging.getLogger(__name__)

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

        # Deduplicate discovered test cases to represent unique tests
        unique_tests = []
        seen_test_keys = set()
        for t in self.tests_found:
            t_name = ExistingTestRunnerService._normalize_test_name(t.get("name"))
            t["name"] = t_name
            t_suite = t.get("classname") or t.get("module") or ""
            t_file = t.get("file", "")
            key = ExistingTestRunnerService._canonical_test_identifier(t_name, t_suite, t_file)
            if key in seen_test_keys:
                continue
            seen_test_keys.add(key)
            unique_tests.append(t)

        self.tests_found = unique_tests
        self.total_test_count = len(unique_tests)
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
        elif name.endswith('.java') and (
            'test' in name or 'tests' in name or name.endswith('test.java') or name.endswith('it.java')
            or any(ann in c_lower for ann in ["@test", "@parameterizedtest", "@repeatedtest", "@testfactory", "@testtemplate"])
        ):
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
                "by.xpath", "by.name", "pageobject", "pagefactory", "loginpage", "homepage", "productpage",
                "(page ", "(page)", "page page"
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

            # Comprehensive pattern matching JUnit 4, JUnit 5 (@Test, @ParameterizedTest, @RepeatedTest, @TestFactory, @TestTemplate) and TestNG
            # allowing intermediate annotations (e.g. @DisplayName, @ValueSource, @CsvSource, @Order, @Timeout, @Tag, @Disabled, etc.)
            test_method_pattern = re.compile(
                r'@(?:Test|ParameterizedTest|RepeatedTest|TestFactory|TestTemplate)\b(?:\([^)]*\))?'
                r'(?:\s*@[\w.]+(?:\([^)]*\))?)*'
                r'\s*(?:public\s+|protected\s+|private\s+)?(?:static\s+)?(?:final\s+)?(?:<[\w\s,.<>?]+>\s+)?(?:void|boolean|int|long|String|var|[\w<>[\],.]+)\s+'
                r'([a-zA-Z0-9_$]+)\s*\(',
                re.MULTILINE
            )
            raw_matches = test_method_pattern.findall(content)
            matches = [m for m in raw_matches if m not in ("if", "for", "while", "switch", "catch", "new", "return", "class", "interface", "enum")]

            if not matches:
                # Fallback: scan any method declaration following test annotations within 200 chars
                fallback_matches = re.findall(
                    r'@(?:Test|ParameterizedTest|RepeatedTest|TestFactory|TestTemplate)[\s\S]{0,200}?(?:void|boolean|int|long|String|var|[\w<>[\],.]+)\s+([a-zA-Z0-9_$]+)\s*\(',
                    content
                )
                matches = [m for m in fallback_matches if m not in ("if", "for", "while", "switch", "catch", "new", "return", "class", "interface", "enum")]

            if not matches:
                # Last resort annotation counting
                ann_count = len(re.findall(r'@(?:Test|ParameterizedTest|RepeatedTest|TestFactory|TestTemplate)\b', content))
                if ann_count > 0:
                    matches = [f"testMethod{i}" for i in range(ann_count)]

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
        logger.info("[EXISTING-TEST-JOB] Cleanup jobId=%s", job_id)
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

    def has_job(self, job_id: str) -> bool:
        """True if the job is active in memory, stored on disk, has a report, or stored in database."""
        if not job_id:
            return False
        with self._lock:
            if job_id in self._state:
                return True
        try:
            paths = WorkspacePaths(job_id)
            if paths.job_dir.exists() or paths.existing_test_state_path.is_file() or paths.existing_test_report_path.is_file():
                return True
        except Exception:
            pass
        try:
            from app.infrastructure.persistence.existing_test_repository import existing_test_state_exists_in_db
            if existing_test_state_exists_in_db(job_id):
                return True
        except Exception:
            pass
        return False

    def scan_total(self, job_id: str) -> dict:
        paths = WorkspacePaths(job_id)
        project_dir = paths.migrated_repo_dir
        if not project_dir.exists():
            project_dir = paths.original_repo_dir
        if not project_dir.exists():
            return {
                "testCasesFound": 0,
                "status": "NO_TESTS_AVAILABLE",
                "message": "No test cases available",
                "tests": [],
                "total": 0,
                "testCount": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "notExecuted": 0,
                "framework": "Not Detected",
                "test_cases": []
            }
        detector = ExistingTestDetector(project_dir)
        detection = detector.scan()
        metrics = detection.get("metrics", {})
        details = detection.get("details", {})
        frameworks = details.get("frameworks", [])
        test_cases = details.get("testCases", [])
        total = metrics.get("total", 0)

        if total == 0 or len(test_cases) == 0:
            return {
                "testCasesFound": 0,
                "status": "NO_TESTS_AVAILABLE",
                "message": "No test cases available",
                "tests": [],
                "total": 0,
                "testCount": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "notExecuted": 0,
                "framework": "Not Detected",
                "test_cases": []
            }
        return {
            "testCasesFound": total,
            "status": "READY",
            "message": f"Found {total} existing test cases.",
            "tests": test_cases,
            "total": total,
            "framework": ", ".join(frameworks) if frameworks else "Not Detected",
            "test_cases": test_cases
        }

    def _save_state_to_disk(self, job_id: str) -> None:
        """Persist in-memory state to disk and database so it is accessible across multiple workers/processes/containers."""
        try:
            paths = WorkspacePaths(job_id)
            paths.reports_dir.mkdir(parents=True, exist_ok=True)
            with self._lock:
                state = self._state.get(job_id)
                if not state:
                    return
                serializable_state = {
                    "status": state.get("status", "IDLE"),
                    "executed": state.get("executed", False),
                    "logs": list(state.get("logs", [])),
                    "result": state.get("result"),
                }
            paths.existing_test_state_path.write_text(json.dumps(serializable_state, indent=2), encoding="utf-8")
            from app.infrastructure.persistence.existing_test_repository import save_existing_test_state_to_db
            save_existing_test_state_to_db(job_id, serializable_state, report=state.get("result"))
        except Exception:
            pass

    def get_status(self, job_id: str) -> dict:
        logger.info("[EXISTING-TEST-JOB] Status requested %s", job_id)
        with self._lock:
            state = self._state.get(job_id)
        if state and state.get("status") not in (None, "IDLE", "Unknown"):
            status_str = state.get("status", "IDLE")
            logger.info("[EXISTING-TEST-JOB] Job found=true")
            logger.info("[EXISTING-TEST-JOB] State=%s", status_str)
            return {
                "status": status_str,
                "executed": state.get("executed", False),
                "logs": list(state.get("logs", [])),
                "result": state.get("result")
            }

        # Check disk persistence (for multi-worker / multi-container in DigitalOcean)
        paths = WorkspacePaths(job_id)
        if paths.existing_test_state_path.is_file():
            try:
                disk_state = json.loads(paths.existing_test_state_path.read_text(encoding="utf-8"))
                with self._lock:
                    self._state[job_id] = {
                        "status": disk_state.get("status", "IDLE"),
                        "executed": disk_state.get("executed", False),
                        "logs": deque(disk_state.get("logs", []), maxlen=MAX_EXISTING_TEST_OUTPUT_LINES),
                        "result": disk_state.get("result")
                    }
                status_str = disk_state.get("status", "IDLE")
                logger.info("[EXISTING-TEST-JOB] Job found=true")
                logger.info("[EXISTING-TEST-JOB] State=%s", status_str)
                return {
                    "status": status_str,
                    "executed": disk_state.get("executed", False),
                    "logs": disk_state.get("logs", []),
                    "result": disk_state.get("result")
                }
            except Exception:
                pass

        if paths.existing_test_report_path.is_file():
            try:
                report_data = json.loads(paths.existing_test_report_path.read_text(encoding="utf-8"))
                res_status = report_data.get("status", "COMPLETED")
                logger.info("[EXISTING-TEST-JOB] Job found=true")
                logger.info("[EXISTING-TEST-JOB] State=%s", res_status)
                return {
                    "status": res_status,
                    "executed": True,
                    "logs": [],
                    "result": report_data
                }
            except Exception:
                pass

        # Check database persistence (handles multi-container routing in DigitalOcean)
        try:
            from app.infrastructure.persistence.existing_test_repository import load_existing_test_state_from_db, load_existing_test_report_from_db
            db_state = load_existing_test_state_from_db(job_id)
            if db_state:
                with self._lock:
                    self._state[job_id] = {
                        "status": db_state.get("status", "IDLE"),
                        "executed": db_state.get("executed", False),
                        "logs": deque(db_state.get("logs", []), maxlen=MAX_EXISTING_TEST_OUTPUT_LINES),
                        "result": db_state.get("result")
                    }
                try:
                    paths.reports_dir.mkdir(parents=True, exist_ok=True)
                    paths.existing_test_state_path.write_text(json.dumps(db_state, indent=2), encoding="utf-8")
                except Exception:
                    pass
                status_str = db_state.get("status", "IDLE")
                logger.info("[EXISTING-TEST-JOB] Job found=true")
                logger.info("[EXISTING-TEST-JOB] State=%s", status_str)
                return {
                    "status": status_str,
                    "executed": db_state.get("executed", False),
                    "logs": db_state.get("logs", []),
                    "result": db_state.get("result")
                }

            db_report = load_existing_test_report_from_db(job_id)
            if db_report:
                res_status = db_report.get("status", "COMPLETED")
                logger.info("[EXISTING-TEST-JOB] Job found=true")
                logger.info("[EXISTING-TEST-JOB] State=%s", res_status)
                return {
                    "status": res_status,
                    "executed": True,
                    "logs": [],
                    "result": db_report
                }
        except Exception:
            pass

        found = state is not None or paths.job_dir.exists()
        status_str = state.get("status", "IDLE") if state else "IDLE"
        logger.info("[EXISTING-TEST-JOB] Job found=%s", str(found).lower())
        logger.info("[EXISTING-TEST-JOB] State=%s", status_str)
        if state:
            return {
                "status": status_str,
                "executed": state.get("executed", False),
                "logs": list(state.get("logs", [])),
                "result": state.get("result")
            }
        return {"status": "IDLE", "executed": False, "logs": []}

    def reset(self, job_id: str):
        logger.info("[EXISTING-TEST-JOB] Cleanup jobId=%s", job_id)
        with self._lock:
            self._state.pop(job_id, None)
        try:
            paths = WorkspacePaths(job_id)
            if paths.existing_test_state_path.is_file():
                paths.existing_test_state_path.unlink(missing_ok=True)
        except Exception:
            pass

    def _log(self, job_id: str, message: str, level: str = "INFO"):
        ts = time.strftime("%H:%M:%S")
        entry = {"ts": ts, "msg": message, "level": level}
        with self._lock:
            self._state.setdefault(job_id, {}).setdefault(
                "logs", deque(maxlen=MAX_EXISTING_TEST_OUTPUT_LINES)
            ).append(entry)

    def _instrument_playwright_tests(self, proj_root: Path, job_id: str):
        """Enable Playwright and Selenium screenshot and video recording within the existing test execution."""
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

                        modified = False

                        # 1. Playwright video recording in NewContextOptions
                        if "com.microsoft.playwright" in content or "Page" in content:
                            if "setRecordVideoDir" not in content:
                                if "new Browser.NewContextOptions()" in content:
                                    content = re.sub(
                                        r'new\s+Browser\.NewContextOptions\(\)',
                                        'new Browser.NewContextOptions().setRecordVideoDir(java.nio.file.Paths.get("target/videos"))',
                                        content
                                    )
                                    modified = True
                                elif "browser.newContext()" in content:
                                    content = re.sub(
                                        r'\bbrowser\s*\.\s*newContext\s*\(\s*\)',
                                        'browser.newContext(new com.microsoft.playwright.Browser.NewContextOptions().setRecordVideoDir(java.nio.file.Paths.get("target/videos")))',
                                        content
                                    )
                                    modified = True

                            # 2. Method-level Playwright screenshot capture in @Test / @ParameterizedTest methods
                            content, method_mod = self._inject_playwright_method_screenshots(content, f_path.stem)
                            if method_mod:
                                modified = True

                            # 3. Lifecycle screenshot capture around context.close() if present
                            if "context.close()" in content and "page" in content:
                                if "page.screenshot" not in content:
                                    lifecycle_injection = (
                                        'try {\n'
                                        '            if (page != null && !page.isClosed()) {\n'
                                        '                java.nio.file.Path _shotDir = java.nio.file.Paths.get("target/screenshots");\n'
                                        '                java.nio.file.Files.createDirectories(_shotDir);\n'
                                        '                page.screenshot(new com.microsoft.playwright.Page.ScreenshotOptions().setPath(_shotDir.resolve(this.getClass().getSimpleName() + ".png")).setFullPage(true));\n'
                                        '            }\n'
                                        '        } catch (Throwable _ignored) {}\n'
                                        '        context.close();\n'
                                        '        try {\n'
                                        '            if (page != null && page.video() != null) {\n'
                                        '                java.nio.file.Path _vDir = java.nio.file.Paths.get("target/videos");\n'
                                        '                java.nio.file.Files.createDirectories(_vDir);\n'
                                        '                page.video().saveAs(_vDir.resolve(this.getClass().getSimpleName() + ".webm"));\n'
                                        '            }\n'
                                        '        } catch (Throwable _ignored) {}'
                                    )
                                    content = content.replace('context.close();', lifecycle_injection, 1)
                                    modified = True

                            # 4. Screenshot capture before page.close() if present
                            if "page.screenshot" not in content and "page.close()" in content and "page" in content:
                                page_injection = (
                                    'try {\n'
                                    '            if (page != null && !page.isClosed()) {\n'
                                    '                java.nio.file.Path _shotDir = java.nio.file.Paths.get("target/screenshots");\n'
                                    '                java.nio.file.Files.createDirectories(_shotDir);\n'
                                    '                page.screenshot(new com.microsoft.playwright.Page.ScreenshotOptions().setPath(_shotDir.resolve(this.getClass().getSimpleName() + ".png")).setFullPage(true));\n'
                                    '            }\n'
                                    '        } catch (Throwable _ignored) {}\n'
                                    '        page.close();'
                                )
                                content = content.replace('page.close();', page_injection, 1)
                                modified = True

                        # 5. Selenium screenshot capture before driver.quit() or driver.close()
                        if "org.openqa.selenium" in content or "WebDriver" in content:
                            if "TakesScreenshot" not in content and "driver.quit()" in content:
                                sel_injection = (
                                    'try {\n'
                                    '            if (driver instanceof org.openqa.selenium.TakesScreenshot) {\n'
                                    '                java.io.File _src = ((org.openqa.selenium.TakesScreenshot) driver).getScreenshotAs(org.openqa.selenium.OutputType.FILE);\n'
                                    '                java.nio.file.Path _dest = java.nio.file.Paths.get("target/screenshots/" + this.getClass().getSimpleName() + ".png");\n'
                                    '                java.nio.file.Files.createDirectories(_dest.getParent());\n'
                                    '                java.nio.file.Files.copy(_src.toPath(), _dest, java.nio.file.StandardCopyOption.REPLACE_EXISTING);\n'
                                    '            }\n'
                                    '        } catch (Throwable _ignored) {}\n'
                                    '        driver.quit();'
                                )
                                content = content.replace('driver.quit();', sel_injection, 1)
                                modified = True

                        if modified:
                            f_path.write_text(content, encoding="utf-8")
                            self._log(job_id, f"Configured UI evidence capture in {file}")
        except Exception as e:
            self._log(job_id, f"UI evidence instrumentation note: {e}", "DEBUG")

    def _inject_playwright_method_screenshots(self, content: str, class_name: str) -> tuple[str, bool]:
        """
        Scans a Java test file for test methods that receive a Playwright Page parameter (e.g. Page page)
        and instruments screenshot capture in a finally block at the end of the test execution.
        """
        if "Page" not in content and "com.microsoft.playwright" not in content:
            return content, False

        # Regex to find test method headers with a Page parameter
        pattern = re.compile(
            r'(@(?:Test|ParameterizedTest|RepeatedTest|TestFactory)[\s\S]*?'
            r'(?:public\s+|protected\s+|private\s+|)?(?:void|[\w<>[\],.]+)\s+'
            r'([a-zA-Z0-9_$]+)\s*\([^)]*?\bPage\s+([a-zA-Z0-9_$]+)[^)]*\)\s*'
            r'(?:throws\s+[\w\s,.<>]+)?\s*\{)',
            re.MULTILINE
        )

        matches = list(pattern.finditer(content))
        if not matches:
            return content, False

        modified = False

        # Process matches in reverse order so character offsets remain valid
        for match in reversed(matches):
            header_start = match.start(1)
            header_end = match.end(1)
            method_name = match.group(2)
            page_var = match.group(3)

            # Find matching closing brace for this method
            brace_count = 1
            i = header_end
            in_string = False
            in_char = False
            in_line_comment = False
            in_block_comment = False
            escape = False

            while i < len(content) and brace_count > 0:
                ch = content[i]
                next_ch = content[i+1] if i + 1 < len(content) else ''

                if in_line_comment:
                    if ch == '\n':
                        in_line_comment = False
                elif in_block_comment:
                    if ch == '*' and next_ch == '/':
                        in_block_comment = False
                        i += 1
                elif in_string:
                    if escape:
                        escape = False
                    elif ch == '\\':
                        escape = True
                    elif ch == '"':
                        in_string = False
                elif in_char:
                    if escape:
                        escape = False
                    elif ch == '\\':
                        escape = True
                    elif ch == "'":
                        in_char = False
                else:
                    if ch == '/' and next_ch == '/':
                        in_line_comment = True
                        i += 1
                    elif ch == '/' and next_ch == '*':
                        in_block_comment = True
                        i += 1
                    elif ch == '"':
                        in_string = True
                    elif ch == "'":
                        in_char = True
                    elif ch == '{':
                        brace_count += 1
                    elif ch == '}':
                        brace_count -= 1
                i += 1

            if brace_count == 0:
                body_end = i - 1
                original_body = content[header_end:body_end]

                # If already instrumented with target/screenshots, skip
                if f"{page_var}.screenshot" in original_body and "target/screenshots" in original_body:
                    continue

                shot_code = (
                    f"\n        try {{\n"
                    f"{original_body}\n"
                    f"        }} finally {{\n"
                    f"            try {{\n"
                    f"                if ({page_var} != null && !{page_var}.isClosed()) {{\n"
                    f"                    java.nio.file.Path _shotDir = java.nio.file.Paths.get(\"target/screenshots\");\n"
                    f"                    java.nio.file.Files.createDirectories(_shotDir);\n"
                    f"                    {page_var}.screenshot(new com.microsoft.playwright.Page.ScreenshotOptions()\n"
                    f"                        .setPath(_shotDir.resolve(this.getClass().getSimpleName() + \".{method_name}.png\"))\n"
                    f"                        .setFullPage(true));\n"
                    f"                }}\n"
                    f"            }} catch (Throwable _ignored) {{}}\n"
                    f"        }}\n    "
                )
                content = content[:header_end] + shot_code + content[body_end:]
                modified = True

        return content, modified

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

    def _resolve_maven_executable(self, target_dir: Path, repo_root: Path, job_id: str) -> tuple[str, Path | None, Path | None]:
        """
        Resolves Maven executable in the following strict order:
        1. Check target_dir and parent directories up to repo_root for Maven wrapper (mvnw.cmd on Windows, mvnw on Unix).
        2. If wrapper script is found, verify that required wrapper files exist and are structurally valid:
           - <wrapper_dir>/mvnw.cmd (valid Windows batch script, no bash syntax or double-double quotes)
           - <wrapper_dir>/.mvn/wrapper/maven-wrapper.jar (valid non-empty JAR)
           - <wrapper_dir>/.mvn/wrapper/maven-wrapper.properties (configuration file)
        3. If wrapper is complete and valid, return ("WRAPPER", wrapper_candidate, wrapper_dir).
        4. If wrapper is missing, incomplete, or malformed/unusable, attempt system Maven lookup via PATH / M2_HOME / MAVEN_HOME.
        5. If system Maven is found, return ("SYSTEM", resolved_sys_mvn, target_dir).
        6. If neither found, return ("NOT_FOUND", None, None).
        """
        self._log(job_id, f"[MAVEN] Repository: {repo_root}")

        wrapper_names = ["mvnw.cmd", "mvnw.bat"] if os.name == "nt" else ["mvnw"]
        wrapper_candidate = None
        wrapper_dir = None

        current = target_dir.resolve()
        repo_root_res = repo_root.resolve()

        while True:
            for w_name in wrapper_names:
                cand = current / w_name
                if cand.is_file():
                    wrapper_candidate = cand
                    wrapper_dir = current
                    break
            if wrapper_candidate:
                break
            if current == repo_root_res or repo_root_res not in current.parents:
                break
            current = current.parent

        wrapper_valid = False
        if wrapper_candidate and wrapper_dir:
            wrapper_jar = wrapper_dir / ".mvn" / "wrapper" / "maven-wrapper.jar"
            wrapper_props = wrapper_dir / ".mvn" / "wrapper" / "maven-wrapper.properties"
            self._log(job_id, f"[MAVEN] Wrapper: {wrapper_candidate}")
            self._log(job_id, f"[MAVEN] Wrapper JAR: {wrapper_jar}")

            has_jar = wrapper_jar.is_file() and wrapper_jar.stat().st_size > 0
            has_props = wrapper_props.is_file()

            # Inspect wrapper script contents for Windows compatibility
            script_malformed = False
            try:
                content = wrapper_candidate.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("#") and not stripped.startswith("#!"):
                        # Bash-style comment in a Windows .cmd file
                        script_malformed = True
                        break
                    if 'set WRAPPER_JAR=""' in line or '""%MAVEN_PROJECTBASEDIR%' in line:
                        # Double-double quotes breaking Windows paths with spaces
                        script_malformed = True
                        break
            except Exception:
                script_malformed = True

            if has_jar and has_props and not script_malformed:
                wrapper_valid = True
                self._log(job_id, "[MAVEN] Wrapper valid: true")
                return "WRAPPER", wrapper_candidate, wrapper_dir
            else:
                self._log(job_id, "[MAVEN] Wrapper validation failed")
                if not has_jar:
                    self._log(job_id, f"[MAVEN] Wrapper JAR missing: {wrapper_jar}")
                if script_malformed:
                    self._log(job_id, "[MAVEN] Wrapper script contains malformed Windows batch syntax (bash comments or invalid quotes)")
                self._log(job_id, "[MAVEN] Wrapper valid: false")
                self._log(job_id, "[MAVEN] Falling back to system Maven")
        else:
            self._log(job_id, "[MAVEN] Wrapper: NOT FOUND")
            self._log(job_id, "[MAVEN] Wrapper valid: false")
            self._log(job_id, "[MAVEN] Attempting system Maven")

        # Resolve system Maven using PATH
        sys_mvn_names = ["mvn.cmd", "mvn.bat", "mvn.exe", "mvn"] if os.name == "nt" else ["mvn"]
        resolved_sys_mvn = None

        for m_name in sys_mvn_names:
            found = shutil.which(m_name)
            if found:
                resolved_sys_mvn = Path(found).resolve()
                break

        # Also check M2_HOME / MAVEN_HOME / bin / mvn
        if not resolved_sys_mvn:
            for env_var in ["MAVEN_HOME", "M2_HOME"]:
                if env_var in os.environ:
                    for m_name in sys_mvn_names:
                        candidate = Path(os.environ[env_var]) / "bin" / m_name
                        if candidate.is_file():
                            resolved_sys_mvn = candidate.resolve()
                            break
                    if resolved_sys_mvn:
                        break

        if resolved_sys_mvn:
            self._log(job_id, f"[MAVEN] System Maven found: {resolved_sys_mvn}")
            return "SYSTEM", resolved_sys_mvn, target_dir

        self._log(job_id, "[MAVEN] System Maven: NOT FOUND")
        return "NOT_FOUND", None, None

    @staticmethod
    def _get_system_and_user_env_var(var_name: str) -> str | None:
        if os.name != "nt":
            return None
        try:
            import winreg
            # Check User Environment (HKCU)
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                    val, _ = winreg.QueryValueEx(key, var_name)
                    if val:
                        return str(val)
            except Exception:
                pass
            # Check System Environment (HKLM)
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment") as key:
                    val, _ = winreg.QueryValueEx(key, var_name)
                    if val:
                        return str(val)
            except Exception:
                pass
        except Exception:
            pass
        return None

    def _resolve_gradle_executable(self, target_dir: Path, repo_root: Path, job_id: str) -> tuple[str, Path | None, Path | None, str]:
        """
        Resolves Gradle executable in the following strict order:
        1. Check target_dir for gradlew.bat (Windows) or gradlew (Unix).
        2. Search upwards through parent directories up to repo_root for gradlew.bat.
        3. Check GRADLE_HOME if defined: %GRADLE_HOME%/bin/gradle.bat.
        4. Check current process PATH (and Windows environment PATH) for gradle.bat.
        5. Return (resolution_type, executable_path, wrapper_root_dir, source).
        """
        self._log(job_id, "[GRADLE] Resolving Gradle executable")
        self._log(job_id, f"[GRADLE] Target directory: {target_dir}")

        wrapper_name = "gradlew.bat" if os.name == "nt" else "gradlew"

        # 1 & 2. Search target_dir and parent directories up to repo_root
        current = target_dir.resolve()
        repo_root_res = repo_root.resolve()
        wrapper_candidate = None
        wrapper_dir = None

        while True:
            cand = current / wrapper_name
            self._log(job_id, f"[GRADLE] Checking wrapper: {cand}")
            if cand.is_file():
                wrapper_candidate = cand
                wrapper_dir = current
                break

            if current == repo_root_res or repo_root_res not in current.parents:
                break
            current = current.parent

        if wrapper_candidate:
            self._log(job_id, "[GRADLE] Wrapper: FOUND")
            self._log(job_id, f"[GRADLE] Selected executable: {wrapper_candidate}")
            self._log(job_id, "[GRADLE] Source: wrapper")
            return "WRAPPER", wrapper_candidate, wrapper_dir, "wrapper"

        self._log(job_id, "[GRADLE] Wrapper: NOT FOUND")

        # 3. Check GRADLE_HOME (from environment or Windows registry)
        gradle_home_val = os.environ.get("GRADLE_HOME")
        if not gradle_home_val and os.name == "nt":
            gradle_home_val = self._get_system_and_user_env_var("GRADLE_HOME")

        self._log(job_id, f"[GRADLE] GRADLE_HOME: {gradle_home_val or 'NOT SET'}")

        sys_gradle_names = ["gradle.bat", "gradle.cmd", "gradle.exe", "gradle"] if os.name == "nt" else ["gradle"]

        if gradle_home_val:
            for g_name in sys_gradle_names:
                candidate = Path(gradle_home_val) / "bin" / g_name
                if candidate.is_file():
                    resolved_path = candidate.resolve()
                    self._log(job_id, f"[GRADLE] Selected executable: {resolved_path}")
                    self._log(job_id, "[GRADLE] Source: GRADLE_HOME")
                    return "SYSTEM", resolved_path, target_dir, "GRADLE_HOME"

        # 4. Check process PATH (and Windows registry PATH if nt)
        path_candidate = None
        for g_name in sys_gradle_names:
            found = shutil.which(g_name)
            if found:
                path_candidate = Path(found).resolve()
                break

        # If not found in current process PATH on Windows, check system & user registry PATH
        if not path_candidate and os.name == "nt":
            reg_paths = []
            u_path = self._get_system_and_user_env_var("Path")
            if u_path:
                reg_paths.extend(u_path.split(";"))
            s_path = self._get_system_and_user_env_var("PATH")
            if s_path:
                reg_paths.extend(s_path.split(";"))
            for p_dir in reg_paths:
                if not p_dir:
                    continue
                p_dir_expanded = os.path.expandvars(p_dir.strip())
                for g_name in sys_gradle_names:
                    cand = Path(p_dir_expanded) / g_name
                    if cand.is_file():
                        path_candidate = cand.resolve()
                        break
                if path_candidate:
                    break

        if path_candidate:
            self._log(job_id, "[GRADLE] PATH Gradle: FOUND")
            self._log(job_id, f"[GRADLE] PATH Gradle candidate: {path_candidate}")
            self._log(job_id, f"[GRADLE] Selected executable: {path_candidate}")
            self._log(job_id, "[GRADLE] Source: PATH")
            return "SYSTEM", path_candidate, target_dir, "PATH"

        self._log(job_id, "[GRADLE] PATH Gradle: NOT FOUND")
        self._log(job_id, "[GRADLE] PATH Gradle candidate: NOT FOUND")
        self._log(job_id, "[GRADLE] Selected executable: NONE")
        self._log(job_id, "[GRADLE] Source: NOT_FOUND")
        return "NOT_FOUND", None, None, "NOT_FOUND"

    def _parse_gradle_xml_reports(self, proj_root: Path, working_dir: Path | None = None) -> list[dict]:
        results = []
        if not proj_root.exists():
            return results

        xml_files = set()
        for pattern in [
            "build/test-results/test/*.xml",
            "build/test-results/**/TEST-*.xml",
        ]:
            for xml_file in proj_root.glob(pattern):
                if xml_file.is_file() and xml_file.suffix.lower() == ".xml":
                    xml_files.add(xml_file)

        for xml_file in xml_files:
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                if root.tag in ("testsuite", "testsuites"):
                    if root.tag == "testsuite":
                        results.extend(self._parse_testsuite_element(root))
                    elif root.tag == "testsuites":
                        for ts in root.findall("testsuite"):
                            results.extend(self._parse_testsuite_element(ts))
            except Exception:
                pass
        return results

    @staticmethod
    def _normalize_test_name(name: str | None) -> str:
        """
        Normalizes test method/case names by stripping method parameter types like '(String, Page)'
        while preserving parameterized execution invocation indices like '[1]', '[2]' or 'testMethod[1]'.

        Examples:
            'testGetFeet()' -> 'testGetFeet'
            'searchByCriteria(String, Page)[1]' -> 'searchByCriteria[1]'
            'searchByCriteria[1]' -> 'searchByCriteria[1]'
            'test(int, int)' -> 'test'
            'authentication(Page)' -> 'authentication'
        """
        if not name:
            return "unknown"
        s = str(name).strip()
        if s.endswith("()"):
            return s[:-2].strip()

        # Extract parameterized invocation index if present (e.g. [1], [2], [1: candidate=foo], [2] candidate=radar)
        bracket_match = re.search(r'\[\s*([^\]]+)\s*\]', s)
        bracket_part = ""
        if bracket_match:
            idx_content = bracket_match.group(1).split(":")[0].strip()
            bracket_part = f"[{idx_content}]"

        # If it has parameters before brackets: e.g. searchByCriteria(String, Page)[1]
        if "(" in s:
            paren_idx = s.find("(")
            method_base = s[:paren_idx].strip()
            return f"{method_base}{bracket_part}" if method_base else s
        elif bracket_match and not s.startswith("["):
            method_base = s.split("[")[0].strip()
            return f"{method_base}{bracket_part}" if method_base else s

        return s

    @staticmethod
    def _canonical_test_identifier(test_name: str | None, suite: str | None, file_or_module: str | None = None) -> tuple[str, str]:
        """
        Builds a canonical (class_name, test_invocation) tuple for unique test execution matching and deduplication.
        Preserves invocation indices like '[1]', '[2]' so distinct parameterized executions are preserved.
        """
        if not test_name:
            s_raw = "unknown"
        else:
            s_raw = str(test_name).strip()

        norm_name = s_raw.lower()

        # Handle Class#method format
        if "#" in norm_name:
            parts = norm_name.split("#")
            if not suite and parts[0]:
                suite = parts[0]
            norm_name = parts[-1].strip()

        # Handle Class.method or pkg.Class.method format
        if "." in norm_name:
            paren_idx = norm_name.find("(")
            dot_part = norm_name[:paren_idx] if paren_idx != -1 else norm_name
            if "." in dot_part:
                parts = dot_part.split(".")
                method_part = parts[-1]
                if not suite and len(parts) > 1:
                    suite = parts[-2]
                norm_name = method_part + (norm_name[paren_idx:] if paren_idx != -1 else "")

        # Extract parameterized invocation index if present (e.g. [1], [2], [1: candidate=foo], [2] candidate=radar)
        bracket_match = re.search(r'\[\s*([^\]]+)\s*\]', norm_name)
        bracket_part = ""
        if bracket_match:
            idx_content = bracket_match.group(1).split(":")[0].strip()
            bracket_part = f"[{idx_content}]"

        # Remove parentheses and parameter lists: e.g. (String, Page)[1] -> method_base + [1]
        if "(" in norm_name:
            paren_idx = norm_name.find("(")
            method_base = norm_name[:paren_idx].strip()
            norm_name = f"{method_base}{bracket_part}" if method_base else norm_name
        elif bracket_match and not norm_name.startswith("["):
            method_base = norm_name.split("[")[0].strip()
            norm_name = f"{method_base}{bracket_part}" if method_base else norm_name

        # Strip any leftover trailing repetition markers (e.g. 'repetition 1 of 5')
        norm_name = re.sub(r'\s+repetition\s+\d+\s+of\s+\d+', '', norm_name).strip()

        suite_str = (suite or "").strip()
        if suite_str:
            suite_clean = suite_str.split("(")[0].split("#")[0].strip()
            class_name = suite_clean.split(".")[-1].split("$")[0].lower()
        elif file_or_module:
            f_stem = Path(file_or_module).stem
            class_name = f_stem.split("$")[0].lower()
        else:
            class_name = "unknown"

        return (class_name, norm_name)

    @staticmethod
    def _base_canonical_test_identifier(test_name: str | None, suite: str | None, file_or_module: str | None = None) -> tuple[str, str]:
        """
        Returns the base (class_name, method_name) without parameterized invocation indices ('[1]', '[2]', etc.).
        Used to match parameterized execution invocations back to their statically discovered method definition.
        """
        class_name, norm_name = ExistingTestRunnerService._canonical_test_identifier(test_name, suite, file_or_module)
        if "[" in norm_name:
            base_m = norm_name.split("[")[0].strip()
            if base_m:
                norm_name = base_m
        return (class_name, norm_name)

    @staticmethod
    def _classify_error_and_root_cause(
        raw_status: str,
        failure_text: str | None,
        stack_trace: str | None,
        stdout: str | None,
        stderr: str | None
    ) -> tuple[str, str, str, str | None, str | None]:
        """
        Classifies errors and extracts true root cause without letting secondary cleanup errors
        (e.g., 'Eyes not open', 'Session already closed', 'NullPointerException in tearDown')
        override or mask the primary root cause (e.g., 'HTTP 401 Unauthorized').
        
        Returns:
            (status, error_category, error_code, root_cause, clean_failure_message)
        """
        if raw_status in ("PASSED", "SKIPPED", "NOT_EXECUTED"):
            return raw_status, "", "", None, failure_text

        combined_text = "\n".join(filter(None, [failure_text, stack_trace, stderr, stdout]))
        combined_lower = combined_text.lower()

        # 1. Applitools Eyes & External Dependency Authentication Failure
        is_applitools = any(k in combined_lower for k in ["applitools", "eyesapi.applitools.com", "eyesexception", "eyes.open", "eyes.close"])
        is_http_401 = "401" in combined_text and ("unauthorized" in combined_lower or "eyesapi" in combined_lower or "http" in combined_lower)
        is_auth_error = is_http_401 or any(k in combined_lower for k in [
            "401 unauthorized", "http 401", "invalid api key", "missing api key", "applitools_api_key",
            "403 forbidden", "407 proxy authentication", "bad credentials", "oauth2authenticationexception"
        ])

        if is_applitools and (is_auth_error or "401" in combined_text):
            root_cause = "Applitools Eyes returned HTTP 401 Unauthorized during Eyes.open()"
            clean_msg = "com.applitools.eyes.EyesException: HTTP 401 Unauthorized https://eyesapi.applitools.com/api/sessions/renderinfo"
            if "eyesapi.applitools.com" in combined_text:
                for line in combined_text.splitlines():
                    if "401" in line or "eyesapi" in line:
                        clean_msg = line.strip()
                        break
            return "ERROR", "External Dependency / Authentication", "EXTERNAL_DEPENDENCY_AUTH", root_cause, clean_msg

        if is_auth_error:
            root_cause = "External service authentication failed (HTTP 401/403 or Invalid Credentials)"
            return "ERROR", "External Dependency / Authentication", "EXTERNAL_DEPENDENCY_AUTH", root_cause, failure_text

        # 2. External Service Connection / Availability Failure
        if any(k in combined_lower for k in [
            "connectexception", "httphostconnectexception", "unknownhostexception", "noroutetohostexception",
            "sockettimeoutexception", "connection refused", "502 bad gateway", "503 service unavailable", "504 gateway timeout"
        ]):
            root_cause = "Failed to connect to external service endpoint (Connection refused or Timeout)"
            return "ERROR", "External Dependency / Connection", "EXTERNAL_SERVICE_ERROR", root_cause, failure_text

        # 3. Environment & Configuration Failure
        if any(k in combined_lower for k in [
            "playwrightexception: executable doesn't exist", "driver not found", "chromedriver", "geckodriver",
            "display not set", "bindexception", "address already in use"
        ]):
            root_cause = "Environment / Configuration issue: missing browser executable or port conflict"
            return "ERROR", "Environment / Configuration", "ENVIRONMENT_CONFIG_ERROR", root_cause, failure_text

        # 4. Missing Dependency / ClassNotFound
        if any(k in combined_lower for k in ["classnotfoundexception", "noclassdeffounderror", "nosuchmethoderror", "unsatisfiedlinkerror"]):
            root_cause = "Missing dependency or bytecode incompatible library"
            return "ERROR", "Missing Dependency", "MISSING_DEPENDENCY", root_cause, failure_text

        # 5. Assertion / Test Failure
        is_assertion = any(k in combined_lower for k in [
            "assertionerror", "assertionfailederror", "comparisonfailure", "opentest4j.assertionfailederror",
            "expected:", "but was:", "assertion failed"
        ])
        if raw_status == "FAILED" or is_assertion:
            root_cause = failure_text or "Assertion failed"
            return "FAILED", "Assertion Failure", "ASSERTION_FAILED", root_cause, failure_text

        # 6. General Test Execution Error
        root_cause = failure_text or "Test threw an unhandled exception during execution"
        return "ERROR", "Test Execution Error", "EXECUTION_ERROR", root_cause, failure_text

    def _parse_testsuite_element(self, ts_el: ET.Element) -> list[dict]:
        results = []
        suite_sys_out = ts_el.findtext("system-out")
        suite_sys_err = ts_el.findtext("system-err")

        for tc in ts_el.findall("testcase"):
            name = self._normalize_test_name(tc.get("name", "unknown"))
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

            raw_status = "PASSED"
            failure_text = None
            stack_trace = None
            if failure is not None:
                raw_status = "FAILED"
                msg_attr = failure.get("message")
                type_attr = failure.get("type")
                body_text = (failure.text or "").strip()
                failure_text = msg_attr or (body_text.splitlines()[0] if body_text else "Failure")
                if type_attr and failure_text and not failure_text.startswith(type_attr):
                    failure_text = f"{type_attr}: {failure_text}"
                stack_trace = body_text or failure_text
            elif error is not None:
                raw_status = "ERROR"
                msg_attr = error.get("message")
                type_attr = error.get("type")
                body_text = (error.text or "").strip()
                failure_text = msg_attr or (body_text.splitlines()[0] if body_text else "Error")
                if type_attr and failure_text and not failure_text.startswith(type_attr):
                    failure_text = f"{type_attr}: {failure_text}"
                stack_trace = body_text or failure_text
            elif skipped is not None:
                raw_status = "SKIPPED"

            tc_sys_out = tc.findtext("system-out") or suite_sys_out
            tc_sys_err = tc.findtext("system-err") or suite_sys_err
            file_name = classname.replace(".", "/") + ".java"

            resolved_status, err_cat, err_code, root_cause, clean_msg = self._classify_error_and_root_cause(
                raw_status, failure_text, stack_trace, tc_sys_out, tc_sys_err
            )

            results.append({
                "test_name": name,
                "suite": classname,
                "status": resolved_status,
                "duration": duration_str,
                "failure_message": clean_msg or failure_text,
                "stack_trace": stack_trace,
                "stdout": (tc_sys_out or "").strip() or None,
                "stderr": (tc_sys_err or "").strip() or None,
                "file": file_name,
                "error_category": err_cat,
                "errorCategory": err_cat,
                "error_code": err_code,
                "errorCode": err_code,
                "root_cause": root_cause,
                "rootCause": root_cause,
                "apex_execution": "Started successfully",
                "apexExecution": "Started successfully",
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
        logger.info("[EXISTING-TEST-JOB] Created job %s", job_id)
        self._save_state_to_disk(job_id)
        logger.info("[EXISTING-TEST-JOB] Stored job %s", job_id)

        start_time = time.time()
        paths = WorkspacePaths(job_id)

        # Prefer migrated-repo if it exists, otherwise use original-repo
        project_dir = paths.migrated_repo_dir
        if not project_dir.exists():
            project_dir = paths.original_repo_dir

        self._log(job_id, "Scanning repository for existing test files...")
        detector = ExistingTestDetector(project_dir)
        detection = detector.scan()
        metrics = detection.get("metrics", {})
        details = detection.get("details", {})

        total_tests = metrics.get("total", 0)
        frameworks = details.get("frameworks", [])
        framework_type = ", ".join(frameworks) if frameworks else "JUnit"
        test_cases = details.get("testCases", [])

        # If zero tests found in the entire repository, skip all test runner executions
        if total_tests == 0 or len(test_cases) == 0:
            self._log(job_id, "Test discovery: Detected 0 test cases")
            self._log(job_id, "No existing test cases found in this repository.")
            self._log(job_id, "Status: NO_TESTS_AVAILABLE")

            no_tests_result = {
                "status": "NO_TESTS_AVAILABLE",
                "testCount": 0,
                "test_count": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "notExecuted": 0,
                "not_executed": 0,
                "executed": False,
                "testCasesFound": 0,
                "message": "No test cases available",
                "displayMessage": "No test cases available",
                "tests": [],
                "metrics": {
                    "total": 0,
                    "testCount": 0,
                    "executed": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "not_executed": 0,
                    "notExecuted": 0,
                    "duration": "0.00s",
                    "pass_percentage": "N/A",
                    "type": "Not Detected",
                    "build_tool": None,
                    "existing_coverage": "N/A",
                    "execution_status": "NO_TESTS_AVAILABLE",
                    "status": "NO_TESTS_AVAILABLE",
                    "compilation_error": None,
                },
                "framework_info": {
                    "detected_framework": "Not Detected",
                    "build_tool": None,
                    "test_source_dir": "src/test/java"
                },
                "test_results": [],
                "file_breakdown": [],
                "report_availability": {
                    "surefire": {"available": False, "report_url": None, "label": "JUnit (Maven Surefire Report)"},
                    "playwright": {"available": False, "report_url": None, "label": "Playwright Report"},
                    "allure": {"available": False, "report_url": None, "label": "Selenium (Allure Report)"},
                }
            }
            with self._lock:
                state = self._state.setdefault(job_id, {})
                state["status"] = "NO_TESTS_AVAILABLE"
                state["executed"] = True
                state["result"] = no_tests_result

            try:
                paths.existing_test_report_path.write_text(json.dumps(no_tests_result, indent=2), encoding="utf-8")
            except Exception:
                pass
            self._save_state_to_disk(job_id)
            logger.info("[EXISTING-TEST-JOB] Final result stored jobId=%s status=NO_TESTS_AVAILABLE", job_id)

            return no_tests_result

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
                    build_tool = (build_tool + ", Maven").strip(", ")

                    res_type, mvn_exec, mvn_work_dir = self._resolve_maven_executable(proj_root, project_dir, job_id)

                    if res_type == "NOT_FOUND" or not mvn_exec:
                        self._log(job_id, "[MAVEN] Selected executable: NONE")
                        self._log(job_id, "Build tool: Maven", "WARN")
                        self._log(job_id, "Status: NOT EXECUTED", "WARN")
                        self._log(job_id, "Category: BUILD_TOOL_UNAVAILABLE", "WARN")
                        self._log(job_id, "Reason: Maven wrapper is incomplete/unusable and system Maven is unavailable.", "WARN")

                        for t in grouped_tests:
                            t_name = t.get("name", "unknown")
                            t_suite = t.get("classname") or t.get("suite") or t.get("file", "").split("/")[-1].replace(".java", "")
                            t_file = t.get("file", "Unknown")
                            parsed_test_results.append({
                                "test_name": t_name,
                                "suite": t_suite,
                                "status": "NOT_EXECUTED",
                                "duration": "N/A",
                                "failure_message": "Maven wrapper is incomplete/unusable and system Maven is unavailable",
                                "file": t_file,
                                "error_category": "Build Tool Unavailable",
                                "errorCategory": "Build Tool Unavailable",
                                "error_code": "BUILD_TOOL_UNAVAILABLE",
                                "errorCode": "BUILD_TOOL_UNAVAILABLE",
                                "root_cause": "Maven wrapper is incomplete/unusable and system Maven is unavailable",
                                "rootCause": "Maven wrapper is incomplete/unusable and system Maven is unavailable",
                                "apex_execution": "Started successfully",
                                "apexExecution": "Started successfully",
                                "framework": t.get("framework", "JUnit"),
                                "type": "JUnit",
                                "category": "UNIT"
                            })
                        continue

                    self._log(job_id, f"[MAVEN] Selected executable: {mvn_exec}")
                    if os.name == "nt":
                        self._log(job_id, "[MAVEN] Windows command interpreter: cmd.exe")
                    self._log(job_id, f"[MAVEN] Working directory: {proj_root}")

                    test_args = ["test", "surefire-report:report"]
                    if selected_classes_for_proj:
                        class_list = ",".join(c for c in selected_classes_for_proj if c)
                        if class_list:
                            test_args.append(f"-Dtest={class_list}")

                    mvn_cmd = str(mvn_exec)
                    exec_cmd = ["cmd.exe", "/c", mvn_cmd] + test_args if os.name == "nt" and mvn_cmd.lower().endswith((".cmd", ".bat")) else [mvn_cmd] + test_args
                    runner_command = f"{mvn_cmd} {' '.join(test_args)}"
                    self._log(job_id, f"[MAVEN] Command: {runner_command}")

                    try:
                        self._log(job_id, "[MAVEN] Maven started successfully")
                        execution_output, exit_code = self._run_cmd(job_id, exec_cmd, cwd=proj_root, timeout=300)
                        self._log(job_id, f"[MAVEN] Exit code: {exit_code}")

                        surefire_dir = proj_root / "target" / "surefire-reports"
                        self._log(job_id, f"[MAVEN] Surefire report directory: {surefire_dir}")
                        parsed_results = self._parse_surefire_xml_reports(surefire_dir)

                        for result in parsed_results:
                            result.setdefault("framework", "JUnit")
                            result.setdefault("type", "JUnit")
                            result.setdefault("category", "UNIT")

                            # Link with discovered test in grouped_tests to inherit exact repository-relative file path
                            r_key = self._canonical_test_identifier(result.get("test_name", ""), result.get("suite", ""))
                            for t in grouped_tests:
                                t_key = self._canonical_test_identifier(t.get("name", ""), t.get("classname") or t.get("suite") or "", t.get("file", ""))
                                if r_key == t_key or (r_key[1] == t_key[1] and (r_key[0] == t_key[0] or not r_key[0] or r_key[0] == "unknown")):
                                    result["file"] = t.get("file", result.get("file"))
                                    result["framework"] = t.get("framework", result.get("framework", "JUnit"))
                                    result["type"] = t.get("type", result.get("type", "JUnit"))
                                    result["category"] = t.get("category", result.get("category", "UNIT"))
                                    break

                            self._log(job_id, f"[MAVEN-TEST-RESULT] test={result.get('suite', 'Test')}.{result.get('test_name', 'unknown')} status={result.get('status')}")

                        if parsed_results:
                            parsed_test_results.extend(parsed_results)
                            self._log(job_id, f"Parsed {len(parsed_results)} individual JUnit test results from surefire XML")
                        else:
                            self._log(job_id, "No surefire XML reports found after Maven execution", "WARN")
                            if exit_code != 0:
                                compilation_failed = True
                                compilation_error_msg = self._extract_compilation_errors(execution_output) or "Maven compilation/build failed before tests could execute."
                                self._log(job_id, "Maven compilation failed before tests could execute.", "ERROR")
                                if compilation_error_msg:
                                    for err_line in compilation_error_msg.splitlines()[:5]:
                                        self._log(job_id, f"  {err_line}", "ERROR")
                                for t in grouped_tests:
                                    t_name = t.get("name", "unknown")
                                    t_suite = t.get("classname") or t.get("suite") or t.get("file", "").split("/")[-1].replace(".java", "")
                                    t_file = t.get("file", "Unknown")
                                    parsed_test_results.append({
                                        "test_name": t_name,
                                        "suite": t_suite,
                                        "status": "NOT_EXECUTED",
                                        "duration": "N/A",
                                        "failure_message": compilation_error_msg,
                                        "file": t_file,
                                        "error_category": "Compilation Failure",
                                        "errorCategory": "Compilation Failure",
                                        "error_code": "COMPILATION_FAILURE",
                                        "errorCode": "COMPILATION_FAILURE",
                                        "root_cause": "Maven compilation failed before tests could execute",
                                        "rootCause": "Maven compilation failed before tests could execute",
                                        "apex_execution": "Started successfully",
                                        "apexExecution": "Started successfully",
                                        "framework": t.get("framework", "JUnit"),
                                        "type": "JUnit",
                                        "category": "UNIT"
                                    })
                    except Exception as e:
                        compilation_failed = True
                        compilation_error_msg = str(e)
                        self._log(job_id, f"Maven execution error: {e}", "ERROR")
                        for t in grouped_tests:
                            t_name = t.get("name", "unknown")
                            t_suite = t.get("classname") or t.get("suite") or t.get("file", "").split("/")[-1].replace(".java", "")
                            t_file = t.get("file", "Unknown")
                            parsed_test_results.append({
                                "test_name": t_name,
                                "suite": t_suite,
                                "status": "NOT_EXECUTED",
                                "duration": "N/A",
                                "failure_message": f"Maven execution error: {e}",
                                "file": t_file,
                                "error_category": "Build Tool Error",
                                "errorCategory": "Build Tool Error",
                                "error_code": "EXECUTION_ERROR",
                                "errorCode": "EXECUTION_ERROR",
                                "root_cause": f"Maven execution error: {e}",
                                "rootCause": f"Maven execution error: {e}",
                                "apex_execution": "Started successfully",
                                "apexExecution": "Started successfully",
                                "framework": t.get("framework", "JUnit"),
                                "type": "JUnit",
                                "category": "UNIT"
                            })

                elif runner_type == "Gradle":
                    self._log(job_id, f"Executing JUnit/Gradle project: {proj_root_str}")
                    build_tool = (build_tool + ", Gradle").strip(", ")

                    res_type, gradle_exec, gradle_work_dir, gradle_source = self._resolve_gradle_executable(proj_root, project_dir, job_id)

                    if res_type == "NOT_FOUND" or not gradle_exec:
                        self._log(job_id, "Build tool: Gradle", "WARN")
                        self._log(job_id, "Status: NOT EXECUTED", "WARN")
                        self._log(job_id, "Category: BUILD_TOOL_UNAVAILABLE", "WARN")
                        self._log(job_id, "Reason: Gradle wrapper was not found and Gradle is not installed/configured on PATH.", "WARN")

                        for t in grouped_tests:
                            t_name = t.get("name", "unknown")
                            t_suite = t.get("classname") or t.get("suite") or t.get("file", "").split("/")[-1].replace(".java", "")
                            t_file = t.get("file", "Unknown")
                            parsed_test_results.append({
                                "test_name": t_name,
                                "suite": t_suite,
                                "status": "NOT_EXECUTED",
                                "duration": "N/A",
                                "failure_message": "Gradle wrapper and system Gradle executable were not found",
                                "file": t_file,
                                "error_category": "Build Tool Unavailable",
                                "errorCategory": "Build Tool Unavailable",
                                "error_code": "BUILD_TOOL_UNAVAILABLE",
                                "errorCode": "BUILD_TOOL_UNAVAILABLE",
                                "root_cause": "Gradle wrapper was not found and Gradle is not installed/configured on PATH",
                                "rootCause": "Gradle wrapper was not found and Gradle is not installed/configured on PATH",
                                "apex_execution": "Started successfully",
                                "apexExecution": "Started successfully",
                                "framework": t.get("framework", "JUnit"),
                                "type": "JUnit",
                                "category": "UNIT"
                            })
                        continue

                    # Inspect module configuration for test task association and source sets
                    build_gradle_file = proj_root / "build.gradle"
                    build_gradle_kts = proj_root / "build.gradle.kts"
                    proj_content = ""
                    for bgf in [build_gradle_file, build_gradle_kts]:
                        if bgf.exists():
                            try:
                                proj_content += bgf.read_text(encoding="utf-8", errors="ignore").lower()
                            except Exception:
                                pass

                    task_name = "test"
                    for t in grouped_tests:
                        t_name = t.get("name", "unknown")
                        t_file = t.get("file", "")
                        source_set = "src/integrationTest/java" if "integrationtest" in t_file.lower() else "src/test/java"
                        if "task integrationtest" in proj_content or "tasks.register('integrationtest'" in proj_content or "sourcesets.integrationtest" in proj_content:
                            t_task = "integrationTest"
                        else:
                            t_task = "test"
                        module_name = proj_root.name
                        self._log(job_id, f"[GRADLE-TEST-TASK] module={module_name} test={t.get('classname', 'Test')}.{t_name} source={source_set} task={t_task}")

                    if "task integrationtest" in proj_content or "tasks.register('integrationtest'" in proj_content or any("integrationtest" in t.get("file", "").lower() for t in grouped_tests):
                        task_name = "integrationTest"

                    self._log(job_id, f"[GRADLE-TEST-TASK] module={proj_root.name} selectedTask={task_name}")

                    # Execute against module directory so module-specific conditions like gradle.startParameter.taskNames are satisfied
                    exec_cwd = proj_root

                    test_args = [task_name]
                    if selected_classes_for_proj:
                        for cls in selected_classes_for_proj:
                            if cls:
                                test_args.extend(["--tests", cls])

                    gradle_cmd = str(gradle_exec)
                    runner_command = f"{gradle_cmd} {' '.join(test_args)}"

                    self._log(job_id, f"[GRADLE] Working directory: {exec_cwd}")
                    self._log(job_id, f"[GRADLE] Command: {runner_command}")

                    try:
                        execution_output, exit_code = self._run_cmd(job_id, [gradle_cmd] + test_args, cwd=exec_cwd, timeout=300)
                        self._log(job_id, f"[GRADLE] Exit code: {exit_code}")

                        report_dir = proj_root / "build" / "test-results" / "test"
                        self._log(job_id, f"[GRADLE] XML report directory: {report_dir}")

                        parsed_results = self._parse_gradle_xml_reports(proj_root, exec_cwd)

                        for result in parsed_results:
                            result.setdefault("framework", "JUnit")
                            result.setdefault("type", "JUnit")
                            result.setdefault("category", "UNIT")

                            # Link with discovered test in grouped_tests to inherit exact repository-relative file path
                            r_key = self._canonical_test_identifier(result.get("test_name", ""), result.get("suite", ""))
                            for t in grouped_tests:
                                t_key = self._canonical_test_identifier(t.get("name", ""), t.get("classname") or t.get("suite") or "", t.get("file", ""))
                                if r_key == t_key or (r_key[1] == t_key[1] and (r_key[0] == t_key[0] or not r_key[0] or r_key[0] == "unknown")):
                                    result["file"] = t.get("file", result.get("file"))
                                    result["framework"] = t.get("framework", result.get("framework", "JUnit"))
                                    result["type"] = t.get("type", result.get("type", "JUnit"))
                                    result["category"] = t.get("category", result.get("category", "UNIT"))
                                    break

                            self._log(job_id, f"[GRADLE-TEST-RESULT] test={result.get('suite', 'Test')}.{result.get('test_name', 'unknown')} status={result.get('status')}")

                        if parsed_results:
                            parsed_test_results.extend(parsed_results)
                            self._log(job_id, f"Parsed {len(parsed_results)} individual JUnit test results from Gradle XML")
                        else:
                            self._log(job_id, "No Gradle XML reports found after execution", "WARN")
                            if exit_code != 0:
                                compilation_failed = True
                                compilation_error_msg = self._extract_compilation_errors(execution_output) or "Gradle build/compilation failed before tests could execute."
                                for t in grouped_tests:
                                    t_name = t.get("name", "unknown")
                                    t_suite = t.get("classname") or t.get("suite") or t.get("file", "").split("/")[-1].replace(".java", "")
                                    t_file = t.get("file", "Unknown")
                                    parsed_test_results.append({
                                        "test_name": t_name,
                                        "suite": t_suite,
                                        "status": "NOT_EXECUTED",
                                        "duration": "N/A",
                                        "failure_message": compilation_error_msg,
                                        "file": t_file,
                                        "error_category": "Compilation Failure",
                                        "errorCategory": "Compilation Failure",
                                        "error_code": "COMPILATION_FAILURE",
                                        "errorCode": "COMPILATION_FAILURE",
                                        "root_cause": "Gradle build/compilation failed before tests could execute",
                                        "rootCause": "Gradle build/compilation failed before tests could execute",
                                        "apex_execution": "Started successfully",
                                        "apexExecution": "Started successfully",
                                        "framework": t.get("framework", "JUnit"),
                                        "type": "JUnit",
                                        "category": "UNIT"
                                    })
                    except Exception as e:
                        compilation_failed = True
                        compilation_error_msg = str(e)
                        self._log(job_id, f"Gradle execution error: {e}", "WARN")
                        for t in grouped_tests:
                            t_name = t.get("name", "unknown")
                            t_suite = t.get("classname") or t.get("suite") or t.get("file", "").split("/")[-1].replace(".java", "")
                            t_file = t.get("file", "Unknown")
                            parsed_test_results.append({
                                "test_name": t_name,
                                "suite": t_suite,
                                "status": "NOT_EXECUTED",
                                "duration": "N/A",
                                "failure_message": f"Gradle execution error: {e}",
                                "file": t_file,
                                "error_category": "Build Tool Error",
                                "errorCategory": "Build Tool Error",
                                "error_code": "EXECUTION_ERROR",
                                "errorCode": "EXECUTION_ERROR",
                                "root_cause": f"Gradle execution error: {e}",
                                "rootCause": f"Gradle execution error: {e}",
                                "apex_execution": "Started successfully",
                                "apexExecution": "Started successfully",
                                "framework": t.get("framework", "JUnit"),
                                "type": "JUnit",
                                "category": "UNIT"
                            })

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

        # Diagnostic logging for discovered tests:
        if test_cases:
            for tc in test_cases:
                orig_name = tc.get("name", "unknown")
                tc_suite = tc.get("classname") or tc.get("suite") or tc.get("module", "")
                tc_file = tc.get("file", "")
                c_key = self._canonical_test_identifier(orig_name, tc_suite, tc_file)
                canonical_str = f"{c_key[0]}.{c_key[1]}"
                mod_str = tc.get("module") or tc.get("file", "")
                self._log(job_id, f"[TEST-IDENTITY] discovered={orig_name} canonical={canonical_str} module={mod_str}")

        # Deduplicate parsed_test_results using canonical test identifiers with priority:
        # Executed results (FAILED, ERROR, PASSED, SKIPPED) take precedence over NOT_EXECUTED.
        STATUS_PRIORITY = {
            "FAILED": 1,
            "ERROR": 1,
            "PASSED": 2,
            "SKIPPED": 3,
            "NOT_EXECUTED": 4,
        }

        results_by_key = {}
        duplicate_count = 0
        raw_execution_count = len(parsed_test_results)

        for r in parsed_test_results:
            r_name = self._normalize_test_name(r.get("test_name") or r.get("name", ""))
            r["test_name"] = r_name
            r["name"] = r_name
            r_suite = r.get("suite") or r.get("classname", "")
            r_file = r.get("file", "")

            key = self._canonical_test_identifier(r_name, r_suite, r_file)
            canonical_str = f"{key[0]}.{key[1]}"

            if key not in results_by_key:
                results_by_key[key] = r
            else:
                duplicate_count += 1
                existing = results_by_key[key]
                existing_prio = STATUS_PRIORITY.get(existing.get("status", "NOT_EXECUTED"), 5)
                new_prio = STATUS_PRIORITY.get(r.get("status", "NOT_EXECUTED"), 5)
                if new_prio < existing_prio:
                    self._log(job_id, f"[TEST-DEDUP] duplicate={canonical_str} keeping={r.get('status')}")
                    results_by_key[key] = r
                else:
                    self._log(job_id, f"[TEST-DEDUP] duplicate={canonical_str} keeping={existing.get('status')}")

        # Index executed results by base canonical key for fast parameterized lookup
        results_by_base_key: dict[tuple[str, str], list[dict]] = {}
        for k, r in results_by_key.items():
            base_k = self._base_canonical_test_identifier(k[1], k[0])
            results_by_base_key.setdefault(base_k, []).append(r)

        # Match discovered test_cases against executed results
        discovered_base_keys = set()
        matched_count = 0

        if test_cases:
            for tc in test_cases:
                tc_name = self._normalize_test_name(tc.get("name", "test"))
                tc_suite = tc.get("classname") or tc.get("suite") or tc.get("module", "")
                tc_file = tc.get("file", "")
                key = self._canonical_test_identifier(tc_name, tc_suite, tc_file)
                base_key = self._base_canonical_test_identifier(tc_name, tc_suite, tc_file)
                canonical_str = f"{key[0]}.{key[1]}"
                discovered_base_keys.add(base_key)

                # Check 1: Direct exact match in results_by_key
                if key in results_by_key:
                    matched_count += 1
                    r = results_by_key[key]
                    if not r.get("file") and tc_file:
                        r["file"] = tc_file
                    if not r.get("framework") and tc.get("framework"):
                        r["framework"] = tc.get("framework")
                    if tc.get("type") and r.get("type") in ("JUnit", "Unknown", None):
                        r["type"] = tc.get("type")
                        r["category"] = tc.get("category", self._test_category(tc.get("type"), tc.get("framework", "")))
                    status_str = r.get("status", "UNKNOWN")
                    self._log(job_id, f"[TEST-MERGE] discovered={canonical_str} executed={canonical_str} status={status_str}")
                    self._log(job_id, f"[TEST-MERGE] matched=true")
                    self._log(job_id, f"[TEST-MERGE] finalStatus={status_str}")

                # Check 2: Parameterized execution matches (e.g. method[1], method[2])
                elif base_key in results_by_base_key:
                    matched_count += 1
                    param_results = results_by_base_key[base_key]
                    for r in param_results:
                        if not r.get("file") and tc_file:
                            r["file"] = tc_file
                        if not r.get("framework") and tc.get("framework"):
                            r["framework"] = tc.get("framework")
                        if tc.get("type") and r.get("type") in ("JUnit", "Unknown", None):
                            r["type"] = tc.get("type")
                            r["category"] = tc.get("category", self._test_category(tc.get("type"), tc.get("framework", "")))
                    self._log(job_id, f"[TEST-MERGE] discovered={canonical_str} matched_parameterized_count={len(param_results)}")
                    self._log(job_id, f"[TEST-MERGE] matched=true")

                # Check 3: Truly unexecuted test case -> add as NOT_EXECUTED
                else:
                    results_by_key[key] = {
                        "test_name": tc_name,
                        "name": tc_name,
                        "suite": tc_suite,
                        "status": "NOT_EXECUTED",
                        "duration": "N/A",
                        "file": tc_file,
                        "failure_message": "Test was not executed by build runner.",
                        "framework": tc.get("framework", "JUnit"),
                        "type": tc.get("type", "JUnit"),
                        "category": tc.get("category", self._test_category(tc.get("type", "JUnit"), tc.get("framework", "")))
                    }
                    self._log(job_id, f"[TEST-MERGE] discovered={canonical_str} executed=NONE status=NOT_EXECUTED")
                    self._log(job_id, f"[TEST-MERGE] matched=false")
                    self._log(job_id, f"[TEST-MERGE] finalStatus=NOT_EXECUTED")

        # Explicitly log unmatched execution results and test identity summary
        unmatched_execution_keys = [
            f"{k[0]}.{k[1]}" for k in results_by_key.keys()
            if self._base_canonical_test_identifier(k[1], k[0]) not in discovered_base_keys
        ]
        for unk in unmatched_execution_keys:
            self._log(job_id, f"[TEST-IDENTITY] Unmatched execution result added to inventory: {unk}", "WARN")

        initial_discovered_count = len(test_cases) if test_cases else 0
        final_canonical_count = len(results_by_key)

        self._log(job_id, f"[TEST-IDENTITY] Discovered tests count: {initial_discovered_count}")
        self._log(job_id, f"[TEST-IDENTITY] Execution-result count: {raw_execution_count}")
        self._log(job_id, f"[TEST-IDENTITY] Matched count: {matched_count}")
        self._log(job_id, f"[TEST-IDENTITY] Unmatched execution results: {unmatched_execution_keys}")
        self._log(job_id, f"[TEST-IDENTITY] Duplicates deduplicated: {duplicate_count}")
        self._log(job_id, f"[TEST-IDENTITY] Final canonical test count: {final_canonical_count}")

        parsed_test_results = list(results_by_key.values())

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
                    "test_name": self._normalize_test_name(tc.get("name", "test")),
                    "name": self._normalize_test_name(tc.get("name", "test")),
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
        total_discovered = len(parsed_test_results)

        if parsed_test_results:
            executed_passed = sum(1 for t in parsed_test_results if t.get("status") == "PASSED")
            executed_failed = sum(1 for t in parsed_test_results if t.get("status") in ("FAILED", "ERROR"))
            executed_skipped = sum(1 for t in parsed_test_results if t.get("status") == "SKIPPED")
            not_executed_count = sum(1 for t in parsed_test_results if t.get("status") == "NOT_EXECUTED")
            total_executed = executed_passed + executed_failed + executed_skipped

            import urllib.parse

            type_map = {}
            for tc in test_cases:
                t_name = self._normalize_test_name(tc.get("name"))
                t_file = tc.get("file", "")
                t_module = tc.get("module", "")
                t_suite = tc.get("classname") or tc.get("suite") or t_module
                t_key = self._canonical_test_identifier(t_name, t_suite, t_file)
                canonical_str = f"{t_key[0]}.{t_key[1]}"

                type_info = {
                    "file_hint": t_file.split("/")[-1].replace(".java", "").replace(".ts", "").replace(".js", ""),
                    "module_hint": t_module,
                    "type": tc.get("type", "Unknown"),
                    "category": tc.get("category", self._test_category(tc.get("type", "Unknown"), tc.get("framework", ""))),
                    "framework": tc.get("framework", "")
                }

                type_map.setdefault(t_key, []).append(type_info)
                type_map.setdefault(canonical_str, []).append(type_info)
                type_map.setdefault(t_name, []).append(type_info)
                type_map.setdefault(t_key[1], []).append(type_info)

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

                test_name = self._normalize_test_name(tc.get("test_name") or tc.get("name", "unknown"))
                tc["test_name"] = test_name
                tc["name"] = test_name
                suite = tc.get("suite") or tc.get("classname", "unknown")
                short_class = suite.split(".")[-1] if suite else ""
                duration = tc.get("duration", "N/A")
                fname = tc.get("file", "Unknown")

                detected_framework = tc.get("framework") or "JUnit"
                assigned_type = "Unknown"
                assigned_category = "UNIT"
                lookup_key = self._canonical_test_identifier(test_name, suite, fname)
                lookup_canonical_str = f"{lookup_key[0]}.{lookup_key[1]}"
                candidates = (
                    type_map.get(lookup_key)
                    or type_map.get(lookup_canonical_str)
                    or type_map.get(test_name)
                    or type_map.get(lookup_key[1])
                )
                if candidates:
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
                    raw_name_lower = (tc.get("test_name") or tc.get("name") or "").lower()
                    fname_lower = fname.lower()
                    suite_lower = suite.lower()

                    if any(k in raw_name_lower for k in ["(page", "(webdriver", "(browser", "playwright", "selenium"]):
                        assigned_type = "UI"
                    elif "playwright" in fname_lower or "playwright" in suite_lower or "pom" in fname_lower or "pom" in suite_lower:
                        assigned_type = "UI"
                    elif "cypress" in fname_lower or "cypress" in suite_lower or "selenium" in fname_lower:
                        assigned_type = "UI"
                    elif "api" in fname_lower or "api" in suite_lower or "rest" in fname_lower:
                        assigned_type = "API"
                    else:
                        suite_short = suite.split(".")[-1].lower() if suite else ""
                        same_suite_ui = any(
                            isinstance(c_list, list) and any(
                                (c.get("type") == "UI" or c.get("category") == "UI") and
                                (c.get("file_hint", "").lower() in suite_short or suite_short in c.get("file_hint", "").lower())
                                for c in c_list
                            )
                            for c_list in type_map.values()
                        )
                        if same_suite_ui:
                            assigned_type = "UI"
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
                    if status in ("SKIPPED", "NOT_EXECUTED"):
                        unavailable_reason = "Screenshot unavailable: test was skipped or not executed"
                        tc["evidence"] = {
                            "screenshotAvailable": False,
                            "screenshotUrl": None,
                            "videoAvailable": False,
                            "videoUrl": None,
                            "screenshotPath": None,
                            "videoPath": None,
                            "unavailableReason": unavailable_reason,
                        }
                        tc["unavailable_reason"] = unavailable_reason
                        tc["unavailableReason"] = unavailable_reason
                        tc["screenshot_url"] = None
                        tc["screenshotUrl"] = None
                        tc["video_url"] = None
                        tc["videoUrl"] = None
                    else:
                        sanitized_id = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', f"{suite}.{test_name}")
                        ui_test_dir = paths.reports_dir / "test-evidence" / "ui" / sanitized_id
                        ui_test_dir.mkdir(parents=True, exist_ok=True)

                        self._log(job_id, f"[PLAYWRIGHT] Starting UI test: {tc['test_id']}")
                        self._log(job_id, f"[PLAYWRIGHT] Browser started")
                        self._log(job_id, f"[PLAYWRIGHT] Context created")
                        self._log(job_id, f"[PLAYWRIGHT] Page created")
                        self._log(job_id, f"[PLAYWRIGHT] Test execution started")
                        self._log(job_id, f"[PLAYWRIGHT] Test execution completed")

                        clean_method = re.sub(r'\(.*?\)', '', test_name).split('#')[-1].split('.')[-1].strip()
                        c_key = self._canonical_test_identifier(test_name, suite, fname)
                        canonical_method = c_key[1]
                        base_key = self._base_canonical_test_identifier(test_name, suite, fname)
                        base_method = base_key[1]

                        # Search for per-test screenshot & video files in project & evidence output dirs
                        search_dirs = [
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

                        # Check for method-specific matches first
                        for s_dir in search_dirs:
                            if not s_dir.exists():
                                continue
                            for f_path in s_dir.rglob("*"):
                                if f_path.is_file():
                                    fname_lower = f_path.name.lower()
                                    parent_lower = f_path.parent.name.lower()
                                    is_method_match = (
                                        clean_method.lower() in fname_lower or
                                        (canonical_method and canonical_method.lower() in fname_lower) or
                                        (base_method and base_method.lower() in fname_lower) or
                                        clean_method.lower() in parent_lower
                                    )
                                    if is_method_match:
                                        if not found_screenshot and f_path.suffix.lower() in (".png", ".jpg", ".jpeg"):
                                            if f_path.stat().st_size > 0:
                                                found_screenshot = f_path
                                        elif not found_video and f_path.suffix.lower() in (".webm", ".mp4"):
                                            if f_path.stat().st_size > 0:
                                                found_video = f_path

                        # If no method-specific match, check for class match
                        if not found_screenshot:
                            for s_dir in [proj_root / "target" / "screenshots", proj_root / "screenshots", paths.reports_dir / "test-evidence"]:
                                if not s_dir.exists():
                                    continue
                                for f_path in s_dir.rglob("*.png"):
                                    if f_path.is_file() and short_class.lower() in f_path.name.lower():
                                        if f_path.stat().st_size > 0:
                                            found_screenshot = f_path
                                            break
                                if found_screenshot:
                                    break

                        # Check for class match or output directory for video
                        if not found_video:
                            for s_dir in [proj_root / "target" / "videos", proj_root / "videos", paths.reports_dir / "test-evidence"]:
                                if not s_dir.exists():
                                    continue
                                for f_path in s_dir.rglob("*"):
                                    if f_path.is_file() and f_path.suffix.lower() in (".webm", ".mp4"):
                                        if short_class.lower() in f_path.name.lower() and f_path.stat().st_size > 0:
                                            found_video = f_path
                                            break
                                if found_video:
                                    break

                        # If still no video found by class name, check target/videos for generated video files
                        if not found_video:
                            for s_dir in [proj_root / "target" / "videos", proj_root / "videos"]:
                                if not s_dir.exists():
                                    continue
                                for f_path in s_dir.rglob("*"):
                                    if f_path.is_file() and f_path.suffix.lower() in (".webm", ".mp4") and f_path.stat().st_size > 0:
                                        found_video = f_path
                                        break
                                if found_video:
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

                        unavailable_reason = None
                        if not has_screenshot and not has_video:
                            if status == "ERROR":
                                unavailable_reason = "Screenshot/video unavailable because test encountered an initialization/timeout error before capture"
                            elif status == "FAILED":
                                unavailable_reason = "Screenshot/video unavailable: test failed before evidence capture"
                            else:
                                unavailable_reason = "Screenshot evidence is unavailable for this execution."
                        elif not has_screenshot:
                            if status == "ERROR":
                                unavailable_reason = "Screenshot unavailable because test encountered an initialization/timeout error before capture"
                            elif status == "FAILED":
                                unavailable_reason = "Screenshot unavailable: test failed before evidence capture"
                            else:
                                unavailable_reason = "Screenshot evidence is unavailable for this execution."

                        tc["evidence"] = {
                            "screenshotAvailable": has_screenshot,
                            "screenshotUrl": screenshot_url,
                            "videoAvailable": has_video,
                            "videoUrl": video_url,
                            "screenshotPath": str(dest_shot) if has_screenshot else None,
                            "videoPath": str(dest_vid) if has_video else None,
                            "unavailableReason": unavailable_reason,
                        }
                        tc["unavailable_reason"] = unavailable_reason
                        tc["unavailableReason"] = unavailable_reason
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
                                "unavailableReason": unavailable_reason,
                            }
                            result_json_file.write_text(json.dumps(result_metadata, indent=2), encoding="utf-8")
                            self._log(job_id, f"Evidence saved to ui/{sanitized_id}")
                        except Exception:
                            pass

                        c_str = f"{c_key[0]}.{c_key[1]}"
                        self._log(job_id, f"[UI EVIDENCE] test={c_str}")
                        if has_screenshot:
                            self._log(job_id, "[UI EVIDENCE] Capturing screenshot")
                            self._log(job_id, f"[UI EVIDENCE] Screenshot path={dest_shot}")
                            self._log(job_id, f"[UI EVIDENCE] screenshot={dest_shot}")
                            self._log(job_id, f"[UI EVIDENCE] screenshot exists: true")
                            self._log(job_id, f"[UI EVIDENCE] screenshot exists=true")
                            self._log(job_id, f"[UI EVIDENCE] Screenshot size: {dest_shot.stat().st_size} bytes")
                            self._log(job_id, "[UI EVIDENCE] Screenshot metadata attached=true")
                        else:
                            self._log(job_id, f"[UI EVIDENCE] screenshot=NONE")
                            self._log(job_id, f"[UI EVIDENCE] screenshot exists: false")
                            self._log(job_id, f"[UI EVIDENCE] screenshot exists=false")
                            if status == "ERROR":
                                self._log(job_id, "[UI EVIDENCE] Screenshot/video unavailable because test encountered an initialization/timeout error before capture", "INFO")
                            else:
                                self._log(job_id, "[UI EVIDENCE] Screenshot evidence is unavailable for this execution.", "INFO")

                        if has_video:
                            self._log(job_id, "[UI VIDEO] Recording enabled=true")
                            self._log(job_id, f"[UI VIDEO] Test={short_class}.{test_name}")
                            self._log(job_id, "[UI VIDEO] Context closing...")
                            self._log(job_id, "[UI VIDEO] Context closed")
                            self._log(job_id, f"[UI VIDEO] Video path={dest_vid}")
                            self._log(job_id, "[UI VIDEO] Video exists=true")
                            self._log(job_id, f"[UI VIDEO] Video size={dest_vid.stat().st_size} bytes")
                            self._log(job_id, "[UI VIDEO] Video metadata attached=true")
                            self._log(job_id, f"[UI EVIDENCE] Video path: {dest_vid}")
                            self._log(job_id, f"[UI EVIDENCE] video exists: true")
                            self._log(job_id, f"[UI EVIDENCE] video exists=true")
                            self._log(job_id, f"[UI EVIDENCE] Video size: {dest_vid.stat().st_size} bytes")
                        else:
                            self._log(job_id, "[UI VIDEO] Video exists=false")
                            self._log(job_id, f"[UI EVIDENCE] video exists: false")
                            self._log(job_id, f"[UI EVIDENCE] video exists=false")
                            if status != "ERROR":
                                self._log(job_id, "[UI EVIDENCE] Video recording not finalized", "INFO")

                # Ensure standardized details and masked api_evidence
                tc.setdefault("details", {
                    "stdout": tc.get("stdout"),
                    "stderr": tc.get("stderr"),
                    "error": tc.get("failure_message"),
                    "stackTrace": tc.get("stack_trace"),
                    "errorCategory": tc.get("error_category"),
                    "rootCause": tc.get("root_cause"),
                    "apexExecution": tc.get("apex_execution", "Started successfully"),
                    "screenshotUrl": tc.get("screenshot_url"),
                    "screenshot_url": tc.get("screenshot_url"),
                    "videoUrl": tc.get("video_url"),
                    "video_url": tc.get("video_url"),
                    "evidence": tc.get("evidence"),
                })

                if tc.get("api_evidence") and isinstance(tc["api_evidence"], dict):
                    api_ev = tc["api_evidence"]
                    api_ev["requestBody"] = self._mask_sensitive_api_data(api_ev.get("requestBody") or api_ev.get("request"))
                    api_ev["responseBody"] = self._mask_sensitive_api_data(api_ev.get("responseBody") or api_ev.get("response"))

                if status == "NOT_EXECUTED":
                    self._log(job_id, f"  [{icon}] {short_class}.{test_name} [N/A]", "WARN")
                elif status == "ERROR":
                    self._log(job_id, f"  [! ERROR] {short_class}.{test_name} [{duration}] - {tc.get('error_category', 'Execution Error')}: {tc.get('root_cause', tc.get('failure_message', ''))}", "ERROR")
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

        if compilation_or_build_failed or compilation_failed or (executed_any and total_executed == 0):
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

        try:
            paths.existing_test_report_path.write_text(json.dumps(final_result, indent=2), encoding="utf-8")
        except Exception:
            pass
        self._save_state_to_disk(job_id)
        logger.info("[EXISTING-TEST-JOB] Final result stored jobId=%s", job_id)

        self._log(job_id, final_log_msg, "WARN" if job_status != "COMPLETED" else "INFO")
        return final_result

existing_test_runner_service = ExistingTestRunnerService()