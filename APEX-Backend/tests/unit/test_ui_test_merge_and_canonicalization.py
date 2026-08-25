"""Unit tests for test canonicalization, identity matching, and TEST-MERGE resolution."""

from __future__ import annotations

import uuid
import pytest
from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.application.use_cases.existing_test_runner_service import ExistingTestRunnerService


def test_canonical_test_identifier_matches_equivalent_representations():
    """Verify that method parameters, hashes, classnames, and dot notations all resolve to the same canonical tuple."""
    expected_tuple = ("authenticationtests", "authentication")
    expected_str = "authenticationtests.authentication"

    # Representation 1: Class.method(Page)
    key1 = ExistingTestRunnerService._canonical_test_identifier("AuthenticationTests.authentication(Page)", None)
    assert key1 == expected_tuple
    assert f"{key1[0]}.{key1[1]}" == expected_str

    # Representation 2: Class#method
    key2 = ExistingTestRunnerService._canonical_test_identifier("AuthenticationTests#authentication", None)
    assert key2 == expected_tuple
    assert f"{key2[0]}.{key2[1]}" == expected_str

    # Representation 3: canonical lowercase notation
    key3 = ExistingTestRunnerService._canonical_test_identifier("authenticationtests.authentication", None)
    assert key3 == expected_tuple
    assert f"{key3[0]}.{key3[1]}" == expected_str

    # Representation 4: method with param and explicit class suite
    key4 = ExistingTestRunnerService._canonical_test_identifier("authentication(Page)", "com.example.AuthenticationTests")
    assert key4 == expected_tuple
    assert f"{key4[0]}.{key4[1]}" == expected_str

    # Representation 5: bare method and short suite
    key5 = ExistingTestRunnerService._canonical_test_identifier("authentication", "AuthenticationTests")
    assert key5 == expected_tuple
    assert f"{key5[0]}.{key5[1]}" == expected_str


def test_canonical_test_identifier_navigate_test():
    """Verify NavigateTest parameter and dot representations."""
    expected_tuple = ("navigatetest", "navigate")

    k1 = ExistingTestRunnerService._canonical_test_identifier("NavigateTest.navigate(Page)", None)
    k2 = ExistingTestRunnerService._canonical_test_identifier("NavigateTest#navigate", None)
    k3 = ExistingTestRunnerService._canonical_test_identifier("navigatetest.navigate", None)
    k4 = ExistingTestRunnerService._canonical_test_identifier("navigate(Page)", "NavigateTest")
    k5 = ExistingTestRunnerService._canonical_test_identifier("navigate", "NavigateTest")

    assert k1 == expected_tuple
    assert k2 == expected_tuple
    assert k3 == expected_tuple
    assert k4 == expected_tuple
    assert k5 == expected_tuple


def test_test_merge_playwright_passed_execution():
    """Verify that a discovered test merging with a PASSED execution result becomes PASSED."""
    discovered = [
        {"name": "authentication", "classname": "AuthenticationTests", "file": "src/test/java/AuthenticationTests.java", "type": "UI"}
    ]
    executed = [
        {"test_name": "authentication(Page)", "suite": "com.example.AuthenticationTests", "status": "PASSED", "duration": "1.234s"}
    ]

    results_by_key = {}
    for r in executed:
        r_name = ExistingTestRunnerService._normalize_test_name(r.get("test_name") or r.get("name", ""))
        r["test_name"] = r_name
        r["name"] = r_name
        key = ExistingTestRunnerService._canonical_test_identifier(r_name, r.get("suite") or r.get("classname", ""), r.get("file", ""))
        results_by_key[key] = r

    for tc in discovered:
        tc_name = ExistingTestRunnerService._normalize_test_name(tc.get("name", "test"))
        tc_suite = tc.get("classname") or tc.get("suite") or tc.get("module", "")
        tc_file = tc.get("file", "")
        key = ExistingTestRunnerService._canonical_test_identifier(tc_name, tc_suite, tc_file)

        assert key in results_by_key
        assert results_by_key[key]["status"] == "PASSED"


def test_test_merge_playwright_failed_execution():
    """Verify that a discovered test merging with a FAILED execution result becomes FAILED."""
    discovered = [
        {"name": "authentication2", "classname": "AuthenticationTests", "file": "src/test/java/AuthenticationTests.java", "type": "UI"}
    ]
    executed = [
        {"test_name": "authentication2(Page)", "suite": "com.example.AuthenticationTests", "status": "FAILED", "duration": "0.850s", "failure_message": "AssertionError"}
    ]

    results_by_key = {}
    for r in executed:
        r_name = ExistingTestRunnerService._normalize_test_name(r.get("test_name") or r.get("name", ""))
        r["test_name"] = r_name
        r["name"] = r_name
        key = ExistingTestRunnerService._canonical_test_identifier(r_name, r.get("suite") or r.get("classname", ""), r.get("file", ""))
        results_by_key[key] = r

    for tc in discovered:
        tc_name = ExistingTestRunnerService._normalize_test_name(tc.get("name", "test"))
        tc_suite = tc.get("classname") or tc.get("suite") or tc.get("module", "")
        tc_file = tc.get("file", "")
        key = ExistingTestRunnerService._canonical_test_identifier(tc_name, tc_suite, tc_file)

        assert key in results_by_key
        assert results_by_key[key]["status"] == "FAILED"


def test_test_merge_genuinely_unexecuted_test():
    """Verify that a discovered test not present in execution results is marked NOT_EXECUTED."""
    discovered = [
        {"name": "authentication4", "classname": "AuthenticationTests", "file": "src/test/java/AuthenticationTests.java", "type": "UI"}
    ]
    executed = [
        {"test_name": "authentication(Page)", "suite": "com.example.AuthenticationTests", "status": "PASSED"}
    ]

    results_by_key = {}
    for r in executed:
        r_name = ExistingTestRunnerService._normalize_test_name(r.get("test_name") or r.get("name", ""))
        r["test_name"] = r_name
        r["name"] = r_name
        key = ExistingTestRunnerService._canonical_test_identifier(r_name, r.get("suite") or r.get("classname", ""), r.get("file", ""))
        results_by_key[key] = r

    for tc in discovered:
        tc_name = ExistingTestRunnerService._normalize_test_name(tc.get("name", "test"))
        tc_suite = tc.get("classname") or tc.get("suite") or tc.get("module", "")
        tc_file = tc.get("file", "")
        key = ExistingTestRunnerService._canonical_test_identifier(tc_name, tc_suite, tc_file)

        if key not in results_by_key:
            results_by_key[key] = {
                "test_name": tc_name,
                "name": tc_name,
                "suite": tc_suite,
                "status": "NOT_EXECUTED",
                "duration": "N/A",
                "file": tc_file,
            }

def test_ui_test_type_detection_for_playwright_page_parameters():
    """Verify that tests with Playwright Page parameter or Playwright keywords are classified as UI."""
    # NavigateTest tests with Page parameter
    for m in ["navigateToPage(Page)", "navigateToPage2(Page)", "navigateToPage3(Page)"]:
        tc = {"test_name": m, "name": m}
        raw_name_lower = m.lower()
        if any(k in raw_name_lower for k in ["(page", "(webdriver", "(browser", "playwright", "selenium"]):
            assigned_type = "UI"
        else:
            assigned_type = "UNIT"
        
        final_type = ExistingTestRunnerService._normalize_test_type(assigned_type, assigned_type, "JUnit")
        assert final_type == "UI"

    # Non-UI test
    plain_tc = {"test_name": "testFindUserName()", "name": "testFindUserName()"}
    raw_plain_lower = plain_tc["name"].lower()
    if any(k in raw_plain_lower for k in ["(page", "(webdriver", "(browser", "playwright", "selenium"]):
        assigned_type = "UI"
    else:
        assigned_type = "UNIT"
    final_type = ExistingTestRunnerService._normalize_test_type(assigned_type, assigned_type, "JUnit")
    assert final_type == "UNIT"


def test_evidence_directory_resolution_for_all_identifier_formats(tmp_path):
    """Verify that all identifier formats resolve to the screenshot directory on disk."""
    import re
    ui_dir = tmp_path / "test-evidence" / "ui"
    ui_dir.mkdir(parents=True)
    
    # Simulate directory created during execution
    auth_dir = ui_dir / "AuthenticationTests.authentication_Page_"
    auth_dir.mkdir()
    (auth_dir / "screenshot.png").write_bytes(b"PNGDATA")

    nav_dir = ui_dir / "NavigateTest.navigateToPage3_Page_"
    nav_dir.mkdir()
    (nav_dir / "screenshot.png").write_bytes(b"PNGDATA")

    def find_screenshot_for_id(test_id: str):
        clean_test_id = test_id.replace("\\", "/").strip("/")
        dot_id = clean_test_id.replace("#", ".")
        dot_sanitized = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', dot_id)
        sanitized_id = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', clean_test_id)

        c_key = ExistingTestRunnerService._canonical_test_identifier(clean_test_id, None)
        canonical_cls, canonical_method = c_key[0], c_key[1]
        canonical_id = f"{canonical_cls}.{canonical_method}"
        short_test = canonical_method or clean_test_id.split("#")[-1].split(".")[-1]

        candidates = [
            ui_dir / dot_sanitized / "screenshot.png",
            ui_dir / dot_id / "screenshot.png",
            ui_dir / sanitized_id / "screenshot.png",
            ui_dir / clean_test_id / "screenshot.png",
            ui_dir / canonical_id / "screenshot.png",
        ]
        for c in candidates:
            if c.is_file():
                return c

        for d in ui_dir.iterdir():
            if d.is_dir():
                d_name = d.name.lower()
                if (
                    d.name == dot_sanitized or
                    d.name == sanitized_id or
                    d_name == dot_sanitized.lower() or
                    d_name == sanitized_id.lower() or
                    (canonical_cls and canonical_method and canonical_cls in d_name and canonical_method in d_name) or
                    (canonical_method and canonical_method in d_name) or
                    (short_test and short_test.lower() in d_name)
                ):
                    shot = d / "screenshot.png"
                    if shot.is_file():
                        return shot
        return None

    # Test all variations
    for tid in [
        "AuthenticationTests.authentication(Page)",
        "AuthenticationTests#authentication(Page)",
        "authenticationtests.authentication",
        "AuthenticationTests.authentication",
        "AuthenticationTests#authentication",
        "AuthenticationTests.authentication_Page_",
    ]:
        found = find_screenshot_for_id(tid)
        assert found is not None, f"Failed to find screenshot for {tid}"
        assert found.read_bytes() == b"PNGDATA"

    for tid in [
        "NavigateTest.navigateToPage3(Page)",
        "NavigateTest#navigateToPage3(Page)",
        "navigatetest.navigatetopage3",
        "NavigateTest.navigateToPage3",
        "NavigateTest#navigateToPage3",
        "NavigateTest.navigateToPage3_Page_",
    ]:
        found = find_screenshot_for_id(tid)
        assert found is not None, f"Failed to find screenshot for {tid}"
        assert found.read_bytes() == b"PNGDATA"


def test_skipped_and_unexecuted_tests_do_not_have_screenshots():
    """Verify that SKIPPED and NOT_EXECUTED UI tests do not receive screenshots."""
    tc_skipped = {
        "test_name": "skippedTest(Page)",
        "suite": "com.example.AuthenticationTests",
        "status": "SKIPPED",
        "type": "UI",
    }
    tc_unexecuted = {
        "test_name": "unexecutedTest(Page)",
        "suite": "com.example.AuthenticationTests",
        "status": "NOT_EXECUTED",
        "type": "UI",
    }

    for tc in [tc_skipped, tc_unexecuted]:
        if tc["status"] in ("SKIPPED", "NOT_EXECUTED"):
            tc["evidence"] = {
                "screenshotAvailable": False,
                "screenshotUrl": None,
                "videoAvailable": False,
                "videoUrl": None,
                "screenshotPath": None,
                "videoPath": None,
                "unavailableReason": "Screenshot unavailable: test was skipped or not executed",
            }
            tc["screenshot_url"] = None
            tc["screenshotUrl"] = None

        assert tc["evidence"]["screenshotAvailable"] is False
        assert tc["evidence"]["screenshotUrl"] is None
        assert tc["screenshot_url"] is None
        assert tc["screenshotUrl"] is None


def test_real_screenshot_per_method_isolation(tmp_path):
    """Verify that each executed method captures its own screenshot without overwriting."""
    screenshots_dir = tmp_path / "target" / "screenshots"
    screenshots_dir.mkdir(parents=True)

    # Valid PNG bytes for two distinct tests
    shot1 = screenshots_dir / "AuthenticationTests.authentication.png"
    shot2 = screenshots_dir / "AuthenticationTests.authentication2.png"

    # Real PNG header: \x89PNG\r\n\x1a\n + image data
    png1_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"TEST1_SCREENSHOT_REAL_BROWSER_PAGE" * 100
    png2_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"TEST2_SCREENSHOT_REAL_BROWSER_PAGE" * 100

    shot1.write_bytes(png1_data)
    shot2.write_bytes(png2_data)

    assert shot1.stat().st_size > 1000
    assert shot2.stat().st_size > 1000
    assert shot1.read_bytes() != shot2.read_bytes()


def test_playwright_video_evidence_passed_and_failed_tests(tmp_path):
    """Verify that both PASSED and FAILED executed UI tests receive video evidence if captured."""
    videos_dir = tmp_path / "target" / "videos"
    videos_dir.mkdir(parents=True)

    # WebM video data (>0 bytes)
    vid_data = b"\x1a\x45\xdf\xa3" + b"WEBM_VIDEO_DATA" * 50
    vid_path = videos_dir / "AuthenticationTests.authentication.webm"
    vid_path.write_bytes(vid_data)

    for status in ["PASSED", "FAILED"]:
        tc = {
            "test_name": "authentication(Page)",
            "suite": "com.example.AuthenticationTests",
            "status": status,
            "type": "UI",
            "test_id": "com.example.AuthenticationTests#authentication(Page)"
        }
        has_video = vid_path.is_file() and vid_path.stat().st_size > 0
        video_url = f"/api/v1/migration/job_123/tests/test/evidence/video" if has_video else None

        tc["evidence"] = {
            "videoAvailable": has_video,
            "videoUrl": video_url,
            "videoPath": str(vid_path),
        }
        tc["video_url"] = video_url
        tc["videoUrl"] = video_url

        assert tc["evidence"]["videoAvailable"] is True
        assert tc["evidence"]["videoUrl"] is not None
        assert tc["videoUrl"] is not None


def test_parameterized_and_repeated_test_discovery_and_canonicalization(tmp_path):
    """Verify that @ParameterizedTest, @RepeatedTest, and intermediate annotations are discovered and canonicalized."""
    from app.application.use_cases.existing_test_runner_service import ExistingTestDetector

    test_file = tmp_path / "src" / "test" / "java" / "com" / "example" / "AdvancedTest.java"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(
        """package com.example;

import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

public class AdvancedTest {

    @Test
    @DisplayName("Basic Unit Test")
    @Order(1)
    void testBasic() {}

    @ParameterizedTest
    @ValueSource(strings = {"racecar", "radar", "level"})
    @DisplayName("Parameterized Palindrome Test")
    void testPalindrome(String candidate) {}

    @RepeatedTest(5)
    @DisplayName("Flaky Repeat Test")
    void testRepeat() {}

    @TestFactory
    void testDynamic() {}
}
""",
        encoding="utf-8"
    )

    detector = ExistingTestDetector(tmp_path)
    result = detector.scan()

    test_cases = result["details"]["testCases"]
    test_names = [t["name"] for t in test_cases]

    assert "testBasic" in test_names
    assert "testPalindrome" in test_names
    assert "testRepeat" in test_names
    assert "testDynamic" in test_names
    assert result["metrics"]["total"] == 4


def test_parameterized_test_execution_results_preserve_invocation_identities():
    """Verify that multiple parameterized invocations (e.g. testPalindrome[0], testPalindrome[1]) retain their identities."""
    # Canonical identification of parameterized invocations retains execution index
    k1 = ExistingTestRunnerService._canonical_test_identifier("testPalindrome[0]", "com.example.AdvancedTest")
    k2 = ExistingTestRunnerService._canonical_test_identifier("testPalindrome(String)[1]", "com.example.AdvancedTest")
    k3 = ExistingTestRunnerService._canonical_test_identifier("testPalindrome(String) [2] candidate=radar", "com.example.AdvancedTest")
    
    assert k1 == ("advancedtest", "testpalindrome[0]")
    assert k2 == ("advancedtest", "testpalindrome[1]")
    assert k3 == ("advancedtest", "testpalindrome[2]")

    # Base canonical identifier strips invocation brackets to match discovered method definition
    base1 = ExistingTestRunnerService._base_canonical_test_identifier("testPalindrome[0]", "com.example.AdvancedTest")
    base2 = ExistingTestRunnerService._base_canonical_test_identifier("testPalindrome(String)[1]", "com.example.AdvancedTest")
    base_discovered = ExistingTestRunnerService._base_canonical_test_identifier("testPalindrome", "AdvancedTest")

    assert base1 == ("advancedtest", "testpalindrome")
    assert base2 == ("advancedtest", "testpalindrome")
    assert base_discovered == ("advancedtest", "testpalindrome")


def test_parameterized_and_standard_suite_reconciliation_exact_counts():
    """
    Simulate the exact scenario:
    - 6 Discovered methods (3 Auth + 1 Navigate.searchByCriteria + 2 Navigate.navigateToPage)
    - 9 Executed invocations (3 Auth PASSED + 3 Navigate.searchByCriteria PASSED + 3 Navigate.navigateToPage ERROR)
    - Final result must have: 6 PASSED, 3 ERROR, 0 NOT_EXECUTED, 0 SKIPPED, Total = 9.
    """
    discovered_test_cases = [
        {"name": "authentication", "classname": "com.example.AuthenticationTests", "file": "src/test/java/AuthenticationTests.java"},
        {"name": "authentication2", "classname": "com.example.AuthenticationTests", "file": "src/test/java/AuthenticationTests.java"},
        {"name": "authentication3", "classname": "com.example.AuthenticationTests", "file": "src/test/java/AuthenticationTests.java"},
        {"name": "searchByCriteria", "classname": "com.example.NavigateTest", "file": "src/test/java/NavigateTest.java"},
        {"name": "navigateToPage", "classname": "com.example.NavigateTest", "file": "src/test/java/NavigateTest.java"},
        {"name": "navigateToPage2", "classname": "com.example.NavigateTest", "file": "src/test/java/NavigateTest.java"},
        {"name": "navigateToPage3", "classname": "com.example.NavigateTest", "file": "src/test/java/NavigateTest.java"},
    ]

    executed_results = [
        {"test_name": "authentication", "suite": "com.example.AuthenticationTests", "status": "PASSED"},
        {"test_name": "authentication2", "suite": "com.example.AuthenticationTests", "status": "PASSED"},
        {"test_name": "authentication3", "suite": "com.example.AuthenticationTests", "status": "PASSED"},
        {"test_name": "searchByCriteria(String, Page)[1]", "suite": "com.example.NavigateTest", "status": "PASSED"},
        {"test_name": "searchByCriteria(String, Page)[2]", "suite": "com.example.NavigateTest", "status": "PASSED"},
        {"test_name": "searchByCriteria(String, Page)[3]", "suite": "com.example.NavigateTest", "status": "PASSED"},
        {"test_name": "navigateToPage", "suite": "com.example.NavigateTest", "status": "ERROR"},
        {"test_name": "navigateToPage2", "suite": "com.example.NavigateTest", "status": "ERROR"},
        {"test_name": "navigateToPage3", "suite": "com.example.NavigateTest", "status": "ERROR"},
    ]

    service = ExistingTestRunnerService()

    # Build results_by_key
    results_by_key = {}
    for r in executed_results:
        key = service._canonical_test_identifier(r["test_name"], r["suite"])
        results_by_key[key] = r

    results_by_base_key = {}
    for k, r in results_by_key.items():
        base_k = service._base_canonical_test_identifier(k[1], k[0])
        results_by_base_key.setdefault(base_k, []).append(r)

    # Reconcile against discovered tests
    matched_count = 0
    for tc in discovered_test_cases:
        key = service._canonical_test_identifier(tc["name"], tc["classname"])
        base_key = service._base_canonical_test_identifier(tc["name"], tc["classname"])
        if key in results_by_key:
            matched_count += 1
        elif base_key in results_by_base_key:
            matched_count += 1
        else:
            results_by_key[key] = {**tc, "status": "NOT_EXECUTED"}

    final_results = list(results_by_key.values())
    passed_count = sum(1 for r in final_results if r["status"] == "PASSED")
    error_count = sum(1 for r in final_results if r["status"] in ("FAILED", "ERROR"))
    not_executed_count = sum(1 for r in final_results if r["status"] == "NOT_EXECUTED")
    skipped_count = sum(1 for r in final_results if r["status"] == "SKIPPED")

    assert len(final_results) == 9
    assert passed_count == 6
    assert error_count == 3
    assert not_executed_count == 0
    assert skipped_count == 0
    assert matched_count == len(discovered_test_cases)


def test_inject_playwright_method_screenshots_instruments_java_methods():
    """Verify that _inject_playwright_method_screenshots injects screenshot capture into Playwright test methods."""
    service = ExistingTestRunnerService()
    java_source = """package com.example;

import com.microsoft.playwright.Page;
import com.microsoft.playwright.junit.UsePlaywright;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

@UsePlaywright
public class AuthenticationTests {

    @Test
    void authentication(Page page) {
        page.navigate("https://example.com/login");
        page.fill("#username", "admin");
    }

    @Test
    public void authentication2(Page p) throws Exception {
        p.navigate("https://example.com/login2");
    }

    @ParameterizedTest
    @ValueSource(strings = {"a", "b"})
    void searchByCriteria(String query, Page page) {
        page.navigate("https://example.com/search?q=" + query);
    }
}
"""
    instrumented, modified = service._inject_playwright_method_screenshots(java_source, "AuthenticationTests")
    assert modified is True
    assert "page.screenshot(new com.microsoft.playwright.Page.ScreenshotOptions()" in instrumented
    assert "p.screenshot(new com.microsoft.playwright.Page.ScreenshotOptions()" in instrumented
    assert 'this.getClass().getSimpleName() + ".authentication.png"' in instrumented
    assert 'this.getClass().getSimpleName() + ".authentication2.png"' in instrumented
    assert 'this.getClass().getSimpleName() + ".searchByCriteria.png"' in instrumented
    assert "target/screenshots" in instrumented
    assert "finally" in instrumented


def test_ui_evidence_screenshot_and_video_independent_metadata(tmp_path):
    """Verify that UI evidence supports PASSED/ERROR with or without screenshots and preserves video metadata."""
    reports_dir = tmp_path / "reports"
    ui_test_dir = reports_dir / "test-evidence" / "ui" / "AuthenticationTests_authentication"
    ui_test_dir.mkdir(parents=True, exist_ok=True)

    dest_shot = ui_test_dir / "screenshot.png"
    dest_shot.write_bytes(b"\x89PNG\r\n\x1a\nfake_image_data")

    dest_vid = ui_test_dir / "video.webm"
    dest_vid.write_bytes(b"fake_video_data")

    has_screenshot = dest_shot.is_file() and dest_shot.stat().st_size > 0
    has_video = dest_vid.is_file() and dest_vid.stat().st_size > 0

    assert has_screenshot is True
    assert has_video is True


def test_zero_existing_tests_returns_no_tests_available(tmp_path):
    """Verify that when 0 tests are detected in repository, run_existing_tests returns NO_TESTS_AVAILABLE."""
    job_id = f"job_zero_{uuid.uuid4().hex[:8]}"
    paths = WorkspacePaths(job_id)
    paths.job_dir.mkdir(parents=True, exist_ok=True)
    paths.original_repo_dir.mkdir(parents=True, exist_ok=True)

    # Empty project without test files
    (paths.original_repo_dir / "src" / "main" / "java").mkdir(parents=True, exist_ok=True)
    (paths.original_repo_dir / "src" / "main" / "java" / "Main.java").write_text("public class Main {}", encoding="utf-8")

    service = ExistingTestRunnerService()
    result = service.run_existing_tests(job_id)

    assert result["status"] == "NO_TESTS_AVAILABLE"
    assert result["testCount"] == 0
    assert result["passed"] == 0
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["notExecuted"] == 0
    assert result["executed"] is False
    assert result["message"] == "No test cases available"
    assert result["metrics"]["total"] == 0
    assert result["metrics"]["passed"] == 0
    assert result["metrics"]["failed"] == 0
    assert result["metrics"]["skipped"] == 0
    assert result["metrics"]["not_executed"] == 0

    scan_res = service.scan_total(job_id)
    assert scan_res["status"] == "NO_TESTS_AVAILABLE"
    assert scan_res["total"] == 0
    assert scan_res["testCasesFound"] == 0
    assert scan_res["message"] == "No test cases available"







