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
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    NOT_EXECUTED = "NOT_EXECUTED"
    APPLICATION_UNAVAILABLE = "APPLICATION_UNAVAILABLE"  # App not reachable — NOT a functional failure
    REVIEW_REQUIRED = "REVIEW_REQUIRED"          # Test assumptions need manual verification
    BLOCKED_AUTHENTICATION = "BLOCKED_AUTHENTICATION"  # Auth could not be established


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
    input_fields: list[dict[str, Any]] = Field(default_factory=list)
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
    video_duration: float | None = None
    video_duration_formatted: str | None = None
    video_size: int | None = None
    recording_status: str | None = None
    trace_url: str | None = None
    trace_available: bool = False


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
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED_DEPENDENCY = "BLOCKED_DEPENDENCY"
    BLOCKED_AUTHENTICATION = "BLOCKED_AUTHENTICATION"
    INVALID = "INVALID"
    PARTIALLY_VALID = "PARTIALLY_VALID"
    HALLUCINATED = "HALLUCINATED"
    DUPLICATE = "DUPLICATE"
    UNSUPPORTED = "UNSUPPORTED"


class TestCaseMetadata(BaseModel):
    __test__ = False
    test_id: str
    endpoint: str | None = None
    method: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    expected_status: int | None = None
    expected_status_source: str | None = None
    authentication_required: bool = False
    authentication_source: str | None = None
    selector: str | None = None
    selector_source: str | None = None
    parameter_sources: dict[str, str] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    validation_status: ValidationStatus = ValidationStatus.VALID


class ProposedTestValidationResult(BaseModel):
    status: ValidationStatus = ValidationStatus.VALID
    repository_evidence: str | None = None
    issue: str | None = None
    playwright_executable: bool = True
    functional_area: str = "General"
    metadata: TestCaseMetadata | None = None


class ValidationSummary(BaseModel):
    total_llm_generated: int = 0
    valid: int = 0
    review_required: int = 0
    blocked_dependency: int = 0
    blocked_authentication: int = 0
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
    baseline_execution_result: ExecutionResult | None = None
    validation: ProposedTestValidationResult | None = None
    metadata: TestCaseMetadata | None = None
    document_id: str | None = None
    source_reference: str | None = None


class ProposedTestTypeBreakdown(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    blocked: int = 0


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
    blocked: int = 0
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


class TestComparisonItem(BaseModel):
    id: str
    title: str
    type: ProposedTestType
    source: str
    baseline_status: ProposedTestStatus = ProposedTestStatus.NOT_EXECUTED
    target_status: ProposedTestStatus = ProposedTestStatus.NOT_EXECUTED
    match: bool = True
    is_regression: bool = False
    is_improvement: bool = False
    baseline_duration: str = "--"
    target_duration: str = "--"


class ProposedTestComparisonResponse(BaseModel):
    job_id: str
    baseline_available: bool = False
    target_available: bool = False
    baseline_metrics: ProposedTestMetrics = Field(default_factory=ProposedTestMetrics)
    target_metrics: ProposedTestMetrics = Field(default_factory=ProposedTestMetrics)
    parity_percentage: str = "0%"
    regressions_count: int = 0
    improvements_count: int = 0
    preserved_passed_count: int = 0
    source_status: dict[str, Any] = Field(default_factory=dict)
    target_status: dict[str, Any] = Field(default_factory=dict)
    test_comparisons: list[TestComparisonItem] = Field(default_factory=list)
