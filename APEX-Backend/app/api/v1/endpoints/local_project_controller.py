"""Local-project capabilities and analysis endpoints (unversioned — mounted at ``/api``).

Provides endpoints for:
  - ``GET /api/local-project/capabilities``
  - ``POST /api/local-project/upload``
  - ``POST /api/local-project/upload-chunk``
  - ``POST /api/local-project/analyze``
  - ``GET /api/local-project/list-files``
  - ``GET /api/local-project/file-content``
  - ``POST /api/local-project/microservice-eligibility``
  - ``POST /api/local-project/generate-brd-document``
"""

from __future__ import annotations

import io
import logging
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.api.deps import User, get_current_user
from app.application.use_cases.analyze_repo_url import _to_repo_analysis
from app.application.use_cases.assess_microservice_eligibility import AssessMicroserviceEligibilityUseCase
from app.application.use_cases.generate_technical_document import GenerateTechnicalDocumentUseCase
from app.application.use_cases.run_discovery import RunDiscoveryUseCase
from app.core.config import settings
from app.core.exceptions import (
    CloneFailedError,
    GithubServiceError,
    InvalidRepositoryUrlError,
    RepositoryAccessDeniedError,
    RepositoryNotFoundError,
)
from app.infrastructure.analyzers.project_analyzer import ProjectAnalyzer
from app.infrastructure.analyzers.spring_boot_eligibility import compute_eligibility
from app.infrastructure.persistence.job_repository import JobRepository
from app.infrastructure.persistence.mongodb import get_mongodb
from app.infrastructure.persistence.mongodb_ownership_repository import record_job_owner as record_mongo_owner
from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.schemas.document_schema import TechnicalDocumentRequest, TechnicalDocumentResponse
from app.schemas.local_project_schema import (
    LocalProjectAnalysisResponse,
    LocalProjectCapabilitiesResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["local-project"])
_document_use_case = GenerateTechnicalDocumentUseCase()
_microservice_use_case = AssessMicroserviceEligibilityUseCase()


@router.get(
    "/local-project/capabilities",
    response_model=LocalProjectCapabilitiesResponse,
    summary="Report whether local-project upload/analysis is available.",
)
async def local_project_capabilities() -> LocalProjectCapabilitiesResponse:
    return LocalProjectCapabilitiesResponse(
        enabled=True,
        hosted_mode=False,
        allow_any_path=True,
        allowed_roots=[],
        supports_upload=True,
        message="Local project upload and analysis are available.",
    )


def _safe_extract_zip(zip_bytes: bytes, target_dir: Path) -> str:
    """Extract zip bytes into target_dir safely, resolving single top-level directory wrapper.

    Returns the project name derived from root directory or files.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # Zip slip protection
        resolved_target = target_dir.resolve()
        for member in zf.infolist():
            member_path = (target_dir / member.filename).resolve()
            if not str(member_path).startswith(str(resolved_target)):
                raise ValueError("Zip file contains path outside extraction target (Zip Slip)")

        # Check if all files are inside a single top-level directory wrapper
        names = [n for n in zf.namelist() if not n.endswith("/")]
        if not names:
            raise ValueError("Zip file is empty")

        top_dirs = {n.split("/")[0] for n in names if "/" in n}
        has_root_files = any("/" not in n for n in names)

        # If all files share a single common top-level dir and there are no files at the root
        strip_prefix = ""
        project_name = "local-project"
        if len(top_dirs) == 1 and not has_root_files:
            single_top = list(top_dirs)[0]
            strip_prefix = f"{single_top}/"
            project_name = single_top

        for member in zf.infolist():
            filename = member.filename
            if strip_prefix and filename.startswith(strip_prefix):
                filename = filename[len(strip_prefix):]
            elif strip_prefix and filename == strip_prefix.rstrip("/"):
                continue

            if not filename or filename.endswith("/"):
                continue

            dest_path = target_dir / filename
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(dest_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

    return project_name


def _resolve_local_project(
    project_path: str | None = None,
    job_id: str | None = None,
) -> tuple[str, str, Path]:
    """Resolves (job_id, project_name, target_dir) for a local project.

    Supports:
      1. Explicit job_id
      2. Direct filesystem directory path
      3. Project name or 'local://<name>' matching a recent job in storage
      4. Fallback to the most recent local project job in storage
    """
    clean_path = (project_path or "").strip()
    if clean_path.startswith("local://"):
        clean_name = clean_path[len("local://"):].strip()
    else:
        clean_name = clean_path

    # 1. If explicit job_id is provided
    if job_id and job_id.strip():
        jid = job_id.strip()
        candidate = WorkspacePaths(jid).original_repo_dir
        if candidate.is_dir() and any(candidate.iterdir()):
            pname = clean_name or "local-project"
            connect = JobRepository().read_connect_report(jid)
            if connect and connect.get("repoName"):
                pname = connect["repoName"]
            return jid, pname, candidate

    # 2. If clean_name is itself a job_id (e.g. "job_...")
    if clean_name.startswith("job_"):
        candidate = WorkspacePaths(clean_name).original_repo_dir
        if candidate.is_dir() and any(candidate.iterdir()):
            connect = JobRepository().read_connect_report(clean_name)
            pname = (connect.get("repoName") if connect else None) or clean_name
            return clean_name, pname, candidate

    # 3. If clean_path is a direct directory on the filesystem
    if clean_path:
        local_dir = Path(clean_path).resolve()
        if local_dir.is_dir() and any(local_dir.iterdir()):
            jid = job_id or f"job_{uuid.uuid4().hex[:12]}"
            return jid, local_dir.name, local_dir

    # 4. Search storage/migration-jobs for matching job or connect report
    storage_dir = settings.storage_dir
    if storage_dir.is_dir():
        job_dirs = sorted(
            [d for d in storage_dir.iterdir() if d.is_dir() and d.name.startswith("job_")],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        for jd in job_dirs:
            connect = JobRepository().read_connect_report(jd.name)
            repo_name = connect.get("repoName") if connect else None
            repo_url = connect.get("repoUrl") if connect else None
            is_local = connect.get("isLocalProject") if connect else False

            matches = False
            if clean_name and (
                jd.name == clean_name
                or repo_name == clean_name
                or repo_url in (clean_path, f"local://{clean_name}")
            ):
                matches = True
            elif not clean_name and is_local:
                matches = True

            if matches:
                candidate = WorkspacePaths(jd.name).original_repo_dir
                if candidate.is_dir() and any(candidate.iterdir()):
                    return jd.name, repo_name or clean_name or "local-project", candidate

    raise HTTPException(
        status_code=404,
        detail=f"Local project workspace for '{clean_name or project_path}' not found. Upload the project first.",
    )


def _analyze_and_build_response(
    job_id: str,
    resolved_project_name: str,
    target_dir: Path,
) -> dict[str, Any]:
    """Runs ProjectAnalyzer and constructs the LocalProjectAnalysisResponse payload."""
    if not target_dir.is_dir() or not any(target_dir.iterdir()):
        raise HTTPException(status_code=400, detail="Project directory is empty or does not exist.")

    analyzer = ProjectAnalyzer()
    try:
        analysis = analyzer.analyze(target_dir)
    except Exception as exc:
        logger.exception("Unexpected error during local project analysis.")
        raise HTTPException(status_code=500, detail=f"Failed to analyze local project: {exc}")

    if not analysis.is_supported:
        raise HTTPException(
            status_code=400,
            detail="Unsupported project type. JavaAPEX requires a Maven (pom.xml) or Gradle (build.gradle) Java project.",
        )

    eligibility = compute_eligibility(
        build_tool_supported=analysis.is_supported,
        build_tool=analysis.build_tool,
        project_type=analysis.project_type,
        spring_framework_version=analysis.spring_framework_version,
        spring_boot_version=analysis.spring_boot_version,
        spring_boot_signal=analysis.spring_boot_signal,
        entrypoint_found=analysis.spring_entry_class is not None,
    )

    repo_analysis = _to_repo_analysis("local", resolved_project_name, analysis)
    repo_analysis["discovery_stages"] = RunDiscoveryUseCase._build_stages(analysis, eligibility)
    repo_analysis["spring_boot_eligibility"] = eligibility.to_dict()

    repo_url = f"local://{resolved_project_name}"
    created_at = datetime.now(timezone.utc).isoformat()
    job_repo = JobRepository()

    if not job_repo.read_connect_report(job_id):
        connect_report = {
            "jobId": job_id,
            "repoUrl": repo_url,
            "owner": "local",
            "repoName": resolved_project_name,
            "repoVisibility": "LOCAL",
            "accessStatus": "LOCAL_PROJECT",
            "isLocalProject": True,
            "createdAt": created_at,
        }
        job_repo.save_connect_report(job_id, connect_report)

    discovery_report = RunDiscoveryUseCase._build_report(
        job_id, repo_url, "local", resolved_project_name, analysis, eligibility, created_at
    )
    job_repo.save_discovery_report(job_id, discovery_report)

    return {
        "jobId": job_id,
        "project_name": resolved_project_name,
        "project_path": repo_url,
        "repo_url": repo_url,
        "owner": "local",
        "repo": resolved_project_name,
        "analysis": repo_analysis,
    }


@router.post(
    "/local-project/upload",
    summary="Upload a local project (ZIP or multi-part folder files) and create a migration job.",
)
async def upload_local_project(
    file: UploadFile | None = File(default=None),
    zip_file: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
    project_name: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """Accepts uploaded project files or a zip archive, creates a migration job,
    and extracts/writes files into the job workspace under `original-repo`.
    """
    effective_zip = zip_file or (file if file and file.filename and file.filename.lower().endswith(".zip") else None)
    
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    paths = WorkspacePaths(job_id)
    target_dir = paths.original_repo_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    resolved_project_name = project_name.strip() if project_name and project_name.strip() else ""

    try:
        if effective_zip:
            content = await effective_zip.read()
            if not content:
                raise HTTPException(status_code=400, detail="Uploaded ZIP file is empty.")
            try:
                extracted_name = _safe_extract_zip(content, target_dir)
                if not resolved_project_name:
                    resolved_project_name = (
                        extracted_name
                        if extracted_name != "local-project"
                        else Path(effective_zip.filename or "uploaded-project").stem
                    )
            except zipfile.BadZipFile:
                raise HTTPException(status_code=400, detail="Uploaded file is not a valid ZIP archive.")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        elif files or file:
            upload_file_list = files if files else ([file] if file else [])
            if not upload_file_list:
                raise HTTPException(status_code=400, detail="No files were provided for upload.")

            # Detect if there is a common root directory
            filenames = [f.filename for f in upload_file_list if f.filename]
            if not filenames:
                raise HTTPException(status_code=400, detail="No valid file paths received.")

            top_dirs = {fn.replace("\\", "/").split("/")[0] for fn in filenames if "/" in fn.replace("\\", "/")}
            has_root_files = any("/" not in fn.replace("\\", "/") for fn in filenames)
            strip_prefix = ""
            if len(top_dirs) == 1 and not has_root_files:
                single_top = list(top_dirs)[0]
                strip_prefix = f"{single_top}/"
                if not resolved_project_name:
                    resolved_project_name = single_top

            for uploaded in upload_file_list:
                rel_path = (uploaded.filename or "").replace("\\", "/")
                if strip_prefix and rel_path.startswith(strip_prefix):
                    rel_path = rel_path[len(strip_prefix):]

                if not rel_path or rel_path.endswith("/"):
                    continue

                dest_path = (target_dir / rel_path).resolve()
                if not str(dest_path).startswith(str(target_dir.resolve())):
                    continue  # Guard against directory traversal

                dest_path.parent.mkdir(parents=True, exist_ok=True)
                file_bytes = await uploaded.read()
                dest_path.write_bytes(file_bytes)

            if not resolved_project_name:
                resolved_project_name = "uploaded-project"
        else:
            raise HTTPException(status_code=400, detail="No files or ZIP archive provided.")

        if not any(target_dir.iterdir()):
            raise HTTPException(status_code=400, detail="Extracted project directory is empty.")

        # Validate that the project contains a supported Maven (pom.xml) or Gradle build file
        analyzer = ProjectAnalyzer()
        try:
            initial_check = analyzer.analyze(target_dir)
        except Exception as exc:
            logger.exception("Unexpected error during local project validation.")
            raise HTTPException(status_code=500, detail=f"Failed to analyze local project: {exc}")

        if not initial_check.is_supported:
            raise HTTPException(
                status_code=400,
                detail="Unsupported project type. JavaAPEX requires a Maven (pom.xml) or Gradle (build.gradle) Java project.",
            )

        if not resolved_project_name:
            resolved_project_name = "local-project"

        repo_url = f"local://{resolved_project_name}"

        # Write connect-report.json so Discovery can find the job and know it is a local project
        connect_report = {
            "jobId": job_id,
            "repoUrl": repo_url,
            "owner": "local",
            "repoName": resolved_project_name,
            "repoVisibility": "LOCAL",
            "accessStatus": "LOCAL_PROJECT",
            "isLocalProject": True,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        JobRepository().save_connect_report(job_id, connect_report)

        # Record user ownership for the newly created job
        mongo_db = await get_mongodb()
        if mongo_db is not None:
            await record_mongo_owner(
                mongo_db, 
                job_id=job_id, 
                user_id=str(current_user.id),
                owner_name=current_user.full_name,
                owner_email=current_user.email,
                repository_name=resolved_project_name
            )

        logger.info("[LOCAL PROJECT UPLOAD SUCCESS] job_id=%s project=%s", job_id, resolved_project_name)

        return JSONResponse(
            status_code=200,
            content={
                "jobId": job_id,
                "project_name": resolved_project_name,
                "project_path": repo_url,
                "repo_url": repo_url,
                "owner": "local",
                "repo": resolved_project_name,
                "analysis": None,
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during local project upload.")
        raise HTTPException(status_code=500, detail=f"Failed to upload local project: {exc}")


@router.post(
    "/local-project/upload-chunk",
    summary="Upload a single chunk of a large local project archive.",
)
async def upload_local_project_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    file_name: str = Form(...),
    project_name: str | None = Form(default=None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """Handles chunked multipart uploads for large local project archives."""
    chunk_dir = settings.storage_dir / "_upload-chunks" / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_file = chunk_dir / f"chunk_{chunk_index:05d}"
    chunk_file.write_bytes(await file.read())

    if chunk_index < total_chunks:
        return JSONResponse(
            status_code=200,
            content={
                "status": "chunk_received",
                "upload_id": upload_id,
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
            },
        )

    # All chunks received — combine them into a single archive
    assembled_bytes = bytearray()
    for idx in range(1, total_chunks + 1):
        c_path = chunk_dir / f"chunk_{idx:05d}"
        if not c_path.exists():
            shutil.rmtree(chunk_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"Missing chunk {idx} of {total_chunks}")
        assembled_bytes.extend(c_path.read_bytes())

    shutil.rmtree(chunk_dir, ignore_errors=True)

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    paths = WorkspacePaths(job_id)
    target_dir = paths.original_repo_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_project_name = project_name.strip() if project_name and project_name.strip() else ""

    try:
        extracted_name = _safe_extract_zip(bytes(assembled_bytes), target_dir)
        if not resolved_project_name:
            resolved_project_name = (
                extracted_name
                if extracted_name != "local-project"
                else Path(file_name).stem
            )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to extract uploaded chunks: {exc}")

    result = await run_in_threadpool(
        _analyze_and_build_response,
        job_id,
        resolved_project_name or "local-project",
        target_dir,
    )

    mongo_db = await get_mongodb()
    if mongo_db is not None:
        await record_mongo_owner(
            mongo_db,
            job_id=job_id,
            user_id=str(current_user.id),
            owner_name=current_user.full_name,
            owner_email=current_user.email,
            repository_name=resolved_project_name or "local-project",
        )

    return JSONResponse(status_code=200, content=result)


@router.post(
    "/local-project/analyze",
    summary="Analyze a local Java project from an uploaded workspace, local path, or direct upload.",
    response_model=LocalProjectAnalysisResponse,
)
async def analyze_local_project(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """Analyzes a local Java project.

    Accepts:
      - JSON body: ``{"project_path": "..."}`` or ``{"job_id": "..."}``
      - Multi-part form data: Direct file/zip upload with optional ``project_name``
    """
    content_type = request.headers.get("content-type", "").lower()
    project_path: str | None = None
    project_name: str | None = None
    job_id: str | None = None
    file: UploadFile | None = None
    zip_file: UploadFile | None = None
    files: list[UploadFile] | None = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        project_path = form.get("project_path")
        project_name = form.get("project_name")
        job_id = form.get("job_id")
        raw_file = form.get("file")
        if raw_file and hasattr(raw_file, "filename") and hasattr(raw_file, "read"):
            file = raw_file
        raw_zip = form.get("zip_file")
        if raw_zip and hasattr(raw_zip, "filename") and hasattr(raw_zip, "read"):
            zip_file = raw_zip
        raw_files = form.getlist("files")
        if raw_files and any(hasattr(f, "filename") and hasattr(f, "read") for f in raw_files):
            files = [f for f in raw_files if hasattr(f, "filename") and hasattr(f, "read")]
    else:
        try:
            body = await request.json()
            if isinstance(body, dict):
                project_path = body.get("project_path")
                project_name = body.get("project_name")
                job_id = body.get("job_id")
        except Exception:
            pass

    # Fallback to query parameters
    if not project_path:
        project_path = request.query_params.get("project_path")
    if not project_name:
        project_name = request.query_params.get("project_name")
    if not job_id:
        job_id = request.query_params.get("job_id")

    # Path A: Files are uploaded directly to /analyze
    effective_zip = zip_file or (file if file and file.filename and file.filename.lower().endswith(".zip") else None)
    if effective_zip or files or file:
        assigned_job_id = job_id or f"job_{uuid.uuid4().hex[:12]}"
        paths = WorkspacePaths(assigned_job_id)
        target_dir = paths.original_repo_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        resolved_project_name = project_name.strip() if project_name and project_name.strip() else ""

        if effective_zip:
            content = await effective_zip.read()
            if not content:
                raise HTTPException(status_code=400, detail="Uploaded ZIP file is empty.")
            try:
                extracted_name = _safe_extract_zip(content, target_dir)
                if not resolved_project_name:
                    resolved_project_name = (
                        extracted_name
                        if extracted_name != "local-project"
                        else Path(effective_zip.filename or "uploaded-project").stem
                    )
            except zipfile.BadZipFile:
                raise HTTPException(status_code=400, detail="Uploaded file is not a valid ZIP archive.")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        else:
            upload_file_list = files if files else ([file] if file else [])
            if not upload_file_list:
                raise HTTPException(status_code=400, detail="No files provided for upload.")

            filenames = [f.filename for f in upload_file_list if f.filename]
            if not filenames:
                raise HTTPException(status_code=400, detail="No valid file paths received.")

            top_dirs = {fn.replace("\\", "/").split("/")[0] for fn in filenames if "/" in fn.replace("\\", "/")}
            has_root_files = any("/" not in fn.replace("\\", "/") for fn in filenames)
            strip_prefix = ""
            if len(top_dirs) == 1 and not has_root_files:
                single_top = list(top_dirs)[0]
                strip_prefix = f"{single_top}/"
                if not resolved_project_name:
                    resolved_project_name = single_top

            for uploaded in upload_file_list:
                rel_path = (uploaded.filename or "").replace("\\", "/")
                if strip_prefix and rel_path.startswith(strip_prefix):
                    rel_path = rel_path[len(strip_prefix):]
                if not rel_path or rel_path.endswith("/"):
                    continue

                dest_path = (target_dir / rel_path).resolve()
                if not str(dest_path).startswith(str(target_dir.resolve())):
                    continue
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_bytes(await uploaded.read())

            if not resolved_project_name:
                resolved_project_name = "uploaded-project"

        result = await run_in_threadpool(
            _analyze_and_build_response,
            assigned_job_id,
            resolved_project_name or "local-project",
            target_dir,
        )

        mongo_db = await get_mongodb()
        if mongo_db is not None:
            await record_mongo_owner(
                mongo_db,
                job_id=assigned_job_id,
                user_id=str(current_user.id),
                owner_name=current_user.full_name,
                owner_email=current_user.email,
                repository_name=resolved_project_name or "local-project",
            )
        return JSONResponse(status_code=200, content=result)

    # Path B: Project path or job ID provided
    if not project_path and not job_id:
        raise HTTPException(
            status_code=400,
            detail="Missing upload: neither project files nor project_path was provided.",
        )

    resolved_job_id, resolved_pname, target_dir = _resolve_local_project(project_path, job_id)
    if project_name and project_name.strip():
        resolved_pname = project_name.strip()

    result = await run_in_threadpool(
        _analyze_and_build_response,
        resolved_job_id,
        resolved_pname,
        target_dir,
    )

    mongo_db = await get_mongodb()
    if mongo_db is not None:
        await record_mongo_owner(
            mongo_db,
            job_id=resolved_job_id,
            user_id=str(current_user.id),
            owner_name=current_user.full_name,
            owner_email=current_user.email,
            repository_name=resolved_pname,
        )

    return JSONResponse(status_code=200, content=result)


@router.get(
    "/local-project/list-files",
    summary="List files/folders in an uploaded local project.",
)
async def list_local_project_files(
    project_path: str = Query(..., description="Project path, name, or job ID."),
    subpath: str = Query("", description="Folder path relative to project root."),
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    resolved_job_id, resolved_pname, target_dir = _resolve_local_project(project_path)
    clean_subpath = (subpath or "").strip().replace("\\", "/").lstrip("/")

    target_path = (target_dir / clean_subpath).resolve() if clean_subpath else target_dir.resolve()
    if not str(target_path).startswith(str(target_dir.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal detected.")
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Subpath not found.")

    files = []
    if target_path.is_dir():
        for item in sorted(target_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            rel = item.relative_to(target_dir).as_posix()
            files.append({
                "name": item.name,
                "path": rel,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0,
                "url": "",
            })

    return JSONResponse(
        status_code=200,
        content={
            "repo_url": f"local://{resolved_pname}",
            "owner": "local",
            "repo": resolved_pname,
            "path": clean_subpath,
            "files": files,
        },
    )


@router.get(
    "/local-project/file-content",
    summary="Read a text file's content from a local project.",
)
async def get_local_project_file_content(
    project_path: str = Query(..., description="Project path, name, or job ID."),
    file_path: str = Query(..., description="File path relative to project root."),
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    resolved_job_id, resolved_pname, target_dir = _resolve_local_project(project_path)
    clean_file_path = file_path.strip().replace("\\", "/").lstrip("/")

    target_file = (target_dir / clean_file_path).resolve()
    if not str(target_file).startswith(str(target_dir.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal detected.")
    if not target_file.is_file():
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        text = target_file.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {exc}")

    return JSONResponse(
        status_code=200,
        content={
            "repo_url": f"local://{resolved_pname}",
            "owner": "local",
            "repo": resolved_pname,
            "file_path": clean_file_path,
            "content": text,
        },
    )


@router.post(
    "/local-project/microservice-eligibility",
    summary="Assess microservice eligibility for a local project.",
)
async def get_local_project_microservice_eligibility(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    project_path: str | None = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            project_path = body.get("project_path")
    except Exception:
        pass

    if not project_path:
        project_path = request.query_params.get("project_path")

    resolved_job_id, resolved_pname, target_dir = _resolve_local_project(project_path)

    try:
        result = await run_in_threadpool(_microservice_use_case.execute, resolved_job_id)
    except Exception as exc:
        logger.warning("Microservice assessment fallback for local project %s: %s", resolved_job_id, exc)
        result = {
            "eligible": False,
            "reason": "Microservice assessment unavailable for this project.",
            "components": [],
        }

    return JSONResponse(status_code=200, content=result)


@router.post(
    "/local-project/generate-brd-document",
    response_model=TechnicalDocumentResponse,
    summary="Generate a technical specification document from uploaded-project analysis.",
)
async def generate_local_project_brd_document(payload: TechnicalDocumentRequest) -> JSONResponse:
    try:
        result = await run_in_threadpool(_document_use_case.execute, payload)
    except InvalidRepositoryUrlError as exc:
        return JSONResponse(status_code=400, content={"detail": exc.message})
    except RepositoryAccessDeniedError as exc:
        return JSONResponse(status_code=403, content={"detail": exc.message})
    except RepositoryNotFoundError as exc:
        return JSONResponse(status_code=404, content={"detail": exc.message})
    except CloneFailedError as exc:
        return JSONResponse(status_code=502, content={"detail": exc.message})
    except GithubServiceError as exc:
        return JSONResponse(status_code=502, content={"detail": exc.message})
    except Exception:
        # Log the real cause server-side; never return raw exception text.
        logger.exception("Unexpected error generating local-project technical document.")
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to generate technical document."},
        )

    return JSONResponse(status_code=200, content=result)
