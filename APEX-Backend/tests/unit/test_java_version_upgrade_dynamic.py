import unittest
from pathlib import Path
from xml.etree import ElementTree
from app.infrastructure.analyzers.java_version_detector import JavaVersionDetector
from app.infrastructure.migration_engine.ast_rule_mapper import AstRuleMapper
from app.infrastructure.migration_engine.automated_migration_runner import AutomatedMigrationRunner

class TestJavaVersionUpgradeDynamic(unittest.TestCase):
    def setUp(self):
        self.detector = JavaVersionDetector()
        self.mapper = AstRuleMapper()
        self.runner = AutomatedMigrationRunner()

    def test_normalize_java_version(self):
        from app.infrastructure.analyzers.java_version_detector import normalize_java_version
        self.assertEqual(normalize_java_version("1.8"), "8")
        self.assertEqual(normalize_java_version("8"), "8")
        self.assertEqual(normalize_java_version("11"), "11")
        self.assertEqual(normalize_java_version("17"), "17")

    def test_detect_java_version_from_pom(self):
        pom_xml = """<project>
            <properties>
                <java.version>1.8</java.version>
            </properties>
        </project>"""
        root = ElementTree.fromstring(pom_xml)
        version = self.detector.detect("MAVEN", root, "", "")
        self.assertEqual(version, "8")

    def test_detect_maven_compiler_properties(self):
        pom_xml = """<project>
            <properties>
                <maven.compiler.source>1.8</maven.compiler.source>
                <maven.compiler.target>1.8</maven.compiler.target>
            </properties>
        </project>"""
        root = ElementTree.fromstring(pom_xml)
        version = self.detector.detect("MAVEN", root, "", "")
        self.assertEqual(version, "8")

    def test_detect_maven_compiler_release(self):
        pom_xml = """<project>
            <properties>
                <maven.compiler.release>11</maven.compiler.release>
            </properties>
        </project>"""
        root = ElementTree.fromstring(pom_xml)
        version = self.detector.detect("MAVEN", root, "", "")
        self.assertEqual(version, "11")

    def test_mapper_selects_correct_rules(self):
        # Migrating from Java 8 to 17
        plan = self.mapper.build_plan(
            project_root=Path("test"),
            source_java="8",
            target_java="17",
            build_tool="MAVEN",
            frameworks=[]
        )
        self.assertIn("MAVEN-JAVA-UPGRADE", plan.activeRules)
        self.assertEqual(plan.targetJavaVersion, 17)

    def test_mapper_already_at_target(self):
        plan = self.mapper.build_plan(
            project_root=Path("test"),
            source_java="17",
            target_java="17",
            build_tool="MAVEN",
            frameworks=[]
        )
        # Should not include upgrade rules if already compatible
        self.assertNotIn("MAVEN-JAVA-UPGRADE", plan.activeRules)

    def test_mapper_newer_source_version(self):
        plan = self.mapper.build_plan(
            project_root=Path("test"),
            source_java="21",
            target_java="17",
            build_tool="MAVEN",
            frameworks=[]
        )
        self.assertNotIn("MAVEN-JAVA-UPGRADE", plan.activeRules)
        self.assertEqual(plan.targetJavaVersion, 17)

if __name__ == "__main__":
    unittest.main()
