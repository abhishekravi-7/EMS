from unittest.mock import AsyncMock
import pytest
from app.application.services.mongodb_auth_service import MongoDBAuthService
from app.core.exceptions import AuthenticationError

@pytest.mark.asyncio
async def test_mongodb_signup_login_flow(mongodb_db, monkeypatch):
    captured_code = None
    async def mock_email(to_email, user_name, verification_code):
        nonlocal captured_code
        captured_code = verification_code
        return True

    monkeypatch.setattr("app.application.services.mongodb_auth_service.send_verification_email", mock_email)

    auth_service = MongoDBAuthService(mongodb_db)
    
    email = "test_mongo@example.com"
    password = "StrongPassword@123"
    full_name = "Mongo User"
    
    # 1. Signup creates pending record and sends code (users collection remains empty)
    result = await auth_service.signup(full_name, email, password)
    assert result["email"] == email
    assert await mongodb_db.users.find_one({"email": email}) is None
    pending = await mongodb_db.pending_signups.find_one({"email": email})
    assert pending is not None
    assert pending["full_name"] == full_name
    assert "password_hash" in pending
    
    # 2. Duplicate Signup before verification is rejected or updates code
    # (if verified user exists, it is rejected)
    assert captured_code is not None

    # Verify code to create user in users collection
    user = await auth_service.verify_email_code(email, captured_code)
    assert user["email"] == email
    assert user["is_email_verified"] is True
    assert await mongodb_db.pending_signups.find_one({"email": email}) is None

    # Duplicate signup now that user is registered must be rejected
    with pytest.raises((AuthenticationError, Exception)):
        await auth_service.signup(full_name, email, password)

    # 3. Login
    logged_in_user, access_token, refresh_token = await auth_service.login(email, password)
    assert logged_in_user["_id"] == user["_id"]
    assert access_token is not None
    assert refresh_token is not None
    
    # 4. Login Wrong Password
    with pytest.raises(AuthenticationError):
        await auth_service.login(email, "WrongPassword@123")
        
    # 5. Refresh
    new_access, new_refresh = await auth_service.refresh_tokens(refresh_token)
    assert new_access is not None
    assert new_refresh is not None
    assert new_access != access_token
    
    # 6. Logout
    await auth_service.logout(new_refresh)
    
    # 7. Refresh after logout (should fail)
    from app.core.exceptions import NotAuthenticatedError
    with pytest.raises(NotAuthenticatedError):
        await auth_service.refresh_tokens(new_refresh)

