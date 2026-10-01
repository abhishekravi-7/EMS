"""Unit tests for verifiable JUnit generation and JaCoCo coverage flow in Java APEX."""

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest

from app.infrastructure.llm.junit_generator import JUnitLLMGenerator
from app.infrastructure.quality_gates.jacoco_service import JaCoCoService
from app.infrastructure.quality_gates.unit_test_runner import UnitTestRunner
from app.application.services.report_service import _get_enriched_test_pipeline
from app.schemas.unit_test import (
    TestExecutionDetail,
    UnitTestAnalysisResponse,
)


def test_generated_test_file_creation_and_verification():
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_dir = Path(tmp_dir)
        generator = JUnitLLMGenerator()
        
        sample_code = """package com.example.service;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class EmployeeServiceTest {
    @Test
    public void testGetEmployeeById_Success() {
        assertTrue(true);
    }

    @Test
    public void testGetEmployeeById_NotFound() {
        assertNotNull("123");
    }
}
"""
        test_file = generator.write_generated_test_file(
            project_dir=project_dir,
            package_name="com.example.service",
            target_class_name="EmployeeService",
            generated_code=sample_code,
        )

        assert test_file.exists()
        assert test_file.is_file()
        assert test_file.stat().st_size > 0
        assert "class EmployeeServiceTest" in test_file.read_text(encoding="utf-8")
        assert test_file.name == "EmployeeServiceTest.java"


def test_generated_test_method_counting():
    import re
    java_code = """
package com.example.service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.api.RepeatedTest;

public class SampleTest {
    @Test
    public void testFirstMethod() {
        // ...
    }

    @ParameterizedTest
    public void testSecondMethod(String arg) {
        // ...
    }

    @RepeatedTest(3)
    void testThirdMethod() {
        // ...
    }

    public void helperMethod() {
        // Not a test
    }
}
"""
    methods = re.findall(
        r"@(?:Test|ParameterizedTest|RepeatedTest)\b(?:\s*\([^)]*\))?\s*(?:public\s+|protected\s+|void\s+)*void\s+([A-Za-z0-9_]+)\s*\(",
        java_code,
    )
    assert len(methods) == 3
    assert "testFirstMethod" in methods
    assert "testSecondMethod" in methods
    assert "testThirdMethod" in methods
    assert "helperMethod" not in methods


def test_generated_vs_existing_test_classification():
    with tempfile.TemporaryDirectory() as tmp_dir:
        reports_dir = Path(tmp_dir) / "surefire-reports"
        reports_dir.mkdir(parents=True)

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.service.EmployeeServiceTest" tests="2" failures="0" errors="0" skipped="0" time="0.05">
    <testcase name="testGetEmployeeById_Success" classname="com.example.service.EmployeeServiceTest" time="0.02"/>
    <testcase name="testGetEmployeeById_NotFound" classname="com.example.service.EmployeeServiceTest" time="0.03"/>
</testsuite>
"""
        (reports_dir / "TEST-com.example.service.EmployeeServiceTest.xml").write_text(xml_content, encoding="utf-8")

        existing_xml = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.ApplicationTests" tests="1" failures="0" errors="0" skipped="0" time="0.1">
    <testcase name="contextLoads" classname="com.example.ApplicationTests" time="0.1"/>
</testsuite>
"""
        (reports_dir / "TEST-com.example.ApplicationTests.xml").write_text(existing_xml, encoding="utf-8")

        runner = UnitTestRunner()
        # Known generated class specified
        known_gen = {"EmployeeServiceTest", "EmployeeService"}
        res = runner.parse_junit_reports(reports_dir=reports_dir, known_generated_classes=known_gen)

        assert res.total_run == 3
        assert len(res.generated_test_results) == 2
        assert len(res.existing_test_results) == 1
        assert res.generated_test_results[0].test_method == "testGetEmployeeById_Success"
        assert res.existing_test_results[0].test_method == "contextLoads"


def test_jacoco_xml_parsing_original_and_final():
    with tempfile.TemporaryDirectory() as tmp_dir:
        report_file = Path(tmp_dir) / "jacoco.xml"
        sample_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd">
<report name="EmployeeManagementSystem">
    <package name="com/employee/system">
        <class name="com/employee/system/service/EmployeeService">
            <method name="getEmployeeById" desc="(Ljava/lang/Long;)Lcom/employee/system/model/Employee;">
                <counter type="INSTRUCTION" missed="5" covered="20"/>
                <counter type="LINE" missed="1" covered="4"/>
            </method>
        </class>
    </package>
    <counter type="INSTRUCTION" missed="50" covered="150"/>
    <counter type="BRANCH" missed="10" covered="30"/>
    <counter type="LINE" missed="20" covered="80"/>
    <counter type="METHOD" missed="4" covered="16"/>
    <counter type="CLASS" missed="0" covered="5"/>
</report>
"""
        report_file.write_text(sample_xml, encoding="utf-8")

        parsed = JaCoCoService.parse_jacoco_xml(report_file)
        assert parsed["available"] is True
        assert parsed["line_coverage_pct"] == 80.0
        assert parsed["branch_coverage_pct"] == 75.0
        assert parsed["instruction_coverage_pct"] == 75.0
        assert parsed["lines_covered"] == 80
        assert parsed["lines_missed"] == 20
        assert parsed["lines_total"] == 100


def test_coverage_improvement_calculation():
    original_cov = {
        "available": True,
        "line_coverage_pct": 52.3,
        "branch_coverage_pct": 44.1,
    }
    final_cov = {
        "available": True,
        "line_coverage_pct": 87.5,
        "branch_coverage_pct": 79.2,
    }

    improv = JaCoCoService.calculate_improvement(original_cov, final_cov)
    assert improv["line_coverage_pp"] == 35.2
    assert improv["branch_coverage_pp"] == 35.1
    assert improv["text"] == "+35.2 pp"
    assert improv["branch_text"] == "+35.1 pp"
    assert original_cov["line_coverage_pct"] != final_cov["line_coverage_pct"]


def test_missing_and_malformed_jacoco_report():
    non_existent = Path("/path/that/does/not/exist/jacoco.xml")
    missing_res = JaCoCoService.parse_jacoco_xml(non_existent)
    assert missing_res["available"] is False
    assert missing_res["line_coverage_pct"] is None

    with tempfile.TemporaryDirectory() as tmp_dir:
        corrupted_file = Path(tmp_dir) / "corrupt.xml"
        corrupted_file.write_text("NOT VALID XML <<>>", encoding="utf-8")
        corrupted_res = JaCoCoService.parse_jacoco_xml(corrupted_file)
        assert corrupted_res["available"] is False
        assert "Malformed JaCoCo XML" in corrupted_res["error"]


def test_ast_fallback_generation():
    from app.application.use_cases.run_unit_tests import RunUnitTestSuiteUseCase
    use_case = RunUnitTestSuiteUseCase()
    analysis = UnitTestAnalysisResponse(
        target_class="EmployeeService",
        package_name="com.employee.system.service",
        existing_tests_count=0,
        covered_methods=["getAllEmployees"],
        uncovered_methods=["deleteEmployee", "updateEmployee"],
        suggested_scenarios=[],
    )
    fallback_code = use_case._generate_ast_fallback_test(analysis)
    assert "package com.employee.system.service;" in fallback_code
    assert "public class EmployeeServiceTest" in fallback_code
    assert "@Test" in fallback_code
    assert "testGetallemployees_Success" in fallback_code
    assert "testDeleteemployee_Success" in fallback_code


def test_report_service_enriched_test_pipeline_preserves_coverage_and_files():
    report = {
        "jobId": "test_job_123",
        "test_pipeline": {
            "test_summary_metrics": {
                "repo_total_files": 10,
                "existing_test_files": 2,
                "new_test_files": 1,
                "existing_test_cases": 4,
                "generated_test_cases": 6,
                "total_test_cases": 10,
            },
            "generated_test_files": [
                {
                    "source_class": "EmployeeService",
                    "test_class": "EmployeeServiceTest",
                    "path": "src/test/java/com/employee/system/service/EmployeeServiceTest.java",
                    "generator": "LLM",
                    "status": "CREATED",
                    "test_method_count": 6,
                }
            ],
            "coverage_result": {
                "available": True,
                "line_coverage_pct": 82.5,
                "original": {"available": True, "line_coverage_pct": 50.0},
                "final": {"available": True, "line_coverage_pct": 82.5},
                "improvement": {"text": "+32.5 pp", "line_coverage_pp": 32.5},
            },
            "executed_test_details": [
                {"test_class": "EmployeeServiceTest", "test_method": "testMethod1", "status": "PASSED"}
            ],
        }
    }
    enriched = _get_enriched_test_pipeline(report)
    assert enriched["test_summary_metrics"]["generated_test_cases"] == 6
    assert enriched["coverage_result"]["original"]["line_coverage_pct"] == 50.0
    assert enriched["coverage_result"]["final"]["line_coverage_pct"] == 82.5
    assert enriched["coverage_result"]["improvement"]["line_coverage_pp"] == 32.5
    assert len(enriched["generated_test_files"]) == 1
    assert enriched["generated_test_files"][0]["status"] == "CREATED"


def test_combine_junit_prompts_import_and_execution():
    from app.core.junit_prompts import combine_junit_prompts
    from app.application.use_cases.run_unit_tests import combine_junit_prompts as run_combine
    assert combine_junit_prompts is run_combine

    combined = combine_junit_prompts(
        selected_prompt_ids=["comprehensive_junit_coverage", "business_logic_functional_paths"],
        manual_prompt="Test user authentication and registration",
    )
    assert "comprehensive" in combined.lower()
    assert "business logic" in combined.lower()
    assert "Test user authentication and registration" in combined


def test_report_service_no_static_fallback_values():
    report = {"jobId": "non_existent_job", "targetJavaVersion": "17"}
    enriched = _get_enriched_test_pipeline(report)
    metrics = enriched["test_summary_metrics"]

    # Verify no fake numbers (12, 48, 16, 64)
    assert metrics["repo_total_files"] == 0
    assert metrics["existing_test_files"] == 0
    assert metrics["new_test_files"] == 0
    assert metrics["existing_test_cases"] == 0
    assert metrics["generated_test_cases"] == 0
    assert metrics["total_test_cases"] == 0

    # Verify no fake coverage (87.5%)
    assert enriched["coverage_result"]["available"] is False
    assert enriched["coverage_result"]["line_coverage_pct"] is None

    # Verify no fake compliance (93.8%)
    assert enriched["prompt_compliance"] is None


def test_report_service_dynamic_scan_existing_test_discovery(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        orig_repo = tmp_path / "original-repo"
        orig_main = orig_repo / "src" / "main" / "java" / "com" / "example"
        orig_test = orig_repo / "src" / "test" / "java" / "com" / "example"
        orig_main.mkdir(parents=True, exist_ok=True)
        orig_test.mkdir(parents=True, exist_ok=True)

        # Create 2 main files
        (orig_main / "UserService.java").write_text("package com.example; public class UserService {}", encoding="utf-8")
        (orig_main / "OrderService.java").write_text("package com.example; public class OrderService {}", encoding="utf-8")

        # Create 2 test files with 5 total methods
        (orig_test / "UserServiceTest.java").write_text(
            """package com.example;
import org.junit.jupiter.api.Test;
public class UserServiceTest {
    @Test public void testCreate() {}
    @Test public void testUpdate() {}
    @Test public void testDelete() {}
}""", encoding="utf-8"
        )
        (orig_test / "OrderServiceTest.java").write_text(
            """package com.example;
import org.junit.jupiter.api.Test;
public class OrderServiceTest {
    @Test public void testPlace() {}
    @Test public void testCancel() {}
}""", encoding="utf-8"
        )

        class MockWorkspacePaths:
            def __init__(self, job_id):
                self.original_repo_dir = orig_repo
                self.migrated_repo_dir = orig_repo
                self.migration_report_path = orig_repo / "report.json"

        import app.infrastructure.workspace.workspace_paths as wp_mod
        monkeypatch.setattr(wp_mod, "WorkspacePaths", MockWorkspacePaths)

        report = {"jobId": "test_dynamic_job", "targetJavaVersion": "17"}
        enriched = _get_enriched_test_pipeline(report)
        metrics = enriched["test_summary_metrics"]

        assert metrics["repo_total_files"] == 4
        assert metrics["existing_test_files"] == 2
        assert metrics["existing_test_cases"] == 5
        assert metrics["new_test_files"] == 0
        assert metrics["generated_test_cases"] == 0
        assert metrics["total_test_cases"] == 5
        assert enriched["coverage_result"]["available"] is False
        assert enriched["prompt_compliance"] is None


def test_missing_jacoco_report_returns_unavailable():
    with tempfile.TemporaryDirectory() as tmp_dir:
        non_existent = Path(tmp_dir) / "does_not_exist.xml"
        result = JaCoCoService.parse_jacoco_xml(non_existent)
        assert result["available"] is False
        assert result["line_coverage_pct"] is None


def test_jacoco_maven_auto_configuration():
    with tempfile.TemporaryDirectory() as tmp_dir:
        proj_dir = Path(tmp_dir)
        pom_path = proj_dir / "pom.xml"
        pom_path.write_text("""<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>sample-app</artifactId>
    <version>1.0.0</version>
    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.11.0</version>
            </plugin>
        </plugins>
    </build>
</project>""", encoding="utf-8")

        assert JaCoCoService.ensure_jacoco_configured(proj_dir) is True
        updated_pom = pom_path.read_text(encoding="utf-8")
        assert "jacoco-maven-plugin" in updated_pom
        assert "prepare-agent" in updated_pom
        assert "0.8.13" in updated_pom


def test_surefire_xml_parsing_with_failures_and_skips():
    with tempfile.TemporaryDirectory() as tmp_dir:
        reports_dir = Path(tmp_dir) / "surefire-reports"
        reports_dir.mkdir(parents=True)

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.service.UserServiceTest" tests="3" failures="1" errors="0" skipped="1" time="0.15">
    <testcase name="testFindById_Success" classname="com.example.service.UserServiceTest" time="0.04"/>
    <testcase name="testFindById_Failed" classname="com.example.service.UserServiceTest" time="0.06">
        <failure message="expected: not null but was: null">java.lang.AssertionError: expected: not null but was: null</failure>
    </testcase>
    <testcase name="testFindById_Disabled" classname="com.example.service.UserServiceTest" time="0.00">
        <skipped/>
    </testcase>
</testsuite>
"""
        (reports_dir / "TEST-com.example.service.UserServiceTest.xml").write_text(xml_content, encoding="utf-8")

        runner = UnitTestRunner()
        res = runner.parse_junit_reports(reports_dir=reports_dir)

        assert res.total_run == 3
        assert res.passed == 1
        assert res.failed == 1
        assert res.skipped == 1
        assert res.execution_status == "PARTIAL"
        assert len(res.existing_test_results) == 3

        failed_detail = next(d for d in res.existing_test_results if d.status == "FAILED")
        assert failed_detail.test_method == "testFindById_Failed"
        assert "expected: not null" in failed_detail.error_message

        skipped_detail = next(d for d in res.existing_test_results if d.status == "SKIPPED")
        assert skipped_detail.test_method == "testFindById_Disabled"


def test_build_result_structured_execution_and_coverage_api():
    from app.application.services.report_service import build_result

    report = {
        "jobId": "test_job_full",
        "runTests": True,
        "run_tests": True,
        "test_pipeline": {
            "execution_status": "EXECUTED",
            "test_execution": {
                "total": 99,
                "passed": 95,
                "failed": 4,
                "errors": 0,
                "skipped": 0,
            },
            "test_cases": {
                "existing": 1,
                "generated": 98,
                "total": 99,
                "executed": 99,
            },
            "coverage": {
                "available": True,
                "line": 78.42,
                "branch": 71.35,
                "instruction": 80.12,
                "method": 82.10,
                "class": 85.00,
            },
            "test_summary_metrics": {
                "existing_test_cases": 1,
                "generated_test_cases": 98,
                "total_test_cases": 99,
                "executed_total_test_methods": 99,
            },
            "executed_test_details": [
                {"test_class": "AuthServiceTest", "test_method": "testLogin", "status": "PASSED"}
            ],
            "coverage_result": {
                "available": True,
                "line_coverage_pct": 78.42,
                "branch_coverage_pct": 71.35,
                "instruction_coverage_pct": 80.12,
                "method_coverage_pct": 82.10,
                "class_coverage_pct": 85.00,
            }
        }
    }

    result_data = build_result(report)
    assert result_data["test_execution"]["total"] == 99
    assert result_data["test_execution"]["passed"] == 95
    assert result_data["test_execution"]["failed"] == 4
    assert result_data["test_cases"]["generated"] == 98
    assert result_data["coverage"]["available"] is True
    assert result_data["coverage"]["line"] == 78.42
    assert result_data["coverage"]["instruction"] == 80.12
    assert result_data["coverage"]["method"] == 82.10
    assert result_data["coverage"]["class"] == 85.00


def test_jacoco_5_dimension_counters_parsing():
    sample_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd">
<report name="demo-project">
    <counter type="INSTRUCTION" missed="200" covered="800"/>
    <counter type="BRANCH" missed="30" covered="70"/>
    <counter type="LINE" missed="50" covered="150"/>
    <counter type="COMPLEXITY" missed="10" covered="40"/>
    <counter type="METHOD" missed="5" covered="45"/>
    <counter type="CLASS" missed="2" covered="18"/>
</report>"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        xml_path = Path(tmp_dir) / "jacoco.xml"
        xml_path.write_text(sample_xml, encoding="utf-8")
        parsed = JaCoCoService.parse_jacoco_xml(xml_path)

        assert parsed["available"] is True
        assert parsed["instruction_coverage_pct"] == 80.0
        assert parsed["branch_coverage_pct"] == 70.0
        assert parsed["line_coverage_pct"] == 75.0
        assert parsed["method_coverage_pct"] == 90.0
        assert parsed["class_coverage_pct"] == 90.0


def test_maven_runner_flags_and_failure_tolerance():
    runner = UnitTestRunner()
    with tempfile.TemporaryDirectory() as tmp_dir:
        reports_dir = Path(tmp_dir) / "surefire-reports"
        reports_dir.mkdir(parents=True)
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.OrderServiceTest" tests="2" failures="1" errors="0" skipped="0" time="0.35">
    <testcase name="testCreateOrder_Success" classname="com.example.OrderServiceTest" time="0.2"/>
    <testcase name="testCreateOrder_InvalidPayment" classname="com.example.OrderServiceTest" time="0.15">
        <failure message="Payment declined">AssertionError</failure>
    </testcase>
</testsuite>"""
        (reports_dir / "TEST-com.example.OrderServiceTest.xml").write_text(xml_content, encoding="utf-8")
        res = runner.parse_junit_reports(reports_dir=reports_dir)
        assert res.total_run == 2
        assert res.passed == 1
        assert res.failed == 1
        assert res.execution_status == "PARTIAL"


def test_timeout_preserves_filesystem_reports_without_fake_zeroes():
    with tempfile.TemporaryDirectory() as tmp_dir:
        mig_dir = Path(tmp_dir)
        surefire_dir = mig_dir / "target" / "surefire-reports"
        surefire_dir.mkdir(parents=True)
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.UserServiceTest" tests="10" failures="1" errors="0" skipped="0" time="1.2">
    <testcase name="test1" classname="com.example.UserServiceTest" time="0.1"/>
    <testcase name="test2" classname="com.example.UserServiceTest" time="0.1"><failure>Failed</failure></testcase>
</testsuite>"""
        (surefire_dir / "TEST-UserServiceTest.xml").write_text(xml_content, encoding="utf-8")

        runner = UnitTestRunner()
        parsed_sf = runner.parse_junit_reports(surefire_dir, exit_code=1)
        assert parsed_sf.total_run == 2
        assert parsed_sf.passed == 1
        assert parsed_sf.failed == 1

        # Unavailable JaCoCo report returns None, not 0.0
        cov_sum = JaCoCoService.get_coverage_summary(mig_dir)
        assert cov_sum["available"] is False
        assert cov_sum["line_coverage_pct"] is None


def test_start_migration_java_ast_analyzer_imported_and_usable():
    import app.application.use_cases.start_migration as sm
    assert hasattr(sm, "JavaASTAnalyzer")
    analyzer = sm.JavaASTAnalyzer()
    res = analyzer.analyze_test_file("class SampleTest { @Test void testOne() {} }", filename="SampleTest.java")
    assert len(res.get("test_methods", [])) == 1
    assert res.get("test_methods")[0] == "testOne"


def test_unit_test_report_generator_html_matches_surefire_and_jacoco(monkeypatch):
    from app.application.services.unit_test_report_generator import UnitTestReportGenerator
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        mig_dir = tmp_path / "storage" / "migration-jobs" / "job_test_report" / "migrated-repo"
        surefire_dir = mig_dir / "target" / "surefire-reports"
        surefire_dir.mkdir(parents=True)
        jacoco_dir = mig_dir / "target" / "site" / "jacoco"
        jacoco_dir.mkdir(parents=True)

        # Write surefire xml
        (surefire_dir / "TEST-com.example.OrderServiceTest.xml").write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.OrderServiceTest" tests="3" failures="0" errors="0" skipped="0" time="0.35">
    <testcase name="testCreate" classname="com.example.OrderServiceTest" time="0.1"/>
    <testcase name="testFind" classname="com.example.OrderServiceTest" time="0.1"/>
    <testcase name="testDelete" classname="com.example.OrderServiceTest" time="0.15"/>
</testsuite>""",
            encoding="utf-8",
        )

        # Write jacoco xml
        (jacoco_dir / "jacoco.xml").write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<report name="demo">
    <counter type="INSTRUCTION" missed="20" covered="80"/>
    <counter type="BRANCH" missed="5" covered="15"/>
    <counter type="LINE" missed="10" covered="40"/>
    <counter type="METHOD" missed="2" covered="8"/>
    <counter type="CLASS" missed="0" covered="5"/>
</report>""",
            encoding="utf-8",
        )

        # Monkeypatch WorkspacePaths storage_dir
        from app.infrastructure.workspace.workspace_paths import WorkspacePaths

        def mock_init(self, job_id: str, storage_dir=None):
            self.job_id = job_id
            self._storage_dir = tmp_path / "storage" / "migration-jobs"

        monkeypatch.setattr(WorkspacePaths, "__init__", mock_init)

        generator = UnitTestReportGenerator()
        html_report = generator.generate_html_report("job_test_report")

        assert "job_test_report" in html_report
        assert "PASSED" in html_report or "EXECUTED" in html_report
        assert "testCreate" in html_report
        assert "testFind" in html_report
        assert "testDelete" in html_report

        # Test CSV generation
        csv_report = generator.generate_csv_report("job_test_report")
        assert "OrderServiceTest" in csv_report
        assert "testCreate" in csv_report
        assert "PASSED" in csv_report


def test_unit_test_report_generator_missing_reports_graceful_handling(monkeypatch):
    from app.application.services.unit_test_report_generator import UnitTestReportGenerator
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        mig_dir = tmp_path / "storage" / "migration-jobs" / "job_empty" / "migrated-repo"
        mig_dir.mkdir(parents=True)

        from app.infrastructure.workspace.workspace_paths import WorkspacePaths

        def mock_init(self, job_id: str, storage_dir=None):
            self.job_id = job_id
            self._storage_dir = tmp_path / "storage" / "migration-jobs"

        monkeypatch.setattr(WorkspacePaths, "__init__", mock_init)

        generator = UnitTestReportGenerator()
        html_report = generator.generate_html_report("job_empty")
        assert "job_empty" in html_report
        assert "N/A" in html_report  # Coverage unavailable shown as N/A, not fake 0%


def test_jacoco_artifact_checks_missing_target_and_files():
    with tempfile.TemporaryDirectory() as tmp_dir:
        proj_dir = Path(tmp_dir)
        # 1. No target directory at all
        status = JaCoCoService.check_artifacts_exist(proj_dir)
        assert status["target_dir"] is False
        assert status["classes_dir"] is False
        assert status["test_classes_dir"] is False
        assert status["jacoco_exec"] is False
        assert status["jacoco_xml"] is False
        assert status["all_ready"] is False

        # 2. Target exists, but missing jacoco.exec and jacoco.xml
        (proj_dir / "target" / "classes").mkdir(parents=True)
        (proj_dir / "target" / "test-classes").mkdir(parents=True)
        status2 = JaCoCoService.check_artifacts_exist(proj_dir)
        assert status2["target_dir"] is True
        assert status2["classes_dir"] is True
        assert status2["test_classes_dir"] is True
        assert status2["jacoco_exec"] is False
        assert status2["jacoco_xml"] is False
        assert status2["all_ready"] is False

        # 3. jacoco.exec exists, but jacoco.xml missing
        (proj_dir / "target" / "jacoco.exec").write_bytes(b"dummy_exec_bytes")
        status3 = JaCoCoService.check_artifacts_exist(proj_dir)
        assert status3["jacoco_exec"] is True
        assert status3["jacoco_xml"] is False
        assert status3["all_ready"] is False

        # 4. All ready
        (proj_dir / "target" / "site" / "jacoco").mkdir(parents=True)
        (proj_dir / "target" / "site" / "jacoco" / "jacoco.xml").write_text("<report name='test'/>", encoding="utf-8")
        status4 = JaCoCoService.check_artifacts_exist(proj_dir)
        assert status4["jacoco_xml"] is True
        assert status4["all_ready"] is True


def test_jacoco_detect_target_major_versions():
    with tempfile.TemporaryDirectory() as tmp_dir:
        proj_dir = Path(tmp_dir)
        pom_path = proj_dir / "pom.xml"

        # Test maven.compiler.release = 25
        pom_path.write_text(
            """<project>
    <properties>
        <maven.compiler.release>25</maven.compiler.release>
    </properties>
</project>""",
            encoding="utf-8",
        )
        assert JaCoCoService.detect_target_major(proj_dir) == 25

        # Test java.version = 17
        pom_path.write_text(
            """<project>
    <properties>
        <java.version>17</java.version>
    </properties>
</project>""",
            encoding="utf-8",
        )
        assert JaCoCoService.detect_target_major(proj_dir) == 17

        # Test maven.compiler.target = 1.8 -> 8
        pom_path.write_text(
            """<project>
    <properties>
        <maven.compiler.target>1.8</maven.compiler.target>
    </properties>
</project>""",
            encoding="utf-8",
        )
        assert JaCoCoService.detect_target_major(proj_dir) == 8


def test_jacoco_auto_execute_when_target_missing_success(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        proj_dir = Path(tmp_dir)
        pom_path = proj_dir / "pom.xml"
        pom_path.write_text(
            """<project>
    <properties><java.version>21</java.version></properties>
</project>""",
            encoding="utf-8",
        )

        # Target directory does NOT exist initially
        assert not (proj_dir / "target").exists()

        # Mock run_command to simulate successful Maven build that creates JaCoCo artifacts
        from app.shared.command_runner import CommandResult

        def mock_run_command(cmd, cwd=None, timeout=None, env=None):
            # Simulate maven creating target/jacoco.exec and target/site/jacoco/jacoco.xml
            site_dir = proj_dir / "target" / "site" / "jacoco"
            site_dir.mkdir(parents=True, exist_ok=True)
            (proj_dir / "target" / "classes").mkdir(parents=True, exist_ok=True)
            (proj_dir / "target" / "test-classes").mkdir(parents=True, exist_ok=True)
            (proj_dir / "target" / "jacoco.exec").write_bytes(b"exec_bytes")
            (site_dir / "jacoco.xml").write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<report name="demo">
    <counter type="INSTRUCTION" missed="10" covered="90"/>
    <counter type="BRANCH" missed="2" covered="8"/>
    <counter type="LINE" missed="5" covered="45"/>
    <counter type="METHOD" missed="1" covered="9"/>
    <counter type="CLASS" missed="0" covered="3"/>
</report>""",
                encoding="utf-8",
            )
            return CommandResult(command=cmd, exit_code=0, stdout="BUILD SUCCESS", stderr="")

        import app.infrastructure.quality_gates.jacoco_service as js_mod
        monkeypatch.setattr(js_mod, "run_command", mock_run_command)
        monkeypatch.setattr("app.shared.command_runner.run_command", mock_run_command)

        summary = JaCoCoService.get_coverage_summary(proj_dir, auto_execute_if_missing=True)
        assert summary["available"] is True
        assert summary["line_coverage_pct"] == 90.0  # 45/(45+5) = 90%
        assert summary["branch_coverage_pct"] == 80.0
        assert summary["instruction_coverage_pct"] == 90.0
        assert summary["method_coverage_pct"] == 90.0
        assert summary["class_coverage_pct"] == 100.0


def test_jacoco_auto_execute_when_compilation_fails(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        proj_dir = Path(tmp_dir)
        pom_path = proj_dir / "pom.xml"
        pom_path.write_text("<project></project>", encoding="utf-8")

        from app.shared.command_runner import CommandResult

        def mock_run_command_fail(cmd, cwd=None, timeout=None, env=None):
            return CommandResult(
                command=cmd,
                exit_code=1,
                stdout="[ERROR] COMPILATION ERROR: cannot find symbol Foo",
                stderr="Compilation failure",
            )

        import app.infrastructure.quality_gates.jacoco_service as js_mod
        monkeypatch.setattr(js_mod, "run_command", mock_run_command_fail)
        monkeypatch.setattr("app.shared.command_runner.run_command", mock_run_command_fail)

        summary = JaCoCoService.get_coverage_summary(proj_dir, auto_execute_if_missing=True)
        assert summary["available"] is False
        assert summary["line_coverage_pct"] is None
        assert summary["branch_coverage_pct"] is None
        assert "cannot find symbol Foo" in summary["message"] or "Compilation failure" in summary["message"]
        assert summary["exit_code"] == 1


def test_jacoco_auto_execute_when_test_fails_preserves_error(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        proj_dir = Path(tmp_dir)
        pom_path = proj_dir / "pom.xml"
        pom_path.write_text("<project></project>", encoding="utf-8")

        from app.shared.command_runner import CommandResult

        def mock_run_test_failure(cmd, cwd=None, timeout=None, env=None):
            return CommandResult(
                command=cmd,
                exit_code=1,
                stdout="[ERROR] Tests run: 5, Failures: 2, Errors: 0, Skipped: 0",
                stderr="There are test failures.",
            )

        import app.infrastructure.quality_gates.jacoco_service as js_mod
        monkeypatch.setattr(js_mod, "run_command", mock_run_test_failure)
        monkeypatch.setattr("app.shared.command_runner.run_command", mock_run_test_failure)

        summary = JaCoCoService.get_coverage_summary(proj_dir, auto_execute_if_missing=True)
        assert summary["available"] is False
        assert summary["line_coverage_pct"] is None
        assert "Tests run: 5, Failures: 2" in summary["message"] or "There are test failures" in summary["message"]


def test_complete_flow_with_migrated_repo_initially_no_target_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        job_id = "job_no_target"
        mig_dir = tmp_path / "storage" / "migration-jobs" / job_id / "migrated-repo"
        mig_dir.mkdir(parents=True)

        # Write pom.xml in migrated repo (target directory DOES NOT EXIST)
        pom_path = mig_dir / "pom.xml"
        pom_path.write_text(
            """<project>
    <groupId>com.example</groupId>
    <artifactId>sample-migrated</artifactId>
    <version>1.0.0</version>
    <properties>
        <maven.compiler.release>21</maven.compiler.release>
    </properties>
</project>""",
            encoding="utf-8",
        )

        assert not (mig_dir / "target").exists()

        # Mock WorkspacePaths
        from app.infrastructure.workspace.workspace_paths import WorkspacePaths

        def mock_init(self, j_id: str, storage_dir=None):
            self.job_id = j_id
            self._storage_dir = tmp_path / "storage" / "migration-jobs"

        monkeypatch.setattr(WorkspacePaths, "__init__", mock_init)

        # Mock run_command so that building generates target, surefire, and jacoco
        from app.shared.command_runner import CommandResult

        def mock_run_command_e2e(cmd, cwd=None, timeout=None, env=None):
            surefire_dir = mig_dir / "target" / "surefire-reports"
            surefire_dir.mkdir(parents=True, exist_ok=True)
            jacoco_dir = mig_dir / "target" / "site" / "jacoco"
            jacoco_dir.mkdir(parents=True, exist_ok=True)
            (mig_dir / "target" / "classes").mkdir(parents=True, exist_ok=True)
            (mig_dir / "target" / "test-classes").mkdir(parents=True, exist_ok=True)
            (mig_dir / "target" / "jacoco.exec").write_bytes(b"exec_content")

            (surefire_dir / "TEST-SampleTest.xml").write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="SampleTest" tests="2" failures="0" errors="0" skipped="0" time="0.05">
    <testcase name="testA" classname="SampleTest" time="0.02"/>
    <testcase name="testB" classname="SampleTest" time="0.03"/>
</testsuite>""",
                encoding="utf-8",
            )
            (jacoco_dir / "jacoco.xml").write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<report name="sample">
    <counter type="INSTRUCTION" missed="20" covered="80"/>
    <counter type="BRANCH" missed="5" covered="15"/>
    <counter type="LINE" missed="10" covered="90"/>
    <counter type="METHOD" missed="1" covered="9"/>
    <counter type="CLASS" missed="0" covered="2"/>
</report>""",
                encoding="utf-8",
            )
            return CommandResult(command=cmd, exit_code=0, stdout="BUILD SUCCESS", stderr="")

        import app.infrastructure.quality_gates.jacoco_service as js_mod
        monkeypatch.setattr(js_mod, "run_command", mock_run_command_e2e)
        monkeypatch.setattr("app.shared.command_runner.run_command", mock_run_command_e2e)

        from app.application.services.unit_test_report_generator import UnitTestReportGenerator
        generator = UnitTestReportGenerator()
        html = generator.generate_html_report(job_id)

        # When target does not exist, it renders gracefully without errors or JaCoCo invocation
        assert "job_no_target" in html
        assert "No executed test methods recorded" in html

    def test_jacoco_baseline_timeout_handling(self, tmp_path, monkeypatch):
        """Verify that a long-running/timed-out baseline JaCoCo execution returns unavailable gracefully."""
        proj_dir = tmp_path / "timed_out_proj"
        proj_dir.mkdir(parents=True)
        (proj_dir / "pom.xml").write_text("<project><modelVersion>4.0.0</modelVersion></project>", encoding="utf-8")

        import app.infrastructure.quality_gates.jacoco_service as js_mod
        from subprocess import TimeoutExpired

        def mock_timeout_command(*args, **kwargs):
            raise TimeoutExpired(cmd="mvn test", timeout=10)

        monkeypatch.setattr(js_mod, "run_command", mock_timeout_command)

        summary = JaCoCoService.get_coverage_summary(proj_dir, auto_execute_if_missing=True, timeout=10)
        assert summary["available"] is False
        assert summary["line_coverage_pct"] is None
        assert "timed out" in summary["message"].lower()

    def test_jacoco_baseline_failure_non_blocking(self, tmp_path, monkeypatch):
        """Verify that a compilation/build failure during JaCoCo execution marks coverage as unavailable without raising unhandled exceptions."""
        proj_dir = tmp_path / "failed_build_proj"
        proj_dir.mkdir(parents=True)
        (proj_dir / "pom.xml").write_text("<project><modelVersion>4.0.0</modelVersion></project>", encoding="utf-8")

        import app.infrastructure.quality_gates.jacoco_service as js_mod
        from app.shared.command_runner import CommandResult

        def mock_failed_command(*args, **kwargs):
            return CommandResult(
                command=["mvn", "test"],
                exit_code=1,
                stdout="[ERROR] Compilation failure in Sample.java",
                stderr="",
            )

        monkeypatch.setattr(js_mod, "run_command", mock_failed_command)

        summary = JaCoCoService.get_coverage_summary(proj_dir, auto_execute_if_missing=True)
        assert summary["available"] is False
        assert summary["line_coverage_pct"] is None
        assert "failed" in summary["message"].lower()

    def test_jacoco_baseline_and_migrated_improvement_calculation(self):
        """Verify that coverage improvement is calculated accurately between baseline and final runs."""
        original = {"available": True, "line_coverage_pct": 40.0, "branch_coverage_pct": 20.0}
        final = {"available": True, "line_coverage_pct": 75.5, "branch_coverage_pct": 50.0}

        improvement = JaCoCoService.calculate_improvement(original, final)
        assert improvement["line_coverage_pp"] == 35.5
        assert improvement["branch_coverage_pp"] == 30.0
        assert improvement["improvement_detected"] is True

        # When baseline is unavailable
        orig_unavail = {"available": False, "line_coverage_pct": None}
        improvement_no_orig = JaCoCoService.calculate_improvement(orig_unavail, final)
        assert improvement_no_orig["line_coverage_pp"] == 75.5
        assert improvement_no_orig["improvement_detected"] is True






