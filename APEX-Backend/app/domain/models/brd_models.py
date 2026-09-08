"""Domain models for Business Requirements Document (BRD) parsing and extraction."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BrdMetadata(BaseModel):
    """Metadata describing an uploaded BRD file for a migration job."""

    job_id: str
    filename: str
    file_type: str
    size_bytes: int
    uploaded_at: str
    status: str = "UPLOADED"


class BrdWorkflowStep(BaseModel):
    """A single sequential step within a business workflow."""

    step_number: int
    action: str
    expected_outcome: str = ""


class BrdRequirement(BaseModel):
    """A specific business/functional requirement extracted from the BRD."""

    id: str = ""
    title: str
    description: str
    category: str = "FUNCTIONAL"
    acceptance_criteria: list[str] = Field(default_factory=list)


class BrdWorkflow(BaseModel):
    """A user or business process workflow extracted from the BRD."""

    name: str
    description: str = ""
    steps: list[str] = Field(default_factory=list)
    structured_steps: list[BrdWorkflowStep] = Field(default_factory=list)
    actors: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    expected_result: str = ""
    requirements_covered: list[str] = Field(default_factory=list)
    is_negative: bool = False
    priority: str = "HIGH"
    target_endpoint_hint: str | None = None
    target_service_hint: str | None = None
    target_ui_hint: str | None = None


class BrdExtractionResult(BaseModel):
    """Consolidated extraction output from a parsed BRD."""

    job_id: str
    filename: str
    raw_text_length: int = 0
    workflows: list[BrdWorkflow] = Field(default_factory=list)
    requirements: list[BrdRequirement] = Field(default_factory=list)
    parsed_at: str = ""
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
