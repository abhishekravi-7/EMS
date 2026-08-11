"""Streaming chat client for Groq (primary LLM for the Strategy chatbot).

Groq exposes an OpenAI-compatible chat completions API, so this is a thin
``httpx`` streaming wrapper (no extra SDK) that mirrors the style of
``huggingface_client``. Yields plain text token deltas as they arrive.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx
import asyncio
import threading

from app.core.config import settings
from app.core.exceptions import ChatLLMNotConfiguredError, ChatLLMServiceError

logger = logging.getLogger(__name__)

_shared_client = None
_client_lock = threading.Lock()

def _get_client():
    global _shared_client
    if _shared_client is None:
        with _client_lock:
            if _shared_client is None:
                _shared_client = httpx.AsyncClient(timeout=settings.chat_llm_request_timeout_seconds)
    return _shared_client


class GroqPermanentError(ChatLLMServiceError):
    """Groq failed with an error that will NOT be fixed by retrying or falling back to Ollama.

    Examples: 401 Unauthorized, 403 Forbidden, 400 Bad Request (bad model name).
    Callers (chat_llm.py) should NOT try Ollama for these — they indicate a
    configuration problem, not a transient network issue.
    """

    status = "GROQ_PERMANENT_ERROR"


class GroqClient:
    provider = "groq"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._api_key = (api_key if api_key is not None else settings.groq_api_key).strip()
        self._base_url = (base_url or settings.groq_base_url).rstrip("/")
        self._model = model or settings.groq_model
        self._timeout = timeout or settings.chat_llm_request_timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def stream_chat(self, system_prompt: str, user_prompt: str) -> AsyncIterator[str]:
        """Yield answer text deltas from Groq. Raises on config/transport errors."""
        if not self._api_key:
            raise ChatLLMNotConfiguredError()

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        max_retries = 3
        client = _get_client()
        for attempt in range(max_retries):
            try:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                        if response.status_code != 200:
                            await response.aread()
                            body_preview = (response.text or "")[:300]
                            logger.error(
                                "[GROQ] HTTP %s | Model: %s | Body: %s",
                                response.status_code,
                                self._model,
                                body_preview,
                            )
                            # 429 = rate limit → retry with backoff
                            if response.status_code == 429 and attempt < max_retries - 1:
                                retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                                logger.warning(
                                    "[GROQ] Rate limited (429). Retrying in %ss (attempt %s/%s)",
                                    retry_after,
                                    attempt + 1,
                                    max_retries,
                                )
                                await asyncio.sleep(retry_after)
                                continue
                            # 401/403/400 = permanent config error → do NOT fall back to Ollama
                            if response.status_code in (400, 401, 403):
                                raise GroqPermanentError(
                                    f"Groq API error ({response.status_code}): {body_preview[:120]}. "
                                    "Please check your LLM_2 API key and model name in .env."
                                )
                            raise ChatLLMServiceError(
                                f"Groq API returned HTTP {response.status_code}."
                            )
                        async for line in response.aiter_lines():
                            delta = _parse_sse_delta(line)
                            if delta:
                                yield delta
                # Successful response, exit retry loop
                return
            except (GroqPermanentError, ChatLLMNotConfiguredError):
                raise  # permanent errors must not be swallowed or retried
            except httpx.HTTPError as exc:
                logger.error(
                    "[GROQ] Connection failed | URL: %s | Model: %s | Cause: %s",
                    self._base_url,
                    self._model,
                    type(exc).__name__,
                )
                raise ChatLLMServiceError("Groq API could not be reached.") from exc
        raise ChatLLMServiceError("Groq API request failed after retries.")




def _parse_sse_delta(line: str) -> str | None:
    """Extract the incremental content from one OpenAI-style SSE line."""
    line = line.strip()
    if not line or not line.startswith("data:"):
        return None
    data = line[len("data:"):].strip()
    if not data or data == "[DONE]":
        return None
    try:
        chunk = json.loads(data)
        return chunk["choices"][0]["delta"].get("content") or None
    except (ValueError, KeyError, IndexError, TypeError):
        return None
