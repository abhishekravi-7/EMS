"""Service for orchestrating existing test discovery and execution."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, Any, List

from app.infrastructure.analyzers.existing_test_detector import ExistingTestDetector
from app.infrastructure.quality_gates.unit_test_runner import UnitTestRunner
from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.core.exceptions import APEXError

class ExistingTestService:
    def __init__(self):
        self._runner = UnitTestRunner()
        # In-memory status tracking for simplicity, keyed by job_id
        self._execution_states: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def discover_tests(self, job_id: str) -> Dict[str, Any]:
        """Discover existing tests in the project directory associated with the job."""
        project_dir = self._resolve_project_dir(job_id)
        detector = ExistingTestDetector(project_dir)
        return detector.discover()

    def run_tests(self, job_id: str, test_classes: List[str]) -> Dict[str, Any]:
        """Launch test execution in the background."""
        with self._lock:
            if job_id in self._execution_states and self._execution_states[job_id]["status"] == "RUNNING":
                return self._execution_states[job_id]

            # Calculate baseline discovery count synchronously to avoid resetting statistics in UI
            try:
                discovery_result = self.discover_tests(job_id)
                total_discovered = sum(len(t["methods"]) for t in discovery_result["tests"])
            except Exception:
                total_discovered = 0

            state = {
                "status": "RUNNING",
                "discovered": total_discovered,
                "executed": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "results": [],
                "logs": ["Starting test execution..."],
                "error": None
            }
            self._execution_states[job_id] = state

        # Run in background thread
        thread = threading.Thread(
            target=self._execute_tests_task,
            args=(job_id, test_classes),
            name=f"test-run-{job_id}",
            daemon=True
        )
        thread.start()

        return state

    def get_status(self, job_id: str) -> Dict[str, Any]:
        """Get current status of test execution."""
        with self._lock:
            return self._execution_states.get(job_id, {"status": "IDLE", "discovered": 0, "executed": 0, "passed": 0, "failed": 0, "skipped": 0, "results": [], "logs": []})

    def _execute_tests_task(self, job_id: str, test_classes: List[str]):
        try:
            project_dir = self._resolve_project_dir(job_id)
            build_tool = "gradle" if (project_dir / "build.gradle").exists() or (project_dir / "build.gradle.kts").exists() else "maven"

            # Step 1: Baseline discovery count
            discovery_result = self.discover_tests(job_id)
            total_discovered = sum(len(t["methods"]) for t in discovery_result["tests"])

            # Step 2: Single-pass targeted execution (Prova approach)
            target_names = test_classes if test_classes else None

            result = self._runner.run(project_dir, build_tool=build_tool, target_class_names=target_names)

            all_results = [
                {
                    "test_class": d.test_class,
                    "test_method": d.test_method,
                    "status": d.status,
                    "execution_time_seconds": d.execution_time_seconds,
                    "error_message": d.error_message
                } for d in result.existing_test_results
            ]

            # Calculate selected methods count for invariants
            selected_methods_count = sum(
                len(t["methods"]) for t in discovery_result["tests"]
                if t["id"] in test_classes
            ) if test_classes else total_discovered

            with self._lock:
                total_executed = result.total_run
                passed_count = result.passed
                failed_count = result.failed
                skipped_count = result.skipped
                execution_status = "COMPLETED"
                error_msg = None

                if total_executed == 0:
                    # Robust error detection from logs (matches Prova strategy)
                    logs_str = "\n".join(result.raw_logs)
                    if "NoSuchFieldException: com.sun.tools.javac.code.TypeTag :: UNKNOWN" in logs_str:
                        error_msg = "LOMBOK_JDK_INCOMPATIBILITY"
                    elif "BUILD FAILURE" in logs_str or "Compilation failure" in logs_str:
                        error_msg = "BUILD_FAILED"

                # Enforce state invariants:
                # 1. executed >= passed + failed + skipped
                summed_results = passed_count + failed_count + skipped_count
                if total_executed < summed_results:
                    print(f"Invariant Guard: total_executed ({total_executed}) < passed+failed+skipped ({summed_results}). Adjusting executed count.")
                    total_executed = summed_results

                # 2. executed <= selected
                if test_classes and total_executed > selected_methods_count:
                    print(f"Invariant Guard: total_executed ({total_executed}) > selected ({selected_methods_count}). Clamping metrics.")
                    total_executed = selected_methods_count
                    passed_count = min(passed_count, selected_methods_count)
                    failed_count = min(failed_count, selected_methods_count - passed_count)
                    skipped_count = min(skipped_count, selected_methods_count - passed_count - failed_count)

                self._execution_states[job_id].update({
                    "status": execution_status,
                    "discovered": total_discovered,
                    "executed": total_executed,
                    "passed": passed_count,
                    "failed": failed_count,
                    "skipped": skipped_count,
                    "results": all_results,
                    "logs": result.raw_logs,
                    "error": error_msg
                })

        except Exception as e:
            with self._lock:
                if job_id in self._execution_states:
                    self._execution_states[job_id].update({
                        "status": "FAILED",
                        "error": str(e),
                        "logs": self._execution_states[job_id].get("logs", []) + [f"Error during execution: {str(e)}"]
                    })

        except Exception as e:
            with self._lock:
                if job_id in self._execution_states:
                    self._execution_states[job_id].update({
                        "status": "FAILED",
                        "error": str(e),
                        "logs": self._execution_states[job_id].get("logs", []) + [f"Error: {str(e)}"]
                    })

    def _resolve_project_dir(self, job_id: str) -> Path:
        paths = WorkspacePaths(job_id)
        # Prefer original repo dir for existing tests discovery/execution if not migrated yet
        if paths.original_repo_dir.exists():
            return paths.original_repo_dir
        if paths.migrated_repo_dir.exists():
            return paths.migrated_repo_dir
        raise APEXError(f"Could not resolve project directory for job {job_id}")
