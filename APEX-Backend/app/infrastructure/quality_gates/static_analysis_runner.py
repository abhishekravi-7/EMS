"""SonarQube quality-gate integration.

Runs SonarQube/SonarCloud analysis after a successful migration:

* Maven projects  → ``mvn sonar:sonar``  (preferred; injects -Dsonar.java.binaries automatically)
* Other projects  → standalone ``sonar-scanner`` CLI

Execution details (command, cwd, resolved executable, PATH, exit code, stdout,
stderr, timing) are logged at INFO/DEBUG so operators can diagnose failures
without touching any existing migration logic.

If the scan fails, a ``SonarScanResult`` with ``scan_mode="cli_failed"`` and a
populated ``error_message`` is returned so the migration continues and the
Result page shows the real failure reason.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import subprocess  # nosec B404
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.infrastructure.java_runtime import build_tool_env

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass (unchanged shape – consumed by QualityGateRunner)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SonarScanResult:
    quality_gate: str | None = None
    bugs: int = 0
    vulnerabilities: int = 0
    code_smells: int = 0
    coverage: float = 0
    duplications: float = 0
    security_hotspots: int = 0
    scan_mode: str = "skipped"
    real_scan: bool = False
    analysis_url: str | None = None
    error_message: str | None = None
    report: dict[str, Any] | None = None
    log_lines: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class StaticAnalysisRunner:
    """Runs SonarQube/SonarCloud analysis when credentials are configured."""

    # ------------------------------------------------------------------ #
    # Public entry-point
    # ------------------------------------------------------------------ #

    def run(
        self,
        project_dir: Path,
        *,
        job_id: str,
        project_name: str | None = None,
        quality_checks_values: dict | None = None,
    ) -> SonarScanResult:
        qc_config = quality_checks_values or {}
        token = (qc_config.get("auth_token") or "").strip()
        if not token:
            return SonarScanResult(
                quality_gate="UNAVAILABLE",
                scan_mode="missing_token",
                error_message="SonarQube token missing. Configure it in User Settings.",
                log_lines=["SonarQube skipped: Token is not configured in user settings."],
            )

        proj_key_val = qc_config.get("project_key") or ""
        project_key = self._project_key(job_id, project_name or project_dir.name, proj_key_val)
        raw_host = (qc_config.get("sonarqube_url") or "http://localhost:9000").strip().rstrip("/")
        if not raw_host.startswith(("http://", "https://")):
            host_url = f"https://{raw_host}" if "sonarcloud.io" in raw_host else f"http://{raw_host}"
        else:
            host_url = raw_host

        analysis_url = f"{host_url}/dashboard?id={urllib.parse.quote(project_key)}"
        display_name = project_name or project_dir.name

        # Log pre-flight context
        logger.info(
            "SonarQube scan starting for job %s | project_key=%s | host=%s | cwd=%s",
            job_id, project_key, host_url, project_dir,
        )

        # Build command -------------------------------------------------------
        if (project_dir / "pom.xml").exists():
            command, early_error = self._maven_command(
                project_dir, project_key, display_name, host_url, token, analysis_url,
            )
        else:
            command, early_error = self._scanner_command(
                project_dir, project_key, display_name, host_url, analysis_url,
            )

        if early_error is not None:
            return early_error

        # Append optional org flag
        sonar_org = (qc_config.get("sonar_organization") or "").strip()
        if sonar_org:
            command.append(f"-Dsonar.organization={sonar_org}")

        # Build environment (with correct JDK and Maven toolchain in PATH) -----
        env = build_tool_env()
        env["SONAR_TOKEN"] = token
        env["SONAR_HOST_URL"] = host_url

        # Resolve executable --------------------------------------------------
        resolved_exe = self._resolve_exe(command[0], search_path=env.get("PATH"))
        if not resolved_exe:
            error_msg = (
                f"Executable '{command[0]}' not found in PATH or known locations. "
                "Ensure Maven or SonarScanner is installed and available."
            )
            logger.error("SonarQube: %s | PATH=%s", error_msg, env.get("PATH", ""))
            return SonarScanResult(
                quality_gate="FAILED",
                scan_mode="cli_failed",
                real_scan=True,
                analysis_url=analysis_url,
                error_message=error_msg,
                log_lines=[error_msg],
            )
        command[0] = resolved_exe

        # Verify working directory --------------------------------------------
        if not project_dir.is_dir():
            error_msg = f"Working directory '{project_dir}' does not exist."
            logger.error("SonarQube: %s", error_msg)
            return SonarScanResult(
                quality_gate="FAILED",
                scan_mode="cli_failed",
                real_scan=True,
                analysis_url=analysis_url,
                error_message=error_msg,
                log_lines=[error_msg],
            )

        # Log execution details -----------------------------------------------
        # Redact token from the logged command
        safe_cmd = " ".join(
            arg.replace(token, "***") if token in arg else arg
            for arg in command
        )
        logger.info("Executing Sonar command: %s", safe_cmd)
        logger.debug("CWD: %s", str(project_dir))
        logger.debug("Resolved executable: %s", resolved_exe)
        logger.debug("PATH: %s", env.get("PATH", ""))

        # Execute -------------------------------------------------------------
        start_time = time.time()
        completed = subprocess.run(  # nosec B603 # noqa: S603
            command,
            cwd=project_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        duration = time.time() - start_time

        output_lines = self._redact(
            (completed.stdout + "\n" + completed.stderr).splitlines(), token
        )

        logger.info(
            "SonarQube scan finished in %.2f s with exit code %s",
            duration, completed.returncode,
        )
        logger.debug("Sonar stdout:\n%s", completed.stdout)
        logger.debug("Sonar stderr:\n%s", completed.stderr)

        # Handle failure ------------------------------------------------------
        if completed.returncode != 0:
            error_msg = (
                f"SonarQube scanner failed (exit {completed.returncode}, "
                f"{duration:.2f}s):\n" + "\n".join(output_lines)
            )
            return SonarScanResult(
                quality_gate="FAILED",
                scan_mode="cli_failed",
                real_scan=True,
                analysis_url=analysis_url,
                error_message=error_msg,
                log_lines=[
                    f"SonarQube scan failed with exit code {completed.returncode} in {duration:.2f}s.",
                ] + output_lines,
            )

        # Read API metrics after a successful scan ----------------------------
        api_data = self._read_sonar_api(host_url, token, project_key, project_dir, output_lines)
        report = {
            "project_key": project_key,
            "analysis_url": analysis_url,
            "quality_gate": api_data.get("quality_gate"),
            "measures": api_data.get("measures", {}),
            "issues": api_data.get("issues", {}),
            "bug_details": api_data.get("bug_details", []),
            "vulnerability_details": api_data.get("vulnerability_details", []),
            "code_smell_details": api_data.get("code_smell_details", []),
            "security_hotspot_details": api_data.get("security_hotspot_details", []),
            "all_issues": api_data.get("all_issues", []),
        }
        return SonarScanResult(
            quality_gate=api_data.get("quality_gate") or "PASSED",
            bugs=int(api_data.get("issues", {}).get("bugs") or 0),
            vulnerabilities=int(api_data.get("issues", {}).get("vulnerabilities") or 0),
            code_smells=int(api_data.get("issues", {}).get("code_smells") or 0),
            coverage=float(api_data.get("measures", {}).get("coverage") or 0),
            duplications=float(
                api_data.get("measures", {}).get("duplicated_lines_density") or 0
            ),
            security_hotspots=int(
                api_data.get("issues", {}).get("security_hotspots") or 0
            ),
            scan_mode="real",
            real_scan=True,
            analysis_url=analysis_url,
            report=report,
            log_lines=[
                "SonarQube scan completed.",
                f"SonarQube dashboard: {analysis_url}",
            ] + output_lines[-10:],
        )

    # ------------------------------------------------------------------ #
    # Command builders
    # ------------------------------------------------------------------ #

    # Fully-qualified Sonar Maven Plugin goal.
    # Using the shorthand "sonar:sonar" requires the plugin to be declared in
    # the project's pom.xml (or in a settings.xml plugin-group).  The FQCN
    # form always works because Maven resolves it from Central on demand.
    _SONAR_MVN_GOAL = (
        "org.sonarsource.scanner.maven:sonar-maven-plugin:sonar"
    )

    def _maven_command(
        self,
        project_dir: Path,
        project_key: str,
        display_name: str,
        host_url: str,
        token: str,
        analysis_url: str,
    ) -> tuple[list[str], SonarScanResult | None]:
        """Build the Maven Sonar command, validating compiled classes first.

        Uses the fully-qualified plugin goal so Maven can resolve it from
        Maven Central even when the project pom.xml does not declare the
        Sonar plugin — eliminating the
        "No plugin found for prefix 'sonar'" error.
        """
        binaries_dir = project_dir / "target" / "classes"
        if not binaries_dir.is_dir():
            error_msg = (
                f"Compiled classes not found at '{binaries_dir}'. "
                "Ensure the Maven build succeeded before SonarQube analysis."
            )
            logger.error("SonarQube: %s", error_msg)
            return [], SonarScanResult(
                quality_gate="FAILED",
                scan_mode="cli_failed",
                real_scan=True,
                analysis_url=analysis_url,
                error_message=error_msg,
                log_lines=[error_msg],
            )

        command = [
            "mvn",
            self._SONAR_MVN_GOAL,          # FQCN — no pom.xml plugin entry needed
            f"-Dsonar.projectKey={project_key}",
            f"-Dsonar.projectName={display_name}",
            f"-Dsonar.host.url={host_url}",
            f"-Dsonar.token={token}",       # sonar.login is deprecated in scanner 5+
            f"-Dsonar.java.binaries={binaries_dir}",
        ]
        logger.info(
            "Maven project detected — using fully-qualified Sonar goal '%s' "
            "with binaries at %s",
            self._SONAR_MVN_GOAL, binaries_dir,
        )
        return command, None

    def _scanner_command(
        self,
        project_dir: Path,
        project_key: str,
        display_name: str,
        host_url: str,
        analysis_url: str,
    ) -> tuple[list[str], SonarScanResult | None]:
        """Build standalone sonar-scanner CLI command."""
        scanner = self._resolve_command(settings.sonarqube_scanner_command)
        if not scanner:
            error_msg = (
                f"sonar-scanner CLI '{settings.sonarqube_scanner_command}' not found on PATH. "
                "Install SonarScanner CLI or set SONAR_SCANNER_COMMAND in .env."
            )
            logger.error("SonarQube: %s", error_msg)
            return [], SonarScanResult(
                quality_gate="UNAVAILABLE",
                scan_mode="missing_cli",
                error_message=error_msg,
                log_lines=[error_msg],
            )
        command = [
            scanner,
            f"-Dsonar.projectKey={project_key}",
            f"-Dsonar.projectName={display_name}",
            "-Dsonar.sources=.",
            f"-Dsonar.host.url={host_url}",
        ]
        logger.info("Non-Maven project — using standalone sonar-scanner: %s", scanner)
        return command, None

    # ------------------------------------------------------------------ #
    # Executable resolution (handles mvn.cmd on Windows)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_exe(name: str, search_path: str | None = None) -> str | None:
        """Resolve an executable name to its full path.

        On Windows, ``mvn`` is really ``mvn.cmd``.  We try the name as-is
        first (works on Linux/macOS), then append common Windows extensions,
        then fall back to hardcoded Maven *Program Files* directories.
        """
        # Direct which lookup (works on Linux/macOS; also finds .cmd on Windows
        # if the bin directory is on PATH)
        found = shutil.which(name, path=search_path)
        if found:
            return found

        # Windows: try explicit extensions
        if os.name == "nt":
            for ext in (".cmd", ".bat", ".exe"):
                found = shutil.which(name + ext, path=search_path)
                if found:
                    return found

            # Fallback: common Maven Program Files installation directories
            if name in ("mvn", "mvn.cmd"):
                common_maven_dirs = [
                    r"C:\Program Files\apache-maven-3.9.16\bin",
                    r"C:\Program Files\apache-maven-3.9.9\bin",
                    r"C:\Program Files\apache-maven-3.9.0\bin",
                    r"C:\Program Files\apache-maven\bin",
                    r"C:\Program Files (x86)\apache-maven-3.9.16\bin",
                ]
                for base in common_maven_dirs:
                    candidate = Path(base) / "mvn.cmd"
                    if candidate.is_file():
                        logger.info("Resolved Maven via fallback: %s", candidate)
                        return str(candidate)

        return None

    @staticmethod
    def _resolve_command(command: str, search_path: str | None = None) -> str | None:
        """Resolve a command name or path to a full executable path."""
        command = command.strip()
        if not command:
            return None
        if Path(command).is_file():
            return command
        return shutil.which(command, path=search_path)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _project_key(job_id: str, name: str, user_project_key: str = "") -> str:
        if user_project_key.strip():
            return user_project_key.strip()
        seed = f"{settings.sonarqube_project_key_prefix}-{job_id}-{name}"
        return re.sub(r"[^A-Za-z0-9_.:-]+", "-", seed).strip("-")[:180]

    @staticmethod
    def _redact(lines: list[str], token: str) -> list[str]:
        if not token:
            return [line for line in lines if line.strip()]
        return [line.replace(token, "***") for line in lines if line.strip()]

    # ------------------------------------------------------------------ #
    # SonarQube REST API readers & CE Task Polling
    # ------------------------------------------------------------------ #

    def _find_task_id(self, project_dir: Path, output_lines: list[str]) -> str | None:
        """Extract Compute Engine Task ID from report-task.txt or scan logs."""
        possible_paths = [
            project_dir / "target" / "sonar" / "report-task.txt",
            project_dir / ".sonar" / "report-task.txt",
            project_dir / "build" / "sonar" / "report-task.txt",
        ]
        for path in possible_paths:
            if path.is_file():
                try:
                    content = path.read_text(encoding="utf-8")
                    for line in content.splitlines():
                        if line.startswith("ceTaskId="):
                            task_id = line.split("=", 1)[1].strip()
                            if task_id:
                                logger.info("Found SonarQube CE task ID from %s: %s", path, task_id)
                                return task_id
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Error reading %s: %s", path, exc)

        full_text = "\n".join(output_lines)
        match = re.search(r"ceTaskId=([A-Za-z0-9_-]+)", full_text)
        if match:
            task_id = match.group(1)
            logger.info("Found SonarQube CE task ID from log output: %s", task_id)
            return task_id

        match = re.search(r"task\?id=([A-Za-z0-9_-]+)", full_text)
        if match:
            task_id = match.group(1)
            logger.info("Found SonarQube CE task ID from task URL: %s", task_id)
            return task_id

        return None

    def _wait_for_ce_task(self, host_url: str, token: str, task_id: str, timeout_seconds: int = 60) -> bool:
        """Poll SonarQube Compute Engine task until SUCCESS, FAILED, or timeout."""
        logger.info("Waiting for SonarQube Compute Engine task %s to finish processing...", task_id)
        start = time.time()
        url = f"{host_url}/api/ce/task?" + urllib.parse.urlencode({"id": task_id})
        while time.time() - start < timeout_seconds:
            try:
                data = self._get_json(url, token)
                status = (data.get("task") or {}).get("status")
                logger.debug("SonarQube CE task %s status: %s", task_id, status)
                if status == "SUCCESS":
                    logger.info("SonarQube Compute Engine task %s completed successfully.", task_id)
                    return True
                if status in ("FAILED", "CANCELED"):
                    logger.warning("SonarQube Compute Engine task %s ended with status: %s", task_id, status)
                    return False
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error checking SonarQube CE task status: %s", exc)
            time.sleep(2)
        logger.warning("Timed out waiting for SonarQube CE task %s after %d seconds.", task_id, timeout_seconds)
        return False

    def _fetch_all_issues(self, host_url: str, token: str, project_key: str) -> dict[str, list[dict[str, Any]]]:
        """Fetch all issue details with pagination from SonarQube API."""
        bug_details: list[dict[str, Any]] = []
        vulnerability_details: list[dict[str, Any]] = []
        code_smell_details: list[dict[str, Any]] = []
        security_hotspot_details: list[dict[str, Any]] = []
        all_issues: list[dict[str, Any]] = []

        page = 1
        page_size = 500
        max_pages = 20  # Limit to 10,000 issues max

        query_param_name = "componentKeys"
        while page <= max_pages:
            try:
                params = {
                    query_param_name: project_key,
                    "ps": page_size,
                    "p": page,
                }
                path = "/api/issues/search?" + urllib.parse.urlencode(params)
                payload = self._get_json(host_url + path, token)
                raw_issues = payload.get("issues") or []

                if not raw_issues and page == 1:
                    for alt_param in ("components", "projects", "projectKeys"):
                        try:
                            alt_path = f"/api/issues/search?{alt_param}={urllib.parse.quote(project_key)}&ps={page_size}&p=1"
                            alt_payload = self._get_json(host_url + alt_path, token)
                            alt_issues = alt_payload.get("issues") or []
                            if alt_issues:
                                raw_issues = alt_issues
                                payload = alt_payload
                                query_param_name = alt_param
                                logger.info("Found %d SonarQube issues using query param '%s'", len(raw_issues), alt_param)
                                break
                        except Exception as alt_exc:  # noqa: BLE001
                            logger.debug("Alternative issue search with %s notice: %s", alt_param, alt_exc)

                if not raw_issues:
                    break

                for issue in raw_issues:
                    comp = str(issue.get("component") or "")
                    file_path = comp.split(":", 1)[1] if ":" in comp else comp

                    item = {
                        "key": issue.get("key"),
                        "type": issue.get("type"),
                        "severity": issue.get("severity"),
                        "rule": issue.get("rule"),
                        "message": issue.get("message"),
                        "component": file_path,
                        "file_path": file_path,
                        "line": issue.get("line"),
                        "line_number": issue.get("line"),
                        "status": issue.get("status"),
                        "resolution": issue.get("resolution"),
                        "effort": issue.get("effort"),
                        "debt": issue.get("debt"),
                        "author": issue.get("author"),
                        "creation_date": issue.get("creationDate"),
                        "update_date": issue.get("updateDate"),
                    }
                    all_issues.append(item)

                    itype = str(issue.get("type") or "").upper()
                    if "BUG" in itype:
                        bug_details.append(item)
                    elif "VULNERAB" in itype:
                        vulnerability_details.append(item)
                    elif "SMELL" in itype:
                        code_smell_details.append(item)
                    elif "HOTSPOT" in itype:
                        security_hotspot_details.append(item)
                    else:
                        code_smell_details.append(item)

                total = int((payload.get("paging") or {}).get("total") or payload.get("total") or 0)
                if page * page_size >= total or len(raw_issues) < page_size:
                    break
                page += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error fetching SonarQube issues page %d: %s", page, exc)
                break

        # Check dedicated hotspots API if needed
        if not security_hotspot_details:
            for h_param in ("projectKey", "project", "component", "componentKeys"):
                try:
                    h_path = f"/api/hotspots/search?{h_param}={urllib.parse.quote(project_key)}&ps=500&p=1"
                    h_payload = self._get_json(host_url + h_path, token)
                    hotspots_list = h_payload.get("hotspots") or []
                    if hotspots_list:
                        logger.info("Found %d SonarQube hotspots using query param '%s'", len(hotspots_list), h_param)
                        for hotspot in hotspots_list:
                            comp = str(hotspot.get("component") or "")
                            file_path = comp.split(":", 1)[1] if ":" in comp else comp
                            item = {
                                "key": hotspot.get("key"),
                                "type": "SECURITY_HOTSPOT",
                                "severity": hotspot.get("vulnerabilityProbability") or hotspot.get("severity") or "MEDIUM",
                                "rule": hotspot.get("ruleKey") or hotspot.get("rule") or "security:hotspot",
                                "message": hotspot.get("message") or "Security hotspot requires manual review",
                                "component": file_path,
                                "file_path": file_path,
                                "line": hotspot.get("line"),
                                "line_number": hotspot.get("line"),
                                "status": hotspot.get("status") or "TO_REVIEW",
                                "resolution": hotspot.get("resolution"),
                                "effort": hotspot.get("effort"),
                                "author": hotspot.get("author"),
                                "creation_date": hotspot.get("creationDate"),
                                "update_date": hotspot.get("updateDate"),
                                "security_category": hotspot.get("securityCategory"),
                                "vulnerability_probability": hotspot.get("vulnerabilityProbability"),
                            }
                            security_hotspot_details.append(item)
                            all_issues.append(item)
                        break
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Hotspot search with %s notice: %s", h_param, exc)

        return {
            "bug_details": bug_details,
            "vulnerability_details": vulnerability_details,
            "code_smell_details": code_smell_details,
            "security_hotspot_details": security_hotspot_details,
            "all_issues": all_issues,
        }

    def _read_sonar_api(
        self,
        host_url: str,
        token: str,
        project_key: str,
        project_dir: Path,
        output_lines: list[str],
    ) -> dict[str, Any]:
        """Poll Compute Engine task if task ID found, then fetch quality gate, measures & issue details."""
        task_id = self._find_task_id(project_dir, output_lines)
        if task_id:
            self._wait_for_ce_task(host_url, token, task_id, timeout_seconds=60)
        else:
            logger.info("No ceTaskId detected. Waiting 3 seconds before fetching SonarQube API metrics...")
            time.sleep(3)

        data: dict[str, Any] = {"issues": {}, "measures": {}}

        # Quality gate status
        try:
            path = "/api/qualitygates/project_status?" + urllib.parse.urlencode(
                {"projectKey": project_key}
            )
            gate = self._get_json(host_url + path, token)
            status = (gate.get("projectStatus") or {}).get("status")
            if status:
                status_upper = str(status).upper()
                if status_upper in ("OK", "PASSED"):
                    data["quality_gate"] = "PASSED"
                elif status_upper in ("ERROR", "FAILED"):
                    data["quality_gate"] = "FAILED"
                else:
                    data["quality_gate"] = status_upper
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unable to read SonarQube quality gate: %s", exc)

        # Detailed issues with pagination
        details = self._fetch_all_issues(host_url, token, project_key)
        data["bug_details"] = details["bug_details"]
        data["vulnerability_details"] = details["vulnerability_details"]
        data["code_smell_details"] = details["code_smell_details"]
        data["security_hotspot_details"] = details["security_hotspot_details"]
        data["all_issues"] = details["all_issues"]

        # Issue summary counts
        data["issues"]["bugs"] = len(details["bug_details"])
        data["issues"]["vulnerabilities"] = len(details["vulnerability_details"])
        data["issues"]["code_smells"] = len(details["code_smell_details"])
        data["issues"]["security_hotspots"] = len(details["security_hotspot_details"])

        # Also attempt search counts as fallback if zero
        if not data["all_issues"]:
            issue_types = {
                "bugs": "BUG",
                "vulnerabilities": "VULNERABILITY",
                "code_smells": "CODE_SMELL",
                "security_hotspots": "SECURITY_HOTSPOT",
            }
            for metric, sonar_type in issue_types.items():
                try:
                    path = "/api/issues/search?" + urllib.parse.urlencode(
                        {"componentKeys": project_key, "types": sonar_type, "ps": 1}
                    )
                    payload = self._get_json(host_url + path, token)
                    data["issues"][metric] = int(payload.get("total") or 0)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Unable to read SonarQube issue metric %s: %s", metric, exc)

        # Measures (coverage, duplication, ratings)
        try:
            metrics = (
                "coverage,duplicated_lines_density,bugs,vulnerabilities,"
                "code_smells,security_hotspots,sqale_rating,reliability_rating,security_rating"
            )
            path = "/api/measures/component?" + urllib.parse.urlencode(
                {"component": project_key, "metricKeys": metrics}
            )
            payload = self._get_json(host_url + path, token)
            for measure in (payload.get("component") or {}).get("measures") or []:
                data["measures"][measure.get("metric")] = float(measure.get("value") or 0)

            # Fallback issue counts from measures if counts are still zero
            for metric in ("bugs", "vulnerabilities", "code_smells", "security_hotspots"):
                if not data["issues"].get(metric) and data["measures"].get(metric):
                    data["issues"][metric] = int(data["measures"][metric])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unable to read SonarQube measure metrics: %s", exc)

        return data

    @staticmethod
    def _get_json(url: str, token: str) -> dict[str, Any]:
        # Security check: validate URL scheme
        if not url.startswith("https://") and not url.startswith("http://"):
            logger.error("Invalid SonarQube API URL: %s", url)
            return {}

        auth = base64.b64encode(f"{token}:".encode("utf-8")).decode("ascii")
        headers = {
            "Authorization": f"Basic {auth}",
            "User-Agent": "Java-APEX-Platform/1.0",
            "Accept": "application/json",
        }
        request = urllib.request.Request(url, headers=headers)  # nosec B310  # noqa: S310
        with urllib.request.urlopen(request, timeout=20) as response:  # nosec B310 # noqa: S310
            return json.loads(response.read().decode("utf-8"))
