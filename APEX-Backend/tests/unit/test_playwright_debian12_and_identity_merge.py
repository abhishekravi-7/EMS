"""Tests for Playwright Debian 12 browser compatibility, driver error classification, and test identity reconciliation."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from app.application.use_cases.existing_test_runner_service import ExistingTestRunnerService


def test_playwright_debian12_browser_adaptation(tmp_path, monkeypatch):
    """Verify that on Debian 12 / Linux, firefox is adapted to chromium with headless mode."""
    service = ExistingTestRunnerService()
    
    # Mock environment to be Linux Debian 12
    monkeypatch.setattr(
        service,
        "_detect_os_environment",
        lambda: {"os": "linux", "distro": "debian", "version": "12.5", "is_linux": True, "is_debian12": True},
    )

    test_file = tmp_path / "BaseTest.java"
    java_code = """package com.example;

import com.microsoft.playwright.*;
import org.junit.jupiter.api.BeforeAll;

public class BaseTest {
    static Playwright playwright;
    static Browser browser;

    @BeforeAll
    static void doInitialSetup() {
        playwright = Playwright.create();
        browser = playwright.firefox().launch();
    }
}
"""
    test_file.write_text(java_code, encoding="utf-8")

    service._instrument_playwright_tests(tmp_path, "job_test_pw_deb12")

    instrumented_code = test_file.read_text(encoding="utf-8")
    assert "playwright.chromium(" in instrumented_code
    assert "playwright.firefox(" not in instrumented_code
    assert "setHeadless(true)" in instrumented_code


def test_playwright_windows_local_preservation(tmp_path, monkeypatch):
    """Verify that on Windows, local test browser configuration is preserved."""
    service = ExistingTestRunnerService()

    # Mock environment to be Windows
    monkeypatch.setattr(
        service,
        "_detect_os_environment",
        lambda: {"os": "windows", "distro": "", "version": "11", "is_linux": False, "is_debian12": False},
    )

    test_file = tmp_path / "BaseTest.java"
    java_code = """package com.example;

import com.microsoft.playwright.*;

public class BaseTest {
    void setup() {
        Playwright playwright = Playwright.create();
        Browser browser = playwright.firefox().launch();
    }
}
"""
    test_file.write_text(java_code, encoding="utf-8")

    service._instrument_playwright_tests(tmp_path, "job_test_pw_win")

    instrumented_code = test_file.read_text(encoding="utf-8")
    assert "playwright.firefox(" in instrumented_code


def test_error_classifier_driver_reason_extraction():
    """Verify that _classify_error_and_root_cause extracts detailed Playwright root causes."""
    service = ExistingTestRunnerService()
    
    raw_status = "ERROR"
    failure_text = "Failed to create driver"
    stack_trace = """java.lang.RuntimeException: Failed to create driver
\tat com.example.BaseTest.doInitialSetup(BaseTest.java:24)
Caused by: com.microsoft.playwright.PlaywrightException: Playwright does not support firefox on debian12
\tat com.microsoft.playwright.impl.Driver.initialize(Driver.java:80)
\t... 30 more"""
    
    status, cat, code, root_cause, clean_msg = service._classify_error_and_root_cause(
        raw_status, failure_text, stack_trace, None, None
    )

    assert status == "ERROR"
    assert "Playwright" in root_cause
    assert "Playwright does not support firefox on debian12" in clean_msg


def test_class_level_setup_failure_reconciliation():
    """Verify that when Surefire reports generic class-level failure (RawTest.unknown), all discovered tests inherit the failure without duplicate unknown entries."""
    service = ExistingTestRunnerService()

    # 4 Discovered tests across 2 classes
    discovered_tests = [
        {"name": "test01", "suite": "RawTest", "classname": "com.example.RawTest", "file": "src/test/java/com/example/RawTest.java", "framework": "JUnit", "type": "Playwright UI"},
        {"name": "test02", "suite": "RawTest", "classname": "com.example.RawTest", "file": "src/test/java/com/example/RawTest.java", "framework": "JUnit", "type": "Playwright UI"},
        {"name": "test01", "suite": "PomTest", "classname": "com.example.PomTest", "file": "src/test/java/com/example/PomTest.java", "framework": "JUnit", "type": "Playwright UI"},
        {"name": "test02", "suite": "PomTest", "classname": "com.example.PomTest", "file": "src/test/java/com/example/PomTest.java", "framework": "JUnit", "type": "Playwright UI"},
    ]

    # Surefire XML emitted class-level failures with test_name as unknown
    parsed_results = [
        {
            "test_name": "unknown",
            "name": "unknown",
            "suite": "com.example.RawTest",
            "status": "FAILED",
            "duration": "0.150s",
            "failure_message": "Failed to create driver: Playwright does not support firefox on debian12",
            "root_cause": "Playwright Driver Error: Playwright does not support firefox on debian12",
            "file": "com/example/RawTest.java",
            "framework": "JUnit",
            "type": "Playwright UI",
            "category": "UI",
        },
        {
            "test_name": "unknown",
            "name": "unknown",
            "suite": "com.example.PomTest",
            "status": "FAILED",
            "duration": "0.120s",
            "failure_message": "Failed to create driver: Playwright does not support firefox on debian12",
            "root_cause": "Playwright Driver Error: Playwright does not support firefox on debian12",
            "file": "com/example/PomTest.java",
            "framework": "JUnit",
            "type": "Playwright UI",
            "category": "UI",
        },
    ]

    # Reconcile using the updated logic
    results_by_key = {}
    for r in parsed_results:
        r_name = service._normalize_test_name(r.get("test_name") or r.get("name", ""))
        r_suite = r.get("suite") or r.get("classname", "")
        r_file = r.get("file", "")
        key = service._canonical_test_identifier(r_name, r_suite, r_file)
        results_by_key[key] = r

    class_level_errors = {}
    for r in parsed_results:
        r_name = service._normalize_test_name(r.get("test_name") or r.get("name", ""))
        r_suite = r.get("suite") or r.get("classname", "")
        r_file = r.get("file", "")
        key = service._canonical_test_identifier(r_name, r_suite, r_file)
        if key[1] in ("unknown", "", "initializationerror", "classmethod", "beforeall", "setup") and r.get("status") in ("FAILED", "ERROR"):
            class_level_errors[key[0]] = r

    for tc in discovered_tests:
        tc_name = service._normalize_test_name(tc.get("name", "test"))
        tc_suite = tc.get("classname") or tc.get("suite") or tc.get("module", "")
        tc_file = tc.get("file", "")
        key = service._canonical_test_identifier(tc_name, tc_suite, tc_file)
        if key[0] in class_level_errors:
            err_template = class_level_errors[key[0]]
            r_inherited = dict(err_template)
            r_inherited["test_name"] = tc_name
            r_inherited["name"] = tc_name
            r_inherited["suite"] = tc_suite
            if tc_file:
                r_inherited["file"] = tc_file
            results_by_key[key] = r_inherited

    # Remove generic class-level failure entries
    keys_to_remove = [
        k for k in list(results_by_key.keys())
        if k[1] in ("unknown", "", "initializationerror", "classmethod", "beforeall", "setup")
        and any(other_k[0] == k[0] and other_k[1] not in ("unknown", "", "initializationerror", "classmethod", "beforeall", "setup") for other_k in results_by_key.keys())
    ]
    for k in keys_to_remove:
        del results_by_key[k]

    final_results = list(results_by_key.values())

    # Assertions
    assert len(final_results) == 4, f"Expected exactly 4 tests, got {len(final_results)}"
    
    test_names = {f"{r['suite']}.{r['test_name']}" for r in final_results}
    assert "com.example.RawTest.test01" in test_names
    assert "com.example.RawTest.test02" in test_names
    assert "com.example.PomTest.test01" in test_names
    assert "com.example.PomTest.test02" in test_names

    # Ensure no *.unknown test is present
    for r in final_results:
        assert r["test_name"] != "unknown"
        assert r["status"] == "FAILED"
        assert "Playwright does not support firefox on debian12" in r["failure_message"]
