"""FastAPI Endpoints for Proposed Functional Test Cases."""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse

from app.api.deps import User, get_current_user, verify_job_ownership
from app.application.use_cases.proposed_tests.proposed_test_service import proposed_test_service
from app.domain.models.proposed_test_models import BulkStatusUpdateRequest, ProposedTestStatus, RunProposedTestsRequest
from app.infrastructure.workspace.workspace_paths import WorkspacePaths

router = APIRouter(prefix="/migration", tags=["proposed-tests"])


# ── 1. Static Subpath Endpoints (MUST be registered before /{test_id}) ────────

@router.post("/{job_id}/proposed-tests/generate")
async def generate_proposed_tests_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Analyzes the migrated repository and generates proposed functional tests."""
    await verify_job_ownership(job_id, current_user)
    try:
        proposals = await asyncio.to_thread(proposed_test_service.generate_proposed_tests, job_id)
        return JSONResponse(content=[p.model_dump() for p in proposals])
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/{job_id}/proposed-tests/status")
async def get_proposed_tests_status_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Returns generation & execution status, progress, live logs, and metrics for a migration job."""
    await verify_job_ownership(job_id, current_user)
    res = proposed_test_service.get_status(job_id)
    return JSONResponse(content=res)


@router.get("/{job_id}/proposed-tests/app-readiness")
async def get_app_readiness_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Checks whether the migrated application is reachable and returns readiness status.

    The Report Page calls this before triggering Playwright execution so that
    infrastructure failures (ECONNREFUSED) are clearly separated from functional failures.
    """
    await verify_job_ownership(job_id, current_user)
    try:
        from app.application.services.status_service import MigrationReportStore
        from app.application.use_cases.proposed_tests.proposed_test_executor import resolve_migrated_app_url
        from app.infrastructure.build.app_readiness_checker import AppReadinessChecker
        from app.infrastructure.workspace.workspace_paths import WorkspacePaths as WP

        paths = WP(job_id)
        # Resolve URL from application config files in migrated repo
        repo_dir = paths.migrated_repo_dir if paths.migrated_repo_dir.exists() else paths.original_repo_dir
        base_url = resolve_migrated_app_url(repo_dir)

        # Read persisted build/startup status from migration report
        migration_report = MigrationReportStore(paths).read() or {}
        build_status = migration_report.get("buildStatus", "UNKNOWN")
        build_success = migration_report.get("buildSuccess", None)
        app_startup_status = migration_report.get("appStartupStatus", "UNKNOWN")
        app_readiness_status_stored = migration_report.get("appReadinessStatus", "UNKNOWN")
        app_pid = migration_report.get("appPid")

        # Perform live readiness check
        readiness = AppReadinessChecker().check(base_url, timeout_s=5.0)

        return JSONResponse(content={
            "job_id": job_id,
            "base_url": base_url,
            "ready": readiness.ready,
            "port": readiness.port,
            "http_status": readiness.http_status,
            "health_endpoint": readiness.health_endpoint,
            "error": readiness.error,
            "elapsed_seconds": readiness.elapsed_seconds,
            # Persisted from migration pipeline
            "build_status": build_status,
            "build_success": build_success,
            "app_startup_status": app_startup_status,
            "app_readiness_status_stored": app_readiness_status_stored,
            "app_pid": app_pid,
        })
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(e), "ready": False})


@router.get("/{job_id}/proposed-tests/results")
async def get_proposed_tests_results_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Returns final execution results and report metrics."""
    await verify_job_ownership(job_id, current_user)
    res = proposed_test_service.get_results(job_id)
    return JSONResponse(content=res)


@router.get("/{job_id}/proposed-tests/baseline")
async def get_proposed_tests_baseline_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Returns pre-migration source repository baseline execution results and metrics."""
    await verify_job_ownership(job_id, current_user)
    res = proposed_test_service.get_baseline_results(job_id)
    if not res:
        # Fallback to computing from proposals
        proposals = proposed_test_service.get_proposed_tests(job_id)
        metrics = proposed_test_service._compute_metrics_for_baseline(proposals)
        res = {
            "job_id": job_id,
            "status": "COMPLETED" if any(p.baseline_execution_result is not None for p in proposals) else "NOT_RUN",
            "metrics": metrics.model_dump(),
            "test_cases": [p.model_dump() for p in proposals],
        }
    return JSONResponse(content=res)


@router.post("/{job_id}/proposed-tests/baseline/run")
async def run_proposed_tests_baseline_endpoint(
    job_id: str,
    build_tool: str = "MAVEN",
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Executes pre-migration baseline build, startup, and test execution against source repository."""
    await verify_job_ownership(job_id, current_user)
    try:
        res = await asyncio.to_thread(proposed_test_service.run_source_baseline, job_id, build_tool=build_tool)
        return JSONResponse(content=res)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(e), "status": "FAILED"})


@router.get("/{job_id}/proposed-tests/comparison")
async def get_proposed_tests_comparison_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Returns side-by-side comparison between pre-migration baseline and target migrated results."""
    await verify_job_ownership(job_id, current_user)
    try:
        comparison = proposed_test_service.get_comparison(job_id)
        return JSONResponse(content=comparison.model_dump())
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/{job_id}/proposed-tests/validation")
async def get_proposed_tests_validation_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Returns the LLM proposed test validation summary and per-test evidence analysis."""
    await verify_job_ownership(job_id, current_user)
    summary = proposed_test_service.get_validation_summary(job_id)
    proposals = proposed_test_service.get_proposed_tests(job_id)
    return JSONResponse(content={
        "job_id": job_id,
        "summary": summary,
        "validated_tests": [p.model_dump() for p in proposals],
    })


@router.post("/{job_id}/proposed-tests/validate")
async def run_proposed_tests_validation_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Runs repository source-code validation on all proposed tests."""
    await verify_job_ownership(job_id, current_user)
    proposals, summary = await asyncio.to_thread(proposed_test_service.validate_proposed_tests, job_id)
    return JSONResponse(content={
        "job_id": job_id,
        "summary": summary,
        "validated_tests": [p.model_dump() for p in proposals],
    })


@router.get("/{job_id}/proposed-tests/report/download")
async def download_proposed_test_report_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Generates and downloads the full Proposed Functional Test Report as JSON."""
    await verify_job_ownership(job_id, current_user)
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
):
    """Bulk updates test statuses (e.g. approve multiple or reject multiple)."""
    await verify_job_ownership(job_id, current_user)
    updated = proposed_test_service.bulk_set_status(job_id, payload.test_ids, payload.status)
    return JSONResponse(content=[p.model_dump() for p in updated])


@router.post("/{job_id}/proposed-tests/run")
async def run_approved_tests_endpoint(
    job_id: str,
    payload: RunProposedTestsRequest | None = Body(default=None),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Starts background execution for proposed and/or existing test cases matching selected sources."""
    await verify_job_ownership(job_id, current_user)
    framework = (payload.framework if payload else "PLAYWRIGHT").upper()
    if framework in ["SELENIUM", "SELENIUM_WEBDRIVER"]:
        raise HTTPException(status_code=400, detail="Selenium support is coming soon.")
    if framework in ["CYPRESS"]:
        raise HTTPException(status_code=400, detail="Cypress support is coming soon.")

    try:
        sources = payload.sources if payload else None
        test_ids = payload.test_ids if payload else None
        res = proposed_test_service.run_approved_tests(job_id, sources=sources, test_ids=test_ids, framework=framework)
        return JSONResponse(status_code=202, content=res)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/{job_id}/proposed-tests")
async def get_proposed_tests_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Retrieves all proposed test cases for a migration job."""
    await verify_job_ownership(job_id, current_user)
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
):
    """Serves Playwright screenshot, video, or log artifact."""
    await verify_job_ownership(job_id, current_user)
    paths = WorkspacePaths(job_id)
    evidence_file = paths.job_dir / "proposed-tests" / "evidence" / test_id / filename

    if not evidence_file.is_file():
        raise HTTPException(status_code=404, detail="Evidence file not found")

    if filename.endswith(".svg"):
        return Response(content=evidence_file.read_bytes(), media_type="image/svg+xml")
    if filename.endswith(".png"):
        return FileResponse(str(evidence_file), media_type="image/png")
    if filename.endswith((".webm", ".mp4")):
        return FileResponse(str(evidence_file), media_type="video/webm")

    return FileResponse(str(evidence_file))


@router.get("/{job_id}/proposed-tests/allure-report")
@router.get("/{job_id}/proposed-tests/allure-report/index.html")
async def get_proposed_test_allure_report_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Serves the generated standalone Allure HTML Report for the proposed test execution."""
    await verify_job_ownership(job_id, current_user)
    paths = WorkspacePaths(job_id)
    report_file = paths.job_dir / "proposed-tests" / "allure-report" / "index.html"

    if not report_file.is_file():
        raise HTTPException(status_code=404, detail="Allure report not found for this migration job")

    return Response(content=report_file.read_text(encoding="utf-8"), media_type="text/html")


@router.get("/{job_id}/proposed-tests/allure-report/{file_path:path}")
async def get_proposed_test_allure_asset_endpoint(
    job_id: str,
    file_path: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Serves static assets and evidence attachments for the Allure report."""
    await verify_job_ownership(job_id, current_user)
    paths = WorkspacePaths(job_id)
    target_file = (paths.job_dir / "proposed-tests" / "allure-report" / file_path).resolve()

    # Prevent directory traversal
    base_report_dir = (paths.job_dir / "proposed-tests" / "allure-report").resolve()
    if not str(target_file).startswith(str(base_report_dir)) or not target_file.is_file():
        # Also check in allure-results
        alt_file = (paths.job_dir / "proposed-tests" / "allure-results" / file_path).resolve()
        base_results_dir = (paths.job_dir / "proposed-tests" / "allure-results").resolve()
        if str(alt_file).startswith(str(base_results_dir)) and alt_file.is_file():
            target_file = alt_file
        else:
            raise HTTPException(status_code=404, detail="Allure report asset not found")

    if target_file.name.endswith(".html"):
        return Response(content=target_file.read_text(encoding="utf-8"), media_type="text/html")
    if target_file.name.endswith(".css"):
        return Response(content=target_file.read_text(encoding="utf-8"), media_type="text/css")
    if target_file.name.endswith(".js"):
        return Response(content=target_file.read_text(encoding="utf-8"), media_type="application/javascript")
    if target_file.name.endswith(".json"):
        return Response(content=target_file.read_text(encoding="utf-8"), media_type="application/json")
    if target_file.name.endswith(".svg"):
        return Response(content=target_file.read_bytes(), media_type="image/svg+xml")
    if target_file.name.endswith(".png"):
        return FileResponse(str(target_file), media_type="image/png")
    if target_file.name.endswith((".webm", ".mp4")):
        return FileResponse(str(target_file), media_type="video/webm")

    return FileResponse(str(target_file))


# ── 2. Parameterized Test ID Endpoints (Registered AFTER static subpaths) ────

@router.post("/{job_id}/proposed-tests/{test_id}/approve")
async def approve_proposed_test_endpoint(
    job_id: str,
    test_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Marks a proposed test as APPROVED."""
    await verify_job_ownership(job_id, current_user)
    updated = proposed_test_service.set_status(job_id, test_id, ProposedTestStatus.APPROVED)
    if not updated:
        raise HTTPException(status_code=404, detail="Proposed test not found")
    return JSONResponse(content=updated.model_dump())


@router.post("/{job_id}/proposed-tests/{test_id}/reject")
async def reject_proposed_test_endpoint(
    job_id: str,
    test_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Marks a proposed test as REJECTED."""
    await verify_job_ownership(job_id, current_user)
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
):
    """Updates a proposed test case definition."""
    await verify_job_ownership(job_id, current_user)
    updated = proposed_test_service.update_proposed_test(job_id, test_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Proposed test not found")
    return JSONResponse(content=updated.model_dump())


@router.get("/{job_id}/proposed-tests/{test_id}")
async def get_proposed_test_detail_endpoint(
    job_id: str,
    test_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Retrieves a single proposed test case by ID."""
    await verify_job_ownership(job_id, current_user)
    test = proposed_test_service.get_proposed_test(job_id, test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Proposed test not found")
    return JSONResponse(content=test.model_dump())
