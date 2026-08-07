"""Unit tests for JavaASTAnalyzer, UnitTestRunner, and JUnitLLMGenerator."""

from __future__ import annotations

from pathlib import Path
import pytest

from app.infrastructure.analyzers.junit_analyzer import JavaASTAnalyzer
from app.infrastructure.quality_gates.unit_test_runner import UnitTestRunner
from app.schemas.unit_test import TestExecutionDetail, UnitTestSuiteResult

SAMPLE_JAVA_SOURCE = """
package com.example.service;

import java.util.Optional;

public class UserService {
    public String findUserName(Long userId) {
        if (userId == null) {
            throw new IllegalArgumentException("User ID cannot be null");
        }
        return "User_" + userId;
    }

    protected void auditUserAccess(String username) {
        // internal audit logic
    }
}
"""

SAMPLE_JUNIT_TEST = """
package com.example.service;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class UserServiceTest {
    @Test
    public void testFindUserName() {
        UserService service = new UserService();
        assertEquals("User_123", service.findUserName(123L));
    }
}
"""


def test_ast_analyzer_extracts_metadata_and_coverage():
    analyzer = JavaASTAnalyzer()
    analysis = analyzer.analyze_source_and_tests(
        source_code=SAMPLE_JAVA_SOURCE,
        test_code=SAMPLE_JUNIT_TEST,
        source_filename="UserService.java",
    )

    assert analysis.package_name == "com.example.service"
    assert analysis.target_class == "UserService"
    assert "findUserName" in analysis.covered_methods
    assert "auditUserAccess" in analysis.uncovered_methods
    assert len(analysis.suggested_scenarios) > 0


def test_unit_test_runner_parses_surefire_xml_reports(tmp_path: Path):
    reports_dir = tmp_path / "surefire-reports"
    reports_dir.mkdir()

    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.service.UserServiceTest" tests="2" failures="1" errors="0" skipped="0" time="0.125">
    <testcase classname="com.example.service.UserServiceTest" name="testFindUserName" time="0.050"/>
    <testcase classname="com.example.service.UserServiceLLMTest" name="testFindUserName_NullId" time="0.075">
        <failure message="Expected exception not thrown" type="java.lang.AssertionError">java.lang.AssertionError: Expected exception</failure>
    </testcase>
</testsuite>
"""
    (reports_dir / "TEST-com.example.service.UserServiceTest.xml").write_text(sample_xml, encoding="utf-8")

    runner = UnitTestRunner()
    res = runner.parse_junit_reports(reports_dir=reports_dir, raw_stdout="BUILD SUCCESS")

    assert res.total_run == 2
    assert res.passed == 1
    assert res.failed == 1
    assert len(res.existing_test_results) == 1
    assert len(res.generated_test_results) == 1
    assert res.generated_test_results[0].status == "FAILED"
    assert res.generated_test_results[0].error_message == "Expected exception not thrown"


def test_unit_test_report_generator_html_rendering():
    from app.application.services.unit_test_report_generator import UnitTestReportGenerator

    generator = UnitTestReportGenerator()
    html_output = generator.generate_html_report(job_id="test-job-123")

    assert "<!DOCTYPE html>" in html_output
    assert "APEX JUnit Test Suite Report" in html_output
    assert "Pre-Existing Test Cases" in html_output
    assert "LLM Generated Test Cases" in html_output
    assert "Before vs After Code Comparison" in html_output


def test_junit4_to_5_modernizer_conversion():
    from app.infrastructure.analyzers.junit4_to_5_converter import JUnit4To5Modernizer

    modernizer = JUnit4To5Modernizer()
    junit4_code = """
package com.example.test;

import org.junit.Test;
import org.junit.Before;
import org.junit.Ignore;
import static org.junit.Assert.*;

public class LegacyTest {
    @Before
    public void setup() {}

    @Test
    @Ignore
    public void testOld() {
        assertEquals("hello", "hello");
    }
}
"""
    converted = modernizer.convert_to_junit5(junit4_code)

    assert "import org.junit.jupiter.api.Test;" in converted
    assert "import org.junit.jupiter.api.BeforeEach;" in converted
    assert "import org.junit.jupiter.api.Disabled;" in converted
    assert "import static org.junit.jupiter.api.Assertions.*;" in converted
    assert "@BeforeEach" in converted
    assert "@Disabled" in converted


