import unittest
from pathlib import Path
from xml.etree import ElementTree
from app.infrastructure.analyzers.spring_boot_detector import SpringBootDetector
from app.infrastructure.migration_engine.ast_rule_mapper import AstRuleMapper, _parse_major
from app.infrastructure.migration_engine.automated_migration_runner import AutomatedMigrationRunner

class TestSpringBootUpgradeDynamic(unittest.TestCase):
    def setUp(self):
        self.detector = SpringBootDetector()
        self.mapper = AstRuleMapper()
        self.runner = AutomatedMigrationRunner()

    def test_detect_from_parent(self):
        pom_xml = """<project>
            <parent>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-starter-parent</artifactId>
                <version>2.7.18</version>
            </parent>
        </project>"""
        root = ElementTree.fromstring(pom_xml)
        version = self.detector.detect(root, "")
        self.assertEqual(version, "2.7.18")

    def test_detect_from_property(self):
        pom_xml = """<project>
            <properties>
                <spring-boot.version>3.2.5</spring-boot.version>
            </properties>
        </project>"""
        root = ElementTree.fromstring(pom_xml)
        version = self.detector.detect(root, "")
        self.assertEqual(version, "3.2.5")

    def test_detect_from_resolved_property(self):
        pom_xml = """<project>
            <parent>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-starter-parent</artifactId>
                <version>${boot.version}</version>
            </parent>
            <properties>
                <boot.version>2.6.4</boot.version>
            </properties>
        </project>"""
        root = ElementTree.fromstring(pom_xml)
        version = self.detector.detect(root, "")
        self.assertEqual(version, "2.6.4")

    def test_mapper_selects_correct_target(self):
        # Target Java 17 should map to Spring Boot 3.2.5 (based on my catalog change)
        plan = self.mapper.build_plan(
            project_root=Path("test"),
            source_java="8",
            target_java="17",
            build_tool="MAVEN",
            frameworks=["spring-boot"],
            current_boot_version="2.7.18"
        )
        self.assertEqual(plan.targetSpringBootVersion, "3.2.5")
        self.assertIn("springboot2-to-3", plan.activePacks)

    def test_mapper_skips_if_already_at_target(self):
        plan = self.mapper.build_plan(
            project_root=Path("test"),
            source_java="17",
            target_java="17",
            build_tool="MAVEN",
            frameworks=["spring-boot"],
            current_boot_version="3.2.5"
        )
        # Should not add the upgrade pack if already at target
        self.assertNotIn("springboot2-to-3", plan.activePacks)

    def test_version_comparison_is_newer(self):
        self.assertTrue(self.runner._is_newer("3.3.2", "3.2.5"))
        self.assertTrue(self.runner._is_newer("4.0.0", "3.3.2"))
        self.assertTrue(self.runner._is_newer("3.2.5.RELEASE", "2.7.18"))
        self.assertFalse(self.runner._is_newer("2.7.18", "3.2.5"))
        self.assertFalse(self.runner._is_newer("3.2.5", "3.2.5"))

    def test_mapper_handles_newer_source_version(self):
        # Source 4.0.0 is newer than target 3.2.5 (for Java 17)
        plan = self.mapper.build_plan(
            project_root=Path("test"),
            source_java="17",
            target_java="17",
            build_tool="MAVEN",
            frameworks=["spring-boot"],
            current_boot_version="4.0.0"
        )
        # It should still record the target version but skip the static pack
        self.assertEqual(plan.targetSpringBootVersion, "3.2.5")
        self.assertNotIn("springboot2-to-3", plan.activePacks)
        self.assertNotIn("SPRINGBOOT-3", plan.activeRules)

if __name__ == "__main__":
    unittest.main()
