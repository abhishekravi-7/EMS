"""FastAPI HTTP controller for JUnit analysis, generation, and execution."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.application.use_cases.run_unit_tests import RunUnitTestSuiteUseCase
from app.application.use_cases.validate_unit_tests import ValidateUnitTestSuiteUseCase
from app.core.exceptions import APEXError
from app.infrastructure.llm.junit_generator import JUnitLLMGenerator
from app.schemas.unit_test import (
    TestingPromptAnalysis,
    TestingPromptAnalysisRequest,
    UnitTestAnalysisRequest,
    UnitTestAnalysisResponse,
    UnitTestGenerateAndRunRequest,
    UnitTestSuiteResult,
    UnitTestValidationReport,
    UnitTestValidationRequest,
)

router = APIRouter(prefix="/unit-tests", tags=["Unit Testing"])


@router.post(
    "/analyze",
    response_model=UnitTestAnalysisResponse,
    summary="Analyze existing JUnit test coverage and scenario gaps",
)
def analyze_unit_tests(request: UnitTestAnalysisRequest) -> UnitTestAnalysisResponse:
    try:
        use_case = RunUnitTestSuiteUseCase()
        return use_case.analyze(request.model_dump())
    except APEXError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during test analysis: {exc}",
        ) from exc


from app.core.junit_prompts import PREDEFINED_JUNIT_PROMPTS, combine_junit_prompts


@router.get(
    "/predefined-prompts",
    summary="Get list of predefined JUnit coverage prompts",
)
def get_predefined_junit_prompts() -> list[dict[str, str]]:
    return PREDEFINED_JUNIT_PROMPTS


@router.post(
    "/analyze-prompt",
    response_model=TestingPromptAnalysis,
    summary="Dynamically analyze a natural language user testing focus prompt",
)
async def analyze_testing_prompt(
    request: TestingPromptAnalysisRequest,
) -> TestingPromptAnalysis:
    try:
        combined_prompt = combine_junit_prompts(
            selected_prompt_ids=request.selected_predefined_prompts,
            manual_prompt=request.manual_prompt or request.prompt,
        )
        if not combined_prompt and request.prompt:
            combined_prompt = request.prompt

        generator = JUnitLLMGenerator()
        return await generator.analyze_testing_prompt(
            prompt=combined_prompt,
            project_context=request.project_context,
        )
    except APEXError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during testing prompt analysis: {exc}",
        ) from exc


@router.post(
    "/validate",
    response_model=UnitTestValidationReport,
    summary="Validate JUnit test code via Multi-Agent pipeline (AST Smell Detector + LLM Critic)",
)
async def validate_unit_tests(
    request: UnitTestValidationRequest,
) -> UnitTestValidationReport:
    try:
        use_case = ValidateUnitTestSuiteUseCase()
        return await use_case.validate(
            source_code=request.source_code,
            test_code=request.test_code,
            target_class_name=request.target_class_name,
        )
    except APEXError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during test validation: {exc}",
        ) from exc


@router.post(
    "/generate-and-run",
    response_model=UnitTestSuiteResult,
    summary="Generate LLM JUnit test cases and run unified test suite (Existing + Generated)",
)
async def generate_and_run_unit_tests(
    request: UnitTestGenerateAndRunRequest,
) -> UnitTestSuiteResult:
    try:
        use_case = RunUnitTestSuiteUseCase()
        return await use_case.execute(request)
    except APEXError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during test generation and execution: {exc}",
        ) from exc

