import asyncio
import time
from app.infrastructure.llm.chat_llm import ChatLLM
from app.infrastructure.llm.groq_client import GroqClient
from app.infrastructure.llm.ollama_client import OllamaClient
from app.core.exceptions import ChatLLMServiceError

class MockGroqClient(GroqClient):
    @property
    def is_configured(self):
        return True
    
    async def stream_chat(self, system_prompt, user_prompt, max_tokens=None):
        print(f"[MockGroq] Sleeping for 3 seconds to simulate rate limit wait...")
        await asyncio.sleep(3)
        print(f"[MockGroq] Yielding token...")
        yield "Hello from Groq"

class MockOllamaClient(OllamaClient):
    @property
    def is_configured(self):
        return True
    
    async def stream_chat(self, system_prompt, user_prompt, max_tokens=None):
        print(f"[MockOllama] Yielding token...")
        yield "Hello from Ollama"

async def test_fallback():
    chat_llm = ChatLLM(groq_client=MockGroqClient(), ollama_client=MockOllamaClient())
    
    # Test 1: Should fallback if first_token_timeout is small (e.g. 1s)
    print("--- Test 1: Small timeout (Should fallback to Ollama) ---")
    try:
        async for chunk in chat_llm.stream_chat("sys", "user", first_token_timeout=1.0):
            print(f"Received: {chunk}")
    except Exception as e:
        print(f"Error: {e}")
        
    print(f"Provider used: {chat_llm.last_provider}")
    
    # Test 2: Should NOT fallback if first_token_timeout is large (e.g. 10s)
    print("\n--- Test 2: Large timeout (Should wait for Groq) ---")
    try:
        async for chunk in chat_llm.stream_chat("sys", "user", first_token_timeout=10.0):
            print(f"Received: {chunk}")
    except Exception as e:
        print(f"Error: {e}")
        
    print(f"Provider used: {chat_llm.last_provider}")

if __name__ == "__main__":
    asyncio.run(test_fallback())
