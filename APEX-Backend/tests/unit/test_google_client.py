import pytest
import respx
from httpx import Response
from app.infrastructure.oauth import google_client
from app.core.exceptions import OAuthProviderError

@pytest.mark.asyncio
async def test_build_authorization_url():
    url = google_client.build_authorization_url(state="test_state", code_challenge="test_challenge")
    assert "https://accounts.google.com/o/oauth2/v2/auth" in url
    assert "state=test_state" in url
    assert "code_challenge=test_challenge" in url
    assert "scope=openid+email+profile" in url

@pytest.mark.asyncio
@respx.mock
async def test_exchange_code_for_profile_success():
    # Mock token exchange
    respx.post("https://oauth2.googleapis.com/token").mock(return_value=Response(
        200, json={"access_token": "mock_access_token"}
    ))

    # Mock userinfo fetch
    respx.get("https://openidconnect.googleapis.com/v1/userinfo").mock(return_value=Response(
        200, json={
            "sub": "google_123",
            "email": "test@example.com",
            "email_verified": True,
            "name": "Test User",
            "picture": "http://example.com/pic.jpg"
        }
    ))

    profile = await google_client.exchange_code_for_profile(code="test_code", code_verifier="test_verifier")

    assert profile.provider_user_id == "google_123"
    assert profile.email == "test@example.com"
    assert profile.email_verified is True
    assert profile.full_name == "Test User"
    assert profile.profile_image == "http://example.com/pic.jpg"

@pytest.mark.asyncio
@respx.mock
async def test_exchange_code_for_profile_token_failure():
    respx.post("https://oauth2.googleapis.com/token").mock(return_value=Response(400))

    with pytest.raises(OAuthProviderError):
        await google_client.exchange_code_for_profile(code="bad_code", code_verifier="v")

@pytest.mark.asyncio
@respx.mock
async def test_exchange_code_for_profile_userinfo_failure():
    respx.post("https://oauth2.googleapis.com/token").mock(return_value=Response(
        200, json={"access_token": "mock_access_token"}
    ))
    respx.get("https://openidconnect.googleapis.com/v1/userinfo").mock(return_value=Response(401))

    with pytest.raises(OAuthProviderError):
        await google_client.exchange_code_for_profile(code="c", code_verifier="v")
