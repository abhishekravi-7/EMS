"""Target Java Version Recommendation endpoint (unversioned - mounted at ``/api``).

The Strategy step calls this immediately after Discovery detects the real
source Java version from the repo's build files. This controller forwards
that detected version + project metadata to a Hugging Face-hosted LLM and
returns a fresh, non-cached recommendation every time.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.application.use_cases.analyze_dependencies import AnalyzeDependenciesUseCase
from app.application.use_cases.explain_risk import ExplainRiskUseCase
from app.application.use_cases.recommend_java_version import RecommendJavaVersionUseCase
from app.core.exceptions import JavaVersionRecommendationError
from app.infrastructure.persistence.database import get_db_optional
from app.schemas.dependency_analysis_schema import (
    DependencyAnalysisRequest,
    DependencyAnalysisResponse,
)
from app.schemas.java_version_schema import (
    JavaVersionRecommendationRequest,
    JavaVersionRecommendationResponse,
    RiskExplanationRequest,
    RiskExplanationResponse,
)

router = APIRouter(tags=["java-version-recommendation"])

_use_case = RecommendJavaVersionUseCase()
_explain_risk_use_case = ExplainRiskUseCase()
_dependency_analysis_use_case = AnalyzeDependenciesUseCase()


@router.post(
    "/java-version-recommendation",
    response_model=JavaVersionRecommendationResponse,
    summary="AI-recommend a target Java version, given the detected source version and project metadata.",
)
async def recommend_java_version(
    payload: JavaVersionRecommendationRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    try:
        result = await _use_case.execute(payload, db=db, current_user=current_user)
    except JavaVersionRecommendationError as exc:
        return JSONResponse(
            status_code=exc.http_status,
            content={"status": exc.status, "message": exc.message, "detail": exc.message},
        )

    return JSONResponse(status_code=200, content=result)


@router.post(
    "/risk-explanation",
    response_model=RiskExplanationResponse,
    summary="AI-generate a concise explanation for the calculated migration risk level.",
)
async def explain_risk(
    payload: RiskExplanationRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    result = await _explain_risk_use_case.execute(payload, db=db, current_user=current_user)


@router.post(
    "/dependency-analysis",
    response_model=DependencyAnalysisResponse,
    summary="AI-analyze repository dependencies for migration risk, category, explanations, and recommendations.",
)
async def analyze_dependencies(
    payload: DependencyAnalysisRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: Session | None = Depends(get_db_optional),  # noqa: B008
) -> JSONResponse:
    result = await _dependency_analysis_use_case.execute(payload, db=db, current_user=current_user)
    return JSONResponse(status_code=200, content=result.model_dump())
