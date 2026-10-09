"""Pydantic schemas for JUnit test analysis, generation, validation, and execution."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TestScenario(BaseModel):
    __test__ = False
    name: str = Field(..., description="Short name of the test scenario")
    scenario_type: str = Field(
        ..., description="Type of scenario: happy_path | boundary | null_check | exception | edge_case"
    )
    description: str = Field(..., description="Detailed description of the test scenario")
    target_method: str = Field(..., description="Target method name being tested")


class TestSmellDetail(BaseModel):
    __test__ = False
    smell_type: str = Field(..., description="NO_ASSERTIONS | TAUTOLOGICAL_ASSERTION | THREAD_SLEEP | OVERMOCKING | MISSING_PACKAGE")
    message: str = Field(..., description="Detailed description of the detected test smell")
    line_number: int | None = Field(None, description="Line number where smell was detected if applicable")
    severity: str = Field("HIGH", description="CRITICAL | HIGH | MEDIUM | LOW")


class UnitTestValidationReport(BaseModel):
    __test__ = False
    is_valid: bool = Field(..., description="True if candidate test passes validation rules")
    critic_score: float = Field(0.0, description="LLM Critic quality score (0.0 to 100.0)")
    smells_detected: list[TestSmellDetail] = Field(default_factory=list)
    critique_feedback: str = Field("", description="Detailed review comments from Critic Agent")
    compiler_passed: bool = Field(True, description="True if test code compiles in sandbox")


class UnitTestValidationRequest(BaseModel):
    source_code: str = Field(..., description="Target Java source code string")
    test_code: str = Field(..., description="Candidate JUnit test code string to validate")
    target_class_name: str | None = Field(None, description="Target Java class name")


class UnitTestAnalysisRequest(BaseModel):
    job_id: str | None = Field(None, description="Optional migration job ID containing target project")
    project_dir: str | None = Field(None, description="Absolute path to target Java project directory")
    relative_source_path: str = Field(..., description="Relative path to Java source file (e.g. src/main/java/com/example/UserService.java)")
    relative_test_path: str | None = Field(None, description="Optional relative path to existing JUnit test file")


class UnitTestAnalysisResponse(BaseModel):
    target_class: str
    package_name: str
    existing_tests_count: int
    covered_methods: list[str]
    uncovered_methods: list[str]
    suggested_scenarios: list[TestScenario]


class TestExecutionDetail(BaseModel):
    __test__ = False
    test_class: str
    test_method: str
    status: str = Field(..., description="PASSED | FAILED | SKIPPED")
    execution_time_seconds: float = 0.0
    error_message: str | None = None
    stack_trace: str | None = None


class TestingPromptAnalysis(BaseModel):
    __test__ = False
    user_prompt: str | None = Field(None, description="Original natural language user testing prompt")
    testing_focus: str = Field("General Testing Focus", description="Summary of user's requested testing focus")
    testing_objective: str = Field("", description="Primary testing objective and scope summary")
    coverage_target: str = Field("80-90%", description="Target coverage percentage range")
    target_areas: list[str] = Field(default_factory=list, description="Target functional areas")
    target_classes: list[str] = Field(default_factory=list, description="Target class names or patterns")
    target_methods: list[str] = Field(default_factory=list, description="Target method names")
    business_logic_areas: list[str] = Field(default_factory=list, description="Core business logic areas")
    execution_paths: list[str] = Field(default_factory=list, description="Execution paths to test")
    branches: list[str] = Field(default_factory=list, description="Conditional branches and decision paths")
    edge_cases: list[str] = Field(default_factory=list, description="Edge cases and boundary conditions")
    negative_scenarios: list[str] = Field(default_factory=list, description="Negative testing scenarios and validation failures")
    exception_scenarios: list[str] = Field(default_factory=list, description="Exception handling scenarios")
    coverage_gaps: list[str] = Field(default_factory=list, description="Identified JaCoCo coverage gaps")
    priority: list[str] = Field(default_factory=list, description="High-priority scenarios")
    priority_areas: list[str] = Field(default_factory=list, description="High priority focus areas")
    scenarios: list[str] = Field(default_factory=list, description="Specific positive and negative test scenarios")
    additional_tests_required: list[str] = Field(default_factory=list, description="Suggested additional tests to close gaps")


class PromptCoverageEvaluation(BaseModel):
    __test__ = False
    user_prompt: str = Field(..., description="Original natural language user testing prompt")
    focus_matched: bool = Field(True, description="True if target focus areas received sufficient test coverage")
    coverage_assessment: str = Field("", description="Concise assessment of prompt-focused test coverage")
    covered_scenarios: list[str] = Field(default_factory=list, description="List of verified covered scenarios")
    uncovered_scenarios: list[str] = Field(default_factory=list, description="List of remaining uncovered scenarios")
    recommendations: list[str] = Field(default_factory=list, description="Actionable testing recommendations")


class PromptComplianceItem(BaseModel):
    __test__ = False
    prompt_id: str = Field(..., description="Predefined prompt ID or 'manual_prompt'")
    prompt_name: str = Field(..., description="Human-readable prompt name")
    expected_scenarios: list[str] = Field(default_factory=list, description="Expected testing criteria/scenarios")
    covered_scenarios: list[str] = Field(default_factory=list, description="Scenarios confirmed satisfied by actual test logic & execution")
    uncovered_scenarios: list[str] = Field(default_factory=list, description="Scenarios not satisfied or missed")
    generated_test_methods: list[str] = Field(default_factory=list, description="Test methods exercising this prompt requirement")
    passed_count: int = Field(0, description="Number of passed test methods")
    failed_count: int = Field(0, description="Number of failed test methods")
    execution_status: str = Field("PASSED", description="PASSED | PARTIAL | FAILED | NOT_RUN")
    jacoco_gaps_addressed: list[str] = Field(default_factory=list, description="JaCoCo coverage gaps addressed")
    compliance_percentage: float = Field(0.0, description="Compliance percentage 0.0 to 100.0")
    recommendations: list[str] = Field(default_factory=list, description="Actionable recommendations")
    inspected_features: dict[str, Any] = Field(default_factory=dict, description="Inspected code features: mocks, assertions, exceptions, boundaries")


class PromptComplianceReport(BaseModel):
    __test__ = False
    overall_compliance_percentage: float = Field(0.0, description="Overall average/weighted prompt compliance percentage")
    total_prompts_evaluated: int = Field(0, description="Total number of evaluated prompts")
    passed_prompts_count: int = Field(0, description="Number of prompts meeting >= 80% compliance")
    failed_prompts_count: int = Field(0, description="Number of prompts below 80% compliance")
    compliance_items: list[PromptComplianceItem] = Field(default_factory=list, description="Compliance item per evaluated prompt")
    evaluation_summary: str = Field("", description="High-level evaluation summary")
    total_test_methods_inspected: int = Field(0, description="Total test methods whose AST/logic was inspected")
    total_assertions_inspected: int = Field(0, description="Total assertions found in tests")
    total_exceptions_verified: int = Field(0, description="Total assertThrows/exceptions checked")
    total_boundary_inputs_tested: int = Field(0, description="Total boundary/null/empty inputs tested")
    total_mocks_verified: int = Field(0, description="Total mock setups/verifications detected")


class UnitTestSuiteResult(BaseModel):
    total_run: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    existing_test_results: list[TestExecutionDetail] = Field(default_factory=list)
    generated_test_results: list[TestExecutionDetail] = Field(default_factory=list)
    generated_test_files: list[dict[str, Any]] = Field(default_factory=list)
    generated_test_execution: dict[str, Any] | None = None
    execution_status: str = "NOT_EXECUTED"
    original_coverage: dict[str, Any] | None = None
    final_coverage: dict[str, Any] | None = None
    coverage_improvement: dict[str, Any] | None = None
    coverage: dict[str, Any] | None = None
    line_coverage_pct: float | None = None
    branch_coverage_pct: float | None = None
    instruction_coverage_pct: float | None = None
    method_coverage_pct: float | None = None
    class_coverage_pct: float | None = None
    generated_code: str = ""
    generated_test_file_path: str | None = None
    validation_report: UnitTestValidationReport | None = None
    prompt_analysis: TestingPromptAnalysis | None = None
    prompt_coverage_evaluation: PromptCoverageEvaluation | None = None
    prompt_compliance: PromptComplianceReport | None = None
    mcp_stats: dict[str, Any] | None = None
    git_publish_status: str | None = None
    git_publish_error: str | None = None
    raw_logs: list[str] = Field(default_factory=list)


class UnitTestGenerateAndRunRequest(BaseModel):
    job_id: str | None = Field(None, description="Migration job ID if running within a migration workflow")
    project_dir: str | None = Field(None, description="Absolute path to target Java project directory if running standalone")
    relative_source_path: str = Field("src/main/java", description="Relative path to source Java file (e.g. src/main/java/com/example/UserService.java)")
    relative_test_path: str | None = Field(None, description="Optional relative path to existing test Java file")
    build_tool: str = Field("maven", description="maven | gradle")
    java_version: str = Field("17", description="Source/Target Java version")
    spring_boot_version: str | None = Field(None, description="Detected Spring Boot version if applicable")
    max_reflection_retries: int = Field(3, description="Maximum retries for self-correction reflection loop")
    enable_validation_agent: bool = Field(True, description="Enable Multi-Agent Critic and Smell Detector validation")
    test_command: str | None = Field(None, description="Optional custom test command to run instead of default maven/gradle test")
    testing_prompt: str | None = Field(None, description="Arbitrary user natural language testing prompt to guide focus")
    selected_predefined_prompts: list[str] | None = Field(default_factory=list, description="List of selected predefined prompt IDs")
    manual_prompt: str | None = Field(None, description="User manual testing prompt")


class TestingPromptAnalysisRequest(BaseModel):
    __test__ = False
    prompt: str | None = Field(None, description="Free-form user testing focus prompt or combined prompt")
    manual_prompt: str | None = Field(None, description="User manual testing prompt")
    selected_predefined_prompts: list[str] | None = Field(default_factory=list, description="List of selected predefined prompt IDs")
    project_context: str | None = Field(None, description="Optional Java project/class context string")


