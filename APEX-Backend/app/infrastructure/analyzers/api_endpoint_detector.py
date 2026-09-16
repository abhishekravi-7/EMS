import json
import logging
import subprocess
from pathlib import Path
from typing import Any, List

from app.core.config import BACKEND_ROOT, WORKSPACE_ROOT, settings
from app.core.exceptions import MigrationEngineJarNotFoundError
from app.shared import file_utils

logger = logging.getLogger(__name__)


def resolve_migration_engine_jar(configured_path: Path | None = None) -> Path:
    """Resolve the location of the migration engine JAR dynamically.

    Prioritizes:
      1. Explicit path passed directly to caller
      2. Configured settings path (supports MIGRATION_ENGINE_JAR_PATH env var)
      3. Relative workspace candidates
    """
    if configured_path:
        path = Path(configured_path)
        if path.exists():
            return path

    settings_path = settings.java_migration_engine_jar
    if settings_path and Path(settings_path).exists():
        return Path(settings_path)

    # Candidate locations relative to project workspace / backend root
    candidates = [
        WORKSPACE_ROOT / "migration-engine" / "target" / "migration-engine-1.0.0-SNAPSHOT.jar",
        BACKEND_ROOT / "migration-engine" / "target" / "migration-engine-1.0.0-SNAPSHOT.jar",
        BACKEND_ROOT.parent / "migration-engine" / "target" / "migration-engine-1.0.0-SNAPSHOT.jar",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    return configured_path or settings_path


class ApiEndpointDetector:
    """Detects API endpoints in a Java project by invoking the Java-based
    EndpointDiscoveryEngine.
    """

    def __init__(self, jar_path: Path | None = None) -> None:
        self._configured_jar_path = jar_path

    @property
    def jar_path(self) -> Path:
        return resolve_migration_engine_jar(self._configured_jar_path)

    def detect(self, project_root: Path) -> List[dict[str, Any]]:
        """Invoke the Java discovery engine to find endpoints."""
        jar = self.jar_path
        if not jar.exists():
            msg = f"Migration engine JAR not found at: {jar}. Please build it by running 'mvn clean package' in the 'migration-engine' directory."
            logger.error(msg)
            raise MigrationEngineJarNotFoundError(jar_path=jar, message=msg)

        try:
            logger.info("Invoking Java Endpoint Discovery for project: %s", file_utils.to_plain_path_str(project_root))
            # Use -cp to specify the main class since the JAR's manifest points to AstMigrationEngine
            process = subprocess.run(
                [
                    "java",
                    "-cp",
                    file_utils.to_plain_path_str(jar),
                    "com.javaapex.migration.engine.EndpointDiscoveryEngine",
                    file_utils.to_plain_path_str(project_root)
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120 # Discovery should be relatively fast
            )

            if process.returncode != 0:
                logger.error("Java Endpoint Discovery failed (exit code %s): %s", process.returncode, process.stderr)
                return []

            try:
                report = json.loads(process.stdout)
                endpoints = report.get("apiEndpoints", [])
                logger.info("Detected %d API endpoints.", len(endpoints))
                return endpoints
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON response from Java discovery engine: %s", process.stdout)
                return []

        except subprocess.TimeoutExpired:
            logger.error("Java Endpoint Discovery timed out.")
            return []
        except Exception:
            logger.exception("Unexpected error during API endpoint detection.")
            return []
