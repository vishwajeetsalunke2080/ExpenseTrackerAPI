"""Property-based tests for AuthService.

These tests verify correctness properties across all valid inputs using Hypothesis.
Each test runs with max_examples=20 for faster test execution.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.6, 2.2, 2.6**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Optional
import bcrypt

from app.services.auth_service import AuthService


# Custom Hypothesis strategies for generating valid test data

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


# Property Tests

@given(
    password=st.text(min_size=0, max_size=50)
)
@settings(max_examples=20, deadline=None)
def test_property_3_password_strength_validation(password: str):
    """
    Feature: user-authentication, Property 3: Password Strength Validation
    
    For any password string, the validation function should accept it if and only if
    it contains at least 8 characters, at least one uppercase letter, at least one
    lowercase letter, and at least one number.
    
    **Validates: Requirements 1.3**
    """
    auth_service = AuthService()
    
    # Act: Validate password
    is_valid = auth_service.validate_password_strength(password)
    
    # Assert: Validation matches requirements
    has_min_length = len(password) >= 8
    has_uppercase = any(c.isupper() for c in password)
    has_lowercase = any(c.islower() for c in password)
    has_number = any(c.isdigit() for c in password)
    
    expected_valid = has_min_length and has_uppercase and has_lowercase and has_number
    
    assert is_valid == expected_valid, (
        f"Password '{password}' validation mismatch. "
        f"Expected: {expected_valid}, Got: {is_valid}. "
        f"Length: {len(password)}, Upper: {has_uppercase}, "
        f"Lower: {has_lowercase}, Number: {has_number}"
    )


@given(
    password=st.text(min_size=1, max_size=100)
)
@settings(max_examples=20, deadline=None)
def test_property_4_password_hashing_security(password: str):
    """
    Feature: user-authentication, Property 4: Password Hashing Security
    
    For any password string, after hashing, the resulting hash should not equal
    the original password and should be a valid bcrypt hash format.
    
    **Validates: Requirements 1.4**
    """
    auth_service = AuthService()
    
    # Act: Hash password
    hashed = auth_service.hash_password(password)
    
    # Assert: Hash is not the same as original password
    assert hashed != password, "Hashed password should not equal plain password"
    
    # Assert: Hash is a valid bcrypt format
    # Bcrypt hashes start with $2b$ and are 60 characters long
    assert hashed.startswith('$2b$'), "Hash should be in bcrypt format"
    assert len(hashed) == 60, f"Bcrypt hash should be 60 characters, got {len(hashed)}"
    
    # Assert: Hash can be used to verify the original password
    password_bytes = password.encode('utf-8')
    hashed_bytes = hashed.encode('utf-8')
    assert bcrypt.checkpw(password_bytes, hashed_bytes), "Hash should verify against original password"


# Database-dependent tests using pytest-asyncio

@pytest.mark.asyncio
async def test_property_1_valid_registration_creates_user_account(test_db):
    """
    Feature: user-authentication, Property 1: Valid Registration Creates User Account
    
    For any valid email and password combination that meets security requirements,
    registering a new user should create a user account in the database with the
    provided email and a hashed password.
    
    **Validates: Requirements 1.1, 1.4**
    """
    from sqlalchemy import select
    from app.models.user import User
    
    auth_service = AuthService()
    
    # Test with multiple examples
    test_cases = [
        ("user1@example.com", "ValidPass123", "John Doe"),
        ("user2@test.org", "SecureP@ss1", None),
        ("user3@mail.net", "MyP4ssword", "Jane Smith"),
    ]
    
    for email, password, full_name in test_cases:
        # Act: Create user
        user = await auth_service.create_user(
            email=email,
            password=password,
            db=test_db,
            full_name=full_name
        )
        
        # Assert: User was created
        assert user is not None
        assert user.id is not None
        assert user.email == email
        assert user.full_name == full_name
        
        # Assert: Password was hashed (not stored in plain text)
        assert user.password_hash != password
        assert user.password_hash is not None
        
        # Assert: User exists in database
        result = await test_db.execute(
            select(User).where(User.email == email)
        )
        db_user = result.scalar_one_or_none()
        assert db_user is not None
        assert db_user.email == email
        assert db_user.password_hash == user.password_hash


@pytest.mark.asyncio
async def test_property_5_new_users_start_unverified(test_db):
    """
    Feature: user-authentication, Property 5: New Users Start Unverified
    
    For any newly created user account, the is_verified field should be False
    until email verification is completed.
    
    **Validates: Requirements 1.6**
    """
    from sqlalchemy import select
    from app.models.user import User
    from app.models.email_verification import EmailVerificationToken
    
    auth_service = AuthService()
    
    # Test with multiple examples
    test_cases = [
        ("newuser1@example.com", "ValidPass123", "User One"),
        ("newuser2@test.org", "SecureP@ss1", None),
        ("newuser3@mail.net", "MyP4ssword", "User Three"),
    ]
    
    for email, password, full_name in test_cases:
        # Act: Create user
        user = await auth_service.create_user(
            email=email,
            password=password,
            db=test_db,
            full_name=full_name
        )
        
        # Assert: User starts unverified
        assert user.is_verified is False, f"New user {email} should start with is_verified=False"
        
        # Assert: User in database is also unverified
        result = await test_db.execute(
            select(User).where(User.email == email)
        )
        db_user = result.scalar_one_or_none()
        assert db_user is not None
        assert db_user.is_verified is False, f"User {email} in database should be unverified"
        
        # Assert: Verification token was created
        token_result = await test_db.execute(
            select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
        )
        verification_token = token_result.scalar_one_or_none()
        assert verification_token is not None, f"Verification token should be created for user {email}"


@pytest.mark.asyncio
async def test_property_7_invalid_credentials_return_generic_error(test_db):
    """
    Feature: user-authentication, Property 7: Invalid Credentials Return Generic Error
    
    For any sign-in attempt with incorrect email or incorrect password, the error
    message should not reveal which credential was incorrect.
    
    **Validates: Requirements 2.2**
    """
    auth_service = AuthService()
    
    # Arrange: Create a verified user
    email = "testuser@example.com"
    password = "CorrectPass123"
    
    user = await auth_service.create_user(
        email=email,
        password=password,
        db=test_db
    )
    # Manually verify the user for this test
    user.is_verified = True
    await test_db.commit()
    
    # Test with multiple wrong passwords
    wrong_passwords = ["WrongPass123", "incorrect", "12345678Aa", "DifferentP@ss1"]
    
    for wrong_password in wrong_passwords:
        # Act: Try to authenticate with wrong password
        result = await auth_service.authenticate_user(
            email=email,
            password=wrong_password,
            db=test_db
        )
        
        # Assert: Authentication fails (returns None, not revealing which credential was wrong)
        assert result is None, f"Authentication with wrong password '{wrong_password}' should return None"
    
    # Test with wrong emails
    wrong_emails = ["wrong@example.com", "notexist@test.org", "fake@mail.net"]
    
    for wrong_email in wrong_emails:
        # Act: Try to authenticate with wrong email
        result = await auth_service.authenticate_user(
            email=wrong_email,
            password=password,
            db=test_db
        )
        
        # Assert: Authentication fails (returns None, not revealing which credential was wrong)
        assert result is None, f"Authentication with wrong email '{wrong_email}' should return None"


@pytest.mark.asyncio
async def test_property_9_unverified_users_cannot_sign_in(test_db):
    """
    Feature: user-authentication, Property 9: Unverified Users Cannot Sign In
    
    For any user account where is_verified is False, attempting to sign in should
    return an error indicating email verification is required, and no tokens should
    be issued.
    
    **Validates: Requirements 2.6**
    """
    from sqlalchemy import select
    from app.models.user import User
    
    auth_service = AuthService()
    
    # Test with multiple unverified users
    test_cases = [
        ("unverified1@example.com", "ValidPass123"),
        ("unverified2@test.org", "SecureP@ss1"),
        ("unverified3@mail.net", "MyP4ssword"),
    ]
    
    for email, password in test_cases:
        # Arrange: Create an unverified user
        user = await auth_service.create_user(
            email=email,
            password=password,
            db=test_db
        )
        
        # Assert: User is unverified
        assert user.is_verified is False
        
        # Act & Assert: Try to authenticate - should raise ValueError
        with pytest.raises(ValueError, match="Email verification required"):
            await auth_service.authenticate_user(
                email=email,
                password=password,
                db=test_db
            )
        
        # Assert: User's last_login_at should not be updated
        result = await test_db.execute(
            select(User).where(User.email == email)
        )
        db_user = result.scalar_one_or_none()
        assert db_user.last_login_at is None, f"Unverified user {email} should not have last_login_at updated"
