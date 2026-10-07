"""Local-project capabilities endpoint (unversioned — mounted at ``/api``).

The Connect step's "Upload Local Project" panel probes this on load to decide
what to tell the user. The upload/analyze pipeline for local projects has not
been built on this backend yet, so this honestly reports the feature as
disabled instead of 404-ing (which previously broke the capabilities probe).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.application.use_cases.generate_technical_document import GenerateTechnicalDocumentUseCase
from app.core.exceptions import (
    CloneFailedError,
    GithubServiceError,
    InvalidRepositoryUrlError,
    RepositoryAccessDeniedError,
    RepositoryNotFoundError,
)
from app.schemas.document_schema import TechnicalDocumentRequest, TechnicalDocumentResponse
from app.schemas.local_project_schema import LocalProjectCapabilitiesResponse

logger = logging.getLogger("local_project")

router = APIRouter(tags=["local-project"])
_document_use_case = GenerateTechnicalDocumentUseCase()


import io
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, File, Form, HTTPException, UploadFile

from app.api.deps import User, get_current_user
from app.infrastructure.persistence.job_repository import JobRepository
from app.infrastructure.persistence.mongodb import get_mongodb
from app.infrastructure.persistence.mongodb_ownership_repository import record_job_owner as record_mongo_owner
from app.infrastructure.workspace.workspace_paths import WorkspacePaths

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
        message="Local project upload is available.",
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

        logger.info("[LOCAL PROJECT UPLOAD SUCCESS] - JobID: %s - Project: %s", job_id, resolved_project_name)

        return JSONResponse(
            status_code=200,
            content={
                "jobId": job_id,
                "project_name": resolved_project_name,
                "project_path": repo_url,
                "repo_url": repo_url,
                "owner": "local",
                "repo": resolved_project_name,
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during local project upload.")
        raise HTTPException(status_code=500, detail=f"Failed to upload local project: {exc}")


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
