from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.application.use_cases.explain_risk import ExplainRiskUseCase, get_default_risk_explanation
from app.schemas.java_version_schema import RiskExplanationRequest


@pytest.mark.asyncio
async def test_explain_risk_returns_llm_generated_text() -> None:
    mock_llm = MagicMock()
    mock_llm.chat_json = AsyncMock(return_value={
        "risk_explanation": "The project uses Maven with Java 17 and contains automated JUnit tests, ensuring baseline modernization readiness."
    })

    use_case = ExplainRiskUseCase(llm_client=mock_llm)
    request = RiskExplanationRequest(
        risk_level="low",
        source_java_version="17",
        build_tool="maven",
        has_tests=True,
    )

    result = await use_case.execute(request)
    assert result.risk_level == "low"
    assert result.risk_explanation == "The project uses Maven with Java 17 and contains automated JUnit tests, ensuring baseline modernization readiness."
    assert result.provider_used == "huggingface"


@pytest.mark.asyncio
async def test_explain_risk_falls_back_gracefully_on_error() -> None:
    mock_llm = MagicMock()
    mock_llm.chat_json = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    mock_chat = MagicMock()
    async def mock_stream(*args, **kwargs):
        raise RuntimeError("Fallback LLM unavailable")
        yield "" # make it an async generator
    mock_chat.stream_chat = mock_stream

    use_case = ExplainRiskUseCase(llm_client=mock_llm, chat_llm=mock_chat)
    request = RiskExplanationRequest(
        risk_level="medium",
        source_java_version="8",
        build_tool="maven",
        has_tests=False,
    )

    result = await use_case.execute(request)
    assert result.risk_level == "medium"
    assert result.risk_explanation == get_default_risk_explanation("medium")
    assert result.provider_used == "heuristic"
