from __future__ import annotations

import logging
from datetime import datetime, timezone
import httpx
import base64
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.api.deps import User
from app.schemas.user_settings_schema import UserSettingsResponse, UserSettingsUpdate, UserGitHubConfig
from app.infrastructure.persistence.mongodb import get_mongodb
from app.infrastructure.persistence.mongodb_user_repository import _get_query_id
from app.api.v1.endpoints.admin_settings_controller import _get_live_env_values
from app.core.config import settings

router = APIRouter(tags=["user-settings"])
logger = logging.getLogger(__name__)


async def _get_current_user_doc(mongo_db, current_user: User) -> dict:
    """Safely fetch user document by numeric ID, string ID, ObjectId, or email."""
    if mongo_db is None or not current_user:
        return {}

    user_id = str(current_user.id)
    # Check numeric ID
    if user_id.isdigit():
        doc = await mongo_db.users.find_one({"_id": int(user_id)})
        if doc:
            return doc

    # Check string ID
    doc = await mongo_db.users.find_one({"_id": user_id})
    if doc:
        return doc

    # Check ObjectId if valid
    if ObjectId.is_valid(user_id):
        doc = await mongo_db.users.find_one({"_id": ObjectId(user_id)})
        if doc:
            return doc

    # Fallback: check by email
    email = getattr(current_user, "email", None)
    if email and isinstance(email, str):
        doc = await mongo_db.users.find_one({"email": email.strip().lower()})
        if doc:
            return doc

    return {}


@router.get("/user/settings/github", response_model=UserSettingsResponse)
async def get_user_github_settings(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> UserSettingsResponse:
    """Fetch the current user's GitHub settings."""
    mongo_db = await get_mongodb()

    # Check if we have the user document
    user_doc = await _get_current_user_doc(mongo_db, current_user)
    github_config = user_doc.get("github_config", user_doc.get("git_config", {}))

    # Mask the PAT if it exists
    pat = github_config.get("pat")
    if pat:
        if len(pat) > 4:
            masked_pat = "****************" + pat[-4:]
        else:
            masked_pat = "********"
    else:
        masked_pat = ""

    # Top-level github_account (set during OAuth) takes precedence if not inside config yet
    github_account = github_config.get("github_account") or user_doc.get("github_account") or ""

    # Process quality_checks_values and mask secrets
    quality_checks_values = user_doc.get("quality_checks_values", {})
    masked_qc_values = {}
    for field_id, value in quality_checks_values.items():
        if field_id in ("sonarqube_project_key", "project_key", "sonarqube_url", "sonarqube_org", "sonar_organization"):
            masked_qc_values[field_id] = value
        elif value and isinstance(value, str) and (
            any(secret_word in field_id.lower() for secret_word in ["token", "secret", "password"])
            or (field_id.endswith("api_key") and "project" not in field_id.lower())
        ):
            if len(value) > 4:
                masked_qc_values[field_id] = "****************" + value[-4:]
            else:
                masked_qc_values[field_id] = "********"
        else:
            masked_qc_values[field_id] = value
    masked_qc_values["sonarqube_url"] = "https://sonarcloud.io"

    # Process llm_values and mask the api_keys
    llm_values = user_doc.get("llm_values", {})
    masked_llm_values = {}
    for k, v in llm_values.items():
        if k.endswith("api_key") and v:
            if len(v) > 4:
                masked_llm_values[k] = "****************" + v[-4:]
            else:
                masked_llm_values[k] = "********"
        else:
            masked_llm_values[k] = v

    from app.infrastructure.persistence.mongodb_system_settings_repository import get_all_settings as get_mongo_settings
    db_settings = await get_mongo_settings(mongo_db) if mongo_db is not None else {}
    env_values = _get_live_env_values()

    def get_system_setting(key: str, default: str) -> str:
        if key in db_settings and db_settings[key] is not None:
            return str(db_settings[key])
        val = env_values.get(key.upper())
        return str(val) if val is not None else default

    system_llm_config = {
        "llm_enabled": get_system_setting("llm_enabled", "false"),
        "groq_models": get_system_setting("groq_models", "[]"),
        "huggingface_models": get_system_setting("huggingface_models", "[]"),
    }

    system_test_cases_config = {
        "test_cases_playwright_enabled": get_system_setting("test_cases_playwright_enabled", "false"),
        "test_cases_cypress_enabled": get_system_setting("test_cases_cypress_enabled", "false"),
        "test_cases_selenium_enabled": get_system_setting("test_cases_selenium_enabled", "false"),
    }

    raw_tc_values = user_doc.get("test_cases_values", {}) or {}
    raw_qc_values = user_doc.get("quality_checks_values", {}) or {}

    effective_tc_values = dict(raw_tc_values)
    # Safe backward-compatibility fallback: read test_cases_values first, fall back to quality_checks_values
    if "selected_predefined_prompts" not in effective_tc_values:
        if "selected_predefined_prompts" in raw_qc_values:
            effective_tc_values["selected_predefined_prompts"] = raw_qc_values["selected_predefined_prompts"]
        elif "selectedPredefinedPrompts" in raw_qc_values:
            effective_tc_values["selected_predefined_prompts"] = raw_qc_values["selectedPredefinedPrompts"]

    if "testing_prompt" not in effective_tc_values:
        if "testing_prompt" in raw_qc_values:
            effective_tc_values["testing_prompt"] = raw_qc_values["testing_prompt"]
        elif "testingPrompt" in raw_qc_values:
            effective_tc_values["testing_prompt"] = raw_qc_values["testingPrompt"]
        elif "junit_prompt" in raw_qc_values:
            effective_tc_values["testing_prompt"] = raw_qc_values["junit_prompt"]
        elif "junitPrompt" in raw_qc_values:
            effective_tc_values["testing_prompt"] = raw_qc_values["junitPrompt"]

    from app.infrastructure.persistence.mongodb_user_repository import normalize_permissions
    user_perms = normalize_permissions(user_doc.get("settings_permissions"))

    is_admin = (
        getattr(current_user, "role", "").upper() in ("ADMIN", "SUPERADMIN") or
        getattr(current_user, "is_admin", False) is True
    )

    global_llm = str(get_system_setting("llm_enabled", "true")).strip().lower() not in ("false", "0", "disabled", "off")
    global_qc_cfg = str(get_system_setting("quality_checks_config", "enabled")).strip().lower() != "disabled"
    global_ci = str(get_system_setting("ci_enabled", "true")).strip().lower() not in ("false", "0", "off")
    global_cd = str(get_system_setting("cd_enabled", "true")).strip().lower() not in ("false", "0", "off")
    global_qc = global_qc_cfg and (global_ci or global_cd)
    global_unit = global_qc_cfg and global_ci

    global_playwright = str(get_system_setting("test_cases_playwright_enabled", "true")).strip().lower() not in ("false", "0", "off")
    global_cypress = str(get_system_setting("test_cases_cypress_enabled", "true")).strip().lower() not in ("false", "0", "off")
    global_selenium = str(get_system_setting("test_cases_selenium_enabled", "true")).strip().lower() not in ("false", "0", "off")
    global_functional = global_playwright or global_cypress or global_selenium

    global_brd = True
    global_test_conn = True

    if is_admin:
        effective_permissions = {
            "llm_settings": global_llm,
            "quality_checks": global_qc,
            "unit_testing": global_unit,
            "functional_testing": global_functional,
            "brd_testing": global_brd,
            "test_connection": global_test_conn,
        }
    else:
        effective_permissions = {
            "llm_settings": bool(global_llm and user_perms.get("llm_settings", True)),
            "quality_checks": bool(global_qc and user_perms.get("quality_checks", True)),
            "unit_testing": bool(global_unit and user_perms.get("unit_testing", True)),
            "functional_testing": bool(global_functional and user_perms.get("functional_testing", True)),
            "brd_testing": bool(global_brd and user_perms.get("brd_testing", True)),
            "test_connection": bool(global_test_conn and user_perms.get("test_connection", True)),
        }

    if not effective_permissions.get("llm_settings", True):
        system_llm_config["llm_enabled"] = "false"

    if not effective_permissions.get("functional_testing", True):
        system_test_cases_config["test_cases_playwright_enabled"] = "false"
        system_test_cases_config["test_cases_cypress_enabled"] = "false"
        system_test_cases_config["test_cases_selenium_enabled"] = "false"

    return UserSettingsResponse(
        github_config=UserGitHubConfig(
            github_account=github_account,
            pat=masked_pat,
            pat_scope=github_config.get("pat_scope", ""),
            repository=github_config.get("repository", ""),
            branch=github_config.get("branch", ""),
            user_access=github_config.get("user_access", "")
        ),
        quality_checks_values=masked_qc_values,
        test_cases_values=effective_tc_values,
        llm_values=masked_llm_values,
        system_llm_config=system_llm_config,
        system_test_cases_config=system_test_cases_config,
        settings_permissions=effective_permissions
    )

@router.post("/user/settings/github", response_model=UserSettingsResponse)
async def update_user_github_settings(
    payload: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> UserSettingsResponse:
    """Update the current user's GitHub settings."""
    mongo_db = await get_mongodb()
    
    # Fetch existing to avoid overwriting existing fields or masked secrets
    user_doc = (await mongo_db.users.find_one({"_id": _get_query_id(str(current_user.id))})) or {} if mongo_db is not None else {}
    existing_config = user_doc.get("github_config", user_doc.get("git_config", {}))
    existing_qc_values = user_doc.get("quality_checks_values", {})
    existing_tc_values = user_doc.get("test_cases_values", {})
    existing_llm_values = user_doc.get("llm_values", {})
    
    incoming_config = payload.github_config.model_dump(exclude_unset=True) if payload.github_config else {}
    merged_config = {**existing_config, **incoming_config}
    pat_val = merged_config.get("pat")
    if pat_val == "********" or (isinstance(pat_val, str) and pat_val.startswith("****************")):
        merged_config["pat"] = existing_config.get("pat")
        
    incoming_qc_values = payload.quality_checks_values or {}
    merged_qc_values = dict(existing_qc_values)
    for field_id, value in incoming_qc_values.items():
        if value == "********" or (isinstance(value, str) and value.startswith("****************")):
            merged_qc_values[field_id] = existing_qc_values.get(field_id, value)
        else:
            merged_qc_values[field_id] = value
    merged_qc_values["sonarqube_url"] = "https://sonarcloud.io"

    # Canonical storage: remove JUnit testing settings from quality_checks_values on new saves
    merged_qc_values.pop("selected_predefined_prompts", None)
    merged_qc_values.pop("selectedPredefinedPrompts", None)
    merged_qc_values.pop("testing_prompt", None)
    merged_qc_values.pop("testingPrompt", None)
    merged_qc_values.pop("junit_prompt", None)
    merged_qc_values.pop("junitPrompt", None)
        
    incoming_tc_values = payload.test_cases_values or {}
    merged_tc_values = {**existing_tc_values, **incoming_tc_values}

    incoming_llm_values = payload.llm_values or {}
    merged_llm_values = dict(existing_llm_values)
    for k, v in incoming_llm_values.items():
        if v == "********" or (isinstance(v, str) and v.startswith("****************")):
            merged_llm_values[k] = existing_llm_values.get(k, v)
        else:
            merged_llm_values[k] = v

    if mongo_db is not None:
        await mongo_db.users.update_one(
            {"_id": _get_query_id(str(current_user.id))},
            {"$set": {
                "github_config": merged_config,
                "quality_checks_values": merged_qc_values,
                "test_cases_values": merged_tc_values,
                "llm_values": merged_llm_values
            }},
            upsert=True
        )
    
    return await get_user_github_settings(current_user)

class SonarqubeTestPayload(BaseModel):
    url: str | None = None
    token: str
    project_key: str | None = None
    org: str | None = None

@router.post("/user/settings/sonarqube/test")
async def test_user_sonarqube_connection(
    payload: SonarqubeTestPayload,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Test SonarQube URL and authentication token."""
    url = (getattr(settings, "sonarqube_host_url", None) or "https://sonarcloud.io").rstrip("/")
    token = (payload.token or "").strip()

    if token == "********" or (isinstance(token, str) and token.startswith("****************")):
        mongo_db = await get_mongodb()
        user_doc = (await _get_current_user_doc(mongo_db, current_user))
        qc_values = user_doc.get("quality_checks_values", {})
        token = qc_values.get("sonarqube_token", token)
        if not token or (isinstance(token, str) and token.startswith("****************")):
            token = _get_live_env_values().get("SONARQUBE_TOKEN") or getattr(settings, "sonarqube_token", "")

    token = (token or "").strip()
    if not token or (isinstance(token, str) and (token.startswith("****************") or token == "********")):
        raise HTTPException(status_code=400, detail="No SonarQube Auth Token provided.")

    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            is_valid_token = False

            # Check 1: /api/authentication/validate with Basic Auth
            r_val = await client.get(f"{url}/api/authentication/validate", auth=(token, ""))
            if r_val.status_code == 200 and r_val.json().get("valid") is True:
                is_valid_token = True
            else:
                # Check 2: /api/users/current with Basic Auth
                r_usr = await client.get(f"{url}/api/users/current", auth=(token, ""))
                if r_usr.status_code == 200 and r_usr.json().get("isLoggedIn") is True:
                    is_valid_token = True
                else:
                    # Check 3: /api/user_tokens/search with Basic Auth
                    r_tok = await client.get(f"{url}/api/user_tokens/search", auth=(token, ""))
                    if r_tok.status_code == 200:
                        is_valid_token = True
                    else:
                        # Check 4: Bearer header fallback
                        r_bearer = await client.get(f"{url}/api/authentication/validate", headers={"Authorization": f"Bearer {token}"})
                        if r_bearer.status_code == 200 and r_bearer.json().get("valid") is True:
                            is_valid_token = True
                        else:
                            r_usr_bearer = await client.get(f"{url}/api/users/current", headers={"Authorization": f"Bearer {token}"})
                            if r_usr_bearer.status_code == 200 and r_usr_bearer.json().get("isLoggedIn") is True:
                                is_valid_token = True

            # If organization is provided, sanitize and verify
            org_cleaned = (payload.org or "").strip()
            if org_cleaned:
                if "sonarcloud.io" in org_cleaned:
                    import urllib.parse
                    parsed = urllib.parse.urlparse(org_cleaned)
                    qs = urllib.parse.parse_qs(parsed.query)
                    if "organization" in qs:
                        org_cleaned = qs["organization"][0]
                    elif "/organizations/" in parsed.path:
                        org_cleaned = parsed.path.split("/organizations/")[-1].split("/")[0]
                org_cleaned = org_cleaned.strip("@/ ")

            # If token wasn't confirmed yet and org is provided, try project search with auth
            if not is_valid_token and org_cleaned:
                r_proj = await client.get(f"{url}/api/projects/search", params={"organization": org_cleaned.lower()}, auth=(token, ""))
                if r_proj.status_code == 200:
                    is_valid_token = True

            if not is_valid_token:
                raise HTTPException(status_code=400, detail="Invalid SonarQube authentication token.")

            if org_cleaned:
                orgs_to_search = list(dict.fromkeys([org_cleaned, org_cleaned.lower()]))
                org_res = await client.get(
                    f"{url}/api/organizations/search",
                    params={"organizations": ",".join(orgs_to_search)},
                    auth=(token, "")
                )
                if org_res.status_code == 200:
                    orgs = org_res.json().get("organizations", [])
                    if not orgs:
                        raise HTTPException(status_code=400, detail=f"Sonar organization '{org_cleaned}' was not found on SonarCloud.")

            return {"status": "success", "valid": True, "message": "SonarQube connection successful! Configuration is valid."}
    except HTTPException:
        raise
    except httpx.RequestError as exc:
        logger.error("SonarQube Test Connection network error: %s", str(exc))
        raise HTTPException(status_code=502, detail="Unable to connect to SonarQube.")
    except Exception as e:
        logger.error("SonarQube Test Connection error: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to connect to SonarQube at {url}.")

class FossaTestPayload(BaseModel):
    api_key: str | None = None
    fossa_api_key: str | None = None

@router.post("/user/settings/fossa/test")
async def test_user_fossa_connection(
    payload: FossaTestPayload,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Test FOSSA API Key against FOSSA API."""
    api_key = payload.api_key or payload.fossa_api_key
    mongo_db = await get_mongodb()
    user_doc = (await mongo_db.users.find_one({"_id": _get_query_id(str(current_user.id))})) or {} if mongo_db is not None else {}
    qc_values = user_doc.get("quality_checks_values", {})

    if api_key == "********" or (isinstance(api_key, str) and api_key.startswith("****************")):
        mongo_db = await get_mongodb()
        user_doc = (await _get_current_user_doc(mongo_db, current_user))
        qc_values = user_doc.get("quality_checks_values", {})
        api_key = qc_values.get("fossa_api_key", api_key)
        if not api_key or (isinstance(api_key, str) and api_key.startswith("****************")):
            api_key = _get_live_env_values().get("FOSSA_API_KEY") or getattr(settings, "fossa_api_key", "")

    if not api_key or (isinstance(api_key, str) and api_key.startswith("****************")):
        raise HTTPException(status_code=400, detail="No FOSSA API Key provided.")

    import httpx
    fossa_endpoints = [
        "https://app.fossa.com/api/cli/organization",
        "https://app.fossa.com/api/users/me",
        "https://app.fossa.com/api/projects",
    ]
    
    last_status = None
    last_error_detail = None

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            response = await client.get(
                "https://app.fossa.com/api/cli/organization",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            if response.status_code in (200, 201):
                return {"status": "success", "valid": True, "message": "FOSSA connection successful! API key validated."}
            elif response.status_code in (401, 403):
                raise HTTPException(status_code=400, detail="Invalid FOSSA API key.")
            else:
                raise HTTPException(status_code=400, detail=f"FOSSA API returned status {response.status_code}.")
    except HTTPException:
        raise
    except httpx.RequestError as exc:
        logger.error("FOSSA Test Connection network error: %s", str(exc))
        raise HTTPException(status_code=502, detail="Unable to connect to FOSSA API server.")
    except Exception as e:
        logger.error("FOSSA Test Connection error: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to test FOSSA connection.")
 
@router.get("/user/settings/quality-checks-config")
async def get_user_quality_checks_config(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Fetch the Super Admin's quality checks configuration."""
    from app.infrastructure.quality_gates.cycode_config import quality_checks_config
    from app.infrastructure.persistence.mongodb_system_settings_repository import get_all_settings

    mongo_db = await get_mongodb()
    system_settings = await get_all_settings(mongo_db) if mongo_db is not None else {}

    raw_qc = system_settings.get("quality_checks_config")
    if not raw_qc:
        from app.api.v1.endpoints.admin_settings_controller import _get_live_env_values
        raw_qc = _get_live_env_values().get("QUALITY_CHECKS_CONFIG")

    def enabled(name: str) -> bool:
        value = system_settings.get(name)
        if value is None:
            value = _get_live_env_values().get(name.upper())
        return str(value if value is not None else "true").strip().lower() in {"1", "true", "yes", "on"}

    qc_res = quality_checks_config(raw_qc)
    migration_logger = logging.getLogger("migration")
    migration_logger.info(
        "[MIGRATION QUALITY GATES FETCH] - SonarQube: %s - FOSSA: %s - Cycode: %s - RunUnitTestSuite: %s - FunctionalTesting: %s",
        "Enabled" if qc_res.get("sonarqube", {}).get("enabled", True) else "Disabled",
        "Configured" if qc_res.get("fossa", {}).get("configured", False) else "Not Configured",
        "Configured" if qc_res.get("cycode", {}).get("configured", False) else "Not Configured",
        "Enabled" if qc_res.get("unit_tests", {}).get("enabled", True) else "Disabled",
        "Enabled" if qc_res.get("functional_testing", {}).get("enabled", True) else "Disabled",
    )

    return {
        "quality_checks_config": qc_res,
        "ci_enabled": enabled("ci_enabled"),
        "cd_enabled": enabled("cd_enabled"),
    }


@router.get("/user/me/settings-permissions")
async def get_my_settings_permissions(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Fetch the effective settings permissions for the currently authenticated user."""
    mongo_db = await get_mongodb()
    user_doc = await _get_current_user_doc(mongo_db, current_user)

    from app.infrastructure.persistence.mongodb_user_repository import normalize_permissions
    user_perms = normalize_permissions(user_doc.get("settings_permissions"))

    from app.infrastructure.persistence.mongodb_system_settings_repository import get_all_settings as get_mongo_settings
    db_settings = await get_mongo_settings(mongo_db) if mongo_db is not None else {}
    env_values = _get_live_env_values()

    def get_sys_bool(key: str, default_val: bool = True) -> bool:
        val = db_settings.get(key)
        if val is None:
            val = env_values.get(key.upper())
        if val is None:
            return default_val
        return str(val).strip().lower() in {"1", "true", "yes", "on"}

    global_llm = get_sys_bool("llm_enabled", True)
    global_qc_cfg = str(db_settings.get("quality_checks_config", env_values.get("QUALITY_CHECKS_CONFIG", "enabled"))).strip().lower() != "disabled"
    global_ci = get_sys_bool("ci_enabled", True)
    global_cd = get_sys_bool("cd_enabled", True)
    global_qc = global_qc_cfg and (global_ci or global_cd)
    global_unit = global_qc_cfg and global_ci

    global_playwright = get_sys_bool("test_cases_playwright_enabled", True)
    global_cypress = get_sys_bool("test_cases_cypress_enabled", True)
    global_selenium = get_sys_bool("test_cases_selenium_enabled", True)
    global_functional = global_playwright or global_cypress or global_selenium

    global_brd = True
    global_test_conn = True

    is_admin = current_user.role in ("SUPERADMIN", "ADMIN", "admin") or getattr(current_user, "is_admin", False)

    if is_admin:
        effective = {
            "llm_settings": global_llm,
            "quality_checks": global_qc,
            "unit_testing": global_unit,
            "functional_testing": global_functional,
            "brd_testing": global_brd,
            "test_connection": global_test_conn,
        }
    else:
        effective = {
            "llm_settings": bool(global_llm and user_perms.get("llm_settings", True)),
            "quality_checks": bool(global_qc and user_perms.get("quality_checks", True)),
            "unit_testing": bool(global_unit and user_perms.get("unit_testing", True)),
            "functional_testing": bool(global_functional and user_perms.get("functional_testing", True)),
            "brd_testing": bool(global_brd and user_perms.get("brd_testing", True)),
            "test_connection": bool(global_test_conn and user_perms.get("test_connection", True)),
        }

    return {
        "status": "success",
        "user_id": str(user_doc.get("_id") or current_user.id),
        "role": current_user.role,
        "permissions": user_perms,
        "user_permissions": user_perms,
        "effective": effective,
        "effective_permissions": effective,
    }

@router.post("/user/settings/github/test")
async def test_user_github_connection(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Test the current user's GitHub PAT connection."""
    mongo_db = await get_mongodb()
    user_doc = await _get_current_user_doc(mongo_db, current_user)
    github_config = user_doc.get("github_config", {})
    pat = github_config.get("pat")

    if not pat:
        raise HTTPException(status_code=400, detail="No Personal Access Token configured.")

    async with httpx.AsyncClient(timeout=10.0) as client:
        base_url = settings.github_api_base_url.rstrip('/')
        response = await client.get(
            f"{base_url}/user",
            headers={"Authorization": f"Bearer {pat}"}
        )
        if response.status_code == 200:
            return {"status": "success", "message": "GitHub connection successful."}
        else:
            logger.error("GitHub Test Connection failed: %s", response.text)
            raise HTTPException(
                status_code=400,
                detail="Unable to connect to GitHub. Please verify your credentials and configuration."
            )

@router.get("/user/settings/github/repos")
async def list_user_github_repos(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """List the repositories available to the current user via their PAT or system PAT."""
    mongo_db = await get_mongodb()
    user_doc = await _get_current_user_doc(mongo_db, current_user)
    github_config = user_doc.get("github_config", {})
    pat = github_config.get("pat")

    if not pat or pat.startswith("****"):
        from app.api.v1.endpoints.admin_settings_controller import _get_live_env_values
        env_values = _get_live_env_values()
        pat = getattr(settings, "github_target_token", None) or getattr(settings, "github_token", None) or env_values.get("GITHUB_TARGET_TOKEN") or env_values.get("GITHUB_TOKEN")

    if not pat:
        raise HTTPException(status_code=400, detail="No Personal Access Token configured.")

    async with httpx.AsyncClient(timeout=10.0) as client:
        base_url = settings.github_api_base_url.rstrip('/')
        response = await client.get(
            f"{base_url}/user/repos?per_page=100&sort=updated",
            headers={"Authorization": f"Bearer {pat}"}
        )
        if response.status_code == 200:
            repos = response.json()
            return [
                {
                    "id": repo["id"],
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "owner": repo["owner"]["login"],
                    "private": repo["private"],
                }
                for repo in repos
            ]
        else:
            logger.error("GitHub Fetch Repos failed: %s", response.text)
            raise HTTPException(
                status_code=400,
                detail="Unable to fetch repositories from GitHub."
            )

@router.get("/user/settings/github/repos/{owner}/{repo}/branches")
async def list_github_repo_branches(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """List the branches for a specific repository."""
    mongo_db = await get_mongodb()
    user_doc = await _get_current_user_doc(mongo_db, current_user)
    github_config = user_doc.get("github_config", {})
    pat = github_config.get("pat")

    if not pat or pat.startswith("****"):
        from app.api.v1.endpoints.admin_settings_controller import _get_live_env_values
        env_values = _get_live_env_values()
        pat = getattr(settings, "github_target_token", None) or getattr(settings, "github_token", None) or env_values.get("GITHUB_TARGET_TOKEN") or env_values.get("GITHUB_TOKEN")

    if not pat:
        raise HTTPException(status_code=400, detail="No Personal Access Token configured.")

    async with httpx.AsyncClient(timeout=10.0) as client:
        base_url = settings.github_api_base_url.rstrip('/')
        response = await client.get(
            f"{base_url}/repos/{owner}/{repo}/branches?per_page=100",
            headers={"Authorization": f"Bearer {pat}"}
        )
        if response.status_code == 200:
            branches = response.json()
            return [{"name": branch["name"]} for branch in branches]
        else:
            logger.error("GitHub Fetch Branches failed: %s", response.text)
            raise HTTPException(
                status_code=400,
                detail=f"Unable to fetch branches for {owner}/{repo}."
            )

class PlaywrightTestPayload(BaseModel):
    base_url: str

@router.post("/user/settings/test-cases/playwright/test")
async def test_user_playwright_connection(
    payload: PlaywrightTestPayload,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Test the user's Playwright connection to their application URL."""
    # We verify that we can reach the base_url
    base_url = payload.base_url
    if not base_url:
        raise HTTPException(status_code=400, detail="No Application / Base URL provided.")

    if not base_url.startswith("http"):
        base_url = "http://" + base_url

    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            response = await client.get(base_url)
            if response.status_code < 500:
                # Even a 404 or 401 might mean the application is running but we hit a protected route.
                # We consider it a successful connection to the server.
                return {"status": "success", "message": "Playwright test connection successful"}
            else:
                logger.error("User Playwright Test Connection failed with status %d", response.status_code)
                raise HTTPException(
                    status_code=400,
                    detail=f"Playwright test connection failed. Server returned status {response.status_code}."
                )
    except Exception as e:
        logger.error("User Playwright Test Connection encountered an error: %s", str(e))
        raise HTTPException(status_code=400, detail="Playwright test connection failed. Unable to reach the Application / Base URL.")

class LlmTestPayload(BaseModel):
    provider: str
    api_key: str
    selected_model: str

@router.post("/user/settings/llm/test")
async def test_user_llm_connection(
    payload: LlmTestPayload,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Test the user's LLM connection."""
    provider = payload.provider.lower()
    api_key = payload.api_key
    selected_model = payload.selected_model

    if api_key == "********" or api_key.startswith("****************"):
        # The user submitted the masked API key, fetch real one
        mongo_db = await get_mongodb()
        user_doc = await _get_current_user_doc(mongo_db, current_user)
        existing_llm_values = user_doc.get("llm_values", {})
        api_key = existing_llm_values.get(f"{provider}_api_key", api_key)

    if not api_key:
        raise HTTPException(status_code=400, detail="No API Key provided.")

    # Since we can't do a full LLM instantiation and test generation cleanly without
    # hitting actual usage limits, we will do a basic HTTP request to the provider's /models or /chat/completions
    # to verify credentials.
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if provider == "groq":
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
            elif provider == "huggingface":
                response = await client.get(
                    "https://huggingface.co/api/whoami-v2",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
            elif provider == "ollama":
                # Ollama typically doesn't need an API key but we can just check models endpoint
                response = await client.get(
                    "http://localhost:11434/api/tags"
                )
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

            if response.status_code == 200:
                return {"status": "success", "message": "LLM connection successful."}
            else:
                logger.error("LLM Test Connection failed with status %d: %s", response.status_code, response.text)
                raise HTTPException(
                    status_code=400,
                    detail="LLM connection failed. Please check your credentials."
                )
    except Exception as e:
        logger.error("LLM Test Connection encountered an error: %s", str(e))
        raise HTTPException(status_code=400, detail="LLM connection failed. Unable to reach the provider.")


class SonarTestPayload(BaseModel):
    sonarqube_url: str | None = None
    auth_token: str | None = None
    project_key: str | None = None
    sonar_organization: str | None = None
 
 
@router.post("/user/settings/sonar/test")
async def test_user_sonar_connection(
    payload: SonarTestPayload,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Test the user's SonarQube credentials and URL."""
    mongo_db = await get_mongodb()
    user_doc = (await mongo_db.users.find_one({"_id": _get_query_id(str(current_user.id))})) or {} if mongo_db is not None else {}
    existing_qc_values = user_doc.get("quality_checks_values", {})
 
    token = (payload.auth_token or "").strip()
    if not token or token == "********" or token.startswith("****************"):
        token = (
            existing_qc_values.get("auth_token")
            or existing_qc_values.get("sonar_token")
            or getattr(settings, "sonar_token", "")
            or getattr(settings, "sonarqube_token", "")
            or ""
        ).strip()
 
    if not token:
        raise HTTPException(status_code=400, detail="No SonarQube authentication token provided.")
 
    raw_url = (getattr(settings, "sonarqube_host_url", None) or "https://sonarcloud.io").strip().rstrip("/")
    if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
        raw_url = f"https://{raw_url}"
 
    auth_b64 = base64.b64encode(f"{token}:".encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Accept": "application/json",
        "User-Agent": "Java-APEX-Platform/1.0",
    }
 
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            val_url = f"{raw_url}/api/authentication/validate"
            response = await client.get(val_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if data.get("valid") is True:
                    return {"status": "success", "message": "SonarQube connection successful. Token is valid."}
                else:
                    raise HTTPException(status_code=400, detail="SonarQube token is invalid.")
            elif response.status_code in (401, 403):
                raise HTTPException(status_code=400, detail="SonarQube authentication failed. Invalid token.")
            else:
                logger.error("SonarQube validate failed status %d: %s", response.status_code, response.text)
                raise HTTPException(status_code=400, detail=f"SonarQube returned status {response.status_code}.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("SonarQube connection error: %s", str(e))
            raise HTTPException(status_code=400, detail=f"Unable to connect to SonarQube at {raw_url}. Check the URL and network.")



 
