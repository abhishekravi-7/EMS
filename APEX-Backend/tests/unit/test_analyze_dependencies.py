import pytest
from unittest.mock import AsyncMock, MagicMock

from app.application.use_cases.analyze_dependencies import AnalyzeDependenciesUseCase
from app.schemas.dependency_analysis_schema import (
    DependencyAnalysisRequest,
    DependencyItemInput,
)


@pytest.mark.asyncio
async def test_analyze_dependencies_with_mock_llm():
    # Setup mock LLM client
    mock_llm_client = MagicMock()
    mock_llm_client.is_configured.return_value = True

    llm_payload = {
        "dependencies": [
            {
                "id": "org.springframework.boot:spring-boot-starter-web",
                "group": "org.springframework.boot",
                "artifact": "spring-boot-starter-web",
                "name": "spring-boot-starter-web",
                "version": "2.7.0",
                "risk": "HIGH",
                "category": "Framework",
                "explanation": "Spring Boot 2.7.x requires upgrade to 3.x for Java 17/21 compatibility.",
                "recommendation": "Upgrade to Spring Boot 3.2+ and update imports from javax.* to jakarta.*.",
            },
            {
                "id": "junit:junit",
                "group": "junit",
                "artifact": "junit",
                "name": "junit",
                "version": "4.13.2",
                "risk": "MEDIUM",
                "category": "Testing",
                "explanation": "JUnit 4 legacy runner.",
                "recommendation": "Migrate to JUnit Jupiter 5.",
            },
            {
                "id": "org.projectlombok:lombok",
                "group": "org.projectlombok",
                "artifact": "lombok",
                "name": "lombok",
                "version": "1.18.24",
                "risk": "LOW",
                "category": "Utility",
                "explanation": "Requires version bump for JDK 21 bytecode compatibility.",
                "recommendation": "Update to 1.18.30+.",
            },
        ],
        "overall_risk": "HIGH",
        "complexity": "MODERATE",
        "overall_explanation": "Framework upgrade required.",
        "complexity_explanation": "Moderate effort needed.",
    }

    mock_llm_client.chat_json = AsyncMock(return_value=llm_payload)

    use_case = AnalyzeDependenciesUseCase(llm_client=mock_llm_client)

    request = DependencyAnalysisRequest(
        source_java_version="8",
        target_java_version="17",
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
            DependencyItemInput(
                group_id="org.projectlombok",
                artifact_id="lombok",
                current_version="1.18.24",
                scope="provided",
            ),
        ],
    )

    response = await use_case.execute(request)

    assert response is not None
    assert len(response.dependencies) == 3
    assert response.counts.total == 3
    assert response.counts.high == 1
    assert response.counts.medium == 1
    assert response.counts.low == 1
    assert response.counts.critical == 0
    assert response.overall_risk == "HIGH"
    assert response.complexity == "MODERATE"

    dep1 = response.dependencies[0]
    assert dep1.group == "org.springframework.boot"
    assert dep1.artifact == "spring-boot-starter-web"
    assert dep1.version == "2.7.0"
    assert dep1.risk == "HIGH"
    assert dep1.category == "Framework"
    assert "javax.* to jakarta.*" in dep1.recommendation


@pytest.mark.asyncio
async def test_analyze_dependencies_fallback_when_llm_unconfigured():
    mock_llm_client = MagicMock()
    mock_llm_client.is_configured.return_value = False
    mock_llm_client.chat_json = AsyncMock(side_effect=RuntimeError("LLM unconfigured"))

    mock_chat = MagicMock()
    async def mock_stream(*args, **kwargs):
        raise RuntimeError("Fallback LLM unavailable")
        yield ""
    mock_chat.stream_chat = mock_stream

    use_case = AnalyzeDependenciesUseCase(llm_client=mock_llm_client, chat_llm=mock_chat)

    request = DependencyAnalysisRequest(
        source_java_version="8",
        target_java_version="17",
        dependencies=[
            DependencyItemInput(
                group_id="javax.servlet",
                artifact_id="javax.servlet-api",
                current_version="3.1.0",
                scope="compile",
            ),
            DependencyItemInput(
                group_id="org.apache.commons",
                artifact_id="commons-lang3",
                current_version="3.12.0",
                scope="compile",
            ),
        ],
    )

    response = await use_case.execute(request)

    assert response is not None
    assert len(response.dependencies) == 2
    assert response.counts.total == 2
    # javax should trigger CRITICAL or HIGH in fallback
    javax_dep = next(d for d in response.dependencies if "javax.servlet" in d.group or "javax" in d.artifact)
    assert javax_dep.risk == "CRITICAL"
    assert "jakarta" in javax_dep.recommendation.lower()


@pytest.mark.asyncio
async def test_analyze_dependencies_batching():
    mock_llm_client = MagicMock()
    mock_llm_client.is_configured.return_value = True

    mock_llm_client.chat_json = AsyncMock(
        return_value={
            "dependencies": [],
            "overall_risk": "MEDIUM",
            "complexity": "MODERATE",
            "overall_explanation": "Batch test.",
            "complexity_explanation": "Batch complexity.",
        }
    )

    use_case = AnalyzeDependenciesUseCase(llm_client=mock_llm_client)

    # 45 dependencies should be split into batches (batch size = 5, total = 9 batches)
    deps = [
        DependencyItemInput(
            group_id="com.example",
            artifact_id=f"lib-{i}",
            current_version="1.0.0",
        )
        for i in range(45)
    ]

    request = DependencyAnalysisRequest(
        source_java_version="11",
        target_java_version="21",
        dependencies=deps,
    )

    response = await use_case.execute(request)

    assert len(response.dependencies) == 45
    assert response.counts.total == 45
    assert mock_llm_client.chat_json.call_count == 9
