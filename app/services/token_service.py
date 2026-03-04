"""Token service for JWT and refresh token management.

This service handles all token-related operations including:
- JWT access token generation and validation (RS256)
- Refresh token generation and management
- Token revocation
- Verification and password reset token generation

Requirements: 2.4, 2.5, 4.1, 4.2, 4.3, 4.4, 5.1, 5.3, 7.1, 7.6, 8.1, 8.2, 8.4, 8.5, 10.5
"""
import jwt
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select

from app.models.refresh_token import RefreshToken
from app.models.email_verification import EmailVerificationToken
from app.models.password_reset import PasswordResetToken


class TokenService:
    """Service for managing JWT access tokens and refresh tokens.
    
    This service provides methods for:
    - Generating and validating JWT access tokens with RS256 signing
    - Creating and managing refresh tokens in the database
    - Revoking tokens for security purposes
    - Generating secure random tokens for email verification and password reset
    
    Note: RS256 private/public keys will be loaded from configuration.
    Until Task 11.4 generates the keys, this service will raise an error
    if RS256 operations are attempted without keys configured.
    """
    
    # Token expiration times
    ACCESS_TOKEN_EXPIRE_MINUTES = 15
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    VERIFICATION_TOKEN_EXPIRE_HOURS = 24
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS = 1
    
    def __init__(self, private_key: Optional[str] = None, public_key: Optional[str] = None, secret_key: Optional[str] = None, algorithm: str = "HS256"):
        """Initialize TokenService with keys for JWT signing.
        
        Args:
            private_key: RSA private key in PEM format for signing JWTs (RS256)
            public_key: RSA public key in PEM format for verifying JWTs (RS256)
            secret_key: Secret key for HS256 signing (temporary until Task 11.4)
            algorithm: JWT algorithm to use (HS256 or RS256)
        """
        self.private_key = private_key
        self.public_key = public_key
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def generate_access_token(self, user_id: int, email: str) -> str:
        """Generate a JWT access token with 15-minute expiration.
        
        Creates a JWT token signed with configured algorithm containing user
        identification information. The token expires after 15 minutes.
        
        Args:
            user_id: The user's database ID
            email: The user's email address
            
        Returns:
            str: Encoded JWT access token
            
        Raises:
            ValueError: If neither RSA private key nor secret key is configured
            
        Requirements: 2.4, 4.1
        """
        if self.algorithm == "RS256" and not self.private_key:
            raise ValueError("RSA private key not configured. Run Task 11.4 to generate keys.")
        if self.algorithm == "HS256" and not self.secret_key:
            raise ValueError("JWT secret key not configured.")
        
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        payload = {
            "sub": str(user_id),
            "email": email,
            "type": "access",
            "exp": expires_at,
            "iat": now
        }
        
        key = self.private_key if self.algorithm == "RS256" else self.secret_key
        token = jwt.encode(payload, key, algorithm=self.algorithm)
        return token
    
    async def generate_refresh_token(self, user_id: int, db: AsyncSession) -> str:
        """Generate a refresh token and store it in the database.
        
        Creates a UUID4-based refresh token with 7-day expiration and
        stores it in the database linked to the user.
        
        Args:
            user_id: The user's database ID
            db: Database session
            
        Returns:
            str: The generated refresh token string
            
        Requirements: 2.5, 4.1
        """
        # Generate a secure random UUID4 token
        token = str(uuid.uuid4())
        
        # Calculate expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        
        # Create database record
        refresh_token = RefreshToken(
            user_id=user_id,
            token=token,
            is_revoked=False,
            expires_at=expires_at
        )
        
        db.add(refresh_token)
        await db.flush()  # Flush to get the token ID, but don't commit
        await db.refresh(refresh_token)
        
        return token
    
    def decode_access_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate a JWT access token.
        
        Validates the token signature using the configured algorithm and
        checks expiration. Returns the decoded payload if valid.
        
        Args:
            token: The JWT access token to decode
            
        Returns:
            Dict[str, Any]: Decoded token payload containing user info
            
        Raises:
            jwt.ExpiredSignatureError: If token has expired
            jwt.InvalidTokenError: If token is invalid or signature verification fails
            ValueError: If neither RSA public key nor secret key is configured
            
        Requirements: 4.2
        """
        if self.algorithm == "RS256" and not self.public_key:
            raise ValueError("RSA public key not configured. Run Task 11.4 to generate keys.")
        if self.algorithm == "HS256" and not self.secret_key:
            raise ValueError("JWT secret key not configured.")
        
        try:
            key = self.public_key if self.algorithm == "RS256" else self.secret_key
            payload = jwt.decode(
                token,
                key,
                algorithms=[self.algorithm],
                options={"verify_exp": True}
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise jwt.ExpiredSignatureError("Access token has expired")
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(f"Invalid access token: {str(e)}")
    
    async def refresh_access_token(self, refresh_token: str, db: AsyncSession) -> Tuple[str, str]:
        """Refresh access token using a valid refresh token.
        
        Validates the refresh token, revokes it, generates new tokens,
        and returns both a new access token and a new refresh token.
        This implements refresh token rotation for security.
        
        Args:
            refresh_token: The refresh token to use
            db: Database session
            
        Returns:
            Tuple[str, str]: (new_access_token, new_refresh_token)
            
        Raises:
            ValueError: If refresh token is invalid, expired, or revoked
            
        Requirements: 4.1, 4.3, 4.4
        """
        # Query the refresh token from database with user relationship
        from app.models.user import User
        from sqlalchemy.orm import selectinload
        
        result = await db.execute(
            select(RefreshToken)
            .options(selectinload(RefreshToken.user))
            .filter(RefreshToken.token == refresh_token)
        )
        token_record = result.scalar_one_or_none()
        
        if not token_record:
            raise ValueError("Invalid refresh token")
        
        # Check if token is revoked
        if token_record.is_revoked:
            raise ValueError("Refresh token has been revoked")
        
        # Check if token is expired
        now = datetime.now(timezone.utc)
        # Ensure expires_at is timezone-aware for comparison
        expires_at = token_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            raise ValueError("Refresh token has expired")
        
        # Get user information
        user = token_record.user
        if not user:
            raise ValueError("User not found for refresh token")
        
        # Revoke the old refresh token (token rotation)
        token_record.is_revoked = True
        # Don't commit here - let the endpoint handle it
        
        # Generate new tokens
        new_access_token = self.generate_access_token(user.id, user.email)
        new_refresh_token = await self.generate_refresh_token(user.id, db)
        
        return new_access_token, new_refresh_token
    
    async def revoke_refresh_token(self, refresh_token: str, db: AsyncSession) -> None:
        """Revoke a specific refresh token.
        
        Marks the refresh token as revoked in the database, preventing
        it from being used to generate new access tokens.
        
        Args:
            refresh_token: The refresh token to revoke
            db: Database session
            
        Raises:
            ValueError: If refresh token is not found
            
        Requirements: 8.1, 8.2
        """
        result = await db.execute(
            select(RefreshToken).filter(RefreshToken.token == refresh_token)
        )
        token_record = result.scalar_one_or_none()
        
        if not token_record:
            raise ValueError("Refresh token not found")
        
        token_record.is_revoked = True
        # Don't commit here - let the endpoint handle it
    
    async def revoke_all_user_tokens(self, user_id: int, db: AsyncSession) -> None:
        """Revoke all refresh tokens for a specific user.
        
        Marks all non-revoked refresh tokens for the user as revoked.
        This is used for sign-out-all-sessions functionality and when
        a user's password is reset.
        
        Args:
            user_id: The user's database ID
            db: Database session
            
        Requirements: 8.4, 8.5
        """
        await db.execute(
            select(RefreshToken)
            .filter(
                and_(
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_revoked == False
                )
            )
            .execution_options(synchronize_session=False)
        )
        
        # Update all non-revoked tokens for this user
        result = await db.execute(
            select(RefreshToken).filter(
                and_(
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_revoked == False
                )
            )
        )
        tokens = result.scalars().all()
        
        for token in tokens:
            token.is_revoked = True
        
        # Don't commit here - let the endpoint handle it
    
    def generate_verification_token(self) -> str:
        """Generate a secure random token for email verification.
        
        Creates a cryptographically secure random token using secrets module.
        The token is URL-safe and suitable for use in email verification links.
        
        Returns:
            str: A secure random verification token (64 characters)
            
        Requirements: 7.1, 10.5
        """
        # Generate 32 random bytes and convert to hex (64 characters)
        return secrets.token_urlsafe(32)
    
    def generate_password_reset_token(self) -> str:
        """Generate a secure random token for password reset.
        
        Creates a cryptographically secure random token using secrets module.
        The token is URL-safe and suitable for use in password reset links.
        
        Returns:
            str: A secure random password reset token (64 characters)
            
        Requirements: 5.1, 5.3, 10.5
        """
        # Generate 32 random bytes and convert to hex (64 characters)
        return secrets.token_urlsafe(32)
