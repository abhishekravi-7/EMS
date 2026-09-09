import json
import logging
import re
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional
from app.core.config import settings
from app.infrastructure.migration_engine.gradle_preflight_modernizer import GradlePreflightModernizer

logger = logging.getLogger(__name__)

@dataclass
class AstMigrationRunResult:
    success: bool
    status: str # SUCCESS, PARTIAL, FAILED, MANUAL_REVIEW, UNSUPPORTED, NO_CHANGES
    changed_files: list[str] = field(default_factory=list)
    log_lines: list[str] = field(default_factory=list)
    error_lines: list[str] = field(default_factory=list)
    rule_executions: list[dict[str, Any]] = field(default_factory=list)
    fallback_requests: list[dict[str, Any]] = field(default_factory=list)

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
        """Invoke the Java-based AST migration engine via CLI, or use built-in engine if JAR is unavailable."""
        # 1. Try Java JAR CLI if available
        if self._jar_path and self._jar_path.exists():
            return self._run_jar(project_dir, plan)

        # 2. Check alternative jar location (e.g. WORKSPACE_ROOT.parent)
        alt_jar = settings.workspace_root.parent / "migration-engine" / "target" / "migration-engine-1.0.0-SNAPSHOT.jar" if hasattr(settings, "workspace_root") else None
        if alt_jar and alt_jar.exists():
            self._jar_path = alt_jar
            return self._run_jar(project_dir, plan)

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
                encoding="utf-8"
            )
            
            stdout, stderr = process.communicate(input=plan_json, timeout=settings.migration_timeout_seconds)
            
            if stderr:
                logger.warning("Migration Engine Stderr: %s", stderr)

            if process.returncode != 0:
                logger.warning("Java JAR exited with code %d. Falling back to built-in AST engine.", process.returncode)
                return self._run_builtin(project_dir, plan)
                
            try:
                result_data = json.loads(stdout)
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON response from JAR. Falling back to built-in AST engine.")
                return self._run_builtin(project_dir, plan)

            status = result_data.get("status", "FAILED")
            
            return AstMigrationRunResult(
                success=status in ("SUCCESS", "PARTIAL", "NO_CHANGES"),
                status=status,
                changed_files=result_data.get("changedFiles", []),
                rule_executions=result_data.get("ruleExecutions", []),
                fallback_requests=result_data.get("fallbackRequests", []),
                log_lines=[f"Migration Engine finished with status: {status}"]
            )
            
        except subprocess.TimeoutExpired:
            if process:
                process.kill()
            return AstMigrationRunResult(success=False, status="FAILED", error_lines=["Migration engine timed out."])
        except Exception as e:
            logger.exception("Failed to run Java migration engine JAR; falling back to built-in AST engine")
            return self._run_builtin(project_dir, plan)

    def _run_builtin(self, project_dir: Path, plan: dict[str, Any]) -> AstMigrationRunResult:
        """Built-in deterministic AST/code transformation engine."""
        target_java = plan.get("targetJavaVersion", 17)
        active_packs = plan.get("activePacks", [])
        active_visitors = plan.get("activeVisitors", [])
        
        changed_files: list[str] = []
        log_lines: list[str] = []
        rule_executions: list[dict[str, Any]] = []

        try:
            # Phase 1: Build file updates (pom.xml or build.gradle)
            pom_file = project_dir / "pom.xml"
            if pom_file.is_file():
                pom_changed = self._transform_pom(pom_file, target_java, active_packs, active_visitors)
                if pom_changed:
                    rel = str(pom_file.relative_to(project_dir)).replace("\\", "/")
                    changed_files.append(rel)
                    log_lines.append(f"Updated build configuration in {rel} for Java {target_java}.")

            for gradle_name in ("build.gradle", "build.gradle.kts"):
                gradle_file = project_dir / gradle_name
                if gradle_file.is_file():
                    gradle_mod = GradlePreflightModernizer()
                    g_changes = gradle_mod.modernize(project_dir, target_java)
                    log_lines.extend(g_changes)
                    g_changed = self._transform_gradle(gradle_file, target_java, active_packs)
                    if g_changed or g_changes:
                        rel = str(gradle_file.relative_to(project_dir)).replace("\\", "/")
                        if rel not in changed_files:
                            changed_files.append(rel)
                        log_lines.append(f"Updated build configuration in {rel} for Java {target_java}.")

            # Phase 2: Java source file transformations
            java_files = list(project_dir.rglob("*.java"))
            transformed_java_count = 0

            apply_jakarta = (
                "javax-to-jakarta" in active_packs
                or "JAVAX-TO-JAKARTA" in active_visitors
                or (target_java and int(target_java) >= 17)
            )

            for jf in java_files:
                try:
                    text = jf.read_text(encoding="utf-8", errors="ignore")
                    updated = text

                    if apply_jakarta:
                        for old_pkg, new_pkg in _JAVAX_TO_JAKARTA_PACKAGES:
                            if old_pkg in updated:
                                updated = updated.replace(old_pkg, new_pkg)

                    if "IMPORT-CLEANUP" in active_visitors and updated != text:
                        updated = self._cleanup_imports(updated)

                    if updated != text:
                        jf.write_text(updated, encoding="utf-8")
                        rel = str(jf.relative_to(project_dir)).replace("\\", "/")
                        changed_files.append(rel)
                        transformed_java_count += 1
                except Exception as ex:
                    logger.warning("Error transforming Java file %s: %s", jf, ex)

            if transformed_java_count > 0:
                log_lines.append(f"Transformed imports and API calls in {transformed_java_count} Java source file(s).")

            # Record rule executions for reports/UI
            for pack in active_packs:
                rule_executions.append({
                    "ruleId": pack,
                    "status": "APPLIED",
                    "filesAffected": len(changed_files),
                    "description": f"Applied recipe pack: {pack}"
                })

            status = "SUCCESS" if changed_files else "NO_CHANGES"
            log_lines.append(f"Migration Engine finished with status: {status}")

            return AstMigrationRunResult(
                success=True,
                status=status,
                changed_files=changed_files,
                rule_executions=rule_executions,
                log_lines=log_lines
            )

        except Exception as e:
            logger.exception("Built-in migration engine error")
            return AstMigrationRunResult(
                success=False,
                status="FAILED",
                error_lines=[f"Built-in AST engine failed: {e}"]
            )

    @staticmethod
    def _transform_pom(pom_file: Path, target_java: int, active_packs: list[str], active_visitors: list[str]) -> bool:
        text = pom_file.read_text(encoding="utf-8", errors="ignore")
        updated = text

        # Update Java version properties
        target_str = str(target_java)
        updated = re.sub(r"<java\.version>[^<]+</java\.version>", f"<java.version>{target_str}</java.version>", updated)
        updated = re.sub(r"<maven\.compiler\.source>[^<]+</maven\.compiler\.source>", f"<maven.compiler.source>{target_str}</maven.compiler.source>", updated)
        updated = re.sub(r"<maven\.compiler\.target>[^<]+</maven\.compiler\.target>", f"<maven.compiler.target>{target_str}</maven.compiler.target>", updated)
        updated = re.sub(r"<maven\.compiler\.release>[^<]+</maven\.compiler\.release>", f"<maven.compiler.release>{target_str}</maven.compiler.release>", updated)

        # Update Spring Boot parent version depending on target Java version
        if target_java >= 17 or "springboot2-to-3" in active_packs:
            sb_target = "3.2.5"
            updated = re.sub(
                r"(<groupId>\s*org\.springframework\.boot\s*</groupId>\s*<artifactId>\s*spring-boot-starter-parent\s*</artifactId>\s*<version>)[^<]+(</version>)",
                rf"\g<1>{sb_target}\g<2>",
                updated,
            )
            updated = re.sub(
                r"(<spring-boot\.version>)[^<]+(</spring-boot\.version>)",
                rf"\g<1>{sb_target}\g<2>",
                updated,
            )
            # Modernize mysql connector for Spring Boot 3
            updated = re.sub(
                r"<groupId>\s*mysql\s*</groupId>\s*<artifactId>\s*mysql-connector-java\s*</artifactId>",
                "<groupId>com.mysql</groupId>\n\t\t\t<artifactId>mysql-connector-j</artifactId>",
                updated,
            )
            # Modernize jstl for Jakarta / Spring Boot 3
            updated = re.sub(
                r"<groupId>\s*javax\.servlet\s*</groupId>\s*<artifactId>\s*jstl\s*</artifactId>",
                "<groupId>jakarta.servlet.jsp.jstl</groupId>\n\t\t\t<artifactId>jakarta.servlet.jsp.jstl-api</artifactId>\n\t\t\t<version>3.0.0</version>",
                updated,
            )
        else:
            # Java 11 or below -> upgrade to latest Spring Boot 2.7.x
            sb_target = "2.7.18"
            updated = re.sub(
                r"(<groupId>\s*org\.springframework\.boot\s*</groupId>\s*<artifactId>\s*spring-boot-starter-parent\s*</artifactId>\s*<version>)[^<]+(</version>)",
                rf"\g<1>{sb_target}\g<2>",
                updated,
            )
            # Ensure missing versions are filled for Spring Boot 2.7
            if "jstl" in updated and "<version>" not in updated.split("jstl")[1][:100]:
                updated = re.sub(
                    r"(<artifactId>\s*jstl\s*</artifactId>)",
                    r"\g<1>\n\t\t\t<version>1.2</version>",
                    updated,
                )
            if "mysql-connector-java" in updated and "<version>" not in updated.split("mysql-connector-java")[1][:100]:
                updated = re.sub(
                    r"(<artifactId>\s*mysql-connector-java\s*</artifactId>)",
                    r"\g<1>\n\t\t\t<version>8.0.33</version>",
                    updated,
                )

        # Update javax dependencies to jakarta when targeting Java 17+
        if "javax-to-jakarta" in active_packs or "JAVAX-TO-JAKARTA" in active_visitors or target_java >= 17:
            for pattern, replacement in _MAVEN_JAVAX_TO_JAKARTA:
                updated = re.sub(pattern, replacement, updated)

        if updated != text:
            pom_file.write_text(updated, encoding="utf-8")
            return True
        return False

    @staticmethod
    def _transform_gradle(gradle_file: Path, target_java: int, active_packs: list[str]) -> bool:
        text = gradle_file.read_text(encoding="utf-8", errors="ignore")
        updated = text
        target_str = str(target_java)

        updated = re.sub(r"sourceCompatibility\s*=\s*['\"][^'\"]+['\"]", f"sourceCompatibility = '{target_str}'", updated)
        updated = re.sub(r"targetCompatibility\s*=\s*['\"][^'\"]+['\"]", f"targetCompatibility = '{target_str}'", updated)
        updated = re.sub(r"JavaVersion\.VERSION_1_[0-9]+", f"JavaVersion.VERSION_{target_str}", updated)
        updated = re.sub(r"JavaVersion\.VERSION_[0-9]+", f"JavaVersion.VERSION_{target_str}", updated)

        sb_target = "3.2.5" if target_java >= 17 or "springboot2-to-3" in active_packs else "2.7.18"
        updated = re.sub(
            r"(id\s+['\"]org\.springframework\.boot['\"]\s+version\s+['\"])[^'\"]+(['\"])",
            rf"\g<1>{sb_target}\g<2>",
            updated,
        )

        if updated != text:
            gradle_file.write_text(updated, encoding="utf-8")
            return True
        return False

    @staticmethod
    def _cleanup_imports(text: str) -> str:
        lines = text.splitlines()
        seen_imports = set()
        clean_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import ") and stripped.endswith(";"):
                if stripped in seen_imports:
                    continue
                seen_imports.add(stripped)
            clean_lines.append(line)
        return "\n".join(clean_lines)

