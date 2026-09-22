import unittest
from pathlib import Path
import tempfile
import shutil

from app.infrastructure.analyzers.frontend_compatibility_analyzer import FrontendCompatibilityAnalyzer
from app.application.services.report_service import _core


class ConversionTypesFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)
        self.analyzer = FrontendCompatibilityAnalyzer()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_jsp_to_react_flow(self):
        """Scenario 1: JSP -> React conversion with dynamic target recommendation."""
        # Setup JSP repo
        jsp_dir = self.repo_path / "src" / "main" / "webapp" / "WEB-INF" / "views"
        jsp_dir.mkdir(parents=True, exist_ok=True)
        (jsp_dir / "welcome.jsp").write_text("<html><body><h1>Welcome</h1></body></html>")
        
        # Analyze repo
        recs = self.analyzer.analyze(self.repo_path)
        self.assertIsNotNone(recs.react)
        self.assertTrue(recs.react.is_recommended)
        react_target = recs.react.target_version
        self.assertTrue(len(react_target) > 0)
        self.assertIn("Compatible", recs.react.compatibility)

        # Config simulation
        options = {
            "uiFrameworkTarget": "React",
            "uiFrameworkVersion": react_target,
            "uiModMode": "JSP -> React",
        }
        ui_target = options.get("uiFrameworkTarget")
        ui_version = options.get("uiFrameworkVersion")
        ui_framework_label = f"{ui_target} {ui_version}".strip() if (ui_target and ui_version) else ui_target

        # Simulated report state
        report_state = {
            "jobId": "test_jsp_react",
            "status": "completed",
            "jspFilesMigrated": 6,
            "jspFrontendFramework": ui_framework_label,
            "sourceJavaVersion": "8",
            "targetJavaVersion": "17",
        }

        # Build report payload
        frontend_result = _core(report_state)
        fm = frontend_result["framework_migrations"]
        self.assertEqual(len(fm), 1)
        self.assertEqual(fm[0]["source_framework"], "JSP")
        self.assertEqual(fm[0]["target_framework"], f"React {react_target}")
        self.assertEqual(fm[0]["files_migrated"], 6)

    def test_jsp_to_angular_flow(self):
        """Scenario 2: JSP -> Angular conversion with dynamic alternative target recommendation."""
        jsp_dir = self.repo_path / "src" / "main" / "webapp"
        jsp_dir.mkdir(parents=True, exist_ok=True)
        (jsp_dir / "index.jsp").write_text("<html><body>Test JSP</body></html>")

        recs = self.analyzer.analyze(self.repo_path)
        self.assertIsNotNone(recs.angular)
        self.assertFalse(recs.angular.is_recommended)
        angular_target = recs.angular.target_version
        self.assertTrue(len(angular_target) > 0)

        options = {
            "uiFrameworkTarget": "Angular",
            "uiFrameworkVersion": angular_target,
            "uiModMode": "JSP -> Angular",
        }
        ui_target = options.get("uiFrameworkTarget")
        ui_version = options.get("uiFrameworkVersion")
        ui_framework_label = f"{ui_target} {ui_version}".strip() if (ui_target and ui_version) else ui_target

        report_state = {
            "jobId": "test_jsp_angular",
            "status": "completed",
            "jspFilesMigrated": 6,
            "jspFrontendFramework": ui_framework_label,
            "sourceJavaVersion": "8",
            "targetJavaVersion": "17",
        }

        frontend_result = _core(report_state)
        fm = frontend_result["framework_migrations"]
        self.assertEqual(len(fm), 1)
        self.assertEqual(fm[0]["source_framework"], "JSP")
        self.assertEqual(fm[0]["target_framework"], f"Angular {angular_target}")
        self.assertEqual(fm[0]["files_migrated"], 6)

    def test_jsf_to_react_flow(self):
        """Scenario 3: JSF -> React conversion with dynamic target recommendation."""
        jsf_dir = self.repo_path / "src" / "main" / "webapp"
        jsf_dir.mkdir(parents=True, exist_ok=True)
        (jsf_dir / "home.xhtml").write_text("<html xmlns:h='http://java.sun.com/jsf/html'></html>")

        recs = self.analyzer.analyze(self.repo_path)
        self.assertIsNotNone(recs.react)
        react_target = recs.react.target_version

        options = {
            "uiFrameworkTarget": "React",
            "uiFrameworkVersion": react_target,
            "uiModMode": "JSF -> React",
        }
        ui_target = options.get("uiFrameworkTarget")
        ui_version = options.get("uiFrameworkVersion")
        ui_framework_label = f"{ui_target} {ui_version}".strip() if (ui_target and ui_version) else ui_target

        report_state = {
            "jobId": "test_jsf_react",
            "status": "completed",
            "jsfFilesMigrated": 3,
            "jsfFrontendFramework": ui_framework_label,
            "sourceJavaVersion": "8",
            "targetJavaVersion": "17",
        }

        frontend_result = _core(report_state)
        fm = frontend_result["framework_migrations"]
        self.assertEqual(len(fm), 1)
        self.assertEqual(fm[0]["source_framework"], "JSF")
        self.assertEqual(fm[0]["target_framework"], f"React {react_target}")
        self.assertEqual(fm[0]["files_migrated"], 3)

    def test_jsf_to_angular_flow(self):
        """Scenario 4: JSF -> Angular conversion with dynamic target recommendation."""
        jsf_dir = self.repo_path / "src" / "main" / "webapp"
        jsf_dir.mkdir(parents=True, exist_ok=True)
        (jsf_dir / "dashboard.xhtml").write_text("<html xmlns:h='http://java.sun.com/jsf/html'></html>")

        recs = self.analyzer.analyze(self.repo_path)
        self.assertIsNotNone(recs.angular)
        angular_target = recs.angular.target_version

        options = {
            "uiFrameworkTarget": "Angular",
            "uiFrameworkVersion": angular_target,
            "uiModMode": "JSF -> Angular",
        }
        ui_target = options.get("uiFrameworkTarget")
        ui_version = options.get("uiFrameworkVersion")
        ui_framework_label = f"{ui_target} {ui_version}".strip() if (ui_target and ui_version) else ui_target

        report_state = {
            "jobId": "test_jsf_angular",
            "status": "completed",
            "jsfFilesMigrated": 3,
            "jsfFrontendFramework": ui_framework_label,
            "sourceJavaVersion": "8",
            "targetJavaVersion": "17",
        }

        frontend_result = _core(report_state)
        fm = frontend_result["framework_migrations"]
        self.assertEqual(len(fm), 1)
        self.assertEqual(fm[0]["source_framework"], "JSF")
        self.assertEqual(fm[0]["target_framework"], f"Angular {angular_target}")
        self.assertEqual(fm[0]["files_migrated"], 3)


if __name__ == "__main__":
    unittest.main()
