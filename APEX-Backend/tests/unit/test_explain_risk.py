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


@pytest.mark.asyncio
async def test_explain_risk_uses_user_settings_groq() -> None:
    from app.api.deps import User
    from app.infrastructure.llm.chat_llm import ChatLLM
    from app.infrastructure.llm.groq_client import GroqClient
    from app.core.context import llm_values_ctx

    mock_chat = MagicMock(spec=ChatLLM)
    mock_chat.last_provider = "groq"
    async def mock_stream(*args, **kwargs):
        ctx = llm_values_ctx.get()
        assert ctx.get("groq_api_key") == "gsk_user_configured_key_123"
        yield '{"risk_explanation": "Java 8 to 17 upgrade explained via user Groq credentials."}'
    mock_chat.stream_chat = mock_stream

    mock_hf = MagicMock()
    mock_hf.chat_json = AsyncMock(side_effect=RuntimeError("HF not configured"))

    use_case = ExplainRiskUseCase(llm_client=mock_hf, chat_llm=mock_chat)
    user = User(
        id="user_123",
        email="test@company.com",
        llm_values={"groq_api_key": "gsk_user_configured_key_123", "groq_model": "llama-3.3-70b"}
    )
    request = RiskExplanationRequest(
        risk_level="medium",
        source_java_version="8",
        build_tool="maven",
        has_tests=True,
    )

    result = await use_case.execute(request, current_user=user)
    assert result.risk_explanation == "Java 8 to 17 upgrade explained via user Groq credentials."
    assert result.provider_used == "groq"


@pytest.mark.asyncio
async def test_explain_risk_uses_user_settings_huggingface() -> None:
    from app.api.deps import User
    from app.infrastructure.llm.huggingface_client import HuggingFaceClient
    from app.core.context import llm_values_ctx

    mock_hf = MagicMock(spec=HuggingFaceClient)
    async def mock_chat_json(system_prompt, user_prompt):
        ctx = llm_values_ctx.get()
        assert ctx.get("huggingface_api_key") == "hf_user_configured_token_456"
        return {"risk_explanation": "Java 11 to 21 upgrade explained via user HuggingFace credentials."}
    mock_hf.chat_json = mock_chat_json

    use_case = ExplainRiskUseCase(llm_client=mock_hf)
    user = User(
        id="user_456",
        email="test2@company.com",
        llm_values={"huggingface_api_key": "hf_user_configured_token_456", "huggingface_model": "meta-llama/Llama-3.1-8B-Instruct:novita"}
    )
    request = RiskExplanationRequest(
        risk_level="low",
        source_java_version="11",
        build_tool="maven",
        has_tests=True,
    )

    result = await use_case.execute(request, current_user=user)
    assert result.risk_explanation == "Java 11 to 21 upgrade explained via user HuggingFace credentials."
    assert result.provider_used == "huggingface"
