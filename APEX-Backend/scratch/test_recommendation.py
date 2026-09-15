import httpx
import asyncio
import json

async def test():
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                'source_java_version': '8',
                'build_tool': 'maven',
                'dependencies': [],
                'has_tests': True,
                'api_endpoint_count': 0,
                'risk_level': 'low'
            }
            print(f"Sending request to http://127.0.0.1:8000/api/java-version-recommendation with payload: {payload}")
            resp = await client.post('http://127.0.0.1:8000/api/java-version-recommendation', json=payload, timeout=60.0)
            print(f'Status: {resp.status_code}')
            print(f'Body: {resp.text}')
    except Exception as e:
        print(f'Error: {type(e).__name__}: {e}')

if __name__ == "__main__":
    asyncio.run(test())
