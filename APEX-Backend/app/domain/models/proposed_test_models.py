"""Domain models for Proposed Functional Test Cases."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProposedTestType(str, Enum):
    UNIT = "UNIT"
    API = "API"
    UI = "UI"


class ProposedTestPriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ProposedTestStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    READY = "READY"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    NOT_EXECUTED = "NOT_EXECUTED"


class StepExecutionRecord(BaseModel):
    step_number: int
    description: str
    status: ProposedTestStatus = ProposedTestStatus.PASSED
    duration: str = "0.1s"
    error: str | None = None


class ApiTestSpec(BaseModel):
    method: str = "GET"
    endpoint: str = "/"
    headers: dict[str, str] = Field(default_factory=dict)
    request_body: Any | None = None
    expected_status: int = 200
    actual_status: int | None = None
    expected_response: Any | None = None
    assertions: list[str] = Field(default_factory=list)


class UnitTestSpec(BaseModel):
    target_class: str = ""
    target_method: str = ""
    input_data: Any | None = None
    mock_data: Any | None = None
    expected_output: Any | None = None
    assertions: list[str] = Field(default_factory=list)


class UiTestSpec(BaseModel):
    target_route: str = "/"
    input_fields: list[dict[str, str]] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    expected_elements: list[str] = Field(default_factory=list)
    selectors: dict[str, str] = Field(default_factory=dict)
    assertions: list[str] = Field(default_factory=list)


class ExecutionEvidence(BaseModel):
    screenshot_url: str | None = None
    video_url: str | None = None
    logs_url: str | None = None
    screenshot_available: bool = False
    video_available: bool = False
    trace_url: str | None = None


class ExecutionResult(BaseModel):
    status: ProposedTestStatus = ProposedTestStatus.NOT_EXECUTED
    duration: str = "0.0s"
    executed_at: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    error: str | None = None
    error_type: str | None = None  # "FUNCTIONAL_FAILURE" | "INFRASTRUCTURE_FAILURE"
    stack_trace: str | None = None
    actual_status_code: int | None = None
    response_time_ms: int | None = None
    actual_response: Any | None = None
    evidence: ExecutionEvidence = Field(default_factory=ExecutionEvidence)
    assertions_passed: int = 0
    assertions_failed: int = 0
    steps_execution: list[StepExecutionRecord] = Field(default_factory=list)


class ValidationStatus(str, Enum):
    VALID = "VALID"
    PARTIALLY_VALID = "PARTIALLY_VALID"
    INVALID = "INVALID"
    HALLUCINATED = "HALLUCINATED"
    DUPLICATE = "DUPLICATE"
    UNSUPPORTED = "UNSUPPORTED"


class ProposedTestValidationResult(BaseModel):
    status: ValidationStatus = ValidationStatus.VALID
    repository_evidence: str | None = None
    issue: str | None = None
    playwright_executable: bool = True
    functional_area: str = "General"


class ValidationSummary(BaseModel):
    total_llm_generated: int = 0
    valid: int = 0
    partially_valid: int = 0
    invalid: int = 0
    hallucinated: int = 0
    duplicate: int = 0
    unsupported: int = 0
    functional_coverage: dict[str, str] = Field(default_factory=dict)


class ProposedTestCase(BaseModel):
    id: str
    title: str
    description: str
    type: ProposedTestType
    priority: ProposedTestPriority
    source: str
    reason: str
    preconditions: list[str] = Field(default_factory=list)
    test_data: dict[str, Any] | None = None
    steps: list[str] = Field(default_factory=list)
    expected_result: str
    status: ProposedTestStatus = ProposedTestStatus.PROPOSED
    generation_source: str = "AI_GENERATED"
    api_spec: ApiTestSpec | None = None
    unit_spec: UnitTestSpec | None = None
    ui_spec: UiTestSpec | None = None
    execution_result: ExecutionResult | None = None
    validation: ProposedTestValidationResult | None = None


class ProposedTestTypeBreakdown(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0


class ProposedTestPriorityBreakdown(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0


class ProposedTestMetrics(BaseModel):
    total: int = 0
    approved: int = 0
    rejected: int = 0
    executed: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    not_executed: int = 0
    gaps_count: int = 0
    ai_generated_count: int = 0
    brd_generated_count: int = 0
    llm_generated_count: int = 0
    functional_doc_generated_count: int = 0
    existing_generated_count: int = 0
    existing_count: int = 0
    duration: str = "0.0s"
    pass_percentage: str = "0%"
    unit_metrics: ProposedTestTypeBreakdown = Field(default_factory=ProposedTestTypeBreakdown)
    api_metrics: ProposedTestTypeBreakdown = Field(default_factory=ProposedTestTypeBreakdown)
    ui_metrics: ProposedTestTypeBreakdown = Field(default_factory=ProposedTestTypeBreakdown)
    priority_metrics: ProposedTestPriorityBreakdown = Field(default_factory=ProposedTestPriorityBreakdown)


class BulkStatusUpdateRequest(BaseModel):
    test_ids: list[str]
    status: ProposedTestStatus


class RunProposedTestsRequest(BaseModel):
    sources: list[str] | None = None
    test_ids: list[str] | None = None
    framework: str = "PLAYWRIGHT"
