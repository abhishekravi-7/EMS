"""FOSSA quality-gate integration."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FossaScanResult:
    policy_status: str | None = None
    total_dependencies: int = 0
    license_issues: int = 0
    vulnerabilities: int = 0
    outdated_dependencies: int = 0
    scan_mode: str = "skipped"
    real_scan: bool = False
    analysis_url: str | None = None
    error_message: str | None = None
    report: dict[str, Any] | None = None
    log_lines: list[str] = field(default_factory=list)


class DependencyCheckRunner:
    """Runs FOSSA analysis when a FOSSA API key is configured."""

    def run(self, project_dir: Path, *, job_id: str, project_name: str | None = None) -> FossaScanResult:
        api_key = settings.fossa_api_key.strip()
        if not api_key:
            return FossaScanResult(
                policy_status="UNAVAILABLE",
                scan_mode="missing_token",
                error_message="Set FOSSA_API_KEY in .env to enable FOSSA quality gate scans.",
                log_lines=["FOSSA skipped: FOSSA_API_KEY is not configured."],
            )

        cli = self._resolve_command(settings.fossa_cli_command)
        if not cli:
            return FossaScanResult(
                policy_status="UNAVAILABLE",
                scan_mode="missing_cli",
                error_message="FOSSA CLI (fossa) was not found on PATH or known locations.",
                log_lines=["FOSSA skipped: FOSSA CLI was not found on PATH."],
            )

        project = self._project_name(job_id, project_name or project_dir.name)
        host_url = (settings.fossa_endpoint.strip() if settings.fossa_endpoint.strip() else "https://app.fossa.com").rstrip("/")
        analysis_url = self._analysis_url(project)

        env = os.environ.copy()
        env["FOSSA_API_KEY"] = api_key
        if settings.fossa_endpoint.strip():
            env["FOSSA_ENDPOINT"] = settings.fossa_endpoint.strip()

        logger.info("Running FOSSA analysis for job %s | project=%s | cwd=%s | cli=%s", job_id, project, project_dir, cli)

        # Step 1: fossa analyze
        analyze_cmd = [cli, "analyze", "--project", project]

        # Is Maven project?
        if (project_dir / "pom.xml").exists():
            logger.info("Maven project detected for FOSSA analysis.")

        safe_analyze_cmd = " ".join([arg.replace(api_key, "***") for arg in analyze_cmd])
        logger.info("Executing FOSSA command: %s", safe_analyze_cmd)
        logger.debug("CWD: %s | CLI: %s", str(project_dir), cli)

        start_time = time.time()
        analyze = subprocess.run(
            analyze_cmd,
            cwd=project_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        duration_analyze = time.time() - start_time
        analyze_output = (analyze.stdout + "\n" + analyze.stderr).strip()
        analyze_lines = self._redact(analyze_output.splitlines(), api_key)

        logger.info("FOSSA analyze finished in %.2f s with exit code %s", duration_analyze, analyze.returncode)
        logger.debug("FOSSA analyze stdout: %s", analyze.stdout)
        logger.debug("FOSSA analyze stderr: %s", analyze.stderr)

        # Check for authentication failure
        if "401" in analyze_output or "unauthorized" in analyze_output.lower() or "invalid api key" in analyze_output.lower():
            return FossaScanResult(
                policy_status="FAILED",
                scan_mode="authentication_failed",
                real_scan=True,
                analysis_url=analysis_url,
                error_message="FOSSA API authentication failed. Verify your FOSSA_API_KEY.",
                log_lines=["FOSSA authentication failed."] + analyze_lines[-15:],
            )

        if analyze.returncode not in (0, 1):
            error_msg = f"FOSSA analysis failed (exit {analyze.returncode}):\n" + "\n".join(analyze_lines)
            return FossaScanResult(
                policy_status="FAILED",
                scan_mode="analysis_failed",
                real_scan=True,
                analysis_url=analysis_url,
                error_message=error_msg,
                log_lines=[f"FOSSA analysis failed with exit code {analyze.returncode}."] + analyze_lines[-20:],
            )

        # Step 2: fossa test --format json
        test_cmd = [cli, "test", "--project", project, "--format", "json"]
        logger.info("Executing FOSSA test: %s", " ".join(test_cmd))

        start_test_time = time.time()
        test = subprocess.run(
            test_cmd,
            cwd=project_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        duration_test = time.time() - start_test_time
        test_lines = self._redact((test.stdout + "\n" + test.stderr).splitlines(), api_key)

        logger.info("FOSSA test finished in %.2f s with exit code %s", duration_test, test.returncode)
        logger.debug("FOSSA test stdout: %s", test.stdout)
        logger.debug("FOSSA test stderr: %s", test.stderr)

        parsed = self._parse_json_output(test.stdout)

        # Exit code semantics for `fossa test`:
        #   0 = policy passed (no issues found)
        #   1 = policy failed (issues/violations found) — this is a SCAN RESULT, not an error
        #  >1 = CLI execution failure (bad credentials, network error, invalid command, etc.)
        if test.returncode > 1:
            error_msg = f"FOSSA test command failed (exit {test.returncode}) — this is a CLI execution error, not a policy result."
            logger.error("%s | stdout=%s | stderr=%s", error_msg, test.stdout[:500], test.stderr[:500])
            return FossaScanResult(
                policy_status="FAILED",
                scan_mode="test_cli_error",
                real_scan=True,
                analysis_url=analysis_url,
                error_message=error_msg,
                report={"project": project, "policy_status": "FAILED", "analysis_url": analysis_url, "raw": parsed},
                log_lines=[
                    f"FOSSA test CLI error (exit {test.returncode}) — not a policy violation.",
                    f"FOSSA dashboard: {analysis_url}",
                ] + test_lines[-20:],
            )

        extracted = self._extract_detailed_data(parsed)
        # Exit code 0 = PASSED, exit code 1 = policy violations found (FAILED policy, successful scan)
        policy_status = "PASSED" if test.returncode == 0 else "FAILED"
        if test.returncode == 1:
            logger.info(
                "FOSSA test returned exit code 1: policy violations detected. "
                "This is a successful scan with findings, not a migration failure."
            )

        report = {
            "project": project,
            "policy_status": policy_status,
            "analysis_url": analysis_url,
            "total_dependencies": extracted["total_dependencies"],
            "license_issues": extracted["license_issues"],
            "vulnerabilities": extracted["vulnerabilities"],
            "outdated_dependencies": extracted["outdated_count"],
            "vulnerabilities_critical": extracted["vulnerabilities_critical"],
            "vulnerabilities_high": extracted["vulnerabilities_high"],
            "vulnerabilities_medium": extracted["vulnerabilities_medium"],
            "vulnerabilities_low": extracted["vulnerabilities_low"],
            "dependencies_list": extracted["dependencies_list"],
            "licenses_list": extracted["licenses_list"],
            "vulnerabilities_list": extracted["vulnerabilities_list"],
            "outdated_list": extracted["outdated_list"],
            "raw": parsed,
        }

        # scan_mode = "real" for both PASSED (0) and policy-FAILED (1); only CLI errors get a different mode
        scan_mode = "real"

        return FossaScanResult(
            policy_status=policy_status,
            license_issues=extracted["license_issues"],
            vulnerabilities=extracted["vulnerabilities"],
            total_dependencies=extracted["total_dependencies"],
            outdated_dependencies=extracted["outdated_count"],
            scan_mode=scan_mode,
            real_scan=True,
            analysis_url=analysis_url,
            # error_message is informational only — it does NOT cause a migration failure
            error_message=None if policy_status == "PASSED" else "FOSSA policy check found violations. See the FOSSA dashboard for details.",
            report=report,
            log_lines=[
                "FOSSA analysis completed.",
                f"FOSSA policy status: {policy_status}",
                f"FOSSA dashboard: {analysis_url}",
            ] + analyze_lines[-5:] + test_lines[-10:],
        )

    @staticmethod
    def _resolve_command(command: str) -> str | None:
        command = (command or "fossa").strip()
        found = shutil.which(command)
        if found:
            return found

        if os.name == "nt":
            for ext in (".exe", ".cmd", ".bat"):
                found = shutil.which(command + ext)
                if found:
                    return found

            # Windows fallback locations
            user_profile = os.environ.get("USERPROFILE", "")
            possible_paths = [
                r"C:\Program Files\FOSSA\fossa.exe",
                r"C:\Program Files (x86)\FOSSA\fossa.exe",
                r"C:\ProgramData\fossa\fossa.exe",
                r"C:\fossa\fossa.exe",
                os.path.join(user_profile, "AppData", "Local", "FOSSA", "fossa.exe") if user_profile else "",
                os.path.join(user_profile, ".fossa", "bin", "fossa.exe") if user_profile else "",
            ]
            for p in possible_paths:
                if p and Path(p).is_file():
                    logger.info("Resolved FOSSA via fallback path: %s", p)
                    return p

        return None

    @staticmethod
    def _project_name(job_id: str, name: str) -> str:
        seed = f"java-apex-{job_id}-{name}"
        return re.sub(r"[^A-Za-z0-9_.:-]+", "-", seed).strip("-")[:180]

    @staticmethod
    def _analysis_url(project: str) -> str | None:
        endpoint = settings.fossa_endpoint.rstrip("/") if settings.fossa_endpoint else "https://app.fossa.com"
        return f"{endpoint}/projects/custom%2B{project}"

    @staticmethod
    def _redact(lines: list[str], secret: str) -> list[str]:
        if not secret:
            return [l for l in lines if l.strip()]
        return [line.replace(secret, "***") for line in lines if line.strip()]

    @staticmethod
    def _parse_json_output(output: str) -> Any:
        output = (output or "").strip()
        if not output:
            return None
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return None

    def _extract_detailed_data(self, payload: Any) -> dict[str, Any]:
        """Extract structured dependency, license, vulnerability, and outdated package arrays."""
        result = {
            "total_dependencies": 0,
            "license_issues": 0,
            "vulnerabilities": 0,
            "outdated_count": 0,
            "vulnerabilities_critical": 0,
            "vulnerabilities_high": 0,
            "vulnerabilities_medium": 0,
            "vulnerabilities_low": 0,
            "dependencies_list": [],
            "licenses_list": [],
            "vulnerabilities_list": [],
            "outdated_list": [],
        }

        if not payload:
            return result

        def safe_text(val: Any) -> str:
            if val is None:
                return ""
            if isinstance(val, str):
                return val
            if isinstance(val, dict):
                for key in ("text", "value", "name", "label", "summary", "title", "message"):
                    if key in val and val[key] is not None:
                        return safe_text(val[key])
                try:
                    logger.debug("Unknown dict structure in FOSSA JSON: %s", val)
                    return json.dumps(val)
                except Exception:
                    return str(val)
            if isinstance(val, list):
                return ", ".join(safe_text(v) for v in val if v is not None)
            return str(val)

        dependencies_map: dict[str, dict[str, Any]] = {}
        licenses_map: dict[str, dict[str, Any]] = {}
        vulnerabilities_list: list[dict[str, Any]] = []
        outdated_list: list[dict[str, Any]] = []

        # Traverse FOSSA payload
        if isinstance(payload, dict):
            # Check issues array
            issues = payload.get("issues") or payload.get("graph") or []
            if isinstance(issues, list):
                for iss in issues:
                    if isinstance(iss, dict):
                        itype = safe_text(iss.get("type")).lower()
                        title_raw = iss.get("title") or iss.get("summary") or iss.get("rule") or "Issue"
                        title = safe_text(title_raw)
                        sev = safe_text(iss.get("severity") or iss.get("level") or "medium").upper()
                        pkg = safe_text(iss.get("package") or iss.get("dependency") or "Unknown")

                        if "license" in itype or "license" in title.lower():
                            result["license_issues"] += 1
                            lic_name = safe_text(iss.get("license") or title)
                            if lic_name not in licenses_map:
                                licenses_map[lic_name] = {
                                    "name": lic_name,
                                    "risk": "HIGH" if "prohibited" in title.lower() else "MEDIUM",
                                    "affected_packages": [pkg] if pkg != "Unknown" else [],
                                    "count": 1,
                                }
                            else:
                                if pkg != "Unknown" and pkg not in licenses_map[lic_name]["affected_packages"]:
                                    licenses_map[lic_name]["affected_packages"].append(pkg)
                                licenses_map[lic_name]["count"] += 1
                        elif "vuln" in itype or "vuln" in title.lower() or "cve" in title.lower():
                            result["vulnerabilities"] += 1
                            if "CRIT" in sev:
                                result["vulnerabilities_critical"] += 1
                            elif "HIGH" in sev:
                                result["vulnerabilities_high"] += 1
                            elif "MED" in sev:
                                result["vulnerabilities_medium"] += 1
                            else:
                                result["vulnerabilities_low"] += 1

                            vulnerabilities_list.append({
                                "id": safe_text(iss.get("id") or iss.get("cve") or title),
                                "severity": sev,
                                "package": pkg,
                                "installed_version": safe_text(iss.get("version") or iss.get("installed_version") or "N/A"),
                                "fixed_version": safe_text(iss.get("fixed_version") or iss.get("fix") or "N/A"),
                                "cve": safe_text(iss.get("cve") or (title if "cve" in title.lower() else "N/A")),
                                "description": safe_text(iss.get("description") or title),
                                "reference": safe_text(iss.get("url") or iss.get("reference")) or None,
                            })

            # Check dependencies array
            deps = payload.get("dependencies") or payload.get("modules") or []
            if isinstance(deps, list):
                for dep in deps:
                    if isinstance(dep, dict):
                        pkg_name = safe_text(dep.get("name") or dep.get("package") or dep.get("locator") or "Unknown")
                        version = safe_text(dep.get("version") or dep.get("revision") or "N/A")
                        lic = safe_text(dep.get("license") or dep.get("licenses") or "Unknown")

                        dependencies_map[pkg_name] = {
                            "package": pkg_name,
                            "version": version,
                            "license": lic,
                            "risk": "LOW" if lic != "Unknown" else "MEDIUM",
                        }

                        if dep.get("outdated") or dep.get("latest_version"):
                            outdated_list.append({
                                "package": pkg_name,
                                "current_version": version,
                                "latest_version": safe_text(dep.get("latest_version") or "Latest"),
                            })

        result["dependencies_list"] = list(dependencies_map.values())
        result["licenses_list"] = list(licenses_map.values())
        result["vulnerabilities_list"] = vulnerabilities_list
        result["outdated_list"] = outdated_list

        result["total_dependencies"] = len(result["dependencies_list"])
        result["outdated_count"] = len(result["outdated_list"])

        return result
