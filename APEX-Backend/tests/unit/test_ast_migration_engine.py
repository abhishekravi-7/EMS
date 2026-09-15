import tempfile
import unittest
from pathlib import Path
from app.infrastructure.migration_engine.automated_migration_runner import AutomatedMigrationRunner
from app.infrastructure.migration_engine.ast_automated_migration_runner import AstMigrationRunner
from app.infrastructure.migration_engine.ast_rule_mapper import AstRuleMapper

class TestAstMigrationEngine(unittest.TestCase):
    def setUp(self):
        self.runner = AutomatedMigrationRunner()
        self.mapper = AstRuleMapper()
        self.ast_runner = AstMigrationRunner(jar_path=Path("non_existent_migration_engine.jar"))

    def test_discovery_and_planning(self):
        plan = self.mapper.build_plan(
            project_root=Path("/dummy/project"),
            source_java="8",
            target_java="17",
            build_tool="MAVEN",
            frameworks=["spring-boot", "javax-ee"]
        )
        self.assertEqual(plan.sourceJavaVersion, 8)
        self.assertEqual(plan.targetJavaVersion, 17)
        self.assertIn("java8-to-11", plan.activePacks)
        self.assertIn("java11-to-17", plan.activePacks)
        self.assertIn("springboot2-to-3", plan.activePacks)
        self.assertIn("javax-to-jakarta", plan.activePacks)

    def test_jakarta_migration_detection(self):
        plan = self.mapper.build_plan(
            project_root=Path("/dummy/project"),
            source_java="11",
            target_java="17",
            build_tool="MAVEN",
            frameworks=["jakarta-ee"]
        )
        self.assertIn("javax-to-jakarta", plan.activePacks)
        self.assertIn("JAVAX-TO-JAKARTA", plan.activeVisitors)

    def test_builtin_ast_transformation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            pom_path = tmp_path / "pom.xml"
            pom_path.write_text(
                """<project>
    <properties>
        <java.version>1.8</java.version>
        <maven.compiler.source>1.8</maven.compiler.source>
        <maven.compiler.target>1.8</maven.compiler.target>
    </properties>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>2.0.4.RELEASE</version>
    </parent>
    <dependencies>
        <dependency>
            <groupId>javax.persistence</groupId>
            <artifactId>javax.persistence-api</artifactId>
        </dependency>
    </dependencies>
</project>""",
                encoding="utf-8"
            )

            src_path = tmp_path / "src" / "main" / "java" / "com" / "example"
            src_path.mkdir(parents=True, exist_ok=True)
            java_file = src_path / "User.java"
            java_file.write_text(
                """package com.example;
import javax.persistence.Entity;
import javax.persistence.Id;
import javax.persistence.Table;

@Entity
@Table(name = "users")
public class User {
    @Id
    private Long id;
}
""",
                encoding="utf-8"
            )

            plan = {
                "planId": "PLAN-test",
                "projectRoot": str(tmp_path),
                "sourceJavaVersion": 8,
                "targetJavaVersion": 17,
                "buildSystem": "MAVEN",
                "activePacks": ["java8-to-11", "java11-to-17", "springboot2-to-3", "javax-to-jakarta"],
                "activeRules": [],
                "activeVisitors": ["JAVAX-TO-JAKARTA", "IMPORT-CLEANUP"]
            }

            result = self.ast_runner.run(tmp_path, plan)
            self.assertTrue(result.success)
            self.assertEqual(result.status, "SUCCESS")

            # Check pom.xml updates
            updated_pom = pom_path.read_text(encoding="utf-8")
            self.assertIn("<java.version>17</java.version>", updated_pom)
            self.assertIn("3.2.5", updated_pom)
            self.assertIn("jakarta.persistence", updated_pom)

            # Check Java file updates
            updated_java = java_file.read_text(encoding="utf-8")
            self.assertIn("import jakarta.persistence.Entity;", updated_java)
            self.assertIn("import jakarta.persistence.Id;", updated_java)
            self.assertNotIn("javax.persistence", updated_java)

if __name__ == '__main__':
    unittest.main()

