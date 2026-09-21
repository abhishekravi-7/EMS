"""Connect endpoint.

The controller is intentionally thin: it receives the request, delegates to the
:class:`ConnectPipeline`, and shapes the response. It contains no GitHub logic.
"""

import logging
import time

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.application.pipelines.connect_pipeline import ConnectPipeline
from app.application.use_cases.connect_repository import parse_github_url
from app.core.exceptions import ConnectError
from app.infrastructure.persistence.database import get_db_optional
from app.infrastructure.persistence.migration_ownership_repository import record_job_owner
from app.infrastructure.persistence.models import User
from app.schemas.connect_schema import ConnectRequest, ConnectResponse
from app.shared.response_builder import build_connect_error, build_connect_success

logger = logging.getLogger(__name__)

router = APIRouter(tags=["connect"])

_pipeline = ConnectPipeline()


@router.post(
    "/connect",
    response_model=ConnectResponse,
    summary="Validate a GitHub repository and create a migration job.",
)
async def connect_repository(
    payload: ConnectRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    """Validate the repository URL, detect visibility/access, and create a job.

    No cloning or migration happens here — this only verifies access and stores
    the connect report. Requires login: the resulting job is recorded as
    owned by `current_user`, so every later stage (Discovery, Migration,
    Docs) can verify the same user is the one asking for it.
    """
    t0 = time.perf_counter()
    has_token = bool((payload.github_token or "").strip())

    # Sanitize URL for logging to avoid credential disclosure
    try:
        parsed = parse_github_url(payload.repo_url)
        log_url = f"github.com/{parsed.owner}/{parsed.repo}"
    except Exception:  # noqa: BLE001
        log_url = "[invalid-url]"

    logger.info(
        "[CONNECT START] user_id=%s repo_url=%s has_token=%s",
        current_user.id,
        log_url,
        has_token,
    )

    try:
        t_pipe = time.perf_counter()
        
        from app.api.deps import resolve_github_token
        normalized_token = await resolve_github_token(payload.github_token, current_user)

        result = await _pipeline.run(payload.repo_url, normalized_token)
        logger.info(
            "[CONNECT PIPELINE DONE] elapsed=%.3fs job_id=%s visibility=%s status=%s",
            time.perf_counter() - t_pipe,
            result.job_id,
            result.repo_visibility,
            result.access_status,
        )
    except ConnectError as exc:
        logger.warning(
            "[CONNECT ERROR] elapsed=%.3fs status_code=%s access_status=%s message=%s",
            time.perf_counter() - t0,
            exc.http_status,
            exc.access_status,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=build_connect_error(
                access_status=exc.access_status,
                message=exc.message,
            ),
        )

    t_db = time.perf_counter()
    from app.core.config import settings

    if settings.persistence_backend == "mongodb":
        from app.infrastructure.persistence.mongodb import get_mongodb
        from app.infrastructure.persistence.mongodb_ownership_repository import (
            record_job_owner as record_mongo_owner,
        )

        mongo_db = await get_mongodb()
        if mongo_db is not None:
            await record_mongo_owner(
                mongo_db, 
                job_id=result.job_id, 
                user_id=str(current_user.id),
                owner_name=current_user.full_name,
                owner_email=current_user.email,
                repository_name=f"{result.owner}/{result.repo_name}" if result.owner else result.repo_name
            )
        else:
            logger.warning("[CONNECT] MongoDB enabled but unavailable - skipping ownership record.")
    else:
        await run_in_threadpool(record_job_owner, db, job_id=result.job_id, user_id=current_user.id)

    logger.info(
        "[CONNECT DB RECORD DONE] elapsed=%.3fs job_id=%s",
        time.perf_counter() - t_db,
        result.job_id,
    )

    total_elapsed = time.perf_counter() - t0
    logger.info(
        "[CONNECT RESPONSE] total_elapsed=%.3fs job_id=%s status=200",
        total_elapsed,
        result.job_id,
    )

    return JSONResponse(
        status_code=200,
        content=build_connect_success(
            job_id=result.job_id,
            repo_url=result.repo_url,
            owner=result.owner,
            repo_name=result.repo_name,
            repo_visibility=result.repo_visibility,
            access_status=result.access_status,
            message=result.message,
        ),
    )


def _format_relative_time(dt) -> str:
    """Helper to convert datetime to human readable relative time."""
    if not dt:
        return "Recently"
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    seconds = max(0, diff.total_seconds())
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        mins = int(seconds // 60)
        return f"{mins} min{'s' if mins != 1 else ''} ago"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(seconds // 86400)
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    months = int(days // 30)
    return f"{months} month{'s' if months != 1 else ''} ago"


@router.get(
    "/connect/recent-repositories",
    summary="Get recent repository connections and migration analyses for the user.",
)
async def get_recent_repositories(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """Fetch recent repositories connected or analyzed by the user, enriched with authoritative metadata."""
    from app.core.config import settings
    from app.infrastructure.persistence.job_repository import JobRepository

    job_repo = JobRepository()
    recent_list = []
    seen_repos = set()


    if settings.persistence_backend == "mongodb":
        from app.infrastructure.persistence.mongodb import get_mongodb
        mongo_db = await get_mongodb()
        if mongo_db is not None:
            # Query authorized jobs for the user
            is_admin = str(current_user.id) in ("1", "admin") or getattr(current_user, "role", "") == "ADMIN"
            query_filter = {} if is_admin else {"user_id": str(current_user.id)}
            cursor = mongo_db.migration_job_owners.find(query_filter).sort("last_updated", -1).limit(50)
            user_docs = await cursor.to_list(length=50)

            for doc in user_docs:
                job_id = doc.get("job_id")
                if not job_id:
                    continue

                repo_name_raw = doc.get("repository_name")
                connect_rep = job_repo.read_connect_report(job_id) or {}
                discovery_rep = job_repo.read_discovery_report(job_id)

                # If report is in MongoDB, load as fallback
                if not discovery_rep:
                    disc_doc = await mongo_db.discovery_reports.find_one({"job_id": job_id})
                    if disc_doc and "report_json" in disc_doc:
                        discovery_rep = disc_doc["report_json"]

                # Resolve repository display name
                if repo_name_raw:
                    repo_part = repo_name_raw.split("/", 1)[1] if "/" in repo_name_raw else repo_name_raw
                elif connect_rep.get("repoName"):
                    repo_part = connect_rep["repoName"]
                else:
                    repo_part = "Unnamed repository"

                # Deduplicate by repository name - keep the most recent job run
                dedup_key = repo_part.strip().lower()
                if dedup_key in seen_repos:
                    continue
                seen_repos.add(dedup_key)

                # Authoritative Owner: directly from MongoDB migration_job_owners.owner_name
                raw_owner_name = doc.get("owner_name")
                if raw_owner_name and str(raw_owner_name).strip():
                    owner_display = str(raw_owner_name).strip()
                else:
                    owner_display = "Owner unavailable"

                # Tech stack from discovery report or build tool
                tech_stack = "Java"
                if discovery_rep:
                    java_ver = discovery_rep.get("currentJavaVersion") or discovery_rep.get("detected_java_version")
                    frameworks = discovery_rep.get("frameworks") or []
                    build_tool = discovery_rep.get("buildTool") or "Maven"
                    if frameworks:
                        tech_stack = f"Java / {frameworks[0]}"
                    elif build_tool:
                        tech_stack = f"Java / {build_tool}"
                    elif java_ver:
                        tech_stack = f"Java {java_ver}"
                elif connect_rep:
                    tech_stack = "Java"

                # Components / API Endpoint Metrics
                if not discovery_rep:
                    components_str = "Not analyzed"
                else:
                    disc_status = (discovery_rep.get("status") or "").upper()
                    if disc_status in ("RUNNING", "IN_PROGRESS", "STARTING", "QUEUED"):
                        components_str = "Analyzing…"
                    elif disc_status in ("FAILED", "ERROR"):
                        components_str = "Analysis failed"
                    else:
                        # Completed or report has endpoints
                        api_count = None
                        if "apiEndpoints" in discovery_rep and isinstance(discovery_rep["apiEndpoints"], list):
                            api_count = len(discovery_rep["apiEndpoints"])
                        elif "apiEndpointCount" in discovery_rep and isinstance(discovery_rep["apiEndpointCount"], int):
                            api_count = discovery_rep["apiEndpointCount"]
                        elif discovery_rep.get("discoveryStages", {}).get("repositoryMap", {}).get("apiEndpointCount") is not None:
                            api_count = discovery_rep["discoveryStages"]["repositoryMap"]["apiEndpointCount"]

                        if api_count is not None:
                            if api_count == 1:
                                components_str = "1 API"
                            else:
                                components_str = f"{api_count} APIs"
                        else:
                            components_str = "Unavailable"

                # Default Branch
                default_branch = connect_rep.get("defaultBranch") or (discovery_rep.get("defaultBranch") if discovery_rep else None) or "main"

                # Visibility
                vis_raw = (connect_rep.get("repoVisibility") or "PRIVATE").upper()
                if "PUB" in vis_raw:
                    visibility = "Public"
                elif "LOC" in vis_raw:
                    visibility = "Local"
                else:
                    visibility = "Private"

                # Status
                if discovery_rep:
                    disc_status = (discovery_rep.get("status") or "").upper()
                    if disc_status in ("DISCOVERY_COMPLETED", "COMPLETED", "SUCCESS"):
                        status = "Analyzed"
                    elif disc_status in ("RUNNING", "IN_PROGRESS", "STARTING", "QUEUED"):
                        status = "Analyzing"
                    elif disc_status in ("FAILED", "ERROR"):
                        status = "Failed"
                    else:
                        status = "Analyzed"
                elif connect_rep:
                    status = "Connected"
                else:
                    status = "Connected"

                last_updated_dt = doc.get("last_updated")
                recent_list.append({
                    "jobId": job_id,
                    "repositoryName": repo_part,
                    "owner": owner_display,
                    "techStack": tech_stack,
                    "componentsCount": components_str,
                    "defaultBranch": default_branch,
                    "visibility": visibility,
                    "lastUpdated": last_updated_dt.isoformat() if hasattr(last_updated_dt, "isoformat") else str(last_updated_dt or ""),
                    "lastUpdatedFormatted": _format_relative_time(last_updated_dt),
                    "status": status,
                    "repoUrl": connect_rep.get("repoUrl") or f"https://github.com/{repo_name_raw or repo_part}",
                })

    return JSONResponse(status_code=200, content={"repositories": recent_list})



