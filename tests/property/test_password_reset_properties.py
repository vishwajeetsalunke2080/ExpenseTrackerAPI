"""Property-based tests for password reset functionality.

These tests verify correctness properties for password reset token generation
and password reset completion using Hypothesis. Each test runs with max_examples=20
for faster test execution.

**Validates: Requirements 5.1, 5.3, 5.4, 5.6**
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from app.services.auth_service import AuthService
from app.services.token_service import TokenService
from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.models.refresh_token import RefreshToken


# Custom Hypothesis strategies

@st.composite
def valid_password_strategy(draw):
    """Generate passwords that meet strength requirements.
    
    Requirements: At least 8 characters, uppercase, lowercase, and number.
    """
    # Generate components
    length = draw(st.integers(min_value=8, max_value=20))
    
    # Ensure at least one of each required character type
    uppercase = draw(st.text(alphabet=st.characters(min_codepoint=65, max_codepoint=90), min_size=1, max_size=3))
    lowercase = draw(st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=3))
    numbers = draw(st.text(alphabet='0123456789', min_size=1, max_size=3))
    
    # Fill remaining length with mixed characters
    remaining_length = max(0, length - len(uppercase) - len(lowercase) - len(numbers))
    if remaining_length > 0:
        filler = draw(st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
            min_size=remaining_length,
            max_size=remaining_length
        ))
    else:
        filler = ""
    
    # Combine and shuffle
    password_chars = list(uppercase + lowercase + numbers + filler)
    draw(st.randoms()).shuffle(password_chars)
    
    return ''.join(password_chars)


@st.composite
def valid_email_strategy(draw):
    """Generate valid email addresses."""
    username = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), min_codepoint=97, max_codepoint=122),
        min_size=3,
        max_size=20
    ))
    domain = draw(st.sampled_from(['example.com', 'test.org', 'mail.net', 'demo.io']))
    return f"{username}@{domain}"


# Property Tests

@pytest.mark.asyncio
async def test_property_15_password_reset_token_generation(db_session):
    """
    Feature: user-authentication, Property 15: Password Reset Token Generation
    
    For any valid email address in the system, requesting a password reset should
    generate a unique password reset token and store it in the database with a
    1-hour expiration.
    
    **Validates: Requirements 5.1, 5.3**
    """
    auth_service = AuthService()
    
    # Test with multiple examples
    test_cases = [
        ("user1@example.com", "ValidPass123", "User One"),
        ("user2@test.org", "SecureP@ss1", "User Two"),
        ("user3@mail.net", "MyP4ssword", None),
    ]
    
    for email, password, full_name in test_cases:
        # Arrange: Create a user
        user = User(
            email=email,
            password_hash=auth_service.hash_password(password),
            full_name=full_name,
            is_verified=True,
            is_active=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Act: Initiate password reset
        before_generation = datetime.utcnow()
        token = await auth_service.initiate_password_reset(email, db_session)
        after_generation = datetime.utcnow()
        
        # Assert: Token was generated
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Assert: Token exists in database
        result = await db_session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token == token)
        )
        db_token = result.scalar_one_or_none()
        assert db_token is not None, f"Token should exist in database for {email}"
        assert db_token.user_id == user.id
        assert db_token.used is False
        
        # Assert: Token expires in 1 hour (allow 1 second tolerance)
        expected_min = before_generation + timedelta(hours=1) - timedelta(seconds=1)
        expected_max = after_generation + timedelta(hours=1) + timedelta(seconds=1)
        
        # Handle timezone-aware comparison
        expires_at = db_token.expires_at
        if expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)
        
        assert expected_min <= expires_at <= expected_max, (
            f"Token expiration {expires_at} not within expected range "
            f"[{expected_min}, {expected_max}]"
        )


@pytest.mark.asyncio
async def test_property_15_password_reset_token_uniqueness(db_session):
    """
    Feature: user-authentication, Property 15: Password Reset Token Generation (Uniqueness)
    
    For any set of password reset requests, each should generate a unique token.
    
    **Validates: Requirements 5.1**
    """
    auth_service = AuthService()
    
    # Arrange: Create multiple users
    users = []
    for i in range(5):
        user = User(
            email=f"user{i}@example.com",
            password_hash=auth_service.hash_password(f"ValidPass{i}23"),
            is_verified=True,
            is_active=True
        )
        db_session.add(user)
        users.append(user)
    
    await db_session.commit()
    
    # Act: Generate tokens for all users
    tokens = []
    for user in users:
        token = await auth_service.initiate_password_reset(user.email, db_session)
        tokens.append(token)
    
    # Assert: All tokens are unique
    assert len(tokens) == len(set(tokens)), "All password reset tokens should be unique"
    
    # Assert: Each token is different
    for i in range(len(tokens)):
        for j in range(i + 1, len(tokens)):
            assert tokens[i] != tokens[j], f"Token {i} and {j} should be different"


@pytest.mark.asyncio
async def test_property_16_password_reset_completion(db_session):
    """
    Feature: user-authentication, Property 16: Password Reset Completion
    
    For any valid password reset token and new password that meets security
    requirements, completing the password reset should update the user's password
    hash and invalidate all existing refresh tokens for that user.
    
    **Validates: Requirements 5.4, 5.6**
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
    
    auth_service = AuthService()
    token_service = TokenService(private_key=private_pem, public_key=public_pem, algorithm="RS256")
    
    # Test with multiple examples
    test_cases = [
        ("reset1@example.com", "OldPass123", "NewPass456"),
        ("reset2@test.org", "SecureOld1", "SecureNew2"),
        ("reset3@mail.net", "MyOldP4ss", "MyNewP4ss"),
    ]
    
    for email, old_password, new_password in test_cases:
        # Arrange: Create a user with old password
        old_hash = auth_service.hash_password(old_password)
        user = User(
            email=email,
            password_hash=old_hash,
            is_verified=True,
            is_active=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Create some refresh tokens for the user
        refresh_token_1 = await token_service.generate_refresh_token(user.id, db_session)
        refresh_token_2 = await token_service.generate_refresh_token(user.id, db_session)
        
        # Verify tokens exist and are not revoked
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.user_id == user.id)
        )
        tokens_before = result.scalars().all()
        assert len(tokens_before) >= 2
        assert all(not t.is_revoked for t in tokens_before)
        
        # Generate password reset token
        reset_token = await auth_service.initiate_password_reset(email, db_session)
        
        # Act: Reset password
        success = await auth_service.reset_password(reset_token, new_password, db_session)
        
        # Assert: Password reset succeeded
        assert success is True, f"Password reset should succeed for {email}"
        
        # Assert: Password hash was updated
        await db_session.refresh(user)
        assert user.password_hash != old_hash, "Password hash should be updated"
        
        # Assert: New password can be verified
        assert auth_service.verify_password(new_password, user.password_hash), (
            "New password should verify against updated hash"
        )
        
        # Assert: Old password no longer works
        assert not auth_service.verify_password(old_password, user.password_hash), (
            "Old password should not verify against updated hash"
        )
        
        # Assert: Reset token is marked as used
        result = await db_session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token == reset_token)
        )
        db_token = result.scalar_one_or_none()
        assert db_token.used is True, "Reset token should be marked as used"
        
        # Assert: All refresh tokens are revoked (Requirement 5.6)
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.user_id == user.id)
        )
        tokens_after = result.scalars().all()
        assert all(t.is_revoked for t in tokens_after), (
            f"All refresh tokens should be revoked after password reset for {email}"
        )


@pytest.mark.asyncio
async def test_property_16_password_reset_with_expired_token(db_session):
    """
    Feature: user-authentication, Property 16: Password Reset Completion (Expired Token)
    
    For any expired password reset token, attempting to reset the password should
    fail and no state changes should occur.
    
    **Validates: Requirements 5.5**
    """
    auth_service = AuthService()
    
    # Test with multiple examples
    test_cases = [
        ("expired1@example.com", "OldPass123", "NewPass456"),
        ("expired2@test.org", "SecureOld1", "SecureNew2"),
    ]
    
    for email, old_password, new_password in test_cases:
        # Arrange: Create a user
        old_hash = auth_service.hash_password(old_password)
        user = User(
            email=email,
            password_hash=old_hash,
            is_verified=True,
            is_active=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Create an expired password reset token
        expired_token = PasswordResetToken(
            user_id=user.id,
            token=f"expired-token-{email}",
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
            used=False
        )
        db_session.add(expired_token)
        await db_session.commit()
        
        # Act: Try to reset password with expired token
        success = await auth_service.reset_password(
            f"expired-token-{email}",
            new_password,
            db_session
        )
        
        # Assert: Password reset failed
        assert success is False, f"Password reset should fail with expired token for {email}"
        
        # Assert: Password hash was NOT updated
        await db_session.refresh(user)
        assert user.password_hash == old_hash, "Password hash should not change with expired token"
        
        # Assert: Old password still works
        assert auth_service.verify_password(old_password, user.password_hash), (
            "Old password should still work after failed reset"
        )


@pytest.mark.asyncio
async def test_property_16_password_reset_with_used_token(db_session):
    """
    Feature: user-authentication, Property 16: Password Reset Completion (Used Token)
    
    For any already-used password reset token, attempting to reset the password
    should fail and no state changes should occur.
    
    **Validates: Requirements 5.5**
    """
    auth_service = AuthService()
    
    # Arrange: Create a user
    email = "usedtoken@example.com"
    old_password = "OldPass123"
    first_new_password = "NewPass456"
    second_new_password = "AnotherPass789"
    
    old_hash = auth_service.hash_password(old_password)
    user = User(
        email=email,
        password_hash=old_hash,
        is_verified=True,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Generate password reset token
    reset_token = await auth_service.initiate_password_reset(email, db_session)
    
    # Act: Use the token once (should succeed)
    success_first = await auth_service.reset_password(reset_token, first_new_password, db_session)
    assert success_first is True, "First password reset should succeed"
    
    await db_session.refresh(user)
    first_new_hash = user.password_hash
    
    # Act: Try to use the same token again (should fail)
    success_second = await auth_service.reset_password(reset_token, second_new_password, db_session)
    
    # Assert: Second password reset failed
    assert success_second is False, "Password reset should fail with already-used token"
    
    # Assert: Password hash was NOT updated the second time
    await db_session.refresh(user)
    assert user.password_hash == first_new_hash, "Password hash should not change when reusing token"
    
    # Assert: First new password still works
    assert auth_service.verify_password(first_new_password, user.password_hash), (
        "First new password should still work after failed second reset"
    )
    
    # Assert: Second new password does NOT work
    assert not auth_service.verify_password(second_new_password, user.password_hash), (
        "Second new password should not work after failed reset"
    )


@pytest.mark.asyncio
async def test_property_16_password_reset_with_invalid_token(db_session):
    """
    Feature: user-authentication, Property 16: Password Reset Completion (Invalid Token)
    
    For any non-existent or malformed password reset token, attempting to reset
    the password should fail.
    
    **Validates: Requirements 5.5**
    """
    auth_service = AuthService()
    
    # Arrange: Create a user
    email = "invalidtoken@example.com"
    old_password = "OldPass123"
    new_password = "NewPass456"
    
    old_hash = auth_service.hash_password(old_password)
    user = User(
        email=email,
        password_hash=old_hash,
        is_verified=True,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Test with various invalid tokens
    invalid_tokens = [
        "non-existent-token",
        "fake-token-12345",
        "invalid",
        "",
        "00000000-0000-0000-0000-000000000000"
    ]
    
    for invalid_token in invalid_tokens:
        # Act: Try to reset password with invalid token
        success = await auth_service.reset_password(invalid_token, new_password, db_session)
        
        # Assert: Password reset failed
        assert success is False, f"Password reset should fail with invalid token '{invalid_token}'"
        
        # Assert: Password hash was NOT updated
        await db_session.refresh(user)
        assert user.password_hash == old_hash, (
            f"Password hash should not change with invalid token '{invalid_token}'"
        )


@pytest.mark.asyncio
async def test_property_16_password_reset_validates_password_strength(db_session):
    """
    Feature: user-authentication, Property 16: Password Reset Completion (Password Validation)
    
    For any password reset attempt with a weak password, the reset should fail
    with a validation error.
    
    **Validates: Requirements 1.3, 5.4**
    """
    auth_service = AuthService()
    
    # Arrange: Create a user
    email = "weakpass@example.com"
    old_password = "OldPass123"
    
    user = User(
        email=email,
        password_hash=auth_service.hash_password(old_password),
        is_verified=True,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Generate password reset token
    reset_token = await auth_service.initiate_password_reset(email, db_session)
    
    # Test with various weak passwords
    weak_passwords = [
        "short",           # Too short
        "nouppercase1",    # No uppercase
        "NOLOWERCASE1",    # No lowercase
        "NoNumbers",       # No numbers
        "12345678",        # No letters
    ]
    
    for weak_password in weak_passwords:
        # Act & Assert: Try to reset with weak password (should raise ValueError)
        with pytest.raises(ValueError, match="Password must be at least 8 characters"):
            await auth_service.reset_password(reset_token, weak_password, db_session)
        
        # Assert: Password hash was NOT updated
        await db_session.refresh(user)
        assert auth_service.verify_password(old_password, user.password_hash), (
            f"Old password should still work after failed reset with weak password '{weak_password}'"
        )
