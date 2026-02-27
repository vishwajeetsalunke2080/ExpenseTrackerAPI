"""Integration tests for complete authentication flows.

Tests complete end-to-end authentication workflows including:
- Signup → Verify Email → Signin flow
- Password reset flow
- OAuth flow with mocked provider
- Token refresh flow
- Session revocation flow
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch
from sqlalchemy import select, update

from app.models.user import User
from app.models.email_verification import EmailVerificationToken
from app.models.password_reset import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.services.email_service import EmailService


@pytest.mark.asyncio
class TestCompleteSignupVerifySigninFlow:
    """Test complete signup → verify email → signin flow."""
    
    async def test_complete_signup_verification_signin_flow(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test complete flow: user signs up, verifies email, then signs in.
        Validates: All requirements
        """
        # Step 1: Sign up
        signup_data = {
            "email": "newuser@example.com",
            "password": "SecurePass123",
            "full_name": "New User"
        }
        
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock) as mock_email:
            signup_response = await test_client.post("/auth/signup", json=signup_data)
        
        assert signup_response.status_code == 201
        signup_result = signup_response.json()
        assert signup_result["email"] == signup_data["email"]
        assert signup_result["is_verified"] is False
        assert mock_email.called
        
        # Step 2: Attempt to sign in before verification (should fail)
        signin_data = {
            "email": signup_data["email"],
            "password": signup_data["password"]
        }
        
        signin_response = await test_client.post("/auth/signin", json=signin_data)
        assert signin_response.status_code == 401
        assert "EMAIL_NOT_VERIFIED" in signin_response.json()["error_code"]
        
        # Step 3: Get verification token from database
        result = await test_db.execute(
            select(EmailVerificationToken)
            .join(User)
            .where(User.email == signup_data["email"])
        )
        verification_token = result.scalar_one()
        
        # Step 4: Verify email
        verify_response = await test_client.post(
            f"/auth/verify-email?token={verification_token.token}"
        )
        assert verify_response.status_code == 200
        
        # Step 5: Sign in after verification (should succeed)
        signin_response = await test_client.post("/auth/signin", json=signin_data)
        assert signin_response.status_code == 200
        signin_result = signin_response.json()
        assert "access_token" in signin_result
        assert "refresh_token" in signin_result
        assert signin_result["token_type"] == "bearer"
        
        # Step 6: Access protected route with token
        headers = {"Authorization": f"Bearer {signin_result['access_token']}"}
        profile_response = await test_client.get("/users/me", headers=headers)
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["email"] == signup_data["email"]
        assert profile_data["is_verified"] is True


@pytest.mark.asyncio
class TestCompletePasswordResetFlow:
    """Test complete password reset flow."""
    
    async def test_complete_password_reset_flow(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test complete password reset flow: request → receive token → reset password → signin.
        Validates: All requirements
        """
        # Step 1: Create and verify a user
        signup_data = {
            "email": "resetuser@example.com",
            "password": "OldPassword123",
            "full_name": "Reset User"
        }
        
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            await test_client.post("/auth/signup", json=signup_data)
        
        # Manually verify the user
        await test_db.execute(
            update(User)
            .where(User.email == signup_data["email"])
            .values(is_verified=True)
        )
        await test_db.commit()
        
        # Step 2: Sign in with old password (should work)
        signin_response = await test_client.post("/auth/signin", json={
            "email": signup_data["email"],
            "password": signup_data["password"]
        })
        assert signin_response.status_code == 200
        old_tokens = signin_response.json()
        
        # Step 3: Request password reset
        with patch.object(EmailService, 'send_password_reset_email', new_callable=AsyncMock) as mock_email:
            reset_request_response = await test_client.post(
                "/auth/forgot-password",
                json={"email": signup_data["email"]}
            )
        
        assert reset_request_response.status_code == 200
        assert mock_email.called
        
        # Step 4: Get reset token from database
        result = await test_db.execute(
            select(PasswordResetToken)
            .join(User)
            .where(User.email == signup_data["email"])
            .order_by(PasswordResetToken.created_at.desc())
        )
        reset_token = result.scalar_one()
        
        # Step 5: Reset password with token
        new_password = "NewSecurePass456"
        reset_response = await test_client.post("/auth/reset-password", json={
            "token": reset_token.token,
            "new_password": new_password
        })
        assert reset_response.status_code == 200
        
        # Step 6: Verify old tokens are invalidated
        headers = {"Authorization": f"Bearer {old_tokens['access_token']}"}
        profile_response = await test_client.get("/users/me", headers=headers)
        assert profile_response.status_code == 401
        
        # Step 7: Sign in with old password (should fail)
        signin_response = await test_client.post("/auth/signin", json={
            "email": signup_data["email"],
            "password": signup_data["password"]
        })
        assert signin_response.status_code == 401
        
        # Step 8: Sign in with new password (should work)
        signin_response = await test_client.post("/auth/signin", json={
            "email": signup_data["email"],
            "password": new_password
        })
        assert signin_response.status_code == 200
        new_tokens = signin_response.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens



@pytest.mark.asyncio
class TestCompleteOAuthFlow:
    """Test complete OAuth flow with mocked provider."""
    
    async def test_complete_oauth_flow_new_user(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test OAuth flow for a new user: initiate → callback → tokens.
        Validates: All requirements
        """
        provider = "google"
        
        # Step 1: Initiate OAuth (get authorization URL)
        oauth_init_response = await test_client.get(f"/auth/oauth/{provider}")
        assert oauth_init_response.status_code == 307  # Redirect
        assert "google.com" in oauth_init_response.headers["location"]
        
        # Step 2: Mock OAuth provider callback
        mock_oauth_user_info = {
            "id": "google_user_123",
            "email": "oauthuser@gmail.com",
            "name": "OAuth User",
            "verified_email": True
        }
        
        mock_token_response = {
            "access_token": "mock_google_access_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        with patch('app.services.oauth_service.OAuthService.exchange_code_for_token', 
                   new_callable=AsyncMock, return_value=mock_token_response["access_token"]) as mock_exchange, \
             patch('app.services.oauth_service.OAuthService.get_user_info',
                   new_callable=AsyncMock, return_value=mock_oauth_user_info) as mock_user_info:
            
            # Step 3: OAuth callback with authorization code
            callback_response = await test_client.get(
                f"/auth/oauth/{provider}/callback?code=mock_auth_code&state=mock_state"
            )
        
        assert callback_response.status_code == 200
        callback_result = callback_response.json()
        assert "access_token" in callback_result
        assert "refresh_token" in callback_result
        assert callback_result["token_type"] == "bearer"
        
        # Step 4: Verify user was created in database
        result = await test_db.execute(
            select(User).where(User.email == mock_oauth_user_info["email"])
        )
        user = result.scalar_one()
        assert user.email == mock_oauth_user_info["email"]
        assert user.is_verified is True  # OAuth users are auto-verified
        
        # Step 5: Verify OAuth account was linked
        from app.models.oauth_account import OAuthAccount
        result = await test_db.execute(
            select(OAuthAccount).where(OAuthAccount.user_id == user.id)
        )
        oauth_account = result.scalar_one()
        assert oauth_account.provider == provider
        assert oauth_account.provider_user_id == mock_oauth_user_info["id"]
        
        # Step 6: Access protected route with token
        headers = {"Authorization": f"Bearer {callback_result['access_token']}"}
        profile_response = await test_client.get("/users/me", headers=headers)
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["email"] == mock_oauth_user_info["email"]
    
    async def test_complete_oauth_flow_existing_user(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test OAuth flow for an existing user: should link to existing account.
        Validates: All requirements
        """
        provider = "google"
        
        # Step 1: Create existing user via OAuth
        mock_oauth_user_info = {
            "id": "google_user_456",
            "email": "existinguser@gmail.com",
            "name": "Existing User",
            "verified_email": True
        }
        
        with patch('app.services.oauth_service.OAuthService.exchange_code_for_token',
                   new_callable=AsyncMock, return_value="mock_token"), \
             patch('app.services.oauth_service.OAuthService.get_user_info',
                   new_callable=AsyncMock, return_value=mock_oauth_user_info):
            
            first_callback = await test_client.get(
                f"/auth/oauth/{provider}/callback?code=first_code&state=state1"
            )
        
        assert first_callback.status_code == 200
        first_tokens = first_callback.json()
        
        # Step 2: Sign in again with same OAuth account
        with patch('app.services.oauth_service.OAuthService.exchange_code_for_token',
                   new_callable=AsyncMock, return_value="mock_token_2"), \
             patch('app.services.oauth_service.OAuthService.get_user_info',
                   new_callable=AsyncMock, return_value=mock_oauth_user_info):
            
            second_callback = await test_client.get(
                f"/auth/oauth/{provider}/callback?code=second_code&state=state2"
            )
        
        assert second_callback.status_code == 200
        second_tokens = second_callback.json()
        
        # Step 3: Verify both tokens work and point to same user
        headers1 = {"Authorization": f"Bearer {first_tokens['access_token']}"}
        headers2 = {"Authorization": f"Bearer {second_tokens['access_token']}"}
        
        profile1 = await test_client.get("/users/me", headers=headers1)
        profile2 = await test_client.get("/users/me", headers=headers2)
        
        assert profile1.status_code == 200
        assert profile2.status_code == 200
        assert profile1.json()["id"] == profile2.json()["id"]
        assert profile1.json()["email"] == mock_oauth_user_info["email"]


@pytest.mark.asyncio
class TestTokenRefreshFlow:
    """Test token refresh flow."""
    
    async def test_complete_token_refresh_flow(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test token refresh flow: signin → use token → refresh → use new token.
        Validates: All requirements
        """
        # Step 1: Create and verify a user
        signup_data = {
            "email": "refreshuser@example.com",
            "password": "SecurePass123",
            "full_name": "Refresh User"
        }
        
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            await test_client.post("/auth/signup", json=signup_data)
        
        await test_db.execute(
            update(User)
            .where(User.email == signup_data["email"])
            .values(is_verified=True)
        )
        await test_db.commit()
        
        # Step 2: Sign in to get initial tokens
        signin_response = await test_client.post("/auth/signin", json={
            "email": signup_data["email"],
            "password": signup_data["password"]
        })
        assert signin_response.status_code == 200
        initial_tokens = signin_response.json()
        
        # Step 3: Use access token to access protected route
        headers = {"Authorization": f"Bearer {initial_tokens['access_token']}"}
        profile_response = await test_client.get("/users/me", headers=headers)
        assert profile_response.status_code == 200
        
        # Step 4: Refresh tokens
        refresh_response = await test_client.post("/auth/refresh", json={
            "refresh_token": initial_tokens["refresh_token"]
        })
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        assert new_tokens["access_token"] != initial_tokens["access_token"]
        assert new_tokens["refresh_token"] != initial_tokens["refresh_token"]
        
        # Step 5: Verify old refresh token is revoked
        old_refresh_response = await test_client.post("/auth/refresh", json={
            "refresh_token": initial_tokens["refresh_token"]
        })
        assert old_refresh_response.status_code == 401
        
        # Step 6: Use new access token to access protected route
        new_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
        new_profile_response = await test_client.get("/users/me", headers=new_headers)
        assert new_profile_response.status_code == 200
        assert new_profile_response.json()["email"] == signup_data["email"]


@pytest.mark.asyncio
class TestSessionRevocationFlow:
    """Test session revocation flow."""
    
    async def test_complete_signout_flow(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test signout flow: signin → signout → verify tokens revoked.
        Validates: All requirements
        """
        # Step 1: Create and verify a user
        signup_data = {
            "email": "signoutuser@example.com",
            "password": "SecurePass123",
            "full_name": "Signout User"
        }
        
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            await test_client.post("/auth/signup", json=signup_data)
        
        await test_db.execute(
            update(User)
            .where(User.email == signup_data["email"])
            .values(is_verified=True)
        )
        await test_db.commit()
        
        # Step 2: Sign in
        signin_response = await test_client.post("/auth/signin", json={
            "email": signup_data["email"],
            "password": signup_data["password"]
        })
        assert signin_response.status_code == 200
        tokens = signin_response.json()
        
        # Step 3: Verify access token works
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        profile_response = await test_client.get("/users/me", headers=headers)
        assert profile_response.status_code == 200
        
        # Step 4: Sign out
        signout_response = await test_client.post(
            "/auth/signout",
            json={"refresh_token": tokens["refresh_token"]},
            headers=headers
        )
        assert signout_response.status_code == 204
        
        # Step 5: Verify access token is revoked
        profile_response = await test_client.get("/users/me", headers=headers)
        assert profile_response.status_code == 401
        
        # Step 6: Verify refresh token is revoked
        refresh_response = await test_client.post("/auth/refresh", json={
            "refresh_token": tokens["refresh_token"]
        })
        assert refresh_response.status_code == 401
    
    async def test_revoke_all_sessions_flow(
        self,
        test_client: AsyncClient,
        test_db: AsyncSession
    ):
        """
        Test revoke all sessions: create multiple sessions → revoke all → verify all revoked.
        Validates: All requirements
        """
        # Step 1: Create and verify a user
        signup_data = {
            "email": "multisession@example.com",
            "password": "SecurePass123",
            "full_name": "Multi Session User"
        }
        
        with patch.object(EmailService, 'send_verification_email', new_callable=AsyncMock):
            await test_client.post("/auth/signup", json=signup_data)
        
        await test_db.execute(
            update(User)
            .where(User.email == signup_data["email"])
            .values(is_verified=True)
        )
        await test_db.commit()
        
        # Step 2: Create multiple sessions (sign in multiple times)
        sessions = []
        for i in range(3):
            signin_response = await test_client.post("/auth/signin", json={
                "email": signup_data["email"],
                "password": signup_data["password"]
            })
            assert signin_response.status_code == 200
            sessions.append(signin_response.json())
        
        # Step 3: Verify all sessions work
        for session in sessions:
            headers = {"Authorization": f"Bearer {session['access_token']}"}
            profile_response = await test_client.get("/users/me", headers=headers)
            assert profile_response.status_code == 200
        
        # Step 4: Revoke all sessions using first session
        headers = {"Authorization": f"Bearer {sessions[0]['access_token']}"}
        revoke_response = await test_client.post("/users/me/revoke-all-sessions", headers=headers)
        assert revoke_response.status_code == 200
        
        # Step 5: Verify all sessions are revoked
        for session in sessions:
            headers = {"Authorization": f"Bearer {session['access_token']}"}
            profile_response = await test_client.get("/users/me", headers=headers)
            assert profile_response.status_code == 401
        
        # Step 6: Verify all refresh tokens are revoked
        for session in sessions:
            refresh_response = await test_client.post("/auth/refresh", json={
                "refresh_token": session["refresh_token"]
            })
            assert refresh_response.status_code == 401
        
        # Step 7: Verify user can sign in again after revocation
        signin_response = await test_client.post("/auth/signin", json={
            "email": signup_data["email"],
            "password": signup_data["password"]
        })
        assert signin_response.status_code == 200
        new_tokens = signin_response.json()
        
        headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
        profile_response = await test_client.get("/users/me", headers=headers)
        assert profile_response.status_code == 200
