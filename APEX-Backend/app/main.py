"""FastAPI application entrypoint.

Run locally with::

    uvicorn app.main:app --reload --reload-dir app --port 8000
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# LLM Token Tracing
import token_tracing as tt
from app.api.utility_llm_monitoring_router import router as llm_monitoring_router
from app.api.utility_router import utility_router
from app.api.v1.router import api_router
from app.core import watch_exclusions as _watch_exclusions  # noqa: F401
from app.core.config import settings
from app.core.context import job_id_ctx, repository_url_ctx, user_id_ctx
from app.core.logging_config import configure_logging
from app.infrastructure.java_runtime import log_java_runtime_diagnostics
from app.infrastructure.persistence.mongodb import mongodb_manager

from app.application.services.llm_token_tracing_service import ChainedTraceSink, MongoDBTraceSink
from app.infrastructure.persistence.mongodb_system_settings_repository import get_all_settings

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup/shutdown hook — runs once when the server boots."""
    settings.validate_auth_settings()
    log_java_runtime_diagnostics()

    logger.info("Authentication Provider: MongoDB")
    logger.info("Active Persistence: MongoDB")

    # Safe SMTP Diagnostics (no secrets or passwords logged)
    logger.info("SMTP configured: %s", settings.is_smtp_configured)
    logger.info("SMTP host: %s", settings.smtp_host or "(not configured)")
    logger.info("SMTP port: %d", settings.smtp_port)
    logger.info("SMTP username configured: %s", bool(settings.smtp_username))
    logger.info("SMTP password configured: %s", bool(settings.smtp_password))
    logger.info("SMTP TLS enabled: %s", settings.smtp_use_tls)
    logger.info("SMTP from address: %s", settings.smtp_from_address or "(not configured)")

    # Initialize MongoDB
    await mongodb_manager.connect()

    # Load dynamic settings overrides from MongoDB
    try:
        db = mongodb_manager.get_async_db()
        if db is not None:
            overrides = await get_all_settings(db)
            for key, value in overrides.items():
                if hasattr(settings, key) and value is not None:
                    if isinstance(getattr(settings, key), bool):
                        bool_val = str(value).lower() in ("true", "1", "yes", "on")
                        setattr(settings, key, bool_val)
                    else:
                        setattr(settings, key, value)
            logger.info("Applied %d dynamic setting overrides from MongoDB", len(overrides))
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to load dynamic settings from MongoDB: %s", str(e))

    # Initialize LLM Token Tracing
    sinks = [tt.JsonlTraceSink("logs/llm_usage.jsonl"), MongoDBTraceSink()]

    tt.init_token_tracing(
        sink=ChainedTraceSink(sinks),
        pricing_provider=tt.ChainedPricingProvider(tt.StaticPricingProvider()),
        provider="groq" if settings.groq_api_key else "ollama",
    )
    logger.info("LLM Token Tracing initialized (sinks: JSONL + MongoDB)")

    yield
    mongodb_manager.close()


from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app = FastAPI(title=settings.app_name, lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    for err in exc.errors():
        loc = err.get("loc", ())
        if "email" in loc:
            return JSONResponse(
                status_code=422,
                content={"detail": "Please enter a valid email address."},
            )
    errors = exc.errors()
    msg = errors[0].get("msg", "Invalid request parameters.") if errors else "Invalid request parameters."
    return JSONResponse(status_code=422, content={"detail": msg})

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

from fastapi.responses import JSONResponse
from app.core.exceptions import LLMNotConfiguredError, ChatLLMNotConfiguredError

@app.exception_handler(LLMNotConfiguredError)
async def llm_not_configured_handler(request: Request, exc: LLMNotConfiguredError):
    return JSONResponse(
        status_code=400,
        content={"detail": "llm is not configured setup in settings"},
    )

@app.exception_handler(ChatLLMNotConfiguredError)
async def chat_llm_not_configured_handler(request: Request, exc: ChatLLMNotConfiguredError):
    return JSONResponse(
        status_code=400,
        content={"detail": "llm is not configured setup in settings"},
    )

# All v1 endpoints are mounted under /api/v1 (-> POST /api/v1/connect).
app.include_router(api_router, prefix=settings.api_v1_prefix)

# LLM token monitoring endpoints under /api/llm
app.include_router(llm_monitoring_router, prefix="/api")

# Unversioned utility endpoints the frontend calls directly under /api
# (-> GET /api/github/repo-visibility, GET /api/local-project/capabilities).
app.include_router(utility_router, prefix="/api")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok", "service": settings.app_name}
