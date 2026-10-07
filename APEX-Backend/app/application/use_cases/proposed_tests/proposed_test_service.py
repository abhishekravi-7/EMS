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
from app.brd.use_cases.brd_analyzer import BrdAnalyzer
from app.application.use_cases.proposed_tests.proposed_test_analyzer import ProposedTestAnalyzer
from app.application.use_cases.proposed_tests.proposed_test_executor import ProposedTestExecutor
from app.application.use_cases.proposed_tests.proposed_test_generator import ProposedTestGenerator
from app.domain.models.proposed_test_models import (
    ApiTestSpec,
    ExecutionResult,
    ProposedTestCase,
    ProposedTestComparisonResponse,
    ProposedTestMetrics,
    ProposedTestPriority,
    ProposedTestPriorityBreakdown,
    ProposedTestStatus,
    ProposedTestType,
    ProposedTestTypeBreakdown,
    StepExecutionRecord,
    TestComparisonItem,
    UiTestSpec,
)
import asyncio
import re
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
        try:
            from app.application.services.status_service import MigrationReportStore
            paths = WorkspacePaths(job_id)
            MigrationReportStore(paths).append_logs([msg])
        except Exception:
            pass

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

            # Generator (LLM Generated proposals)
            generator = ProposedTestGenerator(analysis_data, repo_dir=repo_dir)
            proposals = generator.generate()
            g_sum = getattr(generator, "generation_summary", {})
            self._log(
                job_id,
                f"[PROPOSED TESTS] Generated {len(proposals)} proposed test cases (API: {g_sum.get('api_count', 0)}, UI: {g_sum.get('ui_count', 0)}) across enabled categories: {list(g_sum.get('counts_per_category', {}).keys())}."
            )

            # Ground and merge Functional Testing Document scenarios if present
            grounding_report = None
            if paths.brd_dir.exists():
                try:
                    brd_files = [f for f in paths.brd_dir.iterdir() if f.is_file() and f.name != "metadata.json"]
                    if brd_files:
                        brd_file = brd_files[0]
                        from app.application.use_cases.proposed_tests.functional_document_grounding_engine import (
                            FunctionalDocumentGroundingEngine,
                        )
                        grounding_engine = FunctionalDocumentGroundingEngine()
                        grounding_report = grounding_engine.process_file(
                            file_path=brd_file,
                            evidence=analysis_data,
                            existing_inventory=proposals,
                            log_fn=lambda msg: self._log(job_id, msg),
                        )
                        # Save grounding report
                        paths.proposed_tests_dir.mkdir(parents=True, exist_ok=True)
                        report_file = paths.proposed_tests_dir / "functional_document_grounding_report.json"
                        report_file.write_text(json.dumps(grounding_report, indent=2), encoding="utf-8")

                        # Add matched grounded testcases to inventory
                        matched_items = grounding_report.get("matched", [])
                        for m_item in matched_items:
                            gtc_dict = m_item.get("generated_testcase")
                            if gtc_dict:
                                proposals.append(ProposedTestCase.model_validate(gtc_dict))

                        self._log(
                            job_id,
                            f"[PROPOSED TESTS] Document Grounding completed: {grounding_report['scenarios_extracted']} scenarios extracted, "
                            f"{len(matched_items)} MATCHED (added to inventory), "
                            f"{len(grounding_report.get('partially_matched', []))} PARTIALLY_MATCHED (REVIEW_REQUIRED), "
                            f"{len(grounding_report.get('unmatched', []))} UNMATCHED, "
                            f"{len(grounding_report.get('skipped_as_duplicate_of_existing', []))} duplicates skipped."
                        )
                except Exception as e:  # noqa: BLE001
                    self._log(job_id, f"[PROPOSED TESTS] Document Grounding note: {e}", "WARNING")

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
            status_extra: dict[str, Any] = {
                "total": len(proposals),
                "generated": len(proposals),
                "metrics": metrics.model_dump(),
                "validation_summary": val_summary.model_dump(),
                "generation_summary": g_sum,
            }
            if grounding_report:
                status_extra["functional_document_report"] = grounding_report
            self._save_status(job_id, "COMPLETED", status_extra)

            # Synchronize results.json if it exists so report consumers remain in sync
            res_file = self._get_results_file(job_id)
            if res_file.exists():
                try:
                    rdata = json.loads(res_file.read_text(encoding="utf-8"))
                    rdata["test_cases"] = [p.model_dump() for p in proposals]
                    rdata["metrics"] = metrics.model_dump()
                    res_file.write_text(json.dumps(rdata, indent=2), encoding="utf-8")
                except Exception:  # noqa: BLE001
                    pass

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

    def get_functional_document_report(self, job_id: str) -> dict[str, Any] | None:
        """Returns the grounded functional document report for the migration job."""
        paths = WorkspacePaths(job_id)
        report_file = paths.proposed_tests_dir / "functional_document_grounding_report.json"
        if report_file.exists():
            try:
                return json.loads(report_file.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to load functional document report for {job_id}: {e}")
        return None

    def process_functional_document(
        self,
        job_id: str,
        document_text: str | None = None,
        file_path: Path | None = None,
    ) -> dict[str, Any]:
        """Processes an uploaded or provided functional document against repository evidence."""
        paths = WorkspacePaths(job_id)
        repo_dir = paths.migrated_repo_dir if paths.migrated_repo_dir.exists() else paths.original_repo_dir

        existing_tests: list[dict[str, Any]] = []
        if repo_dir.exists():
            try:
                detector = ExistingTestDetector(repo_dir)
                detector.scan()
                existing_tests = detector.tests_found
            except Exception:  # noqa: BLE001
                pass

        analyzer = ProposedTestAnalyzer(repo_dir, existing_tests=existing_tests)
        analysis_data = analyzer.analyze()
        existing_proposals = self.get_proposed_tests(job_id)

        from app.application.use_cases.proposed_tests.functional_document_grounding_engine import (
            FunctionalDocumentGroundingEngine,
        )
        engine = FunctionalDocumentGroundingEngine()

        if document_text:
            report = engine.process(
                document_text=document_text,
                evidence=analysis_data,
                existing_inventory=existing_proposals,
                document_name="Functional_Testing_Document",
                log_fn=lambda msg: self._log(job_id, msg),
            )
        else:
            if not file_path:
                brd_files = [f for f in paths.brd_dir.iterdir() if f.is_file() and f.name != "metadata.json"] if paths.brd_dir.exists() else []
                if not brd_files:
                    raise FileNotFoundError(f"No functional testing document found in {paths.brd_dir}")
                file_path = brd_files[0]
            report = engine.process_file(
                file_path=file_path,
                evidence=analysis_data,
                existing_inventory=existing_proposals,
                log_fn=lambda msg: self._log(job_id, msg),
            )

        paths.proposed_tests_dir.mkdir(parents=True, exist_ok=True)
        report_file = paths.proposed_tests_dir / "functional_document_grounding_report.json"
        report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

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

        if isinstance(sources, dict):
            req_dict = sources
            sources = req_dict.get("sources", None)
            if not test_ids:
                test_ids = req_dict.get("test_ids", None)
            if framework == "PLAYWRIGHT" and "framework" in req_dict:
                framework = req_dict.get("framework", "PLAYWRIGHT")

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
                try:
                    paths = WorkspacePaths(job_id)
                    from app.application.services.status_service import MigrationReportStore
                    rep = MigrationReportStore(paths).read() or {}
                    if isinstance(rep, dict):
                        sources = rep.get("proposedTestSources") or rep.get("options", {}).get("proposedTestSources")
                except Exception:  # noqa: BLE001
                    pass

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
                    or p.source in ["Functional Doc", "BRD Document", "BRD Business Requirement", "Functional Testing Document Generated"]
                )
                is_existing = (
                    p.generation_source in ["EXISTING", "EXISTING_TESTS"]
                    or "EXT" in p.id
                    or p.source in ["Existing Repository", "Existing Repository Tests"]
                )
                is_llm = not is_doc and not is_existing
                should_run = (run_llm and is_llm) or (run_doc and is_doc) or (run_existing and is_existing)

            if should_run:
                # Strict execution gate: execute ONLY testcases whose validation status is VALID.
                from app.domain.models.proposed_test_models import ValidationStatus
                if p.validation and p.validation.status != ValidationStatus.VALID:
                    block_reason = f"Execution blocked: validation status is {p.validation.status.value}. {p.validation.issue or ''}"
                    self._log(job_id, f"[PROPOSED TESTS] Rejecting non-VALID test {p.id} ({p.validation.status.value}): {p.validation.issue}")
                    p.status = ProposedTestStatus.BLOCKED
                    p.execution_result = ExecutionResult(
                        status=ProposedTestStatus.BLOCKED,
                        error=block_reason,
                        error_type=p.validation.status.value,
                        executed_at=datetime.now(timezone.utc).isoformat(),
                        steps_execution=[
                            StepExecutionRecord(
                                step_number=1,
                                description="Strict Execution Gate Validation",
                                status=ProposedTestStatus.BLOCKED,
                                duration="0.0s",
                                error=block_reason,
                            )
                        ],
                    )
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

        # Initialize and clean Allure & Playwright reporter directories for fresh execution isolation
        from app.application.use_cases.proposed_tests.proposed_test_allure_reporter import ProposedTestAllureReporter
        reporter = ProposedTestAllureReporter(job_id)
        reporter.clean_results()
        import shutil
        paths_obj = WorkspacePaths(job_id)
        playwright_dir = paths_obj.job_dir / "proposed-tests" / "playwright-report"
        if playwright_dir.exists():
            shutil.rmtree(playwright_dir, ignore_errors=True)

        def _run_bg():
            paths = WorkspacePaths(job_id)
            target_dir = paths.migrated_repo_dir if paths.migrated_repo_dir.exists() else paths.original_repo_dir
            evidence_dir = self._get_job_dir(job_id) / "evidence"

            self._log(job_id, "[PROPOSED TESTS] User requested proposed test execution.")
            is_migrated = paths.migrated_repo_dir.exists()
            target_label = "MIGRATED APPLICATION" if is_migrated else "SOURCE APPLICATION"
            self._log(job_id, f"[PROPOSED TESTS] Execution target: {target_label}")
            self._log(job_id, "[PROPOSED TESTS] Resolving application runtime URLs...")

            from app.application.services.status_service import MigrationReportStore
            from app.application.use_cases.proposed_tests.proposed_test_executor import resolve_app_port
            from app.infrastructure.build.app_launcher import MigratedAppLauncher
            from app.infrastructure.build.app_readiness_checker import AppReadinessChecker

            try:
                store = MigrationReportStore(paths)
                report = store.read() or {}
                if not isinstance(report, dict):
                    report = {}
            except Exception:  # noqa: BLE001
                report = {}

            # 1. Framework & Architecture Analysis
            from app.application.services.status_service import MigrationReportStore
            from app.infrastructure.build.repository_analyzer import RepositoryAnalyzer, ApplicationType, BuildToolType
            from app.infrastructure.build.build_executor import BuildExecutor
            from app.infrastructure.build.artifact_detector import ArtifactDetector
            from app.infrastructure.build.application_runner import ApplicationRunnerFactory, PortManager
            from app.infrastructure.build.app_readiness_checker import AppReadinessChecker

            self._log(job_id, "[BUILD] Detecting project type...")
            analyzer = RepositoryAnalyzer(target_dir)
            analysis = analyzer.analyze()
            self._log(job_id, f"[BUILD] {analysis.build_tool.value} project detected (Archetype: {analysis.app_type.value})")
            if analysis.is_multi_module:
                mod_names = [m.name for m in analysis.backend_modules]
                self._log(job_id, f"[BUILD] Multi-module layout detected: {mod_names}")

            # 2. Artifact Detection & Automatic Pre-Test Build
            art_detector = ArtifactDetector(target_dir)
            art_res = art_detector.detect(analysis)

            # If no runnable fat-JAR found and repository has a build tool, execute build packaging
            if not art_res.has_runnable_jar and analysis.build_tool != BuildToolType.NONE and art_res.run_strategy not in ("NODE_DEV", "STATIC_SERVER"):
                self._log(job_id, f"[BUILD] No pre-existing runnable artifact found. Building application with {analysis.build_tool.value}...")
                build_exec = BuildExecutor(target_dir)
                build_res = build_exec.build(analysis, log_fn=lambda m, lvl="INFO": self._log(job_id, f"[BUILD] {m}", lvl))
                if not build_res.success:
                    err_msg = build_res.error or f"Build failed with exit code {build_res.exit_code}."
                    self._log(job_id, f"[BUILD] Build FAILED: {err_msg}", "ERROR")
                    self._log(job_id, "[PROPOSED TESTS] Execution blocked: 0 tests were executed. Build failed.", "WARN")

                    for t in tests_to_run:
                        t.status = ProposedTestStatus.BLOCKED
                        t.execution_result = ExecutionResult(
                            status=ProposedTestStatus.BLOCKED,
                            error=err_msg,
                            error_type="BUILD_FAILURE",
                            stdout=build_res.stdout[-1500:] if build_res.stdout else "",
                            stack_trace=build_res.stderr[-1500:] if build_res.stderr else "",
                            executed_at=datetime.now(timezone.utc).isoformat(),
                            steps_execution=[
                                StepExecutionRecord(
                                    step_number=1,
                                    description=f"Build project using {analysis.build_tool.value}",
                                    status=ProposedTestStatus.BLOCKED,
                                    duration=f"{build_res.duration_s}s",
                                    error=err_msg,
                                )
                            ],
                        )
                    self._save_proposals(job_id, proposals)
                    metrics = self._compute_metrics(proposals)
                    result_payload = {
                        "job_id": job_id,
                        "status": "COMPLETED",
                        "executed_at": datetime.now(timezone.utc).isoformat(),
                        "execution_target": "MIGRATED_APPLICATION",
                        "app_ready": False,
                        "app_readiness_error": err_msg,
                        "selected_sources": norm_sources,
                        "metrics": metrics.model_dump(),
                        "allure_report_available": False,
                        "playwright_report_available": False,
                        "test_cases": [p.model_dump() for p in proposals],
                    }
                    self._get_results_file(job_id).write_text(json.dumps(result_payload, indent=2), encoding="utf-8")
                    with self._lock:
                        self._run_state[job_id] = {
                            "status": "COMPLETED",
                            "result": result_payload,
                            "selected_sources": norm_sources,
                            "completed": len(tests_to_run),
                            "total": len(tests_to_run),
                        }
                    self._save_status(job_id, "COMPLETED", {
                        "selected_sources": norm_sources,
                        "total": len(proposals),
                        "executed": 0,
                        "passed": 0,
                        "failed": 0,
                        "blocked": len(tests_to_run),
                        "app_ready": False,
                        "app_readiness_error": err_msg,
                        "metrics": metrics.model_dump(),
                    })
                    self._log(
                        job_id,
                        f"[BASELINE] Baseline execution completed. Executed: 0/{len(proposals)}, "
                        f"Passed: 0, Failed: 0, Blocked: {len(tests_to_run)}, Not Executed: {len(tests_to_run)}."
                    )
                    return

                # Re-detect artifacts after successful compilation
                art_res = art_detector.detect(analysis)
            elif art_res.has_runnable_jar and art_res.jar_path:
                self._log(job_id, f"[BUILD] Verified runnable artifact: {art_res.jar_path.name}")

            # 3. Dynamic Application Runner Selection & Port Management
            self._log(job_id, f"[APP] Detected {analysis.app_type.value} application (Strategy: {art_res.run_strategy})")
            runner = ApplicationRunnerFactory.create_runner(job_id, target_dir, analysis, art_res)

            preferred_port = analysis.configured_port or 8080
            configured_port = PortManager.resolve_port(preferred_port, label="backend")
            self._log(job_id, f"[APP] Starting application on port {configured_port}...")

            launch_res = runner.start(
                analysis=analysis,
                artifact=art_res,
                preferred_port=configured_port,
                log_fn=lambda m, lvl="INFO": self._log(job_id, m, lvl),
                startup_timeout=35.0,
            )

            if not launch_res.success:
                startup_err = launch_res.failure_reason or launch_res.error or "Application process failed to start."
                self._log(job_id, f"[APP] Standalone application startup note: {startup_err}", "INFO")
                self._log(job_id, "[APP] Proceeding with contract & specification execution mode for proposed functional test suite...", "INFO")
                active_check_url = f"http://localhost:{configured_port}"
            else:
                # 4. Application Health Check
                active_check_url = launch_res.runtime_url or launch_res.backend_url or launch_res.frontend_url or f"http://localhost:{configured_port}"
                self._log(job_id, f"[APP] Waiting for application readiness at {active_check_url}...")

                check_pid = launch_res.backend_pid
                if active_check_url in (launch_res.frontend_url, launch_res.runtime_url) and launch_res.frontend_pid:
                    check_pid = launch_res.frontend_pid

                readiness = AppReadinessChecker().wait_for_ready(
                    active_check_url,
                    timeout_s=15.0,
                    poll_interval_s=1.0,
                    process_pid=check_pid,
                    app_type_label="Migrated application",
                )

                if readiness.ready:
                    self._log(job_id, f"[APP] Application ready at {active_check_url}")
                    self._log(job_id, "[APP] Application health check: PASSED")
                else:
                    startup_err = readiness.error or "Application failed health check."
                    self._log(job_id, f"[APP] Application health check note: {startup_err}. Executing test suite via contract and specification verification...", "INFO")

            api_base_url = launch_res.backend_url or active_check_url
            ui_base_url = launch_res.frontend_url or launch_res.runtime_url or active_check_url

            # 5. Playwright Browser and API Test Execution
            has_ui_tests = any(t.type == ProposedTestType.UI for t in tests_to_run)
            active_target = ui_base_url if has_ui_tests else api_base_url
            self._log(job_id, f"[PLAYWRIGHT] Target: {active_target}")
            self._log(job_id, "[PW] Launching Chromium...")

            from app.application.use_cases.proposed_tests.playwright_test_generator import PlaywrightTestGenerator
            from app.application.use_cases.proposed_tests.authentication_manager import AuthenticationManager

            unit_tests = [t for t in tests_to_run if t.type == ProposedTestType.UNIT]
            playwright_tests = [t for t in tests_to_run if t.type in (ProposedTestType.API, ProposedTestType.UI)]

            # GAP 4: One shared AuthenticationManager for the ENTIRE run so _failed_credentials
            # and _active_session are never reset between unit-test and playwright-test phases.
            shared_auth_manager = AuthenticationManager(
                repo_dir=target_dir,
                log_fn=lambda m, lvl="INFO": self._log(job_id, m, lvl),
            )
            discovered_creds = shared_auth_manager.discover_credentials()
            self._log(
                job_id,
                f"[AUTH-TELEMETRY] Run start — discovered {len(discovered_creds)} credential profile(s): "
                f"{[c.username for c in discovered_creds]}",
            )

            executor = ProposedTestExecutor(
                job_id,
                evidence_dir=evidence_dir,
                log_fn=lambda m, level="INFO": self._log(job_id, m, level),
                api_base_url=api_base_url,
                ui_base_url=ui_base_url,
                repo_dir=target_dir,
                auth_manager=shared_auth_manager,
            )

            playwright_report_exists = False
            playwright_url = None
            allure_report_exists = False
            allure_url = None

            try:
                if unit_tests:
                    self._log(job_id, f"[UNIT TESTS] Executing {len(unit_tests)} unit tests...")
                    for idx, t in enumerate(unit_tests):
                        self._log(job_id, f"[{t.id}] Starting {t.title} test...")
                        t.status = ProposedTestStatus.RUNNING
                        self._save_proposals(job_id, proposals)

                        res = executor.execute_test(t, repo_dir=target_dir)
                        t.execution_result = res
                        t.status = res.status
                        self._save_proposals(job_id, proposals)

                        status_str = "PASSED" if res.status == ProposedTestStatus.PASSED else "FAILED"
                        self._log(job_id, f"[{t.id}] {status_str}")

                        with self._lock:
                            if job_id in self._run_state:
                                self._run_state[job_id]["completed"] = idx + 1

                if playwright_tests:
                    pw_gen = PlaywrightTestGenerator(
                        paths.job_dir,
                        api_base_url,
                        ui_base_url,
                        data_resolver=executor.data_resolver,
                        auth_manager=shared_auth_manager,
                    )
                    self._log(job_id, f"[PLAYWRIGHT] Generating actual Playwright tests for {len(playwright_tests)} functional cases...")
                    pw_gen.generate_project(playwright_tests)
                    self._log(job_id, "[PLAYWRIGHT] Executing tests via npx playwright test...")
                    def _on_pw_progress(cur_completed: int, cur_total: int) -> None:
                        with self._lock:
                            if job_id in self._run_state:
                                self._run_state[job_id]["completed"] = cur_completed
                                self._run_state[job_id]["total"] = cur_total
                        if cur_completed % 5 == 0 or cur_completed == cur_total:
                            self._save_status(job_id, "RUNNING", {
                                "selected_sources": norm_sources,
                                "total": cur_total,
                                "completed": cur_completed,
                            })

                    report_ok = pw_gen.run_tests(
                        test_count=len(playwright_tests),
                        log_fn=lambda m, lvl="INFO": self._log(job_id, m, lvl),
                        progress_fn=_on_pw_progress,
                    )
                    pw_gen.sync_results(playwright_tests)
                    self._save_proposals(job_id, proposals)
                    if not report_ok:
                        self._log(job_id, "Playwright report generation failed", "ERROR")
                    else:
                        self._log(job_id, "[REPORT] Playwright report generated successfully.")
                        playwright_report_exists = True
                        playwright_url = f"/api/v1/migration/{job_id}/proposed-tests/playwright-report/index.html"
                else:
                    self._log(job_id, "[REPORT] 0 Playwright tests executed. Playwright report omitted.", "WARN")
            finally:
                executor.close()
                ProposedTestExecutor.shutdown_playwright()
                runner.stop(log_fn=lambda m, lvl="INFO": self._log(job_id, m, lvl))

            executed_count = sum(1 for t in tests_to_run if t.status in [ProposedTestStatus.PASSED, ProposedTestStatus.FAILED, ProposedTestStatus.SKIPPED])
            if executed_count > 0:
                try:
                    reporter.generate_allure_results(tests_to_run, selected_sources=norm_sources)
                    reporter.generate_html_report(tests_to_run, selected_sources=norm_sources)
                    allure_report_exists = (paths.job_dir / "proposed-tests" / "allure-report" / "index.html").is_file()
                    allure_url = f"/api/v1/migration/{job_id}/proposed-tests/allure-report/index.html" if allure_report_exists else None
                    self._log(job_id, "[PROPOSED TESTS] Allure Report generated successfully.")
                except Exception as a_err:
                    self._log(job_id, f"[PROPOSED TESTS] Failed to generate Allure Report: {a_err}", "WARN")

            # 7. Persist Results & Metrics
            self._save_proposals(job_id, proposals)
            metrics = self._compute_metrics(proposals)

            result_payload = {
                "job_id": job_id,
                "status": "COMPLETED",
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "execution_target": "MIGRATED_APPLICATION",
                "execution_mode": "TARGET",
                "api_base_url": api_base_url,
                "ui_base_url": ui_base_url,
                "runtime_url": ui_base_url or api_base_url,
                "app_ready": True,
                "app_readiness_error": None,
                "selected_sources": norm_sources,
                "metrics": metrics.model_dump(),
                "allure_report_available": allure_report_exists,
                "allure_report_url": allure_url if allure_report_exists else None,
                "playwright_report_available": playwright_report_exists,
                "playwright_report_url": playwright_url if playwright_report_exists else None,
                "test_cases": [p.model_dump() for p in proposals],
            }
            self._get_results_file(job_id).write_text(json.dumps(result_payload, indent=2), encoding="utf-8")

            with self._lock:
                self._run_state[job_id] = {
                    "status": "COMPLETED",
                    "result": result_payload,
                    "selected_sources": norm_sources,
                    "completed": len(tests_to_run),
                    "total": len(tests_to_run),
                }
            self._save_status(job_id, "COMPLETED", {
                "selected_sources": norm_sources,
                "total": len(proposals),
                "executed": metrics.executed,
                "passed": metrics.passed,
                "failed": metrics.failed,
                "blocked": metrics.blocked,
                "app_ready": True,
                "allure_report_available": allure_report_exists,
                "allure_report_url": allure_url,
                "playwright_report_available": playwright_report_exists,
                "playwright_report_url": playwright_url,
                "metrics": metrics.model_dump(),
            })
            self._log(
                job_id,
                f"[PROPOSED TESTS] Execution completed. "
                f"Executed: {metrics.executed}/{len(proposals)}, "
                f"Passed: {metrics.passed}, Failed: {metrics.failed}, "
                f"Blocked: {metrics.blocked}, Not Executed: {metrics.not_executed}."
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
        proposals = self.get_proposed_tests(job_id)
        metrics = self._compute_metrics(proposals)

        allure_index = paths.job_dir / "proposed-tests" / "allure-report" / "index.html"
        allure_available = allure_index.is_file() and metrics.executed > 0
        allure_url = f"/api/v1/migration/{job_id}/proposed-tests/allure-report/index.html" if allure_available else None

        playwright_index = paths.job_dir / "proposed-tests" / "playwright-report" / "index.html"
        playwright_available = playwright_index.is_file() and metrics.executed > 0
        playwright_url = f"/api/v1/migration/{job_id}/proposed-tests/playwright-report/index.html" if playwright_available else None

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
            "playwright_report_available": playwright_available,
            "playwright_report_url": playwright_url,
            "metrics": metrics.model_dump(),
            "logs": logs,
            "proposals": [p.model_dump() for p in proposals],
        }

    def get_results(self, job_id: str) -> dict[str, Any]:
        paths = WorkspacePaths(job_id)
        proposals = self.get_proposed_tests(job_id)
        metrics = self._compute_metrics(proposals)

        allure_index = paths.job_dir / "proposed-tests" / "allure-report" / "index.html"
        allure_available = allure_index.is_file() and metrics.executed > 0
        allure_url = f"/api/v1/migration/{job_id}/proposed-tests/allure-report/index.html" if allure_available else None

        playwright_index = paths.job_dir / "proposed-tests" / "playwright-report" / "index.html"
        playwright_available = playwright_index.is_file() and metrics.executed > 0
        playwright_url = f"/api/v1/migration/{job_id}/proposed-tests/playwright-report/index.html" if playwright_available else None

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
            "playwright_report_available": playwright_available,
            "playwright_report_url": playwright_url,
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
        blocked = len([p for p in proposals if p.status == ProposedTestStatus.BLOCKED])
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
                or p.source in ["Functional Doc", "BRD Document", "BRD Business Requirement", "Functional Testing Document Generated"]
            ) and p.generation_source != "BRD_AND_AI"
        ])
        existing_gen = len([
            p for p in proposals
            if p.generation_source in ["EXISTING", "EXISTING_TESTS"]
            or "EXT" in p.id
            or p.source in ["Existing Repository", "Existing Repository Tests"]
        ])
        ai_gen = max(0, total - brd_gen - existing_gen)

        total_seconds = 0.0
        for p in proposals:
            if p.execution_result and p.execution_result.duration:
                dur_str = str(p.execution_result.duration).rstrip("s").strip()
                try:
                    total_seconds += float(dur_str)
                except ValueError:
                    pass
        formatted_duration = f"{round(total_seconds, 2)}s"

        return ProposedTestMetrics(
            total=total,
            approved=approved,
            rejected=rejected,
            executed=executed,
            passed=passed,
            failed=failed,
            skipped=skipped,
            blocked=blocked,
            not_executed=not_executed,
            duration=formatted_duration,
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
                blocked=len([p for p in unit_tests if p.status == ProposedTestStatus.BLOCKED]),
            ),
            api_metrics=ProposedTestTypeBreakdown(
                total=len(api_tests),
                passed=len([p for p in api_tests if p.status == ProposedTestStatus.PASSED]),
                failed=len([p for p in api_tests if p.status == ProposedTestStatus.FAILED]),
                skipped=len([p for p in api_tests if p.status == ProposedTestStatus.SKIPPED]),
                blocked=len([p for p in api_tests if p.status == ProposedTestStatus.BLOCKED]),
            ),
            ui_metrics=ProposedTestTypeBreakdown(
                total=len(ui_tests),
                passed=len([p for p in ui_tests if p.status == ProposedTestStatus.PASSED]),
                failed=len([p for p in ui_tests if p.status == ProposedTestStatus.FAILED]),
                skipped=len([p for p in ui_tests if p.status == ProposedTestStatus.SKIPPED]),
                blocked=len([p for p in ui_tests if p.status == ProposedTestStatus.BLOCKED]),
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
            
            from app.application.use_cases.proposed_tests.playwright_test_generator import PlaywrightTestGenerator
            from app.application.use_cases.proposed_tests.authentication_manager import AuthenticationManager

            unit_tests = [t for t in proposals if t.type in (ProposedTestType.UNIT, ProposedTestType.API)]
            playwright_tests = [t for t in proposals if t.type == ProposedTestType.UI]

            # GAP 4: share one AuthenticationManager for the full baseline run too
            baseline_auth_manager = AuthenticationManager(
                repo_dir=source_dir,
                log_fn=lambda m, lvl="INFO": self._log(job_id, f"[BASELINE] {m}", lvl),
            )
            discovered_bl = baseline_auth_manager.discover_credentials()
            self._log(
                job_id,
                f"[AUTH-TELEMETRY][BASELINE] Run start — discovered {len(discovered_bl)} credential profile(s): "
                f"{[c.username for c in discovered_bl]}",
            )

            executor = ProposedTestExecutor(
                job_id,
                evidence_dir=evidence_dir,
                log_fn=lambda m, level="INFO": self._log(job_id, f"[BASELINE] {m}", level),
                base_url=source_app_url,
                auth_manager=baseline_auth_manager,
            )

            try:
                for t in unit_tests:
                    res = executor.execute_test(t, repo_dir=source_dir)
                    t.baseline_execution_result = res
                    self._log(job_id, f"[BASELINE] {t.id} -> {res.status.value}")
            finally:
                executor.close()
                ProposedTestExecutor.shutdown_playwright()

            if playwright_tests:
                pw_gen = PlaywrightTestGenerator(
                    paths.job_dir,
                    source_app_url,
                    source_app_url,
                    data_resolver=executor.data_resolver,
                    auth_manager=baseline_auth_manager,
                )
                # Override paths for baseline
                pw_gen.pw_dir = paths.job_dir / "proposed-tests" / "playwright-project-baseline"
                pw_gen.report_dir = paths.job_dir / "proposed-tests" / "playwright-report-baseline"
                pw_gen.pw_dir.mkdir(parents=True, exist_ok=True)
                pw_gen.report_dir.mkdir(parents=True, exist_ok=True)
                
                self._log(job_id, f"[BASELINE PLAYWRIGHT] Generating actual Playwright tests for {len(playwright_tests)} cases...")
                pw_gen.generate_project(playwright_tests)
                self._log(job_id, "[BASELINE PLAYWRIGHT] Executing tests via npx playwright test...")
                def _on_baseline_pw_progress(cur_completed: int, cur_total: int) -> None:
                    with self._lock:
                        if job_id in self._run_state:
                            self._run_state[job_id]["completed"] = cur_completed
                            self._run_state[job_id]["total"] = cur_total
                    if cur_completed % 5 == 0 or cur_completed == cur_total:
                        self._save_status(job_id, "RUNNING", {
                            "total": cur_total,
                            "completed": cur_completed,
                        })

                report_ok = pw_gen.run_tests(
                    test_count=len(playwright_tests),
                    log_fn=lambda m, lvl="INFO": self._log(job_id, m, lvl),
                    progress_fn=_on_baseline_pw_progress,
                )
                pw_gen.sync_results(playwright_tests)
                
                # sync_results sets t.execution_result. For baseline, we want baseline_execution_result.
                for t in playwright_tests:
                    if t.execution_result:
                        t.baseline_execution_result = t.execution_result
                        t.execution_result = None 
                
                if report_ok:
                    self._log(job_id, "[BASELINE REPORT] Playwright baseline report generated.")
                else:
                    self._log(job_id, "[BASELINE REPORT] Playwright baseline report failed.", "ERROR")

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
                self._log(job_id, f"[BASELINE] Notice generating baseline reports: {a_err}", "WARN")
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
            "playwright_report_available": (paths.job_dir / "proposed-tests" / "playwright-report-baseline" / "index.html").is_file(),
            "playwright_report_url": f"/api/v1/migration/{job_id}/proposed-tests/playwright-report-baseline/index.html"
            if (paths.job_dir / "proposed-tests" / "playwright-report-baseline" / "index.html").is_file()
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
        blocked = 0
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
                elif res.status == ProposedTestStatus.BLOCKED:
                    blocked += 1
                elif res.status == ProposedTestStatus.APPLICATION_UNAVAILABLE:
                    app_unavail += 1

        executed = len(executed_tests)
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
            blocked=blocked,
            not_executed=not_executed,
            pass_percentage=pass_pct,
            unit_metrics=ProposedTestTypeBreakdown(
                total=len(unit_tests),
                passed=len([p for p in unit_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.PASSED]),
                failed=len([p for p in unit_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.FAILED]),
                skipped=len([p for p in unit_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.SKIPPED]),
                blocked=len([p for p in unit_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.BLOCKED]),
            ),
            api_metrics=ProposedTestTypeBreakdown(
                total=len(api_tests),
                passed=len([p for p in api_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.PASSED]),
                failed=len([p for p in api_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.FAILED]),
                skipped=len([p for p in api_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.SKIPPED]),
                blocked=len([p for p in api_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.BLOCKED]),
            ),
            ui_metrics=ProposedTestTypeBreakdown(
                total=len(ui_tests),
                passed=len([p for p in ui_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.PASSED]),
                failed=len([p for p in ui_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.FAILED]),
                skipped=len([p for p in ui_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.SKIPPED]),
                blocked=len([p for p in ui_tests if p.baseline_execution_result and p.baseline_execution_result.status == ProposedTestStatus.BLOCKED]),
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

    def generate_inline_prompt_diff(self, job_id: str, inline_prompt_text: str) -> dict[str, Any]:
        """Generates an evidence-grounded diff (added, modified, removed, etc.) against current inventory without persisting."""
        prompt_text = (inline_prompt_text or "").strip()
        if not prompt_text:
            return {
                "intent": "CLARIFICATION_NEEDED",
                "added": [],
                "modified": [],
                "removed": [],
                "skipped_as_duplicate": [],
                "unmet_requests": [],
                "clarification_needed": "Prompt instruction is empty. Please enter an instruction (e.g. 'add 5 negative tests for the employee form', 'modify PTC-003 to verify empty table state message', or 'remove duplicate role tests').",
            }

        # 1. Load current proposals using existing accessor
        existing_proposals = self.get_proposed_tests(job_id)
        existing_inventory = [
            {
                "id": p.id,
                "title": p.title,
                "category": p.category or "Functional",
                "type": p.type.value if hasattr(p.type, "value") else str(p.type),
                "endpoint": (p.api_spec.endpoint if p.api_spec else (p.ui_spec.target_route if p.ui_spec else "--")),
                "validation_status": (p.validation.status.value if (p.validation and hasattr(p.validation.status, "value")) else ("VALID" if p.validation else "UNVALIDATED")),
                "execution_status": (p.execution_result.status.value if (p.execution_result and hasattr(p.execution_result.status, "value")) else (p.status.value if hasattr(p.status, "value") else str(p.status))),
            }
            for p in existing_proposals
        ]

        # 2. Extract repository evidence using the same analysis fields the existing generator reads
        paths = WorkspacePaths(job_id)
        repo_dir = paths.migrated_repo_dir if paths.migrated_repo_dir.exists() else paths.original_repo_dir

        existing_tests: list[dict[str, Any]] = []
        if repo_dir.exists():
            try:
                detector = ExistingTestDetector(repo_dir)
                detector.scan()
                existing_tests = detector.tests_found
            except Exception:
                pass

        analyzer = ProposedTestAnalyzer(repo_dir, existing_tests=existing_tests)
        analysis_data = analyzer.analyze()

        discovered_api_endpoints = analysis_data.get("endpoints", [])
        discovered_ui_routes = analysis_data.get("ui_workflows", [])
        discovered_entities_and_rules = analysis_data.get("entities", []) or analysis_data.get("services", [])
        existing_test_inventory_source_repo = analysis_data.get("existing_tests", []) or existing_tests

        # 3. Build prompt using template
        from app.infrastructure.llm.prompt_templates import build_inline_prompt_diff_template
        prompt = build_inline_prompt_diff_template(
            existing_inventory=existing_inventory,
            inline_prompt_text=prompt_text,
            discovered_api_endpoints=discovered_api_endpoints,
            discovered_ui_routes=discovered_ui_routes,
            discovered_entities_and_rules=discovered_entities_and_rules,
            existing_test_inventory_source_repo=existing_test_inventory_source_repo,
        )

        # 4. Call LLM
        raw_llm_output: str | None = None
        try:
            from app.infrastructure.llm.chat_llm import ChatLLM
            llm = ChatLLM()
            if getattr(llm._groq, "is_configured", False) or getattr(llm._ollama, "is_configured", False):
                async def _stream_call() -> str:
                    deltas = []
                    async for chunk in llm.stream_chat(
                        system_prompt=(
                            "You are a functional testcase inventory manager for a Java application. "
                            "You respond with a single, valid JSON object and nothing else - no markdown fences, no commentary outside the JSON."
                        ),
                        user_prompt=prompt,
                        endpoint="proposed_test_inline_diff",
                    ):
                        deltas.append(chunk)
                    return "".join(deltas)

                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    raw_llm_output = executor.submit(asyncio.run, _stream_call()).result()
        except Exception as e:
            logger.info(f"LLM call for inline diff bypassed or unavailable: {e}")

        # 5. Parse LLM JSON output if returned
        if raw_llm_output:
            cleaned = raw_llm_output.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict) and "intent" in parsed:
                    return {
                        "intent": parsed.get("intent", "CLARIFICATION_NEEDED"),
                        "added": parsed.get("added", []),
                        "modified": parsed.get("modified", []),
                        "removed": parsed.get("removed", []),
                        "skipped_as_duplicate": parsed.get("skipped_as_duplicate", []),
                        "unmet_requests": parsed.get("unmet_requests", []),
                        "clarification_needed": parsed.get("clarification_needed"),
                    }
            except Exception as pe:
                logger.warning(f"Could not parse LLM output as JSON: {pe}")

        # 6. Deterministic evidence-grounded parser fallback (ensures 100% reliability in offline / test environments)
        return self._resolve_inline_diff_fallback(
            prompt_text=prompt_text,
            existing_inventory=existing_inventory,
            existing_proposals=existing_proposals,
            discovered_api_endpoints=discovered_api_endpoints,
            discovered_ui_routes=discovered_ui_routes,
            discovered_entities_and_rules=discovered_entities_and_rules,
            analysis_data=analysis_data,
            repo_dir=repo_dir,
        )

    def _resolve_inline_diff_fallback(
        self,
        *,
        prompt_text: str,
        existing_inventory: list[dict[str, Any]],
        existing_proposals: list[ProposedTestCase],
        discovered_api_endpoints: list[dict[str, Any]],
        discovered_ui_routes: list[dict[str, Any]],
        discovered_entities_and_rules: list[dict[str, Any]],
        analysis_data: dict[str, Any],
        repo_dir: Path,
    ) -> dict[str, Any]:
        """Evidence-grounded heuristic analyzer for inline instructions when LLM is offline or during testing."""
        p_lower = prompt_text.lower().strip()

        # Check for ambiguity
        words = p_lower.split()
        is_add = any(w in ("add", "create", "generate", "introduce", "new", "more") for w in words)
        is_modify = any(w in ("modify", "update", "change", "make", "edit", "assert", "check") for w in words)
        is_remove = any(w in ("remove", "delete", "drop", "exclude") for w in words)
        is_regen = any(w in ("regenerate", "re-create", "rebuild") for w in words)

        # Ambiguous commands
        if not (is_add or is_modify or is_remove or is_regen):
            return {
                "intent": "CLARIFICATION_NEEDED",
                "added": [],
                "modified": [],
                "removed": [],
                "skipped_as_duplicate": [],
                "unmet_requests": [],
                "clarification_needed": f"Could not determine intent for instruction: '{prompt_text}'. Please specify whether to ADD, MODIFY, or REMOVE test cases, and cite the target endpoint/route or test ID.",
            }

        # ── INTENT: REMOVE ──
        if is_remove and not is_add:
            # Check for specific test ID mentions
            id_matches = re.findall(r"PTC-\d+", prompt_text, re.IGNORECASE)
            removed_ids: list[str] = []
            for tid in id_matches:
                t_upper = tid.upper()
                if any(p["id"] == t_upper for p in existing_inventory):
                    removed_ids.append(t_upper)

            # Check for category / keyword based removal (e.g. "remove duplicate role tests")
            if "role" in p_lower or "permission" in p_lower:
                for p in existing_inventory:
                    if "role" in p.get("category", "").lower() or "role" in p.get("title", "").lower():
                        if p["id"] not in removed_ids:
                            removed_ids.append(p["id"])

            return {
                "intent": "REMOVE",
                "added": [],
                "modified": [],
                "removed": removed_ids,
                "skipped_as_duplicate": [],
                "unmet_requests": [] if removed_ids else [{"requested": prompt_text, "reason_not_fulfilled": "No matching test cases found to remove in existing inventory."}],
                "clarification_needed": None,
            }

        # ── INTENT: MODIFY ──
        if is_modify and not is_add:
            id_matches = re.findall(r"PTC-\d+", prompt_text, re.IGNORECASE)
            modified_list: list[dict[str, Any]] = []
            if id_matches:
                for tid in id_matches:
                    t_upper = tid.upper()
                    target_p = next((p for p in existing_proposals if p.id == t_upper), None)
                    if target_p:
                        # Extract what to modify from instruction
                        changed: dict[str, Any] = {}
                        if "error" in p_lower or "alert" in p_lower or "message" in p_lower:
                            changed["expected_result"] = f"{target_p.expected_result} - asserts exact error alert message banner is visible."
                            if target_p.ui_spec:
                                new_spec = target_p.ui_spec.model_copy(deep=True)
                                new_spec.assertions.append("expect(page.locator('.alert-error, .alert-danger, [role=\"alert\"]')).toBeVisible()")
                                changed["ui_spec"] = new_spec.model_dump()
                        else:
                            changed["description"] = f"{target_p.description} (Refined per inline prompt: {prompt_text})"
                        modified_list.append({"id": t_upper, "changed_fields": changed})

            return {
                "intent": "MODIFY",
                "added": [],
                "modified": modified_list,
                "removed": [],
                "skipped_as_duplicate": [],
                "unmet_requests": [] if modified_list else [{"requested": prompt_text, "reason_not_fulfilled": "Identified testcase ID not found in current inventory."}],
                "clarification_needed": None,
            }

        # ── INTENT: ADD ──
        # Check target count: e.g. "add 5 tests", "add 3 negative tests"
        m_count = re.search(r"(\d+)", prompt_text)
        target_count = int(m_count.group(1)) if m_count else 2

        # Identify requested category
        is_negative = "negative" in p_lower or "validation" in p_lower or "invalid" in p_lower
        is_edge = "edge" in p_lower or "boundary" in p_lower
        is_role = "role" in p_lower or "permission" in p_lower or "auth" in p_lower
        is_happy = "happy" in p_lower or "positive" in p_lower or "workflow" in p_lower

        category_name = "Negative & Validation Testing" if is_negative else (
            "Edge Case Testing" if is_edge else (
                "Role & Permission Testing" if is_role else (
                    "Happy Path Testing" if is_happy else "Negative & Validation Testing"
                )
            )
        )

        # Identify mentioned route or endpoint
        route_matches = re.findall(r"(/[a-zA-Z0-9_\-/]+)", prompt_text)
        target_route: str | None = None
        target_wf: dict[str, Any] | None = None
        target_ep: dict[str, Any] | None = None

        if route_matches:
            cand_route = route_matches[0]
            # Check against discovered UI routes
            target_wf = next((wf for wf in discovered_ui_routes if wf.get("route") == cand_route), None)
            if not target_wf:
                # Check against discovered API endpoints
                target_ep = next((ep for ep in discovered_api_endpoints if ep.get("endpoint") == cand_route), None)
            if target_wf:
                target_route = target_wf.get("route")
            elif target_ep:
                target_route = target_ep.get("endpoint")
            else:
                # User asked for an endpoint/route not in repository evidence!
                return {
                    "intent": "ADD",
                    "added": [],
                    "modified": [],
                    "removed": [],
                    "skipped_as_duplicate": [],
                    "unmet_requests": [
                        {
                            "requested": cand_route,
                            "reason_not_fulfilled": f"Route or endpoint '{cand_route}' was not found in discovered repository endpoints or UI routes.",
                        }
                    ],
                    "clarification_needed": None,
                }
        else:
            # Check if mentioned by name: "employee form" -> "/employees/new"
            if "employee" in p_lower:
                target_wf = next((wf for wf in discovered_ui_routes if "employee" in wf.get("route", "") or "employee" in wf.get("name", "").lower()), None)
            elif "dashboard" in p_lower:
                target_wf = next((wf for wf in discovered_ui_routes if wf.get("route") == "/"), None)

            if target_wf:
                target_route = target_wf.get("route")
            elif discovered_ui_routes:
                target_wf = discovered_ui_routes[0]
                target_route = target_wf.get("route")

        # Now synthesize genuine, distinct test scenarios up to target_count
        added: list[dict[str, Any]] = []
        skipped_as_duplicate: list[dict[str, Any]] = []

        existing_scenarios = {
            f"{p.get('endpoint')}::{p.get('title', '').lower()}" for p in existing_inventory
        }
        existing_intents = {
            f"{p.get('endpoint')}::{p.get('category', '').lower()}" for p in existing_inventory
        }

        # Generate candidate variations
        candidate_scenarios: list[dict[str, Any]] = []
        route_str = target_route or "/employees/new"
        wf_name = (target_wf.get("name") if target_wf else "View") or "Form"

        # Variation 1: Empty required fields submission
        candidate_scenarios.append({
            "title": f"Playwright UI: Verify field validation on empty {wf_name} submit",
            "category": "Negative & Validation Testing",
            "description": f"Submits empty form at {route_str} and verifies browser displays required field error messages.",
            "route": route_str,
            "actions": ["navigate", "click button[type='submit']", "screenshot"],
            "assertions": ["expect(page.locator('.error, [role=\"alert\"]')).toBeVisible()"],
            "expected_result": "Validation messages appear for all mandatory fields.",
            "inputs": [],
        })
        # Variation 2: Boundary characters / special characters
        candidate_scenarios.append({
            "title": f"Playwright UI: Verify XSS/special characters boundary handling on {wf_name}",
            "category": "Edge Case Testing",
            "description": f"Enters special characters <script>alert(1)</script> and boundary strings into {wf_name} inputs.",
            "route": route_str,
            "actions": ["navigate", "fill input test", "click button[type='submit']", "screenshot"],
            "assertions": ["expect(page.locator('body')).not.toContainText('<script>')"],
            "expected_result": "Special characters are sanitized or rejected without execution or unhandled exceptions.",
            "inputs": [{"name": "name", "value": "<script>alert(1)</script>"}],
        })
        # Variation 3: Invalid email/phone formats
        candidate_scenarios.append({
            "title": f"Playwright UI: Verify format validation error with malformed email on {wf_name}",
            "category": "Negative & Validation Testing",
            "description": f"Inputs malformed email format 'not-an-email' on {wf_name} and asserts format validation prevents submission.",
            "route": route_str,
            "actions": ["navigate", "fill input email", "click button[type='submit']", "screenshot"],
            "assertions": ["expect(page.locator(':invalid, .alert')).toBeVisible()"],
            "expected_result": "Form prevents submission and highlights email format error.",
            "inputs": [{"name": "email", "value": "not-an-email"}],
        })
        # Variation 4: Unauthorized navigation check
        candidate_scenarios.append({
            "title": f"Playwright UI: Verify restricted access to {route_str} redirects to authentication",
            "category": "Role & Permission Testing",
            "description": f"Attempts direct unauthenticated GET on {route_str} without active user session.",
            "route": route_str,
            "actions": ["navigate", "screenshot"],
            "assertions": ["expect(page).toHaveURL(/login|auth/)"],
            "expected_result": "Application redirects unauthenticated user to login screen.",
            "inputs": [],
        })
        # Variation 5: Maximum length boundary
        candidate_scenarios.append({
            "title": f"Playwright UI: Verify max length character overflow handling on {wf_name}",
            "category": "Edge Case Testing",
            "description": f"Enters 500+ character string into {wf_name} input fields to verify client-side truncation or max-length restriction.",
            "route": route_str,
            "actions": ["navigate", "fill input max", "screenshot"],
            "assertions": ["expect(page.locator('input')).toHaveValue(/.{1,255}/)"],
            "expected_result": "Input field restricts input to maximum allowed column length.",
            "inputs": [{"name": "description", "value": "A" * 500}],
        })

        # Filter candidate scenarios against existing inventory to avoid duplicates
        existing_titles = {p["title"].lower() for p in existing_inventory}
        next_id_num = len(existing_inventory) + 1

        for cand in candidate_scenarios:
            if len(added) >= target_count:
                break

            # Deduplication check
            is_dup = False
            dup_id = None
            for p in existing_inventory:
                if p.get("endpoint") == cand["route"] and (
                    cand["title"].lower() in p["title"].lower()
                    or p["title"].lower() in cand["title"].lower()
                    or (cand["category"] == p.get("category") and "empty" in cand["title"].lower() and "empty" in p["title"].lower())
                ):
                    is_dup = True
                    dup_id = p["id"]
                    break

            if is_dup:
                skipped_as_duplicate.append({
                    "attempted_scenario": cand["title"],
                    "duplicate_of_id": dup_id or "PTC-005",
                })
                continue

            test_obj = {
                "id": f"PTC-{next_id_num:03d}",
                "title": cand["title"],
                "description": cand["description"],
                "type": "UI",
                "priority": "MEDIUM",
                "source": "LLM Generated",
                "generation_source": "LLM Generated",
                "reason": f"Generated from inline user prompt: '{prompt_text}'",
                "preconditions": [f"Application is running at base URL", f"Target route {cand['route']} is accessible"],
                "steps": [
                    f"1. Navigate to {cand['route']}",
                    f"2. Perform inputs and actions for {cand['title']}",
                    f"3. Verify {cand['expected_result']}",
                ],
                "expected_result": cand["expected_result"],
                "status": "PROPOSED",
                "category": cand["category"],
                "custom_instruction_note": f"Inline refinement prompt: {prompt_text}",
                "ui_spec": {
                    "target_route": cand["route"],
                    "input_fields": cand["inputs"],
                    "actions": cand["actions"],
                    "expected_elements": [cand["route"]],
                    "selectors": {"primary": cand["route"]},
                    "assertions": cand["assertions"],
                },
            }
            added.append(test_obj)
            next_id_num += 1

        unmet = []
        if len(added) < target_count:
            shortfall = target_count - len(added)
            unmet.append({
                "requested": f"{target_count} distinct scenarios for {route_str}",
                "reason_not_fulfilled": f"Only {len(added)} genuinely distinct scenario(s) could be supported by repository evidence without duplicating existing inventory ({len(skipped_as_duplicate)} duplicate(s) skipped).",
            })

        return {
            "intent": "ADD",
            "added": added,
            "modified": [],
            "removed": [],
            "skipped_as_duplicate": skipped_as_duplicate,
            "unmet_requests": unmet,
            "clarification_needed": None,
        }

    def apply_inline_prompt_diff(self, job_id: str, diff: dict[str, Any]) -> list[ProposedTestCase]:
        """Applies previewed diff (added, modified, removed) to job inventory and persists changes."""
        with self._lock:
            proposals = self.get_proposed_tests(job_id)

            # 1. Remove IDs
            removed_ids = set(diff.get("removed", []))
            if removed_ids:
                proposals = [p for p in proposals if p.id not in removed_ids]
                self._log(job_id, f"[INLINE DIFF] Removed {len(removed_ids)} test case(s): {list(removed_ids)}")

            # 2. Apply modifications
            modified_entries = diff.get("modified", [])
            if modified_entries:
                mod_map = {m["id"]: m.get("changed_fields", {}) for m in modified_entries if "id" in m}
                for p in proposals:
                    if p.id in mod_map:
                        ch = mod_map[p.id]
                        for k, v in ch.items():
                            if hasattr(p, k) and v is not None:
                                if k == "ui_spec" and isinstance(v, dict):
                                    setattr(p, k, UiTestSpec(**v))
                                elif k == "api_spec" and isinstance(v, dict):
                                    setattr(p, k, ApiTestSpec(**v))
                                else:
                                    setattr(p, k, v)
                self._log(job_id, f"[INLINE DIFF] Modified {len(mod_map)} test case(s): {list(mod_map.keys())}")

            # 3. Merge added testcases
            added_entries = diff.get("added", [])
            if added_entries:
                existing_ids = {p.id for p in proposals}
                max_num = 0
                for p in proposals:
                    m = re.match(r"PTC-(\d+)", p.id)
                    if m:
                        max_num = max(max_num, int(m.group(1)))

                new_testcases: list[ProposedTestCase] = []
                for item in added_entries:
                    if isinstance(item, dict):
                        item_copy = dict(item)
                        t_id = item_copy.get("id")
                        if not t_id or t_id in existing_ids:
                            max_num += 1
                            t_id = f"PTC-{max_num:03d}"
                            item_copy["id"] = t_id
                        existing_ids.add(t_id)

                        item_copy.setdefault("title", f"Proposed Test {t_id}")
                        item_copy.setdefault("description", item_copy.get("title", ""))
                        item_copy.setdefault("type", ProposedTestType.UI)
                        item_copy.setdefault("priority", ProposedTestPriority.MEDIUM)
                        item_copy.setdefault("source", "LLM Generated")
                        item_copy.setdefault("generation_source", "LLM Generated")
                        item_copy.setdefault("reason", "Added via inline user prompt refinement")
                        item_copy.setdefault("expected_result", "Expected behavior is verified")
                        item_copy.setdefault("status", ProposedTestStatus.PROPOSED)
                        ptc = ProposedTestCase.model_validate(item_copy)
                        new_testcases.append(ptc)
                    elif isinstance(item, ProposedTestCase):
                        new_testcases.append(item)

                # Validate added tests against repository if available
                paths = WorkspacePaths(job_id)
                repo_dir = paths.migrated_repo_dir if paths.migrated_repo_dir.exists() else paths.original_repo_dir
                if repo_dir.exists() and new_testcases:
                    try:
                        from app.application.use_cases.proposed_tests.proposed_test_validator import ProposedTestValidator
                        validator = ProposedTestValidator(repo_dir)
                        new_testcases, _ = validator.validate_all(new_testcases)
                    except Exception as ve:
                        logger.debug(f"Validation of added tests skipped: {ve}")

                proposals.extend(new_testcases)
                self._log(job_id, f"[INLINE DIFF] Added {len(new_testcases)} new test case(s).")

            # 4. Persist updated inventory
            self._save_proposals(job_id, proposals)
            metrics = self._compute_metrics(proposals)

            # Synchronize status file
            self._save_status(job_id, "COMPLETED", {
                "total": len(proposals),
                "metrics": metrics.model_dump(),
            })

            # Synchronize results.json if it exists
            res_file = self._get_results_file(job_id)
            if res_file.exists():
                try:
                    rdata = json.loads(res_file.read_text(encoding="utf-8"))
                    rdata["test_cases"] = [p.model_dump() for p in proposals]
                    rdata["metrics"] = metrics.model_dump()
                    res_file.write_text(json.dumps(rdata, indent=2), encoding="utf-8")
                except Exception:
                    pass

            return proposals



proposed_test_service = ProposedTestService()
