import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from app.core.config import settings
from app.infrastructure.migration_engine.gradle_modernizer import GradleModernizer
from app.infrastructure.migration_engine.pom_modernizer import PomModernizer
from app.shared import file_utils

logger = logging.getLogger(__name__)


@dataclass
class AstMigrationRunResult:
    success: bool
    status: str  # SUCCESS, PARTIAL, FAILED, MANUAL_REVIEW, UNSUPPORTED, NO_CHANGES
    changed_files: list[str] = field(default_factory=list)
    log_lines: list[str] = field(default_factory=list)
    error_lines: list[str] = field(default_factory=list)
    rule_executions: list[dict[str, Any]] = field(default_factory=list)
    fallback_requests: list[dict[str, Any]] = field(default_factory=list)
    dependency_upgrades: list[dict[str, str]] = field(default_factory=list)
    spring_boot_before: str | None = None
    spring_boot_after: str | None = None


# Common Java EE -> Jakarta EE namespace mappings
_JAVAX_TO_JAKARTA_PACKAGES = [
    ("javax.persistence.", "jakarta.persistence."),
    ("javax.servlet.", "jakarta.servlet."),
    ("javax.annotation.", "jakarta.annotation."),
    ("javax.validation.", "jakarta.validation."),
    ("javax.transaction.", "jakarta.transaction."),
    ("javax.ws.rs.", "jakarta.ws.rs."),
    ("javax.xml.bind.", "jakarta.xml.bind."),
    ("javax.inject.", "jakarta.inject."),
    ("javax.mail.", "jakarta.mail."),
    ("javax.ejb.", "jakarta.ejb."),
    ("javax.jms.", "jakarta.jms."),
]

# Maven dependency replacements for Jakarta EE
_MAVEN_JAVAX_TO_JAKARTA = [
    (r"<groupId>\s*javax\.persistence\s*</groupId>\s*<artifactId>\s*javax\.persistence-api\s*</artifactId>",
     "<groupId>jakarta.persistence</groupId>\n            <artifactId>jakarta.persistence-api</artifactId>"),
    (r"<groupId>\s*javax\.servlet\s*</groupId>\s*<artifactId>\s*javax\.servlet-api\s*</artifactId>",
     "<groupId>jakarta.servlet</groupId>\n            <artifactId>jakarta.servlet-api</artifactId>"),
    (r"<groupId>\s*javax\.annotation\s*</groupId>\s*<artifactId>\s*javax\.annotation-api\s*</artifactId>",
     "<groupId>jakarta.annotation</groupId>\n            <artifactId>jakarta.annotation-api</artifactId>"),
    (r"<groupId>\s*javax\.validation\s*</groupId>\s*<artifactId>\s*validation-api\s*</artifactId>",
     "<groupId>jakarta.validation</groupId>\n            <artifactId>jakarta.validation-api</artifactId>"),
    (r"<groupId>\s*javax\.transaction\s*</groupId>\s*<artifactId>\s*javax\.transaction-api\s*</artifactId>",
     "<groupId>jakarta.transaction</groupId>\n            <artifactId>jakarta.transaction-api</artifactId>"),
]

class AstMigrationRunner:
    def __init__(self, jar_path: Optional[Path] = None):
        self._jar_path = jar_path or settings.java_migration_engine_jar

    def run(self, project_dir: Path, plan: dict[str, Any]) -> AstMigrationRunResult:
        """Invoke the Java-based AST migration engine via CLI with in-process Python fallback."""
        if not self._jar_path.exists():
            logger.info("Migration engine JAR not found at %s. Executing in-process Python AST fallback rules.", self._jar_path)
            return self._run_python_fallback_rules(project_dir, plan)

        # 3. Fallback to built-in AST / Rule Engine
        logger.info("Java migration engine JAR not found at %s. Executing built-in AST migration engine.", self._jar_path)
        return self._run_builtin(project_dir, plan)

    def _run_jar(self, project_dir: Path, plan: dict[str, Any]) -> AstMigrationRunResult:
        plan_json = json.dumps(plan)
        process = None

        try:
            logger.info("Invoking Java Migration Engine for project: %s", project_dir)
            process = subprocess.Popen(
                ["java", "-jar", str(self._jar_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )

            stdout, stderr = process.communicate(input=plan_json, timeout=settings.migration_timeout_seconds)

            if stderr:
                logger.warning("Migration Engine Stderr: %s", stderr)

            if process.returncode != 0:
                logger.warning("Java process exited with code %s. Falling back to in-process rules.", process.returncode)
                fallback_res = self._run_python_fallback_rules(project_dir, plan)
                fallback_res.log_lines.insert(0, f"Java process exited with code {process.returncode}; executed Python fallback AST engine.")
                return fallback_res

            try:
                result_data = json.loads(stdout)
            except json.JSONDecodeError:
                fallback_res = self._run_python_fallback_rules(project_dir, plan)
                fallback_res.log_lines.insert(0, "Failed to parse Java engine JSON; executed Python fallback AST engine.")
                return fallback_res

            status = result_data.get("status", "FAILED")
            changed = result_data.get("changedFiles", [])

            return AstMigrationRunResult(
                success=status in ("SUCCESS", "PARTIAL", "NO_CHANGES"),
                status=status,
                changed_files=changed,
                rule_executions=result_data.get("ruleExecutions", []),
                fallback_requests=result_data.get("fallbackRequests", []),
                log_lines=[f"Migration Engine finished with status: {status}, changed {len(changed)} files."],
            )

        except subprocess.TimeoutExpired:
            if process:
                process.kill()
            return AstMigrationRunResult(
                success=False,
                status="FAILED",
                error_lines=["Migration engine timed out."],
            )
        except Exception as e:
            logger.exception("Failed to run AST migration engine; triggering Python fallback")
            fallback_res = self._run_python_fallback_rules(project_dir, plan)
            fallback_res.error_lines.append(f"Subprocess error: {e}")
            return fallback_res

    def _run_python_fallback_rules(self, project_dir: Path, plan: dict[str, Any]) -> AstMigrationRunResult:
        """In-process Python AST & Regex transformation fallback engine."""
        changed_files: list[str] = []
        logs: list[str] = ["In-process Python Fallback AST Engine started."]
        target_java = str(plan.get("targetJavaVersion") or "17")
        active_visitors = plan.get("activeVisitors", [])
        active_packs = plan.get("activePacks", [])

        # 1. Modernize Build Manifest (pom.xml or build.gradle)
        pom_path = project_dir / "pom.xml"
        dep_upgrades: list[dict[str, str]] = []
        sb_before: str | None = None
        sb_after: str | None = None

        if pom_path.exists():
            pom_res = PomModernizer().modernize(pom_path, target_java)
            dep_upgrades = pom_res.dependency_upgrades
            sb_before = pom_res.spring_boot_before
            sb_after = pom_res.spring_boot_after
            if pom_res.modified:
                changed_files.extend(pom_res.changed_files)
                logs.extend(pom_res.log_lines)
        elif (project_dir / "build.gradle").exists() or (project_dir / "build.gradle.kts").exists():
            gradle_res = GradleModernizer().modernize(project_dir, target_java)
            dep_upgrades = gradle_res.dependency_upgrades
            sb_before = gradle_res.spring_boot_before
            sb_after = gradle_res.spring_boot_after
            if gradle_res.modified:
                changed_files.extend(gradle_res.changed_files)
                logs.extend(gradle_res.log_lines)

        # 2. Modernize Java source files (Javax to Jakarta, JUnit 4 to 5, Import cleanup)
        for java_path in project_dir.rglob("*.java"):
            source = file_utils.read_text(java_path)
            original_source = source

            if "javax-to-jakarta" in active_packs or "JAVAX-TO-JAKARTA" in active_visitors or "jakarta" in str(active_packs):
                source = re.sub(r"\bjavax\.persistence\b", "jakarta.persistence", source)
                source = re.sub(r"\bjavax\.servlet\b", "jakarta.servlet", source)
                source = re.sub(r"\bjavax\.annotation\b", "jakarta.annotation", source)
                source = re.sub(r"\bjavax\.validation\b", "jakarta.validation", source)
                source = re.sub(r"\bjavax\.ws\.rs\b", "jakarta.ws.rs", source)
                source = re.sub(r"\bjavax\.xml\.bind\b", "jakarta.xml.bind", source)

            if "junit" in str(active_packs) or "junit" in source:
                source = source.replace("import org.junit.Test;", "import org.junit.jupiter.api.Test;")
                source = source.replace("import org.junit.Before;", "import org.junit.jupiter.api.BeforeEach;")
                source = source.replace("import org.junit.After;", "import org.junit.jupiter.api.AfterEach;")
                source = source.replace("import org.junit.Ignore;", "import org.junit.jupiter.api.Disabled;")
                source = source.replace("@Before\n", "@BeforeEach\n")
                source = source.replace("@After\n", "@AfterEach\n")
                source = source.replace("@Ignore\n", "@Disabled\n")

            if source != original_source:
                java_path.write_text(source, encoding="utf-8")
                rel_path = java_path.relative_to(project_dir).as_posix()
                changed_files.append(rel_path)

        logs.append(f"In-process Python Fallback AST Engine completed. Transformed {len(changed_files)} file(s).")
        return AstMigrationRunResult(
            success=True,
            status="SUCCESS" if changed_files else "NO_CHANGES",
            changed_files=changed_files,
            log_lines=logs,
            dependency_upgrades=dep_upgrades,
            spring_boot_before=sb_before,
            spring_boot_after=sb_after,
        )
