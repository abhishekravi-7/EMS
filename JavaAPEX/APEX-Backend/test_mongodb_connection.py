import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

backend_directory = Path(__file__).resolve().parent
load_dotenv(backend_directory / ".env")

mongodb_uri = os.getenv("MONGODB_URI")
database_name = os.getenv("MONGODB_DATABASE")

if not mongodb_uri:
    raise RuntimeError("MONGODB_URI is missing from APEX-Backend/.env")

if not database_name:
    raise RuntimeError("MONGODB_DATABASE is missing from APEX-Backend/.env")

client = MongoClient(
    mongodb_uri,
    serverSelectionTimeoutMS=5000,
)

try:
    result = client.admin.command("ping")
    database = client[database_name]

    print("MongoDB connection successful:", result)
    print("Database:", database.name)
    print("Collections:", database.list_collection_names())
finally:
    client.close()
