import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from app.schemas.unit_test import (
    TestingPromptAnalysis,
    PromptCoverageEvaluation,
    UnitTestGenerateAndRunRequest,
    UnitTestSuiteResult,
    TestExecutionDetail,
)
from app.infrastructure.llm.prompt_templates import (
    build_testing_prompt_analysis_prompt,
    build_prompt_coverage_evaluation_prompt,
    build_junit_generation_prompt,
)
from app.infrastructure.llm.junit_generator import JUnitLLMGenerator
from app.application.use_cases.run_unit_tests import RunUnitTestSuiteUseCase


def test_schema_models():
    # Verify TestingPromptAnalysis schema
    analysis = TestingPromptAnalysis(
        user_prompt="Focus mainly on file upload error handling",
        testing_focus="File Upload Error Scenarios",
        target_areas=["FileUploadController", "StorageService"],
        target_classes=["FileUploadController", "StorageService"],
        target_methods=["uploadFile", "validateFile"],
        priority=["Large Files", "Invalid Extensions"],
        scenarios=["File size limit exceeded", "Unsupported file type"],
        edge_cases=["Empty file payload", "Special characters in file name"],
    )
    assert analysis.user_prompt == "Focus mainly on file upload error handling"
    assert "FileUploadController" in analysis.target_classes

    # Verify PromptCoverageEvaluation schema
    eval_model = PromptCoverageEvaluation(
        user_prompt="Focus mainly on file upload error handling",
        focus_matched=True,
        coverage_assessment="Excellent coverage of file size and extension validations.",
        covered_scenarios=["File size limit exceeded", "Unsupported file type"],
        uncovered_scenarios=[],
        recommendations=["Add multi-part upload edge case"],
    )
    assert eval_model.focus_matched is True

    # Verify UnitTestGenerateAndRunRequest accepts testing_prompt
    req = UnitTestGenerateAndRunRequest(
        relative_source_path="src/main/java/com/example/UserService.java",
        testing_prompt="Focus on password hashing and authentication failures",
    )
    assert req.testing_prompt == "Focus on password hashing and authentication failures"


def test_prompt_templates():
    user_prompt = "Test invalid credentials and expired token scenarios"

    analysis_prompt = build_testing_prompt_analysis_prompt(user_prompt, project_context="AuthService.java")
    assert user_prompt in analysis_prompt
    assert "AuthService.java" in analysis_prompt

    eval_prompt = build_prompt_coverage_evaluation_prompt(
        prompt=user_prompt,
        analysis_summary="Focus on Auth",
        executed_tests_summary="AuthServiceTest: testLogin_InvalidCredentials",
        coverage_pct=85.0,
    )
    assert user_prompt in eval_prompt
    assert "AuthServiceTest" in eval_prompt

    gen_prompt = build_junit_generation_prompt(
        source_code="public class AuthService {}",
        package_name="com.example.auth",
        target_class_name="AuthService",
        testing_focus_context="Focus prompt: Test invalid credentials",
    )
    assert "Focus prompt: Test invalid credentials" in gen_prompt


@pytest.mark.anyio
async def test_junit_generator_analyze_prompt():
    generator = JUnitLLMGenerator()
    mock_llm_json = """{
        "user_prompt": "Focus on payment calculation logic",
        "testing_focus": "Payment calculation and discount boundaries",
        "target_areas": ["PaymentService"],
        "target_classes": ["PaymentService"],
        "target_methods": ["calculateTotal"],
        "priority": ["High"],
        "scenarios": ["Zero amount discount", "Negative price input"],
        "edge_cases": ["Floating point rounding"]
    }"""

    async def mock_stream(*args, **kwargs):
        yield mock_llm_json

    with patch.object(generator._chat_llm, "stream_chat", side_effect=mock_stream):
        res = await generator.analyze_testing_prompt("Focus on payment calculation logic")
        assert res.testing_focus == "Payment calculation and discount boundaries"
        assert "PaymentService" in res.target_classes


@pytest.mark.anyio
async def test_use_case_backward_compatibility():
    """Ensure that when no testing_prompt is provided, RunUnitTestSuiteUseCase runs standard JUnit execution."""
    use_case = RunUnitTestSuiteUseCase()

    mock_runner_result = UnitTestSuiteResult(
        build_tool="maven",
        passed_count=2,
        failed_count=0,
        line_coverage_pct=90.0,
        existing_test_results=[TestExecutionDetail(test_class="AuthTest", test_method="testLogin", status="PASSED")],
    )

    with patch.object(use_case._runner, "run", return_value=mock_runner_result), \
         patch.object(use_case._generator, "generate_test_class", new_callable=AsyncMock) as mock_gen, \
         patch.object(use_case._generator, "write_generated_test_file", return_value=Path("src/test/java/AuthServiceTest.java")):
        mock_gen.return_value = "public class AuthServiceTest {}"
        req = UnitTestGenerateAndRunRequest(
            project_dir=".",
            relative_source_path="src/main/java/com/example/AuthService.java",
            testing_prompt=None,  # No prompt provided
        )
        # Mock file system checks
        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value="package com.example; public class AuthService {}"):
            res = await use_case.execute(req)
            assert res.prompt_analysis is None
            assert res.prompt_coverage_evaluation is None
