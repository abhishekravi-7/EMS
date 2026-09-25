"""Thin async client over Hugging Face's OpenAI-compatible chat completions API.

Uses the Inference Providers router (``https://router.huggingface.co/v1``) so
any ``LLM_1``-authorized chat model can be swapped in via configuration,
with no code change. Intentionally generic (not tied to any one feature) so
other LLM-backed features in this package can reuse it.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

import token_tracing as tt
from app.core.config import settings
from app.core.exceptions import LLMNotConfiguredError, LLMServiceError

logger = logging.getLogger(__name__)


class HuggingFaceClient:
    _disabled: bool = False
    _disabled_reason: str = ""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = (base_url or settings.huggingface_api_base_url).rstrip("/")
        self._model = model or settings.huggingface_model
        self._timeout = timeout or settings.huggingface_request_timeout_seconds
        self.last_usage: tuple[int, int, int, int] | None = None

    async def _call_groq_direct(self, system_prompt: str, user_prompt: str, api_key: str) -> dict[str, Any]:
        """Direct fallback call to Groq's OpenAI-compatible JSON endpoint."""
        url = "https://api.groq.com/openai/v1/chat/completions"
        model = settings.groq_model or "openai/gpt-oss-20b"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                return self._extract_json(content)
            raise LLMServiceError(f"Groq direct call returned HTTP {response.status_code}")

    async def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Send a chat completion request and return the parsed JSON content.

        Raises :class:`LLMNotConfiguredError` when no token is configured, and
        :class:`LLMServiceError` on any transport/HTTP failure or a response
        that isn't parseable JSON.
        """
        token = (settings.huggingface_token or "").strip()
        groq_key = (settings.groq_api_key or "").strip()

        if token.startswith("gsk_"):
            return await self._call_groq_direct(system_prompt, user_prompt, token)

        if not token or HuggingFaceClient._disabled:
            if groq_key:
                return await self._call_groq_direct(system_prompt, user_prompt, groq_key)
            raise LLMNotConfiguredError(HuggingFaceClient._disabled_reason or "Hugging Face is not configured.")

        from app.core.context import llm_values_ctx

        if not settings.llm_enabled:
            raise LLMNotConfiguredError()

        ctx_vals = llm_values_ctx.get()
        token = ctx_vals.get("huggingface_api_key")
        model_to_use = ctx_vals.get("huggingface_model")

        if not token or not model_to_use:
            raise LLMNotConfiguredError("LLM is not configured. Please setup your API key and model in User Settings.")

        payload = {
            "model": model_to_use,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": settings.huggingface_temperature,
            "max_tokens": settings.huggingface_max_tokens,
        }
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        import asyncio

        max_retries = 3
        start_time = time.time()
        error = None
        body = None
        self.last_usage = None

        try:
            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        logger.info(
                            "[HuggingFace] Sending request to %s/chat/completions (attempt %s/%s)",
                            self._base_url,
                            attempt + 1,
                            max_retries,
                        )
                        response = await client.post(
                            f"{self._base_url}/chat/completions", headers=headers, json=payload
                        )

                    if response.status_code == 429 and attempt < max_retries - 1:
                        retry_after = int(response.headers.get("Retry-After", 2**attempt))
                        logger.warning(
                            "[HuggingFace] Rate limited (429). Retrying in %ss (attempt %s/%s)",
                            retry_after,
                            attempt + 1,
                            max_retries,
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    if response.status_code in (401, 402, 403):
                        HuggingFaceClient._disabled = True
                        HuggingFaceClient._disabled_reason = f"Hugging Face API returned HTTP {response.status_code} (Payment/Auth required)."
                        logger.warning(
                            "[HuggingFace] API returned HTTP %s. Disabling HuggingFace for session and routing via Groq.",
                            response.status_code,
                        )
                        if groq_key:
                            return await self._call_groq_direct(system_prompt, user_prompt, groq_key)
                        raise LLMServiceError(f"Hugging Face API returned HTTP {response.status_code}.")

                    if response.status_code != 200:
                        error = f"HTTP {response.status_code}"
                        logger.error("[HuggingFace] API failed with HTTP %s", response.status_code)
                        raise LLMServiceError(f"Hugging Face API returned HTTP {response.status_code}.")

                    try:
                        body = response.json()
                    except json.JSONDecodeError as exc:
                        error = "Malformed JSON response"
                        logger.error("[HuggingFace] Malformed JSON response from API")
                        raise LLMServiceError("Hugging Face API returned a malformed JSON response.") from exc

                    self.last_usage = tt.extract_usage(body)
                    try:
                        content = body["choices"][0]["message"]["content"]
                    except (KeyError, IndexError, TypeError) as exc:
                        error = "Unexpected payload shape"
                        logger.error("[HuggingFace] Unexpected payload shape: %s", body)
                        raise LLMServiceError("Hugging Face API returned an unexpected payload shape.") from exc

                    return self._extract_json(content)

                except httpx.TimeoutException as exc:
                    error = "Timeout"
                    logger.error("[HuggingFace] Request timed out after %ss", self._timeout)
                    if attempt < max_retries - 1:
                        continue
                    raise LLMServiceError("Hugging Face API request timed out.") from exc
                except httpx.ConnectError as exc:
                    error = "Connection Error"
                    logger.error("[HuggingFace] Failed to connect to %s", self._base_url)
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                    raise LLMServiceError("Could not connect to Hugging Face API.") from exc
                except httpx.HTTPError as exc:
                    error = f"HTTP error: {type(exc).__name__}"
                    logger.error("[HuggingFace] HTTP transport error: %s", str(exc))
                    if attempt < max_retries - 1:
                        continue
                    raise LLMServiceError(f"Hugging Face API transport error: {type(exc).__name__}") from exc
                except Exception as exc:
                    if isinstance(exc, LLMServiceError):
                        raise
                    error = f"Unexpected error: {type(exc).__name__}"
                    logger.error("[HuggingFace] Unexpected error during call: %s", str(exc), exc_info=True)
                    raise LLMServiceError(f"An unexpected error occurred during LLM call: {type(exc).__name__}") from exc

            raise LLMServiceError("Hugging Face API request failed after all retry attempts.")
        finally:
            duration_ms = (time.time() - start_time) * 1000
            try:
                usage = tt.extract_usage(body) if body else (0, 0, 0, 0)
                tt.get_token_tracer().record(
                    role="chat",
                    model=model_to_use,
                    call_type="chat",
                    duration_ms=duration_ms,
                    usage=usage,
                    provider="huggingface",
                    endpoint="java_version_recommendation",
                    error=error,
                )
            except Exception as e:  # noqa: BLE001
                logger.debug("Non-fatal: Token tracer failed: %s", type(e).__name__)

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        text = (content or "").strip()
        # Some models wrap JSON in ```json ... ``` fences despite instructions
        # not to.
        if text.startswith("```"):
            text = text.strip("`")
            if text[:4].lower() == "json":
                text = text[4:]

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise LLMServiceError("Hugging Face model response did not contain JSON.")

        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMServiceError("Hugging Face model response was not valid JSON.") from exc

        if not isinstance(parsed, dict):
            raise LLMServiceError("Hugging Face model response JSON was not an object.")
        return parsed
