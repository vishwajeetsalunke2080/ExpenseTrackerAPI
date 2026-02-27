"""Unit tests for AuthService."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import select

from app.services.auth_service import AuthService
from app.models.user import User
from app.models.email_verification import EmailVerificationToken
from app.models.password_reset import PasswordResetToken


@pytest.mark.asyncio
class TestAuthService:
    """Test suite for AuthService."""
    
    async def test_hash_password(self):
        """Test password hashing produces valid bcrypt hash."""
        service = AuthService()
        password = "TestPassword123"
        
        hashed = service.hash_password(password)
        
        # Hash should not equal original password
        assert hashed != password
        # Hash should be a valid bcrypt hash (starts with $2b$)
        assert hashed.startswith("$2b$")
        # Hash should contain cost factor 12
        assert "$2b$12$" in hashed
    
    async def test_verify_password_correct(self):
        """Test password verification with correct password."""
        service = AuthService()
        password = "TestPassword123"
        hashed = service.hash_password(password)
        
        result = service.verify_password(password, hashed)
        
        assert result is True
    
    async def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        service = AuthService()
        password = "TestPassword123"
        wrong_password = "WrongPassword456"
        hashed = service.hash_password(password)
        
        result = service.verify_password(wrong_password, hashed)
        
        assert result is False
    
    async def test_validate_password_strength_valid(self):
        """Test password strength validation with valid password."""
        service = AuthService()
        
        # Valid password: 8+ chars, uppercase, lowercase, number
        assert service.validate_password_strength("ValidPass123") is True
        assert service.validate_password_strength("Abcdefg1") is True
        assert service.validate_password_strength("MyP@ssw0rd") is True
    
    async def test_validate_password_strength_too_short(self):
        """Test password strength validation with too short password."""
        service = AuthService()
        
        # Less than 8 characters
        assert service.validate_password_strength("Pass1") is False
        assert service.validate_password_strength("Abc123") is False
    
    async def test_validate_password_strength_no_uppercase(self):
        """Test password strength validation without uppercase."""
        service = AuthService()
        
        # No uppercase letter
        assert service.validate_password_strength("password123") is False
    
    async def test_validate_password_strength_no_lowercase(self):
        """Test password strength validation without lowercase."""
        service = AuthService()
        
        # No lowercase letter
        assert service.validate_password_strength("PASSWORD123") is False
    
    async def test_validate_password_strength_no_number(self):
        """Test password strength validation without number."""
        service = AuthService()
        
        # No number
        assert service.validate_password_strength("PasswordOnly") is False
    
    async def test_create_user_success(self, db_session):
        """Test successful user creation."""
        service = AuthService()
        email = "test@example.com"
        password = "ValidPass123"
        
        user = await service.create_user(email, password, db_session)
        
        assert user.id is not None
        assert user.email == email
        assert user.password_hash != password
        assert user.is_verified is False
        assert user.is_active is True
        
        # Verify user was saved to database
        result = await db_session.execute(
            select(User).where(User.email == email)
        )
        db_user = result.scalar_one_or_none()
        assert db_user is not None
        assert db_user.email == email
    
    async def test_create_user_with_full_name(self, db_session):
        """Test user creation with full name."""
        service = AuthService()
        email = "test@example.com"
        password = "ValidPass123"
        full_name = "Test User"
        
        user = await service.create_user(email, password, db_session, full_name=full_name)
        
        assert user.full_name == full_name
    
    async def test_create_user_generates_verification_token(self, db_session):
        """Test that user creation generates verification token."""
        service = AuthService()
        email = "test@example.com"
        password = "ValidPass123"
        
        user = await service.create_user(email, password, db_session)
        
        # Check verification token was created
        result = await db_session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user.id
            )
        )
        token = result.scalar_one_or_none()
        assert token is not None
        assert token.used is False
        assert token.expires_at > datetime.utcnow()
    
    async def test_create_user_weak_password(self, db_session):
        """Test user creation with weak password fails."""
        service = AuthService()
        email = "test@example.com"
        weak_password = "weak"
        
        with pytest.raises(ValueError, match="Password must be at least 8 characters"):
            await service.create_user(email, weak_password, db_session)
    
    async def test_create_user_duplicate_email(self, db_session):
        """Test user creation with duplicate email fails."""
        service = AuthService()
        email = "test@example.com"
        password = "ValidPass123"
        
        # Create first user
        await service.create_user(email, password, db_session)
        
        # Try to create second user with same email
        with pytest.raises(ValueError, match="Email already exists"):
            await service.create_user(email, password, db_session)
    
    async def test_authenticate_user_success(self, db_session):
        """Test successful user authentication."""
        service = AuthService()
        email = "test@example.com"
        password = "ValidPass123"
        
        # Create and verify user
        user = await service.create_user(email, password, db_session)
        user.is_verified = True
        await db_session.commit()
        
        # Authenticate
        authenticated_user = await service.authenticate_user(email, password, db_session)
        
        assert authenticated_user is not None
        assert authenticated_user.id == user.id
        assert authenticated_user.email == email
        assert authenticated_user.last_login_at is not None
    
    async def test_authenticate_user_wrong_password(self, db_session):
        """Test authentication with wrong password."""
        service = AuthService()
        email = "test@example.com"
        password = "ValidPass123"
        wrong_password = "WrongPass456"
        
        # Create and verify user
        user = await service.create_user(email, password, db_session)
        user.is_verified = True
        await db_session.commit()
        
        # Try to authenticate with wrong password
        authenticated_user = await service.authenticate_user(email, wrong_password, db_session)
        
        assert authenticated_user is None
    
    async def test_authenticate_user_nonexistent_email(self, db_session):
        """Test authentication with nonexistent email."""
        service = AuthService()
        
        authenticated_user = await service.authenticate_user(
            "nonexistent@example.com",
            "SomePass123",
            db_session
        )
        
        assert authenticated_user is None
    
    async def test_authenticate_user_unverified_email(self, db_session):
        """Test authentication with unverified email fails."""
        service = AuthService()
        email = "test@example.com"
        password = "ValidPass123"
        
        # Create user (unverified by default)
        await service.create_user(email, password, db_session)
        
        # Try to authenticate
        with pytest.raises(ValueError, match="Email verification required"):
            await service.authenticate_user(email, password, db_session)
    
    async def test_verify_email_success(self, db_session):
        """Test successful email verification."""
        service = AuthService()
        email = "test@example.com"
        password = "ValidPass123"
        
        # Create user
        user = await service.create_user(email, password, db_session)
        
        # Get verification token
        result = await db_session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user.id
            )
        )
        token_record = result.scalar_one()
        
        # Verify email
        success = await service.verify_email(token_record.token, db_session)
        
        assert success is True
        
        # Check user is verified
        await db_session.refresh(user)
        assert user.is_verified is True
        
        # Check token is marked as used
        await db_session.refresh(token_record)
        assert token_record.used is True
    
    async def test_verify_email_invalid_token(self, db_session):
        """Test email verification with invalid token."""
        service = AuthService()
        
        success = await service.verify_email("invalid_token", db_session)
        
        assert success is False
    
    async def test_verify_email_expired_token(self, db_session):
        """Test email verification with expired token."""
        service = AuthService()
        email = "test@example.com"
        password = "ValidPass123"
        
        # Create user
        user = await service.create_user(email, password, db_session)
        
        # Get and expire verification token
        result = await db_session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user.id
            )
        )
        token_record = result.scalar_one()
        token_record.expires_at = datetime.utcnow() - timedelta(hours=1)
        await db_session.commit()
        
        # Try to verify with expired token
        success = await service.verify_email(token_record.token, db_session)
        
        assert success is False
    
    async def test_initiate_password_reset_success(self, db_session):
        """Test successful password reset initiation."""
        service = AuthService()
        email = "test@example.com"
        password = "ValidPass123"
        
        # Create user
        user = await service.create_user(email, password, db_session)
        
        # Initiate password reset
        token = await service.initiate_password_reset(email, db_session)
        
        assert token is not None
        
        # Check token was saved to database
        result = await db_session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id
            )
        )
        token_record = result.scalar_one_or_none()
        assert token_record is not None
        assert token_record.token == token
        assert token_record.used is False
        assert token_record.expires_at > datetime.utcnow()
    
    async def test_initiate_password_reset_nonexistent_email(self, db_session):
        """Test password reset initiation with nonexistent email."""
        service = AuthService()
        
        token = await service.initiate_password_reset("nonexistent@example.com", db_session)
        
        # Should return None without revealing email doesn't exist
        assert token is None
    
    async def test_reset_password_success(self, db_session):
        """Test successful password reset."""
        service = AuthService()
        email = "test@example.com"
        old_password = "OldPass123"
        new_password = "NewPass456"
        
        # Create user
        user = await service.create_user(email, old_password, db_session)
        old_hash = user.password_hash
        
        # Initiate password reset
        token = await service.initiate_password_reset(email, db_session)
        
        # Reset password
        success = await service.reset_password(token, new_password, db_session)
        
        assert success is True
        
        # Check password was changed
        await db_session.refresh(user)
        assert user.password_hash != old_hash
        assert service.verify_password(new_password, user.password_hash) is True
        assert service.verify_password(old_password, user.password_hash) is False
    
    async def test_reset_password_invalid_token(self, db_session):
        """Test password reset with invalid token."""
        service = AuthService()
        
        success = await service.reset_password("invalid_token", "NewPass123", db_session)
        
        assert success is False
    
    async def test_reset_password_expired_token(self, db_session):
        """Test password reset with expired token."""
        service = AuthService()
        email = "test@example.com"
        password = "ValidPass123"
        
        # Create user and initiate reset
        user = await service.create_user(email, password, db_session)
        token = await service.initiate_password_reset(email, db_session)
        
        # Expire the token
        result = await db_session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token == token
            )
        )
        token_record = result.scalar_one()
        token_record.expires_at = datetime.utcnow() - timedelta(hours=1)
        await db_session.commit()
        
        # Try to reset with expired token
        success = await service.reset_password(token, "NewPass123", db_session)
        
        assert success is False
    
    async def test_reset_password_weak_password(self, db_session):
        """Test password reset with weak password."""
        service = AuthService()
        email = "test@example.com"
        password = "ValidPass123"
        
        # Create user and initiate reset
        await service.create_user(email, password, db_session)
        token = await service.initiate_password_reset(email, db_session)
        
        # Try to reset with weak password
        with pytest.raises(ValueError, match="Password must be at least 8 characters"):
            await service.reset_password(token, "weak", db_session)
    
    async def test_reset_password_revokes_all_refresh_tokens(self, db_session):
        """Test that password reset revokes all existing refresh tokens (Requirement 5.6)."""
        from app.services.token_service import TokenService
        from app.models.refresh_token import RefreshToken
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
        email = "test@example.com"
        old_password = "OldPass123"
        new_password = "NewPass456"
        
        # Create user
        user = await auth_service.create_user(email, old_password, db_session)
        
        # Generate multiple refresh tokens for the user
        refresh_token_1 = await token_service.generate_refresh_token(user.id, db_session)
        refresh_token_2 = await token_service.generate_refresh_token(user.id, db_session)
        refresh_token_3 = await token_service.generate_refresh_token(user.id, db_session)
        
        # Verify tokens exist and are not revoked
        result = await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.is_revoked == False
            )
        )
        active_tokens_before = result.scalars().all()
        assert len(active_tokens_before) == 3
        
        # Initiate and complete password reset
        reset_token = await auth_service.initiate_password_reset(email, db_session)
        success = await auth_service.reset_password(reset_token, new_password, db_session)
        
        assert success is True
        
        # Verify all refresh tokens are now revoked
        result = await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.is_revoked == False
            )
        )
        active_tokens_after = result.scalars().all()
        assert len(active_tokens_after) == 0
        
        # Verify all tokens are marked as revoked
        result = await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.is_revoked == True
            )
        )
        revoked_tokens = result.scalars().all()
        assert len(revoked_tokens) == 3

    async def test_resend_verification_email_success(self, db_session):
        """Test resending verification email for unverified user."""
        service = AuthService()
        
        # Create unverified user with initial token
        user = await service.create_user(
            email="test@example.com",
            password="TestPass123",
            db=db_session
        )
        
        # Get the initial token
        result = await db_session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used == False
            )
        )
        initial_token = result.scalar_one()
        initial_token_value = initial_token.token
        
        # Resend verification email
        new_token = await service.resend_verification_email(
            email="test@example.com",
            db=db_session
        )
        
        # Should return a new token
        assert new_token is not None
        assert new_token != initial_token_value
        
        # Old token should be marked as used
        await db_session.refresh(initial_token)
        assert initial_token.used is True
        
        # New token should exist and be unused
        result = await db_session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token == new_token,
                EmailVerificationToken.used == False
            )
        )
        new_token_record = result.scalar_one()
        assert new_token_record is not None
        assert new_token_record.user_id == user.id
    
    async def test_resend_verification_email_already_verified(self, db_session):
        """Test resending verification email for already verified user."""
        service = AuthService()
        
        # Create and verify user
        user = await service.create_user(
            email="test@example.com",
            password="TestPass123",
            db=db_session
        )
        user.is_verified = True
        await db_session.commit()
        
        # Try to resend verification email
        new_token = await service.resend_verification_email(
            email="test@example.com",
            db=db_session
        )
        
        # Should return None for already verified user
        assert new_token is None
    
    async def test_resend_verification_email_nonexistent_user(self, db_session):
        """Test resending verification email for nonexistent user."""
        service = AuthService()
        
        # Try to resend for nonexistent email
        new_token = await service.resend_verification_email(
            email="nonexistent@example.com",
            db=db_session
        )
        
        # Should return None without revealing user doesn't exist
        assert new_token is None
