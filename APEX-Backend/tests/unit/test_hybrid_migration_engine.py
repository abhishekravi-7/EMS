"""Unit tests for the Hybrid Neuro-Symbolic Migration Engine."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.infrastructure.migration_engine.ast_automated_migration_runner import AstMigrationRunner
from app.infrastructure.migration_engine.ast_rule_mapper import AstRuleMapper
from app.infrastructure.migration_engine.automated_migration_runner import AutomatedMigrationRunner
from app.infrastructure.migration_engine.llm_self_healing_repair import LlmSelfHealingRepair, RepairResult


class HybridMigrationEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.java_file = self.tmp_dir / "src" / "main" / "java" / "com" / "example" / "Sample.java"
        self.java_file.parent.mkdir(parents=True, exist_ok=True)
        self.java_file.write_text(
            "package com.example;\nimport javax.persistence.Entity;\n@Entity\npublic class Sample {}\n",
            encoding="utf-8",
        )
        self.pom_file = self.tmp_dir / "pom.xml"
        self.pom_file.write_text("<project><properties><java.version>8</java.version></properties></project>", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_ast_rule_mapper_dynamic_planning(self) -> None:
        mapper = AstRuleMapper()
        plan = mapper.build_plan(
            project_root=self.tmp_dir,
            source_java="8",
            target_java="17",
            build_tool="MAVEN",
            frameworks=["spring-boot", "javax-ee"],
        )
        self.assertEqual(plan.sourceJavaVersion, 8)
        self.assertEqual(plan.targetJavaVersion, 17)
        self.assertIn("java8-to-11", plan.activePacks)
        self.assertIn("java11-to-17", plan.activePacks)
        self.assertIn("javax-to-jakarta", plan.activePacks)
        self.assertIn("JAVAX-TO-JAKARTA", plan.activeVisitors)

    def test_ast_runner_fallback_execution(self) -> None:
        runner = AstMigrationRunner(jar_path=Path("non_existent_migration_engine.jar"))
        plan = {
            "targetJavaVersion": 17,
            "activePacks": ["javax-to-jakarta"],
            "activeVisitors": ["JAVAX-TO-JAKARTA"],
        }
        res = runner.run(self.tmp_dir, plan)
        self.assertTrue(res.success)
        mod_java = self.java_file.read_text(encoding="utf-8")
        self.assertIn("import jakarta.persistence.Entity;", mod_java)
        self.assertNotIn("javax.persistence", mod_java)
        mod_pom = self.pom_file.read_text(encoding="utf-8")
        self.assertIn("<java.version>17</java.version>", mod_pom)

    @patch.object(LlmSelfHealingRepair, "_call_llm_sync")
    def test_llm_self_healing_repair(self, mock_llm_call) -> None:
        mock_llm_call.return_value = (
            "```java\npackage com.example;\nimport jakarta.persistence.Entity;\n@Entity\npublic class Sample {}\n```"
        )
        repair = LlmSelfHealingRepair()
        errors = [f"Error in {self.java_file.as_posix()}:12: cannot find symbol javax.persistence"]
        res = repair.repair_build_failures(self.tmp_dir, errors, target_java_version="17")
        self.assertTrue(res.success)
        self.assertIn("src/main/java/com/example/Sample.java", res.repaired_files)

    def test_automated_migration_runner_end_to_end(self) -> None:
        runner = AutomatedMigrationRunner()
        result = runner.run(
            self.tmp_dir,
            "MAVEN",
            "17",
            include_jakarta=True,
            conversion_types=["java_version", "jakarta"],
            enable_llm_repair=False,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.effective_target_java_version, "17")


if __name__ == "__main__":
    unittest.main()
