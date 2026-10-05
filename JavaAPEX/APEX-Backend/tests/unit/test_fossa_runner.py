"""Unit tests for FOSSA DependencyCheckRunner."""

from __future__ import annotations

import json
import os
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.infrastructure.quality_gates.dependency_check_runner import (
    DependencyCheckRunner,
    FossaScanResult,
)


def test_fossa_missing_token(tmp_path: Path):
    """When FOSSA_API_KEY is empty, DependencyCheckRunner returns missing_token result."""
    runner = DependencyCheckRunner()
    with patch.object(settings, "fossa_api_key", ""):
        result = runner.run(tmp_path, job_id="job_test_123")
        assert result.scan_mode == "missing_token"
        assert result.policy_status == "UNAVAILABLE"
        assert result.real_scan is False
        assert "Set FOSSA_API_KEY in .env" in (result.error_message or "")


def test_fossa_missing_cli(tmp_path: Path):
    """When FOSSA CLI cannot be resolved, runner falls back to built-in dependency scanner."""
    runner = DependencyCheckRunner()
    with patch.object(settings, "fossa_api_key", "test-api-key"), \
         patch.object(DependencyCheckRunner, "_resolve_command", return_value=None):
        result = runner.run(tmp_path, job_id="job_test_123")
        assert result.scan_mode == "built_in_scanner"
        assert result.policy_status == "PASSED"
        assert result.real_scan is True


def test_fossa_missing_maven_for_maven_project(tmp_path: Path):
    """When a Maven project has no working Maven executable, returns missing_maven."""
    (tmp_path / "pom.xml").write_text("<project></project>", encoding="utf-8")
    runner = DependencyCheckRunner()
    with patch.object(settings, "fossa_api_key", "test-api-key"), \
         patch.object(DependencyCheckRunner, "_resolve_command", return_value="C:\\fossa\\fossa.exe"), \
         patch.object(DependencyCheckRunner, "_resolve_maven", return_value=None):
        result = runner.run(tmp_path, job_id="job_test_123")
        assert result.scan_mode == "missing_maven"
        assert result.policy_status == "UNAVAILABLE"
        assert "Maven executable was not found" in (result.error_message or "")


def test_fossa_cli_resolution_priority(tmp_path: Path):
    """Tests resolution order: explicit FOSSA_CLI_PATH -> which -> fallbacks."""
    fake_cli = tmp_path / "fossa.exe"
    fake_cli.write_text("binary", encoding="utf-8")

    with patch.dict(os.environ, {"FOSSA_CLI_PATH": str(fake_cli)}):
        resolved = DependencyCheckRunner._resolve_command()
        assert resolved == str(fake_cli)


# ==============================================================================
# TEST 1: FOSSA exit code 0 + valid JSON -> PASSED, issue counts = 0
# ==============================================================================
def test_fossa_exit_0_valid_json(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project></project>", encoding="utf-8")
    runner = DependencyCheckRunner()

    mock_analyze = MagicMock(returncode=0, stdout='{"locator": "custom+12345/test-project$123"}', stderr="")
    mock_test = MagicMock(returncode=0, stdout=json.dumps({"issues": [], "dependencies": [{"name": "pkg-1", "version": "1.0"}]}), stderr="")

    with patch.object(settings, "fossa_api_key", "valid-key"), \
         patch("app.infrastructure.quality_gates.dependency_check_runner.build_tool_env", return_value={"PATH": "C:\\fake"}), \
         patch.object(DependencyCheckRunner, "_resolve_command", return_value="fossa.exe"), \
         patch.object(DependencyCheckRunner, "_get_fossa_version", return_value="v3.8.3"), \
         patch.object(DependencyCheckRunner, "_resolve_maven", return_value="mvn.cmd"), \
         patch.object(DependencyCheckRunner, "_test_maven_executable", return_value=True), \
         patch("subprocess.run", side_effect=[mock_analyze, mock_test]), \
         patch.object(DependencyCheckRunner, "_fetch_dependency_count", return_value=1):

        result = runner.run(tmp_path, job_id="job_test_1")
        assert result.scan_mode == "real"
        assert result.policy_status == "PASSED"
        assert result.real_scan is True
        assert result.license_issues == 0
        assert result.vulnerabilities == 0
        assert result.outdated_dependencies == 0
        assert result.total_dependencies == 1


# ==============================================================================
# TEST 2: FOSSA exit code 1 + valid JSON -> FAILED, actual counts preserved
# ==============================================================================
def test_fossa_exit_1_valid_json(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project></project>", encoding="utf-8")
    runner = DependencyCheckRunner()

    issues_payload = {
        "issues": [
            {"issue_type": "policy_conflict", "revisionId": "custom+mvn+com.example:lib$1.0", "title": "GPL License Denied"},
            {"issue_type": "denied_license", "revisionId": "custom+mvn+com.example:lib2$2.0", "title": "AGPL Denied"},
            {"issue_type": "vulnerability", "revisionId": "custom+mvn+com.example:vuln$1.0", "cve": "CVE-2023-9999", "severity": "HIGH"},
            {"issue_type": "outdated_dependency", "revisionId": "custom+mvn+com.example:out$1.0", "version": "1.0", "latest_version": "2.0"},
        ]
    }
    mock_analyze = MagicMock(returncode=0, stdout='{"locator": "custom+12345/test-project$123"}', stderr="")
    mock_test = MagicMock(returncode=1, stdout=json.dumps(issues_payload), stderr="")

    with patch.object(settings, "fossa_api_key", "valid-key"), \
         patch("app.infrastructure.quality_gates.dependency_check_runner.build_tool_env", return_value={"PATH": "C:\\fake"}), \
         patch.object(DependencyCheckRunner, "_resolve_command", return_value="fossa.exe"), \
         patch.object(DependencyCheckRunner, "_get_fossa_version", return_value="v3.8.3"), \
         patch.object(DependencyCheckRunner, "_resolve_maven", return_value="mvn.cmd"), \
         patch.object(DependencyCheckRunner, "_test_maven_executable", return_value=True), \
         patch("subprocess.run", side_effect=[mock_analyze, mock_test]), \
         patch.object(DependencyCheckRunner, "_fetch_dependency_count", return_value=25):

        result = runner.run(tmp_path, job_id="job_test_2")
        assert result.scan_mode == "real"
        assert result.policy_status == "FAILED"
        assert result.real_scan is True
        assert result.license_issues == 2
        assert result.denied_license_issues == 1
        assert result.vulnerabilities == 1
        assert result.outdated_dependencies == 1
        assert result.total_dependencies == 25


# ==============================================================================
# TEST 3: FOSSA exit code 1 + JSON surrounded by CLI banners and ANSI escape codes
# ==============================================================================
def test_fossa_exit_1_json_surrounded_by_cli_text_and_ansi(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project></project>", encoding="utf-8")
    runner = DependencyCheckRunner()

    raw_cli_stdout = (
        "\x1b[1m\x1b[34m========================================\x1b[0m\n"
        "\x1b[32m[FOSSA CLI v3.8.3]\x1b[0m Checking policy rules...\n"
        '{\n  "issues": [\n    {"issue_type": "policy_conflict", "package": "lib-a"},\n    {"issue_type": "vulnerability", "severity": "CRITICAL"}\n  ]\n}\n'
        "\x1b[31mPolicy check completed: 2 issues found.\x1b[0m\n"
    )
    mock_analyze = MagicMock(returncode=0, stdout='{"locator": "custom+12345/test-project$123"}', stderr="")
    mock_test = MagicMock(returncode=1, stdout=raw_cli_stdout, stderr="")

    with patch.object(settings, "fossa_api_key", "valid-key"), \
         patch("app.infrastructure.quality_gates.dependency_check_runner.build_tool_env", return_value={"PATH": "C:\\fake"}), \
         patch.object(DependencyCheckRunner, "_resolve_command", return_value="fossa.exe"), \
         patch.object(DependencyCheckRunner, "_get_fossa_version", return_value="v3.8.3"), \
         patch.object(DependencyCheckRunner, "_resolve_maven", return_value="mvn.cmd"), \
         patch.object(DependencyCheckRunner, "_test_maven_executable", return_value=True), \
         patch("subprocess.run", side_effect=[mock_analyze, mock_test]), \
         patch.object(DependencyCheckRunner, "_fetch_dependency_count", return_value=10):

        result = runner.run(tmp_path, job_id="job_test_3")
        assert result.policy_status == "FAILED"
        assert result.license_issues == 1
        assert result.vulnerabilities == 1
        assert result.total_dependencies == 10


# ==============================================================================
# TEST 4: FOSSA exit code 1 + unparseable output -> policy FAILED, counts = None (not 0)
# ==============================================================================
def test_fossa_exit_1_unparseable_output(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project></project>", encoding="utf-8")
    runner = DependencyCheckRunner()

    unparseable_stdout = "Error: evaluation completed with violations but output was not structured.\nViolations exist in target project."
    mock_analyze = MagicMock(returncode=0, stdout="", stderr="")
    mock_test = MagicMock(returncode=1, stdout=unparseable_stdout, stderr="")

    with patch.object(settings, "fossa_api_key", "valid-key"), \
         patch("app.infrastructure.quality_gates.dependency_check_runner.build_tool_env", return_value={"PATH": "C:\\fake"}), \
         patch.object(DependencyCheckRunner, "_resolve_command", return_value="fossa.exe"), \
         patch.object(DependencyCheckRunner, "_get_fossa_version", return_value="v3.8.3"), \
         patch.object(DependencyCheckRunner, "_resolve_maven", return_value="mvn.cmd"), \
         patch.object(DependencyCheckRunner, "_test_maven_executable", return_value=True), \
         patch("subprocess.run", side_effect=[mock_analyze, mock_test]), \
         patch.object(DependencyCheckRunner, "_fetch_dependency_count", return_value=None):

        result = runner.run(tmp_path, job_id="job_test_4")
        assert result.policy_status == "FAILED"
        assert result.license_issues is None
        assert result.vulnerabilities is None
        assert result.outdated_dependencies is None


# ==============================================================================
# TEST 5: FOSSA exit code >1 -> execution failure reported correctly
# ==============================================================================
def test_fossa_exit_greater_than_1(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project></project>", encoding="utf-8")
    runner = DependencyCheckRunner()

    mock_analyze = MagicMock(returncode=0, stdout='{"locator": "custom+12345/test-project$123"}', stderr="")
    mock_test = MagicMock(returncode=2, stdout="Fatal CLI error: connection refused", stderr="Error: connection refused")

    with patch.object(settings, "fossa_api_key", "valid-key"), \
         patch("app.infrastructure.quality_gates.dependency_check_runner.build_tool_env", return_value={"PATH": "C:\\fake"}), \
         patch.object(DependencyCheckRunner, "_resolve_command", return_value="fossa.exe"), \
         patch.object(DependencyCheckRunner, "_get_fossa_version", return_value="v3.8.3"), \
         patch.object(DependencyCheckRunner, "_resolve_maven", return_value="mvn.cmd"), \
         patch.object(DependencyCheckRunner, "_test_maven_executable", return_value=True), \
         patch("subprocess.run", side_effect=[mock_analyze, mock_test]):

        result = runner.run(tmp_path, job_id="job_test_5")
        assert result.policy_status == "UNAVAILABLE"
        assert result.scan_mode == "test_failed"
        assert result.real_scan is False
        assert "CLI execution error" in (result.error_message or "")


# ==============================================================================
# TEST 6: Valid FOSSA locator -> dependency API is called with real locator
# ==============================================================================
def test_fossa_valid_locator_api_called():
    runner = DependencyCheckRunner()

    mock_response = MagicMock()
    mock_response.read.return_value = b'[{"name": "lib-1"}, {"name": "lib-2"}, {"name": "lib-3"}]'
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        count = runner._fetch_dependency_count(
            host_url="https://app.fossa.com",
            api_key="test-key",
            locator="custom+98765/my-service$abc123",
            project="test-project",
        )
        assert count == 3
        # Verify request URL used the encoded real locator
        req_arg = mock_urlopen.call_args[0][0]
        assert "custom%2B98765%2Fmy-service%24abc123" in req_arg.full_url
        assert "custom+1/" not in req_arg.full_url


# ==============================================================================
# TEST 7: No FOSSA locator -> no fake "custom+1/<project>" locator, count = None
# ==============================================================================
def test_fossa_no_locator_no_api_call():
    runner = DependencyCheckRunner()

    with patch("urllib.request.urlopen") as mock_urlopen:
        count = runner._fetch_dependency_count(
            host_url="https://app.fossa.com",
            api_key="test-key",
            locator=None,
            project="test-project",
            analysis_url=None,
        )
        assert count is None
        mock_urlopen.assert_not_called()


# ==============================================================================
# TEST 8: Dependency API returns 404 initially -> limited retry then None
# ==============================================================================
def test_fossa_dependency_api_404_retry_and_fallback():
    runner = DependencyCheckRunner()

    http_404_err = urllib.error.HTTPError(
        url="https://app.fossa.com/api/revisions/foo/dependencies",
        code=404,
        msg="Not Found",
        hdrs={},
        fp=None,
    )

    with patch("urllib.request.urlopen", side_effect=http_404_err) as mock_urlopen, \
         patch("time.sleep") as mock_sleep:
        count = runner._fetch_dependency_count(
            host_url="https://app.fossa.com",
            api_key="test-key",
            locator="custom+12345/proj$rev",
            project="proj",
            max_retries=3,
            retry_delay_seconds=0.1,
        )
        assert count is None
        assert mock_urlopen.call_count == 3
        assert mock_sleep.call_count == 2


# ==============================================================================
# TEST 9: FOSSA API key configured -> passed in env and NEVER logged
# ==============================================================================
def test_fossa_api_key_in_env_and_never_logged(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project></project>", encoding="utf-8")
    runner = DependencyCheckRunner()

    secret_key = "FOSSA_SECRET_TOKEN_999888777"
    mock_analyze = MagicMock(returncode=0, stdout='{"locator": "custom+12345/test$1"}', stderr="")
    mock_test = MagicMock(returncode=0, stdout='{"issues": []}', stderr="")

    captured_envs: list[dict] = []

    def mock_subprocess_run(cmd, *args, **kwargs):
        if "env" in kwargs:
            captured_envs.append(kwargs["env"])
        if "analyze" in cmd:
            return mock_analyze
        return mock_test

    with patch.object(settings, "fossa_api_key", ""), \
         patch("app.infrastructure.quality_gates.dependency_check_runner.build_tool_env", return_value={"PATH": "C:\\fake"}), \
         patch.object(DependencyCheckRunner, "_resolve_command", return_value="fossa.exe"), \
         patch.object(DependencyCheckRunner, "_resolve_maven", return_value="mvn.cmd"), \
         patch.object(DependencyCheckRunner, "_test_maven_executable", return_value=True), \
         patch("subprocess.run", side_effect=mock_subprocess_run), \
         patch.object(DependencyCheckRunner, "_fetch_dependency_count", return_value=5):

        result = runner.run(
            tmp_path,
            job_id="job_sec_test",
            quality_checks_values={"fossa_api_key": secret_key},
        )

        assert result.scan_mode == "real"
        assert len(captured_envs) >= 2
        # Check that subprocess env had the real API key
        for env in captured_envs:
            assert env.get("FOSSA_API_KEY") == secret_key

        # Check that logs NEVER leak the secret key
        for line in result.log_lines:
            assert secret_key not in line

