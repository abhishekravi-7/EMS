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
    ProposedTestCase,
    ProposedTestMetrics,
    ProposedTestPriority,
    ProposedTestPriorityBreakdown,
    ProposedTestStatus,
    ProposedTestType,
    ProposedTestTypeBreakdown,
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

            # Static analyzer
            analyzer = ProposedTestAnalyzer(repo_dir, existing_tests=existing_tests)
            analysis_data = analyzer.analyze()

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
                if test_ids and p.id not in test_ids:
                    continue
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
            repo_dir = paths.migrated_repo_dir if paths.migrated_repo_dir.exists() else paths.original_repo_dir
            evidence_dir = self._get_job_dir(job_id) / "evidence"

            from app.application.use_cases.proposed_tests.proposed_test_executor import resolve_migrated_app_url
            resolved_base_url = resolve_migrated_app_url(repo_dir)

            executor = ProposedTestExecutor(
                job_id,
                evidence_dir=evidence_dir,
                log_fn=lambda m, level="INFO": self._log(job_id, m, level),
                base_url=resolved_base_url,
            )

            source_names = []
            if run_llm:
                source_names.append("LLM Generated")
            if run_doc:
                source_names.append("Functional Testing Document")
            if run_existing:
                source_names.append("Existing Repository")

            self._log(job_id, f"Playwright execution started against migrated application ({resolved_base_url})")
            self._log(job_id, f"Selected sources: {', '.join(source_names)}")
            self._log(job_id, f"Resolved {len(tests_to_run)} test cases")

            # Execute strictly the selected tests
            for t in tests_to_run:
                self._log(job_id, f"Running {t.id} - {t.title}")
                t.status = ProposedTestStatus.RUNNING
                self._save_proposals(job_id, proposals)

                res = executor.execute_test(t, repo_dir=repo_dir)
                t.execution_result = res
                t.status = res.status
                self._save_proposals(job_id, proposals)
                self._log(job_id, f"{t.id} {res.status.value}")

                with self._lock:
                    if job_id in self._run_state:
                        self._run_state[job_id]["completed"] += 1

            # Generate standard Allure results and standalone HTML report for executed tests
            try:
                reporter.generate_allure_results(tests_to_run, selected_sources=norm_sources)
                reporter.generate_html_report(tests_to_run, selected_sources=norm_sources)
                self._log(job_id, "Allure Report generated successfully.")
            except Exception as a_err:  # noqa: BLE001
                self._log(job_id, f"Failed to generate Allure Report: {a_err}", "WARN")

            # Compute and persist final results & metrics strictly for the executed tests
            metrics = self._compute_metrics(tests_to_run)
            allure_url = f"/api/v1/migration/{job_id}/proposed-tests/allure-report/index.html"
            result_payload = {
                "job_id": job_id,
                "status": "COMPLETED",
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "selected_sources": norm_sources,
                "metrics": metrics.model_dump(),
                "allure_report_available": True,
                "allure_report_url": allure_url,
                "test_cases": [p.model_dump() for p in tests_to_run],
            }
            self._get_results_file(job_id).write_text(json.dumps(result_payload, indent=2), encoding="utf-8")

            with self._lock:
                self._run_state[job_id] = {
                    "status": "COMPLETED",
                    "result": result_payload,
                    "selected_sources": norm_sources,
                    "allure_report_available": True,
                    "allure_report_url": allure_url,
                }
            self._save_status(job_id, "COMPLETED", {
                "selected_sources": norm_sources,
                "total": len(tests_to_run),
                "executed": metrics.executed,
                "passed": metrics.passed,
                "failed": metrics.failed,
                "allure_report_available": True,
                "allure_report_url": allure_url,
                "metrics": metrics.model_dump(),
            })
            self._log(job_id, f"Playwright execution completed. Total: {len(tests_to_run)}, Passed: {metrics.passed}, Failed: {metrics.failed}")

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

        res_file = self._get_results_file(job_id)
        if res_file.exists():
            try:
                rdata = json.loads(res_file.read_text(encoding="utf-8"))
                return {
                    "job_id": job_id,
                    "status": mem_state.get("status") if mem_state else rdata.get("status", "COMPLETED"),
                    "progress": {
                        "total": rdata.get("metrics", {}).get("total", len(rdata.get("test_cases", []))),
                        "completed": rdata.get("metrics", {}).get("executed", len(rdata.get("test_cases", []))),
                    },
                    "selected_sources": rdata.get("selected_sources", persisted_sources),
                    "allure_report_available": allure_available,
                    "allure_report_url": allure_url,
                    "metrics": rdata.get("metrics", {}),
                    "logs": logs,
                    "proposals": rdata.get("test_cases", []),
                }
            except Exception:  # noqa: BLE001
                pass

        proposals = self.get_proposed_tests(job_id)
        metrics = self._compute_metrics(proposals)
        current_status = mem_state.get("status") if mem_state else persisted_status
        if not proposals and current_status != "GENERATING":
            current_status = "IDLE"

        return {
            "job_id": job_id,
            "status": current_status,
            "progress": {
                "total": mem_state.get("total", len(proposals)) if mem_state else len(proposals),
                "completed": mem_state.get("completed", 0) if mem_state else 0,
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

        res_file = self._get_results_file(job_id)
        if res_file.exists():
            try:
                data = json.loads(res_file.read_text(encoding="utf-8"))
                data["allure_report_available"] = allure_available
                data["allure_report_url"] = allure_url
                return data
            except Exception:  # noqa: BLE001, S110
                pass  # nosec B110

        proposals = self.get_proposed_tests(job_id)
        metrics = self._compute_metrics(proposals)
        return {
            "job_id": job_id,
            "status": "IDLE",
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
        not_executed = total - executed

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
                p.generation_source in ["BRD_DOCUMENT", "FUNCTIONAL_DOC", "FUNCTIONAL_DOCUMENT"]
                or ("BRD" in p.id and p.generation_source != "BRD_AND_AI")
                or p.source in ["BRD Document", "BRD Business Requirement"]
            )
            and p.generation_source != "BRD_AND_AI"
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
        target = self._get_proposals_file(job_id)
        data = [p.model_dump() for p in proposals]
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")


proposed_test_service = ProposedTestService()
