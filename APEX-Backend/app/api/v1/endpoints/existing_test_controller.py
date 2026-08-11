"""FastAPI controller for discovering and running existing repository tests."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, verify_job_ownership
from app.application.services.existing_test_service import ExistingTestService
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.models import User
from app.schemas.existing_test import (
    ExistingTestDiscoveryResponse,
    ExistingTestRunRequest,
    ExistingTestStatusResponse
)

router = APIRouter(prefix="/existing-tests", tags=["Existing Tests"])
_service = ExistingTestService()

@router.get(
    "/discover/{job_id}",
    response_model=ExistingTestDiscoveryResponse,
    summary="Discover existing tests in the repository"
)
async def discover_existing_tests(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ExistingTestDiscoveryResponse:
    verify_job_ownership(db, job_id, current_user)
    try:
        return _service.discover_tests(job_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test discovery failed: {str(exc)}"
        )

@router.post(
    "/run/{job_id}",
    response_model=ExistingTestStatusResponse,
    summary="Run selected existing tests"
)
async def run_existing_tests(
    job_id: str,
    request: ExistingTestRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ExistingTestStatusResponse:
    verify_job_ownership(db, job_id, current_user)
    try:
        return _service.run_tests(job_id, request.testClasses)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test execution failed: {str(exc)}"
        )

@router.get(
    "/status/{job_id}",
    response_model=ExistingTestStatusResponse,
    summary="Get existing test execution status"
)
async def get_existing_test_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ExistingTestStatusResponse:
    verify_job_ownership(db, job_id, current_user)
    return _service.get_status(job_id)
