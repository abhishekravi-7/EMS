"""Streaming chat client for a local Ollama server (fallback LLM).

Used only when Groq is unavailable. Ollama streams newline-delimited JSON
objects (not SSE) from ``POST /api/chat``; each object carries a
``message.content`` delta. No API key is required — availability is simply
whether the local server responds.

Error types are distinguished so callers can surface a precise user message:
- Connection refused / unreachable  → OllamaUnavailableError
- Model not found (404)             → OllamaModelNotFoundError
- Timeout                           → OllamaTimeoutError
- Other HTTP error                  → ChatLLMServiceError
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings
from app.core.exceptions import ChatLLMServiceError

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


class OllamaUnavailableError(ChatLLMServiceError):
    """Raised when the Ollama server cannot be reached (not running / wrong URL)."""

    status = "OLLAMA_UNAVAILABLE"

    def __init__(self, base_url: str, model: str, cause: Exception | None = None) -> None:
        msg = (
            "The local AI service is currently unavailable. "
            "Please make sure Ollama is running and the configured model is available. "
            "Run: ollama serve"
        )
        super().__init__(msg)
        self._base_url = base_url
        self._model = model
        self.__cause__ = cause
        logger.error(
            "[OLLAMA] Connection failed | URL: %s | Model: %s | Cause: %s",
            base_url,
            model,
            type(cause).__name__ if cause else "unknown",
        )


class OllamaModelNotFoundError(ChatLLMServiceError):
    """Raised when the Ollama server is reachable but the model is not installed."""

    status = "OLLAMA_MODEL_NOT_FOUND"

    def __init__(self, base_url: str, model: str) -> None:
        msg = (
            f"The local AI service is running but the required model '{model}' "
            f"is not installed. Run: ollama pull {model}"
        )
        super().__init__(msg)
        logger.error(
            "[OLLAMA] Model not found | URL: %s | Model: %s | Run: ollama pull %s",
            base_url,
            model,
            model,
        )


class OllamaTimeoutError(ChatLLMServiceError):
    """Raised when the Ollama server is reachable but the response timed out."""

    status = "OLLAMA_TIMEOUT"

    def __init__(self, base_url: str, model: str) -> None:
        msg = (
            "The local AI service is running but the response took too long. "
            "The model may still be loading. Please wait and try again."
        )
        super().__init__(msg)
        logger.error(
            "[OLLAMA] Request timeout | URL: %s | Model: %s",
            base_url,
            model,
        )


class OllamaClient:
    provider = "ollama"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._model = model or settings.ollama_model
        self._timeout = timeout or settings.chat_llm_request_timeout_seconds
        self.last_usage: tuple[int, int, int, int] | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self._base_url)

    async def health_check(self) -> dict:
        """Check if the Ollama server is reachable and the configured model is available."""
        try:
            client = _get_client()
            response = await client.get(f"{self._base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                model_available = any(
                    self._model in name or name.startswith(self._model.split(":")[0])
                    for name in models
                )
                return {
                    "available": True,
                    "model": self._model,
                    "model_installed": model_available,
                    "installed_models": models,
                    "url": self._base_url,
                }
            return {
                "available": False,
                "model": self._model,
                "message": f"Ollama server returned HTTP {response.status_code}",
                "url": self._base_url,
            }
        except httpx.TimeoutException:
            return {
                "available": False,
                "model": self._model,
                "message": "Ollama server connection timed out",
                "url": self._base_url,
            }
        except httpx.ConnectError:
            return {
                "available": False,
                "model": self._model,
                "message": "Ollama server is not reachable. Run: ollama serve",
                "url": self._base_url,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "available": False,
                "model": self._model,
                "message": f"Ollama health check failed: {type(exc).__name__}",
                "url": self._base_url,
            }

    async def stream_chat(self, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> AsyncIterator[str]:
        """Stream from local Ollama server."""
        async for delta in self._stream_ollama_internal(system_prompt, user_prompt):
            yield delta

    async def _stream_ollama_internal(self, system_prompt: str, user_prompt: str) -> AsyncIterator[str]:
        """Original Ollama streaming logic."""
        self.last_usage = None
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,
            "options": {"temperature": 0.2},
        }

        try:
            client = _get_client()
            async with client.stream(
                "POST", f"{self._base_url}/api/chat", json=payload
            ) as response:
                if response.status_code == 404:
                    await response.aread()
                    raise OllamaModelNotFoundError(self._base_url, self._model)
                if response.status_code != 200:
                    await response.aread()
                    body = response.text[:200] if response.text else ""
                    logger.error(
                        "[OLLAMA] HTTP %s | URL: %s | Model: %s | Body: %s",
                        response.status_code,
                        self._base_url,
                        self._model,
                        body,
                    )
                    raise ChatLLMServiceError(
                        f"Ollama server returned HTTP {response.status_code}. "
                        "Please check that the model is installed and Ollama is running."
                    )
                async for line in response.aiter_lines():
                    delta, usage = _parse_ndjson_line(line)
                    if usage:
                        self.last_usage = usage
                    if delta:
                        yield delta
        except (OllamaModelNotFoundError, OllamaTimeoutError, OllamaUnavailableError, ChatLLMServiceError):
            raise  # already typed — pass through unchanged
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError(self._base_url, self._model) from exc
        except httpx.ConnectError as exc:
            raise OllamaUnavailableError(self._base_url, self._model, cause=exc) from exc
        except httpx.HTTPError as exc:
            # Generic transport error (not connection refused, not timeout)
            raise OllamaUnavailableError(self._base_url, self._model, cause=exc) from exc


def _parse_ndjson_line(line: str) -> tuple[str | None, tuple[int, int, int, int] | None]:
    """Extract the content delta and usage from one Ollama NDJSON line."""
    line = line.strip()
    if not line:
        return None, None
    try:
        obj = json.loads(line)
        delta = (obj.get("message") or {}).get("content")

        usage = None
        if obj.get("done"):
            prompt = obj.get("prompt_eval_count", 0)
            completion = obj.get("eval_count", 0)
            total = prompt + completion
            usage = (prompt, completion, total, 0)

        return delta, usage
    except ValueError:
        return None, None


def _parse_sse_delta(line: str) -> str | None:
    """Extract the incremental content from one OpenAI-style SSE line (Groq)."""
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
