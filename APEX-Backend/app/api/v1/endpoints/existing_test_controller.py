import asyncio
from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, verify_job_ownership
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.models import User
from app.application.use_cases.existing_test_runner_service import existing_test_runner_service

router = APIRouter(tags=["existing-tests"])

@router.get("/existing-tests/scan/{job_id}")
async def scan_existing_tests_total(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fast scan — returns total test count before execution (no run)."""
    verify_job_ownership(db, job_id, current_user)
    try:
        res = await asyncio.to_thread(
            existing_test_runner_service.scan_total, job_id
        )
        return JSONResponse(content=res)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/existing-tests/run/{job_id}")
async def run_existing_tests_endpoint(
    job_id: str,
    test_selection: list[dict] | None = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start existing tests in the background and return immediately."""
    verify_job_ownership(db, job_id, current_user)
    try:
        current = existing_test_runner_service.get_status(job_id)
        if current.get("status") in {"RUNNING", "IN_PROGRESS"}:
            return JSONResponse(
                status_code=202,
                content={
                    "status": current.get("status"),
                    "started": False,
                    "message": "Existing tests are already running.",
                    "result": current.get("result"),
                },
            )

        async def _run_background():
            try:
                await asyncio.to_thread(existing_test_runner_service.run_existing_tests, job_id, test_selection)
            except Exception as bg_err:
                with existing_test_runner_service._lock:
                    state = existing_test_runner_service._state.setdefault(job_id, {})
                    state["status"] = "FAILED"
                    state["executed"] = True
                    state["result"] = {
                        "status": "FAILED",
                        "executed": True,
                        "metrics": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
                        "error": str(bg_err),
                    }
                existing_test_runner_service._log(job_id, f"Existing test background run failed: {bg_err}", "ERROR")

        asyncio.create_task(_run_background())
        return JSONResponse(
            status_code=202,
            content={
                "status": "RUNNING",
                "started": True,
                "message": "Existing tests started in the background.",
            },
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/existing-tests/status/{job_id}")
async def get_existing_tests_status_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns current run status + live logs + final result when done."""
    verify_job_ownership(db, job_id, current_user)
    try:
        res = existing_test_runner_service.get_status(job_id)
        return JSONResponse(content=res)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.delete("/existing-tests/reset/{job_id}")
async def reset_existing_tests_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset execution state for a job."""
    verify_job_ownership(db, job_id, current_user)
    try:
        existing_test_runner_service.reset(job_id)
        return JSONResponse(content={"reset": True})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/existing-tests/stop/{job_id}")
async def stop_existing_tests_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Aborts/terminates the current execution of existing tests."""
    verify_job_ownership(db, job_id, current_user)
    try:
        existing_test_runner_service.stop_existing_tests(job_id)
        return JSONResponse(content={"stopped": True})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
