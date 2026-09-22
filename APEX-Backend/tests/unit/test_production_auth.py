import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.services.mongodb_auth_service import MongoDBAuthService
from app.core.exceptions import (
    AccountDisabledError,
    EmailAlreadyRegisteredError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidVerificationTokenError,
    OAuthAccountConflictError,
    OAuthEmailMissingError,
)
from app.infrastructure.persistence import mongodb_user_repository
from app.main import app



@pytest.mark.asyncio
async def test_signup_creates_unverified_user_and_verification_code(mongodb_db, monkeypatch):
    """Local signup creates temporary pending_signups record, does NOT create user in users collection, and sends 6-digit code."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    
    mock_send_email = AsyncMock(return_value=True)
    monkeypatch.setattr("app.application.services.mongodb_auth_service.send_verification_email", mock_send_email)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/signup",
            json={
                "fullName": "Javaapex User",
                "email": "  JAVAAPEX@DOMAIN.COM  ",
                "password": "StrongPassword@123",
                "confirmPassword": "StrongPassword@123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "javaapex@domain.com"
        assert "message" in data

    # Check MongoDB users collection: MUST BE EMPTY (NO RECORD FOR USER)
    user = await mongodb_db.users.find_one({"email": "javaapex@domain.com"})
    assert user is None
    users_count = await mongodb_db.users.count_documents({})
    assert users_count == 0

    # Check MongoDB pending_signups collection: temporary record exists
    pending = await mongodb_db.pending_signups.find_one({"email": "javaapex@domain.com"})
    assert pending is not None
    assert pending["email"] == "javaapex@domain.com"
    assert pending["full_name"] == "Javaapex User"
    assert pending["password_hash"] is not None
    assert pending["verification_code_hash"] is not None
    assert pending["attempts"] == 0
    assert pending["expires_at"] is not None

    # Check email service was invoked with 6-digit code
    assert mock_send_email.called
    call_kwargs = mock_send_email.call_args[1]
    assert call_kwargs["to_email"] == "javaapex@domain.com"
    verification_code = call_kwargs["verification_code"]
    assert len(verification_code) == 6
    assert verification_code.isdigit()
    assert hashlib.sha256(verification_code.encode()).hexdigest() == pending["verification_code_hash"]


@pytest.mark.asyncio
async def test_unverified_user_cannot_login(mongodb_db, monkeypatch):
    """Attempting login without verifying email fails because user is not in users collection."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    monkeypatch.setattr("app.application.services.mongodb_auth_service.send_verification_email", AsyncMock(return_value=True))

    auth_service = MongoDBAuthService(mongodb_db)
    await auth_service.signup("Javaapex User", "unverified@domain.com", "StrongPassword@123")

    with pytest.raises(InvalidCredentialsError):
        await auth_service.login("unverified@domain.com", "StrongPassword@123")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={"email": "unverified@domain.com", "password": "StrongPassword@123"},
        )
        assert response.status_code == 401
        assert "access_token" not in response.cookies


@pytest.mark.asyncio
async def test_email_verification_code_flow(mongodb_db, monkeypatch):
    """Verifying email with valid 6-digit code creates user in users collection, deletes pending signup, and establishes session."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    monkeypatch.setattr("app.infrastructure.persistence.mongodb.get_mongodb", AsyncMock(return_value=mongodb_db))
    
    captured_code = None
    async def mock_email(to_email, user_name, verification_code):
        nonlocal captured_code
        captured_code = verification_code
        return True

    monkeypatch.setattr("app.application.services.mongodb_auth_service.send_verification_email", mock_email)

    auth_service = MongoDBAuthService(mongodb_db)
    await auth_service.signup("Javaapex User", "javaapex.verify@domain.com", "StrongPassword@123")
    assert captured_code is not None
    assert len(captured_code) == 6

    # Verify user does NOT exist in users collection prior to code verification
    assert await mongodb_db.users.find_one({"email": "javaapex.verify@domain.com"}) is None
    assert await mongodb_db.pending_signups.find_one({"email": "javaapex.verify@domain.com"}) is not None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Verify email code API
        response = await client.post(
            "/api/auth/verify-email-code",
            json={"email": "javaapex.verify@domain.com", "code": captured_code},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Email verified successfully."
        assert data["user"]["email"] == "javaapex.verify@domain.com"
        assert data["user"]["isEmailVerified"] is True
        assert data["user"]["id"] == 1
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

        # Check MongoDB user is NOW created in users and verified
        user = await mongodb_db.users.find_one({"email": "javaapex.verify@domain.com"})
        assert user is not None
        assert user["_id"] == 1
        assert user["is_email_verified"] is True

        # Check pending signup is deleted
        pending = await mongodb_db.pending_signups.find_one({"email": "javaapex.verify@domain.com"})
        assert pending is None

        # Immediate access to protected /me endpoint with cookies from verification
        me_resp = await client.get("/api/auth/me", cookies=response.cookies)
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "javaapex.verify@domain.com"

        # Subsequent login also succeeds with email + password only
        login_resp = await client.post(
            "/api/auth/login",
            json={"email": "javaapex.verify@domain.com", "password": "StrongPassword@123"},
        )
        assert login_resp.status_code == 200
        assert "access_token" in login_resp.cookies
        assert "refresh_token" in login_resp.cookies


@pytest.mark.asyncio
async def test_invalid_code_attempts_and_rate_limits(mongodb_db, monkeypatch):
    """Wrong verification code increments attempts and invalidates after 5 failed attempts without creating user."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    monkeypatch.setattr("app.application.services.mongodb_auth_service.send_verification_email", AsyncMock(return_value=True))

    auth_service = MongoDBAuthService(mongodb_db)
    await auth_service.signup("Javaapex User", "attempts@domain.com", "StrongPassword@123")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 4 incorrect attempts
        for i in range(4):
            resp = await client.post(
                "/api/auth/verify-email-code",
                json={"email": "attempts@domain.com", "code": "000000"},
            )
            assert resp.status_code == 400
            assert "invalid" in resp.json()["detail"].lower()
            # User must NOT be created
            assert await mongodb_db.users.find_one({"email": "attempts@domain.com"}) is None

        # 5th incorrect attempt locks/invalidates the code and removes pending signup
        resp5 = await client.post(
            "/api/auth/verify-email-code",
            json={"email": "attempts@domain.com", "code": "000000"},
        )
        assert resp5.status_code == 400
        assert "too many incorrect attempts" in resp5.json()["detail"].lower()

        # Check pending signup is removed and users collection is still empty
        assert await mongodb_db.pending_signups.find_one({"email": "attempts@domain.com"}) is None
        assert await mongodb_db.users.find_one({"email": "attempts@domain.com"}) is None


@pytest.mark.asyncio
async def test_expired_or_reused_verification_code_rejected(mongodb_db, monkeypatch):
    """Expired or non-existent verification code is rejected without creating user."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    auth_service = MongoDBAuthService(mongodb_db)

    # 1. Invalid code
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/verify-email-code",
            json={"email": "nonexistent@domain.com", "code": "123456"},
        )
        assert resp.status_code == 400

    # 2. Expired pending signup
    code_hash = hashlib.sha256("654321".encode()).hexdigest()
    await mongodb_db.pending_signups.insert_one({
        "email": "expired@domain.com",
        "password_hash": "dummy_hash",
        "full_name": "Expired User",
        "verification_code_hash": code_hash,
        "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
        "created_at": datetime.now(timezone.utc) - timedelta(minutes=11),
        "updated_at": datetime.now(timezone.utc) - timedelta(minutes=11),
        "attempts": 0,
    })

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/verify-email-code",
            json={"email": "expired@domain.com", "code": "654321"},
        )
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()
        assert await mongodb_db.users.find_one({"email": "expired@domain.com"}) is None


@pytest.mark.asyncio
async def test_resend_verification_code(mongodb_db, monkeypatch):
    """Resend verification code enforces 60s cooldown rate limit and updates pending_signups with fresh 6-digit code."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    mock_send_email = AsyncMock(return_value=True)
    monkeypatch.setattr("app.application.services.mongodb_auth_service.send_verification_email", mock_send_email)

    auth_service = MongoDBAuthService(mongodb_db)
    await auth_service.signup("Javaapex User", "resend.code@domain.com", "StrongPassword@123")

    mock_send_email.reset_mock()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Calling immediately hits rate-limiting cooldown (60s), returns 400 with cooldown message
        response = await client.post(
            "/api/auth/resend-verification-code",
            json={"email": "RESEND.CODE@DOMAIN.COM"},
        )
        assert response.status_code == 400
        assert "60 seconds" in response.json()["detail"]
        assert not mock_send_email.called

        # 2. Simulate 65s passed by backdating updated_at
        await mongodb_db.pending_signups.update_one(
            {"email": "resend.code@domain.com"},
            {"$set": {"updated_at": datetime.now(timezone.utc) - timedelta(seconds=65), "created_at": datetime.now(timezone.utc) - timedelta(seconds=65)}},
        )

        # 3. Calling after cooldown sends fresh 6-digit code
        response2 = await client.post(
            "/api/auth/resend-verification-code",
            json={"email": "RESEND.CODE@DOMAIN.COM"},
        )
        assert response2.status_code == 200
        assert mock_send_email.called
        assert mock_send_email.call_args[1]["to_email"] == "resend.code@domain.com"
        assert len(mock_send_email.call_args[1]["verification_code"]) == 6



@pytest.mark.asyncio
async def test_google_id_token_authentication(mongodb_db, monkeypatch):
    """Google ID token sign-in (One Tap/Button) verifies token, creates user, auto-verifies email, and returns session cookies."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    
    mock_claims = {
        "sub": "google-user-123456",
        "email": "google.user@gmail.com",
        "email_verified": True,
        "name": "Google User",
        "picture": "https://lh3.googleusercontent.com/a/abc",
    }
    monkeypatch.setattr(
        "app.application.services.mongodb_auth_service.verify_google_id_token",
        AsyncMock(return_value=mock_claims),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/google",
            json={"credential": "mock_google_id_token_jwt_string"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["user"]["id"], int)
        assert data["user"]["email"] == "google.user@gmail.com"
        assert data["user"]["fullName"] == "Google User"
        assert data["user"]["isEmailVerified"] is True
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

    # Check MongoDB documents
    created_id = data["user"]["id"]
    user = await mongodb_db.users.find_one({"_id": created_id})
    assert user["_id"] == created_id
    assert user["auth_provider"] == "google"
    assert user["is_email_verified"] is True

    oauth_acc = await mongodb_db.oauth_accounts.find_one({"provider": "google", "provider_user_id": "google-user-123456"})
    assert oauth_acc is not None
    assert oauth_acc["user_id"] == created_id


@pytest.mark.asyncio
async def test_safe_account_linking_with_existing_email(mongodb_db, monkeypatch):
    """OAuth login with verified email matching an existing local account safely links without duplicating user."""
    auth_service = MongoDBAuthService(mongodb_db)
    
    # 1. User created locally with verified email javaapex@linktest.com
    local_user = await mongodb_user_repository.create_user(
        mongodb_db,
        full_name="Javaapex Local",
        email="javaapex@linktest.com",
        password="StrongPass@123",
        is_email_verified=True,
    )
    target_id = local_user["_id"]
    assert isinstance(target_id, int)

    # 2. User signs in with GitHub with same verified email
    github_user = await auth_service.authenticate_with_oauth(
        provider="github",
        provider_user_id="github-uid-789",
        email="JAVAAPEX@LINKTEST.COM",
        email_verified=True,
        full_name="Javaapex GitHub",
        profile_image="https://avatars.githubusercontent.com/u/789",
    )
    # Linked to local_user, not a new user
    assert github_user["_id"] == target_id

    # Check oauth_accounts collection
    oauth_acc = await mongodb_db.oauth_accounts.find_one({"provider": "github", "provider_user_id": "github-uid-789"})
    assert oauth_acc is not None
    assert oauth_acc["user_id"] == target_id


@pytest.mark.asyncio
async def test_oauth_unverified_email_linking_rejected(mongodb_db):
    """OAuth provider with unverified email cannot link to existing account (prevents account takeover)."""
    auth_service = MongoDBAuthService(mongodb_db)
    await mongodb_user_repository.create_user(
        mongodb_db,
        full_name="Existing User",
        email="victim@domain.com",
        password="StrongPass@123",
        is_email_verified=True,
    )

    with pytest.raises(OAuthAccountConflictError):
        await auth_service.authenticate_with_oauth(
            provider="github",
            provider_user_id="attacker-fake-999",
            email="victim@domain.com",
            email_verified=False,  # Unverified!
            full_name="Attacker",
            profile_image=None,
        )


@pytest.mark.asyncio
async def test_no_session_or_jwt_or_auth_sessions_record_before_verification(mongodb_db, monkeypatch):
    """Ensure no JWT cookies or auth_sessions records exist before email verification."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    monkeypatch.setattr("app.application.services.mongodb_auth_service.send_verification_email", AsyncMock(return_value=True))

    auth_service = MongoDBAuthService(mongodb_db)
    await auth_service.signup("Javaapex Unverified", "unverified.session@domain.com", "StrongPassword@123")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Attempt login before verification
        login_resp = await client.post(
            "/api/auth/login",
            json={"email": "unverified.session@domain.com", "password": "StrongPassword@123"},
        )
        assert login_resp.status_code == 401
        assert "access_token" not in login_resp.cookies
        assert "refresh_token" not in login_resp.cookies

        # 2. Check auth_sessions collection in MongoDB
        session_count = await mongodb_db.auth_sessions.count_documents({})
        assert session_count == 0

        # 3. Check users collection is empty
        users_count = await mongodb_db.users.count_documents({})
        assert users_count == 0


@pytest.mark.asyncio
async def test_duplicate_email_signup_case_insensitive_rejected(mongodb_db, monkeypatch):
    """Duplicate signup with differing case or whitespace is rejected when verified account exists."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    monkeypatch.setattr("app.application.services.mongodb_auth_service.send_verification_email", AsyncMock(return_value=True))

    await mongodb_user_repository.create_user(
        mongodb_db,
        full_name="Original User",
        email="javaapex.case@domain.com",
        password="StrongPassword@123",
        is_email_verified=True,
    )

    auth_service = MongoDBAuthService(mongodb_db)

    # Attempt signup with uppercase/spaces
    with pytest.raises(EmailAlreadyRegisteredError):
        await auth_service.signup("Duplicate User", "  JAVAAPEX.CASE@DOMAIN.COM  ", "StrongPassword@123")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/signup",
            json={
                "fullName": "Duplicate User",
                "email": "Javaapex.Case@Domain.Com",
                "password": "StrongPassword@123",
                "confirmPassword": "StrongPassword@123",
            },
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()



@pytest.mark.asyncio
async def test_case_insensitive_and_whitespace_email_normalization(mongodb_db, monkeypatch):
    """Email normalization handles mixed case and whitespace across all authentication operations."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    captured_code = None
    async def mock_email(to_email, user_name, verification_code):
        nonlocal captured_code
        captured_code = verification_code
        return True

    monkeypatch.setattr("app.application.services.mongodb_auth_service.send_verification_email", mock_email)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Signup with mixed case & spaces
        signup_resp = await client.post(
            "/api/auth/signup",
            json={
                "fullName": "Normalization Test",
                "email": "   User.Normalize@Domain.COM   ",
                "password": "StrongPassword@123",
                "confirmPassword": "StrongPassword@123",
            },
        )
        assert signup_resp.status_code == 201
        assert signup_resp.json()["email"] == "user.normalize@domain.com"

        # Verify with 6-digit code
        verify_resp = await client.post(
            "/api/auth/verify-email-code",
            json={"email": "   USER.NORMALIZE@DOMAIN.COM   ", "code": captured_code},
        )
        assert verify_resp.status_code == 200

        # Login with different casing & spaces
        login_resp = await client.post(
            "/api/auth/login",
            json={
                "email": "  USER.NORMALIZE@DOMAIN.COM  ",
                "password": "StrongPassword@123",
            },
        )
        assert login_resp.status_code == 200
        assert login_resp.json()["user"]["email"] == "user.normalize@domain.com"


@pytest.mark.asyncio
async def test_google_oauth_redirect_flow(mongodb_db, monkeypatch):
    """Google OAuth redirect initiates PKCE flow and completes login on callback."""
    from app.infrastructure.oauth.google_client import GoogleUserProfile

    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    monkeypatch.setattr("app.core.config.settings.google_client_id", "mock-google-id")
    monkeypatch.setattr("app.core.config.settings.google_client_secret", "mock-google-secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login endpoint initiates redirect and sets PKCE cookie
        login_resp = await client.get("/api/auth/google/login", follow_redirects=False)
        assert login_resp.status_code == 302
        assert "accounts.google.com" in login_resp.headers["location"]
        assert "state=" in login_resp.headers["location"]
        assert "google_code_verifier" in login_resp.cookies

        # Extract state from redirect URL
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(login_resp.headers["location"])
        qs = parse_qs(parsed.query)
        state = qs["state"][0]
        verifier = login_resp.cookies["google_code_verifier"]

        # 2. Mock Google profile exchange
        mock_profile = GoogleUserProfile(
            provider_user_id="google-sub-98765",
            email="google.redirect@domain.com",
            email_verified=True,
            full_name="Google User Redirect",
            profile_image="https://photo.url",
        )
        monkeypatch.setattr(
            "app.infrastructure.oauth.google_client.exchange_code_for_profile",
            AsyncMock(return_value=mock_profile),
        )

        # 3. Callback with valid state and cookie
        callback_resp = await client.get(
            f"/api/auth/google/callback?code=mock_code&state={state}",
            cookies={"google_code_verifier": verifier},
            follow_redirects=False,
        )
        assert callback_resp.status_code == 302
        assert "/connect" in callback_resp.headers["location"]
        assert "access_token" in callback_resp.cookies
        assert "refresh_token" in callback_resp.cookies

        # Check user in MongoDB
        user = await mongodb_db.users.find_one({"email": "google.redirect@domain.com"})
        assert user is not None
        assert user["is_email_verified"] is True


@pytest.mark.asyncio
async def test_github_oauth_redirect_flow(mongodb_db, monkeypatch):
    """GitHub OAuth redirect flow completes login and establishes session."""
    from app.infrastructure.oauth.github_client import GithubUserProfile

    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    monkeypatch.setattr("app.core.config.settings.github_client_id", "mock-github-id")
    monkeypatch.setattr("app.core.config.settings.github_client_secret", "mock-github-secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login endpoint initiates redirect with state
        login_resp = await client.get("/api/auth/github/login", follow_redirects=False)
        assert login_resp.status_code == 302
        assert "github.com/login/oauth/authorize" in login_resp.headers["location"]

        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(login_resp.headers["location"])
        qs = parse_qs(parsed.query)
        state = qs["state"][0]

        # 2. Mock GitHub profile exchange with verified primary email
        mock_profile = GithubUserProfile(
            provider_user_id="github-uid-54321",
            email="github.redirect@domain.com",
            email_verified=True,
            full_name="GitHub Redirect User",
            profile_image="https://avatars.github.com/u/54321",
        )
        monkeypatch.setattr(
            "app.infrastructure.oauth.github_client.exchange_code_for_profile",
            AsyncMock(return_value=mock_profile),
        )

        # 3. Callback
        callback_resp = await client.get(
            f"/api/auth/github/callback?code=mock_code&state={state}",
            follow_redirects=False,
        )
        assert callback_resp.status_code == 302
        assert "/connect" in callback_resp.headers["location"]
        assert "access_token" in callback_resp.cookies
        assert "refresh_token" in callback_resp.cookies

        # Check user in MongoDB
        user = await mongodb_db.users.find_one({"email": "github.redirect@domain.com"})
        assert user is not None
        assert user["is_email_verified"] is True


@pytest.mark.asyncio
async def test_oauth_stale_mapping_resolves_and_does_not_disable_account(mongodb_db, monkeypatch):
    """An oauth_account pointing to a non-existent user_id does NOT raise AccountDisabledError, but self-heals by verified email."""
    auth_service = MongoDBAuthService(mongodb_db)

    # 1. Create user in users collection
    user = await mongodb_user_repository.create_user(
        mongodb_db,
        full_name="Javaapex Real",
        email="javaapex.stale@domain.com",
        is_email_verified=True,
    )
    real_user_id = user["_id"]

    # 2. Simulate stale oauth_accounts document pointing to old/orphaned ID 9999
    await mongodb_db.oauth_accounts.insert_one({
        "user_id": 9999,
        "provider": "google",
        "provider_user_id": "google-sub-stale-111",
        "provider_email": "javaapex.stale@domain.com",
    })

    # 3. OAuth login with this Google identity should NOT fail with AccountDisabledError, but self-heal
    authenticated_user = await auth_service.authenticate_with_oauth(
        provider="google",
        provider_user_id="google-sub-stale-111",
        email="JAVAAPEX.STALE@DOMAIN.COM",
        email_verified=True,
        full_name="Javaapex Real",
        profile_image=None,
    )
    assert authenticated_user["_id"] == real_user_id

    # Check that oauth_accounts was updated to real_user_id
    updated_oauth = await mongodb_db.oauth_accounts.find_one({
        "provider": "google",
        "provider_user_id": "google-sub-stale-111",
    })
    assert updated_oauth is not None
    assert updated_oauth["user_id"] == real_user_id


@pytest.mark.asyncio
async def test_oauth_missing_is_active_field_defaults_to_active(mongodb_db):
    """Legacy user document lacking 'is_active' field is treated as active, not disabled."""
    auth_service = MongoDBAuthService(mongodb_db)

    # Insert legacy user without is_active
    await mongodb_db.users.insert_one({
        "_id": 50,
        "full_name": "Legacy User",
        "email": "legacy.oauth@domain.com",
        "is_email_verified": True,
        # 'is_active' field is intentionally omitted
    })

    user = await auth_service.authenticate_with_oauth(
        provider="google",
        provider_user_id="google-sub-legacy-222",
        email="legacy.oauth@domain.com",
        email_verified=True,
        full_name="Legacy User",
        profile_image=None,
    )
    assert user["_id"] == 50


@pytest.mark.asyncio
async def test_oauth_genuinely_disabled_account_rejected(mongodb_db):
    """An account that is explicitly disabled (is_active=False or status='disabled') is rejected."""
    from app.core.exceptions import AccountDisabledError
    auth_service = MongoDBAuthService(mongodb_db)

    # 1. User with is_active=False
    await mongodb_db.users.insert_one({
        "_id": 51,
        "full_name": "Disabled User 1",
        "email": "disabled1@domain.com",
        "is_active": False,
        "is_email_verified": True,
    })

    with pytest.raises(AccountDisabledError):
        await auth_service.authenticate_with_oauth(
            provider="google",
            provider_user_id="google-sub-disabled-1",
            email="disabled1@domain.com",
            email_verified=True,
            full_name="Disabled User 1",
            profile_image=None,
        )

    # 2. User with status='disabled'
    await mongodb_db.users.insert_one({
        "_id": 52,
        "full_name": "Disabled User 2",
        "email": "disabled2@domain.com",
        "status": "disabled",
        "is_email_verified": True,
    })

    with pytest.raises(AccountDisabledError):
        await auth_service.authenticate_with_oauth(
            provider="google",
            provider_user_id="google-sub-disabled-2",
            email="disabled2@domain.com",
            email_verified=True,
            full_name="Disabled User 2",
            profile_image=None,
        )


@pytest.mark.asyncio
async def test_oauth_provider_not_configured_error(mongodb_db, monkeypatch):
    """When OAuth provider is not configured, /login redirects with provider_not_configured error."""
    monkeypatch.setattr("app.core.config.settings.google_client_id", "")
    monkeypatch.setattr("app.core.config.settings.google_client_secret", "")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/auth/google/login", follow_redirects=False)
        assert resp.status_code == 302
        assert "oauth_error=provider_not_configured" in resp.headers["location"]


@pytest.mark.asyncio
async def test_signup_fails_gracefully_when_smtp_delivery_fails(mongodb_db, monkeypatch):
    """When SMTP delivery fails during signup, backend returns 502 and does NOT claim email was sent."""
    from app.infrastructure.email.email_service import EmailDeliveryError

    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    mock_send_email = AsyncMock(side_effect=EmailDeliveryError("SMTP authentication failed."))
    monkeypatch.setattr("app.application.services.mongodb_auth_service.send_verification_email", mock_send_email)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/signup",
            json={
                "fullName": "SMTP Fail User",
                "email": "smtp.fail@domain.com",
                "password": "StrongPassword@123",
                "confirmPassword": "StrongPassword@123",
            },
        )
        assert response.status_code == 502
        data = response.json()
        assert "Unable to send the verification email" in data["detail"]


@pytest.mark.asyncio
async def test_resend_verification_fails_gracefully_when_smtp_delivery_fails(mongodb_db, monkeypatch):
    """When SMTP delivery fails during resend verification, backend returns 502."""
    from app.infrastructure.email.email_service import EmailDeliveryError

    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))

    # Create unverified user
    await mongodb_user_repository.create_user(
        mongodb_db,
        full_name="Resend User",
        email="resend.fail@domain.com",
        password="StrongPassword@123",
        is_email_verified=False,
    )

    mock_send_email = AsyncMock(side_effect=EmailDeliveryError("SMTP connection timed out."))
    monkeypatch.setattr("app.application.services.mongodb_auth_service.send_verification_email", mock_send_email)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/resend-verification",
            json={"email": "resend.fail@domain.com"},
        )
        assert response.status_code == 502
        data = response.json()
        assert "Unable to send the verification email" in data["detail"]


@pytest.mark.asyncio
async def test_google_oauth_signup_intent_and_error_redirect(mongodb_db, monkeypatch):
    """Google OAuth with intent=signup creates state containing intent and redirects to /signup on error."""
    from urllib.parse import parse_qs, urlparse
    from app.core import security

    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    monkeypatch.setattr("app.core.config.settings.google_client_id", "mock-google-id")
    monkeypatch.setattr("app.core.config.settings.google_client_secret", "mock-google-secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Initiate login with intent=signup
        resp = await client.get("/api/auth/google/login?intent=signup", follow_redirects=False)
        assert resp.status_code == 302
        parsed = urlparse(resp.headers["location"])
        qs = parse_qs(parsed.query)
        state = qs["state"][0]

        # Verify state payload contains intent=signup
        state_payload = security.decode_oauth_state_token(state, expected_provider="google")
        assert state_payload["intent"] == "signup"

        # 2. Simulate user cancellation / access_denied on callback
        callback_resp = await client.get(
            f"/api/auth/google/callback?error=access_denied&state={state}",
            follow_redirects=False,
        )
        assert callback_resp.status_code == 302
        # Must redirect back to /signup, NOT /signin
        assert "/signup?oauth_error=access_denied" in callback_resp.headers["location"]


@pytest.mark.asyncio
async def test_github_oauth_signup_intent_and_error_redirect(mongodb_db, monkeypatch):
    """GitHub OAuth with intent=signup creates state containing intent and redirects to /signup on error."""
    from urllib.parse import parse_qs, urlparse
    from app.core import security

    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    monkeypatch.setattr("app.core.config.settings.github_client_id", "mock-github-id")
    monkeypatch.setattr("app.core.config.settings.github_client_secret", "mock-github-secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Initiate login with intent=signup
        resp = await client.get("/api/auth/github/login?intent=signup", follow_redirects=False)
        assert resp.status_code == 302
        parsed = urlparse(resp.headers["location"])
        qs = parse_qs(parsed.query)
        state = qs["state"][0]

        # Verify state payload contains intent=signup
        state_payload = security.decode_oauth_state_token(state, expected_provider="github")
        assert state_payload["intent"] == "signup"

        # 2. Simulate user cancellation on callback
        callback_resp = await client.get(
            f"/api/auth/github/callback?error=access_denied&state={state}",
            follow_redirects=False,
        )
        assert callback_resp.status_code == 302
        # Must redirect back to /signup, NOT /signin
        assert "/signup?oauth_error=access_denied" in callback_resp.headers["location"]


@pytest.mark.asyncio
async def test_signup_requires_only_email_password_confirm(mongodb_db, monkeypatch):
    """Signup succeeds with only email, password, and confirmPassword (no fullName required)."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    monkeypatch.setattr("app.infrastructure.persistence.mongodb.get_mongodb", AsyncMock(return_value=mongodb_db))

    sent_code = None
    async def mock_send(to_email, user_name, verification_code):
        nonlocal sent_code
        sent_code = verification_code
        return True

    monkeypatch.setattr("app.application.services.mongodb_auth_service.send_verification_email", mock_send)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Signup with only email, password, confirmPassword
        signup_resp = await client.post(
            "/api/auth/signup",
            json={
                "email": "minimal.signup@example.com",
                "password": "SecurePassword@2026",
                "confirmPassword": "SecurePassword@2026",
            },
        )
        assert signup_resp.status_code == 201
        data = signup_resp.json()
        assert data["email"] == "minimal.signup@example.com"
        assert sent_code is not None

        # Verify no user in users collection before verification
        assert await mongodb_db.users.find_one({"email": "minimal.signup@example.com"}) is None
        assert await mongodb_db.pending_signups.find_one({"email": "minimal.signup@example.com"}) is not None

        # Verify code
        verify_resp = await client.post(
            "/api/auth/verify-email-code",
            json={
                "email": "minimal.signup@example.com",
                "code": sent_code,
            },
        )
        assert verify_resp.status_code == 200
        verify_data = verify_resp.json()
        assert verify_data["user"]["email"] == "minimal.signup@example.com"
        assert verify_data["user"]["isEmailVerified"] is True
        assert "access_token" in verify_resp.cookies
        assert "refresh_token" in verify_resp.cookies

        # User is authenticated and can access /api/auth/me immediately without logging in
        me_resp = await client.get("/api/auth/me", cookies=verify_resp.cookies)
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "minimal.signup@example.com"


@pytest.mark.asyncio
async def test_signup_email_format_validation(mongodb_db, monkeypatch):
    """Signup rejects invalid email formats on the backend."""
    monkeypatch.setattr("app.api.v1.endpoints.auth_controller.get_mongodb", AsyncMock(return_value=mongodb_db))
    monkeypatch.setattr("app.infrastructure.persistence.mongodb.get_mongodb", AsyncMock(return_value=mongodb_db))

    invalid_emails = [
        "abc",
        "abc@",
        "@gmail.com",
        "abc@gmail",
        "abc..test@gmail.com",
        "user @gmail.com",
        "plainaddress",
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for bad_email in invalid_emails:
            resp = await client.post(
                "/api/auth/signup",
                json={
                    "email": bad_email,
                    "password": "StrongPassword@123",
                    "confirmPassword": "StrongPassword@123",
                },
            )
            assert resp.status_code == 422, f"Expected 422 for invalid email: {bad_email}, got {resp.status_code}"







