"""
Authentication and authorization exception classes.

This module defines a hierarchy of custom exceptions for the authentication system,
providing consistent error handling with appropriate HTTP status codes and error codes.
"""

from typing import Optional
from datetime import datetime, timezone


class AuthException(Exception):
    """
    Base exception class for all authentication-related errors.
    
    All authentication exceptions inherit from this class and provide:
    - A human-readable error message
    - A machine-readable error code
    - An appropriate HTTP status code
    """
    
    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 400
    ):
        """
        Initialize the authentication exception.
        
        Args:
            message: Human-readable error description
            error_code: Machine-readable error identifier
            status_code: HTTP status code for the error response
        """
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.timestamp = datetime.now(timezone.utc)
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON response."""
        return {
            "detail": self.message,
            "error_code": self.error_code,
            "timestamp": self.timestamp.isoformat() + "Z"
        }


class InvalidCredentialsError(AuthException):
    """Raised when email or password is incorrect during sign-in."""
    
    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(
            message=message,
            error_code="INVALID_CREDENTIALS",
            status_code=401
        )


class EmailNotVerifiedError(AuthException):
    """Raised when user attempts to sign in without verifying their email."""
    
    def __init__(self, message: str = "Email address has not been verified. Please check your email for the verification link."):
        super().__init__(
            message=message,
            error_code="EMAIL_NOT_VERIFIED",
            status_code=401
        )


class TokenExpiredError(AuthException):
    """Raised when an access token, refresh token, or other token has expired."""
    
    def __init__(self, message: str = "Token has expired", token_type: Optional[str] = None):
        if token_type:
            message = f"{token_type.capitalize()} token has expired"
        super().__init__(
            message=message,
            error_code="TOKEN_EXPIRED",
            status_code=401
        )


class TokenInvalidError(AuthException):
    """Raised when a token is malformed or has an invalid signature."""
    
    def __init__(self, message: str = "Invalid or malformed token"):
        super().__init__(
            message=message,
            error_code="TOKEN_INVALID",
            status_code=401
        )


class AccountLockedError(AuthException):
    """Raised when an account is temporarily locked due to failed sign-in attempts."""
    
    def __init__(self, message: str = "Account is temporarily locked due to multiple failed sign-in attempts. Please try again later.", locked_until: Optional[datetime] = None):
        if locked_until:
            message = f"Account is locked until {locked_until.strftime('%Y-%m-%d %H:%M:%S UTC')}. Please try again later."
        super().__init__(
            message=message,
            error_code="ACCOUNT_LOCKED",
            status_code=401
        )


class RateLimitError(AuthException):
    """Raised when rate limit is exceeded for an operation."""
    
    def __init__(self, message: str = "Too many requests. Please try again later.", retry_after: Optional[int] = None):
        if retry_after:
            message = f"Too many requests. Please try again in {retry_after} seconds."
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429
        )


class ValidationError(AuthException):
    """Raised when input validation fails."""
    
    def __init__(self, message: str = "Validation error", field: Optional[str] = None):
        if field:
            message = f"Validation error for field '{field}': {message}"
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400
        )


class UserNotFoundError(AuthException):
    """Raised when a user cannot be found in the database."""
    
    def __init__(self, message: str = "User not found"):
        super().__init__(
            message=message,
            error_code="USER_NOT_FOUND",
            status_code=404
        )


class DuplicateEmailError(AuthException):
    """Raised when attempting to register with an email that already exists."""
    
    def __init__(self, message: str = "An account with this email address already exists"):
        super().__init__(
            message=message,
            error_code="DUPLICATE_EMAIL",
            status_code=409
        )


class TokenRevokedError(AuthException):
    """Raised when attempting to use a revoked token."""
    
    def __init__(self, message: str = "Token has been revoked"):
        super().__init__(
            message=message,
            error_code="TOKEN_REVOKED",
            status_code=401
        )


class PasswordStrengthError(AuthException):
    """Raised when a password does not meet security requirements."""
    
    def __init__(self, message: str = "Password does not meet security requirements. Must be at least 8 characters and contain uppercase, lowercase, and number."):
        super().__init__(
            message=message,
            error_code="WEAK_PASSWORD",
            status_code=400
        )


class OAuthProviderError(AuthException):
    """Raised when OAuth provider authentication fails."""
    
    def __init__(self, message: str = "OAuth authentication failed", provider: Optional[str] = None):
        if provider:
            message = f"Authentication with {provider} failed: {message}"
        super().__init__(
            message=message,
            error_code="OAUTH_PROVIDER_ERROR",
            status_code=400
        )
