import pytest
from unittest.mock import MagicMock, patch
from app.application.use_cases.proposed_tests.proposed_test_service import ProposedTestService
from app.domain.models.proposed_test_models import (
    ProposedTestCase,
    ProposedTestType,
    ProposedTestPriority,
    ProposedTestStatus,
    ExecutionResult,
)


@pytest.fixture
def mock_proposals():
    return [
        ProposedTestCase(
            id="PTC-001",
            title="LLM API Test Endpoint 1",
            description="LLM generated test case for Endpoint 1",
            type=ProposedTestType.API,
            priority=ProposedTestPriority.HIGH,
            source="Controller",
            reason="Endpoint gap test",
            expected_result="200 OK",
            status=ProposedTestStatus.PROPOSED,
            generation_source="AI_GENERATED",
        ),
        ProposedTestCase(
            id="PTC-002",
            title="LLM UI Workflow Test",
            description="LLM generated UI test",
            type=ProposedTestType.UI,
            priority=ProposedTestPriority.MEDIUM,
            source="UI",
            reason="UI workflow verification",
            expected_result="UI renders correctly",
            status=ProposedTestStatus.PROPOSED,
            generation_source="STATIC_ANALYSIS",
        ),
        ProposedTestCase(
            id="PTC-003",
            title="BRD Functional Business Requirement 1",
            description="Functional testing document BRD requirement",
            type=ProposedTestType.API,
            priority=ProposedTestPriority.HIGH,
            source="BRD Document",
            reason="BRD requirement verification",
            expected_result="Business logic valid",
            status=ProposedTestStatus.PROPOSED,
            generation_source="BRD_DOCUMENT",
        ),
        ProposedTestCase(
            id="PTC-004",
            title="Execute ExistingTestSuite.testMethod1",
            description="Existing repository test method 1",
            type=ProposedTestType.UNIT,
            priority=ProposedTestPriority.HIGH,
            source="Existing Repository",
            reason="Existing unit test coverage",
            expected_result="Pass with 0 errors",
            status=ProposedTestStatus.PROPOSED,
            generation_source="EXISTING",
        ),
        ProposedTestCase(
            id="PTC-005",
            title="Execute ExistingTestSuite.testMethod2",
            description="Existing repository test method 2",
            type=ProposedTestType.UNIT,
            priority=ProposedTestPriority.HIGH,
            source="Existing Repository",
            reason="Existing unit test coverage",
            expected_result="Pass with 0 errors",
            status=ProposedTestStatus.PROPOSED,
            generation_source="EXISTING",
        ),
    ]


def test_combination_1_none_selected(tmp_path, mock_proposals):
    service = ProposedTestService()
    job_id = "test-job-comb-1"
    
    with patch.object(service, "get_proposed_tests", return_value=mock_proposals):
        with patch.object(service, "_get_job_dir", return_value=tmp_path):
            res = service.run_approved_tests(job_id, sources=[])
            assert res["status"] in ["IDLE", "COMPLETED"]
            assert res["total"] == 0
            assert res["executed"] == 0


def test_combination_2_llm_only(tmp_path, mock_proposals):
    service = ProposedTestService()
    job_id = "test-job-comb-2"
    
    with patch.object(service, "get_proposed_tests", return_value=mock_proposals):
        with patch.object(service, "_get_job_dir", return_value=tmp_path):
            with patch("app.application.use_cases.proposed_tests.proposed_test_service.ProposedTestExecutor") as mock_exec_cls:
                mock_exec = MagicMock()
                mock_exec.execute_test.return_value = ExecutionResult(
                    status=ProposedTestStatus.PASSED,
                    duration="0.05s",
                    assertions_passed=1,
                    assertions_failed=0,
                )
                mock_exec_cls.return_value = mock_exec
                
                res = service.run_approved_tests(job_id, sources=["LLM"])
                assert res["status"] == "RUNNING"
                assert res["total_approved"] == 2  # PTC-001, PTC-002


def test_combination_3_functional_doc_only(tmp_path, mock_proposals):
    service = ProposedTestService()
    job_id = "test-job-comb-3"
    
    with patch.object(service, "get_proposed_tests", return_value=mock_proposals):
        with patch.object(service, "_get_job_dir", return_value=tmp_path):
            with patch("app.application.use_cases.proposed_tests.proposed_test_service.ProposedTestExecutor") as mock_exec_cls:
                mock_exec = MagicMock()
                mock_exec.execute_test.return_value = ExecutionResult(
                    status=ProposedTestStatus.PASSED,
                    duration="0.05s",
                    assertions_passed=1,
                    assertions_failed=0,
                )
                mock_exec_cls.return_value = mock_exec
                
                res = service.run_approved_tests(job_id, sources=["FUNCTIONAL_DOC"])
                assert res["status"] == "RUNNING"
                assert res["total_approved"] == 1  # PTC-003


def test_combination_4_existing_only(tmp_path, mock_proposals):
    service = ProposedTestService()
    job_id = "test-job-comb-4"
    
    with patch.object(service, "get_proposed_tests", return_value=mock_proposals):
        with patch.object(service, "_get_job_dir", return_value=tmp_path):
            with patch("app.application.use_cases.proposed_tests.proposed_test_service.ProposedTestExecutor") as mock_exec_cls:
                mock_exec = MagicMock()
                mock_exec.execute_test.return_value = ExecutionResult(
                    status=ProposedTestStatus.PASSED,
                    duration="0.05s",
                    assertions_passed=1,
                    assertions_failed=0,
                )
                mock_exec_cls.return_value = mock_exec
                
                res = service.run_approved_tests(job_id, sources=["EXISTING"])
                assert res["status"] == "RUNNING"
                assert res["total_approved"] == 2  # PTC-004, PTC-005


def test_combination_5_llm_and_doc(tmp_path, mock_proposals):
    service = ProposedTestService()
    job_id = "test-job-comb-5"
    
    with patch.object(service, "get_proposed_tests", return_value=mock_proposals):
        with patch.object(service, "_get_job_dir", return_value=tmp_path):
            with patch("app.application.use_cases.proposed_tests.proposed_test_service.ProposedTestExecutor") as mock_exec_cls:
                mock_exec = MagicMock()
                mock_exec.execute_test.return_value = ExecutionResult(
                    status=ProposedTestStatus.PASSED,
                    duration="0.05s",
                    assertions_passed=1,
                    assertions_failed=0,
                )
                mock_exec_cls.return_value = mock_exec
                
                res = service.run_approved_tests(job_id, sources=["LLM", "FUNCTIONAL_DOC"])
                assert res["status"] == "RUNNING"
                assert res["total_approved"] == 3  # 2 LLM + 1 Doc


def test_combination_6_llm_and_existing(tmp_path, mock_proposals):
    service = ProposedTestService()
    job_id = "test-job-comb-6"
    
    with patch.object(service, "get_proposed_tests", return_value=mock_proposals):
        with patch.object(service, "_get_job_dir", return_value=tmp_path):
            with patch("app.application.use_cases.proposed_tests.proposed_test_service.ProposedTestExecutor") as mock_exec_cls:
                mock_exec = MagicMock()
                mock_exec.execute_test.return_value = ExecutionResult(
                    status=ProposedTestStatus.PASSED,
                    duration="0.05s",
                    assertions_passed=1,
                    assertions_failed=0,
                )
                mock_exec_cls.return_value = mock_exec
                
                res = service.run_approved_tests(job_id, sources=["LLM", "EXISTING"])
                assert res["status"] == "RUNNING"
                assert res["total_approved"] == 4  # 2 LLM + 2 Existing


def test_combination_7_doc_and_existing(tmp_path, mock_proposals):
    service = ProposedTestService()
    job_id = "test-job-comb-7"
    
    with patch.object(service, "get_proposed_tests", return_value=mock_proposals):
        with patch.object(service, "_get_job_dir", return_value=tmp_path):
            with patch("app.application.use_cases.proposed_tests.proposed_test_service.ProposedTestExecutor") as mock_exec_cls:
                mock_exec = MagicMock()
                mock_exec.execute_test.return_value = ExecutionResult(
                    status=ProposedTestStatus.PASSED,
                    duration="0.05s",
                    assertions_passed=1,
                    assertions_failed=0,
                )
                mock_exec_cls.return_value = mock_exec
                
                res = service.run_approved_tests(job_id, sources=["FUNCTIONAL_DOC", "EXISTING"])
                assert res["status"] == "RUNNING"
                assert res["total_approved"] == 3  # 1 Doc + 2 Existing


def test_combination_8_all_three(tmp_path, mock_proposals):
    service = ProposedTestService()
    job_id = "test-job-comb-8"
    
    with patch.object(service, "get_proposed_tests", return_value=mock_proposals):
        with patch.object(service, "_get_job_dir", return_value=tmp_path):
            with patch("app.application.use_cases.proposed_tests.proposed_test_service.ProposedTestExecutor") as mock_exec_cls:
                mock_exec = MagicMock()
                mock_exec.execute_test.return_value = ExecutionResult(
                    status=ProposedTestStatus.PASSED,
                    duration="0.05s",
                    assertions_passed=1,
                    assertions_failed=0,
                )
                mock_exec_cls.return_value = mock_exec
                
                res = service.run_approved_tests(job_id, sources=["LLM", "FUNCTIONAL_DOC", "EXISTING"])
                assert res["status"] == "RUNNING"
                assert res["total_approved"] == 5  # 2 LLM + 1 Doc + 2 Existing


def test_metrics_computation(mock_proposals):
    service = ProposedTestService()
    metrics = service._compute_metrics(mock_proposals)
    
    assert metrics.total == 5
    assert metrics.ai_generated_count == 2
    assert metrics.brd_generated_count == 1
    assert metrics.existing_count == 2
