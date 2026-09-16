import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from app.infrastructure.analyzers.api_endpoint_detector import ApiEndpointDetector

@pytest.fixture
def detector():
    return ApiEndpointDetector()

def test_detect_no_jar(detector):
    with patch.object(Path, "exists", return_value=False):
        with pytest.raises(RuntimeError, match="Migration engine JAR not found"):
            detector.detect(Path("/tmp/fake-repo"))

@patch("subprocess.run")
def test_detect_success(mock_run, detector):
    # Mock successful Java execution
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='{"status": "SUCCESS", "apiEndpoints": [{"id": "1", "httpMethod": "GET", "path": "/api/test", "controller": "TestController"}]}',
        stderr=""
    )
    
    with patch.object(Path, "exists", return_value=True):
        results = detector.detect(Path("/tmp/fake-repo"))
        assert len(results) == 1
        assert results[0]["path"] == "/api/test"
        assert results[0]["httpMethod"] == "GET"

@patch("subprocess.run")
def test_detect_failure(mock_run, detector):
    # Mock failed Java execution
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="Some Java Error"
    )
    
    with patch.object(Path, "exists", return_value=True):
        results = detector.detect(Path("/tmp/fake-repo"))
        assert results == []

@patch("subprocess.run")
def test_detect_malformed_json(mock_run, detector):
    # Mock success but invalid JSON
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="not a json",
        stderr=""
    )
    
    with patch.object(Path, "exists", return_value=True):
        results = detector.detect(Path("/tmp/fake-repo"))
        assert results == []
