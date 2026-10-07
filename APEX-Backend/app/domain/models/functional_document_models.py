"""Domain models for Functional Testing Document extraction, grounding against repository evidence, and testcase generation."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from app.domain.models.proposed_test_models import ProposedTestCase


class GroundingStatus(str, Enum):
    MATCHED = "MATCHED"
    PARTIALLY_MATCHED = "PARTIALLY_MATCHED"
    UNMATCHED = "UNMATCHED"


class ExtractedScenario(BaseModel):
    """A discrete functional scenario extracted from a functional testing document."""

    id: str = ""
    raw_description: str
    implied_subject: str
    implied_type: str  # "API" or "UI"
    method_hint: str | None = None
    endpoint_hint: str | None = None
    route_hint: str | None = None
    fields_mentioned: list[str] = Field(default_factory=list)
    actions_mentioned: list[str] = Field(default_factory=list)
    expected_result: str = ""
    expected_status_hint: int | None = None
    is_negative: bool = False
    priority: str = "MEDIUM"
    raw_context: dict[str, Any] = Field(default_factory=dict)


class MatchedScenarioItem(BaseModel):
    raw_description: str
    generated_testcase: dict[str, Any] | ProposedTestCase


class PartiallyMatchedScenarioItem(BaseModel):
    raw_description: str
    matched_evidence: str
    missing_detail: str


class UnmatchedScenarioItem(BaseModel):
    raw_description: str
    reason: str


class DuplicateSkippedItem(BaseModel):
    raw_description: str
    duplicate_of_id: str


class FunctionalDocumentGroundingReport(BaseModel):
    """Standardized output report of the Functional Document Grounding Engine."""

    scenarios_extracted: int
    matched: list[dict[str, Any]] = Field(default_factory=list)
    partially_matched: list[dict[str, Any]] = Field(default_factory=list)
    unmatched: list[dict[str, Any]] = Field(default_factory=list)
    non_scenario_content_excluded: list[str] = Field(default_factory=list)
    skipped_as_duplicate_of_existing: list[dict[str, Any]] = Field(default_factory=list)
