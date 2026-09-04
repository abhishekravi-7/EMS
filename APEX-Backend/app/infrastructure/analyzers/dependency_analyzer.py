"""Extracts declared dependencies from Maven or Gradle build files."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree.ElementTree import Element  # nosec B405 - type annotation only; callers parse via defusedxml

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
    declared_version: str | None = None
    resolved_version: str | None = None
    version_source: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "groupId": self.group_id,
            "artifactId": self.artifact_id,
            "version": self.version,
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
            return self._from_maven(pom_root, project_root)
        if build_gradle_text:
            return self._from_gradle(build_gradle_text)
        return []

    # -- Maven --------------------------------------------------------------- #

    def _from_maven(self, pom_root: Element, project_root: Path | None = None) -> list[Dependency]:
        properties = self._maven_properties(pom_root)
        managed = self._maven_managed_dependencies(pom_root, properties)

        resolved_from_mvn = {}
        if project_root and (project_root / "pom.xml").exists():
            resolved_from_mvn = self._resolve_via_maven(project_root)

        dependencies_block = pom_root.find("dependencies")
        if dependencies_block is None:
            return []

        result: list[Dependency] = []
        for dependency in dependencies_block.findall("dependency"):
            group = self._text(dependency.find("groupId"))
            artifact = self._text(dependency.find("artifactId"))
            if not group or not artifact:
                continue

            raw_version = self._text(dependency.find("version"))
            declared = self._resolve(raw_version, properties)

            # Priority resolution
            resolved = declared
            source = "Declared in POM" if raw_version else None

            if not resolved:
                # Try managed dependencies from current POM
                resolved = managed.get((group, artifact))
                if resolved:
                    source = "Managed in POM"

            if not resolved:
                # Try Maven resolution (Effective POM / Dependency List)
                resolved = resolved_from_mvn.get((group, artifact))
                if resolved:
                    source = "Resolved by Maven (Effective POM/BOM)"

            # Final fallback/labeling
            status_reason = None
            if not resolved:
                if not raw_version:
                    status_reason = "MANAGED_VERSION_UNAVAILABLE"
                elif declared != raw_version and not declared:
                    status_reason = "VERSION_PROPERTY_UNRESOLVED"
                else:
                    status_reason = "MAVEN_RESOLUTION_FAILED"

            result.append(Dependency(
                group_id=group,
                artifact_id=artifact,
                version=resolved or "Unknown version",
                declared_version=declared,
                resolved_version=resolved,
                version_source=source if resolved else status_reason
            ))
        return result

    def _resolve_via_maven(self, project_dir: Path) -> dict[tuple[str, str], str]:
        """Run 'mvn dependency:list' to get fully resolved versions."""
        mvn = resolve_executable("mvn")
        if not mvn:
            logger.debug("Maven executable not found; skipping dynamic resolution.")
            return {}

        command = [mvn, "dependency:list", "-DoutputAbsoluteArtifactFilename=false", "-B"]
        try:
            result = run_command(command, cwd=project_dir, timeout=60)
            if not result.succeeded:
                logger.debug("Maven dependency:list failed: %s", result.stderr)
                return {}
            return self._parse_mvn_dependency_list(result.stdout)
        except Exception as exc:
            logger.debug("Error running Maven: %s", exc)
            return {}

    @staticmethod
    def _parse_mvn_dependency_list(stdout: str) -> dict[tuple[str, str], str]:
        resolved = {}
        for line in stdout.splitlines():
            if "[INFO]    " not in line:
                continue
            parts = line.split("[INFO]    ")[-1].strip().split(":")
            if len(parts) >= 4:
                group = parts[0]
                artifact = parts[1]
                version = parts[-2]
                resolved[(group, artifact)] = version
        return resolved

    def _maven_managed_dependencies(self, pom_root: Element, properties: dict[str, str]) -> dict[tuple[str, str], str]:
        managed = {}
        dep_mgmt = pom_root.find("dependencyManagement")
        if dep_mgmt is not None:
            deps = dep_mgmt.find("dependencies")
            if deps is not None:
                for dependency in deps.findall("dependency"):
                    group = self._text(dependency.find("groupId"))
                    artifact = self._text(dependency.find("artifactId"))
                    version = self._resolve(self._text(dependency.find("version")), properties)
                    if group and artifact and version:
                        managed[(group, artifact)] = version
        return managed

    @staticmethod
    def _maven_properties(pom_root: Element) -> dict[str, str]:
        properties: dict[str, str] = {}
        block = pom_root.find("properties")
        if block is not None:
            for child in block:
                if child.text:
                    properties[child.tag] = child.text.strip()
        return properties

    @staticmethod
    def _resolve(version: str | None, properties: dict[str, str]) -> str | None:
        if not version:
            return None
        match = re.fullmatch(r"\$\{(.+?)\}", version.strip())
        if match:
            return properties.get(match.group(1))
        return version.strip()

    @staticmethod
    def _text(node: Element | None) -> str | None:
        return node.text.strip() if node is not None and node.text else None

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
