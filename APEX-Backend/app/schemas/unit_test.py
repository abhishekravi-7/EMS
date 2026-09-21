"""Pydantic schemas for JUnit test analysis, generation, validation, and execution."""

from __future__ import annotations

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


class UnitTestSuiteResult(BaseModel):
    total_run: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    existing_test_results: list[TestExecutionDetail] = Field(default_factory=list)
    generated_test_results: list[TestExecutionDetail] = Field(default_factory=list)
    generated_code: str = ""
    generated_test_file_path: str | None = None
    validation_report: UnitTestValidationReport | None = None
    raw_logs: list[str] = Field(default_factory=list)


class UnitTestGenerateAndRunRequest(BaseModel):
    job_id: str | None = Field(None, description="Migration job ID if running within a migration workflow")
    project_dir: str | None = Field(None, description="Absolute path to target Java project directory if running standalone")
    relative_source_path: str = Field(..., description="Relative path to source Java file (e.g. src/main/java/com/example/UserService.java)")
    relative_test_path: str | None = Field(None, description="Optional relative path to existing test Java file")
    build_tool: str = Field("maven", description="maven | gradle")
    java_version: str = Field("17", description="Source/Target Java version")
    spring_boot_version: str | None = Field(None, description="Detected Spring Boot version if applicable")
    max_reflection_retries: int = Field(3, description="Maximum retries for self-correction reflection loop")
    enable_validation_agent: bool = Field(True, description="Enable Multi-Agent Critic and Smell Detector validation")
    test_command: str | None = Field(None, description="Optional custom test command to run instead of default maven/gradle test")
