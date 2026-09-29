"""Unit tests for JUnit Test Prompt Compliance Analyzer in Java APEX."""

import pytest
from app.infrastructure.analyzers.junit_prompt_compliance_analyzer import (
    JUnitPromptComplianceAnalyzer,
    ParsedTestMethod,
)
from app.schemas.unit_test import (
    PromptComplianceItem,
    PromptComplianceReport,
    TestExecutionDetail,
    TestingPromptAnalysis,
)


SAMPLE_JAVA_TEST_CODE = """
package com.example.service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Mockito;
import org.mockito.junit.jupiter.MockitoExtension;
import java.util.Collections;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

@ExtendWith(MockitoExtension.class)
public class UserServiceTest {

    @Mock
    private UserRepository userRepository;

    @InjectMocks
    private UserService userService;

    @Test
    @DisplayName("Create user with valid credentials should succeed")
    public void testCreateUser_Success() {
        // Arrange
        User user = new User("alice", "alice@example.com");
        Mockito.when(userRepository.save(user)).thenReturn(user);

        // Act
        User created = userService.createUser(user);

        // Assert
        assertNotNull(created, "Created user must not be null");
        assertEquals("alice", created.getUsername());
        Mockito.verify(userRepository).save(user);
    }

    @Test
    @DisplayName("Create user with null input should throw IllegalArgumentException")
    public void testCreateUser_NullInput() {
        // Act & Assert
        assertThrows(IllegalArgumentException.class, () -> {
            userService.createUser(null);
        });
    }

    @Test
    @DisplayName("Create user with empty username should reject and throw validation error")
    public void testCreateUser_EmptyUsername() {
        // Arrange
        User user = new User("", "empty@example.com");

        // Act & Assert
        assertThrows(ValidationException.class, () -> {
            userService.createUser(user);
        });
    }

    @Test
    @DisplayName("Calculate user quota with boundary limits")
    public void testCalculateUserQuota_BoundaryValues() {
        // Arrange & Act
        int quotaZero = userService.calculateQuota(0);
        int quotaMax = userService.calculateQuota(Integer.MAX_VALUE);
        int quotaNegative = userService.calculateQuota(-1);

        // Assert
        assertEquals(0, quotaZero);
        assertTrue(quotaMax > 0);
        assertEquals(-1, quotaNegative);
    }
}
"""

SAMPLE_EMPTY_TEST_CODE = """
package com.example.service;

import org.junit.jupiter.api.Test;

public class DummyTest {
    @Test
    public void testNothing() {
        // No assertions, no logic, no checks
    }
}
"""


def test_parse_test_source_code():
    analyzer = JUnitPromptComplianceAnalyzer()
    methods = analyzer.parse_test_source_code(SAMPLE_JAVA_TEST_CODE, class_name="UserServiceTest")

    assert len(methods) == 4
    method_names = [m.method_name for m in methods]
    assert "testCreateUser_Success" in method_names
    assert "testCreateUser_NullInput" in method_names
    assert "testCreateUser_EmptyUsername" in method_names
    assert "testCalculateUserQuota_BoundaryValues" in method_names

    # Check testCreateUser_Success inspection
    success_m = next(m for m in methods if m.method_name == "testCreateUser_Success")
    assert success_m.display_name == "Create user with valid credentials should succeed"
    assert success_m.assertions_count >= 2
    assert success_m.has_mocks is True
    assert success_m.has_assert_throws is False

    # Check testCreateUser_NullInput inspection
    null_m = next(m for m in methods if m.method_name == "testCreateUser_NullInput")
    assert null_m.has_assert_throws is True
    assert "IllegalArgumentException" in null_m.asserted_exceptions
    assert "null_reference" in null_m.boundary_inputs

    # Check testCalculateUserQuota_BoundaryValues inspection
    quota_m = next(m for m in methods if m.method_name == "testCalculateUserQuota_BoundaryValues")
    assert "numeric_boundary_constant" in quota_m.boundary_inputs or "numeric_edge_value" in quota_m.boundary_inputs
    assert quota_m.assertions_count >= 3


def test_deep_inspection_not_relying_solely_on_method_names():
    analyzer = JUnitPromptComplianceAnalyzer()
    # Code with a method claiming to be an exception test, but having no assertThrows or assertions
    fake_exception_test = """
    package com.example;
    import org.junit.jupiter.api.Test;
    public class FakeTest {
        @Test
        public void testExceptionHandlingAndFailureScenario() {
            int a = 1 + 1; // Does NOT actually assert throws or verify exceptions
        }
    }
    """
    fake_methods = analyzer.parse_test_source_code(fake_exception_test, class_name="FakeTest")
    assert len(fake_methods) == 1
    assert fake_methods[0].has_assert_throws is False
    assert fake_methods[0].assertions_count == 0

    fake_report = analyzer.evaluate_compliance(
        test_source_code=fake_exception_test,
        selected_prompt_ids=["exception_negative_scenario"],
    )
    exc_item = fake_report.compliance_items[0]
    # Compliance should be penalized because no actual assertThrows was used
    assert exc_item.compliance_percentage < 80.0
    assert any("assertThrows" in r for r in exc_item.recommendations)

    # Real exception test
    real_report = analyzer.evaluate_compliance(
        test_source_code=SAMPLE_JAVA_TEST_CODE,
        selected_prompt_ids=["exception_negative_scenario"],
    )
    real_exc_item = real_report.compliance_items[0]
    assert real_exc_item.compliance_percentage >= 80.0
    assert len(real_exc_item.covered_scenarios) >= 3


def test_all_five_predefined_prompts_evaluation():
    analyzer = JUnitPromptComplianceAnalyzer()
    exec_details = [
        TestExecutionDetail(test_class="UserServiceTest", test_method="testCreateUser_Success", status="PASSED"),
        TestExecutionDetail(test_class="UserServiceTest", test_method="testCreateUser_NullInput", status="PASSED"),
        TestExecutionDetail(test_class="UserServiceTest", test_method="testCreateUser_EmptyUsername", status="PASSED"),
        TestExecutionDetail(test_class="UserServiceTest", test_method="testCalculateUserQuota_BoundaryValues", status="PASSED"),
    ]

    report = analyzer.evaluate_compliance(
        test_source_code=SAMPLE_JAVA_TEST_CODE,
        executed_test_details=exec_details,
        line_coverage_pct=88.5,
        branch_coverage_pct=84.0,
    )

    assert report.total_prompts_evaluated == 5
    assert report.overall_compliance_percentage >= 85.0
    assert report.passed_prompts_count >= 4
    assert report.total_test_methods_inspected == 4
    assert report.total_assertions_inspected >= 5
    assert report.total_exceptions_verified >= 2
    assert report.total_boundary_inputs_tested >= 3

    # Check each prompt item
    ids = [item.prompt_id for item in report.compliance_items]
    assert "comprehensive_junit_coverage" in ids
    assert "business_logic_functional_paths" in ids
    assert "branch_condition_edge_case" in ids
    assert "exception_negative_scenario" in ids
    assert "jacoco_dynamic_coverage_gap" in ids

    for item in report.compliance_items:
        assert item.prompt_name
        assert len(item.expected_scenarios) > 0
        assert len(item.covered_scenarios) > 0
        assert item.execution_status == "PASSED"
        assert item.compliance_percentage > 70.0


def test_manual_prompt_evaluation():
    analyzer = JUnitPromptComplianceAnalyzer()
    analysis = TestingPromptAnalysis(
        user_prompt="Focus on user creation and validation error handling",
        testing_focus="User Creation & Validation Error Paths",
        target_areas=["UserService"],
        target_classes=["UserService"],
        target_methods=["createUser"],
        priority=["Valid user creation", "Validation error handling"],
        scenarios=["Verify successful user creation", "Verify validation exception on null or empty input"],
        edge_cases=["Null input", "Empty username string"],
    )

    report = analyzer.evaluate_compliance(
        test_source_code=SAMPLE_JAVA_TEST_CODE,
        manual_prompt="Focus on user creation and validation error handling",
        manual_prompt_analysis=analysis,
        selected_prompt_ids=["comprehensive_junit_coverage"],
    )

    assert report.total_prompts_evaluated == 2
    manual_item = next(i for i in report.compliance_items if i.prompt_id == "manual_prompt")
    assert manual_item.prompt_name == "Manual User Testing Prompt"
    assert len(manual_item.covered_scenarios) >= 1
    assert manual_item.compliance_percentage >= 80.0
    assert manual_item.execution_status == "PASSED"


def test_execution_failure_penalization():
    analyzer = JUnitPromptComplianceAnalyzer()
    failed_exec_details = [
        TestExecutionDetail(test_class="UserServiceTest", test_method="testCreateUser_Success", status="FAILED", error_message="AssertionError: expected Alice got null"),
        TestExecutionDetail(test_class="UserServiceTest", test_method="testCreateUser_NullInput", status="FAILED", error_message="NullPointerException"),
        TestExecutionDetail(test_class="UserServiceTest", test_method="testCreateUser_EmptyUsername", status="FAILED"),
        TestExecutionDetail(test_class="UserServiceTest", test_method="testCalculateUserQuota_BoundaryValues", status="FAILED"),
    ]

    report = analyzer.evaluate_compliance(
        test_source_code=SAMPLE_JAVA_TEST_CODE,
        executed_test_details=failed_exec_details,
        line_coverage_pct=50.0,
        branch_coverage_pct=45.0,
    )

    for item in report.compliance_items:
        assert item.execution_status == "FAILED"
        assert item.failed_count > 0
        # When execution fails completely, compliance score is significantly reduced
        assert item.compliance_percentage < 80.0


def test_empty_test_penalization():
    analyzer = JUnitPromptComplianceAnalyzer()
    report = analyzer.evaluate_compliance(
        test_source_code=SAMPLE_EMPTY_TEST_CODE,
        selected_prompt_ids=["comprehensive_junit_coverage", "business_logic_functional_paths"],
        line_coverage_pct=20.0,
    )

    for item in report.compliance_items:
        # Dummy test without assertions or logic cannot meet compliance requirements
        assert item.compliance_percentage < 70.0
        assert len(item.uncovered_scenarios) > 0
