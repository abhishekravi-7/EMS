import urllib.parse
from collections import deque
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.application.use_cases.existing_test_runner_service import existing_test_runner_service
from app.main import app


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = "test-user-123"
    user.email = "test@example.com"
    return user


def test_existing_test_runner_service_get_logs():
    job_id = "job_test_logs_001"
    with existing_test_runner_service._lock:
        existing_test_runner_service._state[job_id] = {
            "status": "COMPLETED",
            "executed": True,
            "logs": deque([
                {"ts": "12:00:00", "msg": "[1/4] Running com.javacodegeeks.examples.junitmavenexample.CalculatorTest#testSum", "level": "INFO"},
                {"ts": "12:00:01", "msg": "[2/4] com.javacodegeeks.examples.junitmavenexample.CalculatorTest#testSum: PASSED", "level": "INFO"},
                "Raw string log line"
            ]),
            "result": {
                "status": "COMPLETED",
                "test_results": [
                    {
                        "test_id": "com.javacodegeeks.examples.junitmavenexample.CalculatorTest#testSum",
                        "test_name": "testSum",
                        "suite": "CalculatorTest",
                        "framework": "JUnit",
                        "status": "PASSED",
                        "duration": "0.005s"
                    }
                ]
            }
        }

    logs = existing_test_runner_service.get_logs(job_id)
    assert len(logs) == 3
    assert "[12:00:00] [INFO] [1/4] Running com.javacodegeeks.examples.junitmavenexample.CalculatorTest#testSum" in logs[0]
    assert "[12:00:01] [INFO] [2/4] com.javacodegeeks.examples.junitmavenexample.CalculatorTest#testSum: PASSED" in logs[1]
    assert logs[2] == "Raw string log line"


def test_download_logs_endpoint_passed_test(mock_user):
    job_id = "job_7c797e7fcd39"
    test_id = "com.javacodegeeks.examples.junitmavenexample.CalculatorTest#testSum"
    
    with existing_test_runner_service._lock:
        existing_test_runner_service._state[job_id] = {
            "status": "COMPLETED",
            "executed": True,
            "logs": deque([
                {"ts": "12:00:00", "msg": "Starting existing test execution...", "level": "INFO"},
                {"ts": "12:00:01", "msg": "[1/4] Running com.javacodegeeks.examples.junitmavenexample.CalculatorTest#testSum", "level": "INFO"},
                {"ts": "12:00:02", "msg": "[2/4] com.javacodegeeks.examples.junitmavenexample.CalculatorTest#testSum: PASSED", "level": "INFO"},
            ]),
            "result": {
                "status": "COMPLETED",
                "test_results": [
                    {
                        "test_id": test_id,
                        "test_name": "testSum",
                        "suite": "CalculatorTest",
                        "framework": "JUnit",
                        "status": "PASSED",
                        "duration": "0.005s"
                    }
                ]
            }
        }

    with patch("app.api.v1.endpoints.existing_test_report_controller.verify_job_ownership"), \
         patch("app.api.deps.get_current_user", return_value=mock_user):
        
        client = TestClient(app)
        quoted_test_id = urllib.parse.quote(test_id, safe="")
        response = client.get(f"/api/v1/existing-tests/report/{job_id}/test/{quoted_test_id}/logs")
        
        assert response.status_code == 200
        content = response.text
        
        # Verify metadata header
        assert f"Execution ID: {job_id}" in content
        assert "Test Name: testSum" in content
        assert "Class: CalculatorTest" in content
        assert "Framework: JUnit" in content
        assert "Status: PASSED" in content
        assert "Duration: 0.005s" in content
        
        # Verify actual logs are present and not empty or "No execution logs recorded"
        assert "[1/4] Running com.javacodegeeks.examples.junitmavenexample.CalculatorTest#testSum" in content
        assert "No execution logs recorded." not in content


def test_download_logs_endpoint_failed_test(mock_user):
    job_id = "job_failed_test_002"
    test_id = "com.example.DemoTest#testFail"
    
    with existing_test_runner_service._lock:
        existing_test_runner_service._state[job_id] = {
            "status": "COMPLETED",
            "executed": True,
            "logs": deque([
                {"ts": "12:00:00", "msg": "Running com.example.DemoTest#testFail...", "level": "INFO"},
                {"ts": "12:00:01", "msg": "AssertionError: expected <1> but was <2>", "level": "ERROR"},
            ]),
            "result": {
                "status": "COMPLETED",
                "test_results": [
                    {
                        "test_id": test_id,
                        "test_name": "testFail",
                        "suite": "DemoTest",
                        "framework": "JUnit",
                        "status": "FAILED",
                        "duration": "0.010s",
                        "error": "AssertionError: expected <1> but was <2>",
                        "stack_trace": "java.lang.AssertionError: expected <1> but was <2>\n\tat DemoTest.testFail(DemoTest.java:15)"
                    }
                ]
            }
        }

    with patch("app.api.v1.endpoints.existing_test_report_controller.verify_job_ownership"), \
         patch("app.api.deps.get_current_user", return_value=mock_user):
        
        client = TestClient(app)
        quoted_test_id = urllib.parse.quote(test_id, safe="")
        response = client.get(f"/api/v1/existing-tests/report/{job_id}/test/{quoted_test_id}/logs")
        
        assert response.status_code == 200
        content = response.text
        
        assert f"Execution ID: {job_id}" in content
        assert "Status: FAILED" in content
        assert "[ERROR] AssertionError: expected <1> but was <2>" in content
        assert "java.lang.AssertionError" in content


def test_download_logs_endpoint_genuinely_empty_logs(mock_user):
    job_id = "job_empty_logs_003"
    test_id = "com.example.EmptyTest#testEmpty"
    
    with existing_test_runner_service._lock:
        existing_test_runner_service._state[job_id] = {
            "status": "COMPLETED",
            "executed": True,
            "logs": deque([]),
            "result": {
                "status": "COMPLETED",
                "test_results": [
                    {
                        "test_id": test_id,
                        "test_name": "testEmpty",
                        "suite": "EmptyTest",
                        "framework": "JUnit",
                        "status": "NOT_EXECUTED",
                    }
                ]
            }
        }

    with patch("app.api.v1.endpoints.existing_test_report_controller.verify_job_ownership"), \
         patch("app.api.deps.get_current_user", return_value=mock_user):
        
        client = TestClient(app)
        quoted_test_id = urllib.parse.quote(test_id, safe="")
        response = client.get(f"/api/v1/existing-tests/report/{job_id}/test/{quoted_test_id}/logs")
        
        assert response.status_code == 200
        content = response.text
        
        assert f"Execution ID: {job_id}" in content
        assert "Status: NOT_EXECUTED" in content
        assert "No execution logs recorded." in content
