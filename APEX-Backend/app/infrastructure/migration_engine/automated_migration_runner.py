"""Orchestrates the actual code migration using the custom AST-based engine.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.infrastructure.analyzers.project_analyzer import ProjectAnalyzer
from app.infrastructure.java_runtime import build_compatible_java_target
from app.infrastructure.migration_engine.ast_automated_migration_runner import AstMigrationRunner, AstMigrationRunResult
from app.infrastructure.migration_engine.ast_rule_mapper import AstRuleMapper
from app.shared.command_runner import resolve_executable, run_command

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
            project_root=analysis.project_root,
            source_java=analysis.current_java_version,
            target_java=effective_target,
            build_tool=build_tool,
            frameworks=analysis.frameworks,
            current_boot_version=analysis.spring_boot_version,
            conversion_types=conversion_types
        )

        # 3. Execution (Java Engine CLI)
        result = self._ast_runner.run(analysis.project_root, {
            "planId": plan.planId,
            "projectRoot": str(plan.projectRoot),
            "sourceJavaVersion": plan.sourceJavaVersion,
            "targetJavaVersion": plan.targetJavaVersion,
            "buildSystem": plan.buildSystem,
            "activePacks": plan.activePacks,
            "activeRules": plan.activeRules,
            "activeVisitors": plan.activeVisitors,
            "targetSpringBootVersion": plan.targetSpringBootVersion,
            "dependencyMappings": plan.dependencyMappings
        })

        # 4. Post-migration discovery to find the new version
        # Use robust Maven evaluation for the final report
        post_analysis = self._analyzer.analyze(migrated_repo_dir)
        boot_before = analysis.spring_boot_version
        boot_after = self._get_effective_boot_version(post_analysis.project_root) or post_analysis.spring_boot_version or boot_before

        java_before = analysis.current_java_version
        java_after = self._get_effective_java_version(post_analysis.project_root) or post_analysis.current_java_version or java_before

        # 5. Dependency upgrade results
        dependency_upgrades = self._compare_dependencies(analysis.dependencies, post_analysis.dependencies, plan.dependencyMappings)
        
        dep_status = "NOT_APPLICABLE"
        if conversion_types and "java_version" in conversion_types:
             if dependency_upgrades:
                  dep_status = "UPGRADED"
             else:
                  dep_status = "UNCHANGED"

        # 6. Plugin upgrade results
        plugin_upgrades = self._compare_plugins(analysis.build_plugins, post_analysis.build_plugins, plan.pluginMappings)
        plugin_status = "NOT_APPLICABLE"
        if conversion_types and "java_version" in conversion_types:
             if plugin_upgrades:
                  plugin_status = "UPGRADED"
             else:
                  plugin_status = "UNCHANGED"

        note = None
        status = result.status

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
             p_status = "completed" if result.success else "failed"
             if p == "springboot2-to-3" and boot_before == boot_after and boot_before is not None:
                  p_status = "unchanged"
             if p.startswith("java") and java_before == java_after and java_before != "UNKNOWN":
                  p_status = "unchanged"
             phase_results.append({"id": p, "status": p_status})

        return MigrationRunResult(
            success=result.success,
            status=status,
            tool=build_tool.lower(),
            project_dir=migrated_repo_dir,
            log_lines=result.log_lines,
            error_lines=result.error_lines,
            effective_target_java_version=java_after if java_after != "UNKNOWN" else effective_target,
            recipes=plan.activePacks,
            already_compatible=result.status == "NO_CHANGES" or (
                boot_before == boot_after and java_before == java_after
                and boot_before is not None and java_before != "UNKNOWN"
            ),
            spring_conversion_requested=bool(conversion_types and "spring_boot" in conversion_types),
            spring_boot_version_before=boot_before,
            spring_boot_version_after=boot_after,
            phase_results=phase_results,
            rule_executions=result.rule_executions,
            spring_conversion_supported=True if boot_after else None,
            spring_conversion_note=note,
            dependency_upgrades=dependency_upgrades,
            dependency_migration_status=dep_status,
            plugin_upgrades=plugin_upgrades,
            plugin_migration_status=plugin_status
        )

    def _compare_plugins(self, before: list[Any], after: list[Any], mappings: list[dict[str, str]]) -> list[dict]:
        """Compare build plugins before and after and report changes."""
        upgrades = []
        
        def get_plugin_key(p: Any) -> tuple[str, str]:
            # Handle both old and new BuildPlugin structures safely
            gid = getattr(p, "group_id", None)
            aid = getattr(p, "artifact_id", None)
            
            if gid is None or aid is None:
                # Fallback to parsing 'id' field if it exists (old structure)
                pid = getattr(p, "id", "")
                if ":" in pid:
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
                v_before = p_before.version
                v_after = p_after.version
                
                if v_before and v_after and v_before != v_after:
                    upgrades.append({
                        "coordinate": f"{key[0]}:{key[1]}",
                        "groupId": key[0],
                        "artifactId": key[1],
                        "oldVersion": v_before,
                        "newVersion": v_after,
                        "status": "UPGRADED"
                    })
        return upgrades

    def _compare_dependencies(self, before: list[Any], after: list[Any], mappings: list[dict[str, str]]) -> list[dict]:
        """Compare dependencies before and after and report changes."""
        upgrades = []
        after_map = {(d.group_id, d.artifact_id): d for d in after}

        mapping_dict = {(m["groupId"], m["artifactId"]): m["targetVersion"] for m in mappings}

        for dep_before in before:
            key = (dep_before.group_id, dep_before.artifact_id)
            dep_after = after_map.get(key)

            if dep_after:
                v_before = dep_before.resolved_version or dep_before.version
                v_after = dep_after.resolved_version or dep_after.version

                if v_before != v_after and v_before != "Unknown version" and v_after != "Unknown version":
                    upgrades.append({
                        "coordinate": f"{dep_before.group_id}:{dep_before.artifact_id}",
                        "groupId": dep_before.group_id,
                        "artifactId": dep_before.artifact_id,
                        "oldVersion": v_before,
                        "newVersion": v_after,
                        "resolvedVersion": v_after,
                        "status": "UPGRADED",
                        "versionSource": dep_after.version_source
                    })
                elif key in mapping_dict:
                    # If it was supposed to be upgraded but isn't
                    pass
        return upgrades

    def _get_effective_java_version(self, project_dir: Path) -> str | None:
        """Use Maven to resolve the effective Java version."""
        mvn = resolve_executable("mvn")
        if not mvn or not (project_dir / "pom.xml").exists():
            return None

        # Priority properties to check
        for expr in ["java.version", "maven.compiler.release", "maven.compiler.source"]:
            cmd = [mvn, "-q", "help:evaluate", f"-Dexpression={expr}", "-DforceStdout", "-B"]
            res = run_command(cmd, cwd=project_dir, timeout=30)
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
        if not mvn or not (project_dir / "pom.xml").exists():
            return None

        # 1. Try common properties/parent via help:evaluate
        for expr in ["project.parent.version", "spring-boot.version", "spring.boot.version"]:
            cmd = [mvn, "-q", "help:evaluate", f"-Dexpression={expr}", "-DforceStdout", "-B"]
            res = run_command(cmd, cwd=project_dir, timeout=30)
            val = res.stdout.strip()
            if res.succeeded and val and not val.startswith("[") and val != "null":
                if re.match(r"^\d+\.\d+\.\d+", val):
                    return val

        # 2. Fallback to dependency list
        cmd = [mvn, "dependency:list", "-DincludeGroupIds=org.springframework.boot", "-DincludeArtifactIds=spring-boot-starter", "-DoutputAbsoluteArtifactFilename=false", "-B"]
        res = run_command(cmd, cwd=project_dir, timeout=60)
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
        def _parse(v: str) -> list[int]:
            # Normalize: 3.2.5.RELEASE -> 3.2.5, 3.2.0-RC1 -> 3.2.0
            # Just take the numeric parts
            parts = []
            for p in re.split(r"[.\-]", v):
                if p.isdigit():
                    parts.append(int(p))
                else:
                    # Non-numeric parts like RELEASE or RC1 are ignored or treated as 0
                    break
            return parts

        p1 = _parse(v1)
        p2 = _parse(v2)

        # Compare element by element
        for i in range(max(len(p1), len(p2))):
            val1 = p1[i] if i < len(p1) else 0
            val2 = p2[i] if i < len(p2) else 0
            if val1 > val2:
                return True
            if val1 < val2:
                return False
        return False
