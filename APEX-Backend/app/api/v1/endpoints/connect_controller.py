"""Connect endpoint.

The controller is intentionally thin: it receives the request, delegates to the
:class:`ConnectPipeline`, and shapes the response. It contains no GitHub logic.
"""

import logging
import time

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.application.pipelines.connect_pipeline import ConnectPipeline
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
    logger.info(
        "[CONNECT START] user_id=%s repo_url=%s has_token=%s",
        current_user.id,
        payload.repo_url,
        has_token,
    )

    try:
        t_pipe = time.perf_counter()
        result = await _pipeline.run(payload.repo_url, payload.github_token)
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

