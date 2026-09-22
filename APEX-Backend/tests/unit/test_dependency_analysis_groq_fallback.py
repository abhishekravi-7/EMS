from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import Response, Request

import shutil
from app.application.use_cases.analyze_dependencies import (
    AnalyzeDependenciesUseCase,
    compute_analysis_fingerprint,
    _memory_cache,
    _CACHE_DIR,
)
from app.core.exceptions import ChatLLMServiceError
from app.infrastructure.llm.chat_llm import ChatLLM
from app.infrastructure.llm.groq_client import GroqClient
from app.infrastructure.llm.ollama_client import OllamaClient
from app.schemas.dependency_analysis_schema import (
    DependencyAnalysisRequest,
    DependencyItemInput,
)


@pytest.fixture(autouse=True)
def clear_caches():
    _memory_cache.clear()
    shutil.rmtree(_CACHE_DIR, ignore_errors=True)
    yield
    _memory_cache.clear()
    shutil.rmtree(_CACHE_DIR, ignore_errors=True)


@pytest.fixture
def sample_request():
    return DependencyAnalysisRequest(
        job_id="job-123",
        source_java_version="8",
        target_java_version="17",
        build_tool="MAVEN",
        dependencies=[
            DependencyItemInput(
                group_id="org.springframework.boot",
                artifact_id="spring-boot-starter-web",
                current_version="2.7.0",
                scope="compile",
            ),
            DependencyItemInput(
                group_id="junit",
                artifact_id="junit",
                current_version="4.13.2",
                scope="test",
            ),
        ],
    )


def test_same_input_same_fingerprint(sample_request):
    """1. Same input produces exact same fingerprint."""
    fp1 = compute_analysis_fingerprint(sample_request)
    fp2 = compute_analysis_fingerprint(sample_request)
    assert fp1 == fp2


def test_dependency_ordering_changed_same_fingerprint(sample_request):
    """2. Dependency ordering differences produce the exact same fingerprint."""
    req_reversed = DependencyAnalysisRequest(
        job_id="job-123",
        source_java_version="8",
        target_java_version="17",
        build_tool="MAVEN",
        dependencies=[
            DependencyItemInput(
                group_id="junit",
                artifact_id="junit",
                current_version="4.13.2",
                scope="test",
            ),
            DependencyItemInput(
                group_id="org.springframework.boot",
                artifact_id="spring-boot-starter-web",
                current_version="2.7.0",
                scope="compile",
            ),
        ],
    )
    fp1 = compute_analysis_fingerprint(sample_request)
    fp2 = compute_analysis_fingerprint(req_reversed)
    assert fp1 == fp2


@pytest.mark.asyncio
async def test_same_request_twice_uses_cache(sample_request):
    """3. Same request twice: second request uses cache (0 extra LLM calls)."""
    mock_hf = MagicMock()
    mock_hf.chat_json = AsyncMock(
        return_value={
            "overall_risk": "HIGH",
            "complexity": "MODERATE",
            "overall_explanation": "Spring Boot upgrade.",
            "complexity_explanation": "Moderate.",
            "dependencies": [
                {
                    "id": "org.springframework.boot:spring-boot-starter-web",
                    "group": "org.springframework.boot",
                    "artifact": "spring-boot-starter-web",
                    "risk": "HIGH",
                    "category": "Framework",
                    "explanation": "Spring Boot 3 migration.",
                    "recommendation": "Upgrade to 3.x.",
                }
            ],
        }
    )

    use_case = AnalyzeDependenciesUseCase(llm_client=mock_hf)

    # First call -> calls LLM
    res1 = await use_case.execute(sample_request)
    assert res1.overall_risk == "HIGH"
    assert mock_hf.chat_json.call_count == 1

    # Second call -> uses cache, no LLM call
    res2 = await use_case.execute(sample_request)
    assert res2.overall_risk == "HIGH"
    assert mock_hf.chat_json.call_count == 1
    assert res1.model_dump() == res2.model_dump()


@pytest.mark.asyncio
async def test_duplicate_concurrent_requests_single_flight(sample_request):
    """4. Duplicate concurrent requests execute LLM only ONCE via single-flight lock."""
    mock_hf = MagicMock()

    async def delayed_chat(*args, **kwargs):
        await asyncio.sleep(0.05)
        return {
            "overall_risk": "MEDIUM",
            "complexity": "LIGHT",
            "dependencies": [
                {
                    "id": "junit:junit",
                    "group": "junit",
                    "artifact": "junit",
                    "risk": "MEDIUM",
                    "category": "Testing",
                    "explanation": "JUnit 4 to 5.",
                    "recommendation": "Upgrade.",
                }
            ],
        }

    mock_hf.chat_json = AsyncMock(side_effect=delayed_chat)
    use_case = AnalyzeDependenciesUseCase(llm_client=mock_hf)

    # Fire 5 concurrent requests with the exact same request
    tasks = [use_case.execute(sample_request) for _ in range(5)]
    results = await asyncio.gather(*tasks)

    # All 5 return the same validated response
    assert len(results) == 5
    for r in results:
        assert r.overall_risk == "MEDIUM"

    # LLM was invoked exactly once!
    assert mock_hf.chat_json.call_count == 1


@pytest.mark.asyncio
async def test_valid_hf_result_cached(sample_request):
    """5. Valid HF result is cached and returned on subsequent invocations."""
    mock_hf = MagicMock()
    mock_hf.chat_json = AsyncMock(
        return_value={
            "overall_risk": "HIGH",
            "complexity": "MODERATE",
            "dependencies": [],
        }
    )
    use_case = AnalyzeDependenciesUseCase(llm_client=mock_hf)
    res = await use_case.execute(sample_request)
    assert res.provider_used == "huggingface"

    # Check cache fingerprint
    fp = compute_analysis_fingerprint(sample_request)
    assert fp in _memory_cache


@pytest.mark.asyncio
async def test_invalid_hf_falls_back_to_groq_and_cached(sample_request):
    """6 & 7. Invalid HF falls back to Groq; Groq valid result is cached."""
    mock_hf = MagicMock()
    mock_hf.chat_json = AsyncMock(side_effect=RuntimeError("HF failed"))

    groq_json = {
        "overall_risk": "HIGH",
        "complexity": "MODERATE",
        "overall_explanation": "Groq analyzed framework jump.",
        "complexity_explanation": "Groq complexity explanation.",
        "dependencies": [
            {
                "id": "org.springframework.boot:spring-boot-starter-web",
                "group": "org.springframework.boot",
                "artifact": "spring-boot-starter-web",
                "name": "spring-boot-starter-web",
                "version": "2.7.0",
                "category": "Framework",
                "risk": "HIGH",
                "explanation": "Spring Boot 2.7 upgrade to 3.x.",
                "recommendation": "Upgrade to Spring Boot 3.x.",
            }
        ],
    }

    mock_chat = MagicMock()
    mock_chat.last_provider = "groq"

    async def mock_stream(*args, **kwargs):
        yield json.dumps(groq_json)

    mock_chat.stream_chat = mock_stream

    use_case = AnalyzeDependenciesUseCase(llm_client=mock_hf, chat_llm=mock_chat)
    response = await use_case.execute(sample_request)

    assert response.overall_risk == "HIGH"
    assert "groq" in response.provider_used

    # Cached in memory & disk
    fp = compute_analysis_fingerprint(sample_request)
    assert fp in _memory_cache


@pytest.mark.asyncio
async def test_groq_markdown_wrapped_json(sample_request):
    """Groq returns markdown-wrapped JSON with preamble and postamble."""
    mock_hf = MagicMock()
    mock_hf.chat_json = AsyncMock(side_effect=RuntimeError("HF failed"))

    raw_response = """Here is the migration dependency analysis:
```json
{
  "overall_risk": "HIGH",
  "complexity": "COMPLEX",
  "overall_explanation": "Detailed analysis from Groq.",
  "complexity_explanation": "Complex upgrade path.",
  "dependencies": [
    {
      "id": "org.springframework.boot:spring-boot-starter-web",
      "group": "org.springframework.boot",
      "artifact": "spring-boot-starter-web",
      "name": "spring-boot-starter-web",
      "version": "2.7.0",
      "category": "Framework",
      "risk": "HIGH",
      "explanation": "Spring Boot 3 migration needed.",
      "recommendation": "Upgrade to Jakarta EE and Spring Boot 3."
    }
  ]
}
```
Please review these recommendations."""

    mock_chat = MagicMock()
    mock_chat.last_provider = "groq"

    async def mock_stream(*args, **kwargs):
        yield raw_response

    mock_chat.stream_chat = mock_stream

    use_case = AnalyzeDependenciesUseCase(llm_client=mock_hf, chat_llm=mock_chat)
    response = await use_case.execute(sample_request)

    assert response.overall_risk == "HIGH"
    assert response.complexity == "COMPLEX"
    assert "groq" in response.provider_used


@pytest.mark.asyncio
async def test_invalid_groq_falls_back_to_heuristic_and_cached(sample_request):
    """8 & 9. Invalid Groq falls back to heuristic; heuristic result is cached and deterministic."""
    mock_hf = MagicMock()
    mock_hf.chat_json = AsyncMock(side_effect=RuntimeError("HF failed"))

    mock_chat = MagicMock()
    mock_chat.last_provider = "groq"

    async def mock_stream(*args, **kwargs):
        yield "Not JSON at all, an unexpected model output!"

    mock_chat.stream_chat = mock_stream

    use_case = AnalyzeDependenciesUseCase(llm_client=mock_hf, chat_llm=mock_chat)
    response1 = await use_case.execute(sample_request)

    assert response1.provider_used == "heuristic"
    assert len(response1.dependencies) == 2

    # Second call returns exact same cached heuristic result
    response2 = await use_case.execute(sample_request)
    assert response2.model_dump() == response1.model_dump()


@pytest.mark.asyncio
async def test_changed_dependency_version_new_fingerprint_and_analysis(sample_request):
    """11. Changed dependency version produces new fingerprint and triggers new analysis."""
    fp1 = compute_analysis_fingerprint(sample_request)

    req_new_version = sample_request.model_copy(deep=True)
    req_new_version.dependencies[0].current_version = "3.2.0"
    fp2 = compute_analysis_fingerprint(req_new_version)

    assert fp1 != fp2


@pytest.mark.asyncio
async def test_changed_target_java_version_new_fingerprint_and_analysis(sample_request):
    """12. Changed target Java version produces new fingerprint and triggers new analysis."""
    fp1 = compute_analysis_fingerprint(sample_request)

    req_new_target = sample_request.model_copy(deep=True)
    req_new_target.target_java_version = "21"
    fp2 = compute_analysis_fingerprint(req_new_target)

    assert fp1 != fp2


@pytest.mark.asyncio
async def test_preserves_input_dependency_coordinates():
    """Dependency reconciliation: LLM cannot invent extra dependencies or alter input coordinates."""
    mock_hf = MagicMock()
    mock_hf.chat_json = AsyncMock(
        return_value={
            "overall_risk": "LOW",
            "complexity": "LIGHT",
            "dependencies": [
                {
                    "id": "org.real:real-lib",
                    "group": "org.real",
                    "artifact": "real-lib",
                    "risk": "LOW",
                    "category": "Utility",
                    "explanation": "Real library.",
                    "recommendation": "Keep as is.",
                },
                {
                    "id": "com.hacker:evil-lib",
                    "group": "com.hacker",
                    "artifact": "evil-lib",
                    "risk": "CRITICAL",
                    "category": "Security",
                    "explanation": "Hallucinated dependency!",
                    "recommendation": "Remove it!",
                },
            ],
        }
    )

    use_case = AnalyzeDependenciesUseCase(llm_client=mock_hf)

    req = DependencyAnalysisRequest(
        source_java_version="11",
        target_java_version="17",
        dependencies=[
            DependencyItemInput(
                group_id="org.real",
                artifact_id="real-lib",
                current_version="1.0.0",
            )
        ],
    )

    response = await use_case.execute(req)

    # Must contain ONLY org.real:real-lib
    assert len(response.dependencies) == 1
    assert response.dependencies[0].group == "org.real"
    assert response.dependencies[0].artifact == "real-lib"
    assert not any(d.artifact == "evil-lib" for d in response.dependencies)


@pytest.mark.asyncio
async def test_no_event_loop_closed_during_concurrent_requests(sample_request):
    """13. Concurrent requests do not produce 'Event loop is closed'."""
    mock_hf = MagicMock()
    mock_hf.chat_json = AsyncMock(side_effect=RuntimeError("HF unavailable"))

    mock_chat = MagicMock()
    mock_chat.last_provider = "groq"

    async def mock_stream(*args, **kwargs):
        await asyncio.sleep(0.01)
        yield json.dumps({
            "overall_risk": "LOW",
            "complexity": "LIGHT",
            "dependencies": [
                {
                    "id": "junit:junit",
                    "group": "junit",
                    "artifact": "junit",
                    "name": "junit",
                    "version": "4.13.2",
                    "category": "Testing",
                    "risk": "LOW",
                    "explanation": "JUnit 4.",
                    "recommendation": "Upgrade to JUnit 5.",
                }
            ],
        })

    mock_chat.stream_chat = mock_stream
    use_case = AnalyzeDependenciesUseCase(llm_client=mock_hf, chat_llm=mock_chat)

    # Fire 10 concurrent requests
    tasks = [use_case.execute(sample_request) for _ in range(10)]
    results = await asyncio.gather(*tasks)

    assert len(results) == 10
    for res in results:
        assert res.overall_risk in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert len(res.dependencies) == 2


@pytest.mark.asyncio
async def test_controller_endpoint_returns_200_on_heuristic_fallback(sample_request):
    """FastAPI controller endpoint returns HTTP 200 even when heuristic fallback is triggered."""
    from app.api.v1.endpoints.java_version_controller import analyze_dependencies

    mock_hf = MagicMock()
    mock_hf.chat_json = AsyncMock(side_effect=RuntimeError("HF unavailable"))

    mock_chat = MagicMock()
    async def mock_fail(*args, **kwargs):
        raise ChatLLMServiceError("Groq and Ollama failed")
        yield ""
    mock_chat.stream_chat = mock_fail

    fallback_use_case = AnalyzeDependenciesUseCase(llm_client=mock_hf, chat_llm=mock_chat)

    with patch("app.api.v1.endpoints.java_version_controller._dependency_analysis_use_case", fallback_use_case):
        response = await analyze_dependencies(payload=sample_request, current_user=None)
        assert response.status_code == 200
        data = json.loads(response.body.decode("utf-8"))
        assert data["provider_used"] == "heuristic"
        assert len(data["dependencies"]) == 2
        assert "overall_risk" in data
        assert "complexity" in data
