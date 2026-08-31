"""FastAPI Endpoints for Proposed Functional Test Cases."""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, verify_job_ownership
from app.application.use_cases.proposed_tests.proposed_test_service import proposed_test_service
from app.domain.models.proposed_test_models import BulkStatusUpdateRequest, ProposedTestStatus
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.models import User
from app.infrastructure.workspace.workspace_paths import WorkspacePaths

router = APIRouter(prefix="/migration", tags=["proposed-tests"])


# ── 1. Static Subpath Endpoints (MUST be registered before /{test_id}) ────────

@router.post("/{job_id}/proposed-tests/generate")
async def generate_proposed_tests_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Analyzes the migrated repository and generates proposed functional tests."""
    verify_job_ownership(db, job_id, current_user)
    try:
        proposals = await asyncio.to_thread(proposed_test_service.generate_proposed_tests, job_id)
        return JSONResponse(content=[p.model_dump() for p in proposals])
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/{job_id}/proposed-tests/status")
async def get_proposed_tests_status_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Returns generation & execution status, progress, live logs, and metrics for a migration job."""
    verify_job_ownership(db, job_id, current_user)
    res = proposed_test_service.get_status(job_id)
    return JSONResponse(content=res)


@router.get("/{job_id}/proposed-tests/results")
async def get_proposed_tests_results_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Returns final execution results and report metrics."""
    verify_job_ownership(db, job_id, current_user)
    res = proposed_test_service.get_results(job_id)
    return JSONResponse(content=res)


@router.get("/{job_id}/proposed-tests/report/download")
async def download_proposed_test_report_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Generates and downloads the full Proposed Functional Test Report as JSON."""
    verify_job_ownership(db, job_id, current_user)
    res = proposed_test_service.get_results(job_id)
    return Response(
        content=json.dumps(res, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="proposed-tests-report-{job_id}.json"'},
    )


@router.post("/{job_id}/proposed-tests/bulk-status")
async def bulk_status_update_endpoint(
    job_id: str,
    payload: BulkStatusUpdateRequest = Body(...),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Bulk updates test statuses (e.g. approve multiple or reject multiple)."""
    verify_job_ownership(db, job_id, current_user)
    updated = proposed_test_service.bulk_set_status(job_id, payload.test_ids, payload.status)
    return JSONResponse(content=[p.model_dump() for p in updated])


@router.post("/{job_id}/proposed-tests/run")
async def run_approved_tests_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Starts background execution for all APPROVED proposed test cases."""
    verify_job_ownership(db, job_id, current_user)
    try:
        res = proposed_test_service.run_approved_tests(job_id)
        return JSONResponse(status_code=202, content=res)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/{job_id}/proposed-tests")
async def get_proposed_tests_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Retrieves all proposed test cases for a migration job."""
    verify_job_ownership(db, job_id, current_user)
    try:
        proposals = await asyncio.to_thread(proposed_test_service.get_proposed_tests, job_id)
        return JSONResponse(content=[p.model_dump() for p in proposals])
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/{job_id}/proposed-tests/evidence/{test_id}/{filename}")
async def get_proposed_test_evidence_endpoint(
    job_id: str,
    test_id: str,
    filename: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Serves Playwright screenshot, video, or log artifact."""
    verify_job_ownership(db, job_id, current_user)
    paths = WorkspacePaths(job_id)
    evidence_file = paths.job_dir / "proposed-tests" / "evidence" / test_id / filename

    if not evidence_file.is_file():
        raise HTTPException(status_code=404, detail="Evidence file not found")

    if filename.endswith(".svg"):
        return Response(content=evidence_file.read_bytes(), media_type="image/svg+xml")
    if filename.endswith(".png"):
        return FileResponse(str(evidence_file), media_type="image/png")
    if filename.endswith(".webm") or filename.endswith(".mp4"):
        return FileResponse(str(evidence_file), media_type="video/webm")

    return FileResponse(str(evidence_file))


# ── 2. Parameterized Test ID Endpoints (Registered AFTER static subpaths) ────

@router.post("/{job_id}/proposed-tests/{test_id}/approve")
async def approve_proposed_test_endpoint(
    job_id: str,
    test_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Marks a proposed test as APPROVED."""
    verify_job_ownership(db, job_id, current_user)
    updated = proposed_test_service.set_status(job_id, test_id, ProposedTestStatus.APPROVED)
    if not updated:
        raise HTTPException(status_code=404, detail="Proposed test not found")
    return JSONResponse(content=updated.model_dump())


@router.post("/{job_id}/proposed-tests/{test_id}/reject")
async def reject_proposed_test_endpoint(
    job_id: str,
    test_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Marks a proposed test as REJECTED."""
    verify_job_ownership(db, job_id, current_user)
    updated = proposed_test_service.set_status(job_id, test_id, ProposedTestStatus.REJECTED)
    if not updated:
        raise HTTPException(status_code=404, detail="Proposed test not found")
    return JSONResponse(content=updated.model_dump())


@router.put("/{job_id}/proposed-tests/{test_id}")
async def update_proposed_test_endpoint(
    job_id: str,
    test_id: str,
    updates: dict[str, Any] = Body(...),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Updates a proposed test case definition."""
    verify_job_ownership(db, job_id, current_user)
    updated = proposed_test_service.update_proposed_test(job_id, test_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Proposed test not found")
    return JSONResponse(content=updated.model_dump())


@router.get("/{job_id}/proposed-tests/{test_id}")
async def get_proposed_test_detail_endpoint(
    job_id: str,
    test_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Retrieves a single proposed test case by ID."""
    verify_job_ownership(db, job_id, current_user)
    test = proposed_test_service.get_proposed_test(job_id, test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Proposed test not found")
    return JSONResponse(content=test.model_dump())
