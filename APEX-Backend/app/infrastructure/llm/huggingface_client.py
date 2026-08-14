"""Thin async client over Hugging Face's OpenAI-compatible chat completions API.

Uses the Inference Providers router (``https://router.huggingface.co/v1``) so
any ``LLM_1``-authorized chat model can be swapped in via configuration,
with no code change. Intentionally generic (not tied to any one feature) so
other LLM-backed features in this package can reuse it.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
import token_tracing as tt

from app.core.config import settings
from app.core.exceptions import LLMNotConfiguredError, LLMServiceError


class HuggingFaceClient:
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

    async def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Send a chat completion request and return the parsed JSON content.

        Raises :class:`LLMNotConfiguredError` when no token is configured, and
        :class:`LLMServiceError` on any transport/HTTP failure or a response
        that isn't parseable JSON.
        """
        token = (settings.huggingface_token or "").strip()
        if not token:
            raise LLMNotConfiguredError()

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        start_time = time.time()
        error = None
        body = None
        self.last_usage = None
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions", headers=headers, json=payload
                )

            if response.status_code != 200:
                error = f"HTTP {response.status_code}"
                raise LLMServiceError(f"Hugging Face API returned HTTP {response.status_code}.")

            body = response.json()
            self.last_usage = tt.extract_usage(body)
            content = body["choices"][0]["message"]["content"]
            return self._extract_json(content)

        except httpx.HTTPError as exc:
            error = str(exc)
            raise LLMServiceError() from exc
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            error = f"Invalid payload: {type(exc).__name__}"
            raise LLMServiceError("Hugging Face API returned an unexpected payload shape.") from exc
        finally:
            duration_ms = (time.time() - start_time) * 1000
            try:
                usage = tt.extract_usage(body) if body else (0, 0, 0, 0)
                tt.get_token_tracer().record(
                    role="chat",
                    model=self._model,
                    call_type="chat",
                    duration_ms=duration_ms,
                    usage=usage,
                    provider="huggingface",
                    endpoint="java_version_recommendation",
                    error=error,
                )
            except Exception:
                pass

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
