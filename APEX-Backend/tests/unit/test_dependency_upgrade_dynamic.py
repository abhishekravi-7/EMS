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
        pom_xml = """<project>
            <dependencies>
                <dependency>
                    <groupId>org.json</groupId>
                    <artifactId>json</artifactId>
                    <version>20230227</version>
                </dependency>
            </dependencies>
        </project>"""
        root = ElementTree.fromstring(pom_xml)
        deps = self.detector.analyze(root, "")
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
            Dependency(group_id="org.json", artifact_id="json", version="20230227", resolved_version="20230227")
        ]
        after = [
            Dependency(group_id="org.json", artifact_id="json", version="20231013", resolved_version="20231013", version_source="Declared in POM")
        ]
        mappings = [{"groupId": "org.json", "artifactId": "json", "targetVersion": "20231013"}]
        
        upgrades = self.runner._compare_dependencies(before, after, mappings)
        self.assertEqual(len(upgrades), 1)
        self.assertEqual(upgrades[0]["groupId"], "org.json")
        self.assertEqual(upgrades[0]["oldVersion"], "20230227")
        self.assertEqual(upgrades[0]["newVersion"], "20231013")
        self.assertEqual(upgrades[0]["status"], "UPGRADED")

    def test_compare_dependencies_unchanged(self):
        before = [
            Dependency(group_id="org.json", artifact_id="json", version="20231013", resolved_version="20231013")
        ]
        after = [
            Dependency(group_id="org.json", artifact_id="json", version="20231013", resolved_version="20231013")
        ]
        mappings = [{"groupId": "org.json", "artifactId": "json", "targetVersion": "20231013"}]
        
        upgrades = self.runner._compare_dependencies(before, after, mappings)
        self.assertEqual(len(upgrades), 0)

if __name__ == "__main__":
    unittest.main()
