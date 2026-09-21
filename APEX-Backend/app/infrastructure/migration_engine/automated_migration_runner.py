"""Orchestrates Hybrid Neuro-Symbolic Code Migration.

Phase 1: Deterministic AST Rule Pass (AstMigrationRunner)
Phase 2: Compilation Verification (BuildValidator)
Phase 3: LLM Self-Healing Repair Loop (LlmSelfHealingRepair)
"""

from __future__ import annotations

import logging
import re
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
from app.shared.command_runner import resolve_executable, run_command
from app.shared.file_utils import find_shallowest_dir_with

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
    dependency_migration_status: str = "NOT_APPLICABLE"
    plugin_upgrades: list[dict] = field(default_factory=list)
    plugin_migration_status: str = "NOT_APPLICABLE"


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
            project_root=analysis.project_root,
            source_java=analysis.current_java_version,
            target_java=effective_target,
            build_tool=build_tool,
            frameworks=analysis.frameworks,
            current_boot_version=analysis.spring_boot_version,
            conversion_types=conversion_types,
        )

        # Filter mappings to prevent downgrades before execution
        safe_dependency_mappings = []
        for mapping in plan.dependencyMappings:
            gid, aid, target = mapping["groupId"], mapping["artifactId"], mapping["targetVersion"]
            # find current version
            current = next((d.resolved_version or d.version for d in analysis.dependencies if d.group_id == gid and d.artifact_id == aid), None)
            if not current or self._is_newer(target, current):
                safe_dependency_mappings.append(mapping)

        safe_plugin_mappings = []
        for mapping in plan.pluginMappings:
            gid, aid, target = mapping["groupId"], mapping["artifactId"], mapping["targetVersion"]
            current = next((p.version for p in analysis.build_plugins if (p.group_id == gid or not p.group_id) and p.artifact_id == aid), None)
            if not current or self._is_newer(target, current):
                safe_plugin_mappings.append(mapping)

        # 3. Phase 1: Deterministic AST Execution (Java Engine CLI)
        ast_result = self._ast_runner.run(analysis.project_root, {
            "planId": plan.planId,
            "projectRoot": str(plan.projectRoot),
            "sourceJavaVersion": plan.sourceJavaVersion,
            "targetJavaVersion": plan.targetJavaVersion,
            "buildSystem": plan.buildSystem,
            "activePacks": plan.activePacks,
            "activeRules": plan.activeRules,
            "activeVisitors": plan.activeVisitors,
            "targetSpringBootVersion": plan.targetSpringBootVersion,
            "dependencyMappings": safe_dependency_mappings,
            "pluginMappings": safe_plugin_mappings,
        })

        accumulated_logs = list(ast_result.log_lines)
        accumulated_errors = list(ast_result.error_lines)
        final_status = ast_result.status

        # 4. Phase 2 & 3: Iterative Compilation Check + LLM Self-Healing Repair
        if enable_llm_repair:
            target_major = None
            if effective_target:
                try:
                    target_major = int(str(effective_target).strip())
                except ValueError:
                    target_major = None

            max_heal_cycles = 3
            previous_error_count = float("inf")
            desperation_triggered = False

            for cycle in range(1, max_heal_cycles + 1):
                compile_check = self._build_validator.validate(
                    migrated_repo_dir, build_tool, target_major
                )

                if compile_check.success or compile_check.skipped:
                    if cycle == 1:
                        accumulated_logs.append(
                            "Phase 2 Compilation Verification: BUILD SUCCESS on first pass."
                        )
                    else:
                        accumulated_logs.append(
                            f"Phase 3 LLM Self-Healing resolved all errors after {cycle - 1} repair cycle(s)!"
                        )
                    final_status = "SUCCESS"
                    break

                current_error_count = len(compile_check.error_lines)
                accumulated_logs.append(
                    f"Heal cycle {cycle}/{max_heal_cycles}: "
                    f"{current_error_count} compiler error(s) detected."
                )

                if cycle > 1 and current_error_count >= previous_error_count:
                    accumulated_logs.append(
                        "No error reduction detected \u2014 stopping self-healing loop."
                    )
                    final_status = "PARTIAL"
                    break

                previous_error_count = current_error_count
                accumulated_errors.extend(compile_check.error_lines[:20])

                repair_res = self._llm_repair.repair_build_failures(
                    migrated_repo_dir,
                    compile_check.error_lines,
                    target_java_version=effective_target,
                    max_files_to_fix=0,
                )
                accumulated_logs.extend(repair_res.log_lines)

                if not repair_res.success:
                    accumulated_logs.append(
                        "LLM Self-Healing could not patch any files this cycle."
                    )
                    final_status = "PARTIAL"
                    break
            else:
                final_status = "PARTIAL"
                accumulated_logs.append(
                    f"LLM Self-Healing exhausted {max_heal_cycles} repair cycles. "
                    "Remaining errors require manual SME review."
                )

        # 5. Post-migration discovery to find the new version
        # Use robust Maven evaluation for the final report
        post_analysis = self._analyzer.analyze(migrated_repo_dir)
        boot_before = ast_result.spring_boot_before or analysis.spring_boot_version
        boot_after = self._get_effective_boot_version(post_analysis.project_root) or post_analysis.spring_boot_version or boot_before

        java_before = analysis.current_java_version
        java_after = self._get_effective_java_version(post_analysis.project_root) or post_analysis.current_java_version or java_before

        # 6. Dependency upgrade results
        dependency_upgrades = self._compare_dependencies(analysis.dependencies, post_analysis.dependencies, plan.dependencyMappings)

        dep_status = "NOT_APPLICABLE"
        if conversion_types and "java_version" in conversion_types:
            if dependency_upgrades:
                dep_status = "UPGRADED"
            else:
                dep_status = "UNCHANGED"

        # 7. Plugin upgrade results
        plugin_upgrades = self._compare_plugins(analysis.build_plugins, post_analysis.build_plugins, plan.pluginMappings)
        plugin_status = "NOT_APPLICABLE"
        if conversion_types and "java_version" in conversion_types:
            if plugin_upgrades:
                plugin_status = "UPGRADED"
            else:
                plugin_status = "UNCHANGED"

        note = None
        status = final_status

        if plan.incompatibleReason:
            status = "MANUAL_REVIEW"
            note = plan.incompatibleReason
        elif boot_before and plan.targetSpringBootVersion:
            if self._is_newer(boot_before, plan.targetSpringBootVersion):
                status = "MANUAL_REVIEW"
                note = f"The source Spring Boot version ({boot_before}) is newer than the configured target ({plan.targetSpringBootVersion}). Automated downgrade was skipped."
            elif boot_before == plan.targetSpringBootVersion:
                note = "The project already uses the configured target Spring Boot version."

        phase_results = []
        for p in plan.activePacks:
            p_status = "completed" if (final_status in ("SUCCESS", "PARTIAL", "NO_CHANGES")) else "failed"
            if p == "springboot2-to-3" and boot_before == boot_after and boot_before is not None:
                p_status = "unchanged"
            if p.startswith("java") and java_before == java_after and java_before != "UNKNOWN":
                p_status = "unchanged"
            phase_results.append({"id": p, "status": p_status})

        return MigrationRunResult(
            success=final_status in ("SUCCESS", "PARTIAL", "NO_CHANGES") and status != "FAILED",
            status=status,
            tool=build_tool.lower(),
            project_dir=migrated_repo_dir,
            log_lines=accumulated_logs,
            error_lines=accumulated_errors,
            effective_target_java_version=java_after if java_after != "UNKNOWN" else effective_target,
            recipes=plan.activePacks,
            already_compatible=final_status == "NO_CHANGES" or (
                boot_before == boot_after and java_before == java_after
                and boot_before is not None and java_before != "UNKNOWN"
            ),
            spring_conversion_requested=bool(conversion_types and "spring_boot" in conversion_types),
            spring_boot_version_before=boot_before,
            spring_boot_version_after=boot_after,
            phase_results=phase_results,
            rule_executions=ast_result.rule_executions,
            spring_conversion_supported=True if boot_after else None,
            spring_conversion_note=note,
            dependency_upgrades=dependency_upgrades,
            dependency_migration_status=dep_status,
            plugin_upgrades=plugin_upgrades,
            plugin_migration_status=plugin_status,
        )

    def _compare_plugins(self, before: list[Any], after: list[Any], mappings: list[dict[str, str]]) -> list[dict]:
        """Compare build plugins before and after and report changes."""
        upgrades = []

        def get_plugin_key(p: Any) -> tuple[str, str]:
            gid = getattr(p, "group_id", None)
            aid = getattr(p, "artifact_id", None)
            if gid is None or aid is None:
                pid = getattr(p, "id", "")
                if pid and ":" in pid:
                    parts = pid.split(":")
                    gid = parts[0]
                    aid = parts[1]
                else:
                    gid = "org.apache.maven.plugins"
                    aid = pid
            return (gid or "org.apache.maven.plugins", aid or "")

        after_map = {get_plugin_key(p): p for p in after}

        mapping_dict = {(m["groupId"], m["artifactId"]): m["targetVersion"] for m in mappings}

        for p_before in before:
            key = get_plugin_key(p_before)
            p_after = after_map.get(key)

            if p_after:
                v_before = getattr(p_before, "version", None)
                v_after = getattr(p_after, "version", None)

                if v_before and v_after and v_before != v_after:
                    upgrades.append({
                        "coordinate": f"{key[0]}:{key[1]}",
                        "groupId": key[0],
                        "artifactId": key[1],
                        "oldVersion": v_before,
                        "newVersion": v_after,
                        "status": "UPGRADED",
                    })
        return upgrades

    def _compare_dependencies(self, before: list[Any], after: list[Any], mappings: list[dict[str, str]]) -> list[dict]:
        """Compare every dependency before and after and report changes or status."""
        results = []

        # Keys for comparison: (module, groupId, artifactId, scope, classifier)
        def get_key(d: Any) -> tuple[str, str, str, str, str]:
            return (
                str(getattr(d, "module", "root")),
                str(getattr(d, "group_id", "")),
                str(getattr(d, "artifact_id", "")),
                str(getattr(d, "scope", "compile")),
                str(getattr(d, "classifier", "") or ""),
            )

        before_map = {get_key(d): d for d in before}
        after_map = {get_key(d): d for d in after}

        # approved mapping dict for rule/target lookups
        mapping_dict = {(m["groupId"], m["artifactId"]): m["targetVersion"] for m in mappings}

        all_keys_set = set(before_map.keys())
        all_keys_set.update(after_map.keys())

        all_keys = list(all_keys_set)
        all_keys.sort()

        for key in all_keys:
            mod, gid, aid, scope, classifier = key
            dep_before = before_map.get(key)
            dep_after = after_map.get(key)

            v_before = getattr(dep_before, "resolved_version", None) or getattr(dep_before, "version", None) if dep_before else None
            v_after = getattr(dep_after, "resolved_version", None) or getattr(dep_after, "version", None) if dep_after else None

            status = "UNCHANGED"
            reason = "No resolved-version difference"

            target = mapping_dict.get((gid, aid))

            if not dep_before and dep_after:
                status = "ADDED"
                reason = "New dependency found in migrated tree"
            elif dep_before and not dep_after:
                status = "REMOVED"
                reason = "Dependency no longer present in migrated tree"
            elif dep_before and dep_after:
                if v_before != v_after and v_before and v_after:
                    if self._is_newer(v_after, v_before):
                        status = "UPGRADED"
                        if getattr(dep_after, "version_source", "") == "SPRING_BOOT_PARENT":
                            reason = "Resolved version changed through the upgraded Spring Boot parent"
                        else:
                            reason = f"Upgraded from {v_before} to {v_after}"
                    else:
                        # Downgrade detected!
                        status = "MANUAL_REVIEW"
                        reason = f"Configured target {v_after} is older than source {v_before}; downgrade prevented"
                else:
                    if target:
                        if v_before == target:
                            reason = "Already at approved target"
                        elif self._is_newer(v_before, target):
                            status = "MANUAL_REVIEW"
                            reason = f"Source version {v_before} is newer than configured target {target}; downgrade prevented"
                        else:
                            status = "FAILED"
                            reason = f"Maven could not resolve the configured target version {target}"
                    else:
                        reason = "No approved target mapping exists"
                        if getattr(dep_after, "version_source", "") == "SPRING_BOOT_PARENT":
                            reason = "Managed by unchanged Spring Boot parent"

            # Build result dict
            res = {
                "module": mod,
                "groupId": gid,
                "artifactId": aid,
                "scope": scope,
                "type": getattr(dep_after or dep_before, "type", "jar"),
                "classifier": classifier or None,
                "optional": getattr(dep_after or dep_before, "optional", False),
                "direct": getattr(dep_after or dep_before, "direct", True),
                "transitive": getattr(dep_after or dep_before, "transitive", False),
                "versionSource": getattr(dep_after or dep_before, "version_source", "UNKNOWN"),
                "sourceVersion": v_before,
                "resolvedSourceVersion": v_before,
                "configuredTargetVersion": target,
                "resolvedTargetVersion": v_after,
                "status": status,
                "reason": reason,
            }
            results.append(res)

        return results

    def _get_effective_java_version(self, project_dir: Path) -> str | None:
        """Use Maven to resolve the effective Java version."""
        mvn = resolve_executable("mvn")
        if not mvn:
            return None
        effective_dir = project_dir
        if not (project_dir / "pom.xml").exists():
            found_dir = find_shallowest_dir_with(project_dir, ("pom.xml",))
            if found_dir and (found_dir / "pom.xml").exists():
                effective_dir = found_dir
            else:
                return None

        # Priority properties to check
        for expr in ["maven.compiler.release", "maven.compiler.source", "maven.compiler.target"]:
            cmd = [mvn, "-q", "help:evaluate", f"-Dexpression={expr}", "-DforceStdout", "-B"]
            res = run_command(cmd, cwd=effective_dir, timeout=30)
            val = res.stdout.strip()
            if res.succeeded and val and not val.startswith("[") and val != "null":
                # Normalize 1.8 -> 8 etc.
                if val.startswith("1."):
                    return val.split(".")[1]
                return val
        return None

    def _get_effective_boot_version(self, project_dir: Path) -> str | None:
        """Use Maven to resolve the effective Spring Boot version."""
        mvn = resolve_executable("mvn")
        if not mvn:
            return None
        effective_dir = project_dir
        if not (project_dir / "pom.xml").exists():
            found_dir = find_shallowest_dir_with(project_dir, ("pom.xml",))
            if found_dir and (found_dir / "pom.xml").exists():
                effective_dir = found_dir
            else:
                return None

        # 1. Try common properties/parent via help:evaluate
        for expr in ["project.parent.version", "spring-boot.version", "spring.boot.version"]:
            cmd = [mvn, "-q", "help:evaluate", f"-Dexpression={expr}", "-DforceStdout", "-B"]
            res = run_command(cmd, cwd=effective_dir, timeout=30)
            val = res.stdout.strip()
            if res.succeeded and val and not val.startswith("[") and val != "null":
                if re.match(r"^\d+\.\d+\.\d+", val):
                    return val

        # 2. Fallback to dependency list
        cmd = [mvn, "dependency:list", "-DincludeGroupIds=org.springframework.boot", "-DincludeArtifactIds=spring-boot-starter", "-DoutputAbsoluteArtifactFilename=false", "-B"]
        res = run_command(cmd, cwd=effective_dir, timeout=60)
        if res.succeeded:
            for line in res.stdout.splitlines():
                if ":spring-boot-starter:jar:" in line:
                    parts = line.split(":spring-boot-starter:jar:")
                    if len(parts) > 1:
                        return parts[1].split(":")[0].strip()
        return None

    def _is_newer(self, v1: str, v2: str) -> bool:
        """Simple Maven-like version comparison.
        Returns True if v1 is strictly newer than v2.
        """
        if not v1 or not v2:
            return False

        def _parse(v: str) -> list:
            parts = []
            for p in re.split(r"[.\-]", v):
                if p.isdigit():
                    parts.append(int(p))
                else:
                    parts.append(p)
            return parts

        p1 = _parse(v1)
        p2 = _parse(v2)

        for i in range(max(len(p1), len(p2))):
            val1 = p1[i] if i < len(p1) else 0
            val2 = p2[i] if i < len(p2) else 0

            if isinstance(val1, int) and isinstance(val2, int):
                if val1 > val2:
                    return True
                if val1 < val2:
                    return False
            elif isinstance(val1, str) and isinstance(val2, str):
                if val1 > val2:
                    return True
                if val1 < val2:
                    return False
            elif isinstance(val1, int):
                return True
            else:
                return False
        return False
