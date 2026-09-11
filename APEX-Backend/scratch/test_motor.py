import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

async def test_motor():
    backend_directory = Path(__file__).resolve().parents[1]
    load_dotenv(backend_directory / ".env")

    mongodb_uri = os.getenv("MONGODB_URI")
    print(f"Connecting to: {mongodb_uri[:20]}...")

    client = AsyncIOMotorClient(mongodb_uri, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")
        print("Motor connection successful!")
    except Exception as e:
        print(f"Motor connection failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_motor())
