"""Unit tests for AuthMiddleware.

These tests verify specific scenarios and edge cases for the authentication
middleware including route protection, token validation, and dependency functions.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**
"""
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta, timezone
import jwt

from app.models.user import User
from app.services.token_service import TokenService
from app.middleware.auth import (
    AuthMiddleware,
    get_current_user,
    get_current_active_user,
    get_optional_user
)
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse


def create_test_app():
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
    
    # Route using get_current_user dependency
    @app.get("/user/profile")
    async def get_profile(request: Request, db = Depends(lambda: None)):
        from app.database import get_db
        async for session in get_db():
            user = await get_current_user(request, session)
            return {"id": user.id, "email": user.email}
    
    # Route using get_current_active_user dependency
    @app.get("/user/active")
    async def get_active_profile(request: Request, db = Depends(lambda: None)):
        from app.database import get_db
        async for session in get_db():
            user = await get_current_active_user(None, request, session)
            return {"id": user.id, "email": user.email, "is_active": user.is_active}
    
    # Route using get_optional_user dependency
    @app.get("/user/optional")
    async def get_optional_profile(request: Request, db = Depends(lambda: None)):
        from app.database import get_db
        async for session in get_db():
            user = await get_optional_user(request, session)
            if user:
                return {"id": user.id, "email": user.email}
            return {"message": "No user authenticated"}
    
    # Public routes
    @app.post("/auth/signin")
    async def signin():
        return {"message": "signin endpoint"}
    
    @app.post("/auth/signup")
    async def signup():
        return {"message": "signup endpoint"}
    
    return app


@pytest.fixture
def test_app():
    """Provide test app with middleware."""
    return create_test_app()


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


# Unit Tests

@pytest.mark.asyncio
async def test_middleware_blocks_protected_route_without_token(test_app):
    """Test that protected routes return 401 without authentication token."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as client:
        response = await client.get("/protected")
        assert response.status_code == 401
        assert "missing" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_middleware_allows_public_routes_without_token(test_app):
    """Test that public routes are accessible without authentication."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as client:
        # Test signin route
        response = await client.post("/auth/signin")
        assert response.status_code != 401
        
        # Test signup route
        response = await client.post("/auth/signup")
        assert response.status_code != 401


@pytest.mark.asyncio
async def test_middleware_rejects_invalid_bearer_format(test_app):
    """Test that middleware rejects tokens without proper Bearer format."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as client:
        # Test without Bearer prefix
        response = await client.get(
            "/protected",
            headers={"Authorization": "just-a-token"}
        )
        assert response.status_code == 401
        
        # Test with wrong scheme
        response = await client.get(
            "/protected",
            headers={"Authorization": "Basic token123"}
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_middleware_rejects_expired_token(test_app, token_service, db_session):
    """Test that middleware rejects expired JWT tokens."""
    # Create a user
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
    
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as client:
        response = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_middleware_allows_valid_token(test_app, token_service, db_session):
    """Test that middleware allows access with valid JWT token."""
    # Create a user
    user = User(
        email="testuser@example.com",
        password_hash="hashed_password",
        is_verified=True,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Generate valid token
    token = token_service.generate_access_token(user.id, user.email)
    
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as client:
        response = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user.id
        assert data["user_email"] == user.email


@pytest.mark.asyncio
async def test_middleware_extracts_user_identity(test_app, token_service, db_session):
    """Test that middleware extracts user ID and email from token."""
    # Create a user
    user = User(
        email="user@example.com",
        password_hash="hashed_password",
        is_verified=True,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Generate valid token
    token = token_service.generate_access_token(user.id, user.email)
    
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as client:
        response = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user.id
        assert data["user_email"] == user.email


@pytest.mark.asyncio
async def test_get_current_user_dependency(db_session, token_service):
    """Test get_current_user dependency function."""
    # Create a user
    user = User(
        email="testuser@example.com",
        password_hash="hashed_password",
        is_verified=True,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Create mock request with user_id in state
    from fastapi import Request
    from starlette.datastructures import Headers
    
    class MockRequest:
        def __init__(self, user_id):
            self.state = type('obj', (object,), {'user_id': user_id})()
    
    request = MockRequest(user.id)
    
    # Test get_current_user
    retrieved_user = await get_current_user(request, db_session)
    assert retrieved_user.id == user.id
    assert retrieved_user.email == user.email


@pytest.mark.asyncio
async def test_get_current_user_raises_without_auth(db_session):
    """Test get_current_user raises 401 when no user_id in request state."""
    class MockRequest:
        def __init__(self):
            self.state = type('obj', (object,), {})()
    
    request = MockRequest()
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request, db_session)
    
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_active_user_rejects_inactive(db_session, token_service):
    """Test get_current_active_user rejects inactive users."""
    # Create an inactive user
    user = User(
        email="inactive@example.com",
        password_hash="hashed_password",
        is_verified=True,
        is_active=False  # Inactive user
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    class MockRequest:
        def __init__(self, user_id):
            self.state = type('obj', (object,), {'user_id': user_id})()
    
    request = MockRequest(user.id)
    
    # Test get_current_active_user
    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(None, request, db_session)
    
    assert exc_info.value.status_code == 403
    assert "inactive" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_active_user_allows_active(db_session, token_service):
    """Test get_current_active_user allows active users."""
    # Create an active user
    user = User(
        email="active@example.com",
        password_hash="hashed_password",
        is_verified=True,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    class MockRequest:
        def __init__(self, user_id):
            self.state = type('obj', (object,), {'user_id': user_id})()
    
    request = MockRequest(user.id)
    
    # Test get_current_active_user
    retrieved_user = await get_current_active_user(None, request, db_session)
    assert retrieved_user.id == user.id
    assert retrieved_user.is_active is True


@pytest.mark.asyncio
async def test_get_optional_user_returns_none_without_auth(db_session):
    """Test get_optional_user returns None when no authentication provided."""
    class MockRequest:
        def __init__(self):
            self.state = type('obj', (object,), {})()
    
    request = MockRequest()
    
    # Test get_optional_user
    user = await get_optional_user(request, db_session)
    assert user is None


@pytest.mark.asyncio
async def test_get_optional_user_returns_user_with_auth(db_session, token_service):
    """Test get_optional_user returns user when authenticated."""
    # Create a user
    user = User(
        email="testuser@example.com",
        password_hash="hashed_password",
        is_verified=True,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    class MockRequest:
        def __init__(self, user_id):
            self.state = type('obj', (object,), {'user_id': user_id})()
    
    request = MockRequest(user.id)
    
    # Test get_optional_user
    retrieved_user = await get_optional_user(request, db_session)
    assert retrieved_user is not None
    assert retrieved_user.id == user.id
    assert retrieved_user.email == user.email


@pytest.mark.asyncio
async def test_middleware_oauth_routes_are_public(test_app):
    """Test that OAuth routes with wildcards are treated as public."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as client:
        # OAuth routes should not require authentication
        # Note: They may return 404 or other errors, but not 401
        response = await client.get("/auth/oauth/google")
        assert response.status_code != 401
        
        response = await client.get("/auth/oauth/github")
        assert response.status_code != 401


@pytest.mark.asyncio
async def test_middleware_rejects_malformed_jwt(test_app):
    """Test that middleware rejects malformed JWT tokens."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as client:
        malformed_tokens = [
            "not.a.valid.jwt",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature",
            "completely-invalid-token"
        ]
        
        for token in malformed_tokens:
            response = await client.get(
                "/protected",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 401
