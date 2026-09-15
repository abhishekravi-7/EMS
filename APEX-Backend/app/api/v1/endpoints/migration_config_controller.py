"""Migration Config endpoint.

Thin controller: validates + persists the migration destination/options via the
MigrationConfigPipeline. No repo creation or push happens here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, verify_job_ownership
from app.application.pipelines.migration_config_pipeline import MigrationConfigPipeline
from app.core.exceptions import MigrationConfigError
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.models import User
from app.infrastructure.migration_engine.ast_rule_mapper import load_catalog
from app.schemas.migration_config_schema import (
    MigrationConfigRequest,
    MigrationConfigResponse,
)

router = APIRouter(tags=["migration-config"])

_pipeline = MigrationConfigPipeline()


def _recipe_items() -> list[dict[str, str]]:
    catalog = load_catalog()
    items: list[dict[str, str]] = []

    for pack in catalog.get("packs", []):
        pack_id = str(pack.get("id") or "")
        if pack_id:
            items.append(
                {
                    "id": pack_id,
                    "name": pack_id.replace("-", " ").title(),
                    "description": f"Migration pack: {pack_id}",
                }
            )

    return items


@router.post(
    "/migration-config/{job_id}",
    response_model=MigrationConfigResponse,
    summary="Save the migration destination and options (Migration Config stage).",
)
async def save_migration_config(
    job_id: str,
    payload: MigrationConfigRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Persist the migration configuration for the job.

    Only stores the config (destination + options). Repo creation and push are
    deferred to the Start Migration stage.
    """
    await verify_job_ownership(db, job_id, current_user)
    config = payload.model_dump(by_alias=True)
    try:
        outcome = _pipeline.run(job_id, config)
    except MigrationConfigError as exc:
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
    "/migration/recipes",
    summary="Get the available migration recipe catalog.",
)
async def get_migration_recipes() -> JSONResponse:
    return JSONResponse(status_code=200, content=_recipe_items())
