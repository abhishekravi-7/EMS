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

            # Persist proposals & update status to COMPLETED
            self._save_proposals(job_id, proposals)
            metrics = self._compute_metrics(proposals)
            self._save_status(job_id, "COMPLETED", {
                "total": len(proposals),
                "generated": len(proposals),
                "metrics": metrics.model_dump(),
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

    def run_approved_tests(self, job_id: str) -> dict[str, Any]:
        proposals = self.get_proposed_tests(job_id)
        approved_tests = [p for p in proposals if p.status == ProposedTestStatus.APPROVED]

        if not approved_tests:
            return {
                "status": "COMPLETED",
                "message": "No approved tests found to run. Please approve test cases first.",
                "executed": 0,
            }

        with self._lock:
            self._run_state[job_id] = {
                "status": "RUNNING",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "total": len(approved_tests),
                "completed": 0,
            }
        self._save_status(job_id, "RUNNING", {"total": len(approved_tests), "completed": 0})

        def _run_bg():
            paths = WorkspacePaths(job_id)
            repo_dir = paths.migrated_repo_dir if paths.migrated_repo_dir.exists() else paths.original_repo_dir
            evidence_dir = self._get_job_dir(job_id) / "evidence"

            executor = ProposedTestExecutor(job_id, evidence_dir=evidence_dir, log_fn=lambda m, level="INFO": self._log(job_id, m, level))
            self._log(job_id, f"[PROPOSED TESTS] Starting execution of {len(approved_tests)} approved test cases...")

            for t in approved_tests:
                t.status = ProposedTestStatus.RUNNING
                self._save_proposals(job_id, proposals)

                res = executor.execute_test(t, repo_dir=repo_dir)
                t.execution_result = res
                t.status = res.status
                self._save_proposals(job_id, proposals)

                with self._lock:
                    if job_id in self._run_state:
                        self._run_state[job_id]["completed"] += 1

            # Compute and persist final results & metrics
            metrics = self._compute_metrics(proposals)
            result_payload = {
                "job_id": job_id,
                "status": "COMPLETED",
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "metrics": metrics.model_dump(),
                "test_cases": [p.model_dump() for p in proposals],
            }
            self._get_results_file(job_id).write_text(json.dumps(result_payload, indent=2), encoding="utf-8")

            with self._lock:
                self._run_state[job_id] = {
                    "status": "COMPLETED",
                    "result": result_payload,
                }
            self._save_status(job_id, "COMPLETED", {
                "total": len(proposals),
                "executed": metrics.executed,
                "passed": metrics.passed,
                "failed": metrics.failed,
                "metrics": metrics.model_dump(),
            })
            self._log(job_id, f"[PROPOSED TESTS] Execution finished. Passed: {metrics.passed}/{metrics.executed}")

        thread = threading.Thread(target=_run_bg, daemon=True)
        thread.start()

        return {
            "status": "RUNNING",
            "message": f"Started execution of {len(approved_tests)} approved tests in background.",
            "total_approved": len(approved_tests),
        }

    def get_status(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            mem_state = self._run_state.get(job_id)
            logs = list(self._live_logs.get(job_id, []))

        proposals = self.get_proposed_tests(job_id)
        metrics = self._compute_metrics(proposals)

        # Check persistent status file if available
        status_file = self._get_status_file(job_id)
        persisted_status = "IDLE"
        if status_file.exists():
            try:
                sdata = json.loads(status_file.read_text(encoding="utf-8"))
                persisted_status = sdata.get("status", "IDLE")
            except Exception:  # noqa: BLE001, S110
                pass  # nosec B110

        current_status = mem_state.get("status") if mem_state else persisted_status
        if not proposals and current_status != "GENERATING":
            current_status = "IDLE"

        return {
            "job_id": job_id,
            "status": current_status,
            "progress": {
                "total": mem_state.get("total", len([p for p in proposals if p.status == ProposedTestStatus.APPROVED])) if mem_state else len(proposals),
                "completed": mem_state.get("completed", 0) if mem_state else 0,
            },
            "metrics": metrics.model_dump(),
            "logs": logs,
            "proposals": [p.model_dump() for p in proposals],
        }

    def get_results(self, job_id: str) -> dict[str, Any]:
        res_file = self._get_results_file(job_id)
        if res_file.exists():
            try:
                return json.loads(res_file.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001, S110
                pass  # nosec B110

        proposals = self.get_proposed_tests(job_id)
        metrics = self._compute_metrics(proposals)
        return {
            "job_id": job_id,
            "status": "IDLE",
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

        ai_gen = len([p for p in proposals if p.generation_source in ["AI_GENERATED", "BRD_AND_AI", "STATIC_ANALYSIS", ""]])
        brd_gen = len([p for p in proposals if p.generation_source == "BRD_DOCUMENT"])

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
