"""Ollama adapter for the JaCoCo coverage agent.

Uses a local Ollama model (default: qwen2.5-coder:7b) to generate
test-only JSON changes. Forces JSON mode via ``format="json"`` so
small coder models reliably return parseable output.

Env overrides:
    OLLAMA_MODEL  (default "qwen2.5-coder:7b")
    OLLAMA_HOST   (default "http://localhost:11434")
    OLLAMA_TEMP   (default "0.1")
    OLLAMA_NUM_CTX (default "32768")
    LLM_MAX_RETRIES / LLM_RETRY_BASE_DELAY / LLM_RETRY_MAX_DELAY
                      (429/503 backoff; see coverage_agent.retry)
"""

from __future__ import annotations

import os

from .retry import await_with_retries


DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")
DEFAULT_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

SYSTEM_PROMPT = (
    "You are a JSON-generating bot. "
    "Return ONLY valid JSON with shape "
    '{"changes": [{"path": "src/test/java/...", "action": "create|replace", '
    '"content": "complete Java source"}], "reasoning": "..."}. '
    "Never wrap output in markdown. Never add commentary outside the JSON."
)


class OllamaCoverageLLM:
    """CoverageLLM implementation backed by local Ollama.

    Compatible with ``JaCoCoCoverageAgent`` and ``JsonLLMAdapter`` usage:
        agent = JaCoCoCoverageAgent(llm=OllamaCoverageLLM())
    """

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        temperature: float | None = None,
        num_ctx: int | None = None,
        timeout: float = 300.0,
    ):
        self.model = model or DEFAULT_MODEL
        self.host = host or DEFAULT_HOST
        self.temperature = float(
            os.getenv("OLLAMA_TEMP", str(temperature if temperature is not None else 0.1))
        )
        self.num_ctx = int(
            os.getenv("OLLAMA_NUM_CTX", str(num_ctx if num_ctx is not None else 32768))
        )
        self.timeout = timeout

    async def generate(self, prompt: str) -> str:
        try:
            from ollama import AsyncClient
        except ImportError as exc:
            raise RuntimeError(
                "The 'ollama' python package is not installed. "
                "Run: pip install ollama"
            ) from exc

        client = AsyncClient(host=self.host, timeout=self.timeout)
        response = await await_with_retries(
            lambda: client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                format="json",
                options={"temperature": self.temperature, "num_ctx": self.num_ctx},
            ),
            what=f"Ollama {self.model}",
        )
        # ChatResponse.message.content holds the JSON string.
        try:
            return response.message.content or "{}"
        except AttributeError:
            # Fallback for dict-style responses in older client versions.
            return response["message"]["content"]  # type: ignore[index]
