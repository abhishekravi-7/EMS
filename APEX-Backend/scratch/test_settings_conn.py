import sys
from pathlib import Path
from pymongo import MongoClient

# Add the project root to sys.path
root = Path(__file__).resolve().parents[1]
sys.path.append(str(root))

from app.core.config import settings

print(f"Testing connection with URI: {settings.mongodb_uri[:20]}...")
client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
try:
    client.admin.command("ping")
    print("Connection SUCCESSFUL using settings.mongodb_uri!")
    db = client[settings.mongodb_database]
    print(f"Database: {db.name}")
    print(f"Collections: {db.list_collection_names()}")
except Exception as e:
    print(f"Connection FAILED using settings.mongodb_uri: {e}")
finally:
    client.close()
