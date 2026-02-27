"""End-to-end tests for protected routes.

Tests authentication requirements for protected and public routes.
**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.6**
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta, timezone
import jwt
import os

from app.models.user import User
from app.services.email_service import EmailService
from sqlalchemy import update, select


@pytest.mark.asyncio
class TestProtectedRoutesWithoutAuthentication:
    """Test accessing protected routes without authentication returns 401."""
    
    async def test_get_user_profile_without_token_returns_401(
        self,
        test_client: AsyncClient
    ):
        """
        Test that accessing /users/me without authentication returns 401.
        Validates: Requirements 6.1
        """
        response = await test_client.get("/users/me")
        assert response.status_code == 401
        assert "detail" in response.json()
    
    async def test_update_profile_without_token_returns_401(
        self,
        test_client: AsyncClient
    ):
        """
        Test that updating profile without authentication returns 401.
        Validates: Requirements 6.1
        """
        response = await test_client.put("/users/me", json={"full_name": "New Name"})
        assert response.status_code == 401
    
    async def test_change_password_without_token_returns_401(
        self,
        test_client: AsyncClient
    ):
        """
        Test that changing password without authentication returns 401.
        Validates: Requirements 6.1
        """
        response = await test_client.post("/users/me/change-password", json={
            "current_password": "OldPass123",
            "new_password": "NewPass456"
        })
        assert response.status_code == 401
    
    async def test_revoke_all_sessions_without_token_returns_401(
        self,
        test_client: AsyncClient
    ):
        """
        Test that revoking all sessions without authentication returns 401.
        Validates: Requirements 6.1
        """
        response = await test_client.post("/users/me/revoke-all-sessions")
        assert response.status_code == 401
    
    async def test_signout_without_token_returns_401(
        self,
        test_client: AsyncClient
    ):
        """
        Test that signing out without authentication returns 401.
        Validates: Requirements 6.1
        """
        response = await test_client.post("/auth/signout", json={"refresh_token": "fake-token"})
        assert response.status_code == 401



@pytest.mark.asyncio
class TestProtectedRoutesWithValidToken:
    """Test accessing protected routes with valid token succeeds."""
    
    async def test_get_user_profile_with_valid_token_succeeds(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test that accessing /users/me with valid token returns user data.
        Validates: Requirements 6.4
        """
        signup_data = {
            "email": "validuser@example.com",
            "password": "SecurePass123",
            "full_name": "Valid User"
        }
        
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            await test_client.post("/auth/signup", json=signup_data)
        
        await test_db.execute(
            update(User).where(User.email == signup_data["email"]).values(is_verified=True)
        )
        await test_db.commit()
        
        signin_response = await test_client.post("/auth/signin", json={
            "email": signup_data["email"],
            "password": signup_data["password"]
        })
        tokens = signin_response.json()
        
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        response = await test_client.get("/users/me", headers=headers)
        
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["email"] == signup_data["email"]
        assert user_data["full_name"] == signup_data["full_name"]
        assert user_data["is_verified"] is True
    
    async def test_update_profile_with_valid_token_succeeds(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test that updating profile with valid token succeeds.
        Validates: Requirements 6.4
        """
        signup_data = {
            "email": "updateuser@example.com",
            "password": "SecurePass123",
            "full_name": "Original Name"
        }
        
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            await test_client.post("/auth/signup", json=signup_data)
        
        await test_db.execute(
            update(User).where(User.email == signup_data["email"]).values(is_verified=True)
        )
        await test_db.commit()
        
        signin_response = await test_client.post("/auth/signin", json={
            "email": signup_data["email"],
            "password": signup_data["password"]
        })
        tokens = signin_response.json()
        
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        response = await test_client.put("/users/me", json={
            "full_name": "Updated Name"
        }, headers=headers)
        
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["full_name"] == "Updated Name"
    
    async def test_change_password_with_valid_token_succeeds(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test that changing password with valid token succeeds.
        Validates: Requirements 6.4
        """
        signup_data = {
            "email": "changepass@example.com",
            "password": "OldPassword123",
            "full_name": "Change Pass User"
        }
        
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            await test_client.post("/auth/signup", json=signup_data)
        
        await test_db.execute(
            update(User).where(User.email == signup_data["email"]).values(is_verified=True)
        )
        await test_db.commit()
        
        signin_response = await test_client.post("/auth/signin", json={
            "email": signup_data["email"],
            "password": signup_data["password"]
        })
        tokens = signin_response.json()
        
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        response = await test_client.post("/users/me/change-password", json={
            "current_password": "OldPassword123",
            "new_password": "NewPassword456"
        }, headers=headers)
        
        assert response.status_code == 200
        
        new_signin = await test_client.post("/auth/signin", json={
            "email": signup_data["email"],
            "password": "NewPassword456"
        })
        assert new_signin.status_code == 200


@pytest.mark.asyncio
class TestProtectedRoutesWithInvalidToken:
    """Test accessing protected routes with invalid token returns 401."""
    
    async def test_get_user_profile_with_malformed_token_returns_401(
        self,
        test_client: AsyncClient
    ):
        """
        Test that accessing protected route with malformed token returns 401.
        Validates: Requirements 6.2
        """
        malformed_tokens = [
            "not-a-valid-jwt-token",
            "Bearer invalid",
            "malformed.jwt.token",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"
        ]
        
        for token in malformed_tokens:
            headers = {"Authorization": f"Bearer {token}"}
            response = await test_client.get("/users/me", headers=headers)
            assert response.status_code == 401, f"Malformed token '{token}' should return 401"
    
    async def test_get_user_profile_with_wrong_signature_returns_401(
        self,
        test_client: AsyncClient
    ):
        """
        Test that accessing protected route with wrong signature returns 401.
        Validates: Requirements 6.2
        """
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        
        wrong_private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        wrong_private_pem = wrong_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        payload = {
            "sub": "123",
            "email": "fake@example.com",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "iat": datetime.now(timezone.utc)
        }
        wrong_token = jwt.encode(payload, wrong_private_pem, algorithm="RS256")
        
        headers = {"Authorization": f"Bearer {wrong_token}"}
        response = await test_client.get("/users/me", headers=headers)
        assert response.status_code == 401


@pytest.mark.asyncio
class TestProtectedRoutesWithExpiredToken:
    """Test accessing protected routes with expired token returns 401."""
    
    async def test_get_user_profile_with_expired_token_returns_401(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test that accessing protected route with expired token returns 401.
        Validates: Requirements 6.3
        """
        signup_data = {
            "email": "expireduser@example.com",
            "password": "SecurePass123",
            "full_name": "Expired User"
        }
        
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            await test_client.post("/auth/signup", json=signup_data)
        
        await test_db.execute(
            update(User).where(User.email == signup_data["email"]).values(is_verified=True)
        )
        await test_db.commit()
        
        result = await test_db.execute(
            select(User).where(User.email == signup_data["email"])
        )
        user = result.scalar_one()
        
        jwt_secret = os.getenv("JWT_SECRET_KEY", "test-secret-key-for-testing-min-32-characters-long")
        
        expired_payload = {
            "sub": str(user.id),
            "email": user.email,
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2)
        }
        expired_token = jwt.encode(expired_payload, jwt_secret, algorithm="HS256")
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = await test_client.get("/users/me", headers=headers)
        assert response.status_code == 401
    
    async def test_update_profile_with_expired_token_returns_401(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test that updating profile with expired token returns 401.
        Validates: Requirements 6.3
        """
        signup_data = {
            "email": "expiredupdate@example.com",
            "password": "SecurePass123",
            "full_name": "Expired Update User"
        }
        
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            await test_client.post("/auth/signup", json=signup_data)
        
        await test_db.execute(
            update(User).where(User.email == signup_data["email"]).values(is_verified=True)
        )
        await test_db.commit()
        
        result = await test_db.execute(
            select(User).where(User.email == signup_data["email"])
        )
        user = result.scalar_one()
        
        jwt_secret = os.getenv("JWT_SECRET_KEY", "test-secret-key-for-testing-min-32-characters-long")
        
        expired_payload = {
            "sub": str(user.id),
            "email": user.email,
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=30),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=45)
        }
        expired_token = jwt.encode(expired_payload, jwt_secret, algorithm="HS256")
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = await test_client.put("/users/me", json={
            "full_name": "New Name"
        }, headers=headers)
        assert response.status_code == 401


@pytest.mark.asyncio
class TestPublicRoutesWithoutAuthentication:
    """Test accessing public routes without authentication succeeds."""
    
    async def test_signup_without_authentication_succeeds(
        self,
        test_client: AsyncClient
    ):
        """
        Test that signup endpoint is accessible without authentication.
        Validates: Requirements 6.6
        """
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            response = await test_client.post("/auth/signup", json={
                "email": "publicsignup@example.com",
                "password": "SecurePass123",
                "full_name": "Public User"
            })
        
        assert response.status_code == 201
        user_data = response.json()
        assert user_data["email"] == "publicsignup@example.com"
    
    async def test_signin_without_authentication_succeeds(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test that signin endpoint is accessible without authentication.
        Validates: Requirements 6.6
        """
        signup_data = {
            "email": "publicsignin@example.com",
            "password": "SecurePass123",
            "full_name": "Public Signin User"
        }
        
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            await test_client.post("/auth/signup", json=signup_data)
        
        await test_db.execute(
            update(User).where(User.email == signup_data["email"]).values(is_verified=True)
        )
        await test_db.commit()
        
        response = await test_client.post("/auth/signin", json={
            "email": signup_data["email"],
            "password": signup_data["password"]
        })
        
        assert response.status_code == 200
        tokens = response.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
    
    async def test_forgot_password_without_authentication_succeeds(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test that forgot password endpoint is accessible without authentication.
        Validates: Requirements 6.6
        """
        signup_data = {
            "email": "publicforgot@example.com",
            "password": "SecurePass123",
            "full_name": "Public Forgot User"
        }
        
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            await test_client.post("/auth/signup", json=signup_data)
        
        await test_db.execute(
            update(User).where(User.email == signup_data["email"]).values(is_verified=True)
        )
        await test_db.commit()
        
        with patch.object(EmailService, 'send_password_reset_email', new_callable=AsyncMock):
            response = await test_client.post("/auth/forgot-password", json={
                "email": signup_data["email"]
            })
        
        assert response.status_code == 200
    
    async def test_oauth_initiation_without_authentication_succeeds(
        self,
        test_client: AsyncClient
    ):
        """
        Test that OAuth initiation endpoint is accessible without authentication.
        Validates: Requirements 6.6
        """
        response = await test_client.get("/auth/oauth/google")
        
        assert response.status_code == 307  # Redirect
        assert "location" in response.headers
    
    async def test_verify_email_without_authentication_succeeds(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test that email verification endpoint is accessible without authentication.
        Validates: Requirements 6.6
        """
        signup_data = {
            "email": "publicverify@example.com",
            "password": "SecurePass123",
            "full_name": "Public Verify User"
        }
        
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            await test_client.post("/auth/signup", json=signup_data)
        
        from app.models.email_verification import EmailVerificationToken
        result = await test_db.execute(
            select(EmailVerificationToken)
            .join(User)
            .where(User.email == signup_data["email"])
        )
        verification_token = result.scalar_one()
        
        response = await test_client.post(
            f"/auth/verify-email?token={verification_token.token}"
        )
        
        assert response.status_code == 200
    
    async def test_refresh_token_without_authentication_succeeds(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test that refresh token endpoint is accessible without authentication.
        Validates: Requirements 6.6
        """
        signup_data = {
            "email": "publicrefresh@example.com",
            "password": "SecurePass123",
            "full_name": "Public Refresh User"
        }
        
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            await test_client.post("/auth/signup", json=signup_data)
        
        await test_db.execute(
            update(User).where(User.email == signup_data["email"]).values(is_verified=True)
        )
        await test_db.commit()
        
        signin_response = await test_client.post("/auth/signin", json={
            "email": signup_data["email"],
            "password": signup_data["password"]
        })
        tokens = signin_response.json()
        
        response = await test_client.post("/auth/refresh", json={
            "refresh_token": tokens["refresh_token"]
        })
        
        assert response.status_code == 200
        new_tokens = response.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
