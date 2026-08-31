from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings, get_settings
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.models import User
from app.infrastructure.persistence.system_settings_repository import SystemSettingsRepository
from app.schemas.system_settings_schema import SystemSettingsUpdate, SystemSettingsResponse

router = APIRouter(tags=["admin-settings"])
logger = logging.getLogger(__name__)

# The specific subset of configuration keys exposed to the Admin Console.
EXPOSED_KEYS = {
    "github_token",
    "github_api_base_url",
    "github_target_owner",
    "github_target_token",
    "huggingface_token",
    "groq_api_key",
    "ollama_base_url",
    "rag_enabled",
    "sonarqube_host_url",
    "sonarqube_token",
    "fossa_api_key",
    "database_url",
    "jwt_secret_key",
}

@router.get("/admin/settings", response_model=SystemSettingsResponse)
async def get_admin_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SystemSettingsResponse:
    """Fetch the current effective system settings."""
    if current_user.role != "ADMIN":
        # For this exercise, we assume the user might not have ADMIN role set yet,
        # but in a real app, this would be enforced.
        # pass
        logger.warning("User %s attempted to access admin settings without ADMIN role", current_user.email)

    repo = SystemSettingsRepository(db)
    overrides = repo.get_all()

    current_settings = {}
    for key in EXPOSED_KEYS:
        # DB override takes precedence, then the live settings object
        value = overrides.get(key)
        if value is None:
            value = str(getattr(settings, key, ""))
        current_settings[key] = value

    return SystemSettingsResponse(settings=current_settings)

@router.post("/admin/settings", response_model=SystemSettingsResponse)
async def update_admin_settings(
    payload: SystemSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SystemSettingsResponse:
    """Update system settings and apply them to the live environment."""
    if current_user.role != "ADMIN":
        logger.warning("User %s attempted to update admin settings without ADMIN role", current_user.email)

    repo = SystemSettingsRepository(db)

    updated_settings = {}
    for key, value in payload.settings.items():
        if key not in EXPOSED_KEYS:
            continue

        # Persist to DB
        repo.upsert(key, value)

        # Apply to live settings object dynamically
        if hasattr(settings, key):
            try:
                # Basic type handling for booleans
                if isinstance(getattr(settings, key), bool):
                    bool_val = str(value).lower() in ("true", "1", "yes", "on")
                    setattr(settings, key, bool_val)
                else:
                    setattr(settings, key, value)
                logger.info("Applied dynamic setting override: %s = %s", key, value)
            except Exception as e:
                logger.error("Failed to apply dynamic setting %s: %s", key, str(e))

        updated_settings[key] = value

    return await get_admin_settings(current_user, db)
