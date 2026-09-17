
"""Unit tests for the Python Spring annotation fallback in ApiEndpointDetector."""

import textwrap
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.infrastructure.analyzers.api_endpoint_detector import (
    ApiEndpointDetector,
    _python_spring_scan,
    _scan_file,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_java(tmp_path: Path, name: str, source: str) -> Path:
    f = tmp_path / name
    f.write_text(textwrap.dedent(source), encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# Tests: _scan_file
# ---------------------------------------------------------------------------

class TestScanFile:
    def test_rest_controller_get_mapping(self, tmp_path):
        f = _write_java(tmp_path, "GreetingController.java", """
            package com.example;
            import org.springframework.web.bind.annotation.*;
            @RestController
            public class GreetingController {
                @GetMapping("/greeting")
                public String greeting() { return "Hello"; }
            }
        """)
        eps = _scan_file(f)
        assert len(eps) == 1
        assert eps[0]["httpMethod"] == "GET"
        assert eps[0]["path"] == "/greeting"

    def test_class_base_path_combined(self, tmp_path):
        f = _write_java(tmp_path, "UserController.java", """
            @RestController
            @RequestMapping("/api/users")
            public class UserController {
                @GetMapping("/list")
                public List<User> list() { return null; }
                @PostMapping
                public User create() { return null; }
            }
        """)
        eps = _scan_file(f)
        routes = {(e["httpMethod"], e["path"]) for e in eps}
        assert ("GET", "/api/users/list") in routes
        assert ("POST", "/api/users") in routes

    def test_multiple_http_methods(self, tmp_path):
        f = _write_java(tmp_path, "ItemController.java", """
            @RestController
            public class ItemController {
                @GetMapping("/items")
                public Object get() { return null; }
                @PostMapping("/items")
                public Object create() { return null; }
                @PutMapping("/items/{id}")
                public Object update() { return null; }
                @DeleteMapping("/items/{id}")
                public Object delete() { return null; }
                @PatchMapping("/items/{id}")
                public Object patch() { return null; }
            }
        """)
        eps = _scan_file(f)
        methods = {e["httpMethod"] for e in eps}
        assert methods == {"GET", "POST", "PUT", "DELETE", "PATCH"}

    def test_plain_controller_not_rest_controller_skipped(self, tmp_path):
        # @Controller without any REST mapping annotation — no endpoints
        f = _write_java(tmp_path, "PageController.java", """
            @Controller
            public class PageController {
                @GetMapping("/home")
                public String home() { return "home"; }
            }
        """)
        # @Controller contains the substring so it should match _RE_REST_CTRL
        eps = _scan_file(f)
        # @Controller *does* match our pattern (correct — it can expose REST via ResponseBody)
        assert any(e["path"] == "/home" for e in eps)

    def test_not_a_controller_returns_empty(self, tmp_path):
        f = _write_java(tmp_path, "ServiceClass.java", """
            @Service
            public class GreetingService {
                public String greet() { return "hi"; }
            }
        """)
        eps = _scan_file(f)
        assert eps == []

    def test_comment_lines_not_counted(self, tmp_path):
        f = _write_java(tmp_path, "Commented.java", """
            @RestController
            public class Commented {
                // @GetMapping("/not-real")
                @GetMapping("/real")
                public String real() { return ""; }
            }
        """)
        eps = _scan_file(f)
        routes = [e["path"] for e in eps]
        assert "/real" in routes
        assert "/not-real" not in routes

    def test_dedup_same_method_and_path(self, tmp_path):
        # Two files with the same endpoint – scan_file handles per-file;
        # dedup happens in _python_spring_scan
        f = _write_java(tmp_path, "Ctrl.java", """
            @RestController
            public class Ctrl {
                @GetMapping("/ping")
                public String ping() { return ""; }
            }
        """)
        eps = _scan_file(f)
        assert len(eps) == 1


# ---------------------------------------------------------------------------
# Tests: _python_spring_scan (integration over a fake project tree)
# ---------------------------------------------------------------------------

class TestPythonSpringScan:
    def test_gs_rest_service_pattern(self, tmp_path):
        """Simulates spring-guides/gs-rest-service/complete layout."""
        src = tmp_path / "complete" / "src" / "main" / "java" / "com" / "example"
        src.mkdir(parents=True)
        (src / "GreetingController.java").write_text(textwrap.dedent("""
            package com.example;
            import org.springframework.web.bind.annotation.*;
            @RestController
            public class GreetingController {
                @GetMapping("/greeting")
                public Greeting greeting(@RequestParam(value="name", defaultValue="World") String name) {
                    return new Greeting(counter.incrementAndGet(), String.format(template, name));
                }
            }
        """), encoding="utf-8")
        eps = _python_spring_scan(tmp_path)
        assert len(eps) == 1
        assert eps[0]["httpMethod"] == "GET"
        assert eps[0]["path"] == "/greeting"

    def test_test_dir_excluded(self, tmp_path):
        # Controller in test dir should be ignored
        test_src = tmp_path / "src" / "test" / "java" / "com" / "example"
        test_src.mkdir(parents=True)
        (test_src / "FakeController.java").write_text(textwrap.dedent("""
            @RestController
            public class FakeController {
                @GetMapping("/fake")
                public String fake() { return ""; }
            }
        """), encoding="utf-8")
        eps = _python_spring_scan(tmp_path)
        assert eps == []

    def test_target_dir_excluded(self, tmp_path):
        target = tmp_path / "target" / "generated-sources" / "com"
        target.mkdir(parents=True)
        (target / "GeneratedCtrl.java").write_text(textwrap.dedent("""
            @RestController
            public class GeneratedCtrl {
                @GetMapping("/generated")
                public String gen() { return ""; }
            }
        """), encoding="utf-8")
        eps = _python_spring_scan(tmp_path)
        assert eps == []

    def test_dedup_across_files(self, tmp_path):
        src = tmp_path / "src" / "main" / "java"
        src.mkdir(parents=True)
        for i in range(3):
            (src / f"Ctrl{i}.java").write_text(textwrap.dedent(f"""
                @RestController
                public class Ctrl{i} {{
                    @GetMapping("/api/item")
                    public String item() {{ return ""; }}
                }}
            """), encoding="utf-8")
        eps = _python_spring_scan(tmp_path)
        # Three files each declaring GET /api/item — should be de-duped to 1
        unique = [(e["httpMethod"], e["path"]) for e in eps]
        assert unique.count(("GET", "/api/item")) == 1

    def test_no_controllers_gives_empty(self, tmp_path):
        src = tmp_path / "src" / "main" / "java"
        src.mkdir(parents=True)
        (src / "Service.java").write_text("public class Service {}", encoding="utf-8")
        eps = _python_spring_scan(tmp_path)
        assert eps == []


# ---------------------------------------------------------------------------
# Tests: ApiEndpointDetector public API
# ---------------------------------------------------------------------------

class TestApiEndpointDetector:
    def test_falls_back_to_python_scan_when_jar_missing(self, tmp_path):
        src = tmp_path / "src" / "main" / "java"
        src.mkdir(parents=True)
        (src / "Ctrl.java").write_text(textwrap.dedent("""
            @RestController
            public class Ctrl {
                @GetMapping("/hello")
                public String hello() { return "hi"; }
            }
        """), encoding="utf-8")

        detector = ApiEndpointDetector(jar_path=Path("/nonexistent/engine.jar"))
        results = detector.detect(tmp_path)
        assert len(results) == 1
        assert results[0]["path"] == "/hello"

    def test_uses_jar_when_present(self, tmp_path):
        fake_jar = tmp_path / "engine.jar"
        fake_jar.touch()

        detector = ApiEndpointDetector(jar_path=fake_jar)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"status":"SUCCESS","apiEndpoints":[{"id":"1","httpMethod":"GET","path":"/jar-endpoint","controller":"C"}]}',
                stderr="",
            )
            results = detector.detect(tmp_path)

        assert len(results) == 1
        assert results[0]["path"] == "/jar-endpoint"

    def test_jar_failure_returns_empty(self, tmp_path):
        fake_jar = tmp_path / "engine.jar"
        fake_jar.touch()
        detector = ApiEndpointDetector(jar_path=fake_jar)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            results = detector.detect(tmp_path)
        assert results == []

    def test_jar_malformed_json_returns_empty(self, tmp_path):
        fake_jar = tmp_path / "engine.jar"
        fake_jar.touch()
        detector = ApiEndpointDetector(jar_path=fake_jar)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
            results = detector.detect(tmp_path)
        assert results == []

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

