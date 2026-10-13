from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from pydantic import BaseModel, Field


class CoverageAgentRequest(BaseModel):
    project_dir: str
    target_coverage: float = Field(default=80.0, ge=1, le=100)
    max_iterations: int = Field(default=30, ge=1, le=50)
    build_tool: Optional[str] = None
    java_version: Optional[str] = None
    coverage_metric: str = "LINE"
    skip_clean: bool = False
    test_command: Optional[str] = None
    max_parallel_shards: int = Field(default=4, ge=1, le=8)
    shard_package_depth: int = Field(default=4, ge=1, le=10)
    max_gaps_per_shard: int = Field(default=3, ge=1, le=12)
    ignore_test_failures: bool = False
    """When True, reaching the coverage target counts as success even if
    some tests fail. Test execution is always failure-tolerant (so a
    JaCoCo report is produced from whatever ran); this flag only relaxes
    the success criterion. Default False = tests must pass too."""


class CoverageGap(BaseModel):
    package: str = ""
    class_name: str
    source_file: Optional[str] = None
    line_coverage: float = 0.0
    branch_coverage: float = 0.0
    uncovered_lines: list[int] = Field(default_factory=list)
    uncovered_branches: int = 0
    uncovered_methods: list[str] = Field(default_factory=list)
    priority: float = 0.0


class CoverageIteration(BaseModel):
    iteration: int
    coverage_before: float
    coverage_after: float
    tests_changed: list[str] = Field(default_factory=list)
    compilation_ok: bool = False
    tests_ok: bool = False
    build_output: str = ""
    failure: Optional[str] = None
    shard: Optional[str] = None


class CoverageAgentResult(BaseModel):
    success: bool
    target_coverage: float
    initial_coverage: float
    final_coverage: float
    coverage_metric: str
    build_tool: str
    java_version: Optional[str] = None
    iterations: int = 0
    tests_created: int = 0
    tests_modified: int = 0
    compilation_repairs: int = 0
    iteration_history: list[CoverageIteration] = Field(default_factory=list)
    remaining_gaps: list[CoverageGap] = Field(default_factory=list)
    jacoco_report: Optional[str] = None
    failure_reason: Optional[str] = None


@dataclass
class ProjectInfo:
    root: str
    build_tool: str
    java_version: Optional[str]
    test_framework: str
    jacoco_report: Optional[str]
    source_roots: list[str] = field(default_factory=list)
    test_roots: list[str] = field(default_factory=list)
