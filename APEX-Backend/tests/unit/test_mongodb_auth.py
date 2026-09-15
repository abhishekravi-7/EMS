import pytest
from app.application.services.mongodb_auth_service import MongoDBAuthService
from app.core.exceptions import AuthenticationError

@pytest.mark.asyncio
async def test_mongodb_signup_login_flow(mongodb_db):
    auth_service = MongoDBAuthService(mongodb_db)
    
    email = "test_mongo@example.com"
    password = "StrongPassword@123"
    full_name = "Mongo User"
    
    # 1. Signup
    user = await auth_service.signup(full_name, email, password)
    assert user["email"] == email
    assert user["full_name"] == full_name
    assert "password_hash" in user
    assert user["password_hash"] != password
    
    # 2. Duplicate Signup
    with pytest.raises(AuthenticationError):
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
    # Note: refresh_tokens implementation should fail if session not found
    from app.core.exceptions import NotAuthenticatedError
    with pytest.raises(NotAuthenticatedError):
        await auth_service.refresh_tokens(new_refresh)
