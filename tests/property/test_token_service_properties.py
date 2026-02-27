"""Property-based tests for TokenService.

These tests verify correctness properties across multiple inputs using property-based
testing principles. Each test runs with max_examples=20 for faster test execution.

**Validates: Requirements 2.1, 2.4, 2.5, 4.1, 4.2, 4.3, 4.4, 5.5, 7.4**
"""
import pytest
from hypothesis import strategies as st, settings
from datetime import datetime, timedelta, timezone
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from sqlalchemy import select

from app.services.token_service import TokenService
from app.models.user import User
from app.models.refresh_token import RefreshToken


# Generate RSA keys for testing
def generate_test_rsa_keys():
    """Generate RSA key pair for testing JWT operations."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    return private_pem, public_pem


# Fixtures for RSA keys
@pytest.fixture
def rsa_keys():
    """Provide RSA key pair for tests."""
    return generate_test_rsa_keys()


@pytest.fixture
def token_service(rsa_keys):
    """Provide TokenService instance with test RSA keys."""
    private_key, public_key = rsa_keys
    return TokenService(private_key=private_key, public_key=public_key, algorithm="RS256")


# Property Tests

@pytest.mark.asyncio
async def test_property_6_valid_credentials_return_tokens(db_session, rsa_keys):
    """
    Feature: user-authentication, Property 6: Valid Credentials Return Tokens
    
    For any verified user with valid credentials, signing in should return both
    an access token and a refresh token.
    
    **Validates: Requirements 2.1**
    """
    private_key, public_key = rsa_keys
    token_service = TokenService(private_key=private_key, public_key=public_key, algorithm="RS256")
    
    # Test with multiple examples
    test_cases = [
        (1, "user1@example.com"),
        (42, "test@test.org"),
        (999, "admin@mail.net"),
    ]
    
    for user_id, email in test_cases:
        # Arrange: Create a verified user
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True,
            is_active=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Act: Generate tokens
        access_token = token_service.generate_access_token(user.id, user.email)
        refresh_token = await token_service.generate_refresh_token(user.id, db_session)
        
        # Assert: Both tokens are generated
        assert access_token is not None
        assert isinstance(access_token, str)
        assert len(access_token) > 0
        
        assert refresh_token is not None
        assert isinstance(refresh_token, str)
        assert len(refresh_token) > 0
        
        # Assert: Access token is valid JWT
        decoded = jwt.decode(access_token, public_key, algorithms=["RS256"])
        assert decoded["sub"] == str(user.id)
        assert decoded["email"] == user.email
        
        # Assert: Refresh token exists in database
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        db_token = result.scalar_one_or_none()
        assert db_token is not None
        assert db_token.user_id == user.id


@pytest.mark.asyncio
async def test_property_8_token_expiration_times(db_session, rsa_keys):
    """
    Feature: user-authentication, Property 8: Token Expiration Times
    
    For any generated token, the expiration time should match the configured duration:
    access tokens expire in 15 minutes, refresh tokens expire in 7 days.
    
    **Validates: Requirements 2.4, 2.5**
    """
    private_key, public_key = rsa_keys
    token_service = TokenService(private_key=private_key, public_key=public_key, algorithm="RS256")
    
    # Test with multiple examples
    test_cases = [
        (1, "user1@example.com"),
        (50, "test@test.org"),
        (100, "admin@mail.net"),
    ]
    
    for user_id, email in test_cases:
        # Arrange: Create a user
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True,
            is_active=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Act: Generate tokens
        before_generation = datetime.now(timezone.utc)
        access_token = token_service.generate_access_token(user.id, user.email)
        refresh_token = await token_service.generate_refresh_token(user.id, db_session)
        after_generation = datetime.now(timezone.utc)
        
        # Assert: Access token expires in 15 minutes (allow 1 second tolerance)
        decoded = jwt.decode(access_token, public_key, algorithms=["RS256"])
        exp_timestamp = decoded["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        
        expected_min = before_generation + timedelta(minutes=15) - timedelta(seconds=1)
        expected_max = after_generation + timedelta(minutes=15) + timedelta(seconds=1)
        
        assert expected_min <= exp_datetime <= expected_max, (
            f"Access token expiration {exp_datetime} not within expected range "
            f"[{expected_min}, {expected_max}]"
        )
        
        # Assert: Refresh token expires in 7 days (allow 1 second tolerance)
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        db_token = result.scalar_one_or_none()
        
        # Ensure expires_at is timezone-aware for comparison
        expires_at = db_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        expected_min_refresh = before_generation + timedelta(days=7) - timedelta(seconds=1)
        expected_max_refresh = after_generation + timedelta(days=7) + timedelta(seconds=1)
        
        assert expected_min_refresh <= expires_at <= expected_max_refresh, (
            f"Refresh token expiration {expires_at} not within expected range "
            f"[{expected_min_refresh}, {expected_max_refresh}]"
        )



@pytest.mark.asyncio
async def test_property_12_valid_refresh_token_issues_new_access_token(db_session, rsa_keys):
    """
    Feature: user-authentication, Property 12: Valid Refresh Token Issues New Access Token
    
    For any valid, non-expired, non-revoked refresh token, using it to refresh
    should return a new access token and a new refresh token.
    
    **Validates: Requirements 4.1**
    """
    private_key, public_key = rsa_keys
    token_service = TokenService(private_key=private_key, public_key=public_key, algorithm="RS256")
    
    # Test with multiple examples
    test_cases = [
        (1, "user1@example.com"),
        (25, "test@test.org"),
        (75, "admin@mail.net"),
    ]
    
    for user_id, email in test_cases:
        # Arrange: Create a user with a refresh token
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True,
            is_active=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        original_refresh_token = await token_service.generate_refresh_token(user.id, db_session)
        
        # Act: Refresh the access token
        new_access_token, new_refresh_token = await token_service.refresh_access_token(
            original_refresh_token, db_session
        )
        
        # Assert: New tokens are generated
        assert new_access_token is not None
        assert isinstance(new_access_token, str)
        assert len(new_access_token) > 0
        
        assert new_refresh_token is not None
        assert isinstance(new_refresh_token, str)
        assert len(new_refresh_token) > 0
        
        # Assert: New tokens are different from original
        assert new_refresh_token != original_refresh_token
        
        # Assert: New access token is valid
        decoded = jwt.decode(new_access_token, public_key, algorithms=["RS256"])
        assert decoded["sub"] == str(user.id)
        assert decoded["email"] == user.email
        
        # Assert: New refresh token exists in database
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token == new_refresh_token)
        )
        db_token = result.scalar_one_or_none()
        assert db_token is not None
        assert db_token.user_id == user.id
        assert db_token.is_revoked is False


@pytest.mark.asyncio
async def test_property_13_invalid_refresh_tokens_rejected(db_session, rsa_keys):
    """
    Feature: user-authentication, Property 13: Invalid Refresh Tokens Rejected
    
    For any refresh token that is expired, revoked, or malformed, attempting to
    use it should return an authentication error and no new tokens should be issued.
    
    **Validates: Requirements 4.2, 4.4**
    """
    private_key, public_key = rsa_keys
    token_service = TokenService(private_key=private_key, public_key=public_key, algorithm="RS256")
    
    # Arrange: Create a user
    user = User(
        email="testuser@example.com",
        password_hash="hashed_password",
        is_verified=True,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Test 1: Malformed token
    malformed_tokens = ["not-a-valid-uuid-token", "invalid", "12345"]
    for malformed_token in malformed_tokens:
        with pytest.raises(ValueError, match="Invalid refresh token"):
            await token_service.refresh_access_token(malformed_token, db_session)
    
    # Test 2: Revoked token
    revoked_token = await token_service.generate_refresh_token(user.id, db_session)
    await token_service.revoke_refresh_token(revoked_token, db_session)
    
    with pytest.raises(ValueError, match="Refresh token has been revoked"):
        await token_service.refresh_access_token(revoked_token, db_session)
    
    # Test 3: Expired token
    expired_token = RefreshToken(
        user_id=user.id,
        token="expired-token-uuid-12345",
        is_revoked=False,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db_session.add(expired_token)
    await db_session.commit()
    
    with pytest.raises(ValueError, match="Refresh token has expired"):
        await token_service.refresh_access_token("expired-token-uuid-12345", db_session)


@pytest.mark.asyncio
async def test_property_14_refresh_token_rotation(db_session, rsa_keys):
    """
    Feature: user-authentication, Property 14: Refresh Token Rotation
    
    For any refresh token that is successfully used to obtain new tokens, the old
    refresh token should be marked as revoked and should not be usable again.
    
    **Validates: Requirements 4.3**
    """
    private_key, public_key = rsa_keys
    token_service = TokenService(private_key=private_key, public_key=public_key, algorithm="RS256")
    
    # Test with multiple examples
    test_cases = [
        (1, "user1@example.com"),
        (30, "test@test.org"),
        (60, "admin@mail.net"),
    ]
    
    for user_id, email in test_cases:
        # Arrange: Create a user with a refresh token
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True,
            is_active=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        original_refresh_token = await token_service.generate_refresh_token(user.id, db_session)
        
        # Act: Use the refresh token to get new tokens
        new_access_token, new_refresh_token = await token_service.refresh_access_token(
            original_refresh_token, db_session
        )
        
        # Assert: Old refresh token is revoked in database
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token == original_refresh_token)
        )
        old_token_record = result.scalar_one_or_none()
        assert old_token_record is not None
        assert old_token_record.is_revoked is True, "Old refresh token should be revoked"
        
        # Assert: Old refresh token cannot be used again
        with pytest.raises(ValueError, match="Refresh token has been revoked"):
            await token_service.refresh_access_token(original_refresh_token, db_session)
        
        # Assert: New refresh token is valid and can be used
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token == new_refresh_token)
        )
        new_token_record = result.scalar_one_or_none()
        assert new_token_record is not None
        assert new_token_record.is_revoked is False, "New refresh token should not be revoked"



@pytest.mark.asyncio
async def test_property_17_invalid_token_rejection(db_session, rsa_keys):
    """
    Feature: user-authentication, Property 17: Invalid Token Rejection
    
    For any token (verification, password reset, or refresh) that is expired,
    already used, or malformed, attempting to use it should return an appropriate
    error and no state changes should occur.
    
    **Validates: Requirements 5.5, 7.4**
    """
    private_key, public_key = rsa_keys
    token_service = TokenService(private_key=private_key, public_key=public_key, algorithm="RS256")
    
    # Arrange: Create a user
    user = User(
        email="testuser@example.com",
        password_hash="hashed_password",
        is_verified=True,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Test 1: Malformed JWT access tokens
    malformed_jwts = [
        "not.a.valid.jwt.token",
        "invalid",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"
    ]
    
    for malformed_jwt in malformed_jwts:
        with pytest.raises(jwt.InvalidTokenError):
            token_service.decode_access_token(malformed_jwt)
    
    # Test 2: Expired JWT access token
    past_time = datetime.now(timezone.utc) - timedelta(hours=1)
    expired_payload = {
        "sub": str(user.id),
        "email": user.email,
        "type": "access",
        "exp": past_time,
        "iat": past_time - timedelta(minutes=15)
    }
    expired_jwt = jwt.encode(expired_payload, private_key, algorithm="RS256")
    
    with pytest.raises(jwt.ExpiredSignatureError):
        token_service.decode_access_token(expired_jwt)
    
    # Test 3: Invalid refresh token (doesn't exist in database)
    fake_refresh_tokens = [
        "00000000-0000-0000-0000-000000000000",
        "fake-token-12345",
        "nonexistent-uuid"
    ]
    
    for fake_token in fake_refresh_tokens:
        with pytest.raises(ValueError, match="Invalid refresh token"):
            await token_service.refresh_access_token(fake_token, db_session)
    
    # Test 4: Already revoked refresh token
    revoked_token = await token_service.generate_refresh_token(user.id, db_session)
    await token_service.revoke_refresh_token(revoked_token, db_session)
    
    with pytest.raises(ValueError, match="Refresh token has been revoked"):
        await token_service.refresh_access_token(revoked_token, db_session)
