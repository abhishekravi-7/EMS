import tempfile
import pytest
from pathlib import Path

from app.infrastructure.analyzers.api_endpoint_detector import ApiEndpointDetector

@pytest.fixture
def detector():
    return ApiEndpointDetector()

def test_detect_no_jar(detector):
    # This just ensures we can init without exception
    assert detector is not None

def test_detect_success(detector):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        java_file = root / "TestController.java"
        java_file.write_text(
            'import org.springframework.web.bind.annotation.*;\n'
            '@RestController\n'
            '@RequestMapping("/api")\n'
            'public class TestController {\n'
            '    @GetMapping("/test")\n'
            '    public String test() { return "ok"; }\n'
            '}'
        )
        results = detector.detect(root)
        paths = [r["urlPath"] for r in results]
        assert "/api/test" in paths
        
        # Verify the attributes of the correct endpoint
        endpoint = next(r for r in results if r["urlPath"] == "/api/test")
        assert endpoint["httpMethod"] == "GET"
        assert endpoint["className"] == "TestController"

def test_detect_no_endpoints(detector):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        java_file = root / "NoEndpoint.java"
        java_file.write_text(
            'public class NoEndpoint {\n'
            '    public String test() { return "ok"; }\n'
            '}'
        )
        results = detector.detect(root)
        assert len(results) == 0

