import unittest
from pathlib import Path
from xml.etree import ElementTree
from app.infrastructure.analyzers.dependency_analyzer import Dependency, DependencyAnalyzer
from app.infrastructure.migration_engine.ast_rule_mapper import AstRuleMapper
from app.infrastructure.migration_engine.automated_migration_runner import AutomatedMigrationRunner

class TestDependencyUpgradeDynamic(unittest.TestCase):
    def setUp(self):
        self.detector = DependencyAnalyzer()
        self.mapper = AstRuleMapper()
        self.runner = AutomatedMigrationRunner()

    def test_detect_dependencies_from_pom(self):
        # We need to mock the filesystem and command runner because analyze now runs mvn
        import unittest.mock as mock
        from app.shared.command_runner import CommandResult
        
        with mock.patch("app.infrastructure.analyzers.dependency_analyzer.run_command") as mock_run:
            with mock.patch("pathlib.Path.exists", return_value=True):
                 with mock.patch("pathlib.Path.read_text", side_effect=[
                     "[INFO] com.example:parent:pom:1.0.0\n[INFO] +- org.json:json:jar:20230227:compile", # tree
                     "<project/>" # effective-pom
                 ]):
                     mock_run.return_value = CommandResult([], 0, "success", "")
                     
                     deps = self.detector.analyze(ElementTree.Element("project"), "", Path("."))
                     self.assertEqual(len(deps), 1)
                     self.assertEqual(deps[0].group_id, "org.json")
                     self.assertEqual(deps[0].artifact_id, "json")
                     self.assertEqual(deps[0].version, "20230227")

    def test_mapper_includes_dependency_upgrade_pack(self):
        plan = self.mapper.build_plan(
            project_root=Path("test"),
            source_java="8",
            target_java="17",
            build_tool="MAVEN",
            frameworks=[],
            conversion_types=["java_version"]
        )
        self.assertIn("dependency-upgrade", plan.activePacks)
        self.assertIn("MAVEN-DEPENDENCY-UPGRADE", plan.activeRules)
        self.assertTrue(len(plan.dependencyMappings) > 0)

    def test_compare_dependencies_detects_upgrade(self):
        before = [
            Dependency(group_id="org.json", artifact_id="json", version="20230227", resolved_version="20230227", module="root", scope="compile")
        ]
        after = [
            Dependency(group_id="org.json", artifact_id="json", version="20231013", resolved_version="20231013", version_source="Declared in POM", module="root", scope="compile")
        ]
        mappings = [{"groupId": "org.json", "artifactId": "json", "targetVersion": "20231013"}]
        
        upgrades = self.runner._compare_dependencies(before, after, mappings)
        upgrade_found = next((u for u in upgrades if u["status"] == "UPGRADED"), None)
        self.assertIsNotNone(upgrade_found)
        self.assertEqual(upgrade_found["groupId"], "org.json")
        self.assertEqual(upgrade_found["sourceVersion"], "20230227")
        self.assertEqual(upgrade_found["resolvedTargetVersion"], "20231013")

    def test_compare_dependencies_reports_every_dependency(self):
        before = [
            Dependency(group_id="org.json", artifact_id="json", version="20231013", resolved_version="20231013", module="root", scope="compile"),
            Dependency(group_id="com.google.guava", artifact_id="guava", version="32.0.0-jre", resolved_version="32.0.0-jre", module="root", scope="compile")
        ]
        after = [
            Dependency(group_id="org.json", artifact_id="json", version="20231013", resolved_version="20231013", module="root", scope="compile"),
            Dependency(group_id="com.google.guava", artifact_id="guava", version="32.0.0-jre", resolved_version="32.0.0-jre", module="root", scope="compile")
        ]
        # Mappings don't matter for "reporting every dependency"
        results = self.runner._compare_dependencies(before, after, [])
        self.assertEqual(len(results), 2)
        # Verify both are UNCHANGED
        for res in results:
             self.assertEqual(res["status"], "UNCHANGED")
             self.assertIn("reason", res)
             self.assertNotEqual(res["reason"], "Same")

    def test_compare_dependencies_detects_added_removed(self):
        before = [
            Dependency(group_id="org.json", artifact_id="json", version="20231013", resolved_version="20231013", module="root", scope="compile")
        ]
        after = [
            Dependency(group_id="com.google.guava", artifact_id="guava", version="32.0.0-jre", resolved_version="32.0.0-jre", module="root", scope="compile")
        ]
        results = self.runner._compare_dependencies(before, after, [])
        self.assertEqual(len(results), 2)
        
        status_map = {r["groupId"]: r["status"] for r in results}
        self.assertEqual(status_map["org.json"], "REMOVED")
        self.assertEqual(status_map["com.google.guava"], "ADDED")

    def test_compare_dependencies_prevents_downgrade_strict(self):
        before = [
            Dependency(group_id="org.apache.commons", artifact_id="commons-lang3", version="3.20.0", resolved_version="3.20.0", module="root", scope="compile")
        ]
        # Even if 'after' somehow has 3.14.0 (e.g. from a previous failed run or incorrect engine)
        after = [
            Dependency(group_id="org.apache.commons", artifact_id="commons-lang3", version="3.14.0", resolved_version="3.14.0", module="root", scope="compile")
        ]
        mappings = [{"groupId": "org.apache.commons", "artifactId": "commons-lang3", "targetVersion": "3.14.0"}]
        
        results = self.runner._compare_dependencies(before, after, mappings)
        res = next((r for r in results if r["artifactId"] == "commons-lang3"), None)
        self.assertEqual(res["status"], "MANUAL_REVIEW")
        self.assertIn("downgrade prevented", res["reason"])
