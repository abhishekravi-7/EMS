"""Executes unit tests via Maven/Gradle and parses JUnit XML test reports."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from app.schemas.unit_test import TestExecutionDetail, UnitTestSuiteResult
from app.shared.command_runner import run_command, resolve_executable


class UnitTestRunner:
    def run(
        self,
        project_dir: Path,
        *,
        build_tool: str = "maven",
        target_class_name: str | None = None,
    ) -> UnitTestSuiteResult:
        build_tool_clean = (build_tool or "maven").lower()

        if build_tool_clean == "gradle":
            executable = resolve_executable("gradle") or "gradle"
            if (project_dir / "gradlew").exists() or (project_dir / "gradlew.bat").exists():
                executable = "./gradlew.bat" if (project_dir / "gradlew.bat").exists() else "./gradlew"
            cmd = [executable, "test"]
            if target_class_name:
                cmd.extend(["--tests", f"*{target_class_name}*"])
        else:
            executable = resolve_executable("mvn") or "mvn"
            cmd = [executable, "test", "-DfailIfNoTests=false"]
            if target_class_name:
                cmd.append(f"-Dtest=*{target_class_name}*")

        res = run_command(cmd, cwd=project_dir)


        # Locate XML report directory
        reports_dir = (
            project_dir / "target" / "surefire-reports"
            if build_tool_clean == "maven"
            else project_dir / "build" / "test-results" / "test"
        )

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
                except Exception:
                    continue

                for tc in root.findall("testcase"):
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

        raw_logs = [line for line in (raw_stdout + "\n" + raw_stderr).splitlines() if line.strip()]

        return UnitTestSuiteResult(
            total_run=total_count,
            passed=passed_count,
            failed=failed_count,
            skipped=skipped_count,
            existing_test_results=existing_details,
            generated_test_results=generated_details,
            raw_logs=raw_logs[:200],  # cap log lines to prevent bloat
        )
