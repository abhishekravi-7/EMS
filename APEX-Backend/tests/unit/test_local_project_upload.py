import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from app.api.v1.endpoints.local_project_controller import _safe_extract_zip, local_project_capabilities
from app.application.use_cases.run_discovery import RunDiscoveryUseCase
from app.infrastructure.persistence.job_repository import JobRepository
from app.infrastructure.workspace.workspace_paths import WorkspacePaths


class LocalProjectUploadTests(unittest.IsolatedAsyncioTestCase):
    async def test_capabilities_returns_enabled(self) -> None:
        res = await local_project_capabilities()
        self.assertTrue(res.enabled)
        self.assertTrue(res.supports_upload)

    def test_safe_extract_zip_with_single_top_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir) / "extracted"

            # Create an in-memory ZIP with a single top directory
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("my-project/pom.xml", "<project><modelVersion>4.0.0</modelVersion></project>")
                zf.writestr("my-project/src/main/java/App.java", "public class App {}")

            project_name = _safe_extract_zip(buf.getvalue(), target_dir)
            self.assertEqual(project_name, "my-project")
            self.assertTrue((target_dir / "pom.xml").is_file())
            self.assertTrue((target_dir / "src/main/java/App.java").is_file())

    def test_safe_extract_zip_without_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir) / "extracted"

            # Create an in-memory ZIP without wrapper
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("pom.xml", "<project><modelVersion>4.0.0</modelVersion></project>")
                zf.writestr("src/main/java/App.java", "public class App {}")

            project_name = _safe_extract_zip(buf.getvalue(), target_dir)
            self.assertEqual(project_name, "local-project")
            self.assertTrue((target_dir / "pom.xml").is_file())
            self.assertTrue((target_dir / "src/main/java/App.java").is_file())

    def test_safe_extract_zip_rejects_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir) / "extracted"
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                pass
            with self.assertRaises(ValueError):
                _safe_extract_zip(buf.getvalue(), target_dir)

    def test_run_discovery_on_local_project_skips_clone(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            job_id = "job_local_test_123"
            paths = WorkspacePaths(job_id, storage_dir)
            paths.original_repo_dir.mkdir(parents=True)
            (paths.original_repo_dir / "pom.xml").write_text("<project><modelVersion>4.0.0</modelVersion></project>")
            (paths.original_repo_dir / "src").mkdir()
            (paths.original_repo_dir / "src" / "Main.java").write_text("class Main {}")

            job_repo = JobRepository(storage_dir)
            job_repo.save_connect_report(
                job_id,
                {
                    "jobId": job_id,
                    "repoUrl": "local://my-project",
                    "owner": "local",
                    "repoName": "my-project",
                    "repoVisibility": "LOCAL",
                    "accessStatus": "LOCAL_PROJECT",
                    "isLocalProject": True,
                },
            )

            mock_cloner = MagicMock()
            mock_analyzer = MagicMock()
            mock_analysis = MagicMock()
            mock_analysis.is_supported = True
            mock_analysis.build_tool = "maven"
            mock_analysis.current_java_version = "17"
            mock_analysis.spring_boot_version = None
            mock_analysis.project_type = "STANDARD_JAVA"
            mock_analysis.spring_framework_version = None
            mock_analysis.spring_boot_signal = None
            mock_analysis.spring_entry_class = None
            mock_analysis.multi_module = False
            mock_analysis.dependency_count = 0
            mock_analysis.frontend = MagicMock(detected=False)
            mock_analysis.frontend.to_dict.return_value = {"detected": False, "type": None}
            mock_analysis.dependencies = []
            mock_analysis.build_plugins = []
            mock_analysis.bom_versions = []
            mock_analysis.frameworks = []
            mock_analysis.has_tests = False
            mock_analysis.java_files = ["src/Main.java"]
            mock_analysis.config_files = ["pom.xml"]
            mock_analysis.other_files = []
            mock_analysis.total_file_count = 2
            mock_analysis.build_warning = None
            mock_analysis.has_src_main = True
            mock_analysis.has_src_test = False
            mock_analysis.has_pom_xml = True
            mock_analysis.has_build_gradle = False
            mock_analysis.has_build_gradle_kts = False
            mock_analysis.has_package_json = False
            mock_analysis.modules = []
            mock_analyzer.analyze.return_value = mock_analysis

            use_case = RunDiscoveryUseCase(
                job_repository=job_repo,
                cloner=mock_cloner,
                analyzer=mock_analyzer,
            )

            outcome = use_case.execute(job_id)

            # Verification: cloner.clone was NEVER called for local project
            mock_cloner.clone.assert_not_called()
            # Analyzer was called on the local project directory
            mock_analyzer.analyze.assert_called_once_with(paths.original_repo_dir)
            self.assertEqual(outcome.response["jobId"], job_id)
            self.assertEqual(outcome.response["status"], "DISCOVERY_COMPLETED")


if __name__ == "__main__":
    unittest.main()
