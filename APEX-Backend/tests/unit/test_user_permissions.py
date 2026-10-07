import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException
from app.infrastructure.persistence.mongodb_user_repository import (
    DEFAULT_SETTINGS_PERMISSIONS,
    normalize_permissions,
    get_all_users_sanitized,
)
from app.api.v1.endpoints.admin_settings_controller import (
    list_admin_users,
    get_admin_user_permissions,
    update_admin_user_permissions,
    UserPermissionsPayload,
)
from app.api.v1.endpoints.user_settings_controller import get_my_settings_permissions


def test_normalize_permissions_defaults():
    # None or empty dict returns copy of DEFAULT_SETTINGS_PERMISSIONS
    res = normalize_permissions(None)
    assert res == DEFAULT_SETTINGS_PERMISSIONS
    assert res["llm_settings"] is True
    assert res["quality_checks"] is True

    # Partial permissions dict gets filled with defaults for missing keys
    partial = {"llm_settings": False}
    normalized = normalize_permissions(partial)
    assert normalized["llm_settings"] is False
    assert normalized["quality_checks"] is True
    assert normalized["unit_testing"] is True
    assert normalized["functional_testing"] is True
    assert normalized["brd_testing"] is True
    assert normalized["test_connection"] is True


@pytest.mark.anyio
async def test_get_all_users_sanitized():
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    
    mock_cursor.to_list = AsyncMock(return_value=[
        {
            "_id": 1,
            "full_name": "User One",
            "email": "user1@example.com",
            "role": "USER",
            "password_hash": "secret_hash",
            "settings_permissions": {"functional_testing": False},
        },
        {
            "_id": 2,
            "name": "User Two",
            "email": "user2@example.com",
            "role": "ADMIN",
        }
    ])
    mock_db.users.find.return_value = mock_cursor

    users = await get_all_users_sanitized(mock_db)
    assert len(users) == 2
    
    # Verify sensitive keys removed
    assert "password_hash" not in users[0]
    
    # Verify IDs converted and permissions normalized
    assert users[0]["id"] == 1
    assert users[0]["settings_permissions"]["functional_testing"] is False
    assert users[0]["settings_permissions"]["llm_settings"] is True
    
    assert users[1]["id"] == 2
    assert users[1]["settings_permissions"] == DEFAULT_SETTINGS_PERMISSIONS


@pytest.mark.anyio
async def test_non_admin_blocked_from_admin_endpoints():
    mock_user = MagicMock()
    mock_user.role = "USER"
    mock_user.is_admin = False

    with pytest.raises(HTTPException) as exc_info:
        await list_admin_users(current_user=mock_user)
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        await get_admin_user_permissions("123", current_user=mock_user)
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        payload = UserPermissionsPayload(permissions={"llm_settings": False})
        await update_admin_user_permissions("123", payload, current_user=mock_user)
    assert exc_info.value.status_code == 403


@pytest.mark.anyio
@patch("app.api.v1.endpoints.user_settings_controller.get_mongodb")
@patch("app.infrastructure.persistence.mongodb_system_settings_repository.get_all_settings")
@patch("app.api.v1.endpoints.user_settings_controller._get_current_user_doc")
async def test_effective_permissions_evaluation(mock_get_user, mock_get_sys_settings, mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    # Admin settings: llm_enabled is False (Global disable)
    mock_get_sys_settings.return_value = {
        "llm_enabled": False,
        "quality_checks_config": "enabled",
        "test_cases_playwright_enabled": True,
    }

    # User individual perms: llm_settings is True
    mock_get_user.return_value = {
        "_id": 10,
        "email": "user10@example.com",
        "settings_permissions": {
            "llm_settings": True,
            "quality_checks": True,
            "unit_testing": True,
            "functional_testing": True,
            "brd_testing": True,
            "test_connection": True,
        }
    }

    regular_user = MagicMock()
    regular_user.role = "USER"
    regular_user.is_admin = False
    regular_user.id = 10

    res = await get_my_settings_permissions(current_user=regular_user)
    effective = res["effective_permissions"]

    # Global setting disabled llm_enabled -> Effective llm_settings MUST be False
    assert effective["llm_settings"] is False
    # Other settings where global is enabled and user is True remain True
    assert effective["quality_checks"] is True
    assert effective["functional_testing"] is True


@pytest.mark.anyio
@patch("app.api.v1.endpoints.user_settings_controller.get_mongodb")
@patch("app.infrastructure.persistence.mongodb_system_settings_repository.get_all_settings")
@patch("app.api.v1.endpoints.user_settings_controller._get_current_user_doc")
async def test_admin_gets_all_effective_permissions(mock_get_user, mock_get_sys_settings, mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    mock_get_sys_settings.return_value = {}
    mock_get_user.return_value = {"_id": 1, "role": "ADMIN"}

    admin_user = MagicMock()
    admin_user.role = "ADMIN"
    admin_user.is_admin = True
    admin_user.id = 1

    res = await get_my_settings_permissions(current_user=admin_user)
    effective = res["effective_permissions"]

    # Admins always get True for all modules
    assert effective["llm_settings"] is True
    assert effective["quality_checks"] is True
    assert effective["unit_testing"] is True
    assert effective["functional_testing"] is True
    assert effective["brd_testing"] is True
    assert effective["test_connection"] is True
