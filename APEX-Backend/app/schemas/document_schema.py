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
    brd_instructions: Optional[str] = None
    brd_focus_prompt: Optional[str] = None
    brd_system_prompt: Optional[str] = None
    technical_specification_instructions: Optional[str] = None
    brd_migration_target: Optional[str] = None
    brd_generation_enabled: Optional[bool] = None
    brd_microservices_enabled: Optional[bool] = None
    microservice_assessment_enabled: Optional[bool] = None
    brd_category_business_workflows: Optional[bool] = None
    brd_category_database_data: Optional[bool] = None
    brd_category_architecture: Optional[bool] = None
    brd_category_apis_integrations: Optional[bool] = None
    brd_category_security_access: Optional[bool] = None
    brd_category_reliability_performance: Optional[bool] = None

    model_config = {"populate_by_name": True, "extra": "allow"}


class TechnicalDocumentResponse(BaseModel):
    filename: str
    html: str
    document_type: str = Field(default="TECHNICAL_SPECIFICATION")

    model_config = {"populate_by_name": True}
