"""Pure-Python Spring REST endpoint detector.

Scans the user's cloned Java source tree for Spring MVC / JAX-RS
endpoint annotations and extracts HTTP method + path information.

No external tools, no JAR, no subprocess — just regex over ``.java`` files.
This replaces the previous implementation that invoked the migration-engine
JAR (``EndpointDiscoveryEngine``), which was an accidental coupling:
the JAR is only needed during the Migration phase, not Discovery.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Any, List

from app.shared import file_utils

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Annotation patterns
# ---------------------------------------------------------------------------
# Matches @RestController or @Controller (class-level)
_CONTROLLER_RE = re.compile(
    r"@(?:RestController|Controller)\b"
)

# Matches @RequestMapping(... value/path = "..." ...) at class level for base path
_CLASS_MAPPING_RE = re.compile(
    r"@RequestMapping\s*\(\s*(?:[^)]*?)"
    r'(?:value|path)\s*=\s*(?:"([^"]*)"|\{[^}]*"([^"]*)"[^}]*\})'
    r"|@RequestMapping\s*\(\s*\"([^\"]*)\"\s*\)",
)

# Method-level HTTP mappings  →  (annotation_name, optional_path_group)
_METHOD_MAPPING_RE = re.compile(
    r"@(Get|Post|Put|Delete|Patch)Mapping\s*"
    r"(?:\(\s*(?:value\s*=\s*)?\"([^\"]*)\"[^)]*\)|\(\s*\))?",
)

# Grabs the Java method name immediately after the annotation block
_METHOD_NAME_RE = re.compile(
    r"(?:public|protected|private|static|\s)+\s+\w[\w<>\[\],\s]*\s+(\w+)\s*\("
)

_HTTP_METHOD_MAP = {
    "Get": "GET",
    "Post": "POST",
    "Put": "PUT",
    "Delete": "DELETE",
    "Patch": "PATCH",
}

_MAX_JAVA_FILES = 500  # cap to keep discovery fast on large repos


def _extract_class_base_path(source: str) -> str:
    """Return the class-level @RequestMapping path, or empty string."""
    m = _CLASS_MAPPING_RE.search(source)
    if not m:
        return ""
    # groups: (value="..", path="..", bare "..")
    for grp in m.groups():
        if grp is not None:
            return grp.strip("/")
    return ""


def _extract_class_name(source: str) -> str:
    """Return the Java class name (best effort)."""
    # Require a Java declaration context before 'class': access modifier, annotation,
    # or start of line — to avoid matching identifiers that contain 'class' as a word.
    m = re.search(
        r"(?:(?:public|protected|private|abstract|final|static)\s+)+class\s+(\w+)"
        r"|^\s*class\s+(\w+)",
        source,
        re.MULTILINE,
    )
    if not m:
        return "UnknownController"
    return m.group(1) or m.group(2)


def _normalize_path(*parts: str) -> str:
    """Join path segments cleanly."""
    joined = "/".join(p.strip("/") for p in parts if p)
    return "/" + joined if not joined.startswith("/") else joined


def _detect_in_file(java_path: Path) -> list[dict[str, Any]]:
    """Scan a single .java file for endpoint declarations."""
    try:
        source = file_utils.read_text(java_path)
    except Exception:
        return []

    if not source or not _CONTROLLER_RE.search(source):
        return []

    class_name = _extract_class_name(source)
    base_path = _extract_class_base_path(source)
    endpoints: list[dict[str, Any]] = []

    for m in _METHOD_MAPPING_RE.finditer(source):
        annotation_prefix = m.group(1)   # Get / Post / Put / Delete / Patch / Request
        path_suffix = m.group(2) or ""

        http_method = _HTTP_METHOD_MAP.get(annotation_prefix, "GET")

        # Look for the Java method name that follows this annotation
        rest = source[m.end():]
        name_match = _METHOD_NAME_RE.search(rest[:300])
        method_name = name_match.group(1) if name_match else "unknown"

        full_path = _normalize_path(base_path, path_suffix)

        endpoints.append(
            {
                "id": str(uuid.uuid4())[:8],
                "httpMethod": http_method,
                "path": full_path,
                "controller": class_name,
                "methodName": method_name,
            }
        )

    return endpoints


class ApiEndpointDetector:
    """Detects Spring REST API endpoints by scanning the Java source tree.

    Uses a pure-Python Spring annotation scanner to extract endpoint counts
    directly from source code without requiring a JVM or external tool.
    (Legacy support remains if a custom migration-engine JAR is provided).
    """

    def detect(self, project_root: Path) -> List[dict[str, Any]]:
        """Walk the project source tree and collect endpoint declarations.

        Parameters
        ----------
        project_root:
            Root of the cloned user repository (or the resolved project
            sub-directory when the build file is not at the repo root).

        Returns
        -------
        list[dict]
            Each dict has keys: ``id``, ``httpMethod``, ``path``,
            ``controller``, ``methodName``.
        """
        java_files = list(project_root.rglob("*.java"))

        # Filter out generated sources and test-only sources for brevity,
        # but still scan them — endpoint annotations can appear in tests.
        java_files = java_files[:_MAX_JAVA_FILES]

        if not java_files:
            logger.debug("No Java files found under %s; skipping endpoint detection.", project_root)
            return []

        logger.info(
            "Using native Python Spring annotation scanner for API endpoint detection."
            "Scanning %d Java files for REST endpoint annotations under %s",
            len(java_files),
            file_utils.to_plain_path_str(project_root),
        )

        results: list[dict[str, Any]] = []
        for jf in java_files:
            results.extend(_detect_in_file(jf))

        logger.info("Detected %d API endpoints via Python scanner.", len(results))
        return results
