"""FastAPI HTTP controller for JUnit analysis, generation, and execution."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.application.use_cases.run_unit_tests import RunUnitTestSuiteUseCase
from app.application.use_cases.validate_unit_tests import ValidateUnitTestSuiteUseCase
from app.core.exceptions import APEXError
from app.schemas.unit_test import (
    UnitTestAnalysisRequest,
    UnitTestAnalysisResponse,
    UnitTestGenerateAndRunRequest,
    UnitTestSuiteResult,
    UnitTestValidationRequest,
    UnitTestValidationReport,
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


@router.post(
    "/validate",
    response_model=UnitTestValidationReport,
    summary="Validate JUnit test code via Multi-Agent pipeline (AST Smell Detector + LLM Critic)",
)
async def validate_unit_tests(
    request: UnitTestValidationRequest,
    db: Session = Depends(get_db),
) -> UnitTestValidationReport:
    try:
        use_case = ValidateUnitTestSuiteUseCase()
        return await use_case.validate(
            source_code=request.source_code,
            test_code=request.test_code,
            target_class_name=request.target_class_name,
            db=db,
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
    db: Session = Depends(get_db),
) -> UnitTestSuiteResult:
    try:
        use_case = RunUnitTestSuiteUseCase()
        return await use_case.execute(request, db=db)
    except APEXError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during test generation and execution: {exc}",
        ) from exc

