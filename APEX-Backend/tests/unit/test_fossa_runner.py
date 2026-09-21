"""Unit tests for FOSSA DependencyCheckRunner."""

from __future__ import annotations

import os
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
    """When FOSSA CLI cannot be resolved, runner returns missing_cli result."""
    runner = DependencyCheckRunner()
    with patch.object(settings, "fossa_api_key", "test-api-key"), \
         patch.object(DependencyCheckRunner, "_resolve_command", return_value=None):
        result = runner.run(tmp_path, job_id="job_test_123")
        assert result.scan_mode == "missing_cli"
        assert result.policy_status == "UNAVAILABLE"
        assert result.real_scan is False
        assert "FOSSA CLI (fossa) was not found" in (result.error_message or "")


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


def test_fossa_successful_scan_parsing(tmp_path: Path):
    """Tests parsing of successful FOSSA test output."""
    (tmp_path / "pom.xml").write_text("<project></project>", encoding="utf-8")
    runner = DependencyCheckRunner()

    mock_mvn_v = MagicMock()
    mock_mvn_v.returncode = 0

    mock_analyze = MagicMock()
    mock_analyze.returncode = 0
    mock_analyze.stdout = '{"locator": "custom+12345/test-project$123"}'
    mock_analyze.stderr = "View it in FOSSA at: https://app.fossa.com/projects/custom%2B12345%2Ftest-project"

    mock_test = MagicMock()
    mock_test.returncode = 0
    mock_test.stdout = '{"issues": []}'
    mock_test.stderr = ""

    with patch.object(settings, "fossa_api_key", "valid-key"), \
         patch("app.infrastructure.quality_gates.dependency_check_runner.build_tool_env", return_value={"PATH": "C:\\fake"}), \
         patch.object(DependencyCheckRunner, "_resolve_command", return_value="fossa.exe"), \
         patch.object(DependencyCheckRunner, "_resolve_maven", return_value="mvn.cmd"), \
         patch.object(DependencyCheckRunner, "_test_maven_executable", return_value=True), \
         patch("subprocess.run", side_effect=[mock_analyze, mock_test]), \
         patch.object(DependencyCheckRunner, "_fetch_dependency_count", return_value=12):

        result = runner.run(tmp_path, job_id="job_test_success")
        assert result.scan_mode == "real"
        assert result.policy_status == "PASSED"
        assert result.real_scan is True
        assert result.total_dependencies == 12
        assert result.license_issues == 0
        assert result.vulnerabilities == 0
