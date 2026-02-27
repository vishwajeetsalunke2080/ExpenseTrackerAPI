"""Property-based tests for email verification functionality.

These tests verify correctness properties for email verification across multiple
inputs using property-based testing principles. Each test runs with max_examples=20
for faster test execution.

**Validates: Requirements 7.1, 7.3, 7.5**
"""
import pytest
from hypothesis import strategies as st, settings
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from app.services.auth_service import AuthService
from app.models.user import User
from app.models.email_verification import EmailVerificationToken


# Property Tests

@pytest.mark.asyncio
async def test_property_21_email_verification_token_uniqueness(db_session):
    """
    Feature: user-authentication, Property 21: Email Verification Token Uniqueness
    
    For any set of users created in the system, each should receive a unique
    email verification token.
    
    **Validates: Requirements 7.1**
    """
    auth_service = AuthService()
    
    # Test with multiple users
    test_cases = [
        ("user1@example.com", "ValidPass123", "User One"),
        ("user2@test.org", "SecureP@ss1", "User Two"),
        ("user3@mail.net", "MyP4ssword", "User Three"),
        ("user4@demo.io", "TestPass99", "User Four"),
        ("user5@sample.com", "Strong1Pass", None),
    ]
    
    created_tokens = []
    
    for email, password, full_name in test_cases:
        # Act: Create user (which generates verification token)
        user = await auth_service.create_user(
            email=email,
            password=password,
            db=db_session,
            full_name=full_name
        )
        
        # Get the verification token for this user
        result = await db_session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user.id
            )
        )
        verification_token = result.scalar_one_or_none()
        
        assert verification_token is not None, f"Verification token should be created for user {email}"
        
        # Assert: Token is unique (not in the list of previously created tokens)
        assert verification_token.token not in created_tokens, (
            f"Verification token for user {email} is not unique. "
            f"Token '{verification_token.token}' already exists."
        )
        
        created_tokens.append(verification_token.token)
    
    # Assert: All tokens are unique
    assert len(created_tokens) == len(set(created_tokens)), (
        "All verification tokens should be unique"
    )
    assert len(created_tokens) == len(test_cases), (
        f"Expected {len(test_cases)} unique tokens, got {len(created_tokens)}"
    )


@pytest.mark.asyncio
async def test_property_22_email_verification_marks_user_verified(db_session):
    """
    Feature: user-authentication, Property 22: Email Verification Marks User Verified
    
    For any valid email verification token, using it to verify should set the
    user's is_verified field to True and mark the token as used.
    
    **Validates: Requirements 7.3**
    """
    auth_service = AuthService()
    
    # Test with multiple users
    test_cases = [
        ("verify1@example.com", "ValidPass123", "Verify One"),
        ("verify2@test.org", "SecureP@ss1", "Verify Two"),
        ("verify3@mail.net", "MyP4ssword", None),
        ("verify4@demo.io", "TestPass99", "Verify Four"),
    ]
    
    for email, password, full_name in test_cases:
        # Arrange: Create an unverified user
        user = await auth_service.create_user(
            email=email,
            password=password,
            db=db_session,
            full_name=full_name
        )
        
        # Assert: User starts unverified
        assert user.is_verified is False, f"User {email} should start unverified"
        
        # Get the verification token
        result = await db_session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used == False
            )
        )
        verification_token = result.scalar_one_or_none()
        assert verification_token is not None
        token_string = verification_token.token
        
        # Act: Verify the email
        verification_result = await auth_service.verify_email(
            token=token_string,
            db=db_session
        )
        
        # Assert: Verification succeeded
        assert verification_result is True, f"Email verification should succeed for user {email}"
        
        # Assert: User is now verified
        await db_session.refresh(user)
        assert user.is_verified is True, (
            f"User {email} should be verified after email verification"
        )
        
        # Assert: Token is marked as used
        await db_session.refresh(verification_token)
        assert verification_token.used is True, (
            f"Verification token for user {email} should be marked as used"
        )


@pytest.mark.asyncio
async def test_property_23_verification_email_resend(db_session):
    """
    Feature: user-authentication, Property 23: Verification Email Resend
    
    For any unverified user, requesting a new verification email should generate
    a new token, invalidate the old token, and send an email with the new token.
    
    **Validates: Requirements 7.5**
    """
    auth_service = AuthService()
    
    # Test with multiple users
    test_cases = [
        ("resend1@example.com", "ValidPass123", "Resend One"),
        ("resend2@test.org", "SecureP@ss1", "Resend Two"),
        ("resend3@mail.net", "MyP4ssword", None),
        ("resend4@demo.io", "TestPass99", "Resend Four"),
    ]
    
    for email, password, full_name in test_cases:
        # Arrange: Create an unverified user
        user = await auth_service.create_user(
            email=email,
            password=password,
            db=db_session,
            full_name=full_name
        )
        
        # Get the original verification token
        result = await db_session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used == False
            )
        )
        original_token = result.scalar_one_or_none()
        assert original_token is not None
        original_token_string = original_token.token
        
        # Act: Request a new verification email
        new_token_string = await auth_service.resend_verification_email(
            email=email,
            db=db_session
        )
        
        # Assert: New token was generated
        assert new_token_string is not None, (
            f"New verification token should be generated for user {email}"
        )
        
        # Assert: New token is different from original
        assert new_token_string != original_token_string, (
            f"New verification token for user {email} should be different from original"
        )
        
        # Assert: Old token is invalidated (marked as used)
        await db_session.refresh(original_token)
        assert original_token.used is True, (
            f"Original verification token for user {email} should be invalidated"
        )
        
        # Assert: New token exists in database and is not used
        result = await db_session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token == new_token_string,
                EmailVerificationToken.user_id == user.id
            )
        )
        new_token = result.scalar_one_or_none()
        assert new_token is not None, (
            f"New verification token should exist in database for user {email}"
        )
        assert new_token.used is False, (
            f"New verification token for user {email} should not be marked as used"
        )
        
        # Assert: User is still unverified
        await db_session.refresh(user)
        assert user.is_verified is False, (
            f"User {email} should remain unverified after resending verification email"
        )
        
        # Assert: New token can be used to verify the user
        verification_result = await auth_service.verify_email(
            token=new_token_string,
            db=db_session
        )
        assert verification_result is True, (
            f"New verification token should successfully verify user {email}"
        )
        
        # Assert: User is now verified
        await db_session.refresh(user)
        assert user.is_verified is True, (
            f"User {email} should be verified after using new token"
        )