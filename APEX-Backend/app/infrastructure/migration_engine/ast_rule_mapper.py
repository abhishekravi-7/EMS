import json
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

def load_catalog() -> dict[str, Any]:
    try:
        return json.loads(settings.migration_recipe_catalog_path.read_text(encoding="utf-8"))
    except Exception:
        return {"packs": []}

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
        frameworks: list[str]
    ) -> AstMigrationPlan:
        # Simplified deterministic planning logic
        selected_packs = []
        selected_rules = []
        selected_visitors = []
        
        source_major = _parse_major(source_java) or 8
        target_major = _parse_major(target_java) or 17
        
        # 1. Java Version Packs
        if source_major < 11 and target_major >= 11:
            selected_packs.append("java8-to-11")
        if source_major < 17 and target_major >= 17:
            selected_packs.append("java11-to-17")
        if source_major < 21 and target_major >= 21:
            selected_packs.append("java17-to-21")
            
        # 2. Framework Packs
        if "spring-boot" in frameworks:
            if target_major >= 17:
                selected_packs.append("springboot2-to-3")
            else:
                selected_packs.append("springboot-to-2.7")
        if ("jakarta-ee" in frameworks or "javax-ee" in frameworks or "spring-boot" in frameworks) and target_major >= 17:
            selected_packs.append("javax-to-jakarta")
            selected_visitors.append("JAVAX-TO-JAKARTA")

        # 3. Always include cleanup
        selected_visitors.append("IMPORT-CLEANUP")
        
        return AstMigrationPlan(
            planId="PLAN-" + project_root.name,
            projectRoot=str(project_root),
            sourceJavaVersion=source_major,
            targetJavaVersion=target_major,
            buildSystem=build_tool,
            activePacks=selected_packs,
            activeRules=selected_rules,
            activeVisitors=selected_visitors
        )
