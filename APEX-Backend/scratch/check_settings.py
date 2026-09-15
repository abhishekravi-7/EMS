import sys
from pathlib import Path

# Add the project root to sys.path
root = Path(__file__).resolve().parents[1]
sys.path.append(str(root))

from app.core.config import settings

print(f"AUTH_PROVIDER: {settings.auth_provider}")
print(f"PERSISTENCE_BACKEND: {settings.persistence_backend}")
print(f"MONGODB_ENABLED: {settings.mongodb_enabled}")
print(f"MONGODB_URI: {settings.mongodb_uri}")
print(f"DATABASE_ENABLED: {settings.database_enabled}")
print(f"DATABASE_URL: {settings.database_url}")
print(f"ENV_FILE: {settings.model_config.get('env_file')}")
