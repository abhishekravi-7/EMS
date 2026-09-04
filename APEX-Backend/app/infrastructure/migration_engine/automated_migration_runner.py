"""Orchestrates the actual code migration using the custom AST-based engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.infrastructure.analyzers.project_analyzer import ProjectAnalyzer
from app.infrastructure.java_runtime import build_compatible_java_target
from app.infrastructure.migration_engine.ast_automated_migration_runner import AstMigrationRunner, AstMigrationRunResult
from app.infrastructure.migration_engine.ast_rule_mapper import AstRuleMapper

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

    def run(
        self,
        migrated_repo_dir: Path,
        build_tool: str,
        target_java_version: str | None,
        *,
        include_jakarta: bool,
        conversion_types: list[str] | None = None,
        extra_recipes: list[Any] | None = None,
    ) -> MigrationRunResult:
        logger.info("Starting custom AST-based migration for %s", migrated_repo_dir)
        
        # 1. Discovery
        analysis = self._analyzer.analyze(migrated_repo_dir)
        effective_target, _ = build_compatible_java_target(target_java_version)
        
        # 2. Planning
        plan = self._mapper.build_plan(
            project_root=migrated_repo_dir,
            source_java=analysis.current_java_version,
            target_java=effective_target,
            build_tool=build_tool,
            frameworks=analysis.frameworks
        )
        
        # 3. Execution (Java Engine CLI)
        result = self._ast_runner.run(migrated_repo_dir, {
            "planId": plan.planId,
            "projectRoot": str(plan.projectRoot),
            "sourceJavaVersion": plan.sourceJavaVersion,
            "targetJavaVersion": plan.targetJavaVersion,
            "buildSystem": plan.buildSystem,
            "activePacks": plan.activePacks,
            "activeRules": plan.activeRules,
            "activeVisitors": plan.activeVisitors
        })
        
        return MigrationRunResult(
            success=result.success,
            status=result.status,
            tool=build_tool.lower(),
            project_dir=migrated_repo_dir,
            log_lines=result.log_lines,
            error_lines=result.error_lines,
            effective_target_java_version=effective_target,
            recipes=plan.activePacks, # Mapping packs to "recipes" for UI consistency
            already_compatible=result.status == "NO_CHANGES",
            spring_conversion_requested=bool(conversion_types and "spring_boot" in conversion_types),
            spring_boot_version_before=analysis.spring_boot_version,
            phase_results=[{"id": p, "status": "completed" if result.success else "failed"} for p in plan.activePacks],
            rule_executions=result.rule_executions
        )
