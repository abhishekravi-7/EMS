"""Executes unit tests via Maven/Gradle and parses JUnit XML test reports."""

from __future__ import annotations

import logging
from pathlib import Path

import defusedxml.ElementTree as ET

from app.infrastructure.java_runtime import build_tool_env
from app.schemas.unit_test import TestExecutionDetail, UnitTestSuiteResult
from app.shared.command_runner import resolve_executable, run_command

logger = logging.getLogger(__name__)


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
        known_generated_classes: set[str] | list[str] | None = None,
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
                    
            init_script_path = project_dir / "jacoco-init.gradle"
            if not init_script_path.exists():
                init_script_path.write_text("allprojects { apply plugin: 'jacoco' }\n", encoding="utf-8")
                
            cmd = [executable, "--init-script", "jacoco-init.gradle", "clean", "test", "jacocoTestReport"]
            if targets:
                for name in targets:
                    cmd.extend(["--tests", f"*{name}*"])
        else:
            # Maven Wrapper Check
            mvnw_cmd = project_dir / "mvnw.cmd"
            mvnw_sh = project_dir / "mvnw"
            wrapper_props = project_dir / ".mvn" / "wrapper" / "maven-wrapper.properties"
            wrapper_jar = project_dir / ".mvn" / "wrapper" / "maven-wrapper.jar"
            has_valid_wrapper = wrapper_props.exists() or wrapper_jar.exists()
            if is_windows and mvnw_cmd.exists() and has_valid_wrapper:
                executable = str(mvnw_cmd.resolve())
            elif not is_windows and mvnw_sh.exists() and has_valid_wrapper:
                executable = str(mvnw_sh.resolve())
            else:
                executable = resolve_executable("mvn")
                if not executable:
                    executable = "mvn.cmd" if is_windows else "mvn"
            cmd = [
                executable,
                "clean",
                "org.jacoco:jacoco-maven-plugin:prepare-agent",
                "test",
                "-DfailIfNoTests=false",
                "-DtestFailureIgnore=true",
                "-Dmaven.test.failure.ignore=true",
                "-Dgit.commit.id.skip=true",
                "-Dmaven.gitcommitid.skip=true",
            ]
            if targets:
                cmd.append(f"-Dtest={','.join([f'*{n}*' for n in targets])}")
            cmd.extend(["surefire-report:report", "org.jacoco:jacoco-maven-plugin:report"])

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

        logger.info("[JUnit] Test execution started on %s", project_dir)
        res = run_command(cmd, cwd=project_dir, timeout=600, env=build_tool_env(target_major))

        parsed_res = self.parse_junit_reports(
            reports_dir=reports_dir,
            raw_stdout=res.stdout,
            raw_stderr=res.stderr,
            exit_code=res.exit_code,
            known_generated_classes=set(known_generated_classes) if known_generated_classes else None,
        )

        parsed_res.final_coverage = {"available": False, "line_coverage_pct": None}
        parsed_res.line_coverage_pct = None
        parsed_res.branch_coverage_pct = None
        parsed_res.instruction_coverage_pct = None
        parsed_res.method_coverage_pct = None
        parsed_res.class_coverage_pct = None

        return parsed_res

    def parse_junit_reports(
        self,
        reports_dir: Path,
        raw_stdout: str = "",
        raw_stderr: str = "",
        exit_code: int = 0,
        known_generated_classes: set[str] | None = None,
    ) -> UnitTestSuiteResult:
        import re
        existing_details: list[TestExecutionDetail] = []
        generated_details: list[TestExecutionDetail] = []

        total_count = 0
        passed_count = 0
        failed_count = 0
        skipped_count = 0
        gen_classes = known_generated_classes or set()

        xml_files: list[Path] = []
        if reports_dir.exists() and reports_dir.is_dir():
            xml_files.extend(reports_dir.glob("TEST-*.xml"))
        # Also inspect submodules / build outputs for Surefire or Gradle XML files
        try:
            search_root = reports_dir.parent.parent if reports_dir.parent.exists() and reports_dir.parent.parent.exists() else reports_dir
            for f in search_root.rglob("TEST-*.xml"):
                if f not in xml_files and ".git" not in str(f) and "storage" not in str(f) and "node_modules" not in str(f):
                    xml_files.append(f)
        except Exception:
            pass

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

                    short_class = class_name.split(".")[-1]
                    is_gen = False
                    if gen_classes:
                        if class_name in gen_classes or short_class in gen_classes or f"{short_class}Test" in gen_classes or short_class.replace("Test", "") in gen_classes:
                            is_gen = True
                    if not is_gen and ("LLMTest" in class_name or "LLM" in method_name):
                        is_gen = True

                    if is_gen:
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

        if total_count > 0:
            if failed_count == 0:
                exec_status = "EXECUTED"
            elif passed_count > 0:
                exec_status = "PARTIAL"
            else:
                exec_status = "FAILED"
        elif exit_code != 0:
            combined = (raw_stdout + "\n" + raw_stderr).lower()
            if "compilation error" in combined or "compilation failure" in combined or "compile error" in combined:
                exec_status = "COMPILE FAILED"
            else:
                exec_status = "FAILED"
        else:
            exec_status = "NOT_EXECUTED"

        return UnitTestSuiteResult(
            total_run=total_count,
            passed=passed_count,
            failed=failed_count,
            skipped=skipped_count,
            existing_test_results=existing_details,
            generated_test_results=generated_details,
            execution_status=exec_status,
            raw_logs=raw_logs[:500],
        )
