"""Service layer coordinating Proposed Functional Test Cases generation, review, approval, and execution."""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.application.use_cases.existing_test_runner_service import ExistingTestDetector
from app.application.use_cases.proposed_tests.brd_analyzer import BrdAnalyzer
from app.application.use_cases.proposed_tests.proposed_test_analyzer import ProposedTestAnalyzer
from app.application.use_cases.proposed_tests.proposed_test_executor import ProposedTestExecutor
from app.application.use_cases.proposed_tests.proposed_test_generator import ProposedTestGenerator
from app.domain.models.proposed_test_models import (
    ExecutionResult,
    ProposedTestCase,
    ProposedTestComparisonResponse,
    ProposedTestMetrics,
    ProposedTestPriority,
    ProposedTestPriorityBreakdown,
    ProposedTestStatus,
    ProposedTestType,
    ProposedTestTypeBreakdown,
    TestComparisonItem,
)
from app.infrastructure.workspace.workspace_paths import WorkspacePaths

logger = logging.getLogger(__name__)


class ProposedTestService:
    """Manages Proposed Functional Test Cases per migration job."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._live_logs: dict[str, deque[dict[str, Any]]] = {}
        self._run_state: dict[str, dict[str, Any]] = {}

    def _get_job_dir(self, job_id: str) -> Path:
        paths = WorkspacePaths(job_id)
        pt_dir = paths.job_dir / "proposed-tests"
        pt_dir.mkdir(parents=True, exist_ok=True)
        return pt_dir

    def _get_proposals_file(self, job_id: str) -> Path:
        return self._get_job_dir(job_id) / "proposals.json"

    def _get_status_file(self, job_id: str) -> Path:
        return self._get_job_dir(job_id) / "status.json"

    def _get_results_file(self, job_id: str) -> Path:
        return self._get_job_dir(job_id) / "results.json"

    def _get_baseline_results_file(self, job_id: str) -> Path:
        return self._get_job_dir(job_id) / "baseline-results.json"

    def _get_baseline_status_file(self, job_id: str) -> Path:
        return self._get_job_dir(job_id) / "baseline-status.json"

    def _get_comparison_file(self, job_id: str) -> Path:
        return self._get_job_dir(job_id) / "comparison.json"

    def _get_validation_file(self, job_id: str) -> Path:
        return self._get_job_dir(job_id) / "validation-summary.json"

    def _save_validation_summary(self, job_id: str, summary: Any) -> None:
        try:
            val_file = self._get_validation_file(job_id)
            val_file.write_text(json.dumps(summary.model_dump(), indent=2), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to save validation summary for {job_id}: {e}")

    def _log(self, job_id: str, msg: str, level: str = "INFO") -> None:
        with self._lock:
            if job_id not in self._live_logs:
                self._live_logs[job_id] = deque(maxlen=500)
            entry = {
                "ts": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "msg": msg,
                "level": level,
            }
            self._live_logs[job_id].append(entry)
        logger.info(f"[{job_id}] [{level}] {msg}")

    def _save_status(self, job_id: str, status_str: str, extra: dict[str, Any] | None = None) -> None:
        payload = {
            "job_id": job_id,
            "status": status_str,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **(extra or {}),
        }
        try:
            self._get_status_file(job_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not write status file for {job_id}: {e}")

    def generate_proposed_tests(self, job_id: str) -> list[ProposedTestCase]:
        """Analyzes migrated repo, discovers gaps, and generates proposed tests."""
        self._save_status(job_id, "GENERATING")
        self._log(job_id, "[PROPOSED TESTS] Starting codebase & feature discovery...")
        paths = WorkspacePaths(job_id)

        try:
            # Look for migrated-repo first, fallback to original-repo
            repo_dir = paths.migrated_repo_dir if paths.migrated_repo_dir.exists() else paths.original_repo_dir

            existing_tests: list[dict[str, Any]] = []
            if repo_dir.exists():
                try:
                    detector = ExistingTestDetector(repo_dir)
                    detector.scan()
                    existing_tests = detector.tests_found
                    self._log(job_id, f"[PROPOSED TESTS] Analyzed existing coverage from {len(existing_tests)} existing tests.")
                except Exception as e:  # noqa: BLE001
                    self._log(job_id, f"[PROPOSED TESTS] Note on existing test detection: {e}", "DEBUG")

            # Load migration report data for quality check prompt configurations
            rep_data: dict[str, Any] = {}
            if paths.migration_report_path.exists():
                try:
                    import json
                    rep_data = json.loads(paths.migration_report_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            tc_vals = rep_data.get("test_cases_values") or rep_data.get("testCasesValues") or {}
            qc_vals = rep_data.get("quality_checks_values") or rep_data.get("qualityChecksValues") or {}

            # Static analyzer
            analyzer = ProposedTestAnalyzer(repo_dir, existing_tests=existing_tests)
            analysis_data = analyzer.analyze()
            analysis_data["functional_testing_prompt"] = rep_data.get("functional_testing_prompt") or qc_vals.get("functional_testing_prompt")
            analysis_data["functional_custom_prompt"] = rep_data.get("functional_custom_prompt") or qc_vals.get("functional_custom_prompt")
            analysis_data["functional_testing_suggestions"] = rep_data.get("functional_testing_suggestions") or qc_vals.get("functional_testing_suggestions") or []
            analysis_data["testing_prompt"] = (
                rep_data.get("testing_prompt")
                or tc_vals.get("testing_prompt")
                or qc_vals.get("testing_prompt")
            )
            analysis_data["selected_predefined_prompts"] = (
                rep_data.get("selected_predefined_prompts")
                or tc_vals.get("selected_predefined_prompts")
                or qc_vals.get("selected_predefined_prompts")
                or []
            )

            ep_count = len(analysis_data.get("endpoints", []))
            svc_count = len(analysis_data.get("services", []))
            ui_count = len(analysis_data.get("ui_workflows", []))
            self._log(job_id, f"[PROPOSED TESTS] Discovered: {ep_count} REST endpoints, {svc_count} services, {ui_count} UI workflows.")

            # BRD Analyzer
            brd_analysis = None
            if paths.brd_dir.exists():
                try:
                    brd_files = [f for f in paths.brd_dir.iterdir() if f.is_file() and f.name != "metadata.json"]
                    if brd_files:
                        brd_file = brd_files[0]
                        self._log(job_id, f"[PROPOSED TESTS] Found uploaded BRD document: {brd_file.name}. Parsing requirements...")
                        brd_analyzer = BrdAnalyzer(brd_file, job_id=job_id)
                        brd_analysis = brd_analyzer.extract()
                        if brd_analysis.error:
                            self._log(job_id, f"[PROPOSED TESTS] BRD parser note: {brd_analysis.error}", "WARNING")
                        else:
                            wf_cnt = len(brd_analysis.workflows)
                            req_cnt = len(brd_analysis.requirements)
                            self._log(job_id, f"[PROPOSED TESTS] Extracted {wf_cnt} business workflows and {req_cnt} requirements from BRD.")
                except Exception as e:  # noqa: BLE001
                    self._log(job_id, f"[PROPOSED TESTS] BRD extraction note: {e}", "WARNING")

            # Generator
            generator = ProposedTestGenerator(analysis_data, brd_analysis=brd_analysis)
            proposals = generator.generate()
            self._log(job_id, f"[PROPOSED TESTS] Generated {len(proposals)} proposed test cases across UNIT, API, and UI.")

            # Validate generated test cases against actual repository source code evidence
            from app.application.use_cases.proposed_tests.proposed_test_validator import ProposedTestValidator
            validator = ProposedTestValidator(repo_dir, analysis_data=analysis_data)
            proposals, val_summary = validator.validate_all(proposals)
            self._save_validation_summary(job_id, val_summary)
            self._log(
                job_id,
                f"[PROPOSED TESTS] Validation completed: {val_summary.valid} Valid, "
                f"{val_summary.partially_valid} Partially Valid, {val_summary.hallucinated} Hallucinated, "
                f"{val_summary.invalid} Invalid, {val_summary.duplicate} Duplicate."
            )

            # Persist proposals & update status to COMPLETED
            self._save_proposals(job_id, proposals)
            metrics = self._compute_metrics(proposals)
            self._save_status(job_id, "COMPLETED", {
                "total": len(proposals),
                "generated": len(proposals),
                "metrics": metrics.model_dump(),
                "validation_summary": val_summary.model_dump(),
            })
            return proposals

        except Exception as e:
            self._log(job_id, f"[PROPOSED TESTS] Generation failed: {e}", "ERROR")
            self._save_status(job_id, "FAILED", {"error": str(e)})
            raise

    def get_proposed_tests(self, job_id: str) -> list[ProposedTestCase]:
        """Loads proposals from disk without auto-generating."""
        prop_file = self._get_proposals_file(job_id)
        if prop_file.exists():
            try:
                data = json.loads(prop_file.read_text(encoding="utf-8"))
                return [ProposedTestCase.model_validate(p) for p in data]
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to load proposals for {job_id}: {e}")

        return []

    def get_proposed_test(self, job_id: str, test_id: str) -> ProposedTestCase | None:
        proposals = self.get_proposed_tests(job_id)
        for p in proposals:
            if p.id == test_id:
                return p
        return None

    def update_proposed_test(self, job_id: str, test_id: str, updates: dict[str, Any]) -> ProposedTestCase | None:
        proposals = self.get_proposed_tests(job_id)
        target = None
        for p in proposals:
            if p.id == test_id:
                for k, v in updates.items():
                    if hasattr(p, k) and v is not None:
                        setattr(p, k, v)
                target = p
                break

        if target:
            self._save_proposals(job_id, proposals)
            self._log(job_id, f"[PROPOSED TESTS] Updated test definition for {test_id}")
        return target

    def set_status(self, job_id: str, test_id: str, status: ProposedTestStatus) -> ProposedTestCase | None:
        proposals = self.get_proposed_tests(job_id)
        target = None
        for p in proposals:
            if p.id == test_id:
                p.status = status
                target = p
                break

        if target:
            self._save_proposals(job_id, proposals)
            self._log(job_id, f"[PROPOSED TESTS] {test_id} status updated to: {status.value}")
        return target

    def bulk_set_status(self, job_id: str, test_ids: list[str], status: ProposedTestStatus) -> list[ProposedTestCase]:
        proposals = self.get_proposed_tests(job_id)
        target_ids = set(test_ids)
        updated_items = []
        for p in proposals:
            if p.id in target_ids:
                p.status = status
                updated_items.append(p)

        if updated_items:
            self._save_proposals(job_id, proposals)
            self._log(job_id, f"[PROPOSED TESTS] Bulk updated {len(updated_items)} test(s) to status: {status.value}")
        return proposals

    def get_validation_summary(self, job_id: str) -> dict[str, Any] | None:
        val_file = self._get_validation_file(job_id)
        if val_file.exists():
            try:
                return json.loads(val_file.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                pass
        return None

    def validate_proposed_tests(self, job_id: str) -> tuple[list[ProposedTestCase], dict[str, Any]]:
        proposals = self.get_proposed_tests(job_id)
        paths = WorkspacePaths(job_id)
        repo_dir = paths.migrated_repo_dir if paths.migrated_repo_dir.exists() else paths.original_repo_dir

        analyzer = ProposedTestAnalyzer(repo_dir)
        analysis_data = analyzer.analyze()

        from app.application.use_cases.proposed_tests.proposed_test_validator import ProposedTestValidator
        validator = ProposedTestValidator(repo_dir, analysis_data=analysis_data)
        validated_proposals, val_summary = validator.validate_all(proposals)

        self._save_proposals(job_id, validated_proposals)
        self._save_validation_summary(job_id, val_summary)
        return validated_proposals, val_summary.model_dump()

    def run_proposed_tests(
        self,
        job_id: str,
        request: Any = None,
    ) -> dict[str, Any]:
        sources = getattr(request, "sources", None) if request else None
        test_ids = getattr(request, "test_ids", None) if request else None
        framework = getattr(request, "framework", "PLAYWRIGHT") if request else "PLAYWRIGHT"
        if isinstance(request, dict):
            sources = request.get("sources", sources)
            test_ids = request.get("test_ids", test_ids)
            framework = request.get("framework", framework)
        return self.run_approved_tests(
            job_id=job_id,
            sources=sources,
            test_ids=test_ids,
            framework=framework,
        )

    def run_approved_tests(
        self,
        job_id: str,
        sources: list[str] | None = None,
        test_ids: list[str] | None = None,
        framework: str = "PLAYWRIGHT",
    ) -> dict[str, Any]:
        fw_upper = (framework or "PLAYWRIGHT").upper()
        if fw_upper in ["SELENIUM", "SELENIUM_WEBDRIVER"]:
            raise ValueError("Selenium support is coming soon.")
        if fw_upper in ["CYPRESS"]:
            raise ValueError("Cypress support is coming soon.")

        proposals = self.get_proposed_tests(job_id)
        if not proposals:
            try:
                proposals = self.generate_proposed_tests(job_id)
            except Exception as ex:  # noqa: BLE001
                self._log(job_id, f"[PROPOSED TESTS] Failed to generate tests on run: {ex}", "WARN")

        # If sources is None, check if there are saved sources in status.json or migration-report.json
        if sources is None:
            status_file = self._get_status_file(job_id)
            if status_file.exists():
                try:
                    sdata = json.loads(status_file.read_text(encoding="utf-8"))
                    sources = sdata.get("selected_sources")
                except Exception:  # noqa: BLE001
                    pass
            if sources is None:
                paths = WorkspacePaths(job_id)
                from app.application.services.status_service import MigrationReportStore
                rep = MigrationReportStore(paths).read() or {}
                sources = rep.get("proposedTestSources") or rep.get("options", {}).get("proposedTestSources")

        # Normalize sources
        norm_sources = [s.upper() for s in sources] if sources is not None else ["LLM", "FUNCTIONAL_DOC", "EXISTING"]

        # If user explicitly unselected all sources (empty list)
        if sources is not None and len(sources) == 0:
            self._log(job_id, "[PROPOSED TESTS] No test sources selected for execution.")
            empty_metrics = self._compute_metrics([])
            empty_payload = {
                "job_id": job_id,
                "status": "COMPLETED",
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "selected_sources": [],
                "metrics": empty_metrics.model_dump(),
                "test_cases": [],
            }
            self._get_results_file(job_id).write_text(json.dumps(empty_payload, indent=2), encoding="utf-8")
            self._save_status(job_id, "COMPLETED", {
                "selected_sources": [],
                "total": 0,
                "executed": 0,
                "passed": 0,
                "failed": 0,
                "metrics": empty_metrics.model_dump(),
            })
            return {
                "status": "COMPLETED",
                "message": "No test case sources selected to execute.",
                "executed": 0,
                "total": 0,
            }

        run_llm = any(k in norm_sources for k in ["LLM", "AI_GENERATED", "AI"])
        run_doc = any(k in norm_sources for k in ["FUNCTIONAL_DOC", "FUNCTIONAL_DOCUMENT", "BRD_DOCUMENT", "BRD", "DOCUMENT"])
        run_existing = any(k in norm_sources for k in ["EXISTING", "EXISTING_TESTS", "JUNIT"])

        tests_to_run: list[ProposedTestCase] = []
        seen_ids: set[str] = set()

        for p in proposals:
            if test_ids:
                should_run = (p.id in test_ids)
            else:
                is_doc = (
                    p.generation_source in ["BRD_DOCUMENT", "BRD_AND_AI", "FUNCTIONAL_DOC"]
                    or "BRD" in p.id
                    or p.source in ["BRD Document", "BRD Business Requirement"]
                )
                is_existing = (
                    p.generation_source in ["EXISTING", "EXISTING_TESTS"]
                    or "EXT" in p.id
                    or p.source in ["Existing Repository", "Existing Repository Tests"]
                )
                is_llm = not is_doc and not is_existing
                should_run = (run_llm and is_llm) or (run_doc and is_doc) or (run_existing and is_existing)

            if should_run:
                # If validation flagged test as non-executable (e.g. hallucinated/invalid), skip execution unless explicitly chosen by test_id
                if not test_ids and p.validation and not p.validation.playwright_executable:
                    self._log(job_id, f"[PROPOSED TESTS] Skipping non-executable test {p.id} ({p.validation.status.value}): {p.validation.issue}")
                    continue
                if p.id not in seen_ids:
                    seen_ids.add(p.id)
                    tests_to_run.append(p)

        if not tests_to_run:
            empty_metrics = self._compute_metrics([])
            empty_payload = {
                "job_id": job_id,
                "status": "COMPLETED",
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "selected_sources": norm_sources,
                "metrics": empty_metrics.model_dump(),
                "test_cases": [],
            }
            self._get_results_file(job_id).write_text(json.dumps(empty_payload, indent=2), encoding="utf-8")
            self._save_status(job_id, "COMPLETED", {
                "selected_sources": norm_sources,
                "total": 0,
                "executed": 0,
                "passed": 0,
                "failed": 0,
                "metrics": empty_metrics.model_dump(),
            })
            return {
                "status": "COMPLETED",
                "message": "No test cases found matching the selected sources to execute.",
                "executed": 0,
                "total": 0,
            }

        with self._lock:
            self._run_state[job_id] = {
                "status": "RUNNING",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "selected_sources": norm_sources,
                "total": len(tests_to_run),
                "completed": 0,
            }
        self._save_status(job_id, "RUNNING", {
            "selected_sources": norm_sources,
            "total": len(tests_to_run),
            "completed": 0,
        })

        # Initialize and clean Allure reporter directories for fresh execution isolation
        from app.application.use_cases.proposed_tests.proposed_test_allure_reporter import ProposedTestAllureReporter
        reporter = ProposedTestAllureReporter(job_id)
        reporter.clean_results()

        def _run_bg():
            paths = WorkspacePaths(job_id)
            source_dir = paths.original_repo_dir if paths.original_repo_dir.exists() else paths.migrated_repo_dir
            evidence_dir = paths.job_dir / "evidence"

            self._log(job_id, "[BASELINE] User requested proposed test execution.")
            self._log(job_id, "[BASELINE] Execution target: SOURCE APPLICATION")
            self._log(job_id, "[BASELINE] Resolving source application URL...")

            build_tool = "GRADLE" if (source_dir / "build.gradle").exists() or (source_dir / "build.gradle.kts").exists() else "MAVEN"

            from app.infrastructure.build.build_validator import BuildValidator
            from app.infrastructure.build.app_launcher import MigratedAppLauncher
            from app.infrastructure.build.app_readiness_checker import AppReadinessChecker
            from app.application.use_cases.proposed_tests.proposed_test_executor import resolve_app_port

            self._log(job_id, f"[BASELINE] Building source repository ({build_tool})...")
            build_validator = BuildValidator()
            build_result = build_validator.validate(source_dir, build_tool=build_tool)
            source_build_success = bool(build_result.success or build_result.skipped)

            source_app_url: str | None = None
            launcher = MigratedAppLauncher()
            launched_pid: int | None = None
            app_ready = False
            readiness_error: str | None = None

            if not source_build_success:
                build_err = "\n".join(build_result.error_lines) if build_result.error_lines else "Compilation or packaging failure"
                # Emit all required BASELINE log lines for build-failure path
                self._log(job_id, "[BASELINE] Source build FAILED.", "WARN")
                self._log(job_id, "[BASELINE] Source application will not be started.", "WARN")
                self._log(job_id, "[BASELINE] Proposed test execution skipped because source build failed.", "WARN")
                self._log(job_id, f"[BASELINE] Marking {len(tests_to_run)} valid tests as NOT_EXECUTED.", "INFO")
                readiness_error = f"Source build failed: {build_err}"
                for t in tests_to_run:
                    t.status = ProposedTestStatus.NOT_EXECUTED
                    t.execution_result = ExecutionResult(
                        status=ProposedTestStatus.NOT_EXECUTED,
                        error=readiness_error,
                        error_type="SOURCE_BUILD_FAILED",
                        executed_at=datetime.now(timezone.utc).isoformat(),
                    )
                    t.baseline_execution_result = t.execution_result
            else:
                self._log(job_id, "[BASELINE] Source build SUCCEEDED.")
                source_port = resolve_app_port(source_dir, default_port=8080)
                source_app_url = f"http://localhost:{source_port}"
                self._log(job_id, f"[BASELINE] Resolved source application URL: {source_app_url}")
                self._log(job_id, f"[BASELINE] Resolved source application port: {source_port}")

                self._log(job_id, "[BASELINE] Starting source application...")
                launch_res = launcher.launch(
                    project_dir=source_dir,
                    build_tool=build_tool,
                    port=source_port,
                    app_type_label="Source application",
                    startup_timeout=30.0,
                )

                if launch_res.success:
                    launched_pid = launch_res.pid
                    self._log(job_id, f"[BASELINE] Source application process started. PID={launched_pid}")
                    readiness = AppReadinessChecker().wait_for_ready(
                        source_app_url,
                        timeout_s=30.0,
                        poll_interval_s=2.0,
                        process_pid=launched_pid,
                        app_type_label="Source application",
                        log_attempt_fn=lambda att, max_att: self._log(job_id, f"[BASELINE] Readiness attempt {att}/{max_att}..."),
                    )

                    if readiness.ready:
                        app_ready = True
                        self._log(
                            job_id,
                            f"[BASELINE] Source application READY. URL={source_app_url} "
                            f"(HTTP {readiness.http_status} on {readiness.health_endpoint})",
                        )
                    elif readiness.process_exited:
                        readiness_error = readiness.error or "Process exited prematurely during startup"
                        self._log(job_id, f"[BASELINE] Source application STARTUP FAILED. Process: EXITED\n{readiness_error}", "WARN")
                    else:
                        readiness_error = readiness.error or f"Source application at {source_app_url} did not become ready."
                        self._log(job_id, f"[BASELINE] Source application NOT READY. Reason: {readiness_error}", "WARN")
                else:
                    readiness_error = launch_res.error or "Failed to start source application process"
                    self._log(job_id, f"[BASELINE] Source application STARTUP FAILED: {readiness_error}", "WARN")

                if not app_ready:
                    for t in tests_to_run:
                        t.status = ProposedTestStatus.APPLICATION_UNAVAILABLE
                        t.execution_result = ExecutionResult(
                            status=ProposedTestStatus.APPLICATION_UNAVAILABLE,
                            error=f"Source application unavailable: {readiness_error}",
                            error_type="INFRASTRUCTURE_UNAVAILABLE",
                            executed_at=datetime.now(timezone.utc).isoformat(),
                        )
                        t.baseline_execution_result = t.execution_result

            # ── If App is READY — proceed with Playwright execution against Source ──
            if app_ready and source_app_url:
                executor = ProposedTestExecutor(
                    job_id,
                    evidence_dir=evidence_dir,
                    log_fn=lambda m, level="INFO": self._log(job_id, m, level),
                    base_url=source_app_url,
                )

                self._log(job_id, "[BASELINE] Executing selected proposed tests...")
                for t in tests_to_run:
                    self._log(job_id, f"[BASELINE] Test {t.id} - {t.title}...")
                    t.status = ProposedTestStatus.RUNNING
                    self._save_proposals(job_id, proposals)

                    res = executor.execute_test(t, repo_dir=source_dir)
                    t.execution_result = res
                    t.baseline_execution_result = res
                    t.status = res.status
                    self._save_proposals(job_id, proposals)
                    self._log(job_id, f"[BASELINE] {t.id} {res.status.value}")

                    with self._lock:
                        if job_id in self._run_state:
                            self._run_state[job_id]["completed"] += 1

                # Generate Allure results and standalone HTML report for executed tests
                try:
                    reporter.generate_allure_results(tests_to_run, selected_sources=norm_sources)
                    reporter.generate_html_report(tests_to_run, selected_sources=norm_sources)
                    self._log(job_id, "[BASELINE] Allure Report generated successfully.")
                except Exception as a_err:  # noqa: BLE001
                    self._log(job_id, f"[BASELINE] Failed to generate Allure Report: {a_err}", "WARN")

            # Clean up launched source app process
            if launched_pid:
                try:
                    launcher.stop(launched_pid)
                    self._log(job_id, f"[BASELINE] Stopped source application process (PID={launched_pid}).")
                except Exception as stop_exc:  # noqa: BLE001
                    logger.warning(f"Failed to stop source app process {launched_pid}: {stop_exc}")

            # Save updated proposals preserving complete master inventory
            self._save_proposals(job_id, proposals)
            metrics = self._compute_metrics(proposals)
            baseline_metrics = self._compute_metrics_for_baseline(proposals)
            allure_url = f"/api/v1/migration/{job_id}/proposed-tests/allure-report/index.html"

            result_payload = {
                "job_id": job_id,
                "status": "COMPLETED",
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "execution_target": "SOURCE_APPLICATION",
                "execution_mode": "BASELINE",
                "source_base_url": source_app_url,
                "app_ready": app_ready,
                "app_readiness_error": readiness_error,
                "selected_sources": norm_sources,
                "metrics": metrics.model_dump(),
                "allure_report_available": app_ready,
                "allure_report_url": allure_url if app_ready else None,
                "test_cases": [p.model_dump() for p in proposals],
            }
            self._get_results_file(job_id).write_text(json.dumps(result_payload, indent=2), encoding="utf-8")
            self._get_baseline_results_file(job_id).write_text(json.dumps(result_payload, indent=2), encoding="utf-8")

            with self._lock:
                self._run_state[job_id] = {
                    "status": "COMPLETED",
                    "result": result_payload,
                    "selected_sources": norm_sources,
                    "allure_report_available": app_ready,
                    "allure_report_url": allure_url if app_ready else None,
                }
            self._save_status(job_id, "COMPLETED", {
                "selected_sources": norm_sources,
                "total": len(proposals),
                "executed": metrics.executed,
                "passed": metrics.passed,
                "failed": metrics.failed,
                "app_ready": app_ready,
                "allure_report_available": app_ready,
                "allure_report_url": allure_url if app_ready else None,
                "metrics": metrics.model_dump(),
            })
            # IMPORTANT: use metrics.executed (actual Playwright results), NOT len(tests_to_run).
            # tests_to_run is the list of *valid/selected* tests — it is NOT the executed count.
            # Playwright may never have run (e.g. build failure → executed == 0).
            self._log(
                job_id,
                f"[BASELINE] Baseline execution completed. "
                f"Executed: {metrics.executed}/{len(proposals)}, "
                f"Passed: {metrics.passed}, Failed: {metrics.failed}, "
                f"Not Executed: {metrics.not_executed}."
            )

        thread = threading.Thread(target=_run_bg, daemon=True)
        thread.start()

        return {
            "status": "RUNNING",
            "message": f"Started execution of {len(tests_to_run)} test(s) in background.",
            "total_approved": len(tests_to_run),
        }

    def get_status(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            mem_state = self._run_state.get(job_id)

        paths = WorkspacePaths(job_id)
        allure_index = paths.job_dir / "proposed-tests" / "allure-report" / "index.html"
        allure_available = allure_index.is_file()
        allure_url = f"/api/v1/migration/{job_id}/proposed-tests/allure-report/index.html" if allure_available else None

        persisted_status = "IDLE"
        persisted_sources = None
        status_file = self._get_status_file(job_id)
        if status_file.exists():
            try:
                sdata = json.loads(status_file.read_text(encoding="utf-8"))
                persisted_status = sdata.get("status", "IDLE")
                persisted_sources = sdata.get("selected_sources")
            except Exception:  # noqa: BLE001
                pass

        with self._lock:
            logs = list(self._live_logs.get(job_id, []))

        proposals = self.get_proposed_tests(job_id)
        metrics = self._compute_metrics(proposals)
        current_status = mem_state.get("status") if mem_state else persisted_status
        if not proposals and current_status != "GENERATING":
            current_status = "IDLE"

        res_file = self._get_results_file(job_id)
        if res_file.exists():
            try:
                rdata = json.loads(res_file.read_text(encoding="utf-8"))
                current_status = mem_state.get("status") if mem_state else rdata.get("status", "COMPLETED")
                persisted_sources = rdata.get("selected_sources", persisted_sources)
            except Exception:  # noqa: BLE001
                pass

        return {
            "job_id": job_id,
            "status": current_status,
            "progress": {
                "total": mem_state.get("total", len(proposals)) if mem_state else len(proposals),
                "completed": mem_state.get("completed", 0) if mem_state else metrics.executed,
            },
            "selected_sources": mem_state.get("selected_sources") if mem_state else persisted_sources,
            "allure_report_available": allure_available,
            "allure_report_url": allure_url,
            "metrics": metrics.model_dump(),
            "logs": logs,
            "proposals": [p.model_dump() for p in proposals],
        }

    def get_results(self, job_id: str) -> dict[str, Any]:
        paths = WorkspacePaths(job_id)
        allure_index = paths.job_dir / "proposed-tests" / "allure-report" / "index.html"
        allure_available = allure_index.is_file()
        allure_url = f"/api/v1/migration/{job_id}/proposed-tests/allure-report/index.html" if allure_available else None

        proposals = self.get_proposed_tests(job_id)
        metrics = self._compute_metrics(proposals)

        res_file = self._get_results_file(job_id)
        status = "IDLE"
        selected_sources = None
        executed_at = None
        if res_file.exists():
            try:
                data = json.loads(res_file.read_text(encoding="utf-8"))
                status = data.get("status", "COMPLETED")
                selected_sources = data.get("selected_sources")
                executed_at = data.get("executed_at")
            except Exception:  # noqa: BLE001, S110
                pass  # nosec B110

        return {
            "job_id": job_id,
            "status": status,
            "executed_at": executed_at,
            "selected_sources": selected_sources,
            "allure_report_available": allure_available,
            "allure_report_url": allure_url,
            "metrics": metrics.model_dump(),
            "test_cases": [p.model_dump() for p in proposals],
        }

    def _compute_metrics(self, proposals: list[ProposedTestCase]) -> ProposedTestMetrics:
        total = len(proposals)
        approved = len([p for p in proposals if p.status == ProposedTestStatus.APPROVED])
        rejected = len([p for p in proposals if p.status == ProposedTestStatus.REJECTED])
        executed = len([p for p in proposals if p.status in [ProposedTestStatus.PASSED, ProposedTestStatus.FAILED, ProposedTestStatus.SKIPPED]])
        passed = len([p for p in proposals if p.status == ProposedTestStatus.PASSED])
        failed = len([p for p in proposals if p.status == ProposedTestStatus.FAILED])
        skipped = len([p for p in proposals if p.status == ProposedTestStatus.SKIPPED])
        app_unavailable = len([p for p in proposals if p.status == ProposedTestStatus.APPLICATION_UNAVAILABLE])
        # not_executed: count ONLY tests explicitly marked NOT_EXECUTED.
        # Do NOT use subtraction (total - executed - app_unavailable):
        #   that formula incorrectly counts duplicates, hallucinated, and
        #   other non-candidate tests as "not executed", inflating the number.
        # A test being VALID does NOT mean it was executed.
        # A test being DUPLICATE does NOT mean it was executed.
        # Only real Playwright execution produces PASSED / FAILED / SKIPPED.
        not_executed = len([p for p in proposals if p.status == ProposedTestStatus.NOT_EXECUTED])

        pass_pct = f"{round((passed / executed * 100), 1)}%" if executed > 0 else "0%"

        unit_tests = [p for p in proposals if p.type == ProposedTestType.UNIT]
        api_tests = [p for p in proposals if p.type == ProposedTestType.API]
        ui_tests = [p for p in proposals if p.type == ProposedTestType.UI]

        high_p = len([p for p in proposals if p.priority == ProposedTestPriority.HIGH])
        med_p = len([p for p in proposals if p.priority == ProposedTestPriority.MEDIUM])
        low_p = len([p for p in proposals if p.priority == ProposedTestPriority.LOW])

        brd_gen = len([
            p for p in proposals
            if (
                p.generation_source in ["BRD_DOCUMENT", "FUNCTIONAL_DOC", "FUNCTIONAL_DOCUMENT", "Functional Testing Document Generated"]
                or ("BRD" in p.id and p.generation_source != "BRD_AND_AI")
                or p.source in ["BRD Document", "BRD Business Requirement", "Functional Testing Document Generated"]
            ) and p.generation_source != "BRD_AND_AI"
        ])
        existing_gen = len([
            p for p in proposals
            if p.generation_source in ["EXISTING", "EXISTING_TESTS"]
            or "EXT" in p.id
            or p.source in ["Existing Repository", "Existing Repository Tests"]
        ])
        ai_gen = max(0, total - brd_gen - existing_gen)

        return ProposedTestMetrics(
            total=total,
            approved=approved,
            rejected=rejected,
            executed=executed,
            passed=passed,
            failed=failed,
            skipped=skipped,
            not_executed=not_executed,
            gaps_count=total,
            ai_generated_count=ai_gen,
            brd_generated_count=brd_gen,
            llm_generated_count=ai_gen,
            functional_doc_generated_count=brd_gen,
            existing_generated_count=existing_gen,
            existing_count=existing_gen,
            pass_percentage=pass_pct,
            unit_metrics=ProposedTestTypeBreakdown(
                total=len(unit_tests),
                passed=len([p for p in unit_tests if p.status == ProposedTestStatus.PASSED]),
                failed=len([p for p in unit_tests if p.status == ProposedTestStatus.FAILED]),
                skipped=len([p for p in unit_tests if p.status == ProposedTestStatus.SKIPPED]),
            ),
            api_metrics=ProposedTestTypeBreakdown(
                total=len(api_tests),
                passed=len([p for p in api_tests if p.status == ProposedTestStatus.PASSED]),
                failed=len([p for p in api_tests if p.status == ProposedTestStatus.FAILED]),
                skipped=len([p for p in api_tests if p.status == ProposedTestStatus.SKIPPED]),
            ),
            ui_metrics=ProposedTestTypeBreakdown(
                total=len(ui_tests),
                passed=len([p for p in ui_tests if p.status == ProposedTestStatus.PASSED]),
                failed=len([p for p in ui_tests if p.status == ProposedTestStatus.FAILED]),
                skipped=len([p for p in ui_tests if p.status == ProposedTestStatus.SKIPPED]),
            ),
            priority_metrics=ProposedTestPriorityBreakdown(
                high=high_p,
                medium=med_p,
                low=low_p,
            ),
        )

    def _save_proposals(self, job_id: str, proposals: list[ProposedTestCase]) -> None:
        with self._lock:
            try:
                target = self._get_proposals_file(job_id)
                target.parent.mkdir(parents=True, exist_ok=True)
                data = [p.model_dump() for p in proposals]
                target.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to write proposals file for {job_id}: {e}")

    def run_source_baseline(
        self,
        job_id: str,
        build_tool: str = "MAVEN",
        force_regenerate: bool = False,
    ) -> dict[str, Any]:
        """Builds, starts, validates and executes proposed tests against the SOURCE repository.

        Saves the generated master test suite to proposals.json and records baseline execution
        results in baseline-results.json.
        """
        paths = WorkspacePaths(job_id)
        source_dir = paths.original_repo_dir
        self._log(job_id, "[BASELINE] Starting pre-migration source application validation...")

        if not source_dir.exists():
            err_msg = f"Source repository directory not found at {source_dir}"
            self._log(job_id, f"[BASELINE] Error: {err_msg}", "ERROR")
            return {"status": "FAILED", "error": err_msg}

        from app.infrastructure.build.build_validator import BuildValidator
        from app.infrastructure.build.app_launcher import MigratedAppLauncher
        from app.infrastructure.build.app_readiness_checker import AppReadinessChecker
        from app.application.use_cases.proposed_tests.proposed_test_executor import resolve_app_port

        self._log(job_id, f"[BASELINE] Building source repository ({build_tool})...")
        build_validator = BuildValidator()
        build_result = build_validator.validate(source_dir, build_tool=build_tool)

        source_build_success = bool(build_result.success or build_result.skipped)
        source_app_url: str | None = None
        source_startup_status = "NOT_STARTED"
        source_readiness_status = "NOT_STARTED"
        source_readiness_error: str | None = None
        launcher = MigratedAppLauncher()
        launched_pid: int | None = None

        # Always generate + validate the master test suite from the source repo (if not already generated)
        proposals = self.get_proposed_tests(job_id)
        if not proposals or force_regenerate:
            self._log(job_id, "[BASELINE] Generating master proposed test suite from source repository...")
            proposals = self.generate_proposed_tests(job_id)
        else:
            self._log(job_id, f"[BASELINE] Loaded {len(proposals)} existing proposed test cases from master inventory.")

        if source_build_success:
            self._log(job_id, "[BASELINE] Source build SUCCEEDED.")
            source_port = resolve_app_port(source_dir, default_port=8080)
            source_app_url = f"http://localhost:{source_port}"
            self._log(job_id, f"[BASELINE] Resolved source application URL: {source_app_url}")
            self._log(job_id, f"[BASELINE] Resolved source application port: {source_port}")

            self._log(job_id, "[BASELINE] Launching source application...")
            launch_res = launcher.launch(
                project_dir=source_dir,
                build_tool=build_tool,
                port=source_port,
                app_type_label="Source application",
                startup_timeout=30.0,
            )

            if launch_res.success:
                source_startup_status = "STARTED"
                launched_pid = launch_res.pid
                self._log(job_id, f"[BASELINE] Source application process started. PID={launched_pid}")
                self._log(job_id, "[BASELINE] Waiting for source application startup...")

                readiness = AppReadinessChecker().wait_for_ready(
                    source_app_url,
                    timeout_s=30.0,
                    poll_interval_s=2.0,
                    process_pid=launched_pid,
                    app_type_label="Source application",
                    log_attempt_fn=lambda att, max_att: self._log(job_id, f"[BASELINE] Readiness attempt {att}/{max_att}..."),
                )

                if readiness.ready:
                    source_readiness_status = "READY"
                    self._log(
                        job_id,
                        f"[BASELINE] Source application is READY.\n"
                        f"URL={source_app_url} (HTTP {readiness.http_status} on {readiness.health_endpoint})",
                    )
                elif readiness.process_exited:
                    source_startup_status = "STARTUP_FAILED"
                    source_readiness_status = "APPLICATION_UNAVAILABLE"
                    source_readiness_error = readiness.error
                    self._log(
                        job_id,
                        f"[BASELINE] Source application STARTUP FAILED.\n"
                        f"Process: EXITED\nStartup error:\n{readiness.error}",
                        "WARN",
                    )
                else:
                    source_readiness_status = "NOT_READY"
                    source_readiness_error = readiness.error
                    self._log(
                        job_id,
                        f"[BASELINE] Source application NOT READY.\nReason: {readiness.error}",
                        "WARN",
                    )
            else:
                source_startup_status = "RUNTIME_UNSUPPORTED" if launch_res.runtime_unsupported else "STARTUP_FAILED"
                source_readiness_status = "APPLICATION_UNAVAILABLE"
                source_readiness_error = launch_res.error
                exit_str = f"Exit code: {launch_res.exit_code}\n" if launch_res.exit_code is not None else ""
                self._log(
                    job_id,
                    f"[BASELINE] Source application STARTUP FAILED.\n"
                    f"Process: EXITED\n{exit_str}Startup error:\n{launch_res.error}",
                    "WARN",
                )
        else:
            build_err = "\n".join(build_result.error_lines) if build_result.error_lines else "Compilation or packaging failure"
            self._log(job_id, f"[BASELINE] Source build FAILED: {build_err}", "WARN")

        # Execute Baseline Tests ONLY if Source App is READY
        evidence_dir = self._get_job_dir(job_id) / "baseline-evidence"
        if source_readiness_status == "READY" and source_app_url:
            self._log(job_id, "[BASELINE] Starting Playwright baseline execution...")
            self._log(job_id, f"[BASELINE] Executing {len(proposals)} proposed functional tests against source application...")
            executor = ProposedTestExecutor(
                job_id,
                evidence_dir=evidence_dir,
                log_fn=lambda m, level="INFO": self._log(job_id, f"[BASELINE] {m}", level),
                base_url=source_app_url,
            )

            for t in proposals:
                res = executor.execute_test(t, repo_dir=source_dir)
                t.baseline_execution_result = res
                self._log(job_id, f"[BASELINE] {t.id} -> {res.status.value}")

            try:
                from app.application.use_cases.proposed_tests.proposed_test_allure_reporter import ProposedTestAllureReporter
                baseline_reporter = ProposedTestAllureReporter(
                    job_id,
                    results_dir=paths.job_dir / "proposed-tests" / "allure-results-baseline",
                    report_dir=paths.job_dir / "proposed-tests" / "allure-report-baseline",
                )
                baseline_reporter.generate_allure_results(proposals)
                baseline_reporter.generate_html_report(proposals)
                self._log(job_id, "[BASELINE] Allure baseline report generated.")
            except Exception as a_err:  # noqa: BLE001
                self._log(job_id, f"[BASELINE] Notice generating Allure baseline report: {a_err}", "WARN")
        else:
            reason = "Source build failed" if not source_build_success else (source_readiness_error or "Source application unavailable")
            for t in proposals:
                t.baseline_execution_result = ExecutionResult(
                    status=ProposedTestStatus.NOT_EXECUTED,
                    error=reason,
                )

        if launched_pid:
            try:
                launcher.stop(launched_pid)
                self._log(job_id, f"[BASELINE] Stopped source application process (PID={launched_pid}).")
            except Exception as stop_exc:  # noqa: BLE001
                logger.warning(f"Failed to stop source app process {launched_pid}: {stop_exc}")
                logger.warning(f"Failed to stop source app process {launched_pid}: {stop_exc}")

        self._save_proposals(job_id, proposals)
        baseline_metrics = self._compute_metrics_for_baseline(proposals)

        payload = {
            "job_id": job_id,
            "status": "COMPLETED",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "source_build_success": source_build_success,
            "source_startup_status": source_startup_status,
            "source_readiness_status": source_readiness_status,
            "source_readiness_error": source_readiness_error,
            "source_base_url": source_app_url,
            "metrics": baseline_metrics.model_dump(),
            "allure_report_available": (paths.job_dir / "proposed-tests" / "allure-report-baseline" / "index.html").is_file(),
            "allure_report_url": f"/api/v1/migration/{job_id}/proposed-tests/allure-report-baseline/index.html"
            if (paths.job_dir / "proposed-tests" / "allure-report-baseline" / "index.html").is_file()
            else None,
            "test_cases": [p.model_dump() for p in proposals],
        }

        try:
            self._get_baseline_results_file(job_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to save baseline results file for {job_id}: {e}")

        self._log(
            job_id,
            f"[BASELINE] Pre-migration baseline complete. Executed: {baseline_metrics.executed}, "
            f"Passed: {baseline_metrics.passed}, Failed: {baseline_metrics.failed}."
        )
        return payload

    def _compute_metrics_for_baseline(self, proposals: list[ProposedTestCase]) -> ProposedTestMetrics:
        total = len(proposals)
        executed_tests = []
        passed = 0
        failed = 0
        skipped = 0
        app_unavail = 0

        for p in proposals:
            res = p.baseline_execution_result
            if res:
                if res.status == ProposedTestStatus.PASSED:
                    passed += 1
                    executed_tests.append(p)
                elif res.status == ProposedTestStatus.FAILED:
                    failed += 1
                    executed_tests.append(p)
                elif res.status == ProposedTestStatus.SKIPPED:
                    skipped += 1
                    executed_tests.append(p)
                elif res.status == ProposedTestStatus.APPLICATION_UNAVAILABLE:
                    app_unavail += 1

        executed = len(executed_tests)
        # not_executed for baseline: count only tests whose baseline_execution_result
        # is explicitly NOT_EXECUTED (i.e. valid tests that should have run but didn't).
        # Do NOT use subtraction — that would include duplicates/hallucinated tests
        # which never had a baseline_execution_result and are not execution candidates.
        not_executed = len([
            p for p in proposals
            if p.baseline_execution_result is not None
            and p.baseline_execution_result.status == ProposedTestStatus.NOT_EXECUTED
        ])
        pass_pct = f"{round((passed / executed * 100), 1)}%" if executed > 0 else "0%"

        unit_tests = [p for p in proposals if p.type == ProposedTestType.UNIT]
        api_tests = [p for p in proposals if p.type == ProposedTestType.API]
        ui_tests = [p for p in proposals if p.type == ProposedTestType.UI]

        return ProposedTestMetrics(
            total=total,
            executed=executed,
            passed=passed,
            failed=failed,
            skipped=skipped,
            not_executed=not_executed,
            pass_percentage=pass_pct,
            unit_metrics=ProposedTestTypeBreakdown(
                total=len(unit_tests),
                passed=len([p for p in unit_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.PASSED]),
                failed=len([p for p in unit_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.FAILED]),
                skipped=len([p for p in unit_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.SKIPPED]),
            ),
            api_metrics=ProposedTestTypeBreakdown(
                total=len(api_tests),
                passed=len([p for p in api_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.PASSED]),
                failed=len([p for p in api_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.FAILED]),
                skipped=len([p for p in api_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.SKIPPED]),
            ),
            ui_metrics=ProposedTestTypeBreakdown(
                total=len(ui_tests),
                passed=len([p for p in ui_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.PASSED]),
                failed=len([p for p in ui_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.FAILED]),
                skipped=len([p for p in ui_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.SKIPPED]),
            ),
        )

    def get_baseline_results(self, job_id: str) -> dict[str, Any] | None:
        bf = self._get_baseline_results_file(job_id)
        if bf.exists():
            try:
                return json.loads(bf.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                pass
        return None

    def get_comparison(self, job_id: str) -> ProposedTestComparisonResponse:
        """Compares pre-migration baseline results against target migrated application results."""
        proposals = self.get_proposed_tests(job_id)
        baseline_file = self._get_baseline_results_file(job_id)
        results_file = self._get_results_file(job_id)

        baseline_available = baseline_file.exists() or any(p.baseline_execution_result is not None for p in proposals)
        target_available = results_file.exists() or any(p.execution_result is not None for p in proposals)

        baseline_metrics = self._compute_metrics_for_baseline(proposals)
        target_metrics = self._compute_metrics(proposals)

        regressions = 0
        improvements = 0
        preserved_passed = 0
        comparisons: list[TestComparisonItem] = []

        for p in proposals:
            b_res = p.baseline_execution_result
            t_res = p.execution_result

            b_stat = b_res.status if b_res else ProposedTestStatus.NOT_EXECUTED
            t_stat = t_res.status if t_res else (
                p.status if p.status in [
                    ProposedTestStatus.PASSED,
                    ProposedTestStatus.FAILED,
                    ProposedTestStatus.SKIPPED,
                    ProposedTestStatus.APPLICATION_UNAVAILABLE,
                ] else ProposedTestStatus.NOT_EXECUTED
            )

            is_reg = (b_stat == ProposedTestStatus.PASSED and t_stat in [ProposedTestStatus.FAILED, ProposedTestStatus.APPLICATION_UNAVAILABLE])
            is_imp = (b_stat == ProposedTestStatus.FAILED and t_stat == ProposedTestStatus.PASSED)
            is_pres = (b_stat == ProposedTestStatus.PASSED and t_stat == ProposedTestStatus.PASSED)

            if is_reg:
                regressions += 1
            if is_imp:
                improvements += 1
            if is_pres:
                preserved_passed += 1

            comparisons.append(TestComparisonItem(
                id=p.id,
                title=p.title,
                type=p.type,
                source=p.source,
                baseline_status=b_stat,
                target_status=t_stat,
                match=(b_stat == t_stat),
                is_regression=is_reg,
                is_improvement=is_imp,
                baseline_duration=b_res.duration if b_res else "--",
                target_duration=t_res.duration if t_res else "--",
            ))

        b_pass = baseline_metrics.passed
        t_pass = target_metrics.passed
        parity_num = round((preserved_passed / b_pass * 100), 1) if b_pass > 0 else (100.0 if t_pass > 0 and regressions == 0 else 0.0)

        source_status: dict[str, Any] = {}
        if baseline_file.exists():
            try:
                b_data = json.loads(baseline_file.read_text(encoding="utf-8"))
                source_status = {
                    "build_success": b_data.get("source_build_success", False),
                    "startup_status": b_data.get("source_startup_status", "NOT_STARTED"),
                    "readiness_status": b_data.get("source_readiness_status", "NOT_STARTED"),
                    "base_url": b_data.get("source_base_url"),
                    "error": b_data.get("source_readiness_error"),
                }
            except Exception:  # noqa: BLE001
                pass

        target_status: dict[str, Any] = {}
        if results_file.exists():
            try:
                t_data = json.loads(results_file.read_text(encoding="utf-8"))
                target_status = {
                    "app_ready": t_data.get("app_ready", True),
                    "error": t_data.get("app_readiness_error"),
                }
            except Exception:  # noqa: BLE001
                pass

        return ProposedTestComparisonResponse(
            job_id=job_id,
            baseline_available=baseline_available,
            target_available=target_available,
            baseline_metrics=baseline_metrics,
            target_metrics=target_metrics,
            parity_percentage=f"{parity_num}%",
            regressions_count=regressions,
            improvements_count=improvements,
            preserved_passed_count=preserved_passed,
            source_status=source_status,
            target_status=target_status,
            test_comparisons=comparisons,
        )


proposed_test_service = ProposedTestService()

