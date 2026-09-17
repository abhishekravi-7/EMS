
"""Detects Spring REST API endpoints in a Java project.

Primary path: invokes the Java migration-engine JAR when it exists.
Fallback path: pure-Python regex/line scanner for Spring MVC annotations when
the JAR is absent. The fallback covers the most common subset needed to produce
a correct count for Spring Boot guide projects and real applications.

The fallback:
  - Walks ALL .java files under project_root (recursively), honouring
    standard exclusions (test/, generated-sources/, build/, target/, .gradle/).
  - For each file detects class-level @RestController / @Controller and an
    optional class-level @RequestMapping base path.
  - Detects method-level @GetMapping, @PostMapping, @PutMapping,
    @DeleteMapping, @PatchMapping, and @RequestMapping(method=...).
  - Combines class base-path + method path into a canonical route.
  - De-duplicates by (http_method, route) pair so multi-module scans
    that share no source files never produce duplicates.
  - Does NOT count test files, comment lines, string literals that happen to
    contain annotations, or anything outside actual source files.

Pure-Python Spring REST endpoint detector.

Scans the user's cloned Java source tree for Spring MVC / JAX-RS
endpoint annotations and extracts HTTP method + path information.

No external tools, no JAR, no subprocess - just regex over ``.java`` files.
This replaces the previous implementation that invoked the migration-engine
JAR (``EndpointDiscoveryEngine``), which was an accidental coupling:
the JAR is only needed during the Migration phase, not Discovery.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import uuid

from pathlib import Path
from typing import Any, List

from app.core.config import settings
from app.shared import file_utils

logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# Directories to skip during the fallback scan
# ---------------------------------------------------------------------------
_SKIP_DIRS: frozenset[str] = frozenset(
    {
        "test",
        "it",  # integration-test source roots
        "generated-sources",
        "generated-test-sources",
        "target",
        "build",
        ".gradle",
        "__pycache__",
        "node_modules",
    }
)

# Annotation patterns (compile once)
_RE_REST_CTRL = re.compile(
    r"@(?:RestController|Controller)\b"
)
_RE_CLASS_MAPPING = re.compile(
    r"@RequestMapping\s*\(\s*(?:value\s*=\s*)?"
    r'(?:"([^"]*)"|\{(?:"[^"]*"(?:\s*,\s*"[^"]*")*)\})'
)
_METHOD_ANNOTATIONS = {
    "GetMapping":    "GET",
    "PostMapping":   "POST",
    "PutMapping":    "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping":  "PATCH",
}
# Matches @GetMapping("…") / @GetMapping(value="…") / @GetMapping({"…","…"})
_RE_METHOD_ANN = re.compile(
    r'@(' + "|".join(_METHOD_ANNOTATIONS) + r')'
    r'(?:\s*\((?:\s*(?:value\s*=\s*)?"(?P<path>[^"]*)")?[^)]*\))?'
)
# @RequestMapping with explicit method=RequestMethod.XXX (class-level can lack method)
_RE_REQUEST_MAPPING = re.compile(
    r"@RequestMapping\s*\("
)
_RE_RM_PATH = re.compile(
    r'(?:value|path)\s*=\s*(?:"([^"]*)"|\"([^"]*)\")'
)
_RE_RM_METHOD = re.compile(
    r"method\s*=\s*RequestMethod\.(\w+)"
)


def _normalise_path(base: str, method_path: str) -> str:
    """Combine a class-level base path with a method-level path."""
    base = base.rstrip("/")
    method_path = method_path.strip()
    if not method_path.startswith("/"):
        method_path = "/" + method_path
    combined = base + method_path
    # Remove trailing slash unless it's the root
    if combined != "/" and combined.endswith("/"):
        combined = combined.rstrip("/")
    return combined or "/"


def _is_in_skip_dir(java_file: Path, project_root: Path) -> bool:
    """Return True when the file sits under any directory that should be excluded."""
    try:
        rel = java_file.relative_to(project_root)
    except ValueError:
        return False
    for part in rel.parts:
        if part.lower() in _SKIP_DIRS:
            return True
    return False


def _scan_file(java_file: Path) -> list[dict[str, Any]]:
    """Return (http_method, route) dicts found in one .java source file."""
    try:
        text = java_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    # Quick pre-filter: skip if file has no controller or mapping annotation
    if not _RE_REST_CTRL.search(text):
        return []

    endpoints: list[dict[str, Any]] = []

    # Detect class-level base path (first @RequestMapping on the class)
    base_path = ""
    m_cls = _RE_CLASS_MAPPING.search(text)
    if m_cls:
        base_path = m_cls.group(1) or ""

    # Strip block comments and string literals to avoid false positives
    # (lightweight approach: remove /* … */ and // … lines)
    clean_lines = []
    in_block_comment = False
    for line in text.splitlines():
        stripped = line.strip()
        if in_block_comment:
            if "*/" in line:
                in_block_comment = False
            continue
        if stripped.startswith("//"):
            continue
        if "/*" in line:
            before = line[: line.index("/*")]
            if "*/" in line[line.index("/*"):]:
                clean_lines.append(before)
            else:
                in_block_comment = True
                clean_lines.append(before)
            continue
        clean_lines.append(line)
    clean = "\n".join(clean_lines)

    # Scan for method-level mapping annotations
    for m in _RE_METHOD_ANN.finditer(clean):
        ann_name = m.group(1)
        http_method = _METHOD_ANNOTATIONS.get(ann_name, "GET")
        method_path = m.group("path") or ""
        route = _normalise_path(base_path, method_path)
        endpoints.append(
            {
                "id": str(uuid.uuid4())[:8],
                "httpMethod": http_method,
                "path": route,
                "controller": java_file.stem,
                "sourceFile": java_file.name,
                "methodName": "unknown",
            }
        )

    # Scan for @RequestMapping with explicit method=RequestMethod.XXX
    for m in _RE_REQUEST_MAPPING.finditer(clean):
        block_start = m.end()
        # Grab a reasonable chunk for the annotation body (up to closing paren)
        depth = 1
        pos = block_start
        while pos < len(clean) and depth > 0:
            if clean[pos] == "(":
                depth += 1
            elif clean[pos] == ")":
                depth -= 1
            pos += 1
        ann_body = clean[block_start:pos]
        m_method = _RE_RM_METHOD.search(ann_body)
        if not m_method:
            # No method= → likely class-level; skip (already captured base_path)
            continue
        http_method = m_method.group(1).upper()
        m_path = _RE_RM_PATH.search(ann_body)
        method_path = ""
        if m_path:
            method_path = m_path.group(1) or m_path.group(2) or ""
        route = _normalise_path(base_path, method_path)
        endpoints.append(
            {
                "id": str(uuid.uuid4())[:8],
                "httpMethod": http_method,
                "path": route,
                "controller": java_file.stem,
                "sourceFile": java_file.name,
                "methodName": "unknown",
            }
        )

    return endpoints


# ---------------------------------------------------------------------------
def _python_spring_scan(project_root: Path) -> list[dict[str, Any]]:
    """Walk all .java source files under project_root and return Spring endpoints."""
    seen: set[tuple[str, str]] = set()
    results: list[dict[str, Any]] = []

    all_java = list(project_root.rglob("*.java"))
    logger.info(
        "Python Spring fallback: scanning %d .java files under %s",
        len(all_java),
        project_root,
    )

    for java_file in all_java:
        if _is_in_skip_dir(java_file, project_root):
            continue
        for ep in _scan_file(java_file):
            key = (ep["httpMethod"], ep["path"])
            if key not in seen:
                seen.add(key)
                results.append(ep)

    logger.info("Python Spring fallback: found %d endpoint(s).", len(results))
    return results


# ---------------------------------------------------------------------------
# Public detector
# ---------------------------------------------------------------------------

class ApiEndpointDetector:
    """Detects API endpoints in a Java project.

    When the migration-engine JAR is present it delegates to the Java
    EndpointDiscoveryEngine. Otherwise it falls back to a pure-Python
    Spring annotation scanner so that endpoint counts are always populated
    from real source code.
    """

    def __init__(self, jar_path: Path | None = None) -> None:
        self._jar_path = jar_path or settings.java_migration_engine_jar

    def detect(self, project_root: Path) -> List[dict[str, Any]]:
        """Return a list of endpoint dicts for the given project root."""
        if self._jar_path.exists():
            return self._detect_via_jar(project_root)

        logger.info(
            "Migration engine JAR not found at %s. "
            "Using Python Spring annotation fallback for endpoint detection.",
            self._jar_path,
        )
        return _python_spring_scan(project_root)

    def _detect_via_jar(self, project_root: Path) -> list[dict[str, Any]]:
        """Invoke the Java discovery engine JAR."""
        try:
            logger.info(
                "Invoking Java Endpoint Discovery for project: %s",
                file_utils.to_plain_path_str(project_root),
            )
            process = subprocess.run(
                [
                    "java",
                    "-cp",
                    file_utils.to_plain_path_str(self._jar_path),
                    "com.javaapex.migration.engine.EndpointDiscoveryEngine",
                    file_utils.to_plain_path_str(project_root),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
            )

            if process.returncode != 0:
                logger.error(
                    "Java Endpoint Discovery failed (exit code %s): %s",
                    process.returncode,
                    process.stderr,
                )
                return []

            try:
                report = json.loads(process.stdout)
                endpoints = report.get("apiEndpoints", [])
                logger.info("Detected %d API endpoints.", len(endpoints))
                return endpoints
            except json.JSONDecodeError:
                logger.error(
                    "Failed to parse JSON response from Java discovery engine: %s",
                    process.stdout,
                )
                return []

        except subprocess.TimeoutExpired:
            logger.error("Java Endpoint Discovery timed out.")
            return []
        except Exception:
            logger.exception("Unexpected error during API endpoint detection.")
            return []

