import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from app.core.config import settings

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


def load_catalog() -> dict[str, Any]:
    catalog_path = getattr(settings, "migration_recipe_catalog_path", None)
    if catalog_path and catalog_path.exists():
        try:
            return json.loads(catalog_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse catalog JSON from %s: %s", catalog_path, exc)
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
                    for phase in pack.get("phases", []):
                        if isinstance(phase, dict):
                            selected_rules.extend(phase.get("rules", []))
                            selected_visitors.extend(phase.get("visitors", []))

        # Fallback deterministic rules if catalog yielded empty packs
        if not selected_packs:
            if source_major < 11 and target_major >= 11:
                selected_packs.append("java8-to-11")
            if source_major < 17 and target_major >= 17:
                selected_packs.append("java11-to-17")
            if source_major < 21 and target_major >= 21:
                selected_packs.append("java17-to-21")

            if "spring-boot" in normalized_frameworks:
                selected_packs.append("springboot2-to-3")
            if any(fw in normalized_frameworks for fw in ("jakarta-ee", "javax-ee", "jakarta", "javax")):
                selected_packs.append("javax-to-jakarta")
                selected_visitors.append("JAVAX-TO-JAKARTA")

        if "IMPORT-CLEANUP" not in selected_visitors:
            selected_visitors.append("IMPORT-CLEANUP")

        return AstMigrationPlan(
            planId=f"PLAN-{project_root.name}",
            projectRoot=str(project_root),
            sourceJavaVersion=source_major,
            targetJavaVersion=target_major,
            buildSystem=normalized_build_tool,
            activePacks=list(dict.fromkeys(selected_packs)),
            activeRules=list(dict.fromkeys(selected_rules)),
            activeVisitors=list(dict.fromkeys(selected_visitors)),
        )
