import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from app.core.config import settings

@dataclass(frozen=True)
class AstMigrationPlan:
    planId: str
    projectRoot: str
    sourceJavaVersion: int
    targetJavaVersion: int
    buildSystem: str
    activePacks: list[str] = field(default_factory=list)
    activeRules: list[str] = field(default_factory=list)
    activeVisitors: list[str] = field(default_factory=list)
    targetSpringBootVersion: str | None = None
    incompatibleReason: str | None = None
    dependencyMappings: list[dict[str, str]] = field(default_factory=list)
    pluginMappings: list[dict[str, str]] = field(default_factory=list)

def load_catalog() -> dict[str, Any]:
    try:
        return json.loads(settings.migration_recipe_catalog_path.read_text(encoding="utf-8"))
    except Exception:
        return {"packs": [], "springBootMappings": [], "dependencyMappings": [], "pluginMappings": []}

def _parse_major(version: str | None) -> int | None:
    if not version:
        return None
    text = version.strip().lower().replace("java", "").strip()
    if text.startswith("1."):
        text = text.split(".", 1)[1]
    text = text.split(".", 1)[0]
    return int(text) if text.isdigit() else None

class AstRuleMapper:
    def __init__(self) -> None:
        self._catalog = load_catalog()

    def build_plan(
        self,
        project_root: Path,
        source_java: str,
        target_java: str,
        build_tool: str,
        frameworks: list[str],
        current_boot_version: str | None = None,
        conversion_types: list[str] | None = None
    ) -> AstMigrationPlan:
        selected_packs = []
        selected_rules = []
        selected_visitors = []

        source_major = _parse_major(source_java) or 8
        target_major = _parse_major(target_java) or 17

        # 1. Java Version Packs (Implicitly always considered if java_version is in conversion_types)
        if conversion_types and "java_version" in conversion_types:
            if source_major < 11 and target_major >= 11:
                selected_packs.append("java8-to-11")
            if source_major < 17 and target_major >= 17:
                selected_packs.append("java11-to-17")
            if source_major < 21 and target_major >= 21:
                selected_packs.append("java17-to-21")
            
            # Always include dependency and plugin upgrade if Java is being upgraded
            selected_packs.append("dependency-upgrade")
            selected_packs.append("plugin-upgrade")

        # 2. Framework Packs
        target_boot = None
        if "spring-boot" in frameworks:
            mappings = self._catalog.get("springBootMappings", [])
            for m in mappings:
                if m.get("targetJava") == target_major:
                    target_boot = m.get("targetSpringBoot")
                    break

            if target_boot:
                # Only add the upgrade pack if current version is older
                if not current_boot_version or self._is_newer(target_boot, current_boot_version):
                    selected_packs.append("springboot2-to-3")

        if "jakarta-ee" in frameworks or "javax-ee" in frameworks or ("spring-boot" in frameworks and target_major >= 17):
            selected_packs.append("javax-to-jakarta")

        # 3. Resolve Rules and Visitors from Catalog
        all_packs = self._catalog.get("packs", [])
        for pack_id in selected_packs:
            pack_def = None
            for p in all_packs:
                if p["id"] == pack_id:
                    pack_def = p
                    break
            
            if pack_def:
                for phase in pack_def.get("phases", []):
                    selected_rules.extend(phase.get("rules", []))
                    selected_visitors.extend(phase.get("visitors", []))

        # 4. Deduplicate
        selected_rules = list(dict.fromkeys(selected_rules))
        selected_visitors = list(dict.fromkeys(selected_visitors))

        # Always include cleanup
        if "IMPORT-CLEANUP" not in selected_visitors:
            selected_visitors.append("IMPORT-CLEANUP")

        # 5. Validate Compatibility (e.g. SB3 requires Java 17+)
        incompatible_reason = None
        if target_boot and target_boot.startswith("3.") and target_major < 17:
             incompatible_reason = "The selected Java target is not compatible with the target Spring Boot version (Spring Boot 3 requires Java 17+)."

        return AstMigrationPlan(
            planId="PLAN-" + project_root.name,
            projectRoot=str(project_root),
            sourceJavaVersion=source_major,
            targetJavaVersion=target_major,
            buildSystem=build_tool,
            activePacks=selected_packs,
            activeRules=selected_rules,
            activeVisitors=selected_visitors,
            targetSpringBootVersion=target_boot,
            incompatibleReason=incompatible_reason,
            dependencyMappings=self._catalog.get("dependencyMappings", []),
            pluginMappings=self._catalog.get("pluginMappings", [])
        )

    def _is_newer(self, v1: str, v2: str) -> bool:
        """Simple Maven-like version comparison."""
        try:
            p1 = [int(x) for x in re.findall(r"\d+", v1)]
            p2 = [int(x) for x in re.findall(r"\d+", v2)]
            return p1 > p2
        except:
            return v1 > v2
