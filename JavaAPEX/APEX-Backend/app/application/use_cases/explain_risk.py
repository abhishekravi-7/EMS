"""Risk Explanation use case (LLM-backed with deterministic fallback).

Explains the calculated migration risk level (LOW/MEDIUM/HIGH) based on the
repository's real static analysis factors (build tool, Java version, automated
tests, dependencies, frameworks). Does NOT modify or recalculate the risk level.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.api.deps import User
from app.core.context import user_id_ctx, llm_values_ctx
from app.core.exceptions import LLMResponseInvalidError
from app.infrastructure.llm.chat_llm import ChatLLM
from app.infrastructure.llm.huggingface_client import HuggingFaceClient
from app.infrastructure.llm.prompt_templates import (
    RISK_EXPLANATION_SYSTEM_PROMPT,
    build_risk_explanation_prompt,
)
from app.schemas.java_version_schema import RiskExplanationRequest, RiskExplanationResponse

logger = logging.getLogger(__name__)


def get_default_risk_explanation(risk_level: str) -> str:
    """Fallback explanation matching the standard template sentences."""
    normalized = (risk_level or "").strip().lower()
    if normalized == "low":
        return "The project is already on a modern migration path with build tooling and tests detected."
    if normalized == "medium":
        return "The project has build tooling, but tests are missing or limited."
    return "The project needs extra review because build tooling or Java metadata was not detected."


class ExplainRiskUseCase:
    def __init__(
        self,
        llm_client: HuggingFaceClient | None = None,
        chat_llm: ChatLLM | None = None,
    ) -> None:
        self._llm = llm_client or HuggingFaceClient()
        self._chat_llm = chat_llm or ChatLLM()

    async def execute(
        self,
        request: RiskExplanationRequest,
        db: Any = None,
        current_user: User | None = None,
    ) -> RiskExplanationResponse:
        risk_level = (request.risk_level or "low").strip().lower()
        fallback_text = get_default_risk_explanation(risk_level)

        system_prompt = RISK_EXPLANATION_SYSTEM_PROMPT
        user_prompt = build_risk_explanation_prompt(
            risk_level=risk_level,
            source_java_version=request.source_java_version,
            build_tool=request.build_tool,
            has_tests=request.has_tests,
            dependencies=request.dependencies,
            frameworks=request.frameworks,
            api_endpoint_count=request.api_endpoint_count,
        )

        user_token = None
        llm_token = None
        if current_user:
            user_token = user_id_ctx.set(current_user.id)
            if getattr(current_user, "llm_values", None):
                llm_token = llm_values_ctx.set(current_user.llm_values)

        try:
            try:
                logger.info("[RiskExplanation] Attempting Hugging Face (primary)")
                raw = await self._llm.chat_json(system_prompt, user_prompt)
                explanation = str(raw.get("risk_explanation") or "").strip()
                if not explanation:
                    explanation = fallback_text

                return RiskExplanationResponse(
                    risk_level=risk_level,
                    risk_explanation=explanation,
                    provider_used="huggingface",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[RiskExplanation] Hugging Face failed, falling back to Strategy Chat LLM (Groq/Ollama). Reason: %s",
                    exc,
                )
                # Fallback to the same LLM logic used by the chatbot (Groq -> Ollama)
                response_text = ""
                async for chunk in self._chat_llm.stream_chat(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    endpoint="risk_explanation_fallback",
                ):
                    response_text += chunk

                raw = self._extract_json(response_text)
                explanation = str(raw.get("risk_explanation") or "").strip()
                if not explanation:
                    explanation = fallback_text

                return RiskExplanationResponse(
                    risk_level=risk_level,
                    risk_explanation=explanation,
                    provider_used=self._chat_llm.last_provider or "fallback",
                )
        except Exception as exc:  # noqa: BLE001
            logger.info("[RiskExplanation] All LLM providers failed (%s); using heuristic fallback.", exc)
            return RiskExplanationResponse(
                risk_level=risk_level,
                risk_explanation=fallback_text,
                provider_used="heuristic",
            )
        finally:
            if user_token:
                user_id_ctx.reset(user_token)
            if llm_token:
                llm_values_ctx.reset(llm_token)

    @staticmethod
    def _extract_json(content: str) -> dict:
        text = (content or "").strip()
        # Some models wrap JSON in ```json ... ``` fences
        if text.startswith("```"):
            text = text.strip("`")
            if text[:4].lower() == "json":
                text = text[4:]

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise LLMResponseInvalidError("Fallback model response did not contain JSON.")

        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMResponseInvalidError("Fallback model response was not valid JSON.") from exc
