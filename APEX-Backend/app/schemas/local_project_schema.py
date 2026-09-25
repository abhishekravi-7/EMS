from typing import Any

from pydantic import BaseModel


class LocalProjectCapabilitiesResponse(BaseModel):
    """Body for ``GET /api/local-project/capabilities``."""

    enabled: bool
    hosted_mode: bool
    allow_any_path: bool
    allowed_roots: list[str]
    supports_upload: bool
    message: str


class LocalProjectAnalyzeRequest(BaseModel):
    """Body for ``POST /api/local-project/analyze``."""

    project_path: str | None = None
    project_name: str | None = None
    job_id: str | None = None


class LocalProjectAnalysisResponse(BaseModel):
    """Response body for ``POST /api/local-project/analyze`` and upload."""

    jobId: str | None = None
    project_path: str
    project_name: str
    repo_url: str
    owner: str = "local"
    repo: str
    analysis: dict[str, Any] | None = None
