from __future__ import annotations

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from app.infrastructure.llm.huggingface_client import HuggingFaceClient
from app.infrastructure.llm.groq_client import GroqClient, GroqPermanentError
from app.core.exceptions import LLMServiceError


@pytest.mark.asyncio
async def test_huggingface_402_no_retry() -> None:
    client = HuggingFaceClient()
    client._api_key = "fake_token"
    
    mock_response = AsyncMock()
    mock_response.status_code = 402
    
    # httpx.AsyncClient().post returns mock_response
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        with pytest.raises(LLMServiceError, match="HTTP 402"):
            await client.chat_json("system", "user")
        
        # It should only be called once, no retries
        assert mock_post.call_count == 1


@pytest.mark.asyncio
async def test_groq_429_token_limit_no_retry() -> None:
    client = GroqClient()
    client._api_key = "fake_token"
    
    mock_response = AsyncMock()
    mock_response.status_code = 429
    mock_response.text = '{"error": {"message": "Rate limit reached for model ... output tokens per minute."}}'
    mock_response.aread = AsyncMock(return_value=b'{"error": {"message": "Rate limit reached for model ... output tokens per minute."}}')
    
    with patch("httpx.AsyncClient.stream") as mock_stream:
        # Mock the context manager behavior of stream
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_stream.return_value = mock_context
        
        with pytest.raises(GroqPermanentError, match="Groq token rate limit reached"):
            # We need to iterate the async generator to trigger the exception
            async for _ in client.stream_chat("system", "user"):
                pass
        
        # Should only try once
        assert mock_stream.call_count == 1
