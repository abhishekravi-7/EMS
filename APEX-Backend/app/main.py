"""FastAPI application entrypoint.

Run locally with::

    uvicorn app.main:app --reload --reload-dir app --port 8000
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.deps import get_db
from app.api.utility_router import utility_router
from app.api.utility_llm_monitoring_router import router as llm_monitoring_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.context import user_id_ctx, job_id_ctx, repository_url_ctx
from app.core.logging_config import configure_logging
from app.infrastructure.persistence.database import (
    Base,
    engine,
    ensure_database_exists,
    verify_database_connection,
)

# LLM Token Tracing
import token_tracing as tt

# Import every ORM model module here so `Base.metadata` knows about all
# tables before `create_all()` runs below — SQLAlchemy only creates tables
# for model classes that have actually been imported (their class body must
# have executed at least once). `noqa: F401` because this import is only for
# its import-time side effect, not for anything used by name in this file.
from app.infrastructure.persistence import models as _persistence_models  # noqa: F401

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup/shutdown hook — runs once when the server boots.

    For a Java developer: this is roughly the FastAPI equivalent of a Spring
    Boot `ApplicationRunner`/`@PostConstruct` block that runs once at boot,
    before any request is served.
    """
    settings.validate_auth_settings()
    # Local/dev convenience: create the target database itself if it doesn't
    # exist yet (the PostgreSQL user/role must already exist and have
    # CREATEDB — this does not create roles, only the database).
    #
    # Skipped in production: a managed Postgres provider creates the database
    # for you, and the role it issues owns only that one database — it can
    # neither connect to the `postgres` maintenance database this needs nor
    # run CREATE DATABASE. Attempting it there raises RuntimeError and the
    # service never finishes booting.
    if settings.database_enabled:
        if not settings.is_production:
            ensure_database_exists()
        verify_database_connection()
        # Creates any tables that don't exist yet. Never drops or alters an
        # existing table, and never touches existing rows — safe to run on every
        # startup. Alembic is intentionally not used yet (see requirements.txt).
        Base.metadata.create_all(bind=engine)  # type: ignore[arg-type]
        logger.info("Database tables verified/created.")
    else:
        logger.info("Database disabled by configuration — skipping DB startup tasks.")

    # Initialize LLM Token Tracing
    from app.application.services.llm_token_tracing_service import ChainedTraceSink
    sinks = [tt.JsonlTraceSink("logs/llm_usage.jsonl")]
    if settings.database_enabled:
        from app.application.services.llm_token_tracing_service import DatabaseTraceSink

        sinks.append(DatabaseTraceSink())

    tt.init_token_tracing(
        sink=ChainedTraceSink(sinks),
        pricing_provider=tt.ChainedPricingProvider(tt.StaticPricingProvider()),
        provider="groq" if settings.groq_api_key else "ollama",
    )
    logger.info("LLM Token Tracing initialized (sinks: JSONL + Database)")

    yield
    # (nothing to clean up on shutdown today)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

@app.middleware("http")
async def context_middleware(request: Request, call_next):
    """Middleware to set request-scoped context for tracing and ensure it is reset."""
    user_token = user_id_ctx.set(None)
    job_token = job_id_ctx.set(None)
    repo_token = repository_url_ctx.set(None)
    try:
        return await call_next(request)
    finally:
        user_id_ctx.reset(user_token)
        job_id_ctx.reset(job_token)
        repository_url_ctx.reset(repo_token)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All v1 endpoints are mounted under /api/v1 (-> POST /api/v1/connect).
app.include_router(api_router, prefix=settings.api_v1_prefix)

# LLM token monitoring endpoints under /api/llm
app.include_router(llm_monitoring_router, prefix="/api")

# Unversioned utility endpoints the frontend calls directly under /api
# (-> GET /api/github/repo-visibility, GET /api/local-project/capabilities).
app.include_router(utility_router, prefix="/api")


def _mount_frontend_bundle() -> None:
    """Serve the built SPA when the frontend bundle is present."""
    frontend_dist = Path(__file__).resolve().parents[1] / "frontend-dist"
    if not frontend_dist.is_dir():
        logger.info("Frontend bundle not found at %s; API-only mode.", frontend_dist)
        return

    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


_mount_frontend_bundle()


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok", "service": settings.app_name}
