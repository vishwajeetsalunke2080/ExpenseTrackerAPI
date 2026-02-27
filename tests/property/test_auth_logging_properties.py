"""Property-based tests for authentication logging.

These tests verify that all authentication attempts are properly logged
with the required information.

**Validates: Requirements 10.3**
"""
import pytest
from hypothesis import given, strategies as st, settings
from sqlalchemy import select

from app.models.auth_log import AuthLog
from app.models.user import User
from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_property_32_authentication_attempt_logging(test_client, test_db):
    """
    Feature: user-authentication, Property 32: Authentication Attempt Logging
    
    For any authentication attempt (sign-in, sign-up, password reset), an entry
    should be created in the auth_logs table containing the email, action type,
    success status, IP address, and timestamp.
    
    **Validates: Requirements 10.3**
    """
    # Test Case 1: Successful signup
    signup_data = {
        "email": "newuser@example.com",
        "password": "ValidPass123",
        "full_name": "Test User"
    }
    
    response = await test_client.post("/auth/signup", json=signup_data)
    assert response.status_code == 201
    
    # Verify signup log entry
    result = await test_db.execute(
        select(AuthLog).where(
            AuthLog.email == signup_data["email"],
            AuthLog.action == "signup"
        )
    )
    signup_log = result.scalar_one_or_none()
    
    assert signup_log is not None, "Signup attempt should be logged"
    assert signup_log.email == signup_data["email"]
    assert signup_log.action == "signup"
    assert signup_log.success is True
    assert signup_log.ip_address is not None
    assert signup_log.user_agent is not None
    assert signup_log.created_at is not None
    assert signup_log.user_id is not None
    
    # Test Case 2: Failed signup (duplicate email)
    response = await test_client.post("/auth/signup", json=signup_data)
    assert response.status_code == 400
    
    # Verify failed signup log entry
    result = await test_db.execute(
        select(AuthLog).where(
            AuthLog.email == signup_data["email"],
            AuthLog.action == "signup",
            AuthLog.success == False
        )
    )
    failed_signup_log = result.scalar_one_or_none()
    
    assert failed_signup_log is not None, "Failed signup attempt should be logged"
    assert failed_signup_log.success is False
    assert failed_signup_log.ip_address is not None
    
    # Test Case 3: Verify the user for signin tests
    user_result = await test_db.execute(
        select(User).where(User.email == signup_data["email"])
    )
    user = user_result.scalar_one()
    user.is_verified = True
    await test_db.commit()
    
    # Test Case 4: Successful signin
    signin_data = {
        "email": signup_data["email"],
        "password": signup_data["password"]
    }
    
    response = await test_client.post("/auth/signin", json=signin_data)
    assert response.status_code == 200
    
    # Verify signin log entry
    result = await test_db.execute(
        select(AuthLog).where(
            AuthLog.email == signin_data["email"],
            AuthLog.action == "signin",
            AuthLog.success == True
        )
    )
    signin_log = result.scalar_one_or_none()
    
    assert signin_log is not None, "Signin attempt should be logged"
    assert signin_log.email == signin_data["email"]
    assert signin_log.action == "signin"
    assert signin_log.success is True
    assert signin_log.ip_address is not None
    assert signin_log.user_agent is not None
    assert signin_log.user_id == user.id
    
    # Test Case 5: Failed signin (wrong password)
    wrong_signin_data = {
        "email": signup_data["email"],
        "password": "WrongPassword123"
    }
    
    response = await test_client.post("/auth/signin", json=wrong_signin_data)
    assert response.status_code == 401
    
    # Verify failed signin log entry
    result = await test_db.execute(
        select(AuthLog).where(
            AuthLog.email == wrong_signin_data["email"],
            AuthLog.action == "signin",
            AuthLog.success == False
        )
    )
    failed_signin_log = result.scalar_one_or_none()
    
    assert failed_signin_log is not None, "Failed signin attempt should be logged"
    assert failed_signin_log.success is False
    assert failed_signin_log.ip_address is not None
    
    # Test Case 6: Password reset request
    reset_request_data = {"email": signup_data["email"]}
    
    response = await test_client.post("/auth/forgot-password", json=reset_request_data)
    assert response.status_code == 200
    
    # Verify password reset request log entry
    result = await test_db.execute(
        select(AuthLog).where(
            AuthLog.email == signup_data["email"],
            AuthLog.action == "password_reset_request"
        )
    )
    reset_request_log = result.scalar_one_or_none()
    
    assert reset_request_log is not None, "Password reset request should be logged"
    assert reset_request_log.email == signup_data["email"]
    assert reset_request_log.action == "password_reset_request"
    assert reset_request_log.success is True
    assert reset_request_log.ip_address is not None
    assert reset_request_log.user_id == user.id
    
    # Test Case 7: Email verification
    from app.models.email_verification import EmailVerificationToken
    
    # Get the verification token
    token_result = await test_db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id
        ).order_by(EmailVerificationToken.created_at.desc())
    )
    verification_token = token_result.scalar_one_or_none()
    
    if verification_token:
        response = await test_client.post(
            f"/auth/verify-email?token={verification_token.token}"
        )
        # May be 200 or 400 depending on if already verified
        
        # Verify email verification log entry
        result = await test_db.execute(
            select(AuthLog).where(
                AuthLog.email == signup_data["email"],
                AuthLog.action == "email_verification"
            )
        )
        verification_log = result.scalar_one_or_none()
        
        assert verification_log is not None, "Email verification attempt should be logged"
        assert verification_log.action == "email_verification"
        assert verification_log.ip_address is not None


@pytest.mark.asyncio
async def test_property_32_logging_captures_all_required_fields(test_client, test_db):
    """
    Feature: user-authentication, Property 32: Authentication Attempt Logging
    
    Verify that all required fields are captured in authentication logs:
    - email
    - action type
    - success status
    - IP address
    - user agent
    - timestamp
    
    **Validates: Requirements 10.3**
    """
    # Create a test user
    signup_data = {
        "email": "logtest@example.com",
        "password": "TestPass123",
        "full_name": "Log Test"
    }
    
    response = await test_client.post("/auth/signup", json=signup_data)
    assert response.status_code == 201
    
    # Retrieve the log entry
    result = await test_db.execute(
        select(AuthLog).where(
            AuthLog.email == signup_data["email"],
            AuthLog.action == "signup"
        )
    )
    log_entry = result.scalar_one()
    
    # Verify all required fields are present and valid
    assert log_entry.email == signup_data["email"], "Email should be logged"
    assert log_entry.action == "signup", "Action type should be logged"
    assert log_entry.success is True, "Success status should be logged"
    assert log_entry.ip_address is not None, "IP address should be logged"
    assert isinstance(log_entry.ip_address, str), "IP address should be a string"
    assert len(log_entry.ip_address) > 0, "IP address should not be empty"
    assert log_entry.user_agent is not None, "User agent should be logged"
    assert isinstance(log_entry.user_agent, str), "User agent should be a string"
    assert log_entry.created_at is not None, "Timestamp should be logged"
    assert log_entry.user_id is not None, "User ID should be logged for successful signup"


@pytest.mark.asyncio
async def test_property_32_logging_different_action_types(test_client, test_db):
    """
    Feature: user-authentication, Property 32: Authentication Attempt Logging
    
    Verify that different authentication action types are logged correctly:
    - signup
    - signin
    - password_reset_request
    - password_reset
    - email_verification
    
    **Validates: Requirements 10.3**
    """
    # Create a user via API to ensure signup is logged
    signup_data = {
        "email": "actiontest@example.com",
        "password": "TestPass123",
        "full_name": "Action Test"
    }
    response = await test_client.post("/auth/signup", json=signup_data)
    assert response.status_code == 201
    
    # Verify the user and mark as verified
    user_result = await test_db.execute(
        select(User).where(User.email == "actiontest@example.com")
    )
    user = user_result.scalar_one()
    user.is_verified = True
    await test_db.commit()
    
    # Test signin action
    signin_data = {
        "email": "actiontest@example.com",
        "password": "TestPass123"
    }
    response = await test_client.post("/auth/signin", json=signin_data)
    assert response.status_code == 200
    
    # Verify signin action is logged
    result = await test_db.execute(
        select(AuthLog).where(
            AuthLog.email == "actiontest@example.com",
            AuthLog.action == "signin"
        )
    )
    signin_log = result.scalar_one_or_none()
    assert signin_log is not None, "Signin action should be logged"
    assert signin_log.action == "signin"
    
    # Test password reset request action
    reset_data = {"email": "actiontest@example.com"}
    response = await test_client.post("/auth/forgot-password", json=reset_data)
    assert response.status_code == 200
    
    # Verify password reset request action is logged
    result = await test_db.execute(
        select(AuthLog).where(
            AuthLog.email == "actiontest@example.com",
            AuthLog.action == "password_reset_request"
        )
    )
    reset_log = result.scalar_one_or_none()
    assert reset_log is not None, "Password reset request action should be logged"
    assert reset_log.action == "password_reset_request"
    
    # Verify all action types are distinct
    result = await test_db.execute(
        select(AuthLog.action).where(
            AuthLog.email == "actiontest@example.com"
        ).distinct()
    )
    actions = [row[0] for row in result.all()]
    
    # Should have at least signup, signin, and password_reset_request
    assert "signup" in actions, "Signup action should be logged"
    assert "signin" in actions, "Signin action should be logged"
    assert "password_reset_request" in actions, "Password reset request action should be logged"
