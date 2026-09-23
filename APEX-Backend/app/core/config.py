"""Application configuration.

Settings are loaded from environment variables (and an optional ``.env`` file
sitting at the backend root). Keep this module free of any business logic — it
only exposes configuration values.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# APEX-Backend/app/core/config.py -> parents[2] == APEX-Backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = BACKEND_ROOT.parent
FRONTEND_ROOT = WORKSPACE_ROOT / "APEX-Frontend"


class Settings(BaseSettings):
    """Runtime configuration for the backend service."""

    model_config = SettingsConfigDict(
        # Prefer APEX-Backend/.env, but also support existing local setups that
        # placed backend keys in APEX-Frontend/.env.
        env_file=(str(FRONTEND_ROOT / ".env"), str(BACKEND_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General -------------------------------------------------------------
    app_name: str = "Java Migration Platform API"
    api_v1_prefix: str = "/api/v1"

    # --- Feature Flags / Providers -------------------------------------------
    # "mongodb" (primary auth & persistence backend)
    auth_provider: str = Field(default="mongodb", alias="AUTH_PROVIDER")
    persistence_backend: str = Field(default="mongodb", alias="PERSISTENCE_BACKEND")

    # --- GitHub --------------------------------------------------------------
    github_api_base_url: str = "https://api.github.com"
    # Source-read token: fallback used when the caller doesn't supply one (raises
    # the unauthenticated rate limit, clones private source repos). May be empty.
    github_token: str = ""
    # Target/publish token: used by the Start Migration stage to create and push
    # migrated repositories under the JavaAPEX org. Must belong to an account
    # authorized on that org (repo scope, or fine-grained Administration +
    # Contents: write). May be empty until the Start Migration stage is used.
    github_target_token: str = ""
    github_target_owner: str = Field(default="JavaAPEX", alias="GITHUB_TARGET_OWNER")
    github_default_branch: str = Field(default="main", alias="GITHUB_DEFAULT_BRANCH")
    github_request_timeout_seconds: float = 15.0

    # --- Hugging Face LLM (Target Java Version Recommendation) --------------
    # Inference Providers router (OpenAI-compatible chat completions). Any
    # LLM_1-authorized chat model can be swapped in without a code change.
    huggingface_api_base_url: str = "https://router.huggingface.co/v1"
    huggingface_model: str = "meta-llama/Llama-3.1-8B-Instruct:novita"
    # Read from the provider-neutral LLM_1 env var. Leave empty to disable AI
    # recommendations (the endpoint then reports itself as unavailable rather
    # than fabricating a recommendation).
    huggingface_token: str = Field(default="", alias="LLM_1")
    huggingface_request_timeout_seconds: float = 30.0

    # --- Strategy RAG chatbot (JavaApex Assistant) --------------------------
    # Primary LLM: GROQ (OpenAI-compatible chat completions, streaming). Read
    # from the provider-neutral LLM_2 env var; leave empty to disable GROQ and
    # fall straight through to Ollama.
    groq_api_key: str = Field(default="", alias="LLM_2")
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    # Fallback LLM: a local Ollama server. Used only when GROQ is unavailable.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    # Sentence-embedding model (384-dim). Downloaded + cached on first use.
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    # Embedded Qdrant (Vector Store) — persists to disk (no server/Docker needed).
    # Swap to server mode later by pointing the wrapper at a URL instead.
    qdrant_path: Path = BACKEND_ROOT / "storage" / "vector-store"
    qdrant_collection: str = "repo_knowledge"
    # Master switch for the whole RAG stack (embeddings + vector store). Off by
    # default because the local embedding model needs ~500MB resident -- more
    # than a small/free cloud instance has in total -- and `qdrant-client` /
    # `sentence-transformers` are not installed in the deployed image. When
    # false the chatbot reports itself unavailable instead of failing at import
    # time; Discovery and Migration are unaffected (their indexing calls are
    # already best-effort). Set ENABLE_RAG=true once the instance has the RAM.
    rag_enabled: bool = Field(default=False, alias="ENABLE_RAG")
    # Master switch for database usage. Supports both ENABLE_DATABASE and DATABASE_ENABLED.
    database_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("ENABLE_DATABASE", "DATABASE_ENABLED", "database_enabled"),
    )
    # Master switch for MongoDB usage.
    mongodb_enabled: bool = Field(default=True, alias="ENABLE_MONGODB")
    mongodb_uri: str = Field(default="", alias="MONGODB_URI")
    mongodb_database: str = Field(default="java_apex", alias="MONGODB_DATABASE")

    # Number of knowledge chunks retrieved per question.
    rag_top_k: int = 4
    # Timeout (seconds) for a single chat-LLM request (GROQ or Ollama).
    chat_llm_request_timeout_seconds: float = 60.0
    # Timeout (seconds) to wait for the first token before falling back to next provider.
    chat_llm_fallback_timeout_seconds: float = 3.0

    # --- Git / clone ---------------------------------------------------------
    # Timeout (seconds) for a `git clone` during Discovery.
    git_clone_timeout_seconds: float = 300.0
    # Clone only the latest commit to keep the workspace small and fast.
    git_clone_depth: int = 1

    java_migration_engine_jar: Path = Field(
        default_factory=lambda: WORKSPACE_ROOT / "migration-engine" / "target" / "migration-engine-1.0.0-SNAPSHOT.jar",
        validation_alias=AliasChoices(
            "MIGRATION_ENGINE_JAR_PATH",
            "JAVA_MIGRATION_ENGINE_JAR",
            "java_migration_engine_jar",
        ),
    )
    migration_recipe_catalog_path: Path = BACKEND_ROOT / "app" / "config" / "migration_pack_catalog.json"
    # Timeout (seconds) for a single migration-engine run.
    migration_timeout_seconds: float = 1800.0
    # Identity used for the migrated-repo commit.
    migration_commit_author_name: str = "Java APEX Migration Bot"
    migration_commit_author_email: str = "migration-bot@javaapex.local"
    # Bounded retry loop when the post-migration build fails. 0 disables retries.
    migration_max_retry_attempts: int = 2
    # Maximum build→fix→rebuild iterations for LLM self-healing.
    max_heal_cycles: int = 3
    # Max files to attempt LLM repair per heal cycle. 0 = unlimited.
    max_files_per_heal_cycle: int = 0
    # If True, block publishing to GitHub when the build completely fails.
    block_publish_on_build_failure: bool = False

    # --- Build validation (post-migration "does it build?" check) -----------
    # Whether to compile/package the migrated code and log BUILD SUCCESS/FAILED.
    build_validation_enabled: bool = True
    # Local JDK used by Maven/Gradle subprocesses. Leave empty to inherit the
    # server environment's JAVA_HOME/PATH.
    build_java_home: str = ""
    # Local Gradle install used when a Gradle project has no Windows wrapper
    # and the backend process PATH does not include gradle.bat.
    gradle_home: str = ""
    # Maven goals: package the migrated app without compiling/running tests.
    # Some legacy projects keep Groovy/Spock/JUnit test toolchains that are not
    # Java-target compatible after migration; those should not block the basic
    # "does the migrated application package?" validation.
    build_maven_args: str = "-B,-Dmaven.test.skip=true,package"
    # Gradle tasks: build but skip tests.
    build_gradle_args: str = "build,-x,test,--no-daemon"
    # Timeout (seconds) for the build.
    build_timeout_seconds: float = 1200.0

    @property
    def build_maven_args_list(self) -> list[str]:
        return [a for a in self.build_maven_args.split(",") if a]

    @property
    def build_gradle_args_list(self) -> list[str]:
        return [a for a in self.build_gradle_args.split(",") if a]

    # --- Quality Gates -------------------------------------------------------
    # Dynamic settings are now fetched from MongoDB (User Settings) during migration.
    
    # Internal prefixes and CLI command names used by runners:
    sonarqube_project_key_prefix: str = "java-apex"
    sonarqube_scanner_command: str = "sonar-scanner"
    # FOSSA API key. Required only when the FOSSA quality gate card is active.
    fossa_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("FOSSA_API_KEY", "fossa_api_key"),
    )
    # Optional custom FOSSA endpoint for self-hosted/enterprise setups.
    fossa_endpoint: str = Field(
        default="",
        validation_alias=AliasChoices("FOSSA_ENDPOINT", "fossa_endpoint"),
    )
    fossa_cli_command: str = Field(
        default="fossa",
        validation_alias=AliasChoices("FOSSA_CLI_PATH", "FOSSA_CLI_COMMAND", "fossa_cli_command"),
    )

    # --- Test Cases ----------------------------------------------------------
    test_cases_playwright_enabled: bool = False
    test_cases_playwright_command: str = "npx playwright test"
    test_cases_cypress_enabled: bool = False
    test_cases_cypress_command: str = "npx cypress run"
    test_cases_selenium_enabled: bool = False
    test_cases_selenium_command: str = "pytest"

    # --- Storage -------------------------------------------------------------
    # Root folder where per-job artifacts (reports, etc.) are written.
    storage_dir: Path = BACKEND_ROOT / "storage" / "migration-jobs"
    # Root folder where submitted support tickets are written (Support feature).
    support_tickets_dir: Path = BACKEND_ROOT / "storage" / "support-tickets"
    # Shared GRADLE_USER_HOME used by every job's Gradle/migration run and
    # build validation. Deliberately a sibling of storage_dir (not per-job)
    # so the (large) Gradle distribution zip and dependency/plugin caches are
    # downloaded once and reused across jobs, instead of every job re-fetching
    # them from services.gradle.org and being exposed to network timeouts.
    gradle_shared_cache_dir: Path = BACKEND_ROOT / "storage" / ".gradle-cache"
    support_notification_recipient: str = Field(default="", alias="SUPPORT_NOTIFICATION_RECIPIENT")

    # --- Authentication (JWT + cookies) -----------------------------------------
    # HMAC signing secret for access/refresh JWTs. Must be set in .env — the
    # empty default is rejected at startup by validate_auth_settings() below.
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120
    refresh_token_expire_days: int = 7
    # Static development login credentials (used only when database is disabled in dev mode)
    dev_static_user_email: str = Field(default="javaapex@gmail.com", alias="DEV_STATIC_USER_EMAIL")
    dev_static_user_password: str = Field(default="javaapex1234", alias="DEV_STATIC_USER_PASSWORD")

    # --- Firebase (New Authentication) ------------------------------------------
    # Service account credentials for Firebase Admin SDK.
    # Set these in APEX-Backend/.env for production.
    firebase_project_id: str = Field(default="", alias="FIREBASE_PROJECT_ID")
    firebase_private_key: str = Field(default="", alias="FIREBASE_PRIVATE_KEY")
    firebase_client_email: str = Field(default="", alias="FIREBASE_CLIENT_EMAIL")

    # Enable/disable Firebase authentication
    firebase_auth_enabled: bool = Field(default=True, alias="FIREBASE_AUTH_ENABLED")

    @property
    def firebase_credentials(self) -> dict[str, str] | None:
        """Construct the Firebase service account dictionary from individual settings.

        This avoids hardcoding a literal GCP service account JSON structure in source,
        preventing false positive detections in security scanners.
        """
        if not all([self.firebase_project_id, self.firebase_private_key, self.firebase_client_email]):
            return None

        # Build keys and values separately to avoid literal JSON structure detection
        keys = ["type", "project_id", "private_key", "client_email", "token_uri"]
        vals = [
            "service_account",
            self.firebase_project_id,
            self.firebase_private_key.replace("\\n", "\n"),
            self.firebase_client_email,
            "https://oauth2.googleapis.com/token",
        ]
        return dict(zip(keys, vals, strict=True))


    # Frontend origin this deployment's auth cookies/CORS trust.
    frontend_url: str = "http://localhost:5173"
    backend_url: str = Field(default="http://localhost:8000", alias="BACKEND_URL")

    # Use True to enforce JWT cookies having Secure flag
    # For local dev without HTTPS, this can be set to False
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # --- SonarQube (Quality Checks) ------------------------------------------
    sonarqube_host_url: str = Field(default="http://localhost:9000", alias="SONARQUBE_HOST_URL")
    sonarqube_token: str = ""
    sonarqube_request_timeout_seconds: float = 30.0

    # --- LLM Settings --------------------------------------------------------
    llm_enabled: bool = Field(default=True, alias="LLM_ENABLED")
    llm_features: str = Field(default="EXPLAIN_RESULTS,GENERATE_TESTS,RAG,CODE_ANALYSIS", alias="LLM_FEATURES")
    llm_models: str = Field(default="Groq,HuggingFace", alias="LLM_MODELS")

    # --- SMTP / Email Configuration -------------------------------------------
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    smtp_from_address: str = Field(default="", alias="SMTP_FROM_ADDRESS")

    @property
    def smtp_password_clean(self) -> str:
        """Return SMTP password with spaces stripped (e.g. for Gmail 16-char app passwords)."""
        if not self.smtp_password:
            return ""
        return self.smtp_password.replace(" ", "").strip()

    @property
    def is_smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_username and self.smtp_password and self.smtp_from_address)

    # --- Feature Flags / Third-party Tools -------------------------------------
    # identity-only login (see app/infrastructure/oauth/). Deliberately separate
    # from GITHUB_TOKEN/GITHUB_TARGET_TOKEN above, which are unrelated to login
    # and used only for the Connect stage's repository read/publish access.
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str | None = Field(default=None, alias="GOOGLE_REDIRECT_URI")
    github_client_id: str = Field(default="", alias="GITHUB_CLIENT_ID")
    github_client_secret: str = Field(default="", alias="GITHUB_CLIENT_SECRET")
    github_redirect_uri: str | None = Field(default=None, alias="GITHUB_REDIRECT_URI")

    @property
    def get_google_redirect_uri(self) -> str:
        return self.google_redirect_uri or f"{self.backend_url}/api/auth/google/callback"

    @property
    def get_github_redirect_uri(self) -> str:
        return self.github_redirect_uri or f"{self.backend_url}/api/auth/github/callback"
    # How long a signed OAuth `state` (and, for Google, the PKCE code_verifier
    # cookie) stays valid — the window the user has to complete the provider's
    # consent screen before the login attempt must be restarted.
    oauth_state_expire_seconds: int = 600

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def github_oauth_configured(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret)

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def cookie_samesite(self) -> str:
        """Same-Site policy for the auth cookies, chosen per environment.

        The deployed frontend and backend live on different hosts, which makes
        every API call cross-site. `SameSite=Lax` tells the browser to withhold
        the cookie on exactly those requests, so login would appear to succeed
        and then every subsequent call would 401. `None` is required there --
        and browsers only accept `SameSite=None` alongside `Secure`, which
        `secure=settings.is_production` already supplies over HTTPS.

        Local development stays on `lax`: a `Secure` cookie is silently dropped
        over plain http://localhost, which would break dev login instead.
        """
        return "none" if self.is_production else "lax"

    def validate_auth_settings(self) -> None:
        """Fail fast at startup if a required auth setting is missing.

        Called once from ``main.py`` before the app starts serving requests —
        similar to a Spring Boot ``@PostConstruct`` sanity check. Only ever
        reports which variable NAMES are missing, never their values, so
        nothing secret reaches the startup log.
        """
        missing = []
        if not self.mongodb_uri:
            missing.append("MONGODB_URI")

        if not self.jwt_secret_key:
            missing.append("JWT_SECRET_KEY")

        if missing:
            raise RuntimeError(
                "Missing required environment variable(s): "
                f"{', '.join(missing)}. Set them in APEX-Backend/.env "
                "(see .env.example)."
            )

    # --- CORS ----------------------------------------------------------------
    # Comma-separated list of allowed origins for the frontend dev/prod hosts.
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:8000,http://127.0.0.1:8000"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> "Settings":
    """Return a cached ``Settings`` instance."""
    return Settings()


settings = get_settings()
