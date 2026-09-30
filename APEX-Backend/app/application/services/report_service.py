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

    # 5. UI Transformations (JSP / JSF Modernization)
    ui_trans = report.get("uiTransformations") or []
    for idx, ut in enumerate(ui_trans):
        src_file = ut.get("sourceFile") or ut.get("file") or ""
        target_file = ut.get("targetSourceFile") or ut.get("targetFile") or ""
        cat = ut.get("category") or "Frontend Modernization"
        desc = f"Modernized legacy template {src_file} -> {target_file}" if target_file else f"Modernized legacy template {src_file}"
        key = f"{src_file}:{desc}"
        if key not in seen_keys:
            seen_keys.add(key)
            issues.append({
                "id": f"issue-ui-{idx + 1}",
                "severity": "info",
                "status": "fixed",
                "category": cat,
                "message": desc,
                "file_path": src_file,
                "line_number": 1,
                "column": None,
                "code_snippet": None,
                "suggested_fix": f"Converted to {target_file}" if target_file else "Migrated template",
                "fixed_at": report.get("completedAt") or report.get("startedAt"),
                "conversion_type": "ui_transformation",
            })

    # 6. Source Code Changes (Java modernization / refactoring)
    source_changes = report.get("sourceChanges") or []
    for idx, sc in enumerate(source_changes):
        file_p = sc.get("file") or sc.get("file_path") or ""
        lines_c = sc.get("lines_changed") or 0
        desc = f"Modernized Java source code ({lines_c} lines modified)" if lines_c else "Modernized Java source code"
        key = f"{file_p}:{desc}"
        if key not in seen_keys:
            seen_keys.add(key)
            issues.append({
                "id": f"issue-src-{idx + 1}",
                "severity": "info",
                "status": "fixed",
                "category": "Java Modernization",
                "message": desc,
                "file_path": file_p,
                "line_number": 1,
                "column": None,
                "code_snippet": None,
                "suggested_fix": "Refactored Java source code for target version compatibility",
                "fixed_at": report.get("completedAt") or report.get("startedAt"),
                "conversion_type": "java_version",
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
    framework_migrations = []

    jsp_migrated = report.get("jspFilesMigrated")
    jsf_migrated = report.get("jsfFilesMigrated")

    ui_trans = report.get("uiTransformations") or []
    if ui_trans:
        jsp_t_count = sum(1 for t in ui_trans if t.get("category", "").startswith("JSP") or (t.get("sourceFile") or t.get("file") or "").lower().endswith((".jsp", ".jspf", ".jspx")))
        jsf_t_count = sum(1 for t in ui_trans if t.get("category", "").startswith("JSF") or (t.get("sourceFile") or t.get("file") or "").lower().endswith((".jsf", ".xhtml")))
        if jsp_t_count > 0 and (jsp_migrated is None or jsp_migrated == 0):
            jsp_migrated = jsp_t_count
        if jsf_t_count > 0 and (jsf_migrated is None or jsf_migrated == 0):
            jsf_migrated = jsf_t_count

    if jsp_migrated is not None and jsp_migrated > 0:
        framework_migrations.append({
            "source_framework": "JSP",
            "target_framework": report.get("jspFrontendFramework") or "Modern",
            "files_migrated": jsp_migrated
        })

    if jsf_migrated is not None and jsf_migrated > 0:
        framework_migrations.append({
            "source_framework": "JSF",
            "target_framework": report.get("jsfFrontendFramework") or "Modern",
            "files_migrated": jsf_migrated
        })

    job_id = report.get("jobId", "")
    modified_files = report.get("modifiedFiles") or report.get("modified_files") or []
    files_modified_count = int(report.get("filesModified") or report.get("files_modified") or len(modified_files))

    if job_id:
        file_diffs = _diff_service.get_changed_files_summary(job_id, report)
        if file_diffs and (files_modified_count < len(file_diffs) or files_modified_count == 0):
            files_modified_count = len(file_diffs)

    issues = _build_issues(report)
    issues_fixed = max(
        int(report.get("issuesFixed") or report.get("issues_fixed") or 0),
        len(issues),
    )

    trans_details = build_report_details(report, "transformations")
    transformations_count = int(trans_details.get("total", 0))

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
        "transformations_count": transformations_count,
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
        "framework_migrations": framework_migrations,
        "jsp_files_migrated": jsp_migrated,
        "jsf_files_migrated": jsf_migrated,
        "jsp_frontend_framework": report.get("jspFrontendFramework"),
        "jsf_frontend_framework": report.get("jsfFrontendFramework"),
        "ui_transformations": ui_trans,
        "uiTransformations": ui_trans,
        "spring_conversion_note": report.get("springConversionNote"),
        "run_sonar": bool(report.get("run_sonar") if "run_sonar" in report else (report.get("runSonar") if "runSonar" in report else False)),
        "run_fossa": bool(report.get("run_fossa") if "run_fossa" in report else (report.get("runFossa") if "runFossa" in report else False)),
        "run_tests": bool(report.get("run_tests") if "run_tests" in report else (report.get("runTests") if "runTests" in report else False)),
        "run_functional_tests": bool(
            report.get("run_functional_tests")
            if "run_functional_tests" in report
            else (report.get("runFunctionalTests") if "runFunctionalTests" in report else True)
        ),
        "runSonar": bool(report.get("runSonar") if "runSonar" in report else (report.get("run_sonar") if "run_sonar" in report else False)),
        "runFossa": bool(report.get("runFossa") if "runFossa" in report else (report.get("run_fossa") if "run_fossa" in report else False)),
        "runTests": bool(report.get("runTests") if "runTests" in report else (report.get("run_tests") if "run_tests" in report else False)),
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
    run_sonar = core["run_sonar"]
    run_fossa = core["run_fossa"]
    run_tests = core["run_tests"]
    return {
        **core,
        **_analysis(report),
        "issues_fixed": core["issues_fixed"],
        "api_endpoint_count": 0,
        "issue_count": len(issues),
        "log_entry_count": len(log_lines),
        "file_diff_count": core["files_modified"],
        "has_test_pipeline": bool(report.get("test_pipeline")) if run_tests else False,
        "has_sonar_report": bool(report.get("sonar_report")) if run_sonar else False,
        "has_fossa_report": bool(report.get("fossa_report")) if run_fossa else False,
        "sonar_report": report.get("sonar_report") if run_sonar else None,
        "has_testcase_doc": False,
        "has_clone_path": True,
        "modified_files": report.get("modifiedFiles") or [],
        "uiTransformations": report.get("uiTransformations") or [],
    }


def build_result(report: dict[str, Any]) -> dict[str, Any]:
    """Shape a `MigrationResult` (superset of the summary)."""
    core = _core(report)
    log_lines = report.get("logLines") or []
    job_id = report.get("jobId", "")
    issues = _build_issues(report)
    file_diffs = _diff_service.get_changed_files_summary(job_id, report) if job_id else []
    run_sonar = core["run_sonar"]
    run_fossa = core["run_fossa"]
    run_tests = core["run_tests"]

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

        "test_insights": (report.get("test_insights") or []) if run_tests else [],
        "test_summary": report.get("test_summary") if run_tests else None,
        "test_llm_model": report.get("test_llm_model") if run_tests else None,
        "sonar_report": report.get("sonar_report") if run_sonar else None,
        "fossa_report": report.get("fossa_report") if run_fossa else None,
        "test_pipeline": report.get("test_pipeline") if run_tests else None,
        # --- full migration report detail ---
        "modified_files": report.get("modifiedFiles") or [f["relativePath"] for f in file_diffs],
        "file_diffs": file_diffs,
        "import_changes": report.get("importChanges") or [],
        "source_changes": report.get("sourceChanges") or [],
        "uiTransformations": report.get("uiTransformations") or [],
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


def build_report_details(report: dict[str, Any], detail_type: str) -> dict[str, Any]:
    """Retrieve detailed records for a specific summary category from existing migration results."""
    job_id = report.get("jobId") or report.get("job_id") or ""
    dtype = (detail_type or "files").lower().strip()

    if dtype in ("files", "files_modified"):
        file_diffs = _diff_service.get_changed_files_summary(job_id, report) if job_id else []
        modified_files = report.get("modifiedFiles") or report.get("modified_files") or []

        items: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        for fd in file_diffs:
            p = fd.get("relativePath") or fd.get("fileName") or ""
            if p and p not in seen_paths:
                seen_paths.add(p)
                ctype = str(fd.get("changeType") or "MODIFIED").upper()
                status = "Added" if ctype == "ADDED" else ("Removed" if ctype == "DELETED" else "Modified")
                additions = int(fd.get("addedLineCount") or 0)
                deletions = int(fd.get("removedLineCount") or 0)
                items.append({
                    "path": p,
                    "file_name": fd.get("fileName") or (p.split("/")[-1] if "/" in p else p.split("\\")[-1]),
                    "change_type": ctype,
                    "status": status,
                    "additions": additions,
                    "deletions": deletions,
                    "details": f"+{additions} / -{deletions} lines" if (additions or deletions) else f"{status} during migration",
                })

        for p in modified_files:
            if isinstance(p, str) and p and p not in seen_paths:
                seen_paths.add(p)
                fname = p.split("/")[-1] if "/" in p else p.split("\\")[-1]
                items.append({
                    "path": p,
                    "file_name": fname,
                    "change_type": "MODIFIED",
                    "status": "Modified",
                    "additions": 0,
                    "deletions": 0,
                    "details": "Modified during migration",
                })

        return {
            "migration_id": job_id,
            "type": "files",
            "total": len(items),
            "items": items,
        }

    elif dtype in ("issues", "issues_fixed"):
        issues = _build_issues(report)
        items = []
        for iss in issues:
            items.append({
                "id": iss.get("id"),
                "file": iss.get("file_path") or "src",
                "line": iss.get("line_number") or 1,
                "type": iss.get("category") or "Code Fix",
                "description": iss.get("message") or "Resolved migration issue",
                "fix": iss.get("suggested_fix") or "Applied automated transformation",
                "status": iss.get("status") or "fixed",
                "severity": iss.get("severity") or "info",
                "conversion_type": iss.get("conversion_type"),
            })
        return {
            "migration_id": job_id,
            "type": "issues",
            "total": len(items),
            "items": items,
        }

    elif dtype in ("dependencies", "dependencies_updated", "dependency_updated"):
        dep_upgrades = report.get("dependencyUpgrades") or report.get("dependency_upgrades") or []
        items = []
        for dep in dep_upgrades:
            gid = dep.get("groupId") or dep.get("group_id") or ""
            aid = dep.get("artifactId") or dep.get("artifact_id") or ""
            name = f"{gid}:{aid}" if gid and aid else (gid or aid or dep.get("coordinate") or "dependency")
            items.append({
                "name": name,
                "file": "pom.xml" if str(report.get("buildTool", "")).lower() == "maven" else "build.gradle",
                "old_version": dep.get("sourceVersion") or dep.get("old_version") or dep.get("current_version") or dep.get("oldVersion") or "managed",
                "new_version": dep.get("resolvedTargetVersion") or dep.get("new_version") or dep.get("newVersion") or "updated",
                "status": dep.get("status") or "UPGRADED",
                "scope": dep.get("scope") or "compile",
            })
        return {
            "migration_id": job_id,
            "type": "dependencies",
            "total": len(items),
            "items": items,
        }

    elif dtype in ("vulnerabilities", "vulnerability"):
        fossa_rep = report.get("fossa_report") or {}
        sonar_rep = report.get("sonar_report") or {}
        items = []
        for v in (fossa_rep.get("vulnerabilities") or []):
            if isinstance(v, dict):
                items.append({
                    "package": v.get("package") or v.get("dependency") or "dependency",
                    "identifier": v.get("cveId") or v.get("id") or "VULN",
                    "severity": v.get("severity") or "medium",
                    "affected_version": v.get("affectedVersion") or "current",
                    "fixed_version": v.get("fixedVersion") or "latest",
                    "source": v.get("source") or "FOSSA Scan",
                })
        for v in (sonar_rep.get("vulnerabilities") or []):
            if isinstance(v, dict):
                items.append({
                    "package": v.get("component") or v.get("file") or "source",
                    "identifier": v.get("rule") or v.get("key") or "SONAR-VULN",
                    "severity": v.get("severity") or "medium",
                    "affected_version": "-",
                    "fixed_version": "-",
                    "source": "SonarQube Scan",
                })
        return {
            "migration_id": job_id,
            "type": "vulnerabilities",
            "total": len(items),
            "items": items,
        }

    elif dtype in ("transformations", "code_transmission", "transmission"):
        items = []
        # 1. UI Transformations (JSP / JSF)
        ui_trans = report.get("uiTransformations") or []
        for ut in ui_trans:
            src = ut.get("sourceFile") or ut.get("file") or ""
            target = ut.get("targetSourceFile") or ut.get("targetFile") or (ut.get("file") if ut.get("sourceFile") and ut.get("file") != ut.get("sourceFile") else "")
            src_lower = src.lower()
            target_lower = target.lower()
            src_fw = ut.get("sourceFramework") or ("JSP" if src_lower.endswith((".jsp", ".jspf")) else ("JSF" if src_lower.endswith((".xhtml", ".jsf")) else "Legacy Template"))
            tgt_fw = ut.get("targetFramework") or ("React" if target_lower.endswith((".tsx", ".jsx")) else ("Angular" if target_lower.endswith((".ts", ".html")) else "Modern Component"))
            item = {
                "source_file": src,
                "target_file": target or f"Converted {tgt_fw} component",
                "transformation_type": ut.get("category") or f"{src_fw} -> {tgt_fw}",
                "source_framework": src_fw,
                "target_framework": tgt_fw,
                "status": ut.get("status") or "Completed",
                "additions": ut.get("additions") or 0,
                "deletions": ut.get("deletions") or 0,
            }
            if ut.get("accuracy") is not None:
                item["accuracy"] = ut.get("accuracy")
            items.append(item)
        # 2. Import Changes (Java namespace refactoring)
        for ic in (report.get("importChanges") or []):
            fpath = ic.get("file") or ""
            added = ic.get("added") or []
            removed = ic.get("removed") or []
            is_jakarta = any("jakarta" in str(a) for a in added)
            items.append({
                "source_file": fpath,
                "target_file": fpath,
                "transformation_type": "Jakarta EE Namespace Migration" if is_jakarta else "Import Refactoring",
                "source_framework": "Java EE (javax)",
                "target_framework": "Jakarta EE (jakarta)" if is_jakarta else "Modern Java",
                "status": "Transformed",
                "additions": len(added),
                "deletions": len(removed),
                "details": f"Replaced {len(removed)} old imports with {len(added)} modern imports",
            })
        # 3. Rule executions
        for re_item in (report.get("ruleExecutions") or []):
            fpath = re_item.get("filePath") or re_item.get("file") or ""
            items.append({
                "source_file": fpath,
                "target_file": fpath,
                "transformation_type": re_item.get("category") or "AST Code Transformation",
                "source_framework": "Legacy Java",
                "target_framework": "Modern Java",
                "status": "Transformed",
                "details": re_item.get("message") or re_item.get("description") or "Applied rule transformation",
            })
        return {
            "migration_id": job_id,
            "type": "transformations",
            "total": len(items),
            "items": items,
        }

    return {
        "migration_id": job_id,
        "type": dtype,
        "total": 0,
        "items": [],
    }
