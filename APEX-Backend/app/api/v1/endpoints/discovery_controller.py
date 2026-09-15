"""Discovery endpoint.

Thin controller: receives the request, delegates to the DiscoveryPipeline
(run off the event loop), and returns the response. No clone or analyzer logic
lives here.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, verify_job_ownership
from app.application.pipelines.discovery_pipeline import DiscoveryPipeline
from app.application.use_cases.assess_microservice_eligibility import (
    AssessMicroserviceEligibilityUseCase,
)
from app.application.use_cases.browse_repository import RepositoryFileBrowser
from app.application.use_cases.get_dashboard_stats import GetDashboardStatsUseCase
from app.core.exceptions import DiscoveryError, RepositoryBrowseError
from app.domain.models.brd_models import BrdMetadata
from app.infrastructure.persistence.database import get_db_optional
from app.infrastructure.persistence.job_repository import JobRepository
from app.infrastructure.persistence.models import User
from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.schemas.dashboard_schema import DashboardStatsResponse
from app.schemas.discovery_schema import DiscoveryRequest, DiscoveryResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["discovery"])

_pipeline = DiscoveryPipeline()
_file_browser = RepositoryFileBrowser()
_microservice_use_case = AssessMicroserviceEligibilityUseCase()
_dashboard_stats_use_case = GetDashboardStatsUseCase()


@router.get(
    "/discovery/{job_id}/dashboard-stats:1",
    include_in_schema=False,
)
async def get_dashboard_stats_compat(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> Any:
    """Compatibility route for 'dashboard-stats:1' suffix."""
    return await get_dashboard_stats(job_id, current_user, db)


@router.get(
    "/discovery/{job_id}/dashboard-stats",
    response_model=DashboardStatsResponse,
    summary="Get aggregated dashboard statistics for the migration job.",
)
async def get_dashboard_stats(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> Any:
    try:
        await verify_job_ownership(db, job_id, current_user)
    except HTTPException as exc:
        # If the job is not found or access is denied, return null to avoid console errors.
        if exc.status_code in (403, 404):
            return JSONResponse(status_code=200, content=None)
        raise

    try:
        return await run_in_threadpool(_dashboard_stats_use_case.execute, job_id)
    except Exception as exc:
        logger.exception("Error generating dashboard stats")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/discovery/{job_id}",
    response_model=DiscoveryResponse,
    summary="Clone and analyze a connected repository (Discovery stage).",
)
async def run_discovery(
    job_id: str,
    payload: DiscoveryRequest | None = Body(default=None),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    """Clone the connected repository and analyze the project.

    Read-only after cloning — no migration, build, or file modification happens.
    """
    await verify_job_ownership(db, job_id, current_user)
    token = payload.github_token if payload else None
    force_refresh = payload.force_refresh if payload else False
    try:
        outcome = await run_in_threadpool(_pipeline.run, job_id, token, force_refresh)
    except DiscoveryError as exc:
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "jobId": job_id,
                "status": exc.status,
                "message": exc.message,
            },
        )

    return JSONResponse(status_code=200, content=outcome.response)


@router.get(
    "/discovery/{job_id}/files",
    summary="List files/folders in the cloned repository (Discovery workspace).",
)
async def list_discovery_files(
    job_id: str,
    path: str = Query("", description="Folder path relative to the repository root."),
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    """Lazily list one directory level of the job's already-cloned repo.

    No re-cloning and no GitHub API calls — this reads the ``original-repo``
    clone Discovery already made, so it works for large repos without extra
    round trips (only the currently expanded folder is listed).
    """
    await verify_job_ownership(db, job_id, current_user)
    try:
        entries = await run_in_threadpool(_file_browser.list_directory, job_id, path)
    except RepositoryBrowseError as exc:
        return JSONResponse(
            status_code=exc.http_status,
            content={"jobId": job_id, "status": exc.status, "message": exc.message},
        )

    return JSONResponse(
        status_code=200,
        content={
            "jobId": job_id,
            "path": path,
            "files": [
                {"name": entry.name, "path": entry.path, "type": entry.type, "size": entry.size, "url": ""}
                for entry in entries
            ],
        },
    )


@router.get(
    "/discovery/{job_id}/file",
    summary="Read a text file's content from the cloned repository (Discovery workspace).",
)
async def get_discovery_file_content(
    job_id: str,
    path: str = Query(..., description="File path relative to the repository root."),
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    await verify_job_ownership(db, job_id, current_user)
    try:
        result = await run_in_threadpool(_file_browser.read_file, job_id, path)
    except RepositoryBrowseError as exc:
        return JSONResponse(
            status_code=exc.http_status,
            content={"jobId": job_id, "status": exc.status, "message": exc.message},
        )

    return JSONResponse(
        status_code=200,
        content={
            "jobId": job_id,
            "filePath": result.path,
            "content": result.content,
            "size": result.size,
        },
    )


@router.get(
    "/discovery/{job_id}/microservice-eligibility:1",
    include_in_schema=False,
)
async def get_microservice_eligibility_compat(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    """Compatibility route for 'microservice-eligibility:1' suffix."""
    return await get_microservice_eligibility(job_id, current_user, db)


@router.get(
    "/discovery/{job_id}/microservice-eligibility",
    summary="Assess microservice eligibility from the cloned repository (Discovery workspace).",
)
async def get_microservice_eligibility(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    """Real static analysis over the job's cloned repo.

    Detects controllers/services/repositories/entities, groups them into
    per-controller business chunks via their actual dependency graph, and
    scores each chunk. No re-cloning, no GitHub API calls, no mock data.
    """
    try:
        await verify_job_ownership(db, job_id, current_user)
    except HTTPException as exc:
        # If the job is not found or access is denied, return null to avoid console errors.
        if exc.status_code in (403, 404):
            return JSONResponse(status_code=200, content=None)
        raise

    try:
        result = await run_in_threadpool(_microservice_use_case.execute, job_id)
    except RepositoryBrowseError as exc:
        return JSONResponse(
            status_code=exc.http_status,
            content={"jobId": job_id, "status": exc.status, "message": exc.message},
        )
    except Exception as exc:
        logger.exception("Unexpected error in microservice eligibility for job %s", job_id)
        return JSONResponse(
            status_code=500,
            content={
                "jobId": job_id,
                "status": "ERROR",
                "message": f"An internal error occurred during microservice assessment: {exc}",
            },
        )

    return JSONResponse(status_code=200, content=result)


@router.post(
    "/discovery/{job_id}/brd",
    summary="Upload a Business Requirements Document (BRD) for the migration job.",
)
async def upload_brd_document(
    job_id: str,
    file: UploadFile = File(...),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    await verify_job_ownership(db, job_id, current_user)

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    raw_filename = file.filename
    clean_name = re.sub(r"[^\w\.\-_]", "_", Path(raw_filename).name)
    ext = Path(clean_name).suffix.lower()
    allowed_extensions = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt", ".md"}

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Supported formats: {', '.join(sorted(allowed_extensions))}",
        )

    # Read and check size
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes)")

    max_size_bytes = 25 * 1024 * 1024  # 25 MB
    if len(content) > max_size_bytes:
        raise HTTPException(status_code=400, detail="File exceeds maximum allowed size of 25MB")

    # Content signature validation to prevent file spoofing
    if content.startswith(b"MZ"):
        raise HTTPException(status_code=400, detail="Executable files are not permitted.")

    if ext == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Invalid PDF file content: missing PDF signature.")

    if ext in [".docx", ".xlsx"] and not content.startswith(b"PK\x03\x04"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {ext} file content: missing OpenXML/ZIP archive signature.",
        )

    if ext == ".xls" and not (
        content.startswith(b"\xd0\xcf\x11\xe0")
        or b"<?xml" in content[:200]
        or b"<Workbook" in content[:500]
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid Excel (.xls) file content: missing binary workbook signature.",
        )

    paths = WorkspacePaths(job_id)
    paths.brd_dir.mkdir(parents=True, exist_ok=True)

    # Clear prior BRD files if any
    for existing in paths.brd_dir.iterdir():
        if existing.is_file():
            try:
                existing.unlink()
            except Exception:  # noqa: BLE001, S110
                pass  # nosec B110

    target_file = paths.brd_dir / clean_name
    target_file.write_bytes(content)

    metadata = BrdMetadata(
        job_id=job_id,
        filename=clean_name,
        file_type=ext.lstrip(".").upper(),
        size_bytes=len(content),
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        status="UPLOADED",
    )

    paths.brd_metadata_path.write_text(json.dumps(metadata.model_dump(), indent=2), encoding="utf-8")

    return JSONResponse(status_code=200, content=metadata.model_dump())


@router.get(
    "/discovery/{job_id}/brd:1",
    include_in_schema=False,
)
async def get_brd_metadata_compat(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    """Compatibility route for 'brd:1' suffix seen in some logs."""
    return await get_brd_document_metadata(job_id, current_user, db)


@router.get(
    "/discovery/{job_id}/brd",
    summary="Get uploaded BRD document metadata for the migration job.",
)
async def get_brd_document_metadata(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    try:
        await verify_job_ownership(db, job_id, current_user)
    except HTTPException as exc:
        if exc.status_code in (403, 404):
            return JSONResponse(status_code=200, content={"status": "NONE", "job_id": job_id})
        raise

    paths = WorkspacePaths(job_id)

    if paths.brd_metadata_path.exists():
        try:
            data = json.loads(paths.brd_metadata_path.read_text(encoding="utf-8"))
            return JSONResponse(status_code=200, content=data)
        except Exception:  # noqa: BLE001, S110
            pass  # nosec B110

    job_repo = JobRepository()
    metadata = await run_in_threadpool(job_repo.get_brd_metadata, job_id)
    if metadata:
        return JSONResponse(status_code=200, content=metadata)

    return JSONResponse(status_code=200, content={"status": "NONE", "job_id": job_id})


@router.delete(
    "/discovery/{job_id}/brd",
    summary="Remove uploaded BRD document for the migration job.",
)
async def delete_brd_document(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    await verify_job_ownership(db, job_id, current_user)
    paths = WorkspacePaths(job_id)

    if paths.brd_dir.exists():
        for f in paths.brd_dir.iterdir():
            if f.is_file():
                try:
                    f.unlink()
                except Exception:  # noqa: BLE001, S110
                    pass  # nosec B110
    
    if paths.brd_metadata_path.exists():
        try:
            paths.brd_metadata_path.unlink()
        except Exception: # noqa: BLE001, S110
            pass

    return JSONResponse(status_code=200, content={"status": "DELETED", "job_id": job_id})


@router.get(
    "/discovery/{job_id}/brd/file",
    summary="View the uploaded BRD document for the migration job.",
)
async def view_brd_document(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> Response:
    await verify_job_ownership(db, job_id, current_user)
    paths = WorkspacePaths(job_id)

    if not paths.brd_metadata_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"code": "BRD_NOT_FOUND", "message": "No BRD document uploaded for this job."},
        )

    try:
        metadata = json.loads(paths.brd_metadata_path.read_text(encoding="utf-8"))
        filename = metadata.get("filename", "")
        clean_filename = Path(filename).name
        target_file = paths.brd_dir / clean_filename

        if not target_file.exists() or not target_file.is_file():
            raise HTTPException(
                status_code=404,
                detail={"code": "BRD_FILE_NOT_FOUND", "message": "BRD document file not found."},
            )

        ext = target_file.suffix.lower()
        media_type = "application/octet-stream"
        if ext == ".pdf":
            media_type = "application/pdf"
        elif ext in [".txt", ".md"]:
            media_type = "text/plain; charset=utf-8"
        elif ext == ".docx":
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif ext == ".doc":
            media_type = "application/msword"
        elif ext == ".xlsx":
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif ext == ".xls":
            media_type = "application/vnd.ms-excel"

        content = target_file.read_bytes()
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'inline; filename="{clean_filename}"',
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving BRD file for job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"code": "BRD_READ_ERROR", "message": "Failed to read BRD document."},
        ) from e


@router.get(
    "/discovery/{job_id}/brd/download",
    summary="Download the BRD PDF for the job.",
)
async def download_brd(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> FileResponse:
    await verify_job_ownership(db, job_id, current_user)
    paths = WorkspacePaths(job_id)

    if paths.brd_metadata_path.exists():
        try:
            metadata = json.loads(paths.brd_metadata_path.read_text(encoding="utf-8"))
            filename = metadata.get("filename", "brd.pdf")
            clean_filename = Path(filename).name
            target_file = paths.brd_dir / clean_filename
            if target_file.exists():
                return FileResponse(
                    path=target_file,
                    filename=clean_filename,
                )
        except Exception:
            pass

    if hasattr(paths, 'brd_path') and paths.brd_path.exists():
        return FileResponse(
            path=paths.brd_path,
            filename="brd.pdf",
        )

    raise HTTPException(status_code=404, detail="No BRD found for this job.")
