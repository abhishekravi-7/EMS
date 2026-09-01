import pytest
import respx
from httpx import Response

from app.core.exceptions import OAuthProviderError
from app.infrastructure.oauth import github_client


@pytest.mark.asyncio
async def test_build_authorization_url():
    url = github_client.build_authorization_url(state="test_state")
    assert "https://github.com/login/oauth/authorize" in url
    assert "state=test_state" in url
    assert "scope=read%3Auser+user%3Aemail" in url

@pytest.mark.asyncio
@respx.mock
async def test_exchange_code_for_profile_public_email():
    # Mock token exchange
    respx.post("https://github.com/login/oauth/access_token").mock(return_value=Response(
        200, json={"access_token": "mock_gh_token"}
    ))

    # Mock user profile with public email
    respx.get("https://api.github.com/user").mock(return_value=Response(
        200, json={
            "id": 456,
            "login": "ghuser",
            "name": "Github User",
            "email": "gh@example.com",
            "avatar_url": "http://example.com/gh.jpg"
        }
    ))

    profile = await github_client.exchange_code_for_profile(code="gh_code")

    assert profile.provider_user_id == "456"
    assert profile.email == "gh@example.com"
    assert profile.email_verified is True
    assert profile.full_name == "Github User"
    assert profile.profile_image == "http://example.com/gh.jpg"

@pytest.mark.asyncio
@respx.mock
async def test_exchange_code_for_profile_private_email():
    # Mock token exchange
    respx.post("https://github.com/login/oauth/access_token").mock(return_value=Response(
        200, json={"access_token": "mock_gh_token"}
    ))

    # Mock user profile without public email
    respx.get("https://api.github.com/user").mock(return_value=Response(
        200, json={
            "id": 789,
            "login": "privateuser",
            "email": None,
            "avatar_url": "http://example.com/p.jpg"
        }
    ))

    # Mock emails API
    respx.get("https://api.github.com/user/emails").mock(return_value=Response(
        200, json=[
            {"email": "other@example.com", "primary": False, "verified": True},
            {"email": "primary@example.com", "primary": True, "verified": True}
        ]
    ))

    profile = await github_client.exchange_code_for_profile(code="gh_code")

    assert profile.provider_user_id == "789"
    assert profile.email == "primary@example.com"
    assert profile.email_verified is True

@pytest.mark.asyncio
@respx.mock
async def test_exchange_code_for_profile_failure():
    respx.post("https://github.com/login/oauth/access_token").mock(return_value=Response(401))

    with pytest.raises(OAuthProviderError):
        await github_client.exchange_code_for_profile(code="bad_code")
