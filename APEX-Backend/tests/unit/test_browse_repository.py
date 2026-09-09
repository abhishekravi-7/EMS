import tempfile
import unittest
from pathlib import Path

from app.application.use_cases.browse_repository import RepositoryFileBrowser
from app.infrastructure.workspace.workspace_paths import WorkspacePaths


class BrowseRepositoryTests(unittest.TestCase):
    def test_list_directory_filters_noise_and_build_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            job_id = "test_job_123"
            paths = WorkspacePaths(job_id, storage_dir)
            root = paths.original_repo_dir
            root.mkdir(parents=True)

            # Create real files and folders
            (root / "pom.xml").write_text("<project/>")
            (root / "README.md").write_text("# Hello")
            src_dir = root / "src"
            src_dir.mkdir()
            (src_dir / "Main.java").write_text("class Main {}")

            # Create build/noise directories
            (root / "target").mkdir()
            (root / "target" / "app.jar").write_bytes(b"PK")
            (root / "build").mkdir()
            (root / "build" / "output.txt").write_text("build")
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("git")
            (root / ".gradle").mkdir()
            (root / "node_modules").mkdir()
            (root / ".idea").mkdir()

            browser = RepositoryFileBrowser(storage_dir)
            entries = browser.list_directory(job_id, "")

            entry_names = [e.name for e in entries]
            self.assertIn("pom.xml", entry_names)
            self.assertIn("README.md", entry_names)
            self.assertIn("src", entry_names)

            # Noise / build dirs must not be listed
            self.assertNotIn("target", entry_names)
            self.assertNotIn("build", entry_names)
            self.assertNotIn(".git", entry_names)
            self.assertNotIn(".gradle", entry_names)
            self.assertNotIn("node_modules", entry_names)
            self.assertNotIn(".idea", entry_names)

            # Check subfolder listing
            src_entries = browser.list_directory(job_id, "src")
            self.assertEqual(len(src_entries), 1)
            self.assertEqual(src_entries[0].name, "Main.java")
            self.assertEqual(src_entries[0].type, "file")


if __name__ == "__main__":
    unittest.main()
