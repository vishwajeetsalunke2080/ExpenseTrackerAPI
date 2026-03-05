"""Authentication service for user management and authentication.

This service handles user registration, authentication, email verification,
and password reset functionality. It implements secure password hashing
using bcrypt and manages verification/reset tokens.

Requirements: 1.1, 1.3, 1.4, 1.6, 2.1, 2.2, 2.3, 2.6
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.email_verification import EmailVerificationToken
from app.models.password_reset import PasswordResetToken
from app.services.token_service import TokenService


class AuthService:
    """Service for handling authentication operations.
    
    Provides methods for user creation, authentication, password management,
    and email verification. Uses bcrypt with cost factor 12 for password hashing.
    """
    
    # Bcrypt cost factor for password hashing (Requirement 1.4)
    BCRYPT_COST_FACTOR = 12
    
    async def create_user(
        self,
        email: str,
        password: str,
        db: AsyncSession,
        full_name: Optional[str] = None
    ) -> User:
        """Create a new user account with email and password.
        
        Validates password strength, hashes the password, creates the user record,
        and generates a verification token. The user starts in an unverified state.
        
        Requirements: 1.1, 1.3, 1.4, 1.6
        
        Args:
            email: User's email address
            password: Plain text password
            db: Database session
            full_name: Optional user's full name
            
        Returns:
            Created User object
            
        Raises:
            ValueError: If password doesn't meet strength requirements
            IntegrityError: If email already exists
        """
        # Validate password strength (Requirement 1.3)
        if not self.validate_password_strength(password):
            raise ValueError(
                "Password must be at least 8 characters and contain "
                "uppercase, lowercase, and number"
            )
        
        # Hash the password (Requirement 1.4)
        password_hash = self.hash_password(password)
        
        # Create user with unverified status (Requirement 1.6)
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            is_verified=False,
            is_active=True
        )
        
        try:
            db.add(user)
            await db.flush()  # Flush to get user.id for token generation
            
            # Generate verification token (Requirement 1.5, 7.1)
            verification_token = await self._generate_verification_token(user.id, db)
            
            # Don't commit here - let the endpoint handle the commit
            await db.refresh(user)
            
            return user
            
        except IntegrityError:
            await db.rollback()
            raise ValueError("Email already registered")
    
    async def authenticate_user(
        self,
        email: str,
        password: str,
        db: AsyncSession
    ) -> Optional[User]:
        """Authenticate a user with email and password.
        
        Looks up the user by email, verifies the password hash, and checks
        email verification status. Returns None if authentication fails.
        
        Requirements: 2.1, 2.2, 2.3, 2.6
        
        Args:
            email: User's email address
            password: Plain text password
            db: Database session
            
        Returns:
            User object if authentication succeeds, None otherwise
            
        Raises:
            ValueError: If email is not verified
        """
        # Lookup user by email (Requirement 2.1)
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        # Check if user has a password (OAuth-only users don't)
        if not user.password_hash:
            return None
        
        # Verify password hash (Requirement 2.3)
        if not self.verify_password(password, user.password_hash):
            return None
        
        # Check email verification status (Requirement 2.6)
        if not user.is_verified:
            raise ValueError("Email verification required")
        
        # Check if account is active
        if not user.is_active:
            return None
        
        # Update last login timestamp
        user.last_login_at = datetime.now(timezone.utc)
        # Don't commit here - let the endpoint handle it
        
        return user
    
    async def verify_email(
        self,
        token: str,
        db: AsyncSession
    ) -> bool:
        """Verify a user's email address using a verification token.
        
        Validates the token, checks expiration, marks the user as verified,
        and marks the token as used.
        
        Requirements: 7.3, 7.4
        
        Args:
            token: Email verification token
            db: Database session
            
        Returns:
            True if verification succeeds, False otherwise
        """
        # Find the token
        result = await db.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token == token,
                EmailVerificationToken.used == False
            )
        )
        verification_token = result.scalar_one_or_none()
        
        if not verification_token:
            return False
        
        # Check if token is expired
        if datetime.now(timezone.utc) > verification_token.expires_at:
            return False
        
        # Mark user as verified
        user_result = await db.execute(
            select(User).where(User.id == verification_token.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return False
        
        user.is_verified = True
        verification_token.used = True
        
        # Don't commit here - let the endpoint handle it
        
        return True
    
    async def resend_verification_email(
        self,
        email: str,
        db: AsyncSession
    ) -> Optional[str]:
        """Resend verification email to a user.
        
        Generates a new verification token, invalidates old unused tokens,
        and returns the new token for email sending.
        
        Requirements: 7.5
        
        Args:
            email: User's email address
            db: Database session
            
        Returns:
            New verification token if user exists and is unverified, None otherwise
        """
        # Find user by email
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Don't reveal if email exists (security best practice)
            return None
        
        # Only allow resending for unverified users
        if user.is_verified:
            return None
        
        # Invalidate all existing unused verification tokens for this user
        existing_tokens_result = await db.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used == False
            )
        )
        existing_tokens = existing_tokens_result.scalars().all()
        
        for token in existing_tokens:
            token.used = True
        
        # Generate new verification token
        new_token = await self._generate_verification_token(user.id, db)
        
        # Don't commit here - let the endpoint handle it
        
        return new_token
    
    async def initiate_password_reset(
        self,
        email: str,
        db: AsyncSession
    ) -> Optional[str]:
        """Initiate password reset process for a user.
        
        Generates a password reset token and stores it in the database.
        Returns the token if the user exists, None otherwise.
        
        Requirements: 5.1, 5.3
        
        Args:
            email: User's email address
            db: Database session
            
        Returns:
            Password reset token if user exists, None otherwise
        """
        # Find user by email
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Don't reveal if email exists (security best practice)
            return None
        
        # Generate password reset token
        token = self._generate_password_reset_token()
        
        # Store token in database with 1-hour expiration (Requirement 5.3)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used=False
        )
        
        db.add(reset_token)
        await db.flush()  # Flush to persist but don't commit
        
        return token
    
    async def reset_password(
        self,
        token: str,
        new_password: str,
        db: AsyncSession
    ) -> bool:
        """Reset a user's password using a reset token.
        
        Validates the token, checks expiration, validates new password strength,
        updates the password hash, marks the token as used, and revokes all
        existing refresh tokens for security.
        
        Requirements: 5.4, 5.5, 5.6, 1.3
        
        Args:
            token: Password reset token
            new_password: New plain text password
            db: Database session
            
        Returns:
            True if password reset succeeds, False otherwise
            
        Raises:
            ValueError: If new password doesn't meet strength requirements
        """
        # Find the token
        result = await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token == token,
                PasswordResetToken.used == False
            )
        )
        reset_token = result.scalar_one_or_none()
        
        if not reset_token:
            return False
        
        # Check if token is expired (Requirement 5.5)
        if datetime.now(timezone.utc) > reset_token.expires_at:
            return False
        
        # Validate new password strength (Requirement 1.3)
        if not self.validate_password_strength(new_password):
            raise ValueError(
                "Password must be at least 8 characters and contain "
                "uppercase, lowercase, and number"
            )
        
        # Hash new password
        new_password_hash = self.hash_password(new_password)
        
        # Update user's password
        user_result = await db.execute(
            select(User).where(User.id == reset_token.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return False
        
        user.password_hash = new_password_hash
        reset_token.used = True
        
        # Revoke all existing refresh tokens for security (Requirement 5.6)
        from app.config import settings
        token_service = TokenService(
            private_key=settings.jwt_private_key,
            public_key=settings.jwt_public_key,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )
        await token_service.revoke_all_user_tokens(reset_token.user_id, db)
        
        # Don't commit here - let the endpoint handle it
        
        return True
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt with cost factor 12.
        
        Requirements: 1.4
        
        Args:
            password: Plain text password
            
        Returns:
            Bcrypt password hash as string
        """
        # Generate salt and hash password with cost factor 12
        salt = bcrypt.gensalt(rounds=self.BCRYPT_COST_FACTOR)
        password_bytes = password.encode('utf-8')
        hashed = bcrypt.hashpw(password_bytes, salt)
        
        # Return as string for database storage
        return hashed.decode('utf-8')
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a bcrypt hash.
        
        Uses constant-time comparison to prevent timing attacks.
        
        Requirements: 2.3
        
        Args:
            plain_password: Plain text password to verify
            hashed_password: Bcrypt hash to verify against
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            password_bytes = plain_password.encode('utf-8')
            hashed_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except Exception:
            # Handle any bcrypt errors (invalid hash format, etc.)
            return False
    
    def validate_password_strength(self, password: str) -> bool:
        """Validate that a password meets security requirements.
        
        Password must:
        - Be at least 8 characters long
        - Contain at least one uppercase letter
        - Contain at least one lowercase letter
        - Contain at least one number
        
        Requirements: 1.3
        
        Args:
            password: Password to validate
            
        Returns:
            True if password meets requirements, False otherwise
        """
        if len(password) < 8:
            return False
        
        has_uppercase = any(c.isupper() for c in password)
        has_lowercase = any(c.islower() for c in password)
        has_number = any(c.isdigit() for c in password)
        
        return has_uppercase and has_lowercase and has_number
    
    async def _generate_verification_token(self, user_id: int, db: AsyncSession) -> str:
        """Generate a unique email verification token.
        
        Token expires after 24 hours.
        
        Requirements: 7.1, 7.6
        
        Args:
            user_id: User ID to associate with token
            db: Database session
            
        Returns:
            Generated verification token
        """
        token = secrets.token_urlsafe(32)
        
        verification_token = EmailVerificationToken(
            user_id=user_id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            used=False
        )
        
        db.add(verification_token)
        
        return token
    
    def _generate_password_reset_token(self) -> str:
        """Generate a cryptographically secure password reset token.
        
        Requirements: 5.1, 10.5
        
        Returns:
            Generated password reset token
        """
        return secrets.token_urlsafe(32)
