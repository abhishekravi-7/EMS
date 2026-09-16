"""Unit tests for the pure-Python ApiEndpointDetector.

No subprocess mocking needed — the detector reads .java files directly.
"""
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.infrastructure.analyzers.api_endpoint_detector import (
    ApiEndpointDetector,
    _detect_in_file,
    _extract_class_base_path,
    _extract_class_name,
    _normalize_path,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_java(tmp_path: Path, filename: str, content: str) -> Path:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Unit tests for private helpers
# ---------------------------------------------------------------------------

def test_extract_class_name():
    src = "public class UserController extends BaseController {"
    assert _extract_class_name(src) == "UserController"


def test_extract_class_name_fallback():
    assert _extract_class_name("no class here") == "UnknownController"


def test_extract_class_base_path_value():
    src = '@RequestMapping(value = "/api/users")\npublic class UC {}'
    assert _extract_class_base_path(src) == "api/users"


def test_extract_class_base_path_bare():
    src = '@RequestMapping("/api/items")\npublic class IC {}'
    assert _extract_class_base_path(src) == "api/items"


def test_extract_class_base_path_none():
    src = "public class NoMapping {}"
    assert _extract_class_base_path(src) == ""


def test_normalize_path():
    assert _normalize_path("api/users", "me") == "/api/users/me"
    assert _normalize_path("", "/health") == "/health"
    assert _normalize_path("", "") == "/"


# ---------------------------------------------------------------------------
# _detect_in_file tests
# ---------------------------------------------------------------------------

SIMPLE_REST_CONTROLLER = """\
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users")
public class UserController {

    @GetMapping
    public List<User> getAll() { return null; }

    @PostMapping("/create")
    public User create(@RequestBody User u) { return null; }

    @DeleteMapping("/{id}")
    public void delete(@PathVariable Long id) {}
}
"""

def test_detect_in_file_rest_controller(tmp_path):
    jf = _write_java(tmp_path, "UserController.java", SIMPLE_REST_CONTROLLER)
    results = _detect_in_file(jf)
    assert len(results) == 3
    methods = {r["httpMethod"] for r in results}
    assert methods == {"GET", "POST", "DELETE"}
    controllers = {r["controller"] for r in results}
    assert controllers == {"UserController"}


def test_detect_in_file_no_controller(tmp_path):
    jf = _write_java(tmp_path, "Service.java", "public class MyService { void doStuff() {} }")
    results = _detect_in_file(jf)
    assert results == []


def test_detect_in_file_nonexistent():
    results = _detect_in_file(Path("/nonexistent/file.java"))
    assert results == []


def test_detect_in_file_fields_present(tmp_path):
    jf = _write_java(tmp_path, "UC.java", SIMPLE_REST_CONTROLLER)
    results = _detect_in_file(jf)
    for r in results:
        assert "id" in r
        assert "httpMethod" in r
        assert "path" in r
        assert "controller" in r
        assert "methodName" in r


# ---------------------------------------------------------------------------
# ApiEndpointDetector.detect() integration tests (with tmp filesystem)
# ---------------------------------------------------------------------------

def test_detector_no_java_files(tmp_path):
    detector = ApiEndpointDetector()
    results = detector.detect(tmp_path)
    assert results == []


def test_detector_finds_endpoints(tmp_path):
    _write_java(tmp_path, "UserController.java", SIMPLE_REST_CONTROLLER)
    detector = ApiEndpointDetector()
    results = detector.detect(tmp_path)
    assert len(results) == 3


def test_detector_skips_non_controllers(tmp_path):
    _write_java(tmp_path, "SomeService.java", "public class SomeService { void run(){} }")
    detector = ApiEndpointDetector()
    results = detector.detect(tmp_path)
    assert results == []


def test_detector_multiple_files(tmp_path):
    _write_java(tmp_path, "UserController.java", SIMPLE_REST_CONTROLLER)
    other = """\
@RestController
@RequestMapping("/api/products")
public class ProductController {
    @GetMapping("/{id}")
    public Product get() { return null; }
}
"""
    _write_java(tmp_path, "ProductController.java", other)
    detector = ApiEndpointDetector()
    results = detector.detect(tmp_path)
    assert len(results) == 4
    paths = {r["path"] for r in results}
    assert any("users" in p for p in paths)
    assert any("products" in p for p in paths)


def test_detector_works_without_jar(tmp_path):
    """Critical regression test: Discovery must NOT fail because the migration-engine JAR is absent."""
    _write_java(tmp_path, "HC.java", SIMPLE_REST_CONTROLLER)
    detector = ApiEndpointDetector()
    # No JAR, no env vars, nothing — this must not raise
    results = detector.detect(tmp_path)
    assert isinstance(results, list)
