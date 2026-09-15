import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from app.core.config import settings
from app.shared import file_utils

logger = logging.getLogger(__name__)


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
    catalog_path = getattr(settings, "migration_recipe_catalog_path", None)
    if catalog_path and Path(catalog_path).exists():
        try:
            return json.loads(Path(catalog_path).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse catalog JSON from %s: %s", catalog_path, exc)
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
    """Dynamic rule planner evaluating catalog packs and AST visitors."""

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
        conversion_types: list[str] | None = None,
    ) -> AstMigrationPlan:
        selected_packs: list[str] = []
        selected_rules: list[str] = []
        selected_visitors: list[str] = []

        source_major = _parse_major(source_java) or 8
        target_major = _parse_major(target_java) or 17
        normalized_frameworks = [f.lower() for f in (frameworks or [])]
        normalized_build_tool = (build_tool or "MAVEN").upper()

        catalog_packs = self._catalog.get("packs", [])
        if isinstance(catalog_packs, list) and catalog_packs:
            for pack in catalog_packs:
                if not isinstance(pack, dict):
                    continue
                pack_id = pack.get("id")
                if not pack_id or pack_id in selected_packs:
                    continue

                conds = pack.get("conditions", {})
                req_source = conds.get("sourceJavaVersion")
                req_target = conds.get("targetJavaVersion")
                req_build = conds.get("buildSystem")
                req_frameworks = [f.lower() for f in conds.get("frameworks", [])]

                match = True
                if req_source is not None and source_major > req_source:
                    match = False
                if req_target is not None and target_major < req_target:
                    match = False
                if req_build is not None and req_build.upper() != normalized_build_tool:
                    match = False
                if req_frameworks and not any(fw in normalized_frameworks for fw in req_frameworks):
                    match = False

                if match:
                    selected_packs.append(pack_id)

        # Java Version Packs (Implicitly always considered if conversion_types is None or contains "java_version")
        if conversion_types is None or "java_version" in conversion_types:
            if source_major < 11 and target_major >= 11 and "java8-to-11" not in selected_packs:
                selected_packs.append("java8-to-11")
            if source_major < 17 and target_major >= 17 and "java11-to-17" not in selected_packs:
                selected_packs.append("java11-to-17")
            if source_major < 21 and target_major >= 21 and "java17-to-21" not in selected_packs:
                selected_packs.append("java17-to-21")

            if source_major < target_major:
                if "dependency-upgrade" not in selected_packs:
                    selected_packs.append("dependency-upgrade")
                if "plugin-upgrade" not in selected_packs:
                    selected_packs.append("plugin-upgrade")

        # Framework Packs
        target_boot = None
        if "spring-boot" in normalized_frameworks:
            mappings = self._catalog.get("springBootMappings", [])
            for m in mappings:
                if m.get("targetJava") == target_major:
                    target_boot = m.get("targetSpringBoot")
                    break

            if target_boot:
                if not current_boot_version or self._is_newer(target_boot, current_boot_version):
                    if "springboot2-to-3" not in selected_packs:
                        selected_packs.append("springboot2-to-3")
                else:
                    if "springboot2-to-3" in selected_packs:
                        selected_packs.remove("springboot2-to-3")
            elif current_boot_version and not self._is_newer("3.0.0", current_boot_version):
                if "springboot2-to-3" in selected_packs:
                    selected_packs.remove("springboot2-to-3")

        if (
            any(fw in normalized_frameworks for fw in ("jakarta-ee", "javax-ee", "jakarta", "javax"))
            or ("spring-boot" in normalized_frameworks and target_major >= 17)
        ):
            if "javax-to-jakarta" not in selected_packs:
                selected_packs.append("javax-to-jakarta")
            if "JAVAX-TO-JAKARTA" not in selected_visitors:
                selected_visitors.append("JAVAX-TO-JAKARTA")

        # Resolve Rules and Visitors from Catalog for selected packs
        all_packs = self._catalog.get("packs", [])
        for pack_id in selected_packs:
            for p in all_packs:
                if isinstance(p, dict) and p.get("id") == pack_id:
                    for phase in p.get("phases", []):
                        if isinstance(phase, dict):
                            selected_rules.extend(phase.get("rules", []))
                            selected_visitors.extend(phase.get("visitors", []))

        # Deduplicate
        selected_packs = list(dict.fromkeys(selected_packs))
        selected_rules = list(dict.fromkeys(selected_rules))
        selected_visitors = list(dict.fromkeys(selected_visitors))

        if "IMPORT-CLEANUP" not in selected_visitors:
            selected_visitors.append("IMPORT-CLEANUP")

        # Validate Compatibility (e.g. SB3 requires Java 17+)
        incompatible_reason = None
        if target_boot and target_boot.startswith("3.") and target_major < 17:
            incompatible_reason = "The selected Java target is not compatible with the target Spring Boot version (Spring Boot 3 requires Java 17+)."

        return AstMigrationPlan(
            planId=f"PLAN-{project_root.name}",
            projectRoot=file_utils.to_plain_path_str(project_root),

            sourceJavaVersion=source_major,
            targetJavaVersion=target_major,
            buildSystem=normalized_build_tool,
            activePacks=selected_packs,
            activeRules=selected_rules,
            activeVisitors=selected_visitors,
            targetSpringBootVersion=target_boot,
            incompatibleReason=incompatible_reason,
            dependencyMappings=self._catalog.get("dependencyMappings", []),
            pluginMappings=self._catalog.get("pluginMappings", []),
        )

    def _is_newer(self, v1: str, v2: str) -> bool:
        """Simple Maven-like version comparison."""
        try:
            p1 = [int(x) for x in re.findall(r"\d+", v1)]
            p2 = [int(x) for x in re.findall(r"\d+", v2)]
            return p1 > p2
        except Exception:
            return v1 > v2
