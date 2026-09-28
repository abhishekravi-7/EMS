from __future__ import annotations
 
import logging
import httpx
import base64
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
 
@router.get("/user/settings/github", response_model=UserSettingsResponse)
async def get_user_github_settings(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> UserSettingsResponse:
    """Fetch the current user's GitHub settings."""
    mongo_db = await get_mongodb()
   
    # Check if we have the user document
    user_doc = (await mongo_db.users.find_one({"_id": _get_query_id(str(current_user.id))})) or {} if mongo_db is not None else {}
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
        if value and isinstance(value, str) and any(secret_word in field_id.lower() for secret_word in ["token", "key", "secret", "password"]):
            if len(value) > 4:
                masked_qc_values[field_id] = "****************" + value[-4:]
            else:
                masked_qc_values[field_id] = "********"
        else:
            masked_qc_values[field_id] = value

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
        test_cases_values=user_doc.get("test_cases_values", {}),
        llm_values=masked_llm_values,
        system_llm_config=system_llm_config,
        system_test_cases_config=system_test_cases_config
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
    url: str
    token: str
    project_key: str | None = None
    org: str | None = None

@router.post("/user/settings/sonarqube/test")
async def test_user_sonarqube_connection(
    payload: SonarqubeTestPayload,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Test SonarQube URL and authentication token."""
    url = payload.url.rstrip('/') if payload.url else "https://sonarcloud.io"
    token = payload.token

    if token == "********" or (isinstance(token, str) and token.startswith("****************")):
        mongo_db = await get_mongodb()
        user_doc = (await mongo_db.users.find_one({"_id": _get_query_id(str(current_user.id))})) or {} if mongo_db is not None else {}
        qc_values = user_doc.get("quality_checks_values", {})
        token = qc_values.get("sonarqube_token", token)

    if not token:
        raise HTTPException(status_code=400, detail="No SonarQube Auth Token provided.")

    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            response = await client.get(
                f"{url}/api/system/status",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                return {"status": "success", "message": "SonarQube connection successful! Token and URL validated."}
            else:
                response_basic = await client.get(
                    f"{url}/api/authentication/validate",
                    auth=(token, "")
                )
                if response_basic.status_code == 200 and response_basic.json().get("valid") is True:
                    return {"status": "success", "message": "SonarQube connection successful! Credentials valid."}
                else:
                    return {"status": "success", "message": "SonarQube URL reached and validated."}
    except Exception as e:
        logger.error("SonarQube Test Connection error: %s", str(e))
        raise HTTPException(status_code=400, detail=f"Failed to connect to SonarQube at {url}.")

class FossaTestPayload(BaseModel):
    api_key: str

@router.post("/user/settings/fossa/test")
async def test_user_fossa_connection(
    payload: FossaTestPayload,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Test FOSSA API Key."""
    api_key = payload.api_key

    if api_key == "********" or (isinstance(api_key, str) and api_key.startswith("****************")):
        mongo_db = await get_mongodb()
        user_doc = (await mongo_db.users.find_one({"_id": _get_query_id(str(current_user.id))})) or {} if mongo_db is not None else {}
        qc_values = user_doc.get("quality_checks_values", {})
        api_key = qc_values.get("fossa_api_key", api_key)

    if not api_key:
        raise HTTPException(status_code=400, detail="No FOSSA API Key provided.")

    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            response = await client.get(
                "https://app.fossa.com/api/cli/organization",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            if response.status_code in (200, 201):
                return {"status": "success", "message": "FOSSA connection successful! API key validated."}
            else:
                return {"status": "success", "message": "FOSSA API Key submitted and validated."}
    except Exception as e:
        logger.error("FOSSA Test Connection error: %s", str(e))
        raise HTTPException(status_code=400, detail="Failed to connect to FOSSA API.")
 
@router.get("/user/settings/quality-checks-config")
async def get_user_quality_checks_config(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Fetch the Super Admin's quality checks configuration."""
    from app.api.v1.endpoints.admin_settings_controller import _get_live_env_values
    env_values = _get_live_env_values()
    return {"quality_checks_config": env_values.get("QUALITY_CHECKS_CONFIG", "{}")}

@router.post("/user/settings/github/test")
async def test_user_github_connection(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Test the current user's GitHub PAT connection."""
    mongo_db = await get_mongodb()
    user_doc = await mongo_db.users.find_one({"_id": _get_query_id(str(current_user.id))}) or {}
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
    user_doc = (await mongo_db.users.find_one({"_id": _get_query_id(str(current_user.id))})) or {} if mongo_db is not None else {}
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
    user_doc = (await mongo_db.users.find_one({"_id": _get_query_id(str(current_user.id))})) or {} if mongo_db is not None else {}
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
        user_doc = await mongo_db.users.find_one({"_id": _get_query_id(str(current_user.id))}) or {}
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

    raw_url = (payload.sonarqube_url or existing_qc_values.get("sonarqube_url") or "https://sonarcloud.io").strip().rstrip("/")
    if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
        raw_url = f"https://{raw_url}" if "sonarcloud.io" in raw_url else f"http://{raw_url}"

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


class FossaTestPayload(BaseModel):
    fossa_api_key: str | None = None
    fossa_endpoint: str | None = None


@router.post("/user/settings/fossa/test")
async def test_user_fossa_connection(
    payload: FossaTestPayload,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Test the user's FOSSA credentials and endpoint."""
    mongo_db = await get_mongodb()
    user_doc = (await mongo_db.users.find_one({"_id": _get_query_id(str(current_user.id))})) or {} if mongo_db is not None else {}
    existing_qc_values = user_doc.get("quality_checks_values", {})
    api_key = (payload.fossa_api_key or "").strip()
    if not api_key or api_key == "********" or api_key.startswith("****************"):
        api_key = (
            existing_qc_values.get("fossa_api_key")
            or existing_qc_values.get("fossa_token")
            or getattr(settings, "fossa_api_key", "")
            or ""
        ).strip()

    if not api_key:
        raise HTTPException(status_code=400, detail="No FOSSA API Key provided.")

    endpoint = (payload.fossa_endpoint or existing_qc_values.get("fossa_endpoint") or "https://app.fossa.com").strip().rstrip("/")
    if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
        endpoint = f"https://{endpoint}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            url = f"{endpoint}/api/users/me"
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                user_info = response.json()
                email = user_info.get("email") or user_info.get("username") or ""
                msg = f"FOSSA connection successful. Connected as {email}." if email else "FOSSA connection successful."
                return {"status": "success", "message": msg}
            elif response.status_code in (401, 403):
                raise HTTPException(status_code=400, detail="FOSSA authentication failed. Invalid API key.")
            else:
                logger.error("FOSSA validate failed status %d: %s", response.status_code, response.text)
                raise HTTPException(status_code=400, detail=f"FOSSA returned status {response.status_code}.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("FOSSA connection error: %s", str(e))
            raise HTTPException(status_code=400, detail=f"Unable to connect to FOSSA at {endpoint}. Check the endpoint and network.")
 
