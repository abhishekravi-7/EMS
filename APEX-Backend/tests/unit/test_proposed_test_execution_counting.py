"""
Unit tests for the execution result-counting fix.

Verifies that Executed / Passed / Failed / Not-Executed counts are derived
ONLY from actual Playwright execution results, never from validation status
or the number of valid tests available.

Scenarios covered
-----------------
1. Source build FAILED   -> executed=0, not_executed=len(valid_tests), passed=0, failed=0
2. Build OK + app READY + 5 Playwright results -> executed=5
3. 5 tests selected, app UNAVAILABLE -> executed=0, app_unavailable=5, failed=0
4. valid_count must NEVER be confused with executed_count
5. Master inventory (108 tests) is unchanged after any execution attempt
6. Duplicate/hallucinated tests retain their validation_status regardless of execution
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from app.application.use_cases.proposed_tests.proposed_test_service import ProposedTestService
from app.domain.models.proposed_test_models import (
    ExecutionResult,
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
    ProposedTestValidationResult,
    ValidationStatus,
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _make_test(idx, *, validation_status="VALID", playwright_executable=True):
    """Create a minimal ProposedTestCase."""
    t = ProposedTestCase(
        id=f"TC-{idx:04d}",
        title=f"Test case {idx}",
        description=f"Desc {idx}",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        source="LLM",
        reason="Coverage",
        expected_result="Success",
        status=ProposedTestStatus.PROPOSED,
        generation_source="AI",
    )
    t.validation = ProposedTestValidationResult(
        status=ValidationStatus(validation_status),
        playwright_executable=playwright_executable,
    )
    return t


def _build_inventory(n_valid=86, n_dup=21, n_hall=1):
    tests = []
    for i in range(n_valid):
        tests.append(_make_test(i, validation_status="VALID"))
    for i in range(n_dup):
        tests.append(_make_test(n_valid + i, validation_status="DUPLICATE", playwright_executable=False))
    for i in range(n_hall):
        tests.append(_make_test(n_valid + n_dup + i, validation_status="HALLUCINATED", playwright_executable=False))
    return tests


# --------------------------------------------------------------------------- #
# _compute_metrics  (no I/O, no threads)
# --------------------------------------------------------------------------- #

class TestComputeMetrics:

    def _svc(self):
        return ProposedTestService.__new__(ProposedTestService)

    # 1 -- build failure -------------------------------------------------------
    def test_build_failure_scenario(self):
        """86 valid tests -> NOT_EXECUTED; duplicates/hallucinated -> PROPOSED.
        executed must be 0, not_executed must be 86 (not 108)."""
        svc = self._svc()
        tests = _build_inventory()
        valid_tests = [t for t in tests if t.validation and t.validation.status == ValidationStatus.VALID]
        for t in valid_tests:
            t.status = ProposedTestStatus.NOT_EXECUTED

        metrics = svc._compute_metrics(tests)

        assert metrics.total == 108
        assert metrics.executed == 0, "Build failed -> Playwright never ran -> executed MUST be 0"
        assert metrics.passed == 0
        assert metrics.failed == 0
        assert metrics.not_executed == 86, (
            "not_executed must count only tests explicitly set to NOT_EXECUTED status, "
            "NOT a subtraction formula that includes duplicates/hallucinated"
        )

    # 2 -- valid count != executed count ---------------------------------------
    def test_valid_count_is_not_executed_count(self):
        """All PROPOSED (generation done, no execution): executed must be 0."""
        svc = self._svc()
        tests = _build_inventory()
        metrics = svc._compute_metrics(tests)
        valid_count = sum(1 for t in tests if t.validation and t.validation.status == ValidationStatus.VALID)
        assert valid_count == 86
        assert metrics.executed == 0, "valid_count must NEVER equal executed_count"
        assert metrics.not_executed == 0, "No NOT_EXECUTED statuses have been set yet"

    # 3 -- 5 Playwright results ------------------------------------------------
    def test_five_playwright_results(self):
        """3 PASSED + 2 FAILED -> executed=5."""
        svc = self._svc()
        tests = _build_inventory()
        for t in tests[:3]:
            t.status = ProposedTestStatus.PASSED
        for t in tests[3:5]:
            t.status = ProposedTestStatus.FAILED
        for t in tests[5:86]:
            t.status = ProposedTestStatus.NOT_EXECUTED

        metrics = svc._compute_metrics(tests)

        assert metrics.executed == 5
        assert metrics.passed == 3
        assert metrics.failed == 2
        assert metrics.not_executed == 81
        assert metrics.total == 108

    # 4 -- app unavailable -----------------------------------------------------
    def test_app_unavailable_executed_is_zero(self):
        """5 tests -> APPLICATION_UNAVAILABLE; rest -> NOT_EXECUTED.
        executed=0, failed=0 (infra failure is not a functional failure)."""
        svc = self._svc()
        tests = _build_inventory()
        for t in tests[:5]:
            t.status = ProposedTestStatus.APPLICATION_UNAVAILABLE
        for t in tests[5:86]:
            t.status = ProposedTestStatus.NOT_EXECUTED

        metrics = svc._compute_metrics(tests)

        assert metrics.executed == 0, "APPLICATION_UNAVAILABLE is not a Playwright execution"
        assert metrics.failed == 0, "Infrastructure failure must not increment failed count"
        assert metrics.not_executed == 81
        assert metrics.total == 108

    # 5 -- master inventory unchanged ------------------------------------------
    def test_master_inventory_count_unchanged(self):
        svc = self._svc()
        tests = _build_inventory()
        for t in tests[:10]:
            t.status = ProposedTestStatus.PASSED
        for t in tests[10:20]:
            t.status = ProposedTestStatus.FAILED
        for t in tests[20:86]:
            t.status = ProposedTestStatus.NOT_EXECUTED
        assert svc._compute_metrics(tests).total == 108

    # 6 -- duplicate/hallucinated retain validation_status ---------------------
    def test_duplicate_hallucinated_retain_validation_status(self):
        """Execution must never overwrite validation_status of duplicates/hallucinated."""
        svc = self._svc()
        tests = _build_inventory()
        for t in tests[:86]:
            t.status = ProposedTestStatus.PASSED

        svc._compute_metrics(tests)  # exercising the method

        dup_tests  = [t for t in tests if t.validation and t.validation.status == ValidationStatus.DUPLICATE]
        hall_tests = [t for t in tests if t.validation and t.validation.status == ValidationStatus.HALLUCINATED]
        assert all(t.validation.status == ValidationStatus.DUPLICATE    for t in dup_tests)
        assert all(t.validation.status == ValidationStatus.HALLUCINATED for t in hall_tests)
        # They were never in tests_to_run so their status stayed PROPOSED
        assert all(t.status == ProposedTestStatus.PROPOSED for t in dup_tests)
        assert all(t.status == ProposedTestStatus.PROPOSED for t in hall_tests)


# --------------------------------------------------------------------------- #
# _compute_metrics_for_baseline
# --------------------------------------------------------------------------- #

class TestComputeMetricsForBaseline:

    def _svc(self):
        return ProposedTestService.__new__(ProposedTestService)

    def test_build_failure_baseline_not_executed(self):
        """86 valid tests get NOT_EXECUTED baseline_execution_result.
        Duplicates/hallucinated get no baseline_execution_result.
        not_executed must be 86, NOT 108."""
        svc = self._svc()
        tests = _build_inventory()
        valid_tests = [t for t in tests if t.validation and t.validation.status == ValidationStatus.VALID]
        for t in valid_tests:
            t.baseline_execution_result = ExecutionResult(
                status=ProposedTestStatus.NOT_EXECUTED,
                error="Source build failed",
                error_type="SOURCE_BUILD_FAILED",
            )

        metrics = svc._compute_metrics_for_baseline(tests)

        assert metrics.executed == 0
        assert metrics.passed == 0
        assert metrics.failed == 0
        assert metrics.not_executed == 86, (
            "not_executed must count tests with explicit NOT_EXECUTED baseline_execution_result; "
            "NOT the full 108 (which would wrongly include duplicates/hallucinated)"
        )

    def test_successful_baseline_execution(self):
        """3 PASSED + 2 FAILED baseline results -> executed=5."""
        svc = self._svc()
        tests = _build_inventory()
        valid_tests = [t for t in tests if t.validation and t.validation.status == ValidationStatus.VALID]
        for i, t in enumerate(valid_tests[:5]):
            st = ProposedTestStatus.PASSED if i < 3 else ProposedTestStatus.FAILED
            t.baseline_execution_result = ExecutionResult(status=st)

        metrics = svc._compute_metrics_for_baseline(tests)
        assert metrics.executed == 5
        assert metrics.passed == 3
        assert metrics.failed == 2
        assert metrics.not_executed == 0

    def test_no_baseline_execution_run(self):
        """No baseline results at all -> executed=0, not_executed=0 (not 108)."""
        svc = self._svc()
        tests = _build_inventory()
        metrics = svc._compute_metrics_for_baseline(tests)
        assert metrics.executed == 0
        assert metrics.not_executed == 0, (
            "Tests with no baseline_execution_result must not inflate not_executed"
        )


# --------------------------------------------------------------------------- #
# completion log invariant
# --------------------------------------------------------------------------- #

def test_completion_log_reports_metrics_executed_not_len_tests_to_run(tmp_path):
    """The completion log must say 'Executed: 0/108', not 'Executed: 86/108'
    after a build failure (len(tests_to_run)==86, metrics.executed==0)."""
    svc = ProposedTestService()
    job_id = "job-log-invariant"
    proposals = _build_inventory()
    captured: list[str] = []

    def fake_log(jid, msg, level="INFO"):
        captured.append(msg)

    from app.domain.models.build_result import BuildResult
    failed_build = BuildResult(success=False, tool="maven", skipped=False, error_lines=["Lombok/JDK compilation error"])

    fake_file = MagicMock()
    fake_file.write_text = MagicMock()

    with (
        patch.object(svc, "_log", side_effect=fake_log),
        patch.object(svc, "_save_proposals"),
        patch.object(svc, "_save_status"),
        patch.object(svc, "_get_results_file",          return_value=fake_file),
        patch.object(svc, "_get_baseline_results_file", return_value=fake_file),
        patch.object(svc, "get_proposed_tests",         return_value=proposals),
        patch("app.application.use_cases.proposed_tests.proposed_test_service.WorkspacePaths") as wp,
        patch("app.infrastructure.build.build_validator.BuildValidator.validate", return_value=failed_build),
        patch("app.application.use_cases.proposed_tests.proposed_test_executor.resolve_app_port", return_value=8081),
    ):
        wp.return_value.job_dir          = tmp_path / job_id
        wp.return_value.original_repo_dir = tmp_path / "repo"

        svc.run_approved_tests(job_id, {})
        time.sleep(1.2)  # let background thread finish

    completion = [m for m in captured if "Baseline execution completed" in m]
    assert completion, "Expected a 'Baseline execution completed' log line"
    msg = completion[0]
    assert "Executed: 0/" in msg, \
        f"Expected executed=0 after build failure, got: {msg!r}"
    assert "86/" not in msg, \
        f"86 (valid count) must NOT appear as executed count: {msg!r}"
    assert "Not Executed: 86" in msg, \
        f"Expected 'Not Executed: 86' in log: {msg!r}"
