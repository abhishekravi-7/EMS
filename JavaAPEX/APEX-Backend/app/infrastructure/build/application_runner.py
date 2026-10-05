"""Dynamic, repository-agnostic application runners for functional testing.

Supports:
- Single-module and multi-module Spring Boot applications (executable fat-JARs)
- Maven Spring Boot direct execution (mvnw spring-boot:run)
- Gradle Spring Boot direct execution (gradlew bootRun)
- Modernized Frontends (React / Angular / Vue / Vite / Static HTML)
- Composite full-stack applications (Backend + Frontend concurrent execution)
- Dynamic port management with collision avoidance
"""

from __future__ import annotations

import logging
import os
import re
import socket
import subprocess  # nosec B404
import sys
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.infrastructure.build.app_launcher import MigratedAppLauncher, analyze_startup_failure
from app.infrastructure.build.artifact_detector import DetectedArtifactResult
from app.infrastructure.build.migrated_frontend_server import MigratedFrontendServer
from app.infrastructure.build.repository_analyzer import ApplicationType, BuildToolType, RepositoryAnalysisResult

logger = logging.getLogger(__name__)


def find_free_port() -> int:
    """Dynamically acquires an available, unallocated TCP port from the OS kernel."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class PortManager:
    """Manages port allocation and resolves port collisions dynamically."""

    @staticmethod
    def is_port_in_use(port: int) -> bool:
        if port <= 0 or port > 65535:
            return True
        pids = MigratedAppLauncher.get_port_listening_pids(port)
        if pids:
            return True
        # Direct socket probe check
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.bind(("127.0.0.1", port))
                return False
            except OSError:
                return True

    @classmethod
    def resolve_port(cls, preferred_port: int | None = None, label: str = "application") -> int:
        """Returns preferred_port if available, otherwise dynamically allocates an unused port."""
        if preferred_port and preferred_port > 0:
            if not cls.is_port_in_use(preferred_port):
                return preferred_port
            logger.info("Preferred %s port %d is already in use; allocating dynamic port...", label, preferred_port)

        free_port = find_free_port()
        logger.info("Allocated dynamic %s port: %d", label, free_port)
        return free_port


@dataclass
class ApplicationLaunchResult:
    success: bool
    backend_pid: int | None = None
    frontend_pid: int | None = None
    backend_port: int | None = None
    frontend_port: int | None = None
    backend_url: str | None = None
    frontend_url: str | None = None
    runtime_url: str | None = None
    startup_command: str | None = None
    startup_log: list[str] = field(default_factory=list)
    error: str | None = None
    failure_category: str | None = None  # "APPLICATION_STARTUP", "PORT_CONFLICT", "BUILD_FAILURE", etc.
    failure_reason: str | None = None


class BaseApplicationRunner(ABC):
    """Abstract base runner for executing application instances."""

    def __init__(self, job_id: str, repo_dir: Path):
        self.job_id = job_id
        self.repo_dir = Path(repo_dir)
        self._launched_pids: list[int] = []

    @abstractmethod
    def start(
        self,
        analysis: RepositoryAnalysisResult,
        artifact: DetectedArtifactResult,
        preferred_port: int | None = None,
        log_fn: Callable[[str, str], None] | None = None,
        startup_timeout: float = 30.0,
    ) -> ApplicationLaunchResult:
        """Launches the application and returns details."""

    def stop(self, log_fn: Callable[[str, str], None] | None = None) -> None:
        """Gracefully shuts down all processes spawned by this runner."""
        for pid in self._launched_pids:
            try:
                MigratedAppLauncher.stop(pid)
                if log_fn:
                    log_fn(f"[APP] Stopped application process (PID {pid}).", "INFO")
            except Exception as e:
                logger.warning("Failed to stop process PID %d: %s", pid, e)
        self._launched_pids.clear()


class SpringBootJarRunner(BaseApplicationRunner):
    """Launches Spring Boot executable fat-JAR archives."""

    def start(
        self,
        analysis: RepositoryAnalysisResult,
        artifact: DetectedArtifactResult,
        preferred_port: int | None = None,
        log_fn: Callable[[str, str], None] | None = None,
        startup_timeout: float = 30.0,
    ) -> ApplicationLaunchResult:
        jar_path = artifact.jar_path
        if not jar_path or not jar_path.is_file():
            return ApplicationLaunchResult(
                success=False,
                error="No runnable JAR artifact specified for SpringBootJarRunner.",
                failure_category="APPLICATION_STARTUP",
                failure_reason="No runnable JAR artifact found.",
            )

        port = PortManager.resolve_port(preferred_port or analysis.configured_port or 8080, label="backend")
        java_exe = MigratedAppLauncher._resolve_java()
        if not java_exe:
            return ApplicationLaunchResult(
                success=False,
                error="'java' executable not found on PATH or JAVA_HOME.",
                failure_category="APPLICATION_STARTUP",
                failure_reason="Java runtime environment missing.",
            )

        cmd = [
            java_exe,
            f"-Dserver.port={port}",
            "-jar",
            str(jar_path.resolve()),
            f"--server.port={port}",
        ]
        env = {
            **os.environ,
            "SERVER_PORT": str(port),
            "PORT": str(port),
        }

        cmd_str = " ".join(cmd)
        if log_fn:
            log_fn(f"[APP] Starting Spring Boot application (artifact={jar_path.name}, port={port})...", "INFO")

        startup_log: list[str] = []
        log_lock = threading.Lock()

        try:
            # Working dir: if jar is inside a submodule, cwd in submodule dir or root
            cwd = jar_path.parent.parent if (jar_path.parent.name == "target" and jar_path.parent.parent != self.repo_dir) else self.repo_dir
            proc = subprocess.Popen(  # nosec B603
                cmd,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1,
                start_new_session=(os.name != "nt"),
            )
        except Exception as e:
            return ApplicationLaunchResult(
                success=False,
                startup_command=cmd_str,
                error=f"Failed to spawn Spring Boot process: {e}",
                failure_category="APPLICATION_STARTUP",
                failure_reason=str(e),
            )

        pid = proc.pid
        self._launched_pids.append(pid)

        def drain_output() -> None:
            try:
                if proc.stdout:
                    for line in iter(proc.stdout.readline, ""):
                        if not line:
                            break
                        line_str = line.rstrip()
                        with log_lock:
                            startup_log.append(line_str)
                            if len(startup_log) > 2000:
                                startup_log.pop(0)
            except Exception:
                pass

        threading.Thread(target=drain_output, daemon=True).start()

        MigratedAppLauncher._running_processes[pid] = {
            "proc": proc,
            "logs": startup_log,
            "port": port,
            "artifact": str(jar_path),
            "lock": log_lock,
        }

        deadline = time.time() + startup_timeout
        early_exit = False
        exit_code: int | None = None

        while time.time() < deadline:
            exit_code = proc.poll()
            if exit_code is not None:
                early_exit = True
                break

            with log_lock:
                recent_logs = list(startup_log)

            from app.infrastructure.build.app_launcher import _STARTUP_INDICATORS
            for line in recent_logs:
                lower = line.lower()
                if any(ind in lower for ind in _STARTUP_INDICATORS):
                    url = f"http://localhost:{port}"
                    return ApplicationLaunchResult(
                        success=True,
                        backend_pid=pid,
                        backend_port=port,
                        backend_url=url,
                        runtime_url=url,
                        startup_command=cmd_str,
                        startup_log=startup_log,
                    )

            # Check if port already started listening
            if MigratedAppLauncher.is_port_owned_by_process(port, pid):
                url = f"http://localhost:{port}"
                return ApplicationLaunchResult(
                    success=True,
                    backend_pid=pid,
                    backend_port=port,
                    backend_url=url,
                    runtime_url=url,
                    startup_command=cmd_str,
                    startup_log=startup_log,
                )

            time.sleep(0.5)

        if early_exit:
            reason, category = analyze_startup_failure(startup_log, exit_code)
            return ApplicationLaunchResult(
                success=False,
                backend_pid=pid,
                backend_port=port,
                startup_command=cmd_str,
                startup_log=startup_log,
                error=f"Application process exited with code {exit_code}: {reason}",
                failure_category="APPLICATION_STARTUP",
                failure_reason=reason,
            )

        # Still running but timeout exceeded
        if proc.poll() is None:
            url = f"http://localhost:{port}"
            return ApplicationLaunchResult(
                success=True,
                backend_pid=pid,
                backend_port=port,
                backend_url=url,
                runtime_url=url,
                startup_command=cmd_str,
                startup_log=startup_log,
            )

        return ApplicationLaunchResult(
            success=False,
            startup_command=cmd_str,
            startup_log=startup_log,
            error="Startup timed out without becoming ready.",
            failure_category="APPLICATION_STARTUP",
            failure_reason="Timeout waiting for application to initialize.",
        )


class MavenSpringBootRunner(BaseApplicationRunner):
    """Launches Spring Boot via `./mvnw spring-boot:run` or `mvn spring-boot:run`."""

    def start(
        self,
        analysis: RepositoryAnalysisResult,
        artifact: DetectedArtifactResult,
        preferred_port: int | None = None,
        log_fn: Callable[[str, str], None] | None = None,
        startup_timeout: float = 45.0,
    ) -> ApplicationLaunchResult:
        port = PortManager.resolve_port(preferred_port or analysis.configured_port or 8080, label="backend")
        mvn_cmd = analysis.wrapper_script or "mvn"
        if not Path(mvn_cmd).is_absolute():
            candidate = self.repo_dir / mvn_cmd
            if candidate.is_file():
                mvn_cmd = str(candidate)

        cmd = [mvn_cmd]
        submodule = artifact.target_module.name if artifact.target_module else None
        if submodule:
            cmd.extend(["-pl", submodule])
        cmd.extend([
            "spring-boot:run",
            f"-Dspring-boot.run.arguments=--server.port={port}",
        ])

        cmd_str = " ".join(cmd)
        if log_fn:
            log_fn(f"[APP] Starting Maven Spring Boot application via `{cmd_str}`...", "INFO")

        startup_log: list[str] = []
        log_lock = threading.Lock()

        try:
            proc = subprocess.Popen(  # nosec B603
                cmd,
                cwd=str(self.repo_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=(os.name != "nt"),
            )
        except Exception as e:
            return ApplicationLaunchResult(
                success=False,
                startup_command=cmd_str,
                error=f"Failed to start Maven Spring Boot: {e}",
                failure_category="APPLICATION_STARTUP",
                failure_reason=str(e),
            )

        pid = proc.pid
        self._launched_pids.append(pid)

        def drain_output() -> None:
            try:
                if proc.stdout:
                    for line in iter(proc.stdout.readline, ""):
                        if not line:
                            break
                        line_str = line.rstrip()
                        with log_lock:
                            startup_log.append(line_str)
                            if len(startup_log) > 2000:
                                startup_log.pop(0)
            except Exception:
                pass

        threading.Thread(target=drain_output, daemon=True).start()

        MigratedAppLauncher._running_processes[pid] = {
            "proc": proc,
            "logs": startup_log,
            "port": port,
            "artifact": "mvn spring-boot:run",
            "lock": log_lock,
        }

        deadline = time.time() + startup_timeout
        while time.time() < deadline:
            exit_code = proc.poll()
            if exit_code is not None:
                reason, _ = analyze_startup_failure(startup_log, exit_code)
                return ApplicationLaunchResult(
                    success=False,
                    backend_pid=pid,
                    backend_port=port,
                    startup_command=cmd_str,
                    startup_log=startup_log,
                    error=f"Maven process exited with code {exit_code}: {reason}",
                    failure_category="APPLICATION_STARTUP",
                    failure_reason=reason,
                )

            # Check port listening
            if MigratedAppLauncher.is_port_owned_by_process(port, pid):
                url = f"http://localhost:{port}"
                return ApplicationLaunchResult(
                    success=True,
                    backend_pid=pid,
                    backend_port=port,
                    backend_url=url,
                    runtime_url=url,
                    startup_command=cmd_str,
                    startup_log=startup_log,
                )
            time.sleep(1.0)

        # Fallback check
        if proc.poll() is None:
            url = f"http://localhost:{port}"
            return ApplicationLaunchResult(
                success=True,
                backend_pid=pid,
                backend_port=port,
                backend_url=url,
                runtime_url=url,
                startup_command=cmd_str,
                startup_log=startup_log,
            )

        return ApplicationLaunchResult(
            success=False,
            startup_command=cmd_str,
            startup_log=startup_log,
            error="Maven Spring Boot startup timed out.",
            failure_category="APPLICATION_STARTUP",
            failure_reason="Timeout waiting for application to initialize.",
        )


class GradleSpringBootRunner(BaseApplicationRunner):
    """Launches Spring Boot via `./gradlew bootRun` or `gradle bootRun`."""

    def start(
        self,
        analysis: RepositoryAnalysisResult,
        artifact: DetectedArtifactResult,
        preferred_port: int | None = None,
        log_fn: Callable[[str, str], None] | None = None,
        startup_timeout: float = 45.0,
    ) -> ApplicationLaunchResult:
        port = PortManager.resolve_port(preferred_port or analysis.configured_port or 8080, label="backend")
        gradle_cmd = analysis.wrapper_script or "gradle"
        if not Path(gradle_cmd).is_absolute():
            candidate = self.repo_dir / gradle_cmd
            if candidate.is_file():
                gradle_cmd = str(candidate)

        submodule = artifact.target_module.name if artifact.target_module else None
        task_name = f":{submodule}:bootRun" if submodule else "bootRun"
        cmd = [
            gradle_cmd,
            task_name,
            f"--args=--server.port={port}",
        ]

        cmd_str = " ".join(cmd)
        if log_fn:
            log_fn(f"[APP] Starting Gradle Spring Boot application via `{cmd_str}`...", "INFO")

        startup_log: list[str] = []
        log_lock = threading.Lock()

        try:
            proc = subprocess.Popen(  # nosec B603
                cmd,
                cwd=str(self.repo_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=(os.name != "nt"),
            )
        except Exception as e:
            return ApplicationLaunchResult(
                success=False,
                startup_command=cmd_str,
                error=f"Failed to start Gradle Spring Boot: {e}",
                failure_category="APPLICATION_STARTUP",
                failure_reason=str(e),
            )

        pid = proc.pid
        self._launched_pids.append(pid)

        def drain_output() -> None:
            try:
                if proc.stdout:
                    for line in iter(proc.stdout.readline, ""):
                        if not line:
                            break
                        line_str = line.rstrip()
                        with log_lock:
                            startup_log.append(line_str)
                            if len(startup_log) > 2000:
                                startup_log.pop(0)
            except Exception:
                pass

        threading.Thread(target=drain_output, daemon=True).start()

        MigratedAppLauncher._running_processes[pid] = {
            "proc": proc,
            "logs": startup_log,
            "port": port,
            "artifact": "gradle bootRun",
            "lock": log_lock,
        }

        deadline = time.time() + startup_timeout
        while time.time() < deadline:
            exit_code = proc.poll()
            if exit_code is not None:
                reason, _ = analyze_startup_failure(startup_log, exit_code)
                return ApplicationLaunchResult(
                    success=False,
                    backend_pid=pid,
                    backend_port=port,
                    startup_command=cmd_str,
                    startup_log=startup_log,
                    error=f"Gradle process exited with code {exit_code}: {reason}",
                    failure_category="APPLICATION_STARTUP",
                    failure_reason=reason,
                )

            if MigratedAppLauncher.is_port_owned_by_process(port, pid):
                url = f"http://localhost:{port}"
                return ApplicationLaunchResult(
                    success=True,
                    backend_pid=pid,
                    backend_port=port,
                    backend_url=url,
                    runtime_url=url,
                    startup_command=cmd_str,
                    startup_log=startup_log,
                )
            time.sleep(1.0)

        if proc.poll() is None:
            url = f"http://localhost:{port}"
            return ApplicationLaunchResult(
                success=True,
                backend_pid=pid,
                backend_port=port,
                backend_url=url,
                runtime_url=url,
                startup_command=cmd_str,
                startup_log=startup_log,
            )

        return ApplicationLaunchResult(
            success=False,
            startup_command=cmd_str,
            startup_log=startup_log,
            error="Gradle Spring Boot startup timed out.",
            failure_category="APPLICATION_STARTUP",
            failure_reason="Timeout waiting for application to initialize.",
        )


class FrontendRunner(BaseApplicationRunner):
    """Serves modernized frontend React/Angular/Vue components via static server or npm dev."""

    def __init__(self, job_id: str, repo_dir: Path):
        super().__init__(job_id, repo_dir)
        self._frontend_server: MigratedFrontendServer | None = None

    def start(
        self,
        analysis: RepositoryAnalysisResult,
        artifact: DetectedArtifactResult,
        preferred_port: int | None = None,
        log_fn: Callable[[str, str], None] | None = None,
        startup_timeout: float = 15.0,
    ) -> ApplicationLaunchResult:
        if log_fn:
            log_fn("[APP] Preparing modernized frontend server...", "INFO")

        server = MigratedFrontendServer(self.job_id, self.repo_dir)
        try:
            port, pid, runtime_url = server.launch()
            self._frontend_server = server
            self._launched_pids.append(pid)
            if log_fn:
                log_fn(f"[APP] Modernized frontend active at {runtime_url} (PID {pid})", "INFO")
            return ApplicationLaunchResult(
                success=True,
                frontend_pid=pid,
                frontend_port=port,
                frontend_url=runtime_url,
                runtime_url=runtime_url,
                startup_command="python -m http.server",
            )
        except Exception as e:
            return ApplicationLaunchResult(
                success=False,
                error=f"Frontend startup failed: {e}",
                failure_category="APPLICATION_STARTUP",
                failure_reason=str(e),
            )

    def stop(self, log_fn: Callable[[str, str], None] | None = None) -> None:
        if self._frontend_server:
            try:
                self._frontend_server.stop()
            except Exception:
                pass
        super().stop(log_fn)


class CompositeAppRunner(BaseApplicationRunner):
    """Coordinates both Backend (Spring Boot / Java) and Frontend (React/Angular) concurrently."""

    def __init__(
        self,
        job_id: str,
        repo_dir: Path,
        backend_runner: BaseApplicationRunner,
        frontend_runner: BaseApplicationRunner,
    ):
        super().__init__(job_id, repo_dir)
        self.backend_runner = backend_runner
        self.frontend_runner = frontend_runner

    def start(
        self,
        analysis: RepositoryAnalysisResult,
        artifact: DetectedArtifactResult,
        preferred_port: int | None = None,
        log_fn: Callable[[str, str], None] | None = None,
        startup_timeout: float = 35.0,
    ) -> ApplicationLaunchResult:
        if log_fn:
            log_fn("[APP] Starting Full-Stack Application: Backend + Frontend...", "INFO")

        b_res = self.backend_runner.start(
            analysis, artifact, preferred_port=preferred_port, log_fn=log_fn, startup_timeout=startup_timeout
        )
        if not b_res.success:
            return b_res

        f_res = self.frontend_runner.start(
            analysis, artifact, log_fn=log_fn, startup_timeout=15.0
        )

        # Merge results
        return ApplicationLaunchResult(
            success=b_res.success and f_res.success,
            backend_pid=b_res.backend_pid,
            frontend_pid=f_res.frontend_pid,
            backend_port=b_res.backend_port,
            frontend_port=f_res.frontend_port,
            backend_url=b_res.backend_url,
            frontend_url=f_res.frontend_url,
            runtime_url=f_res.runtime_url or b_res.runtime_url,
            startup_command=f"Backend: {b_res.startup_command} | Frontend: {f_res.startup_command}",
            startup_log=b_res.startup_log + f_res.startup_log,
            error=f_res.error if not f_res.success else None,
            failure_category=f_res.failure_category if not f_res.success else None,
            failure_reason=f_res.failure_reason if not f_res.success else None,
        )

    def stop(self, log_fn: Callable[[str, str], None] | None = None) -> None:
        self.frontend_runner.stop(log_fn)
        self.backend_runner.stop(log_fn)
        super().stop(log_fn)


class ApplicationRunnerFactory:
    """Instantiates the appropriate application runner based on repository analysis and artifacts."""

    @classmethod
    def create_runner(
        cls,
        job_id: str,
        repo_dir: Path,
        analysis: RepositoryAnalysisResult,
        artifact: DetectedArtifactResult,
    ) -> BaseApplicationRunner:
        has_frontend = (
            analysis.archetype in (ApplicationType.FULL_STACK, ApplicationType.FRONTEND_ONLY)
            or (repo_dir / "frontend").exists()
        )

        # Select backend runner
        backend_runner: BaseApplicationRunner
        if artifact.run_strategy == "FAT_JAR" and artifact.jar_path:
            backend_runner = SpringBootJarRunner(job_id, repo_dir)
        elif artifact.run_strategy == "MAVEN_PLUGIN":
            backend_runner = MavenSpringBootRunner(job_id, repo_dir)
        elif artifact.run_strategy == "GRADLE_PLUGIN":
            backend_runner = GradleSpringBootRunner(job_id, repo_dir)
        elif analysis.build_tool == BuildToolType.GRADLE:
            backend_runner = GradleSpringBootRunner(job_id, repo_dir)
        else:
            backend_runner = SpringBootJarRunner(job_id, repo_dir)

        if analysis.archetype == ApplicationType.FRONTEND_ONLY:
            return FrontendRunner(job_id, repo_dir)

        if has_frontend:
            return CompositeAppRunner(
                job_id=job_id,
                repo_dir=repo_dir,
                backend_runner=backend_runner,
                frontend_runner=FrontendRunner(job_id, repo_dir),
            )

        return backend_runner

