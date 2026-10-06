import asyncio
import logging
import time
from collections import deque

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.api.deps import User, get_current_user, verify_job_ownership
from app.application.use_cases.existing_test_runner_service import (
    MAX_EXISTING_TEST_OUTPUT_LINES,
    existing_test_runner_service,
)
from app.infrastructure.persistence.mongodb import get_mongodb
from app.infrastructure.persistence.mongodb_ownership_repository import record_job_owner as record_mongo_owner

logger = logging.getLogger("migration")

router = APIRouter(tags=["existing-tests"])

@router.get("/existing-tests/scan/{job_id}")
async def scan_existing_tests_total(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Fast scan — returns total test count before execution (no run)."""
    await verify_job_ownership(job_id, current_user)
    try:
        logger.info("[MIGRATION TESTS SCAN START] - JobID: %s", job_id)
        res = await asyncio.to_thread(
            existing_test_runner_service.scan_total, job_id
        )
        
        unit_cnt = 0
        func_cnt = 0
        unit_fw = "JUnit"
        func_fw = "Playwright"
        api_cnt = 0
        ui_cnt = 0
        
        if isinstance(res, dict):
            tests_list = res.get("test_cases") or res.get("tests") or []
            framework_str = str(res.get("framework") or "")
            
            if "JUnit" in framework_str or "TestNG" in framework_str or "Jest" in framework_str:
                unit_fw = [f for f in ["JUnit", "TestNG", "Jest", "PyTest"] if f in framework_str]
                unit_fw = unit_fw[0] if unit_fw else "JUnit"
            if "Playwright" in framework_str or "Cypress" in framework_str or "Selenium" in framework_str:
                func_fw = [f for f in ["Playwright", "Cypress", "Selenium"] if f in framework_str]
                func_fw = func_fw[0] if func_fw else "Playwright"

            for t in tests_list:
                cat = str(t.get("category", "")).upper()
                t_type = str(t.get("type", "")).upper()
                f_type = str(t.get("framework", "")).upper()

                if cat == "UI" or "UI" in t_type or "PLAYWRIGHT" in f_type or "CYPRESS" in f_type or "SELENIUM" in f_type:
                    if cat == "API" or "API" in t_type:
                        api_cnt += 1
                    else:
                        ui_cnt += 1
                    func_cnt += 1
                elif cat == "API" or "API" in t_type:
                    api_cnt += 1
                    func_cnt += 1
                else:
                    unit_cnt += 1

            if res.get("total", 0) > 0 and (unit_cnt + func_cnt == 0):
                unit_cnt = res.get("total", 0)

        logger.info(
            "[MIGRATION UNIT TESTS DISCOVERED] - JobID: %s - Total: %d - Framework: %s",
            job_id,
            unit_cnt,
            unit_fw,
        )
        logger.info(
            "[MIGRATION FUNCTIONAL TESTS DISCOVERED] - JobID: %s - Total: %d - Framework: %s - APITests: %d - UITests: %d",
            job_id,
            func_cnt,
            func_fw,
            api_cnt,
            ui_cnt,
        )
        logger.info(
            "[MIGRATION TESTS SCAN SUCCESS] - JobID: %s - TotalUnitTests: %d - TotalFunctionalTests: %d",
            job_id,
            unit_cnt,
            func_cnt,
        )
        return JSONResponse(content=res)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[MIGRATION TESTS SCAN FAILED] - JobID: %s - Error: %s", job_id, e, exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/existing-tests/run/{job_id}")
async def run_existing_tests_endpoint(
    job_id: str,
    test_selection: list[dict] | None = Body(default=None),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Start existing tests in the background and return immediately."""
    await verify_job_ownership(job_id, current_user)
    try:
        current = await asyncio.to_thread(existing_test_runner_service.get_status, job_id)
        if current.get("status") in {"RUNNING", "IN_PROGRESS"}:
            logger.info("[EXISTING-TEST-JOB] Existing tests already running for job %s", job_id)
            return JSONResponse(
                status_code=202,
                content={
                    "status": current.get("status"),
                    "started": False,
                    "message": "Existing tests are already running.",
                    "result": current.get("result"),
                },
            )

        # Immediately initialize running state and persist so polling is instantly available across all instances
        init_log_entry = {
            "ts": time.strftime("%H:%M:%S"),
            "msg": f"Starting existing test execution for job {job_id}...",
            "level": "INFO",
        }
        with existing_test_runner_service._lock:
            existing_test_runner_service._state[job_id] = {
                "status": "RUNNING",
                "executed": False,
                "logs": deque([init_log_entry], maxlen=MAX_EXISTING_TEST_OUTPUT_LINES),
                "result": None,
            }
        await asyncio.to_thread(existing_test_runner_service._save_state_to_disk, job_id)
        logger.info("[EXISTING-TEST-JOB] Created and stored initial RUNNING state for job %s", job_id)

        # Ensure database ownership record is persisted
        try:
            mongo_db = await get_mongodb()
            if mongo_db is not None:
                await record_mongo_owner(
                    mongo_db,
                    job_id=job_id,
                    user_id=str(current_user.id),
                    owner_name=current_user.full_name,
                    owner_email=current_user.email
                )
        except Exception as rec_err:  # noqa: BLE001
            logger.debug("Non-fatal: could not record job owner in MongoDB for %s: %s", job_id, rec_err)

        async def _run_background():
            logger.info("[EXISTING-TEST-JOB] Background execution task started for job %s", job_id)
            try:
                await asyncio.to_thread(existing_test_runner_service.run_existing_tests, job_id, test_selection)
                logger.info("[EXISTING-TEST-JOB] Background execution task completed for job %s", job_id)
            except Exception as bg_err:
                logger.error("[EXISTING-TEST-JOB] Background execution task failed for job %s: %s", job_id, bg_err, exc_info=True)
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
                await asyncio.to_thread(existing_test_runner_service._save_state_to_disk, job_id)
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[EXISTING-TEST-JOB] Failed to start existing tests for job %s: %s", job_id, e, exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/existing-tests/status/{job_id}")
async def get_existing_tests_status_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Returns current run status + live logs + final result when done."""
    await verify_job_ownership(job_id, current_user)
    try:
        res = await asyncio.to_thread(existing_test_runner_service.get_status, job_id)
        return JSONResponse(content=res)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[EXISTING-TEST-JOB] Status endpoint error for job %s: %s", job_id, e, exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.delete("/existing-tests/reset/{job_id}")
async def reset_existing_tests_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Reset execution state for a job."""
    await verify_job_ownership(job_id, current_user)
    try:
        await asyncio.to_thread(existing_test_runner_service.reset, job_id)
        return JSONResponse(content={"reset": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[EXISTING-TEST-JOB] Reset error for job %s: %s", job_id, e, exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/existing-tests/stop/{job_id}")
async def stop_existing_tests_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Aborts/terminates the current execution of existing tests."""
    await verify_job_ownership(job_id, current_user)
    try:
        await asyncio.to_thread(existing_test_runner_service.stop_existing_tests, job_id)
        return JSONResponse(content={"stopped": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[EXISTING-TEST-JOB] Stop error for job %s: %s", job_id, e, exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})
