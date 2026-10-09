import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://localhost:27017/')
    db = client['java_apex']
    
    # Try both integer 101 and string '101'
    for uid in [101, '101']:
        result = await db.users.update_one(
            {'_id': uid},
            {
                '': {
                    'llm_values.ollama_url': 'http://localhost:11434',
                    'llm_values.ollama_model': 'qwen2.5-coder:7b'
                }
            }
        )
        print(f"ID {uid} -> Matched: {result.matched_count}, Modified: {result.modified_count}")

asyncio.run(main())
