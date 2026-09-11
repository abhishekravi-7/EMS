"""Extracts declared dependencies from Maven or Gradle build files."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element  # nosec B405 - type annotation only; callers parse via defusedxml
from defusedxml.ElementTree import fromstring

from app.shared.command_runner import resolve_executable, run_command

logger = logging.getLogger(__name__)

_GRADLE_CONFIGS = (
    "implementation",
    "api",
    "compileOnly",
    "compileOnlyApi",
    "runtimeOnly",
    "testImplementation",
    "testCompileOnly",
    "testRuntimeOnly",
    "annotationProcessor",
    "developmentOnly",
    "compile",  # legacy
    "testCompile",  # legacy
)


@dataclass(frozen=True)
class Dependency:
    group_id: str
    artifact_id: str
    version: str | None
    module: str = "root"
    name: str | None = None
    type: str = "jar"
    classifier: str | None = None
    scope: str = "compile"
    optional: bool = False
    direct: bool = True
    transitive: bool = False
    declared_version: str | None = None
    resolved_version: str | None = None
    version_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "name": self.name or f"{self.group_id}:{self.artifact_id}",
            "groupId": self.group_id,
            "artifactId": self.artifact_id,
            "version": self.version,
            "type": self.type,
            "classifier": self.classifier,
            "scope": self.scope,
            "optional": self.optional,
            "direct": self.direct,
            "transitive": self.transitive,
            "declaredVersion": self.declared_version,
            "resolvedVersion": self.resolved_version,
            "versionSource": self.version_source,
        }


class DependencyAnalyzer:
    def analyze(
        self,
        pom_root: Element | None,
        build_gradle_text: str,
        project_root: Path | None = None,
    ) -> list[Dependency]:
        if pom_root is not None:
            return self._from_maven_comprehensive(project_root)
        if build_gradle_text:
            return self._from_gradle(build_gradle_text)
        return []

    # -- Maven Comprehensive -------------------------------------------------- #

    def _from_maven_comprehensive(self, project_root: Path | None) -> list[Dependency]:
        if not project_root or not (project_root / "pom.xml").exists():
            return []

        mvn = resolve_executable("mvn")
        if not mvn:
            logger.debug("Maven executable not found; falling back to basic parsing.")
            return []

        tree_file = project_root / f"dep-tree-{uuid.uuid4().hex[:8]}.txt"
        pom_file = project_root / f"eff-pom-{uuid.uuid4().hex[:8]}.xml"

        cmd_tree = [mvn, "dependency:tree", f"-DoutputFile={tree_file.name}", "-B"]
        cmd_pom = [mvn, "help:effective-pom", f"-Doutput={pom_file.name}", "-B"]

        try:
            run_command(cmd_tree, cwd=project_root, timeout=120)
            run_command(cmd_pom, cwd=project_root, timeout=120)
            
            tree_content = tree_file.read_text(encoding="utf-8") if tree_file.exists() else ""
            pom_content = pom_file.read_text(encoding="utf-8") if pom_file.exists() else ""
            
            tree_file.unlink(missing_ok=True)
            pom_file.unlink(missing_ok=True)

            return self._parse_maven_outputs(tree_content, pom_content)
        except Exception as exc:
            logger.error("Error during comprehensive Maven analysis: %s", exc)
            return []

    def _parse_maven_outputs(self, tree_content: str, pom_content: str) -> list[Dependency]:
        """Parse dependency:tree and help:effective-pom to extract every dependency."""
        resolved_deps: dict[tuple[str, str, str, str, str], Dependency] = {}
        
        current_module = "root"
        lines = tree_content.splitlines()
        
        # 0. Identify internal modules
        internal_modules = set()
        for line in lines:
            clean_line = line.replace("[INFO]", "").strip()
            m = re.match(r"^([\w.\-]+):([\w.\-]+):pom:([\w.\-]+)$", clean_line)
            if m: internal_modules.add((m.group(1), m.group(2)))

        dep_re = re.compile(r"([\w.\-]+):([\w.\-]+):([\w.\-]+):(?:([\w.\-]+):)?([\w.\-]+):([\w.\-]+)$")
        
        for line in lines:
            info_content = line.split("[INFO]", 1)[1] if "[INFO]" in line else line
            clean_line = info_content.strip()
            if not clean_line: continue
            
            if not any(m in info_content[:10] for m in ["+-", "\\-", "|"]):
                module_match = re.match(r"^([\w.\-]+):([\w.\-]+):pom:([\w.\-]+)$", clean_line)
                if module_match:
                    current_module = module_match.group(2)
                    continue

            dep_match = dep_re.search(clean_line)
            if dep_match:
                gid, aid, dtype, classifier, version, scope = dep_match.groups()
                
                marker_idx = info_content.find("+-")
                if marker_idx == -1: marker_idx = info_content.find("\\-")
                
                # Heuristic for direct vs transitive
                prefix = info_content[:marker_idx] if marker_idx != -1 else info_content
                is_direct = "|" not in prefix and marker_idx != -1
                
                key = (current_module, gid, aid, scope, classifier or "")
                
                if key not in resolved_deps:
                    v_source = "TRANSITIVE" if not is_direct else "UNKNOWN"
                    if (gid, aid) in internal_modules:
                         v_source = "INTERNAL_MODULE"
                         
                    resolved_deps[key] = Dependency(
                        group_id=gid,
                        artifact_id=aid,
                        version=version,
                        module=current_module,
                        type=dtype,
                        classifier=classifier,
                        scope=scope,
                        direct=is_direct,
                        transitive=not is_direct,
                        resolved_version=version,
                        version_source=v_source
                    )

        if pom_content:
            try:
                root = fromstring(pom_content)
                for el in root.iter():
                    if isinstance(el.tag, str) and "}" in el.tag:
                        el.tag = el.tag.split("}", 1)[1]
                
                for dep in resolved_deps.values():
                    if dep.version_source == "UNKNOWN":
                         source = "DIRECT"
                         if dep.group_id.startswith("org.springframework.boot"):
                              source = "SPRING_BOOT_PARENT"
                         
                         object.__setattr__(dep, 'version_source', source)
            except:
                pass
        
        return list(resolved_deps.values())

    # -- Gradle -------------------------------------------------------------- #

    def _from_gradle(self, build_text: str) -> list[Dependency]:
        result: list[Dependency] = []
        seen: set[tuple[str, str]] = set()
        configs = "|".join(_GRADLE_CONFIGS)

        pattern = re.compile(
            rf"\b(?:{configs})\s*[(\s]\s*['\"]([^'\"]+:[^'\"]+)['\"]",
        )
        for match in pattern.finditer(build_text):
            coordinate = match.group(1)
            parts = coordinate.split(":")
            if len(parts) < 2:
                continue
            group, artifact = parts[0], parts[1]
            version = parts[2] if len(parts) >= 3 else None
            key = (group, artifact)
            if key in seen:
                continue
            seen.add(key)
            result.append(Dependency(group, artifact, version))
        return result
