"""Gradle Build Script Modernizer Engine.

Performs deterministic Gradle build manifest modernizations:
1. Spring Boot plugin version upgrades (e.g. 2.7.x -> 3.2.5 when target Java is >= 17/21).
2. Java toolchain and compatibility configuration (sourceCompatibility, targetCompatibility, JavaLanguageVersion).
3. Legacy javax.* to jakarta.* dependency artifact modernizations.
4. Extraction of structured dependency upgrade records for migration reporting.
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
        """Modernize target build.gradle / build.gradle.kts file cleanly."""
        build_file = self._find_build_file(project_dir)
        if build_file is None:
            return GradleModernizationResult(modified=False)

        content = build_file.read_text(encoding="utf-8", errors="ignore")
        original_content = content
        logs: list[str] = []
        upgrades: list[dict[str, str]] = []

        target_java = str(target_java_version or "17").strip()
        try:
            target_major = int(target_java)
        except ValueError:
            target_major = 17

        spring_boot_before: str | None = None
        spring_boot_after: str | None = None

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
                logs.append(f"Upgraded Gradle Spring Boot plugin version from {spring_boot_before} to {target_boot_version} for Java {target_java} compatibility.")
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
            logs.append(f"Updated sourceCompatibility to {target_java}.")

        if "targetCompatibility" in content:
            content = re.sub(r"targetCompatibility\s*=\s*['\"]?\d+(?:\.\d+)?['\"]?", f"targetCompatibility = '{target_java}'", content)
            content = re.sub(r"targetCompatibility\s*=\s*JavaVersion\.VERSION_\d+_\d+", f"targetCompatibility = JavaVersion.VERSION_{target_java}", content)
            logs.append(f"Updated targetCompatibility to {target_java}.")

        if "JavaLanguageVersion.of(" in content:
            content = re.sub(r"JavaLanguageVersion\.of\(\d+\)", f"JavaLanguageVersion.of({target_java})", content)
            logs.append(f"Updated Gradle JavaLanguageVersion toolchain to {target_java}.")

        # 3. Modernize Javax to Jakarta Dependencies in Gradle
        for legacy_coord, (new_group, new_art, new_ver) in _JAVAX_TO_JAKARTA_GRADLE.items():
            artifact_part = legacy_coord.split(":")[1] if ":" in legacy_coord else legacy_coord
            if legacy_coord in content or artifact_part in content:
                content = re.sub(
                    rf"['\"]{re.escape(legacy_coord)}(?::[^'\"]+)?['\"]",
                    f"'{new_group}:{new_art}:{new_ver}'",
                    content,
                )
                logs.append(f"Migrated Gradle dependency {legacy_coord} to {new_group}:{new_art}:{new_ver}.")
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
            changed_files=[build_file.name] if is_modified else [],
            log_lines=logs,
            dependency_upgrades=upgrades,
            spring_boot_before=spring_boot_before,
            spring_boot_after=spring_boot_after,
        )

    @staticmethod
    def _find_build_file(project_dir: Path) -> Path | None:
        for name in ("build.gradle", "build.gradle.kts"):
            candidate = project_dir / name
            if candidate.is_file():
                return candidate
        return None
