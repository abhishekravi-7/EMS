import pytest
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.application.pipelines.migration_execution_pipeline import MigrationExecutionPipeline
from app.infrastructure.quality_gates.jacoco_service import JaCoCoService
from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.application.services.status_service import MigrationReportStore


def test_start_migration_idempotency_same_job_twice(tmp_path):
    """Starting the same job twice must not start a second background thread."""
    job_id = "job_test_idempotency_1"
    
    mock_report = {
        "jobId": job_id,
        "status": "QUEUED",
        "currentStep": "QUEUED",
        "progressPercent": 0,
        "runSonar": False,
        "runFossa": False,
        "runTests": False,
    }
    
    mock_use_case = MagicMock()
    mock_use_case.prepare.return_value = mock_report
    
    pipeline = MigrationExecutionPipeline(use_case=mock_use_case)
    run_started = threading.Event()
    run_continue = threading.Event()

    def fake_run(*args, **kwargs):
        run_started.set()
        run_continue.wait(timeout=2.0)

    mock_use_case.run.side_effect = fake_run

    with patch("app.application.pipelines.migration_execution_pipeline.MigrationReportStore") as mock_store_cls, \
         patch("app.application.pipelines.migration_execution_pipeline.report_service.build_result") as mock_build_res:
        
        mock_store_inst = MagicMock()
        stored_reports = [None, mock_report, mock_report, mock_report, mock_report]
        mock_store_inst.read.side_effect = lambda: stored_reports.pop(0) if stored_reports else mock_report
        mock_store_cls.return_value = mock_store_inst
        mock_build_res.return_value = {"jobId": job_id, "status": "QUEUED"}
        
        # 1st start
        res1 = pipeline.start(job_id, {"target_java_version": "17"})
        assert res1["jobId"] == job_id
        assert mock_use_case.prepare.call_count == 1
        
        # Wait for thread to actually start running
        run_started.wait(timeout=1.0)
        
        # 2nd start while job is actively running in thread
        res2 = pipeline.start(job_id, {"target_java_version": "17"})
        assert res2["jobId"] == job_id
        # prepare and background run should NOT be called a second time
        assert mock_use_case.prepare.call_count == 1
        
        # Release thread
        run_continue.set()


def test_concurrent_migration_start_only_launches_one_execution():
    """Concurrent start calls for the same job ID must only start 1 execution."""
    job_id = "job_test_concurrent_start"
    mock_report = {
        "jobId": job_id,
        "status": "QUEUED",
        "currentStep": "QUEUED",
        "progressPercent": 0,
        "runSonar": False,
        "runFossa": False,
        "runTests": False,
    }
    
    mock_use_case = MagicMock()
    mock_use_case.prepare.return_value = mock_report
    mock_use_case.run.side_effect = lambda *args, **kwargs: time.sleep(0.1)
    
    pipeline = MigrationExecutionPipeline(use_case=mock_use_case)
    
    with patch("app.application.pipelines.migration_execution_pipeline.MigrationReportStore") as mock_store_cls, \
         patch("app.application.pipelines.migration_execution_pipeline.report_service.build_result") as mock_build_res:
        
        mock_store_inst = MagicMock()
        mock_store_inst.read.return_value = None
        mock_store_cls.return_value = mock_store_inst
        mock_build_res.return_value = {"jobId": job_id, "status": "QUEUED"}
        
        threads = []
        results = []
        
        def run_start():
            res = pipeline.start(job_id, {"target_java_version": "17"})
            results.append(res)
            
        for _ in range(5):
            t = threading.Thread(target=run_start)
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        assert len(results) == 5
        # Only 1 prepare call should have executed
        assert mock_use_case.prepare.call_count == 1
        
        # Cleanup
        with pipeline._active_jobs_lock:
            pipeline._active_jobs.discard(job_id)


def test_jacoco_execution_before_pom_exists_returns_unavailable_safely(tmp_path):
    """JaCoCoService must return unavailable when no build file exists without raising errors."""
    empty_dir = tmp_path / "empty_repo"
    empty_dir.mkdir()
    
    res = JaCoCoService.run_jacoco_build(empty_dir)
    assert res["available"] is False
    assert res["line_coverage_pct"] is None
    assert "No build file" in res["message"] or "does not exist" in res["message"]


def test_jacoco_directory_lock_prevents_concurrent_maven_processes(tmp_path):
    """JaCoCoService per-directory lock must serialize build attempts on the same folder."""
    repo_dir = tmp_path / "mock_maven_repo"
    repo_dir.mkdir()
    (repo_dir / "pom.xml").write_text("<project></project>", encoding="utf-8")
    
    lock = JaCoCoService._get_dir_lock(repo_dir)
    assert lock is not None
    
    executed_in_order = []
    
    with patch("app.infrastructure.quality_gates.jacoco_service.run_command") as mock_run_cmd, \
         patch("app.infrastructure.quality_gates.jacoco_service.JaCoCoService.ensure_jacoco_configured", return_value=True), \
         patch("app.infrastructure.quality_gates.jacoco_service.JaCoCoService.detect_target_major", return_value=17), \
         patch("app.infrastructure.java_runtime.build_tool_env", return_value={}):
        
        from app.shared.command_runner import CommandResult
        
        def slow_run(*args, **kwargs):
            executed_in_order.append("start")
            time.sleep(0.05)
            executed_in_order.append("end")
            return CommandResult(exit_code=0, stdout="BUILD SUCCESS", stderr="")
            
        mock_run_cmd.side_effect = slow_run
        
        t1 = threading.Thread(target=lambda: JaCoCoService.run_jacoco_build(repo_dir))
        t2 = threading.Thread(target=lambda: JaCoCoService.run_jacoco_build(repo_dir))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # Operations should be strictly serialized (start, end, start, end)
        assert executed_in_order == ["start", "end", "start", "end"]


def test_worker_actual_execution_and_completion():
    """Verify that StartMigrationUseCase.run is actually executed by the background worker thread."""
    job_id = "job_worker_exec_test"
    mock_report = {
        "jobId": job_id,
        "status": "QUEUED",
        "currentStep": "QUEUED",
        "progressPercent": 0,
    }
    mock_use_case = MagicMock()
    mock_use_case.prepare.return_value = mock_report
    
    worker_called = threading.Event()
    def fake_run(j_id, user_id, gh_token):
        assert j_id == job_id
        assert user_id == 42
        assert gh_token == "ghp_test123"
        worker_called.set()

    mock_use_case.run.side_effect = fake_run
    pipeline = MigrationExecutionPipeline(use_case=mock_use_case)

    with patch("app.application.pipelines.migration_execution_pipeline.MigrationReportStore") as mock_store_cls, \
         patch("app.application.pipelines.migration_execution_pipeline.report_service.build_result") as mock_build_res:
        mock_store_inst = MagicMock()
        mock_store_inst.read.return_value = mock_report
        mock_store_cls.return_value = mock_store_inst
        mock_build_res.return_value = {"jobId": job_id, "status": "QUEUED"}

        res = pipeline.start(job_id, {"target_java_version": "17"}, current_user_id=42, github_token="ghp_test123")
        assert res["jobId"] == job_id
        
        # Verify worker thread runs
        assert worker_called.wait(timeout=2.0) is True
        time.sleep(0.05)
        # Lock should be cleanly released
        assert pipeline.is_job_running(job_id) is False


def test_worker_exception_marks_status_failed_and_releases_lock():
    """Verify that an uncaught exception in the worker updates status to FAILED and releases the lock."""
    job_id = "job_worker_fail_test"
    mock_report = {
        "jobId": job_id,
        "status": "QUEUED",
        "currentStep": "QUEUED",
        "progressPercent": 0,
    }
    mock_use_case = MagicMock()
    mock_use_case.prepare.return_value = mock_report
    
    def failing_run(*args, **kwargs):
        raise RuntimeError("Simulated AST migration crash")

    mock_use_case.run.side_effect = failing_run
    pipeline = MigrationExecutionPipeline(use_case=mock_use_case)

    with patch("app.application.pipelines.migration_execution_pipeline.MigrationReportStore") as mock_store_cls, \
         patch("app.application.pipelines.migration_execution_pipeline.report_service.build_result") as mock_build_res:
        mock_store_inst = MagicMock()
        mock_store_inst.read.return_value = mock_report
        mock_store_cls.return_value = mock_store_inst
        mock_build_res.return_value = {"jobId": job_id, "status": "QUEUED"}

        pipeline.start(job_id, {"target_java_version": "17"})
        
        # Wait briefly for thread to finish
        time.sleep(0.1)
        
        # Verify store updated to FAILED with error message
        mock_store_inst.update.assert_called_with(
            status="FAILED",
            currentStep="Migration worker failed",
            errorMessage="Simulated AST migration crash",
        )
        mock_store_inst.append_logs.assert_called()
        
        # Verify active lock is released
        assert pipeline.is_job_running(job_id) is False
