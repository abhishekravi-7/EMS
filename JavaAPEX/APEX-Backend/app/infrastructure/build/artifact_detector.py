"""Dynamic runnable artifact detection across root and submodules.

Discovers:
- Spring Boot Fat-JARs in target/ or build/libs/ across all modules
- WAR archives for servlet containers
- Detects Main-Class / Start-Class in META-INF/MANIFEST.MF
- Evaluates alternative startup mechanisms (e.g. spring-boot:run, bootRun, npm) when no fat-JAR exists
"""

from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.infrastructure.build.repository_analyzer import JavaModuleInfo, RepositoryAnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class DetectedArtifactResult:
    has_runnable_jar: bool
    jar_path: Path | None = None
    main_class: str | None = None
    target_module: JavaModuleInfo | None = None
    supports_maven_run: bool = False
    supports_gradle_run: bool = False
    supports_node_run: bool = False
    run_strategy: str = "NONE"  # "FAT_JAR", "MAVEN_PLUGIN", "GRADLE_PLUGIN", "NODE_DEV", "STATIC_SERVER", "UNSUPPORTED"
    failure_reason: str | None = None


class ArtifactDetector:
    """Scans repository outputs to locate runnable artifacts and evaluate execution strategies."""

    EXCLUDE_PATTERNS = ("-sources", "-javadoc", "original-", "-plain", "-tests")

    def __init__(self, repo_dir: Path | str) -> None:
        self.repo_dir = Path(repo_dir).resolve()

    def detect(self, analysis: RepositoryAnalysisResult) -> DetectedArtifactResult:
        """Finds runnable JAR artifacts or detects appropriate execution strategy."""
        # 1. Search for Fat-JARs across all modules and subdirectories
        all_jars: list[tuple[Path, int]] = []  # (path, size)

        # Priority 1: Check primary backend module if identified
        dirs_to_search: list[Path] = []
        if analysis.primary_backend_module:
            dirs_to_search.append(analysis.primary_backend_module.path)
        for m in analysis.backend_modules:
            if m.path not in dirs_to_search:
                dirs_to_search.append(m.path)
        if self.repo_dir not in dirs_to_search:
            dirs_to_search.append(self.repo_dir)

        for d in dirs_to_search:
            for sub in ["target", "build/libs", "build/output"]:
                chk = d / sub
                if chk.is_dir():
                    for jar in chk.glob("*.jar"):
                        if jar.is_file() and not any(ex in jar.name.lower() for ex in self.EXCLUDE_PATTERNS):
                            all_jars.append((jar, jar.stat().st_size))

        # Also search entire repo for any JAR in target/ or build/libs/ as fallback
        if not all_jars:
            for p in self.repo_dir.rglob("*.jar"):
                if p.is_file() and ("target" in p.parts or "build" in p.parts):
                    if not any(ex in p.name.lower() for ex in self.EXCLUDE_PATTERNS):
                        all_jars.append((p, p.stat().st_size))

        # 2. Check detected JARs for Spring Boot / Main-Class entry points
        valid_fat_jars: list[tuple[Path, str | None, int]] = []  # (path, main_class, size)
        for jar_path, size in all_jars:
            main_class = self._inspect_manifest(jar_path)
            # Fat-JAR heuristic: Has Main-Class or Start-Class, or size > 1MB
            if main_class or size > 1024 * 1024:
                valid_fat_jars.append((jar_path, main_class, size))

        if valid_fat_jars:
            # Pick the largest fat-JAR
            best_jar, main_cls, _ = max(valid_fat_jars, key=lambda x: x[2])
            # Determine which module owns this JAR
            owning_mod = None
            for m in analysis.backend_modules:
                if m.path in best_jar.parents:
                    owning_mod = m
                    break
            owning_mod = owning_mod or analysis.primary_backend_module

            return DetectedArtifactResult(
                has_runnable_jar=True,
                jar_path=best_jar,
                main_class=main_cls,
                target_module=owning_mod,
                run_strategy="FAT_JAR",
            )

        # 3. If no fat-JAR exists, evaluate build-tool execution plugins
        target_mod = analysis.primary_backend_module or (analysis.backend_modules[0] if analysis.backend_modules else None)
        if (target_mod and target_mod.has_pom) or analysis.build_tool == BuildToolType.MAVEN:
            return DetectedArtifactResult(
                has_runnable_jar=False,
                target_module=target_mod,
                supports_maven_run=True,
                run_strategy="MAVEN_PLUGIN",
            )
        elif (target_mod and target_mod.has_gradle) or analysis.build_tool == BuildToolType.GRADLE:
            return DetectedArtifactResult(
                has_runnable_jar=False,
                target_module=target_mod,
                supports_gradle_run=True,
                run_strategy="GRADLE_PLUGIN",
            )
        elif analysis.primary_frontend_module:
            return DetectedArtifactResult(
                has_runnable_jar=False,
                supports_node_run=True,
                run_strategy="NODE_DEV",
            )
        elif (self.repo_dir / "index.html").exists():
            return DetectedArtifactResult(
                has_runnable_jar=False,
                run_strategy="STATIC_SERVER",
            )

        # 4. No runnable artifact or strategy could be determined
        return DetectedArtifactResult(
            has_runnable_jar=False,
            run_strategy="UNSUPPORTED",
            failure_reason=(
                f"No runnable JAR or execution strategy found in '{self.repo_dir}'. "
                "Ensure build packaging (clean package / clean build) completes successfully."
            ),
        )

    def _inspect_manifest(self, jar_path: Path) -> str | None:
        """Inspects META-INF/MANIFEST.MF for Main-Class or Start-Class."""
        try:
            with zipfile.ZipFile(jar_path, "r") as z:
                if "META-INF/MANIFEST.MF" in z.namelist():
                    content = z.read("META-INF/MANIFEST.MF").decode("utf-8", errors="ignore")
                    m = re.search(r"(?:Main-Class|Start-Class):\s*([^\r\n]+)", content)
                    if m:
                        return m.group(1).strip()
        except Exception:
            pass
        return None
