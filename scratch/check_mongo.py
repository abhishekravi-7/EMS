import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test():
    uri = "mongodb+srv://praveenp4590_db_user:nEigjUXaN9VR6Lsn@cluster0.nskqgcl.mongodb.net/?appName=Cluster0"
    client = AsyncIOMotorClient(uri)
    db = client["java_apex"]

    u_int = await db.users.find_one({"_id": 17})
    print("User with int 17:", u_int)

    u_str = await db.users.find_one({"_id": "17"})
    print("User with str 17:", u_str)

asyncio.run(test())
