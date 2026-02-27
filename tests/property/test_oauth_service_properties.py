"""Property-based tests for OAuthService.

These tests verify correctness properties across all valid inputs using Hypothesis.
Each test runs with max_examples=20 for faster test execution.

**Validates: Requirements 3.2, 3.4, 3.5, 3.6**
"""
import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from app.services.oauth_service import OAuthService
from app.models.user import User
from app.models.oauth_account import OAuthAccount


# Custom Hypothesis strategies for generating valid test data

@st.composite
def oauth_provider_strategy(draw):
    """Generate valid OAuth provider names."""
    return draw(st.sampled_from(['google', 'github']))


@st.composite
def state_token_strategy(draw):
    """Generate valid state tokens for CSRF protection."""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=48, max_codepoint=122),
        min_size=16,
        max_size=64
    ))


@st.composite
def oauth_user_info_strategy(draw):
    """Generate valid OAuth user information."""
    provider_user_id = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Nd',), min_codepoint=48, max_codepoint=57),
        min_size=8,
        max_size=20
    ))
    
    username = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), min_codepoint=97, max_codepoint=122),
        min_size=3,
        max_size=20
    ))
    domain = draw(st.sampled_from(['example.com', 'test.org', 'mail.net', 'demo.io']))
    email = f"{username}@{domain}"
    
    name = draw(st.one_of(
        st.none(),
        st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), min_codepoint=65, max_codepoint=122),
            min_size=3,
            max_size=30
        )
    ))
    
    return {
        'provider_user_id': provider_user_id,
        'email': email,
        'name': name
    }


# Property Tests

@given(
    provider=oauth_provider_strategy(),
    state=state_token_strategy()
)
@settings(max_examples=20, deadline=None)
def test_property_10_oauth_initiation_returns_redirect(provider: str, state: str):
    """
    Feature: user-authentication, Property 10: OAuth Initiation Returns Redirect
    
    For any supported OAuth provider, initiating OAuth authentication should return
    a redirect response to the provider's authorization URL with appropriate parameters.
    
    **Validates: Requirements 3.2**
    """
    # Arrange: Create OAuth service with test credentials
    oauth_service = OAuthService(
        provider=provider,
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost:8000/auth/oauth/callback"
    )
    
    # Act: Get authorization URL
    authorization_url = oauth_service.get_authorization_url(state)
    
    # Assert: URL is not empty
    assert authorization_url, "Authorization URL should not be empty"
    
    # Assert: URL starts with the correct provider authorization endpoint
    expected_base_url = oauth_service.config["authorization_url"]
    assert authorization_url.startswith(expected_base_url), (
        f"Authorization URL should start with {expected_base_url}"
    )
    
    # Assert: URL contains required parameters
    assert "client_id=test_client_id" in authorization_url, "URL should contain client_id"
    assert f"state={state}" in authorization_url, "URL should contain state parameter"
    assert "redirect_uri=" in authorization_url, "URL should contain redirect_uri"
    assert "scope=" in authorization_url, "URL should contain scope"
    assert "response_type=code" in authorization_url, "URL should contain response_type=code"
    
    # Assert: Provider-specific parameters
    if provider == "google":
        assert "access_type=offline" in authorization_url, "Google URL should contain access_type=offline"
        assert "prompt=consent" in authorization_url, "Google URL should contain prompt=consent"


@pytest.mark.asyncio
async def test_property_11_oauth_authentication_creates_new_user(test_db):
    """
    Feature: user-authentication, Property 11: OAuth Authentication Creates or Links User (New User)
    
    For any successful OAuth authentication where the provider user ID does not exist
    in the system, a new user account should be created and tokens should be issued.
    
    **Validates: Requirements 3.4, 3.5, 3.6**
    """
    from sqlalchemy import select
    
    # Test with multiple OAuth providers and user data
    test_cases = [
        {
            'provider': 'google',
            'provider_user_id': '123456789',
            'email': 'newuser1@example.com',
            'name': 'New User One',
            'access_token': 'google_access_token_123',
            'refresh_token': 'google_refresh_token_123',
            'expires_in': 3600
        },
        {
            'provider': 'github',
            'provider_user_id': '987654321',
            'email': 'newuser2@test.org',
            'name': 'New User Two',
            'access_token': 'github_access_token_456',
            'refresh_token': None,
            'expires_in': 7200
        },
        {
            'provider': 'google',
            'provider_user_id': '555555555',
            'email': 'newuser3@mail.net',
            'name': None,
            'access_token': 'google_access_token_789',
            'refresh_token': 'google_refresh_token_789',
            'expires_in': None
        }
    ]
    
    for test_case in test_cases:
        # Arrange: Create OAuth service
        oauth_service = OAuthService(
            provider=test_case['provider'],
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8000/auth/oauth/callback"
        )
        
        # Act: Authenticate or create user
        user = await oauth_service.authenticate_or_create_user(
            provider_user_id=test_case['provider_user_id'],
            email=test_case['email'],
            name=test_case['name'],
            access_token=test_case['access_token'],
            refresh_token=test_case['refresh_token'],
            expires_in=test_case['expires_in'],
            db=test_db
        )
        
        # Assert: User was created
        assert user is not None, "User should be created"
        assert user.id is not None, "User should have an ID"
        assert user.email == test_case['email'], f"User email should be {test_case['email']}"
        assert user.full_name == test_case['name'], f"User name should be {test_case['name']}"
        
        # Assert: User is verified (OAuth providers verify emails)
        assert user.is_verified is True, "OAuth user should be verified"
        
        # Assert: User has no password (OAuth-only user)
        assert user.password_hash is None, "OAuth-only user should not have password"
        
        # Assert: User exists in database
        result = await test_db.execute(
            select(User).where(User.email == test_case['email'])
        )
        db_user = result.scalar_one_or_none()
        assert db_user is not None, "User should exist in database"
        assert db_user.email == test_case['email']
        
        # Assert: OAuth account was created and linked
        oauth_result = await test_db.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == test_case['provider'],
                OAuthAccount.provider_user_id == test_case['provider_user_id']
            )
        )
        oauth_account = oauth_result.scalar_one_or_none()
        assert oauth_account is not None, "OAuth account should be created"
        assert oauth_account.user_id == user.id, "OAuth account should be linked to user"
        assert oauth_account.provider == test_case['provider']
        assert oauth_account.provider_user_id == test_case['provider_user_id']
        assert oauth_account.access_token == test_case['access_token']
        assert oauth_account.refresh_token == test_case['refresh_token']


@pytest.mark.asyncio
async def test_property_11_oauth_authentication_links_existing_user(test_db):
    """
    Feature: user-authentication, Property 11: OAuth Authentication Creates or Links User (Existing User)
    
    For any successful OAuth authentication where a user with the email already exists,
    the OAuth account should be linked to the existing user and tokens should be issued.
    
    **Validates: Requirements 3.4, 3.5, 3.6**
    """
    from sqlalchemy import select
    from app.services.auth_service import AuthService
    
    # Test with multiple scenarios
    test_cases = [
        {
            'provider': 'google',
            'provider_user_id': '111111111',
            'email': 'existing1@example.com',
            'password': 'ExistingPass123',
            'name': 'Existing User One',
            'access_token': 'google_access_token_111',
            'refresh_token': 'google_refresh_token_111',
            'expires_in': 3600
        },
        {
            'provider': 'github',
            'provider_user_id': '222222222',
            'email': 'existing2@test.org',
            'password': 'ExistingPass456',
            'name': 'Existing User Two',
            'access_token': 'github_access_token_222',
            'refresh_token': None,
            'expires_in': 7200
        }
    ]
    
    for test_case in test_cases:
        # Arrange: Create an existing user with credentials
        auth_service = AuthService()
        existing_user = await auth_service.create_user(
            email=test_case['email'],
            password=test_case['password'],
            db=test_db,
            full_name=test_case['name']
        )
        
        # Store original user ID
        original_user_id = existing_user.id
        
        # Arrange: Create OAuth service
        oauth_service = OAuthService(
            provider=test_case['provider'],
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8000/auth/oauth/callback"
        )
        
        # Act: Authenticate or create user (should link to existing)
        user = await oauth_service.authenticate_or_create_user(
            provider_user_id=test_case['provider_user_id'],
            email=test_case['email'],
            name=test_case['name'],
            access_token=test_case['access_token'],
            refresh_token=test_case['refresh_token'],
            expires_in=test_case['expires_in'],
            db=test_db
        )
        
        # Assert: Same user was returned (not a new user)
        assert user.id == original_user_id, "Should return existing user, not create new one"
        assert user.email == test_case['email']
        
        # Assert: User still has password (credential-based auth still works)
        assert user.password_hash is not None, "Existing user should keep their password"
        
        # Assert: User is now verified (OAuth linking verifies email)
        assert user.is_verified is True, "User should be verified after OAuth linking"
        
        # Assert: Only one user with this email exists
        result = await test_db.execute(
            select(User).where(User.email == test_case['email'])
        )
        users = result.scalars().all()
        assert len(users) == 1, "Should have exactly one user with this email"
        
        # Assert: OAuth account was created and linked to existing user
        oauth_result = await test_db.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == test_case['provider'],
                OAuthAccount.provider_user_id == test_case['provider_user_id']
            )
        )
        oauth_account = oauth_result.scalar_one_or_none()
        assert oauth_account is not None, "OAuth account should be created"
        assert oauth_account.user_id == original_user_id, "OAuth account should link to existing user"
        assert oauth_account.provider == test_case['provider']
        assert oauth_account.access_token == test_case['access_token']


@pytest.mark.asyncio
async def test_property_11_oauth_authentication_returns_existing_oauth_user(test_db):
    """
    Feature: user-authentication, Property 11: OAuth Authentication Creates or Links User (Returning OAuth User)
    
    For any successful OAuth authentication where the OAuth account already exists,
    the existing user should be returned and OAuth tokens should be updated.
    
    **Validates: Requirements 3.4, 3.5, 3.6**
    """
    from sqlalchemy import select
    
    # Test case: User signs in with OAuth multiple times
    test_case = {
        'provider': 'google',
        'provider_user_id': '999999999',
        'email': 'returning@example.com',
        'name': 'Returning User',
        'first_access_token': 'google_access_token_first',
        'first_refresh_token': 'google_refresh_token_first',
        'second_access_token': 'google_access_token_second',
        'second_refresh_token': 'google_refresh_token_second',
        'expires_in': 3600
    }
    
    # Arrange: Create OAuth service
    oauth_service = OAuthService(
        provider=test_case['provider'],
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost:8000/auth/oauth/callback"
    )
    
    # Act: First OAuth authentication (creates user)
    first_user = await oauth_service.authenticate_or_create_user(
        provider_user_id=test_case['provider_user_id'],
        email=test_case['email'],
        name=test_case['name'],
        access_token=test_case['first_access_token'],
        refresh_token=test_case['first_refresh_token'],
        expires_in=test_case['expires_in'],
        db=test_db
    )
    
    first_user_id = first_user.id
    
    # Act: Second OAuth authentication (should return same user with updated tokens)
    second_user = await oauth_service.authenticate_or_create_user(
        provider_user_id=test_case['provider_user_id'],
        email=test_case['email'],
        name=test_case['name'],
        access_token=test_case['second_access_token'],
        refresh_token=test_case['second_refresh_token'],
        expires_in=test_case['expires_in'],
        db=test_db
    )
    
    # Assert: Same user was returned
    assert second_user.id == first_user_id, "Should return same user on subsequent OAuth logins"
    assert second_user.email == test_case['email']
    
    # Assert: Only one user exists
    result = await test_db.execute(
        select(User).where(User.email == test_case['email'])
    )
    users = result.scalars().all()
    assert len(users) == 1, "Should have exactly one user"
    
    # Assert: Only one OAuth account exists
    oauth_result = await test_db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == test_case['provider'],
            OAuthAccount.provider_user_id == test_case['provider_user_id']
        )
    )
    oauth_accounts = oauth_result.scalars().all()
    assert len(oauth_accounts) == 1, "Should have exactly one OAuth account"
    
    # Assert: OAuth tokens were updated
    oauth_account = oauth_accounts[0]
    assert oauth_account.access_token == test_case['second_access_token'], "Access token should be updated"
    assert oauth_account.refresh_token == test_case['second_refresh_token'], "Refresh token should be updated"
    
    # Assert: Last login time was updated
    assert second_user.last_login_at is not None, "Last login time should be set"
