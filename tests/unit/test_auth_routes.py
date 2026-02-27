"""Unit tests for authentication routes.

Tests all authentication endpoints with valid and invalid inputs,
error responses, status codes, and rate limiting behavior.

Requirements: 1.1, 1.2, 2.1, 2.2, 4.1, 5.1, 5.4, 7.3, 7.5, 8.1
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from app.models.user import User
from app.models.email_verification import EmailVerificationToken
from app.models.password_reset import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.services.auth_service import AuthService
from app.services.token_service import TokenService


@pytest.mark.asyncio
async def test_signup_success(test_client: AsyncClient, db_session: AsyncSession):
    """Test successful user registration."""
    response = await test_client.post(
        "/auth/signup",
        json={
            "email": "newuser@example.com",
            "password": "ValidPass123",
            "full_name": "New User"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New User"
    assert data["is_verified"] is False
    assert "id" in data


@pytest.mark.asyncio
async def test_signup_duplicate_email(test_client: AsyncClient, db_session: AsyncSession):
    """Test registration with existing email returns error."""
    # Create first user
    await test_client.post(
        "/auth/signup",
        json={
            "email": "duplicate@example.com",
            "password": "ValidPass123"
        }
    )
    
    # Try to create second user with same email
    response = await test_client.post(
        "/auth/signup",
        json={
            "email": "duplicate@example.com",
            "password": "AnotherPass123"
        }
    )
    
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_signup_weak_password(test_client: AsyncClient):
    """Test registration with weak password returns error."""
    # No uppercase
    response = await test_client.post(
        "/auth/signup",
        json={
            "email": "test@example.com",
            "password": "weakpass123"
        }
    )
    assert response.status_code == 422
    
    # No lowercase
    response = await test_client.post(
        "/auth/signup",
        json={
            "email": "test@example.com",
            "password": "WEAKPASS123"
        }
    )
    assert response.status_code == 422
    
    # No number
    response = await test_client.post(
        "/auth/signup",
        json={
            "email": "test@example.com",
            "password": "WeakPassword"
        }
    )
    assert response.status_code == 422
    
    # Too short
    response = await test_client.post(
        "/auth/signup",
        json={
            "email": "test@example.com",
            "password": "Pass1"
        }
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signin_success(test_client: AsyncClient, db_session: AsyncSession):
    """Test successful sign-in with valid credentials."""
    # Create and verify user
    auth_service = AuthService()
    user = await auth_service.create_user(
        email="signin@example.com",
        password="ValidPass123",
        db=db_session
    )
    user.is_verified = True
    await db_session.commit()
    
    # Sign in
    response = await test_client.post(
        "/auth/signin",
        json={
            "email": "signin@example.com",
            "password": "ValidPass123"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 900


@pytest.mark.asyncio
async def test_signin_invalid_credentials(test_client: AsyncClient, db_session: AsyncSession):
    """Test sign-in with invalid credentials returns generic error."""
    # Create and verify user
    auth_service = AuthService()
    user = await auth_service.create_user(
        email="test@example.com",
        password="ValidPass123",
        db=db_session
    )
    user.is_verified = True
    await db_session.commit()
    
    # Wrong password
    response = await test_client.post(
        "/auth/signin",
        json={
            "email": "test@example.com",
            "password": "WrongPass123"
        }
    )
    
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()
    
    # Non-existent email
    response = await test_client.post(
        "/auth/signin",
        json={
            "email": "nonexistent@example.com",
            "password": "ValidPass123"
        }
    )
    
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_signin_unverified_email(test_client: AsyncClient, db_session: AsyncSession):
    """Test sign-in with unverified email returns error."""
    # Create unverified user
    auth_service = AuthService()
    await auth_service.create_user(
        email="unverified@example.com",
        password="ValidPass123",
        db=db_session
    )
    
    response = await test_client.post(
        "/auth/signin",
        json={
            "email": "unverified@example.com",
            "password": "ValidPass123"
        }
    )
    
    assert response.status_code == 401
    assert "verification" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_signin_rate_limiting(test_client: AsyncClient, db_session: AsyncSession):
    """Test account locking after multiple failed sign-in attempts."""
    # Create and verify user
    auth_service = AuthService()
    user = await auth_service.create_user(
        email="ratelimit@example.com",
        password="ValidPass123",
        db=db_session
    )
    user.is_verified = True
    await db_session.commit()
    
    # Make 5 failed attempts
    for i in range(5):
        response = await test_client.post(
            "/auth/signin",
            json={
                "email": "ratelimit@example.com",
                "password": "WrongPass123"
            }
        )
        if i < 4:
            assert response.status_code == 401
    
    # 6th attempt should be rate limited
    response = await test_client.post(
        "/auth/signin",
        json={
            "email": "ratelimit@example.com",
            "password": "WrongPass123"
        }
    )
    
    assert response.status_code == 429
    assert "locked" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_signout_success(test_client: AsyncClient, db_session: AsyncSession):
    """Test successful sign-out revokes refresh token."""
    # Create verified user and sign in
    auth_service = AuthService()
    user = await auth_service.create_user(
        email="signout@example.com",
        password="ValidPass123",
        db=db_session
    )
    user.is_verified = True
    await db_session.commit()
    
    signin_response = await test_client.post(
        "/auth/signin",
        json={
            "email": "signout@example.com",
            "password": "ValidPass123"
        }
    )
    refresh_token = signin_response.json()["refresh_token"]
    
    # Sign out
    response = await test_client.post(
        "/auth/signout",
        json={"refresh_token": refresh_token}
    )
    
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_signout_invalid_token(test_client: AsyncClient):
    """Test sign-out with invalid token returns error."""
    response = await test_client.post(
        "/auth/signout",
        json={"refresh_token": "invalid-token"}
    )
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_refresh_token_success(test_client: AsyncClient, db_session: AsyncSession):
    """Test successful token refresh."""
    # Create verified user and sign in
    auth_service = AuthService()
    user = await auth_service.create_user(
        email="refresh@example.com",
        password="ValidPass123",
        db=db_session
    )
    user.is_verified = True
    await db_session.commit()
    
    signin_response = await test_client.post(
        "/auth/signin",
        json={
            "email": "refresh@example.com",
            "password": "ValidPass123"
        }
    )
    refresh_token = signin_response.json()["refresh_token"]
    
    # Refresh token
    response = await test_client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] != refresh_token  # Token rotation


@pytest.mark.asyncio
async def test_refresh_token_invalid(test_client: AsyncClient):
    """Test refresh with invalid token returns error."""
    response = await test_client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid-token"}
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_verify_email_success(test_client: AsyncClient, db_session: AsyncSession):
    """Test successful email verification."""
    # Create user
    auth_service = AuthService()
    user = await auth_service.create_user(
        email="verify@example.com",
        password="ValidPass123",
        db=db_session
    )
    
    # Get verification token
    from sqlalchemy import select
    result = await db_session.execute(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == user.id)
        .order_by(EmailVerificationToken.created_at.desc())
    )
    token = result.scalar_one()
    
    # Verify email
    response = await test_client.post(
        f"/auth/verify-email?token={token.token}"
    )
    
    assert response.status_code == 200
    assert "verified" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_verify_email_invalid_token(test_client: AsyncClient):
    """Test email verification with invalid token returns error."""
    response = await test_client.post(
        "/auth/verify-email?token=invalid-token"
    )
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_resend_verification_success(test_client: AsyncClient, db_session: AsyncSession):
    """Test resending verification email."""
    # Create unverified user
    auth_service = AuthService()
    await auth_service.create_user(
        email="resend@example.com",
        password="ValidPass123",
        db=db_session
    )
    
    response = await test_client.post(
        "/auth/resend-verification",
        json={"email": "resend@example.com"}
    )
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_success(test_client: AsyncClient, db_session: AsyncSession):
    """Test password reset initiation."""
    # Create user
    auth_service = AuthService()
    await auth_service.create_user(
        email="forgot@example.com",
        password="ValidPass123",
        db=db_session
    )
    
    response = await test_client.post(
        "/auth/forgot-password",
        json={"email": "forgot@example.com"}
    )
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_rate_limiting(test_client: AsyncClient, db_session: AsyncSession):
    """Test password reset rate limiting."""
    # Create user
    auth_service = AuthService()
    await auth_service.create_user(
        email="ratelimit-reset@example.com",
        password="ValidPass123",
        db=db_session
    )
    
    # Make 3 requests
    for i in range(3):
        response = await test_client.post(
            "/auth/forgot-password",
            json={"email": "ratelimit-reset@example.com"}
        )
        assert response.status_code == 200
    
    # 4th request should be rate limited
    response = await test_client.post(
        "/auth/forgot-password",
        json={"email": "ratelimit-reset@example.com"}
    )
    
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_reset_password_success(test_client: AsyncClient, db_session: AsyncSession):
    """Test successful password reset."""
    # Create user and initiate reset
    auth_service = AuthService()
    user = await auth_service.create_user(
        email="reset@example.com",
        password="OldPass123",
        db=db_session
    )
    
    token = await auth_service.initiate_password_reset("reset@example.com", db_session)
    
    # Reset password
    response = await test_client.post(
        "/auth/reset-password",
        json={
            "token": token,
            "new_password": "NewPass123"
        }
    )
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_invalid_token(test_client: AsyncClient):
    """Test password reset with invalid token returns error."""
    response = await test_client.post(
        "/auth/reset-password",
        json={
            "token": "invalid-token",
            "new_password": "NewPass123"
        }
    )
    
    assert response.status_code == 400
