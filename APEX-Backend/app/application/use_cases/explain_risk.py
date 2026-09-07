"""Risk Explanation use case (LLM-backed with deterministic fallback).

Explains the calculated migration risk level (LOW/MEDIUM/HIGH) based on the
repository's real static analysis factors (build tool, Java version, automated
tests, dependencies, frameworks). Does NOT modify or recalculate the risk level.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.context import user_id_ctx
from app.infrastructure.llm.huggingface_client import HuggingFaceClient
from app.infrastructure.llm.prompt_templates import (
    RISK_EXPLANATION_SYSTEM_PROMPT,
    build_risk_explanation_prompt,
)
from app.infrastructure.persistence.models import User
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
    def __init__(self, llm_client: HuggingFaceClient | None = None) -> None:
        self._llm = llm_client or HuggingFaceClient()

    async def execute(
        self,
        request: RiskExplanationRequest,
        db: Session | None = None,
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
        if current_user:
            user_token = user_id_ctx.set(current_user.id)

        try:
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
            logger.info("LLM risk explanation generation failed (%s); using fallback.", exc)
            return RiskExplanationResponse(
                risk_level=risk_level,
                risk_explanation=fallback_text,
                provider_used="heuristic",
            )
        finally:
            if user_token:
                user_id_ctx.reset(user_token)
