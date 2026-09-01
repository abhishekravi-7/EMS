"""Discovery endpoint.

Thin controller: receives the request, delegates to the DiscoveryPipeline
(run off the event loop), and returns the response. No clone or analyzer logic
lives here.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, File, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, verify_job_ownership
from app.application.pipelines.discovery_pipeline import DiscoveryPipeline
from app.application.use_cases.assess_microservice_eligibility import (
    AssessMicroserviceEligibilityUseCase,
)
from app.application.use_cases.browse_repository import RepositoryFileBrowser
from app.core.exceptions import DiscoveryError, RepositoryBrowseError
from app.infrastructure.persistence.database import get_db_optional
from app.infrastructure.persistence.job_repository import JobRepository
from app.infrastructure.persistence.models import User
from app.schemas.discovery_schema import DiscoveryRequest, DiscoveryResponse

router = APIRouter(tags=["discovery"])

_pipeline = DiscoveryPipeline()
_file_browser = RepositoryFileBrowser()
_microservice_use_case = AssessMicroserviceEligibilityUseCase()


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
    verify_job_ownership(db, job_id, current_user)
    token = payload.github_token if payload else None
    try:
        outcome = await run_in_threadpool(_pipeline.run, job_id, token)
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
    verify_job_ownership(db, job_id, current_user)
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
    verify_job_ownership(db, job_id, current_user)
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
    verify_job_ownership(db, job_id, current_user)
    try:
        result = await run_in_threadpool(_microservice_use_case.execute, job_id)
    except RepositoryBrowseError as exc:
        return JSONResponse(
            status_code=exc.http_status,
            content={"jobId": job_id, "status": exc.status, "message": exc.message},
        )

    return JSONResponse(status_code=200, content=result)


@router.post(
    "/discovery/{job_id}/brd",
    summary="Upload a BRD attachment for the job.",
)
async def upload_brd(
    job_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    verify_job_ownership(db, job_id, current_user)
    
    # Simple validation: accept only PDFs and max 10MB (example)
    if file.content_type != "application/pdf":
         return JSONResponse(status_code=415, content={"message": "Only PDF files are supported."})
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
         return JSONResponse(status_code=413, content={"message": "File is too large (max 10MB)."})

    job_repo = JobRepository()
    metadata = await run_in_threadpool(
        job_repo.save_brd_attachment, job_id, content, file.filename
    )
    return JSONResponse(status_code=200, content=metadata)


@router.get(
    "/discovery/{job_id}/brd",
    summary="Get BRD attachment metadata if it exists.",
)
async def get_brd_metadata(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    verify_job_ownership(db, job_id, current_user)
    job_repo = JobRepository()
    metadata = await run_in_threadpool(job_repo.get_brd_metadata, job_id)
    if not metadata:
        return JSONResponse(status_code=404, content={"message": "No BRD found."})
    return JSONResponse(status_code=200, content=metadata)
