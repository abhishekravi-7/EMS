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
        """Invoke the Java discovery engine to find endpoints, with Python fallback."""
        if not self._jar_path.exists():
            logger.warning("Migration engine JAR not found at %s. Using Python regex endpoint discovery fallback.", self._jar_path)
            return self._fallback_python_detect(project_root)

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
                logger.error("Java Endpoint Discovery failed (exit code %s): %s. Falling back to Python scanner.", process.returncode, process.stderr)
                return self._fallback_python_detect(project_root)

            try:
                report = json.loads(process.stdout)
                endpoints = report.get("apiEndpoints", [])
                logger.info("Detected %d API endpoints.", len(endpoints))
                return endpoints if endpoints else self._fallback_python_detect(project_root)
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON response from Java discovery engine: %s. Falling back to Python scanner.", process.stdout)
                return self._fallback_python_detect(project_root)

        except subprocess.TimeoutExpired:
            logger.error("Java Endpoint Discovery timed out. Falling back to Python scanner.")
            return self._fallback_python_detect(project_root)
        except Exception:
            logger.exception("Unexpected error during API endpoint detection. Falling back to Python scanner.")
            return self._fallback_python_detect(project_root)

    def _fallback_python_detect(self, project_root: Path) -> List[dict[str, Any]]:
        """Fallback Python regex scanner for Spring Boot & JAX-RS API endpoints."""
        import os
        import re

        endpoints = []
        if not project_root.exists():
            return endpoints

        for root, _, files in os.walk(project_root):
            for file in files:
                if not file.endswith(".java"):
                    continue
                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                if "@Controller" not in content and "@RestController" not in content and "@Path" not in content:
                    continue

                # Class-level base path
                class_path = ""
                class_match = re.search(r'@(?:RequestMap|Path|ControllerMap)\s*\((?:value\s*=\s*)?["\']([^"\']+)["\']', content)
                if class_match:
                    class_path = class_match.group(1).rstrip("/")

                # Method-level endpoints
                method_patterns = [
                    (r'@GetMapping\s*\((?:value\s*=\s*|path\s*=\s*)?["\']([^"\']+)["\']', "GET"),
                    (r'@PostMapping\s*\((?:value\s*=\s*|path\s*=\s*)?["\']([^"\']+)["\']', "POST"),
                    (r'@PutMapping\s*\((?:value\s*=\s*|path\s*=\s*)?["\']([^"\']+)["\']', "PUT"),
                    (r'@DeleteMapping\s*\((?:value\s*=\s*|path\s*=\s*)?["\']([^"\']+)["\']', "DELETE"),
                    (r'@PatchMapping\s*\((?:value\s*=\s*|path\s*=\s*)?["\']([^"\']+)["\']', "PATCH"),
                    (r'@RequestMapping\s*\((?:value\s*=\s*|path\s*=\s*)?["\']([^"\']+)["\'](?:\s*,\s*method\s*=\s*RequestMethod\.([A-Z]+))?', "ALL"),
                    (r'@GetMapping(?:\(\s*\))?', "GET"),
                    (r'@PostMapping(?:\(\s*\))?', "POST"),
                ]

                for pattern, http_method in method_patterns:
                    for match in re.finditer(pattern, content):
                        sub_path = ""
                        method = http_method
                        if match.groups() and match.group(1):
                            sub_path = match.group(1)
                            if len(match.groups()) > 1 and match.group(2):
                                method = match.group(2)
                        if method == "ALL":
                            method = "GET"

                        full_endpoint = f"{class_path}/{sub_path.lstrip('/')}".rstrip("/")
                        if not full_endpoint.startswith("/"):
                            full_endpoint = "/" + full_endpoint

                        rel_file = str(file_path.relative_to(project_root)).replace("\\", "/")
                        endpoints.append({
                            "urlPath": full_endpoint,
                            "httpMethod": method,
                            "file": rel_file,
                            "className": file.replace(".java", ""),
                        })

        logger.info("Detected %d API endpoints using Python fallback scanner.", len(endpoints))
        return endpoints
