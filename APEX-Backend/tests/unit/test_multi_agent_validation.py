"""Unit tests for TestSmellDetector, TestCriticAgent, and ValidateUnitTestSuiteUseCase."""

from __future__ import annotations

import pytest
from app.infrastructure.analyzers.test_smell_detector import TestSmellDetector
from app.application.use_cases.validate_unit_tests import ValidateUnitTestSuiteUseCase

SAMPLE_SOURCE = """
package com.example.calculator;

public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
}
"""

TAUTOLOGICAL_TEST_CODE = """
package com.example.calculator;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class CalculatorLLMTest {
    @Test
    public void testAdd() {
        assertTrue(true);
    }
}
"""

NO_ASSERTION_TEST_CODE = """
package com.example.calculator;

import org.junit.jupiter.api.Test;

public class CalculatorLLMTest {
    @Test
    public void testAdd() {
        Calculator calc = new Calculator();
        calc.add(2, 3);
    }
}
"""

VALID_TEST_CODE = """
package com.example.calculator;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class CalculatorLLMTest {
    @Test
    public void testAdd_Success() {
        Calculator calc = new Calculator();
        assertEquals(5, calc.add(2, 3));
    }
}
"""


def test_smell_detector_catches_tautological_assertions():
    detector = TestSmellDetector()
    smells = detector.detect_smells(TAUTOLOGICAL_TEST_CODE, "Calculator")

    types = [s.smell_type for s in smells]
    assert "TAUTOLOGICAL_ASSERTION" in types


def test_smell_detector_catches_missing_assertions():
    detector = TestSmellDetector()
    smells = detector.detect_smells(NO_ASSERTION_TEST_CODE, "Calculator")

    types = [s.smell_type for s in smells]
    assert "NO_ASSERTIONS" in types


def test_smell_detector_passes_valid_test_code():
    detector = TestSmellDetector()
    smells = detector.detect_smells(VALID_TEST_CODE, "Calculator")

    critical_smells = [s for s in smells if s.severity in ("CRITICAL", "HIGH")]
    assert len(critical_smells) == 0


@pytest.mark.asyncio
async def test_validate_use_case_rejects_tautological_code():
    use_case = ValidateUnitTestSuiteUseCase()
    report = await use_case.validate(
        source_code=SAMPLE_SOURCE,
        test_code=TAUTOLOGICAL_TEST_CODE,
        target_class_name="Calculator",
    )

    assert report.is_valid is False
    assert any(s.smell_type == "TAUTOLOGICAL_ASSERTION" for s in report.smells_detected)
