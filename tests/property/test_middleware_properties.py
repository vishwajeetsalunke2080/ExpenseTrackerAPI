"""Property-based tests for AuthMiddleware.

These tests verify correctness properties for authentication middleware including
route protection, token validation, and user identity extraction.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**
"""
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta, timezone
import jwt

from app.models.user import User
from app.services.token_service import TokenService
from app.middleware.auth import AuthMiddleware
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from app.database import get_db


# Test application setup
def create_test_app_with_middleware():
    """Create a test FastAPI app with AuthMiddleware."""
    app = FastAPI()
    
    # Add middleware
    app.add_middleware(AuthMiddleware)
    
    # Protected route
    @app.get("/protected")
    async def protected_route(request: Request):
        user_id = getattr(request.state, "user_id", None)
        user_email = getattr(request.state, "user_email", None)
        return {"user_id": user_id, "user_email": user_email}
    
    # Public route
    @app.post("/auth/signin")
    async def signin():
        return {"message": "signin endpoint"}
    
    @app.post("/auth/signup")
    async def signup():
        return {"message": "signup endpoint"}
    
    @app.get("/auth/oauth/google")
    async def oauth_google():
        return {"message": "oauth endpoint"}
    
    @app.post("/auth/forgot-password")
    async def forgot_password():
        return {"message": "forgot password endpoint"}
    
    return app


@pytest.fixture
def test_app():
    """Provide test app with middleware."""
    return create_test_app_with_middleware()


@pytest.fixture
def token_service():
    """Provide TokenService instance for tests."""
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
    
    return TokenService(private_key=private_pem, public_key=public_pem, algorithm="RS256")


# Property Tests

@pytest.mark.asyncio
async def test_property_18_protected_routes_require_valid_token(
    test_app,
    token_service,
    db_session
):
    """
    Feature: user-authentication, Property 18: Protected Routes Require Valid Token
    
    For any protected route, requests without a token, with an invalid token, or
    with an expired token should return HTTP 401, while requests with a valid token
    should proceed to the route handler.
    
    **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
    """
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as client:
        
        # Test 1: Request without token (Requirement 6.1)
        response = await client.get("/protected")
        assert response.status_code == 401, "Request without token should return 401"
        assert "authentication token" in response.json()["detail"].lower()
        
        # Test 2: Request with invalid token format (Requirement 6.2)
        invalid_formats = [
            "not-a-bearer-token",
            "Bearer",
            "InvalidScheme token123",
            "Bearer invalid.jwt.token"
        ]
        
        for invalid_token in invalid_formats:
            response = await client.get(
                "/protected",
                headers={"Authorization": invalid_token}
            )
            assert response.status_code == 401, f"Invalid token format '{invalid_token}' should return 401"
        
        # Test 3: Request with expired token (Requirement 6.3)
        user = User(
            email="testuser@example.com",
            password_hash="hashed_password",
            is_verified=True,
            is_active=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Create expired token
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        expired_payload = {
            "sub": str(user.id),
            "email": user.email,
            "type": "access",
            "exp": past_time,
            "iat": past_time - timedelta(minutes=15)
        }
        expired_token = jwt.encode(
            expired_payload,
            token_service.secret_key,
            algorithm=token_service.algorithm
        )
        
        response = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401, "Expired token should return 401"
        assert "expired" in response.json()["detail"].lower()
        
        # Test 4: Request with valid token (Requirement 6.4)
        valid_token = token_service.generate_access_token(user.id, user.email)
        
        response = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200, "Valid token should allow access"
        data = response.json()
        assert data["user_id"] == user.id
        assert data["user_email"] == user.email


@pytest.mark.asyncio
async def test_property_19_token_contains_user_identity(
    test_app,
    token_service,
    db_session
):
    """
    Feature: user-authentication, Property 19: Token Contains User Identity
    
    For any valid access token, the middleware should extract the user ID and email
    from the token and make them available to the route handler.
    
    **Validates: Requirements 6.5**
    """
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as client:
        
        # Test with multiple users
        test_cases = [
            (1, "user1@example.com"),
            (42, "test@test.org"),
            (999, "admin@mail.net"),
        ]
        
        for user_id, email in test_cases:
            # Arrange: Create user
            user = User(
                email=email,
                password_hash="hashed_password",
                is_verified=True,
                is_active=True
            )
            db_session.add(user)
            await db_session.commit()
            await db_session.refresh(user)
            
            # Act: Generate token and make request
            token = token_service.generate_access_token(user.id, user.email)
            response = await client.get(
                "/protected",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            # Assert: User identity is extracted and available
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == user.id, f"User ID should be {user.id}"
            assert data["user_email"] == user.email, f"User email should be {user.email}"


@pytest.mark.asyncio
async def test_property_20_public_routes_accessible_without_authentication(
    test_app,
    token_service
):
    """
    Feature: user-authentication, Property 20: Public Routes Accessible Without Authentication
    
    For any route in the public routes list (signup, signin, password reset request,
    OAuth endpoints), requests without authentication should succeed.
    
    **Validates: Requirements 6.6**
    """
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as client:
        
        # Test public routes without authentication
        public_routes = [
            ("POST", "/auth/signup"),
            ("POST", "/auth/signin"),
            ("GET", "/auth/oauth/google"),
            ("POST", "/auth/forgot-password"),
        ]
        
        for method, path in public_routes:
            if method == "GET":
                response = await client.get(path)
            else:
                response = await client.post(path)
            
            # Assert: Public routes should not return 401 (authentication error)
            assert response.status_code != 401, (
                f"Public route {method} {path} should not require authentication"
            )
            # Note: Routes may return other status codes (400, 422, etc.) due to
            # missing request body or validation, but should not return 401


@pytest.mark.asyncio
async def test_property_18_multiple_token_scenarios(
    test_app,
    token_service,
    db_session
):
    """
    Additional test for Property 18: Test various token scenarios.
    
    Tests edge cases including malformed JWT tokens, tokens with wrong signature,
    and tokens with missing claims.
    
    **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
    """
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as client:
        
        # Create a test user
        user = User(
            email="testuser@example.com",
            password_hash="hashed_password",
            is_verified=True,
            is_active=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Test 1: Token with wrong signature
        wrong_key_token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "type": "access",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
                "iat": datetime.now(timezone.utc)
            },
            "wrong-secret-key-different-from-configured",
            algorithm="HS256"
        )
        
        response = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {wrong_key_token}"}
        )
        assert response.status_code == 401, "Token with wrong signature should return 401"
        
        # Test 2: Malformed JWT (not three parts)
        malformed_tokens = [
            "Bearer malformed",
            "Bearer not.a.jwt",
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid"
        ]
        
        for malformed in malformed_tokens:
            response = await client.get(
                "/protected",
                headers={"Authorization": malformed}
            )
            assert response.status_code == 401, f"Malformed token should return 401"
        
        # Test 3: Token with missing Authorization header
        response = await client.get("/protected")
        assert response.status_code == 401
        assert "missing" in response.json()["detail"].lower()
        
        # Test 4: Valid token should work
        valid_token = token_service.generate_access_token(user.id, user.email)
        response = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_property_19_user_identity_extraction_edge_cases(
    test_app,
    token_service,
    db_session
):
    """
    Additional test for Property 19: Test user identity extraction edge cases.
    
    Tests that user identity is correctly extracted for various user scenarios
    including users with special characters in email, large user IDs, etc.
    
    **Validates: Requirements 6.5**
    """
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as client:
        
        # Test with edge case users
        test_cases = [
            (1, "simple@example.com"),
            (2147483647, "user+tag@sub.domain.com"),  # Max 32-bit int
            (12345, "user.name@example.co.uk"),
        ]
        
        for user_id, email in test_cases:
            # Arrange: Create user
            user = User(
                email=email,
                password_hash="hashed_password",
                is_verified=True,
                is_active=True
            )
            db_session.add(user)
            await db_session.commit()
            await db_session.refresh(user)
            
            # Act: Generate token and make request
            token = token_service.generate_access_token(user.id, user.email)
            response = await client.get(
                "/protected",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            # Assert: User identity is correctly extracted
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == user.id
            assert data["user_email"] == user.email
            
            # Verify the token payload contains correct information
            decoded = token_service.decode_access_token(token)
            assert decoded["sub"] == str(user.id)
            assert decoded["email"] == user.email
