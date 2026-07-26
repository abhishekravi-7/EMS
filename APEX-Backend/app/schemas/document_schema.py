"""Schemas for generated repository-grounded technical documents."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class TechnicalDocumentRequest(BaseModel):
    repo_url: Optional[str] = None
    repository_url: Optional[str] = None
    source_repo_url: Optional[str] = None
    token: Optional[str] = None
    github_token: Optional[str] = None
    job_id: Optional[str] = None
    migration_job_id: Optional[str] = None
    source_repo: Optional[str] = None
    target_repo: Optional[str] = None
    source_java_version: Optional[str] = None
    target_java_version: Optional[str] = None
    document_type: Optional[str] = Field(default="TECHNICAL_SPECIFICATION")
    analysis: Optional[dict[str, Any]] = None

    model_config = {"populate_by_name": True, "extra": "ignore"}


class TechnicalDocumentResponse(BaseModel):
    filename: str
    html: str
    document_type: str = Field(default="TECHNICAL_SPECIFICATION")

    model_config = {"populate_by_name": True}
