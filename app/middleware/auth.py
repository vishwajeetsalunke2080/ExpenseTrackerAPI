"""Authentication middleware for route protection.

This middleware intercepts all requests to protected routes and validates
JWT tokens. It extracts user identity from valid tokens and makes it
available to route handlers.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.6
"""
from typing import Callable, List, Optional
from fastapi import Request, Response, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import jwt
import re

from app.services.token_service import TokenService
from app.config import settings
from app.database import get_db
from app.models.user import User


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for protecting routes with JWT authentication.
    
    This middleware:
    - Checks if the requested route is public (no authentication required)
    - Extracts JWT token from Authorization header
    - Validates token signature and expiration
    - Extracts user identity and makes it available to route handlers
    - Returns 401 for missing, invalid, or expired tokens on protected routes
    
    Public routes (accessible without authentication):
    - /auth/signup
    - /auth/signin
    - /auth/oauth/*
    - /auth/forgot-password
    - /auth/reset-password
    - /auth/verify-email
    - /auth/resend-verification
    - /docs, /redoc, /openapi.json (API documentation)
    
    Requirements: 6.1, 6.2, 6.3, 6.4, 6.6
    """
    
    def __init__(self, app: ASGIApp, public_paths: Optional[List[str]] = None):
        """Initialize AuthMiddleware.
        
        Args:
            app: The ASGI application
            public_paths: List of path patterns that don't require authentication
        """
        super().__init__(app)
        
        # Default public paths if none provided
        if public_paths is None:
            public_paths = [
                "/auth/signup",
                "/auth/signin",
                "/auth/oauth/.*",  # Regex pattern for OAuth routes
                "/auth/forgot-password",
                "/auth/reset-password",
                "/auth/verify-email",
                "/auth/resend-verification",
                "/auth/refresh",
                "/docs",
                "/redoc",
                "/openapi.json",
                "/"  # Root path
            ]
        
        self.public_paths = public_paths
        self.token_service = TokenService(
            private_key=settings.jwt_private_key,
            public_key=settings.jwt_public_key,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )
    
    def is_public_path(self, path: str) -> bool:
        """Check if the requested path is public (no authentication required).
        
        Args:
            path: The request path
            
        Returns:
            bool: True if path is public, False if authentication is required
        """
        for pattern in self.public_paths:
            # Use regex matching for patterns with wildcards
            if re.match(f"^{pattern}$", path):
                return True
        return False
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and validate authentication.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            Response: The response from the route handler or error response
            
        Requirements: 6.1, 6.2, 6.3, 6.4, 6.6
        """
        # Check if route is public
        if self.is_public_path(request.url.path):
            return await call_next(request)
        
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            # Requirement 6.1: Return 401 for missing token
            return Response(
                content='{"detail":"Missing authentication token"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json"
            )
        
        # Check if Authorization header has Bearer scheme
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            # Requirement 6.2: Return 401 for invalid token format
            return Response(
                content='{"detail":"Invalid authentication token format"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json"
            )
        
        token = parts[1]
        
        try:
            # Validate token and extract payload
            payload = self.token_service.decode_access_token(token)
            
            # Requirement 6.5: Extract user identity and make available to route handlers
            # Store user info in request state for access in route handlers
            request.state.user_id = int(payload.get("sub"))
            request.state.user_email = payload.get("email")
            
            # Requirement 6.4: Allow request to proceed with valid token
            return await call_next(request)
            
        except jwt.ExpiredSignatureError:
            # Requirement 6.3: Return 401 for expired token
            return Response(
                content='{"detail":"Access token has expired"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json"
            )
        except jwt.InvalidTokenError as e:
            # Requirement 6.2: Return 401 for invalid token
            return Response(
                content=f'{{"detail":"Invalid access token: {str(e)}"}}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json"
            )
        except Exception as e:
            # Catch any other errors and return 401
            return Response(
                content=f'{{"detail":"Authentication error: {str(e)}"}}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json"
            )



# Dependency functions for route handlers

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency to get current authenticated user from request.
    
    Extracts user identity from the request state (populated by AuthMiddleware)
    and queries the database to return the full User object.
    
    Args:
        request: The FastAPI request object
        db: Database session (injected by Depends(get_db))
        
    Returns:
        User: The authenticated user object
        
    Raises:
        HTTPException: 401 if user identity not found in request state
        HTTPException: 404 if user not found in database
        
    Requirements: 6.5
    
    Usage:
        @router.get("/protected")
        async def protected_route(
            current_user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_db)
        ):
            return {"user_id": current_user.id}
    """
    from sqlalchemy import select
    
    # Get user_id from request state (set by AuthMiddleware)
    user_id = getattr(request.state, "user_id", None)
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Query user from database using the provided session
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency to get current authenticated and active user.
    
    Extends get_current_user to also verify that the user account is active.
    Inactive users are rejected with 403 Forbidden.
    
    Args:
        current_user: User object (injected by Depends(get_current_user))
        
    Returns:
        User: The authenticated and active user object
        
    Raises:
        HTTPException: 403 if user account is not active
        
    Requirements: 6.5
    
    Usage:
        @router.get("/protected")
        async def protected_route(
            current_user: User = Depends(get_current_active_user)
        ):
            return {"user_id": current_user.id}
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return current_user


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Dependency to optionally get current user if authenticated.
    
    Similar to get_current_user but returns None if no authentication
    is provided instead of raising an error. Useful for routes that
    have different behavior for authenticated vs anonymous users.
    
    Args:
        request: The FastAPI request object
        db: Database session (injected by Depends(get_db))
        
    Returns:
        Optional[User]: The authenticated user object or None
        
    Requirements: 6.5
    
    Usage:
        @router.get("/optional-auth")
        async def optional_auth_route(
            current_user: Optional[User] = Depends(get_optional_user)
        ):
            if current_user:
                return {"user_id": current_user.id}
            return {"message": "Anonymous user"}
    """
    from sqlalchemy import select
    
    # Get user_id from request state (set by AuthMiddleware)
    user_id = getattr(request.state, "user_id", None)
    
    if user_id is None:
        return None
    
    # Query user from database using the provided session
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    return user
