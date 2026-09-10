"""Orchestrates Hybrid Neuro-Symbolic Code Migration.

Phase 1: Deterministic AST Rule Pass (AstMigrationRunner)
Phase 2: Compilation Verification (BuildValidator)
Phase 3: LLM Self-Healing Repair Loop (LlmSelfHealingRepair)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.infrastructure.analyzers.project_analyzer import ProjectAnalyzer
from app.infrastructure.build.build_validator import BuildValidator
from app.infrastructure.java_runtime import build_compatible_java_target
from app.infrastructure.migration_engine.ast_automated_migration_runner import (
    AstMigrationRunResult,
    AstMigrationRunner,
)
from app.infrastructure.migration_engine.ast_rule_mapper import AstRuleMapper
from app.infrastructure.migration_engine.llm_self_healing_repair import LlmSelfHealingRepair

logger = logging.getLogger(__name__)


@dataclass
class MigrationRunResult:
    success: bool
    tool: str  # "maven" | "gradle" | "none"
    status: str = "FAILED"
    project_dir: Path | None = None
    recipes: list[str] = field(default_factory=list)
    log_lines: list[str] = field(default_factory=list)
    error_lines: list[str] = field(default_factory=list)
    used_fallback: bool = False
    tool_unavailable: bool = False
    pre_recipe_failure: bool = False
    recipe_selection_reasons: list[str] = field(default_factory=list)
    build_modernization_lines: list[str] = field(default_factory=list)
    dependency_upgrades: list[dict] = field(default_factory=list)
    effective_target_java_version: str | None = None
    already_compatible: bool = False
    spring_conversion_requested: bool = False
    spring_conversion_supported: bool | None = None
    spring_conversion_note: str | None = None
    spring_boot_version_before: str | None = None
    spring_boot_version_after: str | None = None
    phase_results: list[dict] = field(default_factory=list)
    skipped_recipes: list[dict] = field(default_factory=list)
    rule_executions: list[dict[str, Any]] = field(default_factory=list)


class AutomatedMigrationRunner:
    def __init__(self) -> None:
        self._analyzer = ProjectAnalyzer()
        self._mapper = AstRuleMapper()
        self._ast_runner = AstMigrationRunner()
        self._build_validator = BuildValidator()
        self._llm_repair = LlmSelfHealingRepair()

    def run(
        self,
        migrated_repo_dir: Path,
        build_tool: str,
        target_java_version: str | None,
        *,
        include_jakarta: bool,
        conversion_types: list[str] | None = None,
        extra_recipes: list[Any] | None = None,
        enable_llm_repair: bool = True,
    ) -> MigrationRunResult:
        logger.info("Starting Hybrid Neuro-Symbolic migration for %s", migrated_repo_dir)

        # 1. Discovery
        analysis = self._analyzer.analyze(migrated_repo_dir)
        effective_target, _ = build_compatible_java_target(target_java_version)

        # 2. Planning (Dynamic Rule Catalog Mapper)
        plan = self._mapper.build_plan(
            project_root=migrated_repo_dir,
            source_java=analysis.current_java_version,
            target_java=effective_target,
            build_tool=build_tool,
            frameworks=analysis.frameworks,
        )

        # 3. Phase 1: Deterministic AST Execution
        ast_result = self._ast_runner.run(
            migrated_repo_dir,
            {
                "planId": plan.planId,
                "projectRoot": str(plan.projectRoot),
                "sourceJavaVersion": plan.sourceJavaVersion,
                "targetJavaVersion": plan.targetJavaVersion,
                "buildSystem": plan.buildSystem,
                "activePacks": plan.activePacks,
                "activeRules": plan.activeRules,
                "activeVisitors": plan.activeVisitors,
            },
        )

        accumulated_logs = list(ast_result.log_lines)
        accumulated_errors = list(ast_result.error_lines)
        final_status = ast_result.status

        # 4. Phase 2 & 3: Compilation Check + LLM Self-Healing Repair Loop
        if enable_llm_repair:
            target_major = None
            if effective_target:
                try:
                    target_major = int(str(effective_target).strip())
                except ValueError:
                    target_major = None

            compile_check = self._build_validator.validate(migrated_repo_dir, build_tool, target_major)
            if not compile_check.success and compile_check.error_lines:
                accumulated_logs.append("Phase 2 Compilation Verification reported build errors. Triggering Phase 3 LLM Self-Healing Repair...")
                accumulated_errors.extend(compile_check.error_lines[:15])

                repair_res = self._llm_repair.repair_build_failures(
                    migrated_repo_dir,
                    compile_check.error_lines,
                    target_java_version=effective_target,
                )
                accumulated_logs.extend(repair_res.log_lines)
                if repair_res.success:
                    re_check = self._build_validator.validate(migrated_repo_dir, build_tool, target_major)
                    if re_check.success:
                        final_status = "SUCCESS"
                        accumulated_logs.append("Phase 3 LLM Self-Healing Repair resolved all compilation errors!")
                    else:
                        final_status = "PARTIAL"
                        accumulated_logs.append("LLM Self-Healing Repair patched files; remaining errors require SME manual review.")

        return MigrationRunResult(
            success=final_status in ("SUCCESS", "PARTIAL", "NO_CHANGES"),
            status=final_status,
            tool=build_tool.lower(),
            project_dir=migrated_repo_dir,
            log_lines=accumulated_logs,
            error_lines=accumulated_errors,
            effective_target_java_version=effective_target,
            recipes=plan.activePacks,
            already_compatible=final_status == "NO_CHANGES",
            spring_conversion_requested=bool(conversion_types and "spring_boot" in conversion_types),
            spring_boot_version_before=ast_result.spring_boot_before or analysis.spring_boot_version,
            rule_executions=ast_result.rule_executions,
        )
