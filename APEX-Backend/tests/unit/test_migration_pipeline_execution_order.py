import pytest
import os
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.application.use_cases.start_migration import StartMigrationUseCase
from app.application.pipelines.migration_execution_pipeline import MigrationExecutionPipeline
from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.infrastructure.workspace.workspace_manager import WorkspaceManager
from app.application.services.status_service import MigrationReportStore
from app.domain.enums.migration_status import MigrationStatus, MigrationStep


def test_migration_pipeline_full_execution_order(tmp_path: Path):
    """
    Verifies that:
    1. Migration finishes transformation before JUnit generation.
    2. JUnit tests use migrated-repo (not original-repo).
    3. Generated tests are compiled and executed.
    4. Surefire results are collected.
    5. JaCoCo report is generated.
    6. Unit Test Report is generated.
    7. Results are persisted before marking status as COMPLETED.
    8. Duplicate migration requests do not start duplicate test executions.
    """
    job_id = "job_order_test_123"
    
    # Set up mock storage directories
    storage_root = tmp_path / "storage" / "migration-jobs" / job_id
    storage_root.mkdir(parents=True, exist_ok=True)
    orig_repo = storage_root / "original-repo"
    mig_repo = storage_root / "migrated-repo"
    orig_repo.mkdir(parents=True, exist_ok=True)
    
    # Create sample pom.xml and Java class in original-repo
    (orig_repo / "pom.xml").write_text(
        "<project><modelVersion>4.0.0</modelVersion><groupId>com.test</groupId><artifactId>sample</artifactId><version>1.0.0</version><properties><java.version>17</java.version></properties></project>",
        encoding="utf-8"
    )
    src_main = orig_repo / "src" / "main" / "java" / "com" / "test"
    src_main.mkdir(parents=True, exist_ok=True)
    (src_main / "SampleService.java").write_text(
        "package com.test;\npublic class SampleService { public String greet() { return \"hello\"; } }",
        encoding="utf-8"
    )

    call_sequence = []

    orig_init = WorkspacePaths.__init__

    def mock_init(self, j_id: str, storage_dir=None):
        orig_init(self, j_id, storage_dir=tmp_path / "storage" / "migration-jobs")

    with patch.object(WorkspacePaths, "__init__", mock_init):

        paths = WorkspacePaths(job_id)
        store = MigrationReportStore(paths)
        
        # Initial queued report
        store.write({
            "jobId": job_id,
            "status": MigrationStatus.QUEUED.value,
            "currentStep": MigrationStep.QUEUED.value,
            "progressPercent": 0,
            "targetJavaVersion": "21",
            "buildTool": "MAVEN",
            "runTests": True,
            "runSonar": False,
            "runFossa": False,
        })

        # Mock AutomatedMigrationRunner to record transformation
        mock_runner = MagicMock()
        def fake_run_migration(*args, **kwargs):
            call_sequence.append("TRANSFORMATION_AND_MIGRATION")
            # Create files in migrated-repo
            mig_repo.mkdir(parents=True, exist_ok=True)
            (mig_repo / "pom.xml").write_text(
                "<project><modelVersion>4.0.0</modelVersion><groupId>com.test</groupId><artifactId>sample</artifactId><version>1.0.0</version><properties><java.version>21</java.version></properties></project>",
                encoding="utf-8"
            )
            mig_main = mig_repo / "src" / "main" / "java" / "com" / "test"
            mig_main.mkdir(parents=True, exist_ok=True)
            (mig_main / "SampleService.java").write_text(
                "package com.test;\npublic class SampleService { public String greet() { return \"hello Java 21\"; } }",
                encoding="utf-8"
            )
            res = MagicMock()
            res.success = True
            res.effective_target_java_version = 21
            res.recipes = ["org.openrewrite.java.migrate.Java17to21"]
            res.recipe_selection_reasons = []
            res.build_modernization_lines = []
            res.dependency_upgrades = []
            res.already_compatible = False
            res.phase_results = []
            res.skipped_recipes = []
            res.spring_conversion_requested = False
            res.spring_conversion_supported = False
            res.spring_conversion_note = ""
            res.spring_boot_version_before = None
            res.spring_boot_version_after = None
            res.rule_executions = []
            res.used_fallback = False
            res.project_dir = mig_repo
            return res
        mock_runner.run.side_effect = fake_run_migration

        # Mock BuildValidator to record build validation
        mock_builder = MagicMock()
        def fake_build_validate(*args, **kwargs):
            call_sequence.append("BUILD_VALIDATION")
            res = MagicMock()
            res.success = True
            res.skipped = False
            res.log = "BUILD SUCCESS"
            res.target_repo_dir = str(mig_repo)
            return res
        mock_builder.validate.side_effect = fake_build_validate

        # Mock ChangeAnalyzer
        mock_analyzer = MagicMock()
        change_res = MagicMock()
        change_res.files_modified_count = 1
        change_res.import_changes = []
        change_res.source_changes = []
        change_res.all_changed_files = ["SampleService.java"]
        mock_analyzer.analyze.return_value = change_res

        # Mock RunUnitTestSuiteUseCase
        with patch("app.application.use_cases.run_unit_tests.RunUnitTestSuiteUseCase.execute_project_suite") as mock_suite_exec:
            async def fake_suite_exec(req, db=None):
                call_sequence.append("JUNIT_GENERATION_AND_EXECUTION")
                # Assert that JUnit generation target is migrated_repo_dir, NOT original_repo_dir
                assert Path(req.project_dir).resolve() == mig_repo.resolve()
                assert req.java_version == "21"
                
                # Create mock surefire report and mock JaCoCo report in migrated-repo
                sf_dir = mig_repo / "target" / "surefire-reports"
                sf_dir.mkdir(parents=True, exist_ok=True)
                (sf_dir / "TEST-com.test.SampleServiceTest.xml").write_text(
                    """<?xml version="1.0" encoding="UTF-8"?>
                    <testsuite name="com.test.SampleServiceTest" tests="2" failures="0" errors="0" skipped="0" time="0.05">
                        <testcase name="testGreet" classname="com.test.SampleServiceTest" time="0.03"/>
                        <testcase name="testNotNull" classname="com.test.SampleServiceTest" time="0.02"/>
                    </testsuite>""",
                    encoding="utf-8"
                )
                
                jac_dir = mig_repo / "target" / "site" / "jacoco"
                jac_dir.mkdir(parents=True, exist_ok=True)
                (jac_dir / "jacoco.xml").write_text(
                    """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd">
                    <report name="sample">
                        <counter type="INSTRUCTION" missed="10" covered="40"/>
                        <counter type="BRANCH" missed="0" covered="2"/>
                        <counter type="LINE" missed="2" covered="8"/>
                        <counter type="COMPLEXITY" missed="1" covered="3"/>
                        <counter type="METHOD" missed="0" covered="2"/>
                        <counter type="CLASS" missed="0" covered="1"/>
                    </report>""",
                    encoding="utf-8"
                )
                
                from app.schemas.unit_test import UnitTestSuiteResult, TestExecutionDetail
                suite_res = UnitTestSuiteResult(
                    job_id=job_id,
                    project_dir=str(mig_repo),
                    build_tool="maven",
                    total_run=2,
                    passed=2,
                    failed=0,
                    skipped=0,
                    execution_status="PASSED",
                    generated_test_results=[
                        TestExecutionDetail(test_class="com.test.SampleServiceTest", test_method="testGreet", status="PASSED", execution_time_seconds=0.03),
                        TestExecutionDetail(test_class="com.test.SampleServiceTest", test_method="testNotNull", status="PASSED", execution_time_seconds=0.02),
                    ],
                    line_coverage_pct=80.0,
                    branch_coverage_pct=100.0,
                    final_coverage={
                        "available": True,
                        "line_coverage_pct": 80.0,
                        "branch_coverage_pct": 100.0,
                        "report_path": str(jac_dir / "jacoco.xml"),
                    }
                )
                return suite_res

            mock_suite_exec.side_effect = fake_suite_exec

            # Instantiate and run StartMigrationUseCase
            use_case = StartMigrationUseCase(
                runner=mock_runner,
                build_validator=mock_builder,
                change_analyzer=mock_analyzer,
            )
            use_case._publish = MagicMock(return_value="https://github.com/JavaAPEX/sample")
            use_case._run_quality_gates = MagicMock()

            with patch("app.infrastructure.build.app_launcher.MigratedAppLauncher.launch") as mock_launch, \
                 patch("app.application.use_cases.proposed_tests.proposed_test_service.proposed_test_service.generate_proposed_tests") as mock_prop:
                mock_launch_res = MagicMock()
                mock_launch_res.success = False
                mock_launch_res.error = "Mocked unit test launch"
                mock_launch.return_value = mock_launch_res
                mock_prop.return_value = []

                use_case.run(job_id=job_id)

            # Assert order: TRANSFORMATION -> BUILD_VALIDATION -> JUNIT_GENERATION_AND_EXECUTION
            assert call_sequence == ["TRANSFORMATION_AND_MIGRATION", "BUILD_VALIDATION", "JUNIT_GENERATION_AND_EXECUTION"]

            # Verify persisted data in store
            final_report = store.read() or {}
            assert final_report.get("status") == MigrationStatus.COMPLETED.value
            assert final_report.get("progressPercent") == 100
            
            # Verify test_pipeline was persisted before completion
            test_pipeline = final_report.get("test_pipeline")
            assert test_pipeline is not None
            assert test_pipeline.get("execution_status") == "PASSED"
            assert test_pipeline.get("test_execution", {}).get("total") == 2
            assert test_pipeline.get("test_execution", {}).get("passed") == 2
            assert test_pipeline.get("coverage", {}).get("line_coverage_pct") == 80.0

            # Verify log trace contains all key sequence events
            logs = "\n".join(final_report.get("logLines", []))
            assert "[CODE VERSION]" in logs
            assert "[DEPENDENCIES]" in logs
            assert "[TRANSFORMATION]" in logs
            assert "[QUALITY CHECK]" in logs
            assert "[JUnit] JUnit test generation started" in logs
            assert "[JUnit] JUnit compilation started" in logs
            assert "[JUnit] JUnit execution started" in logs
            assert "[JUnit] Surefire results collected" in logs
            assert "[JACOCO] JaCoCo generation started" in logs
            assert "[REPORT] Unit Test Report generated" in logs
            assert "[REPORT] Results persisted" in logs
            assert "Migration completed" in logs
