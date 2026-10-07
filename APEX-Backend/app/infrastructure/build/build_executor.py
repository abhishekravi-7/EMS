"""Build execution engine for automated application preparation.

Dynamically invokes wrapper (mvnw.cmd, ./mvnw, gradlew.bat, ./gradlew) or system tool.
Captures command, exit code, stdout, stderr, build duration, and generated artifacts.
"""

from __future__ import annotations

import logging
import os
import subprocess  # nosec B404
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.infrastructure.build.repository_analyzer import BuildToolType, RepositoryAnalysisResult
from app.shared.command_runner import resolve_executable

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    success: bool
    command: list[str]
    command_str: str
    exit_code: int
    duration_s: float
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    artifacts: list[Path] = field(default_factory=list)


class BuildExecutor:
    """Executes pre-test builds for Java (Maven/Gradle) and Node repositories."""

    def __init__(self, repo_dir: Path | str) -> None:
        self.repo_dir = Path(repo_dir).resolve()

    def build(
        self,
        analysis: RepositoryAnalysisResult,
        timeout_s: float = 300.0,
        log_fn: Callable[[str, str], None] | None = None,
    ) -> BuildResult:
        """Builds the repository using the appropriate build tool and flags."""
        is_windows = os.name == "nt"

        def _log(msg: str, level: str = "INFO"):
            if log_fn:
                log_fn(msg, level)
            logger.info("[BUILD] %s", msg)

        # Skip build if repository is already packaged or has no build file
        if analysis.build_tool == BuildToolType.NONE:
            _log("No build tool detected; skipping build step.")
            return BuildResult(
                success=True,
                command=[],
                command_str="NONE",
                exit_code=0,
                duration_s=0.0,
                stdout="No build tool required.",
            )

        # Determine working directory for build
        build_dir = self.repo_dir
        if analysis.primary_backend_module and analysis.primary_backend_module.path.exists():
            build_dir = analysis.primary_backend_module.path

        # 1. Resolve Command
        cmd: list[str] = []
        if analysis.build_tool == BuildToolType.MAVEN:
            wrapper = build_dir / ("mvnw.cmd" if is_windows else "mvnw")
            if not wrapper.exists():
                wrapper = self.repo_dir / ("mvnw.cmd" if is_windows else "mvnw")
            if wrapper.exists():
                mvn_cmd = str(wrapper)
            else:
                mvn_cmd = resolve_executable("mvn") or ("mvn.cmd" if is_windows else "mvn")
            cmd = [mvn_cmd, "clean", "package", "-DskipTests"]
        elif analysis.build_tool == BuildToolType.GRADLE:
            wrapper = build_dir / ("gradlew.bat" if is_windows else "gradlew")
            if not wrapper.exists():
                wrapper = self.repo_dir / ("gradlew.bat" if is_windows else "gradlew")
            if wrapper.exists():
                gradle_cmd = str(wrapper)
            else:
                gradle_cmd = resolve_executable("gradle") or ("gradle.bat" if is_windows else "gradle")
            cmd = [gradle_cmd, "clean", "build", "-x", "test"]
        elif analysis.build_tool == BuildToolType.NPM:
            npm_cmd = resolve_executable("npm") or ("npm.cmd" if is_windows else "npm")
            cmd = [npm_cmd, "install"]

        command_str = " ".join(cmd)
        _log(f"Running build command in '{build_dir.name}': {command_str}")

        start_t = time.time()
        env = dict(os.environ)

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(build_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
                shell=is_windows,
            )
            duration = round(time.time() - start_t, 2)
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            success = (proc.returncode == 0)

            if success:
                _log(f"Build completed successfully in {duration}s (exit code 0)")
            else:
                _log(f"Build failed with exit code {proc.returncode} in {duration}s", "ERROR")
                err_snippet = (stderr.strip() or stdout.strip())[-1000:]
                _log(f"Build error output snippet:\n{err_snippet}", "ERROR")

            # Collect artifacts
            artifacts = self._collect_artifacts()

            return BuildResult(
                success=success,
                command=cmd,
                command_str=command_str,
                exit_code=proc.returncode,
                duration_s=duration,
                stdout=stdout,
                stderr=stderr,
                error=None if success else f"Build failed with exit code {proc.returncode}: {stderr[-300:] or stdout[-300:]}",
                artifacts=artifacts,
            )

        except subprocess.TimeoutExpired:
            duration = round(time.time() - start_t, 2)
            err_msg = f"Build timed out after {timeout_s}s"
            _log(err_msg, "ERROR")
            return BuildResult(
                success=False,
                command=cmd,
                command_str=command_str,
                exit_code=-1,
                duration_s=duration,
                error=err_msg,
            )
        except Exception as exc:
            duration = round(time.time() - start_t, 2)
            err_msg = f"Build execution error: {exc}"
            _log(err_msg, "ERROR")
            return BuildResult(
                success=False,
                command=cmd,
                command_str=command_str,
                exit_code=-1,
                duration_s=duration,
                error=err_msg,
            )

    def _collect_artifacts(self) -> list[Path]:
        """Collects generated JAR and WAR artifacts across root and all subdirectories."""
        artifacts: list[Path] = []
        exclude = ("-sources", "-javadoc", "original-", "-plain")
        for ext in ("*.jar", "*.war"):
            for p in self.repo_dir.rglob(ext):
                if p.is_file() and not any(ex in p.name.lower() for ex in exclude):
                    # Ensure it's in a target/ or build/libs/ directory
                    if "target" in p.parts or "build" in p.parts:
                        artifacts.append(p)
        return artifacts
