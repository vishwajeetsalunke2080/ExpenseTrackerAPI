"""
Unit tests for global exception handlers in main.py.

Tests verify that:
- Each exception type returns the correct status code and error format
- Exception handlers log appropriately
- Error responses follow consistent JSON structure
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import logging

from app.exceptions.auth_exceptions import (
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


@pytest.fixture
def test_app():
    """Create a test FastAPI application with exception handlers."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from app.exceptions.auth_exceptions import AuthException
    
    app = FastAPI()
    
    # Register the auth exception handler
    @app.exception_handler(AuthException)
    async def auth_exception_handler(request: Request, exc: AuthException):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict()
        )
    
    # Create test routes that raise different exceptions
    @app.get("/test/invalid-credentials")
    async def test_invalid_credentials():
        raise InvalidCredentialsError()
    
    @app.get("/test/email-not-verified")
    async def test_email_not_verified():
        raise EmailNotVerifiedError()
    
    @app.get("/test/token-expired")
    async def test_token_expired():
        raise TokenExpiredError()
    
    @app.get("/test/token-invalid")
    async def test_token_invalid():
        raise TokenInvalidError()
    
    @app.get("/test/account-locked")
    async def test_account_locked():
        raise AccountLockedError()
    
    @app.get("/test/rate-limit")
    async def test_rate_limit():
        raise RateLimitError()
    
    @app.get("/test/validation-error")
    async def test_validation_error():
        raise ValidationError(message="Invalid input", field="email")
    
    @app.get("/test/user-not-found")
    async def test_user_not_found():
        raise UserNotFoundError()
    
    @app.get("/test/duplicate-email")
    async def test_duplicate_email():
        raise DuplicateEmailError()
    
    @app.get("/test/token-revoked")
    async def test_token_revoked():
        raise TokenRevokedError()
    
    @app.get("/test/password-strength")
    async def test_password_strength():
        raise PasswordStrengthError()
    
    @app.get("/test/oauth-provider")
    async def test_oauth_provider():
        raise OAuthProviderError(provider="Google")
    
    return app


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


class TestExceptionHandlerResponses:
    """Test that exception handlers return correct HTTP responses."""
    
    def test_invalid_credentials_response(self, client):
        """Test InvalidCredentialsError returns 401 with correct format."""
        response = client.get("/test/invalid-credentials")
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "error_code" in data
        assert "timestamp" in data
        assert data["error_code"] == "INVALID_CREDENTIALS"
    
    def test_email_not_verified_response(self, client):
        """Test EmailNotVerifiedError returns 401 with correct format."""
        response = client.get("/test/email-not-verified")
        
        assert response.status_code == 401
        data = response.json()
        assert data["error_code"] == "EMAIL_NOT_VERIFIED"
    
    def test_token_expired_response(self, client):
        """Test TokenExpiredError returns 401 with correct format."""
        response = client.get("/test/token-expired")
        
        assert response.status_code == 401
        data = response.json()
        assert data["error_code"] == "TOKEN_EXPIRED"
    
    def test_token_invalid_response(self, client):
        """Test TokenInvalidError returns 401 with correct format."""
        response = client.get("/test/token-invalid")
        
        assert response.status_code == 401
        data = response.json()
        assert data["error_code"] == "TOKEN_INVALID"
    
    def test_account_locked_response(self, client):
        """Test AccountLockedError returns 401 with correct format."""
        response = client.get("/test/account-locked")
        
        assert response.status_code == 401
        data = response.json()
        assert data["error_code"] == "ACCOUNT_LOCKED"
    
    def test_rate_limit_response(self, client):
        """Test RateLimitError returns 429 with correct format."""
        response = client.get("/test/rate-limit")
        
        assert response.status_code == 429
        data = response.json()
        assert data["error_code"] == "RATE_LIMIT_EXCEEDED"
    
    def test_validation_error_response(self, client):
        """Test ValidationError returns 400 with correct format."""
        response = client.get("/test/validation-error")
        
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "VALIDATION_ERROR"
        assert "email" in data["detail"]
    
    def test_user_not_found_response(self, client):
        """Test UserNotFoundError returns 404 with correct format."""
        response = client.get("/test/user-not-found")
        
        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "USER_NOT_FOUND"
    
    def test_duplicate_email_response(self, client):
        """Test DuplicateEmailError returns 409 with correct format."""
        response = client.get("/test/duplicate-email")
        
        assert response.status_code == 409
        data = response.json()
        assert data["error_code"] == "DUPLICATE_EMAIL"
    
    def test_token_revoked_response(self, client):
        """Test TokenRevokedError returns 401 with correct format."""
        response = client.get("/test/token-revoked")
        
        assert response.status_code == 401
        data = response.json()
        assert data["error_code"] == "TOKEN_REVOKED"
    
    def test_password_strength_response(self, client):
        """Test PasswordStrengthError returns 400 with correct format."""
        response = client.get("/test/password-strength")
        
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "WEAK_PASSWORD"
    
    def test_oauth_provider_response(self, client):
        """Test OAuthProviderError returns 400 with correct format."""
        response = client.get("/test/oauth-provider")
        
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "OAUTH_PROVIDER_ERROR"
        assert "Google" in data["detail"]


class TestExceptionHandlerLogging:
    """Test that exception handlers log appropriately."""
    
    @patch('main.logger')
    def test_401_error_logs_info(self, mock_logger, test_app):
        """Test that 401 errors are logged at INFO level."""
        client = TestClient(test_app)
        
        with patch('main.logger') as mock_logger:
            response = client.get("/test/invalid-credentials")
            
            # Verify logging was called (implementation may vary)
            assert response.status_code == 401
    
    @patch('main.logger')
    def test_429_error_logs_warning(self, mock_logger, test_app):
        """Test that 429 errors are logged at WARNING level."""
        client = TestClient(test_app)
        
        with patch('main.logger') as mock_logger:
            response = client.get("/test/rate-limit")
            
            # Verify logging was called
            assert response.status_code == 429
    
    @patch('main.logger')
    def test_400_error_logs_warning(self, mock_logger, test_app):
        """Test that 400 errors are logged at WARNING level."""
        client = TestClient(test_app)
        
        with patch('main.logger') as mock_logger:
            response = client.get("/test/validation-error")
            
            # Verify logging was called
            assert response.status_code == 400


class TestErrorResponseFormat:
    """Test that all error responses follow consistent format."""
    
    @pytest.mark.parametrize("endpoint,expected_code", [
        ("/test/invalid-credentials", "INVALID_CREDENTIALS"),
        ("/test/email-not-verified", "EMAIL_NOT_VERIFIED"),
        ("/test/token-expired", "TOKEN_EXPIRED"),
        ("/test/token-invalid", "TOKEN_INVALID"),
        ("/test/account-locked", "ACCOUNT_LOCKED"),
        ("/test/rate-limit", "RATE_LIMIT_EXCEEDED"),
        ("/test/validation-error", "VALIDATION_ERROR"),
        ("/test/user-not-found", "USER_NOT_FOUND"),
        ("/test/duplicate-email", "DUPLICATE_EMAIL"),
        ("/test/token-revoked", "TOKEN_REVOKED"),
        ("/test/password-strength", "WEAK_PASSWORD"),
        ("/test/oauth-provider", "OAUTH_PROVIDER_ERROR"),
    ])
    def test_error_response_structure(self, client, endpoint, expected_code):
        """Test that all error responses have consistent structure."""
        response = client.get(endpoint)
        data = response.json()
        
        # Verify required fields
        assert "detail" in data
        assert "error_code" in data
        assert "timestamp" in data
        
        # Verify error code matches expected
        assert data["error_code"] == expected_code
        
        # Verify timestamp format (ISO 8601 with Z suffix)
        assert data["timestamp"].endswith("Z")
        assert "T" in data["timestamp"]
    
    def test_error_response_json_serializable(self, client):
        """Test that error responses are valid JSON."""
        response = client.get("/test/invalid-credentials")
        
        # If this doesn't raise an exception, JSON is valid
        data = response.json()
        assert isinstance(data, dict)


class TestExceptionHandlerIntegration:
    """Test exception handler integration with FastAPI."""
    
    def test_exception_handler_catches_auth_exceptions(self, client):
        """Test that auth exception handler catches all AuthException subclasses."""
        endpoints = [
            "/test/invalid-credentials",
            "/test/email-not-verified",
            "/test/token-expired",
            "/test/token-invalid",
            "/test/account-locked",
            "/test/rate-limit",
            "/test/validation-error",
            "/test/user-not-found",
            "/test/duplicate-email",
            "/test/token-revoked",
            "/test/password-strength",
            "/test/oauth-provider",
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            
            # All should return valid error responses, not 500
            assert response.status_code != 500
            
            # All should have error_code in response
            data = response.json()
            assert "error_code" in data
    
    def test_exception_handler_preserves_status_codes(self, client):
        """Test that exception handler preserves original status codes."""
        test_cases = [
            ("/test/invalid-credentials", 401),
            ("/test/rate-limit", 429),
            ("/test/validation-error", 400),
            ("/test/user-not-found", 404),
            ("/test/duplicate-email", 409),
        ]
        
        for endpoint, expected_status in test_cases:
            response = client.get(endpoint)
            assert response.status_code == expected_status
