from pathlib import Path

file_path = r"c:\JAVA-APEX LATEST\APEX\JavaAPEX-Backend\APEX-Backend\app\application\use_cases\existing_test_runner_service.py"
content = Path(file_path).read_text(encoding="utf-8")

start_marker = '        if project_dir.exists():\n            # Determine supported runners'
end_marker = '        # ── POST-EXECUTION PROCESSING: Calculate Metrics & Breakdown ──────────────────'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Could not find markers!")
    exit(1)

new_logic = """        def _find_project_root_for_test(test_file: str, project_dir: Path, target_files: list) -> Path | None:
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
                    except Exception as e:
                        self._log(job_id, f"Maven execution error: {e}", "WARN")

                elif runner_type == "Gradle":
                    self._log(job_id, f"Executing JUnit/Gradle project: {proj_root_str}")
                    gradle_cmd = "gradlew.bat" if os.name == "nt" else "./gradlew"

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

                        gradle_reports = proj_root / "build" / "test-results" / "test"
                        parsed_results = self._parse_surefire_xml_reports(gradle_reports)

                        for result in parsed_results:
                            result.setdefault("framework", "JUnit")
                            result.setdefault("type", "JUnit")
                            result.setdefault("category", "UNIT")

                        if parsed_results:
                            parsed_test_results.extend(parsed_results)
                            self._log(job_id, f"Parsed {len(parsed_results)} individual JUnit test results from Gradle XML")
                        else:
                            self._log(job_id, "No Gradle XML reports found after execution", "WARN")
                    except Exception as e:
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

"""

new_content = content[:start_idx] + new_logic + content[end_idx:]
Path(file_path).write_text(new_content, encoding="utf-8")
print("Successfully patched existing_test_runner_service.py!")
