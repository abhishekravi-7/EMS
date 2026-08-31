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
    denied_license_issues: int = 0
    flagged_license_issues: int = 0
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
        # analysis_url is a fallback; the real URL will be extracted from CLI output after `fossa analyze` runs
        fallback_url = self._analysis_url(project)

        env = os.environ.copy()
        env["FOSSA_API_KEY"] = api_key
        if settings.fossa_endpoint.strip():
            env["FOSSA_ENDPOINT"] = settings.fossa_endpoint.strip()

        logger.info("Running FOSSA analysis for job %s | project=%s | cwd=%s | cli=%s", job_id, project, project_dir, cli)

        # Step 1: fossa analyze --json
        # --json prints the project metadata containing the project locator to stdout.
        # We use this to get the exact locator needed for the dependency-count API call later.
        # We try --json first; if the CLI doesn't support it we fall back to plain analyze.
        analyze_cmd = [cli, "analyze", "--project", project, "--json"]

        # Is Maven project?
        if (project_dir / "pom.xml").exists():
            logger.info("Maven project detected for FOSSA analysis.")

        safe_analyze_cmd = " ".join([arg.replace(api_key, "***") for arg in analyze_cmd])
        logger.info("Executing FOSSA command: %s", safe_analyze_cmd)
        logger.debug("CWD: %s | CLI: %s", str(project_dir), cli)

        start_time = time.time()
        analyze = subprocess.run(  # nosec B603  # noqa: S603
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

        # If --json caused a non-zero exit (unsupported flag on this CLI version),
        # retry without --json so the upload still happens.
        if analyze.returncode not in (0, 1) and "--json" in analyze_cmd:
            logger.info("fossa analyze --json not supported on this CLI version; retrying without --json.")
            analyze_cmd_plain = [cli, "analyze", "--project", project]
            analyze = subprocess.run(  # nosec B603  # noqa: S603
                analyze_cmd_plain,
                cwd=project_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=900,
                check=False,
            )
            analyze_output = (analyze.stdout + "\n" + analyze.stderr).strip()
            analyze_lines = self._redact(analyze_output.splitlines(), api_key)
            logger.info("FOSSA analyze (plain) finished with exit code %s", analyze.returncode)

        # Try to extract the project locator from the JSON that --json emits.
        # Format: {"id": "...", "revision": "...", "projectId": "..."}
        fossa_locator: str | None = self._extract_locator(analyze.stdout)
        logger.info("FOSSA project locator: %s", fossa_locator or "(not found in CLI output)")

        # Extract the real dashboard URL from the CLI output
        analysis_url = self._extract_dashboard_url(analyze_output) or fallback_url
        logger.info("FOSSA dashboard URL: %s", analysis_url)

        # Check for authentication failure
        if "401" in analyze_output or "unauthorized" in analyze_output.lower() or "invalid api key" in analyze_output.lower():
            logger.error(
                "FOSSA authentication failure detected | token_present=%s | token_len=%d",
                bool(api_key), len(api_key),
            )
            return FossaScanResult(
                policy_status="UNAVAILABLE",
                scan_mode="authentication_failed",
                real_scan=True,
                analysis_url=analysis_url,
                error_message="FOSSA API authentication failed. Verify your FOSSA_API_KEY.",
                log_lines=["FOSSA authentication failed — verify FOSSA_API_KEY."] + analyze_lines[-15:],
            )

        if analyze.returncode not in (0, 1):
            error_msg = f"FOSSA analysis failed (exit {analyze.returncode}) — CLI execution error, not a policy result."
            logger.error("%s | stdout=%s | stderr=%s", error_msg, analyze.stdout[:500], analyze.stderr[:500])
            return FossaScanResult(
                policy_status="UNAVAILABLE",
                scan_mode="analysis_failed",
                real_scan=True,
                analysis_url=analysis_url,
                error_message=error_msg,
                log_lines=[f"FOSSA CLI failed (exit {analyze.returncode})."] + analyze_lines[-20:],
            )

        # Step 2: fossa test --format json
        test_cmd = [cli, "test", "--project", project, "--format", "json"]
        logger.info("Executing FOSSA test: %s", " ".join(test_cmd))

        start_test_time = time.time()
        test = subprocess.run(  # nosec B603  # noqa: S603
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

        # -------------------------------------------------------------------
        # Fetch the real dependency count from the FOSSA API.
        #
        # WHY: `fossa test --format json` only outputs the *issues* array.
        # It never includes a dependency list, so parsing it always yields
        # total_dependencies = 0.  The correct count lives at:
        #   GET /api/revisions/{locator}/dependencies/count  (returns {count: N})
        # or:
        #   GET /api/revisions/{locator}/dependencies        (returns array)
        # We use the locator captured from `fossa analyze --output` if available.
        # -------------------------------------------------------------------
        api_dep_count = self._fetch_dependency_count(
            host_url=host_url,
            api_key=api_key,
            locator=fossa_locator,
            project=project,
            analysis_url=analysis_url,
        )
        if api_dep_count is not None:
            logger.info(
                "FOSSA API returned dependency count=%d for project %s.",
                api_dep_count, project,
            )
            extracted["total_dependencies"] = api_dep_count
        else:
            logger.info(
                "FOSSA dependency count API unavailable; total_dependencies stays at %d.",
                extracted["total_dependencies"],
            )

        # Exit code 0 = policy passed, exit code 1 = policy violations found (successful scan)
        policy_status = "PASSED" if test.returncode == 0 else "FAILED"
        if test.returncode == 1:
            logger.info(
                "FOSSA test returned exit code 1: policy violations detected | "
                "vulnerabilities=%d | license_issues=%d | denied=%d | flagged=%d | outdated=%d. "
                "This is a successful scan with findings — migration will NOT be marked as failed.",
                extracted["vulnerabilities"],
                extracted["license_issues"],
                extracted["denied_license_issues"],
                extracted["flagged_license_issues"],
                extracted["outdated_count"],
            )
        else:
            logger.info(
                "FOSSA test returned exit code 0: policy passed | "
                "total_dependencies=%d | vulnerabilities=%d | license_issues=%d.",
                extracted["total_dependencies"],
                extracted["vulnerabilities"],
                extracted["license_issues"],
            )

        report = {
            "project": project,
            "policy_status": policy_status,
            "analysis_url": analysis_url,
            "total_dependencies": extracted["total_dependencies"],
            "license_issues": extracted["license_issues"],
            "denied_license_issues": extracted["denied_license_issues"],
            "flagged_license_issues": extracted["flagged_license_issues"],
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

        return FossaScanResult(
            policy_status=policy_status,
            license_issues=extracted["license_issues"],
            denied_license_issues=extracted["denied_license_issues"],
            flagged_license_issues=extracted["flagged_license_issues"],
            vulnerabilities=extracted["vulnerabilities"],
            total_dependencies=extracted["total_dependencies"],
            outdated_dependencies=extracted["outdated_count"],
            scan_mode="real",
            real_scan=True,
            analysis_url=analysis_url,
            # error_message is purely informational — never causes a migration failure
            error_message=(
                None if policy_status == "PASSED"
                else "FOSSA policy check found violations. See the FOSSA dashboard for details."
            ),
            report=report,
            log_lines=[
                "FOSSA analysis completed successfully.",
                f"FOSSA policy status: {policy_status}",
                f"FOSSA dashboard: {analysis_url}",
                f"Total dependencies: {extracted['total_dependencies']}",
                f"Vulnerabilities: {extracted['vulnerabilities']} "
                f"(critical={extracted['vulnerabilities_critical']} "
                f"high={extracted['vulnerabilities_high']} "
                f"medium={extracted['vulnerabilities_medium']} "
                f"low={extracted['vulnerabilities_low']})",
                f"License issues: {extracted['license_issues']} "
                f"(denied={extracted['denied_license_issues']} "
                f"flagged={extracted['flagged_license_issues']})",
                f"Outdated dependencies: {extracted['outdated_count']}",
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
        """Fallback URL constructed from the project slug.

        This is used only when the real URL cannot be extracted from the
        FOSSA CLI output.  The format mirrors what FOSSA uses for custom
        integrations, but the organization‑ID component may differ.
        """
        endpoint = settings.fossa_endpoint.rstrip("/") if settings.fossa_endpoint else "https://app.fossa.com"
        import urllib.parse
        encoded_project = urllib.parse.quote(f"custom+{project}", safe="")
        return f"{endpoint}/projects/{encoded_project}"

    @staticmethod
    def _extract_locator(analyze_stdout: str) -> str | None:
        """Parse the project locator from ``fossa analyze --json`` metadata JSON stdout.

        When called with ``--json``, the CLI writes a single JSON line to
        stdout of the form::

            {"id": "custom+12345/project-name$rev", "revision": "<sha>", ...}

        We check for keys "locator", "id", or "projectId" containing the locator.
        """
        if not analyze_stdout:
            return None
        # Try every line for a JSON object
        for line in analyze_stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    val = obj.get("locator") or obj.get("id") or obj.get("projectId")
                    if val:
                        return str(val)
            except json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def _extract_project_id_from_url(url: str | None) -> str | None:
        """Extract the project ID (e.g. custom+1234/my-project) from the FOSSA dashboard URL.

        Example:
            https://app.fossa.com/projects/custom%2B12345%2Fmy-project
            -> custom+12345/my-project
        """
        if not url:
            return None
        try:
            parts = url.split("/projects/")
            if len(parts) < 2:
                return None
            project_part = parts[1].split("?")[0].split("#")[0]
            import urllib.parse
            decoded = urllib.parse.unquote(project_part)
            return decoded
        except Exception:  # noqa: BLE001
            return None

    def _fetch_locator_from_api(self, host_url: str, api_key: str, project_id: str) -> str | None:
        """Query FOSSA revisions API to get the latest locator for a given project ID."""
        import urllib.error
        import urllib.parse
        import urllib.request

        encoded = urllib.parse.quote(project_id, safe="")
        url = f"{host_url}/api/revisions?projectId={encoded}"
        logger.info("Fetching FOSSA revisions to resolve locator: %s", url)
        try:
            req = urllib.request.Request(  # nosec B310  # noqa: S310
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310  # noqa: S310
                raw = resp.read().decode("utf-8", errors="replace")

            data = json.loads(raw)
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                if isinstance(first, dict):
                    val = first.get("locator") or first.get("id")
                    if val:
                        return str(val)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.info("Failed to fetch FOSSA revisions from API: %s", exc)
            return None

    def _fetch_dependency_count(
        self,
        *,
        host_url: str,
        api_key: str,
        locator: str | None,
        project: str,
        analysis_url: str | None = None,
    ) -> int | None:
        """Return the total number of dependencies for this project revision.

        Calls ``GET /api/revisions/{encoded_locator}/dependencies`` on the FOSSA
        REST API.  If the response body is a list, returns its length.  If it is a
        dict with a ``count`` key, returns that value.  Returns ``None`` on any
        error so the caller can fall back gracefully.

        Only the *count* is fetched — no large payload is stored or surfaced.
        The call is made with a short timeout (10 s) so it never blocks the scan.
        """
        import urllib.error
        import urllib.parse
        import urllib.request

        resolved_locator = locator
        if not resolved_locator and analysis_url:
            project_id = self._extract_project_id_from_url(analysis_url)
            if project_id:
                resolved_locator = self._fetch_locator_from_api(host_url, api_key, project_id)

        # Fallback using project slug
        effective_locator = resolved_locator or f"custom+1/{project}"
        encoded = urllib.parse.quote(effective_locator, safe="")
        url = f"{host_url}/api/revisions/{encoded}/dependencies"

        logger.info("Fetching FOSSA dependency count from: %s", url)
        try:
            req = urllib.request.Request(  # nosec B310  # noqa: S310
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310  # noqa: S310
                raw = resp.read().decode("utf-8", errors="replace")

            data = json.loads(raw)

            # API may return a list of dependency objects or a dict {count: N}
            if isinstance(data, list):
                return len(data)
            if isinstance(data, dict):
                count = data.get("count") or data.get("total") or data.get("length")
                if count is not None:
                    return int(count)
                # Some responses wrap the list in a key
                for key in ("dependencies", "items", "results", "data"):
                    if isinstance(data.get(key), list):
                        return len(data[key])

            logger.debug("FOSSA dependency count API response shape unexpected: %s", str(data)[:200])
            return None

        except urllib.error.HTTPError as exc:
            logger.info(
                "FOSSA dependency count API returned HTTP %s for locator %r — "
                "falling back to None. (This is non-fatal.)",
                exc.code, effective_locator,
            )
            return None
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "FOSSA dependency count API call failed (%s) — falling back to None. (Non-fatal.)",
                exc,
            )
            return None

    @staticmethod
    def _extract_dashboard_url(cli_output: str) -> str | None:
        """Extract the real FOSSA dashboard URL from `fossa analyze` stdout/stderr.

        The FOSSA CLI prints a line similar to one of these patterns:
            - "View it in FOSSA at: https://app.fossa.com/projects/..."
            - "Project is available at https://app.fossa.com/projects/..."
            - Any URL containing 'app.fossa.com/projects' or '<endpoint>/projects'

        We prefer the URL the CLI itself reports because it contains the correct
        organization‑ID prefix (e.g. ``custom+12345``) that cannot be guessed locally.
        """
        if not cli_output:
            return None
        # Match any https URL that contains '/projects/' — these are FOSSA project URLs
        url_pattern = re.compile(
            r'https?://[\w.\-]*/projects/[^\s\"\']+'  # URL ending at whitespace/quote
        )
        for line in cli_output.splitlines():
            m = url_pattern.search(line)
            if m:
                url = m.group(0).rstrip(".,;)")  # strip trailing punctuation
                logger.info("Extracted FOSSA dashboard URL from CLI output: %s", url)
                return url
        return None

    @staticmethod
    def _redact(lines: list[str], secret: str) -> list[str]:
        if not secret:
            return [line for line in lines if line.strip()]
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
        """Extract structured dependency, license, vulnerability, and outdated package data.

        The FOSSA CLI (``fossa test --format json``) returns a JSON object whose
        top‑level key is ``issues``.  Each element in that array has an
        ``issue_type`` field (not ``type``) with values such as::

            "policy_conflict"          – license denied by policy
            "unlicensed_dependency"    – dependency has no detected license
            "denied_license"           – license explicitly denied
            "flagged_license"          – license flagged for review
            "vulnerability"            – CVE / security advisory
            "outdated_dependency"      – newer version available

        The ``revisionId`` field contains the package locator (e.g.
        ``custom+pip+requests$2.31.0``).  Severity for vulnerabilities is in
        the nested ``cvssScore`` or ``severity`` field.

        We also handle the older flat format where the top‑level key is ``graph``
        and each node may have a ``type`` field instead of ``issue_type``.
        """
        result: dict[str, Any] = {
            "total_dependencies": 0,
            "license_issues": 0,
            "denied_license_issues": 0,
            "flagged_license_issues": 0,
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
            """Recursively coerce any FOSSA JSON value to a plain string."""
            if val is None:
                return ""
            if isinstance(val, str):
                return val
            if isinstance(val, dict):
                # FOSSA sometimes wraps a string in a dict with one of these keys
                for key in ("text", "value", "name", "label", "summary", "title", "message"):
                    if key in val and val[key] is not None:
                        return safe_text(val[key])
                try:
                    logger.debug("Unknown dict structure in FOSSA JSON field: %s", val)
                    return json.dumps(val)
                except Exception:  # noqa: BLE001
                    return str(val)
            if isinstance(val, list):
                return ", ".join(safe_text(v) for v in val if v is not None)
            return str(val)

        licenses_map: dict[str, dict[str, Any]] = {}
        vulnerabilities_list: list[dict[str, Any]] = []
        outdated_list: list[dict[str, Any]] = []
        dependencies_map: dict[str, dict[str, Any]] = {}

        # ------------------------------------------------------------------ #
        # Parse the top‑level issue list
        # ------------------------------------------------------------------ #
        issues: list[Any] = []
        if isinstance(payload, list):
            # Some CLI versions emit a bare array
            issues = payload
        elif isinstance(payload, dict):
            # Prefer "issues"; fall back to "graph" (older CLI versions)
            raw = payload.get("issues") or payload.get("graph") or []
            if isinstance(raw, list):
                issues = raw

        for iss in issues:
            if not isinstance(iss, dict):
                continue

            # ``issue_type`` is the canonical field in recent FOSSA CLI JSON.
            # Older formats may use ``type`` instead.
            raw_issue_type = safe_text(
                iss.get("issue_type") or iss.get("issueType") or iss.get("type") or ""
            ).lower()

            # Package / locator
            pkg = safe_text(
                iss.get("revisionId")
                or iss.get("revision_id")
                or iss.get("package")
                or iss.get("dependency")
                or iss.get("locator")
                or "Unknown"
            )
            # Strip the locator prefix (e.g. "custom+pip+requests$2.31.0" → "requests$2.31.0")
            if "+" in pkg:
                pkg = pkg.split("+", 2)[-1]

            title = safe_text(
                iss.get("title")
                or iss.get("summary")
                or iss.get("rule")
                or raw_issue_type.replace("_", " ").title()
                or "Issue"
            )

            # ---- License issues ------------------------------------------ #
            is_license_issue = (
                "license" in raw_issue_type
                or raw_issue_type in ("policy_conflict", "unlicensed_dependency")
            )
            if is_license_issue:
                result["license_issues"] += 1
                if "denied" in raw_issue_type:
                    result["denied_license_issues"] += 1
                if "flagged" in raw_issue_type:
                    result["flagged_license_issues"] += 1

                # Accumulate unique license entries
                lic_name = safe_text(
                    iss.get("license")
                    or iss.get("licenseName")
                    or iss.get("license_name")
                    or title
                )
                if lic_name not in licenses_map:
                    licenses_map[lic_name] = {
                        "name": lic_name,
                        "issue_type": raw_issue_type,
                        "risk": "HIGH" if "denied" in raw_issue_type else "MEDIUM",
                        "affected_packages": [pkg] if pkg != "Unknown" else [],
                        "count": 1,
                    }
                else:
                    if pkg != "Unknown" and pkg not in licenses_map[lic_name]["affected_packages"]:
                        licenses_map[lic_name]["affected_packages"].append(pkg)
                    licenses_map[lic_name]["count"] += 1
                continue

            # ---- Vulnerability issues ------------------------------------ #
            is_vuln = (
                raw_issue_type in ("vulnerability", "cve")
                or "vuln" in raw_issue_type
                or "cve" in title.lower()
            )
            if is_vuln:
                result["vulnerabilities"] += 1

                # Severity: may be a nested dict or a plain string
                sev_raw = iss.get("severity") or iss.get("cvss_severity") or ""
                if isinstance(sev_raw, dict):
                    sev_raw = sev_raw.get("severity") or sev_raw.get("rating") or ""
                sev = safe_text(sev_raw).upper()

                if "CRIT" in sev:
                    result["vulnerabilities_critical"] += 1
                elif "HIGH" in sev:
                    result["vulnerabilities_high"] += 1
                elif "MED" in sev:
                    result["vulnerabilities_medium"] += 1
                else:
                    result["vulnerabilities_low"] += 1

                cve_id = safe_text(iss.get("cve") or iss.get("cveId") or iss.get("cve_id") or "")
                vulnerabilities_list.append({
                    "id": cve_id or safe_text(iss.get("id") or title),
                    "severity": sev or "UNKNOWN",
                    "package": pkg,
                    "installed_version": safe_text(
                        iss.get("version") or iss.get("installed_version") or "N/A"
                    ),
                    "fixed_version": safe_text(
                        iss.get("fixed_version") or iss.get("fix") or "N/A"
                    ),
                    "cve": cve_id or "N/A",
                    "description": safe_text(iss.get("description") or title),
                    "reference": safe_text(iss.get("url") or iss.get("reference")) or None,
                })
                continue

            # ---- Outdated dependency ------------------------------------- #
            if "outdated" in raw_issue_type:
                outdated_list.append({
                    "package": pkg,
                    "current_version": safe_text(
                        iss.get("version") or iss.get("installed_version") or "N/A"
                    ),
                    "latest_version": safe_text(
                        iss.get("latest_version") or iss.get("latestVersion") or "Latest"
                    ),
                })
                continue

            # ---- Unknown issue type -------------------------------------- #
            logger.debug(
                "Unrecognised FOSSA issue_type %r for package %r — treating as license issue.",
                raw_issue_type, pkg,
            )
            result["license_issues"] += 1

        # ------------------------------------------------------------------ #
        # Parse the dependency graph (used for total_dependencies count)
        # ------------------------------------------------------------------ #
        dep_sources: list[Any] = []
        if isinstance(payload, dict):
            raw_deps = payload.get("dependencies") or payload.get("modules") or []
            if isinstance(raw_deps, list):
                dep_sources = raw_deps

        for dep in dep_sources:
            if not isinstance(dep, dict):
                continue
            pkg_name = safe_text(
                dep.get("name")
                or dep.get("package")
                or dep.get("locator")
                or dep.get("revisionId")
                or "Unknown"
            )
            if "+" in pkg_name:
                pkg_name = pkg_name.split("+", 2)[-1]
            version = safe_text(dep.get("version") or dep.get("revision") or "N/A")
            lic = safe_text(dep.get("license") or dep.get("licenses") or "Unknown")

            dependencies_map[pkg_name] = {
                "package": pkg_name,
                "version": version,
                "license": lic,
                "risk": "LOW" if lic not in ("Unknown", "") else "MEDIUM",
            }

            if dep.get("outdated") or dep.get("latest_version") or dep.get("latestVersion"):
                if not any(o["package"] == pkg_name for o in outdated_list):
                    outdated_list.append({
                        "package": pkg_name,
                        "current_version": version,
                        "latest_version": safe_text(
                            dep.get("latest_version") or dep.get("latestVersion") or "Latest"
                        ),
                    })

        result["dependencies_list"] = list(dependencies_map.values())
        result["licenses_list"] = list(licenses_map.values())
        result["vulnerabilities_list"] = vulnerabilities_list
        result["outdated_list"] = outdated_list
        result["total_dependencies"] = len(result["dependencies_list"])
        result["outdated_count"] = len(result["outdated_list"])

        return result
