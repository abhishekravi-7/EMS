"""Unit tests ensuring execution of a test subset preserves the master test inventory."""

import json
from pathlib import Path
import pytest

from app.application.use_cases.proposed_tests.proposed_test_service import ProposedTestService
from app.domain.models.proposed_test_models import (
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
)
from app.infrastructure.workspace.workspace_paths import WorkspacePaths


def test_inventory_preservation_after_subset_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify that executing 1 test out of 3 preserves all 3 in proposals and metrics."""
    job_id = "test-job-inventory-preservation"
    
    # Mock WorkspacePaths.job_dir property
    monkeypatch.setattr(WorkspacePaths, "job_dir", tmp_path / job_id)
    
    service = ProposedTestService()
    
    # Create 3 master proposals (2 LLM, 1 BRD)
    p1 = ProposedTestCase(
        id="TC-LLM-001",
        title="LLM Test 1",
        description="Verify LLM API test 1",
        source="LLM Generated",
        reason="Gap coverage",
        expected_result="HTTP 200 OK",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.HIGH,
        status=ProposedTestStatus.APPROVED,
        generation_source="LLM",
    )
    p2 = ProposedTestCase(
        id="TC-LLM-002",
        title="LLM Test 2",
        description="Verify LLM API test 2",
        source="LLM Generated",
        reason="Gap coverage",
        expected_result="HTTP 200 OK",
        type=ProposedTestType.API,
        priority=ProposedTestPriority.MEDIUM,
        status=ProposedTestStatus.APPROVED,
        generation_source="LLM",
    )
    p3 = ProposedTestCase(
        id="TC-BRD-001",
        title="BRD Test 1",
        description="Verify BRD UI workflow",
        source="BRD Document",
        reason="Business requirement",
        expected_result="Dashboard visible",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        status=ProposedTestStatus.APPROVED,
        generation_source="BRD_DOCUMENT",
    )
    
    # Save 3 master proposals
    master_proposals = [p1, p2, p3]
    service._save_proposals(job_id, master_proposals)
    
    # Verify initial status before execution
    initial_status = service.get_status(job_id)
    assert len(initial_status["proposals"]) == 3
    assert initial_status["metrics"]["total"] == 3
    assert initial_status["metrics"]["executed"] == 0
    assert initial_status["metrics"]["not_executed"] == 0
    assert initial_status["metrics"]["brd_generated_count"] == 1
    assert initial_status["metrics"]["llm_generated_count"] == 2

    # Simulate executing only 1 test case (TC-LLM-001)
    p1.status = ProposedTestStatus.PASSED
    service._save_proposals(job_id, master_proposals)
    
    # Write result_payload simulating completed run of TC-LLM-001
    metrics = service._compute_metrics(master_proposals)
    result_payload = {
        "job_id": job_id,
        "status": "COMPLETED",
        "selected_sources": ["LLM"],
        "metrics": metrics.model_dump(),
        "test_cases": [p.model_dump() for p in master_proposals],
    }
    service._get_results_file(job_id).write_text(json.dumps(result_payload, indent=2), encoding="utf-8")
    
    # Verify get_results returns all 3 test cases
    results = service.get_results(job_id)
    assert len(results["test_cases"]) == 3
    assert results["metrics"]["total"] == 3
    assert results["metrics"]["executed"] == 1
    assert results["metrics"]["passed"] == 1
    assert results["metrics"]["not_executed"] == 0
    assert results["metrics"]["brd_generated_count"] == 1
    assert results["metrics"]["llm_generated_count"] == 2
    
    # Verify get_status returns all 3 test cases
    status = service.get_status(job_id)
    assert len(status["proposals"]) == 3
    assert status["metrics"]["total"] == 3
    assert status["metrics"]["executed"] == 1
    assert status["metrics"]["passed"] == 1
    assert status["metrics"]["not_executed"] == 0
