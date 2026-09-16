from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.application.use_cases.recommend_java_version import RecommendJavaVersionUseCase
from app.schemas.java_version_schema import JavaVersionRecommendationRequest


@pytest.mark.asyncio
async def test_recommend_java_version_uses_fallback_on_error() -> None:
    mock_llm = MagicMock()
    mock_llm.chat_json = AsyncMock(side_effect=RuntimeError("HF Down"))
    
    mock_chat = MagicMock()
    async def mock_stream(*args, **kwargs):
        raise RuntimeError("Fallback LLM Down")
        yield ""
    mock_chat.stream_chat = mock_stream

    use_case = RecommendJavaVersionUseCase(llm_client=mock_llm, chat_llm=mock_chat)
    request = JavaVersionRecommendationRequest(
        source_java_version="8",
        build_tool="maven",
        has_tests=True,
    )

    result = await use_case.execute(request)
    assert result["recommended_target_version"] in ["17", "21"]
    assert result["provider_used"] == "rule_based_fallback"


def test_recommend_java_version_fallback_logic() -> None:
    # Test _fallback with already_at_latest
    result = RecommendJavaVersionUseCase._fallback(21, ["17", "21", "25"], True)
    assert result["recommended_target_version"] == "21"
    
    # Test _fallback from old version
    result2 = RecommendJavaVersionUseCase._fallback(8, ["17", "21", "25"], False)
    assert result2["recommended_target_version"] in ["17", "21", "25"]
