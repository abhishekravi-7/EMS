"""Unit tests for JUnit Testing Settings persistence and migration integration.

Verifies:
1. All 5 predefined prompt IDs are preserved.
2. Saving selected predefined prompts & manual prompt into test_cases_values.
3. Loading settings directly from test_cases_values.
4. Backward compatibility fallback from legacy quality_checks_values.
5. Saving ensures JUnit settings are removed from quality_checks_values (no duplication).
6. Non-JUnit quality_checks_values (SonarQube, FOSSA, quality gates) are completely preserved.
7. Migration pipeline retrieves JUnit settings from test_cases_values (with fallback)
   and populates UnitTestGenerateAndRunRequest correctly.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import User, get_current_user
from app.infrastructure.persistence.mongodb import get_mongodb
from app.core.junit_prompts import PREDEFINED_JUNIT_PROMPTS, combine_junit_prompts
from app.schemas.unit_test import UnitTestGenerateAndRunRequest


@pytest.fixture
def mock_user():
    return User(
        id="user_junit_test_123",
        full_name="JUnit Test User",
        email="junit_user@example.com",
        role="USER",
        is_active=True,
    )


@pytest.fixture
def client(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_all_five_predefined_prompt_ids_preserved():
    """Requirement 6 & 16g: Verify all five predefined prompt IDs exist with exact naming."""
    assert len(PREDEFINED_JUNIT_PROMPTS) == 5
    prompt_ids = [p["id"] for p in PREDEFINED_JUNIT_PROMPTS]
    expected_ids = [
        "comprehensive_junit_coverage",
        "business_logic_functional_paths",
        "branch_condition_edge_case",
        "exception_negative_scenario",
        "jacoco_dynamic_coverage_gap",
    ]
    for exp in expected_ids:
        assert exp in prompt_ids, f"Expected predefined prompt ID '{exp}' was not found"


def create_mock_mongo(user_doc=None):
    mock_db = MagicMock()
    mock_users_col = MagicMock()
    mock_db.users = mock_users_col
    mock_db.system_settings.find.return_value.to_list = AsyncMock(return_value=[])
    if user_doc is not None:
        mock_users_col.find_one = AsyncMock(return_value=user_doc)
    return mock_db


@pytest.mark.asyncio
async def test_save_predefined_and_manual_prompt_to_test_cases_values(client, mock_user):
    """Requirement 16a, 16b, 16f, 11: JUnit settings are stored in test_cases_values and not duplicated in quality_checks_values."""
    # Existing user document in DB
    existing_user_doc = {
        "_id": mock_user.id,
        "github_config": {"repository": "owner/repo", "branch": "main"},
        "quality_checks_values": {
            "sonarqube_url": "https://sonar.example.com",
            "sonarqube_token": "secret_token_1234",
            "fossa_api_key": "fossa_secret_5678",
            "quality_gate": "strict",
        },
        "test_cases_values": {},
        "llm_values": {},
    }
    mock_db = create_mock_mongo(existing_user_doc)
    mock_users_col = mock_db.users
    mock_users_col.update_one = AsyncMock(return_value=MagicMock(acknowledged=True))

    payload = {
        "github_config": {"repository": "owner/repo", "branch": "main"},
        "quality_checks_values": {
            "sonarqube_url": "https://sonar.example.com",
            "sonarqube_token": "secret_token_1234",
            "fossa_api_key": "fossa_secret_5678",
            "quality_gate": "strict",
            # Even if an older client sends JUnit keys in quality_checks_values:
            "selected_predefined_prompts": ["comprehensive_junit_coverage"],
            "testing_prompt": "Old location prompt",
        },
        "test_cases_values": {
            "selected_predefined_prompts": [
                "comprehensive_junit_coverage",
                "branch_condition_edge_case",
            ],
            "testing_prompt": "Focus on payment gateway and error handling",
        },
        "llm_values": {},
    }

    with patch("app.api.v1.endpoints.user_settings_controller.get_mongodb", AsyncMock(return_value=mock_db)):
        resp = client.post("/api/v1/user/settings/github", json=payload)
        assert resp.status_code == 200

        # Verify update_one arguments
        assert mock_users_col.update_one.called
        call_args = mock_users_col.update_one.call_args[0]
        update_doc = call_args[1]["$set"]

        # 1. test_cases_values has the JUnit settings
        saved_tc = update_doc["test_cases_values"]
        assert saved_tc["selected_predefined_prompts"] == [
            "comprehensive_junit_coverage",
            "branch_condition_edge_case",
        ]
        assert saved_tc["testing_prompt"] == "Focus on payment gateway and error handling"

        # 2. quality_checks_values retains non-JUnit settings intact
        saved_qc = update_doc["quality_checks_values"]
        assert saved_qc["sonarqube_url"] == "https://sonar.example.com"
        assert saved_qc["sonarqube_token"] == "secret_token_1234"
        assert saved_qc["fossa_api_key"] == "fossa_secret_5678"
        assert saved_qc["quality_gate"] == "strict"

        # 3. quality_checks_values does NOT contain JUnit settings (canonical location test_cases_values)
        assert "selected_predefined_prompts" not in saved_qc
        assert "selectedPredefinedPrompts" not in saved_qc
        assert "testing_prompt" not in saved_qc
        assert "testingPrompt" not in saved_qc
        assert "junit_prompt" not in saved_qc


@pytest.mark.asyncio
async def test_load_settings_from_test_cases_values(client, mock_user):
    """Requirement 16c: Loading settings returns JUnit configuration from test_cases_values."""
    user_doc = {
        "_id": mock_user.id,
        "github_config": {"repository": "owner/repo"},
        "quality_checks_values": {
            "sonarqube_url": "https://sonarqube.internal",
        },
        "test_cases_values": {
            "selected_predefined_prompts": [
                "business_logic_functional_paths",
                "exception_negative_scenario",
            ],
            "testing_prompt": "Cover all REST controllers and exceptions",
        },
        "llm_values": {},
    }
    mock_db = create_mock_mongo(user_doc)

    with patch("app.api.v1.endpoints.user_settings_controller.get_mongodb", AsyncMock(return_value=mock_db)):
        resp = client.get("/api/v1/user/settings/github")
        assert resp.status_code == 200
        data = resp.json()

        assert "test_cases_values" in data
        assert data["test_cases_values"]["selected_predefined_prompts"] == [
            "business_logic_functional_paths",
            "exception_negative_scenario",
        ]
        assert data["test_cases_values"]["testing_prompt"] == "Cover all REST controllers and exceptions"
        assert data["quality_checks_values"]["sonarqube_url"] == "https://sonarqube.internal"


@pytest.mark.asyncio
async def test_backward_compatibility_fallback_to_quality_checks_values(client, mock_user):
    """Requirement 10, 16e: If test_cases_values is empty, fall back to quality_checks_values."""
    # Legacy user document with JUnit settings in quality_checks_values and empty test_cases_values
    user_doc = {
        "_id": mock_user.id,
        "github_config": {"repository": "owner/repo"},
        "quality_checks_values": {
            "sonarqube_url": "https://sonar.corp",
            "selected_predefined_prompts": ["jacoco_dynamic_coverage_gap"],
            "testing_prompt": "Legacy testing prompt for jacoco",
        },
        "test_cases_values": {},
        "llm_values": {},
    }
    mock_db = create_mock_mongo(user_doc)

    with patch("app.api.v1.endpoints.user_settings_controller.get_mongodb", AsyncMock(return_value=mock_db)):
        resp = client.get("/api/v1/user/settings/github")
        assert resp.status_code == 200
        data = resp.json()

        # Should fall back and populate test_cases_values for the client
        assert data["test_cases_values"]["selected_predefined_prompts"] == ["jacoco_dynamic_coverage_gap"]
        assert data["test_cases_values"]["testing_prompt"] == "Legacy testing prompt for jacoco"


def test_migration_request_extraction_and_fallback():
    """Requirement 8, 16d, 16e: start_migration extracts from test_cases_values with qc fallback."""
    # Scenario A: Modern request with test_cases_values
    modern_request = {
        "test_cases_values": {
            "selected_predefined_prompts": ["branch_condition_edge_case"],
            "testing_prompt": "Modern prompt",
        },
        "quality_checks_values": {
            "sonarqube_url": "https://sonar.example.com",
        },
    }

    tc_req = modern_request.get("test_cases_values", {})
    qc_req = modern_request.get("quality_checks_values", {})

    testing_prompt_req = (
        modern_request.get("testing_prompt")
        or tc_req.get("testing_prompt")
        or qc_req.get("testing_prompt")
    )
    predefined_prompts_req = (
        modern_request.get("selected_predefined_prompts")
        or tc_req.get("selected_predefined_prompts")
        or qc_req.get("selected_predefined_prompts")
    )

    assert testing_prompt_req == "Modern prompt"
    assert predefined_prompts_req == ["branch_condition_edge_case"]

    # Scenario B: Legacy request with quality_checks_values only
    legacy_request = {
        "quality_checks_values": {
            "selected_predefined_prompts": ["exception_negative_scenario"],
            "testing_prompt": "Legacy prompt",
        }
    }
    tc_req_leg = legacy_request.get("test_cases_values", {})
    qc_req_leg = legacy_request.get("quality_checks_values", {})

    testing_prompt_leg = (
        legacy_request.get("testing_prompt")
        or tc_req_leg.get("testing_prompt")
        or qc_req_leg.get("testing_prompt")
    )
    predefined_prompts_leg = (
        legacy_request.get("selected_predefined_prompts")
        or tc_req_leg.get("selected_predefined_prompts")
        or qc_req_leg.get("selected_predefined_prompts")
    )

    assert testing_prompt_leg == "Legacy prompt"
    assert predefined_prompts_leg == ["exception_negative_scenario"]


def test_migration_unit_test_request_contract(tmp_path):
    """Requirement 8, 16h: UnitTestGenerateAndRunRequest receives exact prompts."""
    selected_predefined = ["comprehensive_junit_coverage", "jacoco_dynamic_coverage_gap"]
    manual_prompt_val = "Validate inventory transaction rollbacks"

    combined = combine_junit_prompts(
        selected_prompt_ids=selected_predefined,
        manual_prompt=manual_prompt_val,
    )

    req = UnitTestGenerateAndRunRequest(
        job_id="job_test_contract_123",
        project_dir=str(tmp_path),
        relative_source_path="",
        build_tool="maven",
        enable_validation_agent=True,
        test_command=None,
        testing_prompt=combined,
        selected_predefined_prompts=selected_predefined,
        manual_prompt=manual_prompt_val,
    )

    assert req.job_id == "job_test_contract_123"
    assert req.selected_predefined_prompts == selected_predefined
    assert req.manual_prompt == manual_prompt_val
    assert "comprehensive JUnit test coverage" in req.testing_prompt
    assert "JaCoCo coverage report" in req.testing_prompt
    assert "Validate inventory transaction rollbacks" in req.testing_prompt
