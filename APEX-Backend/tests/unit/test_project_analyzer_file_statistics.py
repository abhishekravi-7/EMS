import tempfile
import unittest
from pathlib import Path

from app.infrastructure.analyzers.project_analyzer import ProjectAnalyzer


class ProjectAnalyzerFileStatisticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = ProjectAnalyzer()

    def test_empty_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            analysis = self.analyzer.analyze(root)

            self.assertEqual(analysis.total_file_count, 0)
            self.assertEqual(len(analysis.java_files), 0)
            self.assertEqual(len(analysis.config_files), 0)
            self.assertEqual(len(analysis.other_files), 0)
            self.assertEqual(
                analysis.total_file_count,
                len(analysis.java_files) + len(analysis.config_files) + len(analysis.other_files),
            )

    def test_repository_with_java_files_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            src_dir = root / "src" / "main" / "java" / "com" / "example"
            src_dir.mkdir(parents=True)
            (src_dir / "App.java").write_text("public class App {}")
            (src_dir / "Service.java").write_text("public class Service {}")
            (src_dir / "Model.JAVA").write_text("public class Model {}")

            analysis = self.analyzer.analyze(root)

            self.assertEqual(analysis.total_file_count, 3)
            self.assertEqual(len(analysis.java_files), 3)
            self.assertEqual(len(analysis.config_files), 0)
            self.assertEqual(len(analysis.other_files), 0)
            self.assertEqual(
                analysis.total_file_count,
                len(analysis.java_files) + len(analysis.config_files) + len(analysis.other_files),
            )

    def test_repository_with_xml_and_config_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "pom.xml").write_text("<project></project>")
            (root / "application.yml").write_text("server: port: 8080")
            (root / "config.properties").write_text("key=value")
            (root / "schema.json").write_text("{}")
            (root / "build.gradle.kts").write_text("// gradle")

            analysis = self.analyzer.analyze(root)

            self.assertEqual(analysis.total_file_count, 5)
            self.assertEqual(len(analysis.java_files), 0)
            self.assertEqual(len(analysis.config_files), 5)
            self.assertEqual(len(analysis.other_files), 0)
            self.assertEqual(
                analysis.total_file_count,
                len(analysis.java_files) + len(analysis.config_files) + len(analysis.other_files),
            )

    def test_repository_with_other_files_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "README.md").write_text("# Readme")
            (root / "Dockerfile").write_text("FROM alpine")
            (root / "script.sh").write_text("#!/bin/bash")
            (root / "LICENSE").write_text("MIT")

            analysis = self.analyzer.analyze(root)

            self.assertEqual(analysis.total_file_count, 4)
            self.assertEqual(len(analysis.java_files), 0)
            self.assertEqual(len(analysis.config_files), 0)
            self.assertEqual(len(analysis.other_files), 4)
            self.assertEqual(
                analysis.total_file_count,
                len(analysis.java_files) + len(analysis.config_files) + len(analysis.other_files),
            )

    def test_mixed_repository_with_nested_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            # Root level files
            (root / "pom.xml").write_text("<project></project>")
            (root / "README.md").write_text("# Title")
            (root / "Dockerfile").write_text("FROM openjdk:17")

            # Nested Java files
            java_dir = root / "src" / "main" / "java" / "com" / "example"
            java_dir.mkdir(parents=True)
            (java_dir / "Application.java").write_text("class Application {}")
            (java_dir / "Controller.java").write_text("class Controller {}")
            (java_dir / "Service.java").write_text("class Service {}")

            # Nested test Java file
            test_dir = root / "src" / "test" / "java" / "com" / "example"
            test_dir.mkdir(parents=True)
            (test_dir / "ApplicationTest.java").write_text("class ApplicationTest {}")

            # Nested config files
            res_dir = root / "src" / "main" / "resources"
            res_dir.mkdir(parents=True)
            (res_dir / "application.properties").write_text("app.name=demo")
            (res_dir / "logback.xml").write_text("<configuration/>")

            # Nested other files
            docs_dir = root / "docs" / "architecture"
            docs_dir.mkdir(parents=True)
            (docs_dir / "overview.txt").write_text("architecture")

            analysis = self.analyzer.analyze(root)

            # Expected:
            # Java: 4 (.java)
            # Config: 3 (pom.xml, application.properties, logback.xml)
            # Other: 3 (README.md, Dockerfile, overview.txt)
            # Total: 10
            self.assertEqual(len(analysis.java_files), 4)
            self.assertEqual(len(analysis.config_files), 3)
            self.assertEqual(len(analysis.other_files), 3)
            self.assertEqual(analysis.total_file_count, 10)
            self.assertEqual(
                analysis.total_file_count,
                len(analysis.java_files) + len(analysis.config_files) + len(analysis.other_files),
            )

    def test_noise_and_ignored_directories_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            # Real repository files
            (root / "pom.xml").write_text("<project></project>")
            src_dir = root / "src" / "main" / "java"
            src_dir.mkdir(parents=True)
            (src_dir / "Main.java").write_text("class Main {}")
            (root / "README.md").write_text("docs")

            # Files inside noise / ignored directories (should be skipped)
            git_dir = root / ".git" / "hooks"
            git_dir.mkdir(parents=True)
            (git_dir / "pre-commit.sample").write_text("sample")

            node_modules_dir = root / "node_modules" / "pkg"
            node_modules_dir.mkdir(parents=True)
            (node_modules_dir / "index.js").write_text("js")

            target_dir = root / "target" / "classes"
            target_dir.mkdir(parents=True)
            (target_dir / "Main.class").write_text("bytecode")

            idea_dir = root / ".idea"
            idea_dir.mkdir(parents=True)
            (idea_dir / "workspace.xml").write_text("<xml/>")

            analysis = self.analyzer.analyze(root)

            # Should only count the 3 real files: pom.xml (config), Main.java (java), README.md (other)
            self.assertEqual(len(analysis.java_files), 1)
            self.assertEqual(len(analysis.config_files), 1)
            self.assertEqual(len(analysis.other_files), 1)
            self.assertEqual(analysis.total_file_count, 3)
            self.assertEqual(
                analysis.total_file_count,
                len(analysis.java_files) + len(analysis.config_files) + len(analysis.other_files),
            )


if __name__ == "__main__":
    unittest.main()
