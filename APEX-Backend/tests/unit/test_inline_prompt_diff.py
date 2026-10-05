"""Unit tests for inline prompt diff template builder, preview, and apply operations."""

import json
from pathlib import Path
import pytest

from app.domain.models.proposed_test_models import (
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
    UiTestSpec,
)
from app.infrastructure.llm.prompt_templates import build_inline_prompt_diff_template
from app.application.use_cases.proposed_tests.proposed_test_service import ProposedTestService


def test_build_inline_prompt_diff_template_structure_and_dynamic_content():
    existing_inv = [
        {
            "id": "PTC-001",
            "title": "Verify Dashboard",
            "category": "Happy Path Testing",
            "type": "UI",
            "endpoint": "/",
            "validation_status": "VALID",
            "execution_status": "PASSED",
        }
    ]
    api_endpoints = [{"method": "GET", "endpoint": "/api/users"}]
    ui_routes = [{"name": "UserForm", "route": "/users/new"}]
    entities = [{"name": "User"}]
    repo_tests = [{"name": "testUserSave"}]

    prompt = build_inline_prompt_diff_template(
        existing_inventory=existing_inv,
        inline_prompt_text="add 3 negative tests for /users/new",
        discovered_api_endpoints=api_endpoints,
        discovered_ui_routes=ui_routes,
        discovered_entities_and_rules=entities,
        existing_test_inventory_source_repo=repo_tests,
    )

    assert "ROLE" in prompt
    assert "CURRENT TEST INVENTORY" in prompt
    assert "PTC-001" in prompt
    assert "Verify Dashboard" in prompt
    assert "add 3 negative tests for /users/new" in prompt
    assert "/api/users" in prompt
    assert "/users/new" in prompt
    assert "User" in prompt
    assert "testUserSave" in prompt
    assert "RULES" in prompt
    assert "OUTPUT" in prompt
    assert "CLARIFICATION_NEEDED" in prompt
    assert "skipped_as_duplicate" in prompt
    assert "unmet_requests" in prompt


def test_empty_or_whitespace_prompt_returns_clarification_needed(tmp_path, monkeypatch):
    service = ProposedTestService()
    monkeypatch.setattr(service, "_get_job_dir", lambda j: tmp_path)

    # Empty prompt
    diff = service.generate_inline_prompt_diff("test_job", "")
    assert diff["intent"] == "CLARIFICATION_NEEDED"
    assert diff["added"] == []
    assert diff["modified"] == []
    assert diff["removed"] == []
    assert diff["clarification_needed"] is not None

    # Whitespace prompt
    diff_ws = service.generate_inline_prompt_diff("test_job", "   \n\t  ")
    assert diff_ws["intent"] == "CLARIFICATION_NEEDED"
    assert diff_ws["added"] == []
    assert diff_ws["modified"] == []
    assert diff_ws["removed"] == []
    assert diff_ws["clarification_needed"] is not None


def test_preview_does_not_mutate_state(tmp_path, monkeypatch):
    service = ProposedTestService()
    monkeypatch.setattr(service, "_get_job_dir", lambda j: tmp_path)

    initial_test = ProposedTestCase(
        id="PTC-001",
        title="Initial Dashboard Test",
        description="Dashboard test description",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="LLM Generated",
        reason="Baseline",
        expected_result="Loads dashboard",
        status=ProposedTestStatus.PASSED,
        ui_spec=UiTestSpec(target_route="/"),
    )
    service._save_proposals("test_job", [initial_test])

    # Call preview
    diff = service.generate_inline_prompt_diff("test_job", "remove PTC-001")
    assert diff["intent"] == "REMOVE"
    assert "PTC-001" in diff["removed"]

    # Verify persisted state was NOT touched
    current = service.get_proposed_tests("test_job")
    assert len(current) == 1
    assert current[0].id == "PTC-001"


def test_apply_diff_merges_added_modifies_and_removes(tmp_path, monkeypatch):
    service = ProposedTestService()
    monkeypatch.setattr(service, "_get_job_dir", lambda j: tmp_path)

    initial_tests = [
        ProposedTestCase(
            id="PTC-001",
            title="Initial Dashboard Test",
            description="Dashboard test description",
            type=ProposedTestType.UI,
            priority=ProposedTestPriority.HIGH,
            source="LLM Generated",
            reason="Baseline",
            expected_result="Loads dashboard",
            status=ProposedTestStatus.PASSED,
            ui_spec=UiTestSpec(target_route="/"),
        ),
        ProposedTestCase(
            id="PTC-002",
            title="Old Test to Remove",
            description="Old test",
            type=ProposedTestType.UI,
            priority=ProposedTestPriority.LOW,
            source="LLM Generated",
            reason="Baseline",
            expected_result="Old behavior",
            status=ProposedTestStatus.PASSED,
            ui_spec=UiTestSpec(target_route="/old"),
        ),
    ]
    service._save_proposals("test_job", initial_tests)

    diff = {
        "intent": "ADD",
        "added": [
            {
                "id": "PTC-003",
                "title": "New Form Negative Test",
                "description": "Validation test",
                "type": "UI",
                "priority": "MEDIUM",
                "source": "LLM Generated",
                "reason": "Inline prompt addition",
                "expected_result": "Validation alert is visible",
                "status": "PROPOSED",
                "ui_spec": {
                    "target_route": "/employees/new",
                    "input_fields": [],
                    "actions": ["navigate", "click button[type='submit']"],
                    "expected_elements": ["/employees/new"],
                    "selectors": {},
                    "assertions": ["expect(page.locator('.alert')).toBeVisible()"],
                },
            }
        ],
        "modified": [
            {
                "id": "PTC-001",
                "changed_fields": {
                    "expected_result": "Loads dashboard and verifies live KPI counts",
                },
            }
        ],
        "removed": ["PTC-002"],
        "skipped_as_duplicate": [],
        "unmet_requests": [],
        "clarification_needed": None,
    }

    updated = service.apply_inline_prompt_diff("test_job", diff)

    # PTC-002 should be removed
    assert not any(p.id == "PTC-002" for p in updated)
    # PTC-001 should be modified
    ptc1 = next(p for p in updated if p.id == "PTC-001")
    assert ptc1.expected_result == "Loads dashboard and verifies live KPI counts"
    # PTC-003 should be added
    ptc3 = next(p for p in updated if p.id == "PTC-003")
    assert ptc3.title == "New Form Negative Test"
    assert len(updated) == 2

    # Verify persisted state on disk
    reloaded = service.get_proposed_tests("test_job")
    assert len(reloaded) == 2
    assert reloaded[0].expected_result == "Loads dashboard and verifies live KPI counts"


def test_controller_inline_prompt_preview_and_apply(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.deps import User, get_current_user
    from app.application.use_cases.proposed_tests.proposed_test_service import proposed_test_service

    monkeypatch.setattr(proposed_test_service, "_get_job_dir", lambda j: tmp_path)

    fake_user = User(id="user-123", email="tester@example.com", full_name="Tester")
    app.dependency_overrides[get_current_user] = lambda: fake_user

    async def mock_verify(job_id, user):
        return True

    monkeypatch.setattr("app.api.v1.endpoints.proposed_test_controller.verify_job_ownership", mock_verify)

    sample_diff = {
        "intent": "ADD",
        "added": [
            {
                "id": "PTC-100",
                "title": "Controller Test Case",
                "description": "Added via preview",
                "type": "UI",
                "priority": "HIGH",
                "source": "LLM Generated",
                "reason": "Inline prompt addition",
                "expected_result": "Page renders correctly",
                "status": "PROPOSED",
                "ui_spec": {
                    "target_route": "/test",
                    "input_fields": [],
                    "actions": ["navigate"],
                    "expected_elements": ["/test"],
                    "selectors": {},
                    "assertions": [],
                },
            }
        ],
        "modified": [],
        "removed": [],
        "skipped_as_duplicate": [],
        "unmet_requests": [],
        "clarification_needed": None,
    }

    monkeypatch.setattr(
        proposed_test_service,
        "generate_inline_prompt_diff",
        lambda job_id, prompt: (
            {
                "intent": "CLARIFICATION_NEEDED",
                "added": [],
                "modified": [],
                "removed": [],
                "skipped_as_duplicate": [],
                "unmet_requests": [],
                "clarification_needed": "Please specify which endpoint or route.",
            }
            if not prompt.strip()
            else sample_diff
        ),
    )

    try:
        client = TestClient(app)

        # 1. Preview empty prompt -> CLARIFICATION_NEEDED
        resp_empty = client.post(
            "/api/v1/migration/job-abc/proposed-tests/inline-prompt/preview",
            json={"prompt": ""},
        )
        assert resp_empty.status_code == 200
        data_empty = resp_empty.json()
        assert data_empty["intent"] == "CLARIFICATION_NEEDED"
        assert data_empty["clarification_needed"] is not None

        # 2. Preview valid prompt -> diff
        resp_preview = client.post(
            "/api/v1/migration/job-abc/proposed-tests/inline-prompt/preview",
            json={"prompt": "add 2 negative tests for the employee form"},
        )
        assert resp_preview.status_code == 200
        diff = resp_preview.json()
        assert diff["intent"] == "ADD"
        assert len(diff["added"]) == 1

        # 3. Apply diff -> updated inventory
        resp_apply = client.post(
            "/api/v1/migration/job-abc/proposed-tests/inline-prompt/apply",
            json={"diff": diff},
        )
        assert resp_apply.status_code == 200
        inventory = resp_apply.json()
        assert isinstance(inventory, list)
        assert len(inventory) == 1
        assert inventory[0]["id"] == "PTC-100"

    finally:
        app.dependency_overrides.pop(get_current_user, None)

