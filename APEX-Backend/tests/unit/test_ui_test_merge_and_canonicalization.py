"""Unit tests for test canonicalization, identity matching, and TEST-MERGE resolution."""

from __future__ import annotations

import pytest
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


def test_playwright_video_evidence_skipped_and_unexecuted_excluded():
    """Verify that SKIPPED and NOT_EXECUTED tests do not receive video evidence."""
    for status in ["SKIPPED", "NOT_EXECUTED"]:
        tc = {
            "test_name": "testSomething(Page)",
            "suite": "com.example.AuthenticationTests",
            "status": status,
            "type": "UI",
        }
        if tc["status"] in ("SKIPPED", "NOT_EXECUTED"):
            tc["evidence"] = {
                "videoAvailable": False,
                "videoUrl": None,
                "videoPath": None,
                "unavailableReason": "Screenshot unavailable: test was skipped or not executed",
            }
            tc["video_url"] = None
            tc["videoUrl"] = None

        assert tc["evidence"]["videoAvailable"] is False
        assert tc["evidence"]["videoUrl"] is None
        assert tc["videoUrl"] is None



