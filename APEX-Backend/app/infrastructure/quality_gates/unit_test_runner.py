"""Executes unit tests via Maven/Gradle and parses JUnit XML test reports."""

from __future__ import annotations

from pathlib import Path

import defusedxml.ElementTree as ET

from app.infrastructure.java_runtime import build_tool_env
from app.schemas.unit_test import TestExecutionDetail, UnitTestSuiteResult
from app.shared.command_runner import resolve_executable, run_command


class UnitTestRunner:
    def run(
        self,
        project_dir: Path,
        *,
        build_tool: str = "maven",
        target_class_name: str | None = None,
        target_class_names: list[str] | None = None,
        test_command: str | None = None,
        target_major: int | None = None,
    ) -> UnitTestSuiteResult:
        build_tool_clean = (build_tool or "maven").lower()

        # Combine both target arguments for backward compatibility
        targets = []
        if target_class_name:
            targets.append(target_class_name)
        if target_class_names:
            for n in target_class_names:
                if n not in targets:
                    targets.append(n)

        import os
        is_windows = os.name == "nt"

        if test_command:
            import shlex
            cmd = shlex.split(test_command)
        elif build_tool_clean == "gradle":
            # Gradle Wrapper Check
            gradlew_bat = project_dir / "gradlew.bat"
            gradlew_sh = project_dir / "gradlew"
            if is_windows and gradlew_bat.exists():
                executable = str(gradlew_bat.resolve())
            elif not is_windows and gradlew_sh.exists():
                executable = str(gradlew_sh.resolve())
            else:
                executable = resolve_executable("gradle")
                if not executable:
                    executable = "gradle.bat" if is_windows else "gradle"
            cmd = [executable, "test"]
            if targets:
                for name in targets:
                    cmd.extend(["--tests", f"*{name}*"])
        else:
            # Maven Wrapper Check
            mvnw_cmd = project_dir / "mvnw.cmd"
            mvnw_sh = project_dir / "mvnw"
            if is_windows and mvnw_cmd.exists():
                executable = str(mvnw_cmd.resolve())
            elif not is_windows and mvnw_sh.exists():
                executable = str(mvnw_sh.resolve())
            else:
                executable = resolve_executable("mvn")
                if not executable:
                    executable = "mvn.cmd" if is_windows else "mvn"
            cmd = [executable, "test", "-DfailIfNoTests=false", "-Dgit.commit.id.skip=true", "-Dmaven.gitcommitid.skip=true"]
            if targets:
                cmd.append(f"-Dtest={','.join([f'*{n}*' for n in targets])}")
            # Prova also adds surefire-report:report for Maven
            cmd.append("surefire-report:report")

        # Locate XML report directory and clean stale XML reports from previous runs to prevent leaking results
        reports_dir = (
            project_dir / "target" / "surefire-reports"
            if build_tool_clean == "maven"
            else project_dir / "build" / "test-results" / "test"
        )
        if reports_dir.exists() and reports_dir.is_dir():
            try:
                for xml_file in reports_dir.glob("TEST-*.xml"):
                    xml_file.unlink(missing_ok=True)
            except OSError:
                pass

        res = run_command(cmd, cwd=project_dir, timeout=600, env=build_tool_env(target_major))

        return self.parse_junit_reports(
            reports_dir=reports_dir,
            raw_stdout=res.stdout,
            raw_stderr=res.stderr,
            exit_code=res.exit_code,
        )

    def parse_junit_reports(
        self,
        reports_dir: Path,
        raw_stdout: str = "",
        raw_stderr: str = "",
        exit_code: int = 0,
    ) -> UnitTestSuiteResult:
        import re
        existing_details: list[TestExecutionDetail] = []
        generated_details: list[TestExecutionDetail] = []

        total_count = 0
        passed_count = 0
        failed_count = 0
        skipped_count = 0

        if reports_dir.exists():
            xml_files = list(reports_dir.glob("TEST-*.xml"))
            for xml_file in xml_files:
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                except (ET.ParseError, OSError, ValueError, KeyError):
                    continue

                # Support both <testsuite> and <testsuites> roots (Prova approach)
                testsuites = []
                if root.tag == "testsuites":
                    testsuites = root.findall("testsuite")
                elif root.tag == "testsuite":
                    testsuites = [root]
                else:
                    # Fallback to direct search if tags don't match
                    testsuites = [root]

                for suite in testsuites:
                    for tc in suite.findall("testcase"):
                        total_count += 1
                        method_name = tc.get("name", "unknown")
                        class_name = tc.get("classname", "unknown")
                        time_sec = float(tc.get("time", "0.0"))

                        failure = tc.find("failure")
                        error = tc.find("error")
                        skipped = tc.find("skipped")

                        if failure is not None or error is not None:
                            failed_count += 1
                            node = failure if failure is not None else error
                            detail = TestExecutionDetail(
                                test_class=class_name,
                                test_method=method_name,
                                status="FAILED",
                                execution_time_seconds=time_sec,
                                error_message=node.get("message") if node is not None else "Test failed",
                                stack_trace=node.text if node is not None else None,
                            )
                        elif skipped is not None:
                            skipped_count += 1
                            detail = TestExecutionDetail(
                                test_class=class_name,
                                test_method=method_name,
                                status="SKIPPED",
                                execution_time_seconds=time_sec,
                            )
                        else:
                            passed_count += 1
                            detail = TestExecutionDetail(
                                test_class=class_name,
                                test_method=method_name,
                                status="PASSED",
                                execution_time_seconds=time_sec,
                            )

                        if "LLMTest" in class_name or "LLM" in method_name:
                            generated_details.append(detail)
                        else:
                            existing_details.append(detail)

        # Prova approach: Fallback to regex on console output if no XML results
        if total_count == 0 and (raw_stdout or raw_stderr):
            combined_output = raw_stdout + "\n" + raw_stderr
            pass_match = re.search(r'Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)', combined_output)
            if pass_match:
                total_count = int(pass_match.group(1))
                failed_count = int(pass_match.group(2)) + int(pass_match.group(3))
                skipped_count = int(pass_match.group(4))
                passed_count = total_count - failed_count - skipped_count

        raw_logs = [line for line in (raw_stdout + "\n" + raw_stderr).splitlines() if line.strip()]

        return UnitTestSuiteResult(
            total_run=total_count,
            passed=passed_count,
            failed=failed_count,
            skipped=skipped_count,
            existing_test_results=existing_details,
            generated_test_results=generated_details,
            raw_logs=raw_logs[:500],
        )
