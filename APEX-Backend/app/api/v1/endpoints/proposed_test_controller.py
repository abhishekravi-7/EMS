"""FastAPI Endpoints for Proposed Functional Test Cases."""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
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


@router.get("/{job_id}/proposed-tests/functional-doc/report")
async def get_functional_doc_report_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Returns the grounded functional testing document report for a job."""
    await verify_job_ownership(job_id, current_user)
    report = proposed_test_service.get_functional_document_report(job_id)
    if not report:
        raise HTTPException(status_code=404, detail="No functional document grounding report found for this job.")
    return JSONResponse(content=report)


@router.post("/{job_id}/proposed-tests/functional-doc/process")
async def process_functional_doc_endpoint(
    job_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Processes an uploaded or provided functional testing document against repository evidence."""
    await verify_job_ownership(job_id, current_user)
    try:
        doc_text = payload.get("document_text")
        report = await asyncio.to_thread(
            proposed_test_service.process_functional_document,
            job_id,
            document_text=doc_text,
        )
        return JSONResponse(content=report)
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(e)})


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


@router.get("/{job_id}/proposed-tests/report/download-html")
async def download_proposed_test_html_report_endpoint(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Downloads the full functional test suite HTML report (Playwright HTML Report)."""
    await verify_job_ownership(job_id, current_user)
    paths = WorkspacePaths(job_id)
    report_file = paths.job_dir / "proposed-tests" / "playwright-report" / "index.html"

    if not report_file.is_file():
        raise HTTPException(status_code=404, detail="Playwright HTML report is not available. Playwright report generation failed.")

    content = report_file.read_text(encoding="utf-8")
    return Response(
        content=content,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="playwright-functional-report-{job_id}.html"'},
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


@router.post("/{job_id}/proposed-tests/inline-prompt/preview")
async def preview_inline_prompt_endpoint(
    job_id: str,
    payload: dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Generates an evidence-grounded diff (added, modified, removed) from an inline prompt instruction."""
    await verify_job_ownership(job_id, current_user)
    prompt_text = (payload.get("prompt") or "").strip()
    try:
        diff = await asyncio.to_thread(proposed_test_service.generate_inline_prompt_diff, job_id, prompt_text)
        return JSONResponse(content=diff)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/{job_id}/proposed-tests/inline-prompt/apply")
async def apply_inline_prompt_endpoint(
    job_id: str,
    payload: dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Applies previewed diff to the current inventory and persists changes."""
    await verify_job_ownership(job_id, current_user)
    diff = payload.get("diff") or {}
    try:
        updated = await asyncio.to_thread(proposed_test_service.apply_inline_prompt_diff, job_id, diff)
        return JSONResponse(content=[p.model_dump() for p in updated])
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
    request: Request,
    job_id: str,
    test_id: str,
    filename: str,
):
    """Serves Playwright screenshot, video, or log artifact."""
    paths = WorkspacePaths(job_id)
    if not paths.job_dir.exists():
        raise HTTPException(status_code=404, detail="Migration job not found")

    evidence_file = (paths.job_dir / "proposed-tests" / "evidence" / test_id / filename).resolve()
    base_ev_dir = (paths.job_dir / "proposed-tests" / "evidence").resolve()

    # Prevent directory traversal
    if not str(evidence_file).startswith(str(base_ev_dir)) or not evidence_file.is_file():
        raise HTTPException(status_code=404, detail="Evidence file not found")

    if filename.endswith(".svg"):
        return Response(content=evidence_file.read_bytes(), media_type="image/svg+xml")
    if filename.endswith(".png"):
        return FileResponse(
            str(evidence_file),
            media_type="image/png",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    if filename.endswith((".webm", ".mp4")):
        file_size = evidence_file.stat().st_size
        range_header = request.headers.get("range")
        if range_header and file_size > 0:
            byte_range = range_header.replace("bytes=", "").split("-")
            start = int(byte_range[0]) if byte_range[0] else 0
            end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else file_size - 1
            end = min(end, file_size - 1)
            chunk_size = end - start + 1
            with open(evidence_file, "rb") as f:
                f.seek(start)
                data = f.read(chunk_size)
            return Response(
                content=data,
                status_code=206,
                media_type="video/webm",
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(chunk_size),
                    "Content-Type": "video/webm",
                },
            )
        return FileResponse(
            str(evidence_file),
            media_type="video/webm",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Accept-Ranges": "bytes",
            },
        )
    if filename.endswith(".zip"):
        return FileResponse(str(evidence_file), media_type="application/zip", filename=filename)
    if filename.endswith(".json"):
        return Response(content=evidence_file.read_bytes(), media_type="application/json")
    if filename.endswith((".log", ".txt")):
        return Response(content=evidence_file.read_text(encoding="utf-8", errors="replace"), media_type="text/plain")

    return FileResponse(str(evidence_file))


@router.get("/{job_id}/proposed-tests/{test_id}/report")
async def get_proposed_test_report_endpoint(
    job_id: str,
    test_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Retrieves execution results and real artifacts for a single test case report."""
    await verify_job_ownership(job_id, current_user)
    paths = WorkspacePaths(job_id)
    test = proposed_test_service.get_proposed_test(job_id, test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Proposed test not found")

    evidence_dir = paths.job_dir / "proposed-tests" / "evidence" / test_id
    api_trace = None
    browser_log = None

    if (evidence_dir / "api_trace.json").is_file():
        try:
            api_trace = json.loads((evidence_dir / "api_trace.json").read_text(encoding="utf-8"))
        except Exception:
            pass

    if (evidence_dir / "browser_steps.log").is_file():
        try:
            browser_log = (evidence_dir / "browser_steps.log").read_text(encoding="utf-8")
        except Exception:
            pass

    screenshot_file = evidence_dir / "screenshot.png"
    video_file = evidence_dir / "video.webm"
    trace_file = evidence_dir / "trace.zip"
    logs_file = evidence_dir / "browser_steps.log"

    from app.application.use_cases.proposed_tests.proposed_test_executor import extract_video_metadata

    vid_metadata = extract_video_metadata(video_file) if video_file.is_file() else {"duration": None, "size": 0}
    vid_dur = (
        test.execution_result.evidence.video_duration
        if test.execution_result and test.execution_result.evidence and test.execution_result.evidence.video_duration is not None
        else vid_metadata.get("duration")
    )
    vid_size = (
        test.execution_result.evidence.video_size
        if test.execution_result and test.execution_result.evidence and test.execution_result.evidence.video_size is not None
        else vid_metadata.get("size")
    )
    rec_status = (
        test.execution_result.evidence.recording_status
        if test.execution_result and test.execution_result.evidence and test.execution_result.evidence.recording_status
        else ("RECORDED" if video_file.is_file() and vid_dur else ("FAILED" if video_file.is_file() else "NO_RECORDING"))
    )

    evidence_dict = {
        "screenshot_url": f"/api/v1/migration/{job_id}/proposed-tests/evidence/{test_id}/screenshot.png" if screenshot_file.is_file() else None,
        "screenshot_available": screenshot_file.is_file(),
        "video_url": f"/api/v1/migration/{job_id}/proposed-tests/evidence/{test_id}/video.webm" if video_file.is_file() else None,
        "video_available": video_file.is_file(),
        "video_duration": vid_dur,
        "video_duration_formatted": f"{vid_dur:.2f}s" if vid_dur is not None else None,
        "video_size": vid_size,
        "recording_status": rec_status,
        "trace_url": f"/api/v1/migration/{job_id}/proposed-tests/evidence/{test_id}/trace.zip" if trace_file.is_file() else None,
        "logs_url": f"/api/v1/migration/{job_id}/proposed-tests/evidence/{test_id}/browser_steps.log" if logs_file.is_file() else None,
    }

    has_artifacts = evidence_dir.exists() and any(evidence_dir.iterdir())
    is_executed = test.execution_result is not None and test.execution_result.status not in [
        ProposedTestStatus.NOT_EXECUTED,
        ProposedTestStatus.PROPOSED,
    ]

    exec_dump = test.execution_result.model_dump() if test.execution_result else None
    if exec_dump:
        if not exec_dump.get("evidence"):
            exec_dump["evidence"] = {}
        for k, v in evidence_dict.items():
            if v is not None or k not in exec_dump["evidence"]:
                exec_dump["evidence"][k] = v
    elif has_artifacts:
        exec_dump = {
            "status": test.status.value if hasattr(test.status, "value") else str(test.status),
            "evidence": evidence_dict,
        }

    return JSONResponse(content={
        "job_id": job_id,
        "test_id": test.id,
        "title": test.title,
        "type": test.type.value if hasattr(test.type, "value") else str(test.type),
        "source": test.source,
        "status": test.status.value if hasattr(test.status, "value") else str(test.status),
        "description": test.description,
        "steps": test.steps,
        "preconditions": test.preconditions,
        "expected_result": test.expected_result,
        "api_spec": test.api_spec.model_dump() if test.api_spec else None,
        "ui_spec": test.ui_spec.model_dump() if test.ui_spec else None,
        "execution_result": exec_dump,
        "baseline_execution_result": test.baseline_execution_result.model_dump() if test.baseline_execution_result else None,
        "evidence": evidence_dict,
        "api_trace": api_trace,
        "browser_log": browser_log,
        "has_artifacts": has_artifacts,
        "report_available": is_executed or has_artifacts,
    })





@router.get("/{job_id}/proposed-tests/{report_type}")
@router.get("/{job_id}/proposed-tests/{report_type}/")
@router.get("/{job_id}/proposed-tests/{report_type}/index.html")
async def get_proposed_test_html_report_endpoint(
    request: Request,
    job_id: str,
    report_type: str,
):
    """Serves the generated standalone HTML Reports (Allure/Playwright)."""
    if report_type not in ["allure-report", "allure-report-baseline", "playwright-report", "playwright-report-baseline"]:
        raise HTTPException(status_code=404, detail="Invalid report type")

    # Redirect to index.html if requested without trailing slash/index.html to ensure relative assets resolve properly
    if not request.url.path.endswith("/") and not request.url.path.endswith(".html"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{request.url.path}/index.html", status_code=302)

    paths = WorkspacePaths(job_id)
    if not paths.job_dir.exists():
        raise HTTPException(status_code=404, detail="Migration job not found")

    report_file = paths.job_dir / "proposed-tests" / report_type / "index.html"

    if not report_file.is_file():
        raise HTTPException(status_code=404, detail=f"{report_type} not found for this migration job")

    return FileResponse(str(report_file), media_type="text/html")


@router.get("/{job_id}/proposed-tests/{report_type}/{file_path:path}")
async def get_proposed_test_report_asset_endpoint(
    request: Request,
    job_id: str,
    report_type: str,
    file_path: str,
):
    """Serves static assets and evidence attachments for the reports."""
    if report_type not in ["allure-report", "allure-report-baseline", "playwright-report", "playwright-report-baseline"]:
        raise HTTPException(status_code=404, detail="Invalid report type")

    paths = WorkspacePaths(job_id)
    if not paths.job_dir.exists():
        raise HTTPException(status_code=404, detail="Migration job not found")

    base_report_dir = (paths.job_dir / "proposed-tests" / report_type).resolve()
    target_file = (base_report_dir / file_path).resolve()

    # Prevent directory traversal
    if not str(target_file).startswith(str(base_report_dir)) or not target_file.is_file():
        # Check in allure-results if it's an allure report
        if "allure" in report_type:
            results_dir_name = "allure-results-baseline" if "baseline" in report_type else "allure-results"
            alt_file = (paths.job_dir / "proposed-tests" / results_dir_name / file_path).resolve()
            base_results_dir = (paths.job_dir / "proposed-tests" / results_dir_name).resolve()
            if str(alt_file).startswith(str(base_results_dir)) and alt_file.is_file():
                target_file = alt_file
            else:
                raise HTTPException(status_code=404, detail="Report asset not found")
        else:
            raise HTTPException(status_code=404, detail="Report asset not found")

    if target_file.name.endswith(".html"):
        return FileResponse(str(target_file), media_type="text/html")
    if target_file.name.endswith(".css"):
        return FileResponse(str(target_file), media_type="text/css")
    if target_file.name.endswith(".js"):
        return FileResponse(str(target_file), media_type="application/javascript")
    if target_file.name.endswith(".json"):
        return FileResponse(str(target_file), media_type="application/json")
    if target_file.name.endswith(".svg"):
        return FileResponse(str(target_file), media_type="image/svg+xml")
    if target_file.name.endswith(".png"):
        return FileResponse(str(target_file), media_type="image/png")
    if target_file.name.endswith((".webm", ".mp4")):
        file_size = target_file.stat().st_size
        range_header = request.headers.get("range")
        if range_header and file_size > 0:
            byte_range = range_header.replace("bytes=", "").split("-")
            start = int(byte_range[0]) if byte_range[0] else 0
            end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else file_size - 1
            end = min(end, file_size - 1)
            chunk_size = end - start + 1
            with open(target_file, "rb") as f:
                f.seek(start)
                data = f.read(chunk_size)
            return Response(
                content=data,
                status_code=206,
                media_type="video/webm",
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(chunk_size),
                    "Content-Type": "video/webm",
                },
            )
        return FileResponse(str(target_file), media_type="video/webm")
    if target_file.name.endswith(".ico"):
        return FileResponse(str(target_file), media_type="image/x-icon")

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
