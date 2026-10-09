"""Detects REST API endpoints in Java source files (Spring Boot / Spring MVC / JAX-RS)."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, List

from app.core.config import settings
from app.shared import file_utils

logger = logging.getLogger(__name__)

_TEST_DIR_PARTS = {"test", "tests", "androidtest"}

_SPRING_MAPPING_METHODS = {
    "GetMapping": ["GET"],
    "PostMapping": ["POST"],
    "PutMapping": ["PUT"],
    "DeleteMapping": ["DELETE"],
    "PatchMapping": ["PATCH"],
    "OptionsMapping": ["OPTIONS"],
    "HeadMapping": ["HEAD"],
    "GET": ["GET"],
    "POST": ["POST"],
    "PUT": ["PUT"],
    "DELETE": ["DELETE"],
    "PATCH": ["PATCH"],
    "OPTIONS": ["OPTIONS"],
    "HEAD": ["HEAD"],
}

_ALL_MAPPINGS = set(_SPRING_MAPPING_METHODS.keys()) | {"RequestMapping", "Path"}


def _strip_comments(text: str) -> str:
    """Strip single-line and block comments from Java source code, preserving string literals."""
    out: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    quote_char = ""

    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\":
                if i + 1 < n:
                    out.append(text[i + 1])
                    i += 2
                    continue
            elif c == quote_char:
                in_string = False
            i += 1
        else:
            if c in ('"', "'"):
                in_string = True
                quote_char = c
                out.append(c)
                i += 1
            elif c == "/" and i + 1 < n and text[i + 1] == "/":
                # Single-line comment: skip until newline
                i += 2
                while i < n and text[i] != "\n":
                    i += 1
            elif c == "/" and i + 1 < n and text[i + 1] == "*":
                # Block comment: skip until */
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2  # skip */
            else:
                out.append(c)
                i += 1

    return "".join(out)


def _find_matching_paren(text: str, start_idx: int) -> int:
    """Given index of '(', returns index of matching ')'."""
    depth = 0
    in_string = False
    quote_char = ""
    i = start_idx
    n = len(text)
    while i < n:
        c = text[i]
        if in_string:
            if c == "\\":
                i += 2
                continue
            elif c == quote_char:
                in_string = False
        else:
            if c in ('"', "'"):
                in_string = True
                quote_char = c
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _find_matching_brace(text: str, start_idx: int) -> int:
    """Given index of '{', returns index of matching '}'."""
    depth = 0
    in_string = False
    quote_char = ""
    i = start_idx
    n = len(text)
    while i < n:
        c = text[i]
        if in_string:
            if c == "\\":
                i += 2
                continue
            elif c == quote_char:
                in_string = False
        else:
            if c in ('"', "'"):
                in_string = True
                quote_char = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


_ALL_HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]


def _clean_path(p: str) -> str:
    """Strip query parameters and surrounding whitespace from an endpoint path."""
    p = p.strip()
    if "?" in p:
        p = p.split("?")[0].strip()
    return p


def _extract_annotation_paths(arg_str: str) -> list[str]:
    """Extract path string(s) from annotation arguments.

    Supports:
    - "/path"
    - path = "/path", value = "/path"
    - {"/a", "/b"}
    - path = {"/a", "/b"}, value = {"/a", "/b"}
    - Query parameters stripped
    """
    if not arg_str or not arg_str.strip():
        return [""]
    arg = arg_str.strip()

    # 1. value = { ... } or path = { ... }
    m_named_arr = re.search(r'(?:value|path)\s*=\s*\{([^}]*)\}', arg)
    if m_named_arr:
        raw_items = re.findall(r'["\']([^"\']*)["\']', m_named_arr.group(1))
        cleaned = [_clean_path(item) for item in raw_items]
        return cleaned if cleaned else [""]

    # 2. value = "..." or path = "..."
    m_named = re.search(r'(?:value|path)\s*=\s*["\']([^"\']*)["\']', arg)
    if m_named:
        return [_clean_path(m_named.group(1))]

    # 3. Direct array at start: { ... }
    m_arr = re.search(r'^\s*\{([^}]*)\}', arg)
    if m_arr:
        raw_items = re.findall(r'["\']([^"\']*)["\']', m_arr.group(1))
        cleaned = [_clean_path(item) for item in raw_items]
        return cleaned if cleaned else [""]

    # 4. Direct quoted string at start (e.g. "/path" or "/path", method = ...)
    m_direct = re.search(r'^\s*["\']([^"\']*)["\']', arg)
    if m_direct:
        return [_clean_path(m_direct.group(1))]

    return [""]


def _extract_request_mapping_methods(arg_str: str) -> list[str]:
    """Extract HTTP method(s) from @RequestMapping(..., method = ...).

    If method attribute is not specified, Spring MVC maps to all HTTP methods.
    Returns all applicable HTTP methods rather than blindly defaulting to GET.
    """
    if not arg_str or not arg_str.strip():
        return _ALL_HTTP_METHODS.copy()

    m_match = re.search(r'method\s*=\s*(?:\{([^}]*)\}|(?:[A-Za-z0-9_.]+\.)?([A-Za-z_]+))', arg_str)
    if not m_match:
        return _ALL_HTTP_METHODS.copy()

    raw = m_match.group(1) or m_match.group(2) or ""
    methods: list[str] = []
    for item in re.findall(r'(?:[A-Za-z0-9_.]+\.)?([A-Za-z_]+)', raw):
        m_upper = item.upper()
        if m_upper in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
            methods.append(m_upper)
    return methods if methods else _ALL_HTTP_METHODS.copy()


def _combine_paths(class_path: str, method_path: str) -> str:
    """Combine class-level and method-level mapping paths into a normalized endpoint URL path."""
    cp = (class_path or "").strip()
    mp = (method_path or "").strip()

    if "?" in cp:
        cp = cp.split("?")[0].strip()
    if "?" in mp:
        mp = mp.split("?")[0].strip()

    cp = cp.rstrip("/")
    if cp and not cp.startswith("/"):
        cp = "/" + cp

    mp = mp.strip()
    if mp and not mp.startswith("/"):
        mp = "/" + mp
    mp = mp.rstrip("/")

    full = cp + mp
    full = re.sub(r"/+", "/", full)
    if not full.startswith("/"):
        full = "/" + full
    if len(full) > 1 and full.endswith("/"):
        full = full.rstrip("/")

    return full if full else "/"


def _extract_class_header_annotations_blob(header_text: str) -> str:
    """Extract annotations blob preceding a class declaration.

    Finds the last top-level delimiter (';' or '}') outside strings and parentheses.
    This prevents braces inside annotations (e.g. @RequestMapping("/owners/{ownerId}")
    or array initializers {"/a", "/b"}) from corrupting the extracted annotations.
    """
    depth = 0
    in_str = False
    quote_char = ""
    last_delim = -1
    for idx, ch in enumerate(header_text):
        if in_str:
            if ch == "\\":
                continue
            elif ch == quote_char:
                in_str = False
        else:
            if ch in ('"', "'"):
                in_str = True
                quote_char = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif depth == 0 and ch in (";", "}"):
                last_delim = idx

    return header_text[last_delim + 1:] if last_delim != -1 else header_text


class ApiEndpointDetector:
    """Detects REST API endpoints in Java source files (Spring Boot / Spring MVC / JAX-RS)."""

    def __init__(self, jar_path: Path | None = None) -> None:
        self._jar_path = jar_path or getattr(settings, "java_migration_engine_jar", None)

    def detect(self, project_root: Path) -> List[dict[str, Any]]:
        """Scan repository Java source files and return structured API endpoints."""
        endpoints: List[dict[str, Any]] = []
        seen_endpoints: set[tuple[str, str]] = set()

        if not project_root.exists():
            return endpoints

        for root, _, files in os.walk(project_root):
            for file in files:
                if not file.endswith(".java"):
                    continue
                file_path = Path(root) / file

                try:
                    rel_path = file_path.relative_to(project_root)
                except ValueError:
                    rel_path = Path(file)

                # Skip test directories (e.g. src/test/java, androidTest)
                if any(part.lower() in _TEST_DIR_PARTS for part in rel_path.parts):
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                if not content.strip():
                    continue

                # Quick pre-filter: file must contain at least one controller or mapping annotation
                if not any(token in content for token in (
                    "@Controller", "@RestController", "@RequestMapping",
                    "@GetMapping", "@PostMapping", "@PutMapping", "@DeleteMapping",
                    "@PatchMapping", "@Path"
                )):
                    continue

                file_endpoints = self._parse_java_file(content, str(rel_path))
                for ep in file_endpoints:
                    dedup_key = (ep["httpMethod"], ep["path"])
                    if dedup_key not in seen_endpoints:
                        seen_endpoints.add(dedup_key)
                        endpoints.append(ep)

        return endpoints

    def _fallback_python_detect(self, project_root: Path) -> List[dict[str, Any]]:
        """Backward-compatible alias for detect."""
        return self.detect(project_root)

    def _parse_java_file(self, content: str, rel_path: str) -> List[dict[str, Any]]:
        """Parse a Java file and extract REST API endpoints declared on controllers."""
        clean = _strip_comments(content)
        endpoints: List[dict[str, Any]] = []
        file_seen: set[tuple[str, str]] = set()

        class_regex = re.compile(r'(?:^|\s)class\s+([A-Za-z0-9_$]+)', re.MULTILINE)
        for class_match in class_regex.finditer(clean):
            class_name = class_match.group(1)
            class_pos = class_match.start()

            # Inspect class header for controller annotations
            header_text = clean[:class_pos]
            class_annotations_blob = _extract_class_header_annotations_blob(header_text)

            is_controller = any(
                re.search(rf'@{anno}\b', class_annotations_blob)
                for anno in ("RestController", "Controller", "RequestMapping", "Path")
            )
            if not is_controller:
                continue

            # Extract class-level base path (does not create an endpoint by itself)
            class_paths = [""]
            class_req = re.search(r'@(?:RequestMapping|Path)\b', class_annotations_blob)
            if class_req:
                args = ""
                idx = class_annotations_blob.find("(", class_req.start())
                if idx != -1:
                    end_p = _find_matching_paren(class_annotations_blob, idx)
                    if end_p != -1:
                        args = class_annotations_blob[idx + 1:end_p]
                class_paths = _extract_annotation_paths(args)

            body_start = clean.find("{", class_pos)
            if body_start == -1:
                continue

            body_end = _find_matching_brace(clean, body_start)
            limit = body_end if body_end != -1 else len(clean)

            i = body_start + 1
            while i < limit:
                at_idx = clean.find("@", i, limit)
                if at_idx == -1:
                    break

                m_anno = re.match(r'@([A-Za-z0-9_$]+)', clean[at_idx:limit])
                if not m_anno:
                    i = at_idx + 1
                    continue

                anno_name = m_anno.group(1)
                if anno_name not in _ALL_MAPPINGS:
                    i = at_idx + len(m_anno.group(0))
                    continue

                anno_end = at_idx + len(m_anno.group(0))
                anno_args = ""
                cursor = anno_end
                while cursor < limit and clean[cursor].isspace():
                    cursor += 1
                if cursor < limit and clean[cursor] == "(":
                    end_p = _find_matching_paren(clean, cursor)
                    if end_p != -1:
                        anno_args = clean[cursor + 1:end_p]
                        cursor = end_p + 1

                if anno_name in _SPRING_MAPPING_METHODS:
                    http_methods = _SPRING_MAPPING_METHODS[anno_name]
                    sub_paths = _extract_annotation_paths(anno_args)
                elif anno_name == "RequestMapping":
                    http_methods = _extract_request_mapping_methods(anno_args)
                    sub_paths = _extract_annotation_paths(anno_args)
                elif anno_name == "Path":
                    http_methods = ["GET"]
                    sub_paths = _extract_annotation_paths(anno_args)
                else:
                    http_methods = ["GET"]
                    sub_paths = [""]

                method_name = ""
                scan_pos = cursor
                found_method = False

                while scan_pos < limit:
                    while scan_pos < limit and clean[scan_pos].isspace():
                        scan_pos += 1
                    if scan_pos >= limit:
                        break

                    # Skip other annotations on the method (e.g. @ResponseBody, @PreAuthorize(...))
                    if clean[scan_pos] == "@":
                        scan_pos += 1
                        while scan_pos < limit and (clean[scan_pos].isalnum() or clean[scan_pos] in "_$"):
                            scan_pos += 1
                        while scan_pos < limit and clean[scan_pos].isspace():
                            scan_pos += 1
                        if scan_pos < limit and clean[scan_pos] == "(":
                            end_anno_p = _find_matching_paren(clean, scan_pos)
                            if end_anno_p != -1:
                                scan_pos = end_anno_p + 1
                        continue

                    semi_idx = clean.find(";", scan_pos, limit)
                    brace_idx = clean.find("{", scan_pos, limit)
                    paren_idx = clean.find("(", scan_pos, limit)

                    earliest_stop = min([idx for idx in (semi_idx, brace_idx) if idx != -1] or [limit])
                    if paren_idx == -1 or paren_idx > earliest_stop:
                        break

                    pre_paren_text = clean[scan_pos:paren_idx].strip()
                    m_ident = re.search(r'([A-Za-z0-9_$]+)\s*$', pre_paren_text)
                    if m_ident:
                        method_name = m_ident.group(1)
                        found_method = True

                    end_method_params = _find_matching_paren(clean, paren_idx)
                    if end_method_params != -1:
                        scan_pos = end_method_params + 1
                    else:
                        scan_pos = paren_idx + 1
                    break

                if found_method and method_name:
                    formatted_file = rel_path.replace("\\", "/")
                    line_number = clean[:at_idx].count("\n") + 1
                    for cp in class_paths:
                        for sp in sub_paths:
                            full_path = _combine_paths(cp, sp)
                            for m in http_methods:
                                dedup_k = (m, full_path)
                                if dedup_k not in file_seen:
                                    file_seen.add(dedup_k)
                                    endpoints.append({
                                        "id": f"{class_name}:{method_name}:{m}:{full_path}",
                                        "httpMethod": m,
                                        "method": m,
                                        "path": full_path,
                                        "urlPath": full_path,
                                        "endpoint": full_path,
                                        "controller": class_name,
                                        "className": class_name,
                                        "handlerMethod": method_name,
                                        "methodName": method_name,
                                        "sourceFile": formatted_file,
                                        "file": formatted_file,
                                        "module": "",
                                        "framework": "Spring Boot",
                                        "detectionStatus": "DETECTED",
                                        "lineNumber": line_number,
                                    })

                between = clean[cursor:scan_pos]
                has_another_mapping = any(re.search(rf'@{m}\b', between) for m in _ALL_MAPPINGS)

                if has_another_mapping:
                    i = cursor
                elif found_method:
                    body_brace = clean.find("{", scan_pos, limit)
                    body_semi = clean.find(";", scan_pos, limit)
                    if body_brace != -1 and (body_semi == -1 or body_brace < body_semi):
                        end_body = _find_matching_brace(clean, body_brace)
                        i = end_body + 1 if end_body != -1 else scan_pos
                    else:
                        i = body_semi + 1 if body_semi != -1 else scan_pos
                else:
                    i = at_idx + 1

        return endpoints
