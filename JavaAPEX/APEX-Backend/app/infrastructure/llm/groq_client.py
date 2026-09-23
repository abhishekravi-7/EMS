"""Streaming chat client for Groq (primary LLM for the Strategy chatbot).

Groq exposes an OpenAI-compatible chat completions API, so this is a thin
``httpx`` streaming wrapper (no extra SDK) that mirrors the style of
``huggingface_client``. Yields plain text token deltas as they arrive.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings, settings
from app.core.exceptions import ChatLLMNotConfiguredError, ChatLLMServiceError

logger = logging.getLogger(__name__)

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
        self._api_key_overridden = api_key is not None
        self._model_overridden = model is not None
        self._api_key = (api_key if api_key is not None else settings.groq_api_key).strip()
        self._base_url = (base_url or settings.groq_base_url).rstrip("/")
        self._model = model or settings.groq_model
        self._timeout = timeout or settings.chat_llm_request_timeout_seconds
        self.last_usage: tuple[int, int, int, int] | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _refresh_runtime_config(self) -> bool:
        """Reload provider values so rotated env/.env credentials take effect."""
        refreshed = Settings()
        changed = False
        if not self._api_key_overridden:
            new_api_key = refreshed.groq_api_key.strip()
            changed = changed or new_api_key != self._api_key
            self._api_key = new_api_key
        if not self._model_overridden:
            new_model = refreshed.groq_model.strip()
            changed = changed or new_model != self._model
            self._model = new_model
        return changed

    async def _discover_model(self, client: httpx.AsyncClient) -> bool:
        """Select the first active chat model when the configured model is gone."""
        if self._api_key_overridden and self._model_overridden:
            return False
        try:
            response = await client.get(
                f"{self._base_url}/models",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            if response.status_code != 200:
                return False
            models = response.json().get("data", [])
            candidates = [
                item.get("id")
                for item in models
                if item.get("id") and item.get("active", True)
            ]
            excluded_terms = ("guard", "safeguard", "whisper", "orpheus")
            chat_candidates = [
                model for model in candidates
                if not any(term in model.lower() for term in excluded_terms)
            ]
            preferred = next(
                (model for model in chat_candidates if model.startswith("openai/gpt-oss-20b")),
                None,
            ) or next(
                (model for model in chat_candidates if model.startswith("openai/gpt-oss-")),
                None,
            ) or next(iter(chat_candidates), None)
            if preferred and preferred != self._model:
                logger.warning("[GROQ] Model %s unavailable; switching to %s", self._model, preferred)
                self._model = preferred
                return True
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            logger.warning("[GROQ] Could not refresh model catalog: %s", type(exc).__name__)
        return False

    async def stream_chat(self, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> AsyncIterator[str]:
        """Yield answer text deltas from Groq. Raises on config/transport errors."""
        if not self._api_key:
            raise ChatLLMNotConfiguredError()

        self.last_usage = None
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": settings.chat_llm_temperature,
            "max_tokens": max_tokens if max_tokens is not None else settings.chat_llm_max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        max_retries = 3
        # Keep the transport inside the current event loop. A module-global
        # AsyncClient can retain a closed loop when callers use asyncio.run().
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(max_retries):
                emitted_any = False
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
                            # 429 = rate limit → retry with backoff if short, otherwise fail fast
                            if response.status_code == 429:
                                import re
                                wait_match = re.search(r"try again in (\d+(?:\.\d+)?)s", body_preview, re.IGNORECASE)
                                if wait_match:
                                    retry_after = int(float(wait_match.group(1))) + 1
                                else:
                                    retry_header = response.headers.get("Retry-After")
                                    if retry_header and retry_header.isdigit():
                                        retry_after = int(retry_header)
                                    else:
                                        retry_after = 2 ** attempt

                                if retry_after > 30:
                                    logger.warning("[GROQ] Daily or long rate limit (%ss) hit for model %s. Failing fast.", retry_after, self._model)
                                    raise ChatLLMServiceError(f"Groq rate limit exceeded ({body_preview[:120]}).")
                                if attempt < max_retries - 1:
                                    logger.warning(
                                        "[GROQ] Rate limited (429). Retrying in %ss (attempt %s/%s)",
                                        retry_after,
                                        attempt + 1,
                                        max_retries,
                                    )
                                    await asyncio.sleep(retry_after)
                                    continue
                            # Refresh credentials/model once before treating configuration
                            # errors as permanent. This supports secret rotation without a
                            # process restart and avoids retrying the same bad request.
                            if response.status_code in (400, 401, 403, 404):
                                config_changed = self._refresh_runtime_config()
                                if response.status_code == 404:
                                    config_changed = await self._discover_model(client) or config_changed
                                if config_changed:
                                    logger.info("[GROQ] Runtime configuration refreshed; retrying request")
                                    continue
                                if response.status_code == 404:
                                    raise ChatLLMServiceError(
                                        f"Groq model '{self._model}' is unavailable and no replacement was found."
                                    )
                                raise GroqPermanentError(
                                    f"Groq API error ({response.status_code}): {body_preview[:120]}. "
                                    "Please check your LLM_2 API key and model name in .env."
                                )
                            raise ChatLLMServiceError(
                                f"Groq API returned HTTP {response.status_code}."
                            )
                        async for line in response.aiter_lines():
                            delta, usage = _parse_sse_line(line)
                            if usage:
                                self.last_usage = usage
                            if delta:
                                emitted_any = True
                                yield delta
                    # Successful response, exit retry loop
                    return
                except (GroqPermanentError, ChatLLMNotConfiguredError):
                    raise  # permanent errors must not be swallowed or retried
                except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as exc:
                    logger.error(
                        "[GROQ] Connection failed | URL: %s | Model: %s | Cause: %s",
                        self._base_url,
                        self._model,
                        type(exc).__name__,
                    )
                    if not emitted_any and attempt < max_retries - 1:
                        delay = min(2 ** attempt, 4)
                        logger.warning(
                            "[GROQ] Transient transport failure; retrying in %ss (attempt %s/%s)",
                            delay,
                            attempt + 1,
                            max_retries,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise ChatLLMServiceError("Groq API could not be reached.") from exc
        raise ChatLLMServiceError("Groq API request failed after retries.")




def _parse_sse_line(line: str) -> tuple[str | None, tuple[int, int, int, int] | None]:
    """Extract incremental content and usage from one OpenAI-style SSE line."""
    line = line.strip()
    if not line or not line.startswith("data:"):
        return None, None
    data = line[len("data:"):].strip()
    if not data or data == "[DONE]":
        return None, None
    try:
        chunk = json.loads(data)

        # Extract usage even if choices is missing (common in final chunk)
        usage_obj = chunk.get("usage")
        usage = None
        if usage_obj:
            prompt = usage_obj.get("prompt_tokens", 0)
            completion = usage_obj.get("completion_tokens", 0)
            total = usage_obj.get("total_tokens", prompt + completion)
            usage = (prompt, completion, total, 0)

        choices = chunk.get("choices", [])
        delta = choices[0].get("delta", {}).get("content") if choices else None

        return delta, usage
    except (ValueError, KeyError, IndexError, TypeError):
        return None, None
