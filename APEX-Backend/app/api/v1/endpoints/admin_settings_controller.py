from __future__ import annotations

import logging
from pathlib import Path

import dotenv
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.infrastructure.persistence.models import User
from app.schemas.system_settings_schema import SystemSettingsResponse, SystemSettingsUpdate

router = APIRouter(tags=["admin-settings"])
logger = logging.getLogger(__name__)

# The specific subset of configuration keys exposed to the Admin Console.
EXPOSED_KEYS = {
    "github_client_id",
    "github_client_secret",
    "github_redirect_uri",
    "github_target_owner",
    "github_default_branch",
    "ollama_base_url",
    "rag_enabled",
    "sonarqube_host_url",
    "sonarqube_token",
    "fossa_api_key",
    "database_url",
    "jwt_secret_key",
    "quality_checks_config",
    "test_cases_playwright_enabled",
    "test_cases_playwright_command",
    "llm_enabled",
    "llm_features",
    "groq_models",
    "huggingface_models",
}

ENV_PATH = Path(".env").resolve()

def _get_live_env_values() -> dict:
    """Reads latest values directly from .env file to ensure dynamic syncing."""
    return dotenv.dotenv_values(ENV_PATH)

def _update_env_value(key: str, value: str) -> None:
    """Writes a value back to the .env file."""
    # python-dotenv expects uppercase keys like GITHUB_CLIENT_ID
    dotenv.set_key(ENV_PATH, key.upper(), str(value), quote_mode="always")

@router.get("/admin/settings", response_model=SystemSettingsResponse)
async def get_admin_settings(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> SystemSettingsResponse:
    """Fetch the current effective system settings."""
    if current_user.role not in ("SUPERADMIN",):
        logger.warning("User %s attempted to access admin settings without SUPERADMIN role", current_user.email)
        raise HTTPException(status_code=403, detail="Forbidden")

    env_values = _get_live_env_values()

    current_settings = {}
    for key in EXPOSED_KEYS:
        # DB override takes precedence, then the live settings object
        value = env_values.get(key.upper())
        if value is None:
            value = str(getattr(settings, key, ""))
            
        # Let the UI handle masking via type="password"
        # We want the Super Admin to see the actual token when they click the eye icon.
        current_settings[key] = value

    return SystemSettingsResponse(settings=current_settings)

@router.post("/admin/settings", response_model=SystemSettingsResponse)
async def update_admin_settings(
    payload: SystemSettingsUpdate,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> SystemSettingsResponse:
    """Update system settings and apply them to the live environment."""
    if current_user.role not in ("SUPERADMIN",):
        logger.warning("User %s attempted to update admin settings without SUPERADMIN role", current_user.email)
        raise HTTPException(status_code=403, detail="Forbidden")

    for key, value in payload.settings.items():
        if key not in EXPOSED_KEYS:
            continue

        _update_env_value(key, value)

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
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to apply dynamic setting %s: %s", key, str(e))

    return await get_admin_settings(current_user)

@router.post("/admin/settings/github/test")
async def test_admin_github_connection(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Test the admin's GitHub connection."""
    if current_user.role not in ("SUPERADMIN",):
        raise HTTPException(status_code=403, detail="Forbidden")

    env_values = _get_live_env_values()
    client_id = env_values.get("GITHUB_CLIENT_ID")
    client_secret = env_values.get("GITHUB_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="No valid GitHub Client ID or Secret configured.")
        
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.github.com/applications/{client_id}/token",
                auth=(client_id, client_secret),
                json={"access_token": "dummy"},
                headers={"Accept": "application/vnd.github.v3+json"}
            )
            # 404 means credentials are correct, but the dummy token was not found
            # 401 means credentials (client_id/client_secret) are invalid
            if response.status_code == 404:
                return {"status": "success", "message": "GitHub connection successful. Client credentials are valid."}
            else:
                logger.error("Admin GitHub Test Connection failed with status %d: %s", response.status_code, response.text)
                raise HTTPException(
                    status_code=400, 
                    detail="Invalid GitHub Client ID or Secret."
                )
    except Exception as e:
        logger.error("Admin GitHub Test Connection encountered an error: %s", str(e))
        raise HTTPException(status_code=500, detail="Unable to reach GitHub. Please check your network connection.")

@router.post("/admin/settings/test-cases/playwright/test")
async def test_admin_playwright_connection(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Test the admin's Playwright command/configuration."""
    if current_user.role not in ("ADMIN", "SUPERADMIN"):
        raise HTTPException(status_code=403, detail="Forbidden")

    import subprocess
    import shlex
    
    env_values = _get_live_env_values()
    # The frontend only allows this if enabled, but we can test anyway
    command = env_values.get("TEST_CASES_PLAYWRIGHT_COMMAND", "npx playwright test")
    
    if not command:
        raise HTTPException(status_code=400, detail="No Playwright command configured.")
        
    try:
        # Run the command with --help to see if the executable exists
        # Alternatively, we just check if we can run it
        cmd_parts = shlex.split(command)
        # If it's `npx playwright test`, let's just append `--help` so it doesn't fail on no tests
        cmd_parts.append("--help")
        
        result = subprocess.run(
            cmd_parts,
            capture_output=True,
            text=True,
            timeout=10.0,
            shell=True
        )
        
        if result.returncode == 0:
            return {"status": "success", "message": "Playwright connection/configuration successful."}
        else:
            logger.error("Playwright Test Connection failed. Code: %s, Error: %s", result.returncode, result.stderr)
            raise HTTPException(
                status_code=400, 
                detail="Playwright configuration failed. Please verify the command."
            )
    except FileNotFoundError:
        logger.error("Playwright executable not found: %s", command)
        raise HTTPException(status_code=400, detail="Playwright command not found. Ensure it is installed on the server.")
    except Exception as e:
        logger.error("Playwright Test Connection encountered an error: %s", str(e))
        raise HTTPException(status_code=500, detail="An error occurred while testing Playwright configuration.")
