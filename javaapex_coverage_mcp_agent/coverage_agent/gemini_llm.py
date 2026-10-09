"""Gemini adapter for the JaCoCo coverage agent.

Uses Google AI Studio's free tier (no credit card, API key only).
Recommended model: gemini-2.5-flash — 1M context, ~1500 req/day free,
far more headroom than a local 7B model for large coverage prompts
(source + existing tests + gaps can exceed 30k tokens).

Setup:
    1. Get a free key at https://aistudio.google.com/apikey
    2. setx GEMINI_API_KEY "your-key-here"   (new terminal picks it up)
       or  $env:GEMINI_API_KEY="your-key-here"  (current session only)

Env overrides:
    GEMINI_API_KEY   (required)
    GEMINI_MODEL     (default "gemini-2.5-flash")
    GEMINI_TEMP      (default "0.2")
    GEMINI_THINKING  (default "0" — disable thinking for strict JSON;
                      set e.g. "1024" to allow a thinking budget)
    LLM_MAX_RETRIES / LLM_RETRY_BASE_DELAY / LLM_RETRY_MAX_DELAY
                      (429/503 backoff; see coverage_agent.retry)
"""

from __future__ import annotations

import os

from .retry import await_with_retries


DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = (
    "You are a JSON-generating bot. "
    "Return ONLY valid JSON with shape "
    '{"changes": [{"path": "src/test/java/...", "action": "create|replace", '
    '"content": "complete Java source"}], "reasoning": "..."}. '
    "Never wrap output in markdown. Never add commentary outside the JSON."
)


class GeminiCoverageLLM:
    """CoverageLLM implementation backed by Gemini free tier.

    Compatible with ``JaCoCoCoverageAgent``:
        agent = JaCoCoCoverageAgent(llm=GeminiCoverageLLM())
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        thinking_budget: int | None = None,
        timeout: float = 300.0,
    ):
        self.model = model or DEFAULT_MODEL
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.temperature = float(
            os.getenv("GEMINI_TEMP", str(temperature if temperature is not None else 0.2))
        )
        raw_budget = os.getenv(
            "GEMINI_THINKING",
            str(thinking_budget if thinking_budget is not None else 0),
        )
        self.thinking_budget = int(raw_budget)
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Get a free key at "
                "https://aistudio.google.com/apikey and set "
                'GEMINI_API_KEY="your-key-here".'
            )

    async def generate(self, prompt: str) -> str:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "The 'google-genai' python package is not installed. "
                "Run: pip install google-genai"
            ) from exc

        client = genai.Client(api_key=self.api_key, http_options={"timeout": int(self.timeout * 1000)})
        config_kwargs: dict = {
            "system_instruction": SYSTEM_PROMPT,
            "response_mime_type": "application/json",
            "temperature": self.temperature,
        }
        if self.thinking_budget > 0:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=self.thinking_budget
            )
        else:
            # Disable thinking so small Flash outputs stay strict JSON.
            config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

        response = await await_with_retries(
            lambda: client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            ),
            what=f"Gemini {self.model}",
        )
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response.")
        return text
