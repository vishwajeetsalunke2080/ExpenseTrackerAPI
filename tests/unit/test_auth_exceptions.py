"""
Unit tests for authentication exception classes.

Tests verify that each exception type:
- Returns the correct HTTP status code
- Provides the correct error code
- Formats error responses consistently
- Includes appropriate error messages
"""

import pytest
from datetime import datetime, timedelta
from app.exceptions.auth_exceptions import (
    AuthException,
    InvalidCredentialsError,
    EmailNotVerifiedError,
    TokenExpiredError,
    TokenInvalidError,
    AccountLockedError,
    RateLimitError,
    ValidationError,
    UserNotFoundError,
    DuplicateEmailError,
    TokenRevokedError,
    PasswordStrengthError,
    OAuthProviderError
)


class TestAuthException:
    """Test the base AuthException class."""
    
    def test_base_exception_initialization(self):
        """Test that base exception initializes with correct attributes."""
        exc = AuthException(
            message="Test error",
            error_code="TEST_ERROR",
            status_code=400
        )
        
        assert exc.message == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert exc.status_code == 400
        assert isinstance(exc.timestamp, datetime)
    
    def test_to_dict_format(self):
        """Test that to_dict returns correct JSON structure."""
        exc = AuthException(
            message="Test error",
            error_code="TEST_ERROR",
            status_code=400
        )
        
        result = exc.to_dict()
        
        assert "detail" in result
        assert "error_code" in result
        assert "timestamp" in result
        assert result["detail"] == "Test error"
        assert result["error_code"] == "TEST_ERROR"
        assert result["timestamp"].endswith("Z")


class TestInvalidCredentialsError:
    """Test InvalidCredentialsError exception."""
    
    def test_default_message(self):
        """Test default error message."""
        exc = InvalidCredentialsError()
        
        assert exc.message == "Invalid email or password"
        assert exc.error_code == "INVALID_CREDENTIALS"
        assert exc.status_code == 401
    
    def test_custom_message(self):
        """Test custom error message."""
        exc = InvalidCredentialsError(message="Custom credentials error")
        
        assert exc.message == "Custom credentials error"
        assert exc.error_code == "INVALID_CREDENTIALS"
        assert exc.status_code == 401


class TestEmailNotVerifiedError:
    """Test EmailNotVerifiedError exception."""
    
    def test_default_message(self):
        """Test default error message."""
        exc = EmailNotVerifiedError()
        
        assert "not been verified" in exc.message
        assert exc.error_code == "EMAIL_NOT_VERIFIED"
        assert exc.status_code == 401


class TestTokenExpiredError:
    """Test TokenExpiredError exception."""
    
    def test_default_message(self):
        """Test default error message."""
        exc = TokenExpiredError()
        
        assert exc.message == "Token has expired"
        assert exc.error_code == "TOKEN_EXPIRED"
        assert exc.status_code == 401
    
    def test_with_token_type(self):
        """Test error message with specific token type."""
        exc = TokenExpiredError(token_type="access")
        
        assert "Access token has expired" in exc.message
        assert exc.error_code == "TOKEN_EXPIRED"


class TestTokenInvalidError:
    """Test TokenInvalidError exception."""
    
    def test_default_message(self):
        """Test default error message."""
        exc = TokenInvalidError()
        
        assert "Invalid or malformed token" in exc.message
        assert exc.error_code == "TOKEN_INVALID"
        assert exc.status_code == 401


class TestAccountLockedError:
    """Test AccountLockedError exception."""
    
    def test_default_message(self):
        """Test default error message."""
        exc = AccountLockedError()
        
        assert "temporarily locked" in exc.message
        assert exc.error_code == "ACCOUNT_LOCKED"
        assert exc.status_code == 401
    
    def test_with_locked_until(self):
        """Test error message with specific lock expiration time."""
        locked_until = datetime.utcnow() + timedelta(minutes=15)
        exc = AccountLockedError(locked_until=locked_until)
        
        assert "locked until" in exc.message
        assert exc.error_code == "ACCOUNT_LOCKED"


class TestRateLimitError:
    """Test RateLimitError exception."""
    
    def test_default_message(self):
        """Test default error message."""
        exc = RateLimitError()
        
        assert "Too many requests" in exc.message
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"
        assert exc.status_code == 429
    
    def test_with_retry_after(self):
        """Test error message with retry_after seconds."""
        exc = RateLimitError(retry_after=60)
        
        assert "60 seconds" in exc.message
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"


class TestValidationError:
    """Test ValidationError exception."""
    
    def test_default_message(self):
        """Test default error message."""
        exc = ValidationError()
        
        assert exc.message == "Validation error"
        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.status_code == 400
    
    def test_with_field(self):
        """Test error message with specific field."""
        exc = ValidationError(message="must be a valid email", field="email")
        
        assert "field 'email'" in exc.message
        assert "must be a valid email" in exc.message
        assert exc.error_code == "VALIDATION_ERROR"


class TestUserNotFoundError:
    """Test UserNotFoundError exception."""
    
    def test_default_message(self):
        """Test default error message."""
        exc = UserNotFoundError()
        
        assert exc.message == "User not found"
        assert exc.error_code == "USER_NOT_FOUND"
        assert exc.status_code == 404


class TestDuplicateEmailError:
    """Test DuplicateEmailError exception."""
    
    def test_default_message(self):
        """Test default error message."""
        exc = DuplicateEmailError()
        
        assert "already exists" in exc.message
        assert exc.error_code == "DUPLICATE_EMAIL"
        assert exc.status_code == 409


class TestTokenRevokedError:
    """Test TokenRevokedError exception."""
    
    def test_default_message(self):
        """Test default error message."""
        exc = TokenRevokedError()
        
        assert "revoked" in exc.message
        assert exc.error_code == "TOKEN_REVOKED"
        assert exc.status_code == 401


class TestPasswordStrengthError:
    """Test PasswordStrengthError exception."""
    
    def test_default_message(self):
        """Test default error message."""
        exc = PasswordStrengthError()
        
        assert "security requirements" in exc.message
        assert "8 characters" in exc.message
        assert exc.error_code == "WEAK_PASSWORD"
        assert exc.status_code == 400


class TestOAuthProviderError:
    """Test OAuthProviderError exception."""
    
    def test_default_message(self):
        """Test default error message."""
        exc = OAuthProviderError()
        
        assert "OAuth authentication failed" in exc.message
        assert exc.error_code == "OAUTH_PROVIDER_ERROR"
        assert exc.status_code == 400
    
    def test_with_provider(self):
        """Test error message with specific provider."""
        exc = OAuthProviderError(message="Invalid token", provider="Google")
        
        assert "Google" in exc.message
        assert "Invalid token" in exc.message
        assert exc.error_code == "OAUTH_PROVIDER_ERROR"


class TestExceptionStatusCodes:
    """Test that all exceptions return correct HTTP status codes."""
    
    @pytest.mark.parametrize("exception_class,expected_status", [
        (InvalidCredentialsError, 401),
        (EmailNotVerifiedError, 401),
        (TokenExpiredError, 401),
        (TokenInvalidError, 401),
        (AccountLockedError, 401),
        (TokenRevokedError, 401),
        (RateLimitError, 429),
        (ValidationError, 400),
        (PasswordStrengthError, 400),
        (OAuthProviderError, 400),
        (UserNotFoundError, 404),
        (DuplicateEmailError, 409),
    ])
    def test_status_codes(self, exception_class, expected_status):
        """Test that each exception returns the correct HTTP status code."""
        exc = exception_class()
        assert exc.status_code == expected_status


class TestExceptionErrorCodes:
    """Test that all exceptions have unique error codes."""
    
    def test_unique_error_codes(self):
        """Test that each exception has a unique error code."""
        exceptions = [
            InvalidCredentialsError(),
            EmailNotVerifiedError(),
            TokenExpiredError(),
            TokenInvalidError(),
            AccountLockedError(),
            RateLimitError(),
            ValidationError(),
            UserNotFoundError(),
            DuplicateEmailError(),
            TokenRevokedError(),
            PasswordStrengthError(),
            OAuthProviderError(),
        ]
        
        error_codes = [exc.error_code for exc in exceptions]
        
        # Check that all error codes are unique
        assert len(error_codes) == len(set(error_codes))
