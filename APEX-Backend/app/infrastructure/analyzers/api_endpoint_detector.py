import json
import logging
import subprocess
from pathlib import Path
from typing import Any, List

from app.core.config import settings
from app.shared import file_utils

logger = logging.getLogger(__name__)

class ApiEndpointDetector:
    """Detects API endpoints in a Java project by invoking the Java-based
    EndpointDiscoveryEngine.
    """

    def __init__(self, jar_path: Path | None = None) -> None:
        # Use the same JAR as the migration engine
        self._jar_path = jar_path or settings.java_migration_engine_jar

    def detect(self, project_root: Path) -> List[dict[str, Any]]:
        """Invoke the Java discovery engine to find endpoints."""
        if not self._jar_path.exists():
            logger.warning("Migration engine JAR not found at %s. Skipping endpoint detection.", self._jar_path)
            return []

        try:
            logger.info("Invoking Java Endpoint Discovery for project: %s", file_utils.to_plain_path_str(project_root))
            # Use -cp to specify the main class since the JAR's manifest points to AstMigrationEngine
            process = subprocess.run(
                [
                    "java",
                    "-cp",
                    file_utils.to_plain_path_str(self._jar_path),
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
