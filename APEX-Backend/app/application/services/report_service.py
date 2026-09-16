"""Builds the frontend-facing MigrationJobSummary / MigrationResult payloads.

The migration's internal state lives in ``migration-report.json`` (see
StartMigrationUseCase). These builders translate that state into the exact shapes
the Result page expects, filling out-of-scope fields (sonar/fossa/tests/diffs)
with safe zero/null defaults so the UI renders without crashing.
"""

from __future__ import annotations

from typing import Any
from app.application.services.file_diff_service import FileDiffService
from app.infrastructure.github.repo_creator import RepoCreator

_diff_service = FileDiffService()


def _resolve_target_repo(report: dict[str, Any]) -> str | None:
    target_repo = report.get("targetRepo") or report.get("target_repo")
    if target_repo:
        return target_repo
    dest = report.get("destination") or {}
    if dest.get("mode") == "LOCAL_FOLDER":
        return dest.get("targetLocalDir") or "Local Workspace"
    if dest.get("mode") == "EXISTING_REPO_BRANCH":
        src = report.get("sourceRepoUrl") or ""
        branch = dest.get("targetBranch") or "migration"
        return f"{src.rstrip('/').removesuffix('.git')}/tree/{branch}" if src else branch
    if dest.get("targetRepoName"):
        target_owner = dest.get("targetOwner") or "JavaAPEX"
        target_host = dest.get("targetHost") or "github.com"
        clean_name = RepoCreator.clean_repo_name(dest.get("targetRepoName"))
        return f"https://{target_host}/{target_owner}/{clean_name}"
    return None


def _build_issues(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive detailed issues fixed/found from real migration evidence."""
    explicit_issues = report.get("issues")
    if explicit_issues and isinstance(explicit_issues, list) and len(explicit_issues) > 0:
        return explicit_issues

    issues: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    # 1. AST Rule Executions
    rule_execs = report.get("ruleExecutions") or []
    for idx, rule in enumerate(rule_execs):
        file_p = rule.get("filePath") or rule.get("file") or rule.get("component") or "src"
        rule_id = rule.get("ruleId") or f"rule-{idx + 1}"
        msg = rule.get("message") or rule.get("description") or f"Transformed {rule_id}"
        cat = rule.get("category") or "Code Transformation"
        key = f"{file_p}:{msg}"
        if key not in seen_keys:
            seen_keys.add(key)
            issues.append({
                "id": f"issue-ast-{idx + 1}",
                "severity": "info",
                "status": "fixed",
                "category": cat,
                "message": msg,
                "file_path": file_p,
                "line_number": rule.get("lineNumber") or rule.get("line") or 1,
                "column": None,
                "code_snippet": rule.get("snippet"),
                "suggested_fix": rule.get("fix"),
                "fixed_at": report.get("completedAt") or report.get("startedAt"),
                "conversion_type": rule.get("conversionType") or "java_version",
            })

    # 2. Import Changes
    import_changes = report.get("importChanges") or []
    for idx, ic in enumerate(import_changes):
        file_p = ic.get("file") or ""
        added = ic.get("added") or []
        removed = ic.get("removed") or []
        if added or removed:
            desc = f"Refactored package namespaces/imports (replaced {len(removed)} old imports with {len(added)} modern imports)"
            key = f"{file_p}:{desc}"
            if key not in seen_keys:
                seen_keys.add(key)
                issues.append({
                    "id": f"issue-import-{idx + 1}",
                    "severity": "info",
                    "status": "fixed",
                    "category": "Namespace Migration",
                    "message": desc,
                    "file_path": file_p,
                    "line_number": 1,
                    "column": None,
                    "code_snippet": None,
                    "suggested_fix": None,
                    "fixed_at": report.get("completedAt"),
                    "conversion_type": "jakarta" if any("jakarta" in str(a) for a in added) else "java_version",
                })

    # 3. Dependency Upgrades
    dep_upgrades = report.get("dependencyUpgrades") or report.get("dependency_upgrades") or []
    for idx, dep in enumerate(dep_upgrades):
        if str(dep.get("status", "")).upper() == "UPGRADED":
            gid = dep.get("groupId") or dep.get("group_id") or ""
            aid = dep.get("artifactId") or dep.get("artifact_id") or ""
            src_v = dep.get("sourceVersion") or dep.get("current_version") or "managed"
            target_v = dep.get("resolvedTargetVersion") or dep.get("new_version") or "updated"
            desc = f"Upgraded outdated dependency {gid}:{aid} from {src_v} to {target_v}"
            key = f"pom.xml:{desc}"
            if key not in seen_keys:
                seen_keys.add(key)
                issues.append({
                    "id": f"issue-dep-{idx + 1}",
                    "severity": "info",
                    "status": "fixed",
                    "category": "Dependency Modernization",
                    "message": desc,
                    "file_path": "pom.xml" if report.get("buildTool", "").lower() == "maven" else "build.gradle",
                    "line_number": 1,
                    "column": None,
                    "code_snippet": None,
                    "suggested_fix": None,
                    "fixed_at": report.get("completedAt"),
                    "conversion_type": "dependency_upgrade",
                })

    # 4. Build Modernizations
    build_mods = report.get("buildModernization") or []
    for idx, bmod in enumerate(build_mods):
        desc = str(bmod)
        key = f"build:{desc}"
        if key not in seen_keys:
            seen_keys.add(key)
            issues.append({
                "id": f"issue-build-{idx + 1}",
                "severity": "info",
                "status": "fixed",
                "category": "Build Modernization",
                "message": desc,
                "file_path": "pom.xml" if report.get("buildTool", "").lower() == "maven" else "build.gradle",
                "line_number": 1,
                "column": None,
                "code_snippet": None,
                "suggested_fix": None,
                "fixed_at": report.get("completedAt"),
                "conversion_type": "build_tool",
            })

    return issues


CANONICAL_STAGES = [
    {
        "id": "code-version-update",
        "name": "1. Code version update",
        "description": "Analyzing and updating source code to target version",
        "progress": 16,
    },
    {
        "id": "dependency-updates",
        "name": "2. Dependencies updates",
        "description": "Updating libraries and third-party dependencies",
        "progress": 35,
    },
    {
        "id": "code-transformation",
        "name": "3. Code fix & code transformation",
        "description": "Applying automated fixes and transforming code",
        "progress": 60,
    },
    {
        "id": "quality-check",
        "name": "4. Quality check (Sonar, FOSSA, Unit check - JUnit)",
        "description": "Running static analysis and unit tests",
        "progress": 80,
    },
    {
        "id": "code-depreciation",
        "name": "5. Code Deprecation",
        "description": "Analyzing and reporting deprecated code",
        "progress": 90,
    },
    {
        "id": "migration-report",
        "name": "6. Generating migration report",
        "description": "Compiling results and generating final report",
        "progress": 100,
    },
]


def _build_stages(report: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    raw_status = (report.get("status") or "queued").lower()
    raw_stage = (report.get("currentStage") or "").lower()
    raw_step = report.get("currentStep") or ""
    progress_pct = int(report.get("progressPercent") or report.get("progress_percent") or 0)

    # Determine active stage id
    active_stage_id = "code-version-update"
    if raw_stage:
        active_stage_id = raw_stage
    elif progress_pct >= 92 or "report" in raw_step.lower() or raw_status in ("completed", "success"):
        active_stage_id = "migration-report"
    elif progress_pct >= 82 or "deprecat" in raw_step.lower() or "publish" in raw_step.lower():
        active_stage_id = "code-depreciation"
    elif progress_pct >= 62 or "validat" in raw_step.lower() or "quality" in raw_step.lower() or "test" in raw_step.lower():
        active_stage_id = "quality-check"
    elif progress_pct >= 38 or "migrat" in raw_step.lower() or "transform" in raw_step.lower():
        active_stage_id = "code-transformation"
    elif progress_pct >= 18 or "depend" in raw_step.lower():
        active_stage_id = "dependency-updates"
    else:
        active_stage_id = "code-version-update"

    stage_ids = [s["id"] for s in CANONICAL_STAGES]
    active_idx = stage_ids.index(active_stage_id) if active_stage_id in stage_ids else 0

    stages: list[dict[str, Any]] = []
    for idx, stage in enumerate(CANONICAL_STAGES):
        sid = stage["id"]
        sname = stage["name"]
        tprog = stage["progress"]

        if raw_status in ("completed", "success") or progress_pct >= 100:
            stage_status = "completed"
            stage_prog = tprog
        elif raw_status in ("failed", "error"):
            if idx < active_idx:
                stage_status = "completed"
                stage_prog = tprog
            elif idx == active_idx:
                stage_status = "failed"
                stage_prog = max(progress_pct, 1)
            else:
                stage_status = "pending"
                stage_prog = 0
        elif raw_status == "queued":
            stage_status = "pending"
            stage_prog = 0
        else:
            # Running / in-progress
            if idx < active_idx:
                stage_status = "completed"
                stage_prog = tprog
            elif idx == active_idx:
                stage_status = "in_progress"
                stage_prog = progress_pct
            else:
                stage_status = "pending"
                stage_prog = 0

        stages.append({
            "id": sid,
            "name": sname,
            "description": stage["description"],
            "status": stage_status,
            "progress": stage_prog,
        })

    active_stage_name = CANONICAL_STAGES[active_idx]["name"]
    return active_stage_id, active_stage_name, stages


def _core(report: dict[str, Any]) -> dict[str, Any]:
    """Fields shared by summary + detail."""
    job_id = report.get("jobId", "")
    modified_files = report.get("modifiedFiles") or report.get("modified_files") or []
    files_modified_count = int(report.get("filesModified") or report.get("files_modified") or len(modified_files))

    if files_modified_count == 0 and job_id:
        file_diffs = _diff_service.get_changed_files_summary(job_id, report)
        if file_diffs:
            files_modified_count = len(file_diffs)

    issues = _build_issues(report)
    issues_fixed = int(
        report.get("issuesFixed")
        or report.get("issues_fixed")
        or len(issues)
    )

    dep_upgrades = report.get("dependencyUpgrades") or report.get("dependency_upgrades") or []
    dep_count = int(report.get("dependencyCount") or len(dep_upgrades))
    active_stage_id, active_stage_name, stages = _build_stages(report)

    return {
        "job_id": job_id,
        "status": report.get("status", "queued"),
        "source_repo": report.get("sourceRepoUrl") or report.get("source_repo") or "",
        "target_repo": _resolve_target_repo(report),
        "source_java_version": str(report.get("sourceJavaVersion") or report.get("source_java_version") or ""),
        "target_java_version": str(report.get("targetJavaVersion") or report.get("target_java_version") or ""),
        "effective_target_java_version": str(
            report.get("effectiveTargetJavaVersion")
            or report.get("targetJavaVersion")
            or ""
        ),
        "conversion_types": report.get("conversionTypes") or report.get("conversion_types") or [],
        "started_at": report.get("startedAt") or report.get("started_at") or "",
        "worker_started_at": report.get("startedAt") or report.get("started_at"),
        "completed_at": report.get("completedAt") or report.get("completed_at"),
        "progress_percent": int(report.get("progressPercent") or report.get("progress_percent") or 0),
        "current_step": report.get("currentStep") or report.get("current_step") or "",
        "current_stage": active_stage_id,
        "current_stage_name": active_stage_name,
        "stages": stages,
        "files_modified": files_modified_count,
        "issues_fixed": issues_fixed,
        "error_message": report.get("errorMessage") or report.get("error_message"),
        "dependency_count": dep_count,
        # --- migration engine report fields ---
        "recipes_executed": report.get("recipes") or [],
        "recipe_selection_reasons": report.get("recipeSelection") or [],
        "build_modernization": report.get("buildModernization") or [],
        "dependency_upgrades": dep_upgrades,
        "dependencies": dep_upgrades,
        "used_fallback": bool(report.get("usedFallback")),
        "already_compatible": bool(report.get("alreadyCompatible")),
        "build_status": report.get("buildStatus"),
        "build_success": report.get("buildSuccess"),
        "migration_summary": report.get("migrationSummary") or "",
        "retry_attempts": report.get("retryAttempts") or [],
        "migration_phases": report.get("migrationPhases") or [],
        "skipped_recipes": report.get("skippedRecipes") or [],
        "spring_source_framework": report.get("springSourceFramework") or "",
        "spring_target_framework": report.get("springTargetFramework") or "",
        "spring_boot_version_before": report.get("springBootVersionBefore"),
        "spring_boot_version_after": report.get("springBootVersionAfter"),
        "spring_conversion_requested": bool(report.get("springConversionRequested")),
        "spring_conversion_supported": report.get("springConversionSupported"),
        "spring_conversion_note": report.get("springConversionNote"),
    }


# All the numeric/nullable analysis fields we don't produce — zeroed defaults.
_ZERO_ANALYSIS = {
    "issues_fixed": 0,
    "api_endpoints_validated": 0,
    "api_endpoints_working": 0,
    "tests_run": 0,
    "tests_passed": 0,
    "tests_failed": 0,
    "sonar_quality_gate": None,
    "sonar_bugs": 0,
    "sonar_vulnerabilities": 0,
    "sonar_code_smells": 0,
    "sonar_coverage": 0,
    "sonar_duplications": 0,
    "sonar_security_hotspots": 0,
    "sonar_scan_mode": None,
    "sonar_real_scan": False,
    "sonar_analysis_url": None,
    "sonar_error_message": None,
    "fossa_policy_status": None,
    "fossa_total_dependencies": 0,
    "fossa_license_issues": 0,
    "fossa_denied_license_issues": 0,
    "fossa_flagged_license_issues": 0,
    "fossa_vulnerabilities": 0,
    "fossa_outdated_dependencies": 0,
    "fossa_scan_mode": None,
    "fossa_real_scan": False,
    "fossa_analysis_url": None,
    "fossa_error_message": None,
    "total_errors": 0,
    "total_warnings": 0,
    "errors_fixed": 0,
    "warnings_fixed": 0,
}


def _analysis(report: dict[str, Any]) -> dict[str, Any]:
    """Overlay produced analysis fields on top of stable UI defaults."""
    values = dict(_ZERO_ANALYSIS)
    for key in values:
        if key in report:
            values[key] = report.get(key)
    return values


def build_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Shape a `MigrationJobSummary`."""
    core = _core(report)
    log_lines = report.get("logLines") or []
    issues = _build_issues(report)
    return {
        **core,
        **_analysis(report),
        "issues_fixed": core["issues_fixed"],
        "api_endpoint_count": 0,
        "issue_count": len(issues),
        "log_entry_count": len(log_lines),
        "file_diff_count": core["files_modified"],
        "has_test_pipeline": bool(report.get("test_pipeline")),
        "has_sonar_report": bool(report.get("sonar_report")),
        "has_fossa_report": bool(report.get("fossa_report")),
        "sonar_report": report.get("sonar_report"),
        "has_testcase_doc": False,
        "has_clone_path": True,
    }


def build_result(report: dict[str, Any]) -> dict[str, Any]:
    """Shape a `MigrationResult` (superset of the summary)."""
    core = _core(report)
    log_lines = report.get("logLines") or []
    job_id = report.get("jobId", "")
    issues = _build_issues(report)
    file_diffs = _diff_service.get_changed_files_summary(job_id, report) if job_id else []

    # Update files_modified if diffs discovered additional files
    if file_diffs and core["files_modified"] < len(file_diffs):
        core["files_modified"] = len(file_diffs)

    return {
        **core,
        **_analysis(report),
        "issues_fixed": core["issues_fixed"],
        "migration_log": log_lines,
        "issues": issues,
        "test_insights": report.get("test_insights") or [],
        "test_summary": report.get("test_summary"),
        "test_llm_model": report.get("test_llm_model"),
        "sonar_report": report.get("sonar_report"),
        "test_pipeline": report.get("test_pipeline"),
        # --- full migration report detail ---
        "modified_files": report.get("modifiedFiles") or [f["relativePath"] for f in file_diffs],
        "file_diffs": file_diffs,
        "import_changes": report.get("importChanges") or [],
        "source_changes": report.get("sourceChanges") or [],
    }


def build_logs(report: dict[str, Any]) -> dict[str, Any]:
    """Shape the `/logs` response."""
    return {
        "job_id": report.get("jobId", ""),
        "logs": report.get("logLines") or [],
    }


def build_fossa(report: dict[str, Any]) -> dict[str, Any]:
    """Shape the `/fossa` response."""
    return {
        "job_id": report.get("jobId", ""),
        "fossa": report.get("fossa_report"),
    }
