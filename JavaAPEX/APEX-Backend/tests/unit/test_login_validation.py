from unittest.mock import AsyncMock
import pytest
from httpx import ASGITransport, AsyncClient

from app.application.services.mongodb_auth_service import MongoDBAuthService
from app.core.exceptions import (
    AccountDisabledError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
)
from app.main import app


@pytest.mark.asyncio
async def test_login_invalid_email_format_rejected(mongodb_db, monkeypatch):
    """Invalid email formats (including JAVAAPEX@) must be rejected with 422 and clear message."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    transport = ASGITransport(app=app)
    invalid_emails = [
        "javaapex@",
        "JAVAAPEX@",
        "@gmail.com",
        "javaapex.gmail.com",
        "javaapex@gmail",
        "javaapex",
        "javaapex @gmail.com",
        "javaapex@@gmail.com",
    ]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for invalid_email in invalid_emails:
            response = await client.post(
                "/api/auth/login",
                json={"email": invalid_email, "password": "Password@123"},
            )
            assert response.status_code == 422, f"Failed for email: {invalid_email}"
            data = response.json()
            assert "Please enter a valid email address." in str(data.get("detail", ""))


@pytest.mark.asyncio
async def test_login_unregistered_email_returns_401(mongodb_db, monkeypatch):
    """Unregistered email must return 401 Unauthorized with 'Invalid email or password.'"""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    auth_service = MongoDBAuthService(mongodb_db)
    with pytest.raises(InvalidCredentialsError) as exc_info:
        await auth_service.login("unknownuser987654@gmail.com", "Test@1234")
    assert exc_info.value.http_status == 401
    assert exc_info.value.message == "Invalid email or password."

    # Test via API
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={"email": "unknownuser987654@gmail.com", "password": "Test@1234"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password."
        assert "access_token" not in response.cookies
        assert "refresh_token" not in response.cookies

        # Verify no session created and no new user created
        sessions_count = await mongodb_db.auth_sessions.count_documents({})
        assert sessions_count == 0
        users_count = await mongodb_db.users.count_documents({})
        assert users_count == 0


@pytest.mark.asyncio
async def test_login_registered_email_wrong_password_returns_401(mongodb_db, monkeypatch):
    """Registered email with wrong password must return 401 Unauthorized with 'Invalid email or password.'"""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    from app.infrastructure.persistence import mongodb_user_repository
    await mongodb_user_repository.create_user(
        mongodb_db,
        full_name="Test User",
        email="javaapex@gmail.com",
        password="Test@1234",
        is_email_verified=True,
    )
    auth_service = MongoDBAuthService(mongodb_db)

    with pytest.raises(InvalidCredentialsError) as exc_info:
        await auth_service.login("javaapex@gmail.com", "WrongPassword@123")
    assert exc_info.value.http_status == 401
    assert exc_info.value.message == "Invalid email or password."

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={"email": "javaapex@gmail.com", "password": "WrongPassword@123"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password."
        assert "access_token" not in response.cookies


@pytest.mark.asyncio
async def test_login_registered_email_correct_password_succeeds(mongodb_db, monkeypatch):
    """Registered email with correct password logs in successfully once verified."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    from app.infrastructure.persistence import mongodb_user_repository
    signup_user = await mongodb_user_repository.create_user(
        mongodb_db,
        full_name="Javaapex User",
        email="javaapex@gmail.com",
        password="Test@1234",
        is_email_verified=True,
    )
    auth_service = MongoDBAuthService(mongodb_db)

    user, access_token, refresh_token = await auth_service.login("javaapex@gmail.com", "Test@1234")
    assert user["_id"] == signup_user["_id"]
    assert access_token is not None
    assert refresh_token is not None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={"email": "javaapex@gmail.com", "password": "Test@1234"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "Login successful."
        assert body["user"]["email"] == "javaapex@gmail.com"
        assert body["user"]["id"] == signup_user["_id"]
        assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_login_email_case_insensitivity_and_trimming(mongodb_db, monkeypatch):
    """Emails in lowercase, uppercase, mixed-case, and with whitespace must all log in to the same account."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    from app.infrastructure.persistence import mongodb_user_repository
    signup_user = await mongodb_user_repository.create_user(
        mongodb_db,
        full_name="Javaapex User",
        email="javaapex@gmail.com",
        password="Test@1234",
        is_email_verified=True,
    )
    auth_service = MongoDBAuthService(mongodb_db)

    variations = [
        "javaapex@gmail.com",
        "JAVAAPEX@GMAIL.COM",
        "Javaapex@gmail.com",
        "Javaapex@Gmail.Com",
        "  JAVAAPEX@GMAIL.COM  ",
        "  javaapex@gmail.com  ",
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for variation in variations:
            # 1. Direct service login
            user, access, refresh = await auth_service.login(variation, "Test@1234")
            assert user["email"] == "javaapex@gmail.com"
            assert user["_id"] == signup_user["_id"]

            # 2. HTTP endpoint login
            response = await client.post(
                "/api/auth/login",
                json={"email": variation, "password": "Test@1234"},
            )
            assert response.status_code == 200, f"Login failed for variation: '{variation}'"
            body = response.json()
            assert body["user"]["email"] == "javaapex@gmail.com"
            assert body["user"]["id"] == signup_user["_id"]


@pytest.mark.asyncio
async def test_duplicate_signup_case_insensitive_rejected(mongodb_db, monkeypatch):
    """Attempting signup with JAVAAPEX@GMAIL.COM when javaapex@gmail.com exists must be rejected."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    from app.infrastructure.persistence import mongodb_user_repository
    await mongodb_user_repository.create_user(
        mongodb_db,
        full_name="Javaapex User",
        email="javaapex@gmail.com",
        password="StrongPass@123",
        is_email_verified=True,
    )
    auth_service = MongoDBAuthService(mongodb_db)

    with pytest.raises(EmailAlreadyRegisteredError):
        await auth_service.signup("Javaapex User", "JAVAAPEX@GMAIL.COM", "StrongPass@123")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/signup",
            json={
                "fullName": "Javaapex User",
                "email": "JAVAAPEX@GMAIL.COM",
                "password": "StrongPass@123",
                "confirmPassword": "StrongPass@123",
            },
        )
        assert response.status_code == 409
        assert "An account with this email already exists." in response.json()["detail"]

        # Ensure no duplicate record created
        users = await mongodb_db.users.find({}).to_list(10)
        assert len(users) == 1
        assert users[0]["email"] == "javaapex@gmail.com"


@pytest.mark.asyncio
async def test_login_inactive_user_rejected(mongodb_db):
    """Inactive users (is_active=False) cannot log in."""
    from app.infrastructure.persistence import mongodb_user_repository
    user = await mongodb_user_repository.create_user(
        mongodb_db,
        full_name="Inactive User",
        email="inactive@example.com",
        password="Test@1234",
        is_email_verified=True,
    )
    await mongodb_db.users.update_one({"_id": user["_id"]}, {"$set": {"is_active": False}})

    auth_service = MongoDBAuthService(mongodb_db)
    with pytest.raises(AccountDisabledError):
        await auth_service.login("inactive@example.com", "Test@1234")
