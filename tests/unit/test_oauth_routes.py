"""Unit tests for OAuth authentication routes.

Tests OAuth flow with mocked provider responses, new user creation,
existing user linking, and error handling for provider failures.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from app.models.user import User
from app.models.oauth_account import OAuthAccount
from app.services.oauth_service import OAuthService


@pytest.mark.asyncio
async def test_oauth_login_google_redirect(test_client: AsyncClient):
    """Test OAuth login initiates redirect to Google."""
    response = await test_client.get(
        "/auth/oauth/google",
        follow_redirects=False
    )
    
    assert response.status_code == 302
    assert "Location" in response.headers
    location = response.headers["Location"]
    assert "accounts.google.com" in location
    assert "client_id" in location
    assert "redirect_uri" in location
    assert "scope" in location
    assert "state" in location


@pytest.mark.asyncio
async def test_oauth_login_github_redirect(test_client: AsyncClient):
    """Test OAuth login initiates redirect to GitHub."""
    response = await test_client.get(
        "/auth/oauth/github",
        follow_redirects=False
    )
    
    assert response.status_code == 302
    assert "Location" in response.headers
    location = response.headers["Location"]
    assert "github.com" in location
    assert "client_id" in location
    assert "redirect_uri" in location
    assert "scope" in location
    assert "state" in location


@pytest.mark.asyncio
async def test_oauth_login_unsupported_provider(test_client: AsyncClient):
    """Test OAuth login with unsupported provider returns error."""
    response = await test_client.get(
        "/auth/oauth/facebook",
        follow_redirects=False
    )
    
    assert response.status_code == 400
    assert "unsupported" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_oauth_callback_creates_new_user(test_client: AsyncClient, db_session: AsyncSession):
    """Test OAuth callback creates new user for first-time OAuth login."""
    # Create a mock user to return
    mock_user = User(
        id=1,
        email="newuser@example.com",
        full_name="New OAuth User",
        is_verified=True,
        is_active=True
    )
    
    # Mock OAuth service
    mock_oauth_service = MagicMock()
    mock_oauth_service.exchange_code_for_token = AsyncMock(return_value={
        "access_token": "mock_access_token",
        "refresh_token": "mock_refresh_token",
        "expires_in": 3600
    })
    mock_oauth_service.get_user_info = AsyncMock(return_value={
        "provider_user_id": "google_123456",
        "email": "newuser@example.com",
        "name": "New OAuth User",
        "verified_email": True
    })
    mock_oauth_service.authenticate_or_create_user = AsyncMock(return_value=mock_user)
    
    with patch('app.api.oauth.get_oauth_service', return_value=mock_oauth_service):
        response = await test_client.get(
            "/auth/oauth/google/callback?code=test_code&state=test_state"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 900


@pytest.mark.asyncio
async def test_oauth_callback_links_existing_user(test_client: AsyncClient, db_session: AsyncSession):
    """Test OAuth callback links OAuth account to existing user with same email."""
    # Create existing user with password
    from app.services.auth_service import AuthService
    auth_service = AuthService()
    existing_user = await auth_service.create_user(
        email="existing@example.com",
        password="ExistingPass123",
        db=db_session
    )
    await db_session.commit()
    
    # Mock OAuth service
    mock_oauth_service = MagicMock()
    mock_oauth_service.exchange_code_for_token = AsyncMock(return_value={
        "access_token": "mock_access_token",
        "expires_in": 3600
    })
    mock_oauth_service.get_user_info = AsyncMock(return_value={
        "provider_user_id": "google_789012",
        "email": "existing@example.com",
        "name": "Existing User",
        "verified_email": True
    })
    mock_oauth_service.authenticate_or_create_user = AsyncMock(return_value=existing_user)
    
    with patch('app.api.oauth.get_oauth_service', return_value=mock_oauth_service):
        response = await test_client.get(
            "/auth/oauth/google/callback?code=test_code&state=test_state"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data


@pytest.mark.asyncio
async def test_oauth_callback_returns_existing_oauth_user(test_client: AsyncClient, db_session: AsyncSession):
    """Test OAuth callback returns tokens for existing OAuth user."""
    # Create user with OAuth account
    user = User(
        email="oauth@example.com",
        full_name="OAuth User",
        password_hash=None,
        is_verified=True,
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()
    
    oauth_account = OAuthAccount(
        user_id=user.id,
        provider="github",
        provider_user_id="github_456789",
        access_token="old_token",
        refresh_token="old_refresh"
    )
    db_session.add(oauth_account)
    await db_session.commit()
    
    # Mock OAuth service
    mock_oauth_service = MagicMock()
    mock_oauth_service.exchange_code_for_token = AsyncMock(return_value={
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_in": 3600
    })
    mock_oauth_service.get_user_info = AsyncMock(return_value={
        "provider_user_id": "github_456789",
        "email": "oauth@example.com",
        "name": "OAuth User",
        "verified_email": True
    })
    mock_oauth_service.authenticate_or_create_user = AsyncMock(return_value=user)
    
    with patch('app.api.oauth.get_oauth_service', return_value=mock_oauth_service):
        response = await test_client.get(
            "/auth/oauth/github/callback?code=test_code&state=test_state"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data


@pytest.mark.asyncio
async def test_oauth_callback_missing_code(test_client: AsyncClient):
    """Test OAuth callback without authorization code returns error."""
    response = await test_client.get(
        "/auth/oauth/google/callback"
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_oauth_callback_provider_token_error(test_client: AsyncClient, db_session: AsyncSession):
    """Test OAuth callback handles provider token exchange error."""
    # Mock OAuth service to raise error during token exchange
    with patch.object(OAuthService, 'exchange_code_for_token', new_callable=AsyncMock) as mock_exchange:
        mock_exchange.side_effect = ValueError("Invalid authorization code")
        
        response = await test_client.get(
            "/auth/oauth/google/callback?code=invalid_code&state=test_state"
        )
        
        assert response.status_code == 400
        assert "OAuth authentication failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_oauth_callback_provider_userinfo_error(test_client: AsyncClient, db_session: AsyncSession):
    """Test OAuth callback handles provider user info retrieval error."""
    # Mock OAuth service methods
    mock_token_response = {
        "access_token": "mock_access_token",
        "expires_in": 3600
    }
    
    with patch.object(OAuthService, 'exchange_code_for_token', new_callable=AsyncMock) as mock_exchange, \
         patch.object(OAuthService, 'get_user_info', new_callable=AsyncMock) as mock_get_info:
        
        mock_exchange.return_value = mock_token_response
        mock_get_info.side_effect = Exception("Failed to fetch user info")
        
        response = await test_client.get(
            "/auth/oauth/google/callback?code=test_code&state=test_state"
        )
        
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]


@pytest.mark.asyncio
async def test_oauth_callback_missing_access_token(test_client: AsyncClient, db_session: AsyncSession):
    """Test OAuth callback handles missing access token in provider response."""
    # Mock OAuth service
    mock_oauth_service = MagicMock()
    mock_oauth_service.exchange_code_for_token = AsyncMock(return_value={
        "error": "invalid_grant"
    })
    
    with patch('app.api.oauth.get_oauth_service', return_value=mock_oauth_service):
        response = await test_client.get(
            "/auth/oauth/google/callback?code=test_code&state=test_state"
        )
        
        assert response.status_code == 400
        assert "Failed to obtain access token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_oauth_callback_missing_user_info(test_client: AsyncClient, db_session: AsyncSession):
    """Test OAuth callback handles incomplete user info from provider."""
    # Mock OAuth service
    mock_oauth_service = MagicMock()
    mock_oauth_service.exchange_code_for_token = AsyncMock(return_value={
        "access_token": "mock_access_token",
        "expires_in": 3600
    })
    # Missing email in user info
    mock_oauth_service.get_user_info = AsyncMock(return_value={
        "provider_user_id": "google_123456",
        "name": "User Without Email"
    })
    
    with patch('app.api.oauth.get_oauth_service', return_value=mock_oauth_service):
        response = await test_client.get(
            "/auth/oauth/google/callback?code=test_code&state=test_state"
        )
        
        assert response.status_code == 400
        assert "Failed to obtain user information" in response.json()["detail"]


@pytest.mark.asyncio
async def test_oauth_callback_github_provider(test_client: AsyncClient, db_session: AsyncSession):
    """Test OAuth callback works with GitHub provider."""
    # Create a mock user
    mock_user = User(
        id=1,
        email="github@example.com",
        full_name="GitHub User",
        is_verified=True,
        is_active=True
    )
    
    # Mock OAuth service
    mock_oauth_service = MagicMock()
    mock_oauth_service.exchange_code_for_token = AsyncMock(return_value={
        "access_token": "github_access_token",
        "expires_in": 28800
    })
    mock_oauth_service.get_user_info = AsyncMock(return_value={
        "provider_user_id": "github_999888",
        "email": "github@example.com",
        "name": "GitHub User",
        "verified_email": True
    })
    mock_oauth_service.authenticate_or_create_user = AsyncMock(return_value=mock_user)
    
    with patch('app.api.oauth.get_oauth_service', return_value=mock_oauth_service):
        response = await test_client.get(
            "/auth/oauth/github/callback?code=github_code&state=test_state"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
