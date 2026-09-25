"""Launches Java applications (Source and Migrated) in isolated subprocesses.

Supports Spring Boot executable JARs, Maven (target/*.jar) and Gradle (build/libs/*.jar).
Does NOT hardcode JAR names, ports, or application names.
Detects unsupported runtimes (e.g. standalone WARs without embedded container).
Captures stdout/stderr continuously in a non-blocking background thread.
Provides deep startup failure diagnostics (DB issues, Port conflicts, Missing Beans).
"""

from __future__ import annotations

import logging
import os
import re
import subprocess  # nosec B404
import threading
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Startup log indicators that suggest the app has started successfully
_STARTUP_INDICATORS = [
    "started",
    "started on port",
    "listening on",
    "server started",
    "application started",
    "tomcat started",
    "netty started",
    "undertow started",
    "started successfully",
    "ready",
    "application is ready",
    "main: started",
]

_STARTUP_FAILURE_INDICATORS = [
    "application run failed",
    "unable to start",
    "failed to start",
    "error starting",
    "caused by:",
    "exception in thread",
    "port already in use",
    "address already in use",
    "web server failed to start",
]


@dataclass
class AppLaunchResult:
    success: bool
    pid: int | None = None
    artifact_path: str | None = None
    port: int = 8080
    exit_code: int | None = None
    startup_log: list[str] = field(default_factory=list)
    error: str | None = None
    failure_reason: str | None = None
    failure_category: str | None = None  # "DATABASE", "PORT_CONFLICT", "BEAN_CREATION", "UNSUPPORTED_RUNTIME", "FATAL_ERROR"
    startup_detected: bool = False
    runtime_unsupported: bool = False


def analyze_startup_failure(log_lines: list[str], exit_code: int | None = None) -> tuple[str, str]:
    """Analyzes startup log lines to diagnose the exact root cause of application startup failure.

    Returns:
        (failure_reason, failure_category)
    """
    full_text = "\n".join(log_lines)
    lower_text = full_text.lower()

    # 1. Port Conflict
    if "already in use" in lower_text or "bindexception" in lower_text or "port was already in use" in lower_text:
        port_match = re.search(r"port\s+(\d+)\s+(?:was\s+)?already in use", full_text, re.IGNORECASE)
        port_str = f"Port {port_match.group(1)}" if port_match else "Configured port"
        return (
            f"Port conflict: {port_str} is already occupied by another active process.",
            "PORT_CONFLICT",
        )

    # 2. Database Connection Failure
    db_patterns = [
        r"cannot\s+(?:create\s+poolable\s+connection|get\s+connection)",
        r"communications\s+link\s+failure",
        r"connection\s+refused",
        r"could\s+not\s+(?:obtain|open)\s+connection",
        r"unknown\s+database",
        r"access\s+denied\s+for\s+user",
        r"authentication\s+failed\s+for\s+user",
        r"datasource\s+initialization\s+failed",
        r"hikari.*exception",
        r"failed\s+to\s+initialize\s+datasource",
    ]
    for pat in db_patterns:
        if re.search(pat, full_text, re.IGNORECASE):
            return (
                "Database connection failure: Application failed to establish database connectivity (MySQL/PostgreSQL/Oracle/SQLServer unreachable or credentials invalid).",
                "DATABASE",
            )

    # 3. Missing Main-Class Manifest
    if "no main manifest attribute" in lower_text:
        return (
            "Executable entry point missing: Built JAR archive is missing a Main-Class or Start-Class attribute in META-INF/MANIFEST.MF.",
            "UNSUPPORTED_RUNTIME",
        )

    # 4. Spring Bean / Context Creation Failure
    if "beancreationexception" in lower_text or "nosuchbeandefinitionexception" in lower_text or "application failed to start" in lower_text:
        # Extract Caused by: message if present
        caused_by_matches = re.findall(r"Caused by:\s+([^\n]+)", full_text)
        if caused_by_matches:
            reason = f"Spring ApplicationContext initialization failed: {caused_by_matches[-1].strip()}"
            return (reason, "BEAN_CREATION")
        return ("Spring Boot application failed to start due to a BeanCreationException or missing dependency bean.", "BEAN_CREATION")

    # 5. ClassNotFoundException / NoClassDefFoundError
    if "classnotfoundexception" in lower_text or "noclassdeffounderror" in lower_text:
        class_match = re.search(r"(?:ClassNotFoundException|NoClassDefFoundError):\s+([^\n]+)", full_text)
        detail = class_match.group(1).strip() if class_match else "missing required class"
        return (f"Missing runtime class dependency: {detail}", "FATAL_ERROR")

    # 6. Fallback: extract last error lines
    error_lines = [l for l in log_lines if any(k in l.lower() for k in ["error", "fatal", "exception", "failed"])]
    if error_lines:
        return (f"Application process exited with error: {error_lines[-1][:200]}", "FATAL_ERROR")

    exit_str = f"with exit code {exit_code}" if exit_code is not None else "unexpectedly"
    return (f"Application process terminated {exit_str} before becoming ready.", "FATAL_ERROR")


class MigratedAppLauncher:
    """Finds and launches Java applications (source and migrated) in background subprocesses."""

    # Patterns to exclude when looking for executable fat-JARs
    _JAR_EXCLUDE_PATTERNS = ("original", "sources", "javadoc", "tests", "-plain")

    def find_artifact(self, project_dir: Path, build_tool: str) -> tuple[Path | None, str | None]:
        """Locate runnable JAR or detect WAR files produced by Maven or Gradle.

        Returns:
            (artifact_path, error_if_unsupported)
        """
        bt = (build_tool or "").upper()
        candidates: list[Path] = []
        war_candidates: list[Path] = []

        if bt in ("MAVEN", ""):
            target_dir = project_dir / "target"
            if target_dir.exists():
                candidates += list(target_dir.glob("*.jar"))
                war_candidates += list(target_dir.glob("*.war"))

        if bt in ("GRADLE", ""):
            for libs_dir in [
                project_dir / "build" / "libs",
                project_dir / "build" / "output",
            ]:
                if libs_dir.exists():
                    candidates += list(libs_dir.glob("*.jar"))
                    war_candidates += list(libs_dir.glob("*.war"))

        # Filter out non-executable JARs
        runnable = [
            p for p in candidates
            if p.is_file()
            and not any(excl in p.name.lower() for excl in self._JAR_EXCLUDE_PATTERNS)
        ]

        if not runnable and war_candidates:
            return None, (
                f"Application produces a WAR archive ({war_candidates[0].name}) which requires an external "
                "servlet container (e.g. Apache Tomcat, Jetty, WebLogic). Standalone 'java -jar' execution is not supported."
            )

        if not runnable:
            # Fallback to any JAR at all
            runnable = [p for p in candidates if p.is_file()]

        if not runnable:
            return None, (
                f"No runnable JAR artifact found in project '{project_dir}'. "
                f"Build tool: {build_tool}. Ensure build packaging completed successfully."
            )

        # Pick the largest JAR (fat-JAR heuristic)
        chosen = max(runnable, key=lambda p: p.stat().st_size)

        # Validate that the JAR contains a Main-Class manifest
        try:
            with zipfile.ZipFile(chosen, "r") as z:
                if "META-INF/MANIFEST.MF" in z.namelist():
                    manifest_content = z.read("META-INF/MANIFEST.MF").decode("utf-8", errors="ignore")
                    if "Main-Class:" not in manifest_content and "Start-Class:" not in manifest_content:
                        logger.warning("Selected JAR %s does not declare Main-Class in MANIFEST.MF", chosen.name)
        except Exception as z_err:  # noqa: BLE001
            logger.debug("Could not inspect MANIFEST.MF for %s: %s", chosen.name, z_err)

        return chosen, None

    def launch(
        self,
        project_dir: Path,
        build_tool: str,
        port: int = 8080,
        java_home: str | None = None,
        startup_timeout: float = 30.0,
        app_type_label: str = "Application",
        log_fn: Callable[[str, str], None] | None = None,
    ) -> AppLaunchResult:
        """Launch the Java application and monitor its startup.

        Streams stdout and stderr in background and detects early exit / errors.
        """
        artifact, unsupported_err = self.find_artifact(project_dir, build_tool)
        if unsupported_err or artifact is None:
            return AppLaunchResult(
                success=False,
                error=unsupported_err or "No runnable JAR found.",
                failure_reason=unsupported_err or "No runnable JAR found.",
                failure_category="UNSUPPORTED_RUNTIME",
                runtime_unsupported=True,
            )

        java_exe = self._resolve_java(java_home)
        if not java_exe:
            return AppLaunchResult(
                success=False,
                artifact_path=str(artifact),
                error="'java' executable not found on PATH or JAVA_HOME. Cannot start application.",
                failure_reason="'java' executable not found on PATH or JAVA_HOME.",
                failure_category="FATAL_ERROR",
            )

        cmd = [
            java_exe,
            f"-Dserver.port={port}",
            "-jar",
            str(artifact),
            f"--server.port={port}",
        ]
        env = {
            **os.environ,
            "SERVER_PORT": str(port),
            "PORT": str(port),
        }

        logger.info("Launching %s: %s (port=%d)", app_type_label, " ".join(cmd), port)
        if log_fn:
            log_fn(f"Launching {app_type_label.lower()} process (artifact={artifact.name}, port={port})...", "INFO")

        startup_log: list[str] = []
        log_lock = threading.Lock()

        try:
            proc = subprocess.Popen(  # nosec B603  # noqa: S603
                cmd,
                cwd=str(project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1,
                start_new_session=(os.name != "nt"),
            )
        except Exception as e:
            return AppLaunchResult(
                success=False,
                artifact_path=str(artifact),
                error=f"Failed to spawn {app_type_label.lower()} process: {e}",
                failure_reason=f"Failed to spawn process: {e}",
                failure_category="FATAL_ERROR",
            )

        pid = proc.pid
        logger.info("%s process started with PID %d", app_type_label, pid)

        # Background drainer thread to keep pipe buffer from filling up
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
            except Exception:  # noqa: BLE001
                pass

        reader_thread = threading.Thread(target=drain_output, daemon=True)
        reader_thread.start()

        # Store process reference in registry
        MigratedAppLauncher._running_processes[pid] = {
            "proc": proc,
            "logs": startup_log,
            "port": port,
            "artifact": str(artifact),
            "lock": log_lock,
        }

        # Monitor startup indicators and early process exit
        deadline = time.time() + startup_timeout
        startup_detected = False
        early_exit = False
        exit_code: int | None = None

        while time.time() < deadline:
            exit_code = proc.poll()
            if exit_code is not None:
                early_exit = True
                break

            with log_lock:
                recent_logs = list(startup_log)

            for line in recent_logs:
                lower = line.lower()
                if any(ind in lower for ind in _STARTUP_INDICATORS):
                    startup_detected = True
                    break

            if startup_detected:
                break

            time.sleep(0.2)

        # If process exited prematurely during initial startup window
        if early_exit:
            time.sleep(0.3)  # Allow remaining log lines to drain
            with log_lock:
                final_logs = list(startup_log)
            reason, category = analyze_startup_failure(final_logs, exit_code)
            logger.warning("%s (PID %d) exited with code %s: %s", app_type_label, pid, exit_code, reason)
            return AppLaunchResult(
                success=False,
                pid=pid,
                port=port,
                artifact_path=str(artifact),
                exit_code=exit_code,
                startup_log=final_logs,
                error=reason,
                failure_reason=reason,
                failure_category=category,
            )

        with log_lock:
            current_logs = list(startup_log)

        return AppLaunchResult(
            success=True,
            pid=pid,
            port=port,
            artifact_path=str(artifact),
            startup_log=current_logs,
            startup_detected=startup_detected,
        )

    @staticmethod
    def get_process_info(pid: int) -> dict[str, Any] | None:
        """Returns runtime state and captured logs for a launched process."""
        info = MigratedAppLauncher._running_processes.get(pid)
        if not info:
            return None
        proc = info["proc"]
        exit_code = proc.poll()
        with info["lock"]:
            logs = list(info["logs"])
        return {
            "pid": pid,
            "is_alive": exit_code is None,
            "exit_code": exit_code,
            "port": info["port"],
            "artifact": info["artifact"],
            "logs": logs,
        }

    @staticmethod
    def stop(pid: int) -> None:
        """Terminate application process cleanly."""
        info = MigratedAppLauncher._running_processes.pop(pid, None)
        proc = info["proc"] if isinstance(info, dict) else info
        if proc is not None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
                logger.info("Application (PID %d) terminated cleanly.", pid)
            except Exception as e:  # noqa: BLE001
                logger.warning("Could not terminate app PID %d: %s", pid, e)
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass
        else:
            try:
                import signal
                os.kill(pid, signal.SIGTERM)
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _resolve_java(java_home: str | None = None) -> str | None:
        """Resolve the java executable from JAVA_HOME env or PATH."""
        if java_home:
            candidate = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
            if candidate.exists():
                return str(candidate)

        build_java = os.environ.get("BUILD_JAVA_HOME")
        if build_java:
            candidate = Path(build_java) / "bin" / ("java.exe" if os.name == "nt" else "java")
            if candidate.exists():
                return str(candidate)

        sys_java = os.environ.get("JAVA_HOME")
        if sys_java:
            candidate = Path(sys_java) / "bin" / ("java.exe" if os.name == "nt" else "java")
            if candidate.exists():
                return str(candidate)

        import shutil
        return shutil.which("java")

    # Class-level process registry
    _running_processes: dict[int, Any] = {}


# Alias for backward compatibility
AppLauncher = MigratedAppLauncher
