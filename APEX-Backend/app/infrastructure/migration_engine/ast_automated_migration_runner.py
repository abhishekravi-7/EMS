import json
import logging
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional
from app.core.config import settings
from app.shared import file_utils

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

class AstMigrationRunner:
    def __init__(self, jar_path: Optional[Path] = None):
        self._jar_path = jar_path or settings.java_migration_engine_jar

    def run(self, project_dir: Path, plan: dict[str, Any]) -> AstMigrationRunResult:
        """Invoke the Java-based AST migration engine via CLI."""
        if not self._jar_path.exists():
            return AstMigrationRunResult(
                success=False,
                status="FAILED",
                error_lines=[f"Migration engine JAR not found at {self._jar_path}. Please build it using 'mvn package' in the migration-engine directory."]
            )

        plan_json = json.dumps(plan)
        
        process = None
        try:
            logger.info("Invoking Java Migration Engine for project: %s", file_utils.to_plain_path_str(project_dir))
            process = subprocess.Popen(
                ["java", "-jar", file_utils.to_plain_path_str(self._jar_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                cwd=str(project_dir)
            )
            
            stdout, stderr = process.communicate(input=plan_json, timeout=settings.migration_timeout_seconds)
            
            # Combine stdout and stderr for logging/reporting
            full_output = []
            if stdout and not stdout.strip().startswith("{"):
                full_output.append(stdout)
            if stderr:
                full_output.append(stderr)
                logger.warning("Migration Engine Output (Stderr/Non-JSON Stdout): %s", stderr)

            if process.returncode != 0:
                return AstMigrationRunResult(
                    success=False,
                    status="FAILED",
                    error_lines=[f"Java process exited with code {process.returncode}"] + full_output
                )
                
            try:
                # Find the JSON block in stdout (in case of garbage output)
                json_start = stdout.find("{")
                if json_start == -1:
                    raise json.JSONDecodeError("No JSON object found", stdout, 0)
                
                json_text = stdout[json_start:]
                result_data = json.loads(json_text)
            except json.JSONDecodeError:
                return AstMigrationRunResult(
                    success=False,
                    status="FAILED",
                    error_lines=["Failed to parse JSON response from migration engine", stdout]
                )

            status = result_data.get("status", "FAILED")
            
            return AstMigrationRunResult(
                success=status in ("SUCCESS", "PARTIAL", "NO_CHANGES", "MANUAL_REVIEW"),
                status=status,
                changed_files=result_data.get("changedFiles", []),
                rule_executions=result_data.get("ruleExecutions", []),
                fallback_requests=result_data.get("fallbackRequests", []),
                log_lines=[f"Migration Engine finished with status: {status}"] + full_output
            )
            
        except subprocess.TimeoutExpired:
            if process:
                process.kill()
            return AstMigrationRunResult(success=False, status="FAILED", error_lines=["Migration engine timed out."])
        except Exception as e:
            logger.exception("Failed to run AST migration engine")
            return AstMigrationRunResult(success=False, status="FAILED", error_lines=[str(e)])
