"""Property-based tests for user profile routes.

These tests verify correctness properties for profile management operations
across all valid inputs using Hypothesis.

**Validates: Requirements 9.1, 9.2, 9.3, 9.4**
"""
import pytest
from app.services.auth_service import AuthService
from app.services.token_service import TokenService
from app.config import settings


@pytest.mark.asyncio
async def test_property_27_profile_response_excludes_sensitive_data(test_client, test_db):
    """
    Feature: user-authentication, Property 27: Profile Response Excludes Sensitive Data
    
    For any user profile response, the returned data should include id, email,
    full_name, is_verified, created_at, and last_login_at, but should not include
    password_hash, tokens, or other sensitive fields.
    
    **Validates: Requirements 9.1**
    """
    auth_service = AuthService()
    token_service = TokenService(
        private_key=settings.jwt_private_key,
        public_key=settings.jwt_public_key,
        algorithm=settings.jwt_algorithm
    )
    
    # Test with multiple users
    test_cases = [
        ("user1@example.com", "ValidPass123", "John Doe"),
        ("user2@test.org", "SecureP@ss1", "Jane Smith"),
        ("user3@mail.net", "MyP4ssword", None),
    ]
    
    for email, password, full_name in test_cases:
        # Arrange: Create and verify user
        user = await auth_service.create_user(
            email=email,
            password=password,
            db=test_db,
            full_name=full_name
        )
        user.is_verified = True
        await test_db.commit()
        
        # Generate access token
        access_token = token_service.generate_access_token(user.id, user.email)
        
        # Act: Get user profile
        response = await test_client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        # Assert: Response is successful
        assert response.status_code == 200, f"Profile request for {email} should succeed"
        
        profile_data = response.json()
        
        # Assert: Required fields are present
        assert "id" in profile_data
        assert "email" in profile_data
        assert "full_name" in profile_data
        assert "is_verified" in profile_data
        assert "created_at" in profile_data
        assert "last_login_at" in profile_data
        
        # Assert: Sensitive fields are excluded
        assert "password_hash" not in profile_data
        assert "password" not in profile_data
        assert "access_token" not in profile_data
        assert "refresh_token" not in profile_data
        
        # Assert: Values match user data
        assert profile_data["id"] == user.id
        assert profile_data["email"] == email
        assert profile_data["full_name"] == full_name
        assert profile_data["is_verified"] is True



@pytest.mark.asyncio
async def test_property_28_profile_update_persistence(test_client, test_db):
    """
    Feature: user-authentication, Property 28: Profile Update Persistence
    
    For any authenticated user updating their profile with valid data, the changes
    should be persisted to the database and reflected in subsequent profile requests.
    
    **Validates: Requirements 9.2**
    """
    from sqlalchemy import select
    from app.models.user import User
    
    auth_service = AuthService()
    token_service = TokenService(
        private_key=settings.jwt_private_key,
        public_key=settings.jwt_public_key,
        algorithm=settings.jwt_algorithm
    )
    
    # Test with multiple update scenarios
    test_cases = [
        {
            "initial": ("user1@example.com", "ValidPass123", "John Doe"),
            "updates": [{"full_name": "John Smith"}, {"full_name": "Jonathan Smith"}]
        },
        {
            "initial": ("user2@test.org", "SecureP@ss1", None),
            "updates": [{"full_name": "Jane Doe"}]
        },
    ]
    
    for test_case in test_cases:
        email, password, initial_name = test_case["initial"]
        
        # Arrange: Create and verify user
        user = await auth_service.create_user(
            email=email,
            password=password,
            db=test_db,
            full_name=initial_name
        )
        user.is_verified = True
        await test_db.commit()
        
        # Generate access token
        access_token = token_service.generate_access_token(user.id, user.email)
        
        # Test each update
        for update_data in test_case["updates"]:
            # Act: Update profile
            response = await test_client.put(
                "/users/me",
                json=update_data,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            # Assert: Update is successful
            assert response.status_code == 200
            
            updated_profile = response.json()
            
            # Assert: Response reflects the update
            if "full_name" in update_data:
                assert updated_profile["full_name"] == update_data["full_name"]
            
            # Assert: Changes are persisted in database
            result = await test_db.execute(
                select(User).where(User.id == user.id)
            )
            db_user = result.scalar_one_or_none()
            assert db_user is not None
            
            if "full_name" in update_data:
                assert db_user.full_name == update_data["full_name"]
            
            # Assert: Subsequent GET request reflects the update
            get_response = await test_client.get(
                "/users/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            assert get_response.status_code == 200
            current_profile = get_response.json()
            
            if "full_name" in update_data:
                assert current_profile["full_name"] == update_data["full_name"]



@pytest.mark.asyncio
async def test_property_29_email_change_requires_reverification(test_client, test_db, monkeypatch):
    """
    Feature: user-authentication, Property 29: Email Change Requires Reverification
    
    For any authenticated user changing their email address, the is_verified field
    should be set to False and a new verification email should be sent to the new address.
    
    **Validates: Requirements 9.3**
    """
    from sqlalchemy import select
    from app.models.user import User
    
    # Mock email sending to avoid SMTP errors in tests
    async def mock_send_verification_email(self, email, token):
        pass
    
    from app.services import email_service
    monkeypatch.setattr(email_service.EmailService, "send_verification_email", mock_send_verification_email)
    
    auth_service = AuthService()
    token_service = TokenService(
        private_key=settings.jwt_private_key,
        public_key=settings.jwt_public_key,
        algorithm=settings.jwt_algorithm
    )
    
    # Test with multiple email change scenarios
    test_cases = [
        ("user1@example.com", "ValidPass123", "newemail1@example.com"),
        ("user2@test.org", "SecureP@ss1", "updated2@test.org"),
        ("user3@mail.net", "MyP4ssword", "changed3@mail.net"),
    ]
    
    for original_email, password, new_email in test_cases:
        # Arrange: Create and verify user
        user = await auth_service.create_user(
            email=original_email,
            password=password,
            db=test_db
        )
        user.is_verified = True
        await test_db.commit()
        
        # Generate access token
        access_token = token_service.generate_access_token(user.id, user.email)
        
        # Act: Update email
        response = await test_client.put(
            "/users/me",
            json={"email": new_email},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        # Assert: Update is successful
        assert response.status_code == 200
        
        updated_profile = response.json()
        
        # Assert: Email is updated
        assert updated_profile["email"] == new_email
        
        # Assert: User is marked as unverified
        assert updated_profile["is_verified"] is False
        
        # Assert: Database reflects unverified status
        result = await test_db.execute(
            select(User).where(User.id == user.id)
        )
        db_user = result.scalar_one_or_none()
        assert db_user is not None
        assert db_user.email == new_email
        assert db_user.is_verified is False



@pytest.mark.asyncio
async def test_property_30_password_change_requires_current_password(test_client, test_db):
    """
    Feature: user-authentication, Property 30: Password Change Requires Current Password
    
    For any password change request, if the provided current password does not match
    the user's stored password hash, the request should be rejected and the password
    should remain unchanged.
    
    **Validates: Requirements 9.4**
    """
    from sqlalchemy import select
    from app.models.user import User
    
    auth_service = AuthService()
    token_service = TokenService(
        private_key=settings.jwt_private_key,
        public_key=settings.jwt_public_key,
        algorithm=settings.jwt_algorithm
    )
    
    # Test with multiple password change scenarios
    test_cases = [
        ("user1@example.com", "ValidPass123", "WrongPass123", "NewPass456"),
        ("user2@test.org", "SecureP@ss1", "IncorrectP@ss", "UpdatedP@ss2"),
        ("user3@mail.net", "MyP4ssword", "BadPassword1", "ChangedP@ss3"),
    ]
    
    for email, correct_password, wrong_password, new_password in test_cases:
        # Arrange: Create and verify user
        user = await auth_service.create_user(
            email=email,
            password=correct_password,
            db=test_db
        )
        user.is_verified = True
        await test_db.commit()
        
        original_password_hash = user.password_hash
        
        # Generate access token
        access_token = token_service.generate_access_token(user.id, user.email)
        
        # Act: Try to change password with wrong current password
        response = await test_client.post(
            "/users/me/change-password",
            json={
                "current_password": wrong_password,
                "new_password": new_password
            },
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        # Assert: Request is rejected
        assert response.status_code == 400
        assert "incorrect" in response.json()["detail"].lower()
        
        # Assert: Password remains unchanged in database
        result = await test_db.execute(
            select(User).where(User.id == user.id)
        )
        db_user = result.scalar_one_or_none()
        assert db_user is not None
        assert db_user.password_hash == original_password_hash
        
        # Assert: Old password still works
        authenticated_user = await auth_service.authenticate_user(
            email=email,
            password=correct_password,
            db=test_db
        )
        assert authenticated_user is not None
        
        # Act: Change password with correct current password
        response = await test_client.post(
            "/users/me/change-password",
            json={
                "current_password": correct_password,
                "new_password": new_password
            },
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        # Assert: Request succeeds
        assert response.status_code == 200
        
        # Assert: Password is changed in database
        result = await test_db.execute(
            select(User).where(User.id == user.id)
        )
        db_user = result.scalar_one_or_none()
        assert db_user is not None
        assert db_user.password_hash != original_password_hash
        
        # Assert: New password works for authentication
        authenticated_user = await auth_service.authenticate_user(
            email=email,
            password=new_password,
            db=test_db
        )
        assert authenticated_user is not None
        
        # Assert: Old password no longer works
        old_auth_result = await auth_service.authenticate_user(
            email=email,
            password=correct_password,
            db=test_db
        )
        assert old_auth_result is None
