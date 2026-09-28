from __future__ import annotations
 
import logging
import httpx
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
    
    # Fetch existing to avoid overwriting masked PAT with "********"
    user_doc = (await mongo_db.users.find_one({"_id": _get_query_id(str(current_user.id))})) or {} if mongo_db is not None else {}
    existing_config = user_doc.get("github_config", user_doc.get("git_config", {}))
    existing_qc_values = user_doc.get("quality_checks_values", {})
    
    new_config = payload.github_config.model_dump(exclude_unset=True)
    pat_val = new_config.get("pat")
    if pat_val == "********" or (pat_val and pat_val.startswith("****************")):
        new_config["pat"] = existing_config.get("pat")
        
    new_qc_values = payload.quality_checks_values or {}
    # Restore existing secrets if they come back masked
    for field_id, value in new_qc_values.items():
        if field_id in existing_qc_values:
            if value == "********" or (isinstance(value, str) and value.startswith("****************")):
                new_qc_values[field_id] = existing_qc_values.get(field_id, value)
        
    new_llm_values = payload.llm_values or {}
    existing_llm_values = user_doc.get("llm_values", {})
    for k in list(new_llm_values.keys()):
        if k.endswith("api_key"):
            val = new_llm_values[k]
            if val == "********" or (isinstance(val, str) and val.startswith("****************")):
                new_llm_values[k] = existing_llm_values.get(k, val)

    new_test_cases_values = payload.test_cases_values or {}
    
    if mongo_db is not None:
        await mongo_db.users.update_one(
            {"_id": _get_query_id(str(current_user.id))},
            {"$set": {
                "github_config": new_config,
                "quality_checks_values": new_qc_values,
                "test_cases_values": new_test_cases_values,
                "llm_values": new_llm_values
            }},
            upsert=True
        )
    
    return await get_user_github_settings(current_user)
 
@router.get("/user/settings/quality-checks-config")
async def get_user_quality_checks_config(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Fetch the Super Admin's quality checks configuration."""
    from app.infrastructure.quality_gates.cycode_config import quality_checks_config
    from app.infrastructure.persistence.mongodb_system_settings_repository import get_all_settings

    mongo_db = await get_mongodb()
    system_settings = await get_all_settings(mongo_db) if mongo_db is not None else {}

    def enabled(name: str) -> bool:
        value = system_settings.get(name)
        if value is None:
            value = _get_live_env_values().get(name.upper())
        return str(value if value is not None else "true").strip().lower() in {"1", "true", "yes", "on"}

    return {
        "quality_checks_config": quality_checks_config(),
        "ci_enabled": enabled("ci_enabled"),
        "cd_enabled": enabled("cd_enabled"),
    }

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
        raise HTTPException(status_code=400, detail="LLM connection failed. Unable to reach the provider.")
 
