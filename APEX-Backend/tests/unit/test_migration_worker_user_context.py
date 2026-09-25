from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from app.application.use_cases.start_migration import StartMigrationUseCase
from app.core.context import user_id_ctx


def test_start_migration_worker_user_context_propagation_and_cleanup():
    """Verify that current_user_id (e.g. 82) is correctly set in user_id_ctx during

    execution without UnboundLocalError and cleanly reset afterward.
    """
    uc = StartMigrationUseCase()
    observed_user_ids = []

    with patch("app.application.use_cases.start_migration.MigrationReportStore") as mock_store_cls, \
         patch("app.application.use_cases.start_migration.WorkspaceManager"), \
         patch.object(uc, "_run_migration_with_retries") as mock_run_retries, \
         patch.object(uc, "_publish", return_value="https://github.com/JavaAPEX/repo"), \
         patch.object(uc, "_reindex_knowledge_base"):

        mock_store = MagicMock()
        mock_store.read.return_value = {
            "buildTool": "maven",
            "targetJavaVersion": "21",
            "sourceRepoUrl": "https://github.com/spring-projects/spring-petclinic",
            "conversionTypes": ["java_version"],
            "runTests": False,
        }
        mock_store_cls.return_value = mock_store

        def fake_run_retries(*args, **kwargs):
            observed_user_ids.append(user_id_ctx.get())
            result = MagicMock()
            result.success = True
            result.recipes = []
            result.used_fallback = False
            result.effective_target_java_version = "21"
            result.recipe_selection_reasons = []
            result.build_modernization_lines = []
            result.dependency_upgrades = []
            result.already_compatible = True
            result.phase_results = []
            result.skipped_recipes = []
            result.spring_conversion_requested = False
            result.spring_conversion_supported = None
            result.spring_conversion_note = None
            result.spring_boot_version_before = None
            result.spring_boot_version_after = None
            result.rule_executions = []
            result.project_dir = None
            return result, None, []

        mock_run_retries.side_effect = fake_run_retries

        with patch.object(uc._change_analyzer, "analyze") as mock_analyze:
            mock_analysis = MagicMock()
            mock_analysis.files_modified_count = 0
            mock_analysis.import_changes = []
            mock_analysis.source_changes = []
            mock_analysis.all_changed_files = []
            mock_analyze.return_value = mock_analysis

            # Ensure context is initially None
            assert user_id_ctx.get() is None

            # Execute run with user 82
            uc.run("job_f138bfe8769d", current_user_id=82)

            # Check that inside worker execution, user_id_ctx had value 82
            assert observed_user_ids == [82]

            # Check that context cleanup reset user_id_ctx back to None
            assert user_id_ctx.get() is None


def test_start_migration_worker_multi_user_isolation():
    """Verify that multiple migration jobs for different users run with isolated contexts."""
    uc = StartMigrationUseCase()
    observed_user_ids = []

    with patch("app.application.use_cases.start_migration.MigrationReportStore") as mock_store_cls, \
         patch("app.application.use_cases.start_migration.WorkspaceManager"), \
         patch.object(uc, "_run_migration_with_retries") as mock_run_retries, \
         patch.object(uc, "_publish", return_value="https://github.com/JavaAPEX/repo"), \
         patch.object(uc, "_reindex_knowledge_base"), \
         patch.object(uc._change_analyzer, "analyze") as mock_analyze:

        mock_store = MagicMock()
        mock_store.read.return_value = {
            "buildTool": "maven",
            "targetJavaVersion": "21",
            "sourceRepoUrl": "https://github.com/spring-projects/spring-petclinic",
            "conversionTypes": ["java_version"],
            "runTests": False,
        }
        mock_store_cls.return_value = mock_store

        mock_analysis = MagicMock()
        mock_analysis.files_modified_count = 0
        mock_analysis.import_changes = []
        mock_analysis.source_changes = []
        mock_analysis.all_changed_files = []
        mock_analyze.return_value = mock_analysis

        def make_fake_result():
            result = MagicMock()
            result.success = True
            result.recipes = []
            result.used_fallback = False
            result.effective_target_java_version = "21"
            result.recipe_selection_reasons = []
            result.build_modernization_lines = []
            result.dependency_upgrades = []
            result.already_compatible = True
            result.phase_results = []
            result.skipped_recipes = []
            result.spring_conversion_requested = False
            result.spring_conversion_supported = None
            result.spring_conversion_note = None
            result.spring_boot_version_before = None
            result.spring_boot_version_after = None
            result.rule_executions = []
            result.project_dir = None
            return result, None, []

        def fake_run_retries(*args, **kwargs):
            observed_user_ids.append(user_id_ctx.get())
            return make_fake_result()

        mock_run_retries.side_effect = fake_run_retries

        # Run Job 1 for user 82
        uc.run("job_user_82", current_user_id=82)
        assert user_id_ctx.get() is None

        # Run Job 2 for user 99
        uc.run("job_user_99", current_user_id=99)
        assert user_id_ctx.get() is None

        assert observed_user_ids == [82, 99]
