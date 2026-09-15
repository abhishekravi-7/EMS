"""Gradle Build Script Modernizer Engine.

Performs deterministic Gradle build manifest modernizations:
1. Spring Boot plugin version upgrades (e.g. 2.7.x -> 3.2.5 when target Java is >= 17/21).
2. Java toolchain and compatibility configuration (sourceCompatibility, targetCompatibility, JavaLanguageVersion).
3. Legacy javax.* to jakarta.* dependency artifact modernizations.
4. Multi-subproject Gradle monorepo traversal and inheritance synchronization.
5. Extraction of structured dependency upgrade records for migration reporting.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_JAVAX_TO_JAKARTA_GRADLE = {
    "javax.persistence:javax.persistence-api": ("jakarta.persistence", "jakarta.persistence-api", "3.1.0"),
    "javax.persistence": ("jakarta.persistence", "jakarta.persistence-api", "3.1.0"),
    "javax.servlet:javax.servlet-api": ("jakarta.servlet", "jakarta.servlet-api", "6.0.0"),
    "javax.annotation:javax.annotation-api": ("jakarta.annotation", "jakarta.annotation-api", "2.1.1"),
    "javax.validation:validation-api": ("jakarta.validation", "jakarta.validation-api", "3.0.2"),
}

_IGNORED_DIRS = {"build", ".gradle", ".git", ".idea", ".settings", "node_modules", "bin", "out"}


@dataclass
class GradleModernizationResult:
    modified: bool
    changed_files: list[str] = field(default_factory=list)
    log_lines: list[str] = field(default_factory=list)
    dependency_upgrades: list[dict[str, str]] = field(default_factory=list)
    spring_boot_before: str | None = None
    spring_boot_after: str | None = None


class GradleModernizer:
    def modernize(self, project_dir: Path, target_java_version: str) -> GradleModernizationResult:
        """Modernize target build.gradle / build.gradle.kts files across subprojects."""
        if not project_dir.exists():
            return GradleModernizationResult(modified=False)

        build_files = self._discover_build_files(project_dir)
        if not build_files:
            return GradleModernizationResult(modified=False)

        logs: list[str] = []
        changed_files: list[str] = []
        upgrades: list[dict[str, str]] = []
        spring_boot_before: str | None = None
        spring_boot_after: str | None = None
        is_any_modified = False

        target_java = str(target_java_version or "17").strip()

        for build_file in build_files:
            rel_path = build_file.relative_to(project_dir).as_posix() if build_file.is_relative_to(project_dir) else build_file.name
            is_root = build_file.parent == project_dir

            single_res = self._modernize_single_build_file(
                build_file=build_file,
                rel_path=rel_path,
                target_java=target_java,
                is_root=is_root,
            )

            if single_res.modified:
                is_any_modified = True
                changed_files.extend(single_res.changed_files)
                logs.extend(single_res.log_lines)

            if is_root or not spring_boot_before:
                if single_res.spring_boot_before:
                    spring_boot_before = single_res.spring_boot_before
                if single_res.spring_boot_after:
                    spring_boot_after = single_res.spring_boot_after

            for up in single_res.dependency_upgrades:
                if not any(existing.get("artifact_id") == up.get("artifact_id") for existing in upgrades):
                    upgrades.append(up)

        return GradleModernizationResult(
            modified=is_any_modified,
            changed_files=changed_files,
            log_lines=logs,
            dependency_upgrades=upgrades,
            spring_boot_before=spring_boot_before,
            spring_boot_after=spring_boot_after,
        )

    def _discover_build_files(self, project_dir: Path) -> list[Path]:
        """Find root build.gradle / build.gradle.kts first, followed by subproject build scripts."""
        if project_dir.is_file():
            return [project_dir]

        discovered: list[Path] = []
        for name in ("build.gradle", "build.gradle.kts"):
            root_candidate = project_dir / name
            if root_candidate.is_file():
                discovered.append(root_candidate)

        for pattern in ("**/build.gradle", "**/build.gradle.kts"):
            for candidate in project_dir.glob(pattern):
                if candidate in discovered:
                    continue
                if any(part in _IGNORED_DIRS for part in candidate.parts):
                    continue
                discovered.append(candidate)

        return discovered

    def _modernize_single_build_file(
        self,
        build_file: Path,
        rel_path: str,
        target_java: str,
        is_root: bool,
    ) -> GradleModernizationResult:
        content = build_file.read_text(encoding="utf-8", errors="ignore")
        original_content = content
        logs: list[str] = []
        upgrades: list[dict[str, str]] = []

        try:
            target_major = int(target_java)
        except ValueError:
            target_major = 17

        spring_boot_before: str | None = None
        spring_boot_after: str | None = None
        module_prefix = f"[{rel_path}] " if not is_root else ""

        # 1. Update Spring Boot Plugin Version (DSL Groovy & Kotlin)
        boot_match = (
            re.search(r"id\s*['\"]org\.springframework\.boot['\"]\s*version\s*['\"]([^'\"]+)['\"]", content)
            or re.search(r"id\(\"org\.springframework\.boot\"\)\s*version\s*\"([^\"]+)\"", content)
            or re.search(r"springBootVersion\s*=\s*['\"]([^'\"]+)['\"]", content)
        )
        if boot_match:
            spring_boot_before = boot_match.group(1).strip()
            if target_major >= 17 and (spring_boot_before.startswith("1.") or spring_boot_before.startswith("2.")):
                target_boot_version = "3.2.5"
                content = re.sub(
                    r"(id\s*['\"]org\.springframework\.boot['\"]\s*version\s*['\"])[^'\"]+(['\"])",
                    rf"\g<1>{target_boot_version}\g<2>",
                    content,
                )
                content = re.sub(
                    r'(id\("org\.springframework\.boot"\)\s*version\s*")[^"]+(")',
                    rf"\g<1>{target_boot_version}\g<2>",
                    content,
                )
                content = re.sub(
                    r"(springBootVersion\s*=\s*['\"])[^'\"]+(['\"])",
                    rf"\g<1>{target_boot_version}\g<2>",
                    content,
                )
                spring_boot_after = target_boot_version
                logs.append(f"{module_prefix}Upgraded Gradle Spring Boot plugin version from {spring_boot_before} to {target_boot_version} for Java {target_java} compatibility.")
                upgrades.append({
                    "group_id": "org.springframework.boot",
                    "artifact_id": "spring-boot-gradle-plugin",
                    "old_version": spring_boot_before,
                    "new_version": target_boot_version,
                    "status": "UPGRADED",
                })
            else:
                spring_boot_after = spring_boot_before

        # 2. Update Java Compatibility / Toolchain Settings
        if "sourceCompatibility" in content:
            content = re.sub(r"sourceCompatibility\s*=\s*['\"]?\d+(?:\.\d+)?['\"]?", f"sourceCompatibility = '{target_java}'", content)
            content = re.sub(r"sourceCompatibility\s*=\s*JavaVersion\.VERSION_\d+_\d+", f"sourceCompatibility = JavaVersion.VERSION_{target_java}", content)
            logs.append(f"{module_prefix}Updated sourceCompatibility to {target_java}.")

        if "targetCompatibility" in content:
            content = re.sub(r"targetCompatibility\s*=\s*['\"]?\d+(?:\.\d+)?['\"]?", f"targetCompatibility = '{target_java}'", content)
            content = re.sub(r"targetCompatibility\s*=\s*JavaVersion\.VERSION_\d+_\d+", f"targetCompatibility = JavaVersion.VERSION_{target_java}", content)
            logs.append(f"{module_prefix}Updated targetCompatibility to {target_java}.")

        if "JavaLanguageVersion.of(" in content:
            content = re.sub(r"JavaLanguageVersion\.of\(\d+\)", f"JavaLanguageVersion.of({target_java})", content)
            logs.append(f"{module_prefix}Updated Gradle JavaLanguageVersion toolchain to {target_java}.")

        # 3. Modernize Javax to Jakarta Dependencies in Gradle
        for legacy_coord, (new_group, new_art, new_ver) in _JAVAX_TO_JAKARTA_GRADLE.items():
            artifact_part = legacy_coord.split(":")[1] if ":" in legacy_coord else legacy_coord
            if legacy_coord in content or artifact_part in content:
                content = re.sub(
                    rf"['\"]{re.escape(legacy_coord)}(?::[^'\"]+)?['\"]",
                    f"'{new_group}:{new_art}:{new_ver}'",
                    content,
                )
                logs.append(f"{module_prefix}Migrated Gradle dependency {legacy_coord} to {new_group}:{new_art}:{new_ver}.")
                upgrades.append({
                    "group_id": new_group,
                    "artifact_id": new_art,
                    "old_version": "2.x (javax)",
                    "new_version": f"{new_ver} (jakarta)",
                    "status": "UPGRADED",
                })

        is_modified = content != original_content
        if is_modified:
            build_file.write_text(content, encoding="utf-8")

        return GradleModernizationResult(
            modified=is_modified,
            changed_files=[rel_path] if is_modified else [],
            log_lines=logs,
            dependency_upgrades=upgrades,
            spring_boot_before=spring_boot_before,
            spring_boot_after=spring_boot_after,
        )
