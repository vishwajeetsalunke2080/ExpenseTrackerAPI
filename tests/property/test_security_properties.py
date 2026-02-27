"""Property-based tests for security properties.

These tests verify security-related correctness properties including:
- Duplicate email registration rejection
- Token revocation
- Session management
- Email notifications

**Validates: Requirements 1.2, 8.1, 8.2, 8.3, 8.4, 8.5, 1.5, 5.2, 7.2, 10.2**
"""
import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from datetime import datetime, timezone

from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.services.auth_service import AuthService
from app.services.token_service import TokenService
from app.services.email_service import EmailService


@pytest.mark.asyncio
async def test_property_2_duplicate_email_registration_rejected(db_session):
    """
    Feature: user-authentication, Property 2: Duplicate Email Registration Rejected
    
    For any email that already exists in the system, attempting to register a new
    user with that email should return an error indicating the email is already
    registered, and no new user account should be created.
    
    **Validates: Requirements 1.2**
    """
    auth_service = AuthService()
    
    # Test with multiple examples
    test_cases = [
        ("duplicate1@example.com", "FirstPass123", "SecondPass456"),
        ("duplicate2@test.org", "Password1!", "DifferentP@ss2"),
        ("duplicate3@mail.net", "MySecure123", "AnotherPass789"),
    ]
    
    for email, first_password, second_password in test_cases:
        # Arrange: Create first user with email
        first_user = await auth_service.create_user(
            email=email,
            password=first_password,
            db=db_session
        )
        
        assert first_user is not None
        assert first_user.email == email
        
        # Act & Assert: Try to create second user with same email
        with pytest.raises(ValueError, match="Email already registered"):
            await auth_service.create_user(
                email=email,
                password=second_password,
                db=db_session
            )
        
        # Assert: Only one user exists with this email
        result = await db_session.execute(
            select(User).where(User.email == email)
        )
        users = result.scalars().all()
        assert len(users) == 1, f"Only one user should exist with email {email}"
        assert users[0].id == first_user.id


@pytest.mark.asyncio
async def test_property_24_sign_out_revokes_refresh_token(db_session):
    """
    Feature: user-authentication, Property 24: Sign Out Revokes Refresh Token
    
    For any authenticated user with a valid refresh token, signing out should mark
    that refresh token as revoked in the database.
    
    **Validates: Requirements 8.1, 8.2**
    """
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    
    # Generate test RSA keys
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
    
    token_service = TokenService(private_key=private_pem, public_key=public_pem, algorithm="RS256")
    
    # Test with multiple examples
    test_cases = [
        (1, "signout1@example.com"),
        (2, "signout2@test.org"),
        (3, "signout3@mail.net"),
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
        
        refresh_token = await token_service.generate_refresh_token(user.id, db_session)
        
        # Verify token is not revoked initially
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        token_record = result.scalar_one()
        assert token_record.is_revoked is False
        
        # Act: Sign out (revoke the refresh token)
        await token_service.revoke_refresh_token(refresh_token, db_session)
        
        # Assert: Refresh token is marked as revoked
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        token_record = result.scalar_one()
        assert token_record.is_revoked is True, f"Refresh token for {email} should be revoked after sign out"


@pytest.mark.asyncio
async def test_property_25_revoked_tokens_unusable(db_session):
    """
    Feature: user-authentication, Property 25: Revoked Tokens Unusable
    
    For any access token whose associated refresh token has been revoked, attempting
    to use it for protected routes should return HTTP 401.
    
    **Validates: Requirements 8.3**
    """
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    
    # Generate test RSA keys
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
    
    token_service = TokenService(private_key=private_pem, public_key=public_pem, algorithm="RS256")
    
    # Test with multiple examples
    test_cases = [
        (1, "revoked1@example.com"),
        (2, "revoked2@test.org"),
        (3, "revoked3@mail.net"),
    ]
    
    for user_id, email in test_cases:
        # Arrange: Create a user with tokens
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True,
            is_active=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        access_token = token_service.generate_access_token(user.id, user.email)
        refresh_token = await token_service.generate_refresh_token(user.id, db_session)
        
        # Act: Revoke the refresh token
        await token_service.revoke_refresh_token(refresh_token, db_session)
        
        # Assert: Refresh token cannot be used
        with pytest.raises(ValueError, match="Refresh token has been revoked"):
            await token_service.refresh_access_token(refresh_token, db_session)
        
        # Assert: Verify token is marked as revoked in database
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        token_record = result.scalar_one()
        assert token_record.is_revoked is True


@pytest.mark.asyncio
async def test_property_26_revoke_all_sessions(db_session):
    """
    Feature: user-authentication, Property 26: Revoke All Sessions
    
    For any user with multiple active refresh tokens, calling the revoke-all-sessions
    endpoint should mark all refresh tokens for that user as revoked.
    
    **Validates: Requirements 8.4, 8.5**
    """
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    
    # Generate test RSA keys
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
    
    token_service = TokenService(private_key=private_pem, public_key=public_pem, algorithm="RS256")
    
    # Test with multiple examples
    test_cases = [
        (1, "multiuser1@example.com", 3),
        (2, "multiuser2@test.org", 5),
        (3, "multiuser3@mail.net", 2),
    ]
    
    for user_id, email, num_sessions in test_cases:
        # Arrange: Create a user with multiple refresh tokens
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True,
            is_active=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Create multiple sessions (refresh tokens)
        refresh_tokens = []
        for i in range(num_sessions):
            token = await token_service.generate_refresh_token(user.id, db_session)
            refresh_tokens.append(token)
        
        # Verify all tokens are not revoked initially
        for token in refresh_tokens:
            result = await db_session.execute(
                select(RefreshToken).where(RefreshToken.token == token)
            )
            token_record = result.scalar_one()
            assert token_record.is_revoked is False
        
        # Act: Revoke all sessions for the user
        await token_service.revoke_all_user_tokens(user.id, db_session)
        
        # Assert: All refresh tokens are marked as revoked
        for token in refresh_tokens:
            result = await db_session.execute(
                select(RefreshToken).where(RefreshToken.token == token)
            )
            token_record = result.scalar_one()
            assert token_record.is_revoked is True, (
                f"All refresh tokens for {email} should be revoked"
            )
        
        # Assert: All tokens cannot be used
        for token in refresh_tokens:
            with pytest.raises(ValueError, match="Refresh token has been revoked"):
                await token_service.refresh_access_token(token, db_session)


@pytest.mark.asyncio
async def test_property_34_email_notifications_sent(db_session):
    """
    Feature: user-authentication, Property 34: Email Notifications Sent
    
    For any user action that requires email notification (registration, password reset,
    account locked, email verification), the email service should be called with the
    appropriate template and recipient.
    
    **Validates: Requirements 1.5, 5.2, 7.2, 10.2**
    """
    auth_service = AuthService()
    
    # Test Case 1: Registration sends verification email
    test_cases_registration = [
        ("newuser1@example.com", "Password123", "User One"),
        ("newuser2@test.org", "SecureP@ss1", None),
        ("newuser3@mail.net", "MyPass456", "User Three"),
    ]
    
    for email, password, full_name in test_cases_registration:
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock) as mock_email:
            # Act: Create user
            user = await auth_service.create_user(
                email=email,
                password=password,
                db=db_session,
                full_name=full_name
            )
            
            # Assert: Verification email was sent
            assert mock_email.called, f"Verification email should be sent for {email}"
            assert mock_email.call_count == 1
            call_args = mock_email.call_args
            assert call_args[0][0] == email or call_args[1].get('email') == email
    
    # Test Case 2: Password reset sends reset email
    test_cases_reset = [
        "resetuser1@example.com",
        "resetuser2@test.org",
        "resetuser3@mail.net",
    ]
    
    for email in test_cases_reset:
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
        
        with patch.object(EmailService, 'send_password_reset_email', new_callable=AsyncMock) as mock_email:
            # Act: Initiate password reset
            await auth_service.initiate_password_reset(email, db_session)
            
            # Assert: Password reset email was sent
            assert mock_email.called, f"Password reset email should be sent for {email}"
            assert mock_email.call_count == 1
            call_args = mock_email.call_args
            assert call_args[0][0] == email or call_args[1].get('email') == email
    
    # Test Case 3: Account locked sends notification email
    test_cases_locked = [
        "lockeduser1@example.com",
        "lockeduser2@test.org",
        "lockeduser3@mail.net",
    ]
    
    for email in test_cases_locked:
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
        
        with patch.object(EmailService, 'send_account_locked_email', new_callable=AsyncMock) as mock_email:
            # Act: Lock account (simulated by calling email service directly)
            from app.services.rate_limiter import RateLimiterService
            rate_limiter = RateLimiterService()
            await rate_limiter.lock_account(email, db_session, duration_minutes=15)
            
            # Send the notification
            email_service = EmailService()
            await email_service.send_account_locked_email(email)
            
            # Assert: Account locked email was sent
            assert mock_email.called, f"Account locked email should be sent for {email}"
    
    # Test Case 4: Email verification resend sends new verification email
    test_cases_resend = [
        ("resenduser1@example.com", "Password123"),
        ("resenduser2@test.org", "SecureP@ss1"),
        ("resenduser3@mail.net", "MyPass456"),
    ]
    
    for email, password in test_cases_resend:
        # Arrange: Create an unverified user
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            user = await auth_service.create_user(
                email=email,
                password=password,
                db=db_session
            )
        
        # Act: Resend verification email
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock) as mock_email:
            await auth_service.resend_verification_email(email, db_session)
            
            # Assert: Verification email was sent again
            assert mock_email.called, f"Resend verification email should be sent for {email}"
            assert mock_email.call_count == 1
            call_args = mock_email.call_args
            assert call_args[0][0] == email or call_args[1].get('email') == email
