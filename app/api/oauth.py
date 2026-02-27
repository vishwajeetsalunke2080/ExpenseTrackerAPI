"""OAuth authentication routes.

This module implements OAuth 2.0 authentication endpoints for external
providers (Google, GitHub). It handles authorization redirects and
callback processing.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""
import secrets
from typing import Dict
from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.services.oauth_service import OAuthService
from app.services.token_service import TokenService
from app.schemas.auth import TokenResponse

router = APIRouter(prefix="/auth/oauth", tags=["oauth"])


def get_oauth_service(provider: str) -> OAuthService:
    """Get OAuth service instance for the specified provider.
    
    Args:
        provider: OAuth provider name ('google' or 'github')
        
    Returns:
        OAuthService: Configured OAuth service instance
        
    Raises:
        HTTPException: If provider is not supported or not configured
    """
    if provider == "google":
        if not settings.google_client_id or not settings.google_client_secret:
            raise HTTPException(
                status_code=500,
                detail="Google OAuth is not configured"
            )
        return OAuthService(
            provider="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=settings.google_redirect_uri
        )
    elif provider == "github":
        if not settings.github_client_id or not settings.github_client_secret:
            raise HTTPException(
                status_code=500,
                detail="GitHub OAuth is not configured"
            )
        return OAuthService(
            provider="github",
            client_id=settings.github_client_id,
            client_secret=settings.github_client_secret,
            redirect_uri=settings.github_redirect_uri
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported OAuth provider: {provider}"
        )


@router.get("/{provider}", response_class=RedirectResponse)
async def oauth_login(provider: str) -> RedirectResponse:
    """Initiate OAuth authentication flow.
    
    Generates an authorization URL for the specified OAuth provider and
    redirects the user to the provider's authorization page. A random
    state parameter is included for CSRF protection.
    
    Args:
        provider: OAuth provider name ('google' or 'github')
        
    Returns:
        RedirectResponse: Redirect to provider's authorization page
        
    Raises:
        HTTPException: If provider is not supported or not configured
        
    Requirements: 3.1, 3.2
    """
    oauth_service = get_oauth_service(provider)
    
    # Generate random state for CSRF protection
    state = secrets.token_urlsafe(32)
    
    # TODO: Store state in session/cache for validation in callback
    # For now, we'll skip state validation (should be implemented in production)
    
    # Get authorization URL
    authorization_url = oauth_service.get_authorization_url(state)
    
    return RedirectResponse(url=authorization_url, status_code=302)


@router.get("/{provider}/callback", response_class=RedirectResponse)
async def oauth_callback(
    provider: str,
    code: str = Query(..., description="Authorization code from OAuth provider"),
    state: str = Query(None, description="State parameter for CSRF protection"),
    db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """Handle OAuth callback and complete authentication.
    
    Processes the OAuth callback by exchanging the authorization code for
    an access token, retrieving user information from the provider, and
    creating or linking a user account. Redirects back to frontend with
    JWT tokens in query parameters.
    
    Args:
        provider: OAuth provider name ('google' or 'github')
        code: Authorization code from OAuth provider
        state: State parameter for CSRF protection (optional)
        db: Database session
        
    Returns:
        RedirectResponse: Redirect to frontend with tokens in query params
        
    Raises:
        HTTPException: If OAuth flow fails or provider returns an error
        
    Requirements: 3.3, 3.4, 3.5
    """
    try:
        # Get OAuth service
        oauth_service = get_oauth_service(provider)
        
        # TODO: Validate state parameter against stored value
        # For now, we'll skip state validation (should be implemented in production)
        
        # Exchange authorization code for access token
        token_response = await oauth_service.exchange_code_for_token(code)
        
        # Extract tokens from response
        provider_access_token = token_response.get("access_token")
        provider_refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in")
        
        if not provider_access_token:
            # Redirect to frontend with error
            error_url = f"{settings.frontend_url}/auth/callback?error=token_exchange_failed"
            return RedirectResponse(url=error_url, status_code=302)
        
        # Get user information from provider
        user_info = await oauth_service.get_user_info(provider_access_token)
        
        # Extract user details
        provider_user_id = user_info.get("provider_user_id")
        email = user_info.get("email")
        name = user_info.get("name")
        
        if not provider_user_id or not email:
            # Redirect to frontend with error
            error_url = f"{settings.frontend_url}/auth/callback?error=user_info_failed"
            return RedirectResponse(url=error_url, status_code=302)
        
        # Authenticate or create user
        user = await oauth_service.authenticate_or_create_user(
            provider_user_id=provider_user_id,
            email=email,
            name=name,
            access_token=provider_access_token,
            refresh_token=provider_refresh_token,
            expires_in=expires_in,
            db=db
        )
        
        # Generate JWT tokens for our application
        token_service = TokenService(
            private_key=settings.jwt_private_key,
            public_key=settings.jwt_public_key,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )
        access_token = token_service.generate_access_token(user.id, user.email)
        refresh_token = await token_service.generate_refresh_token(user.id, db)
        
        # Redirect to frontend with tokens in query parameters
        callback_url = f"{settings.frontend_url}/auth/callback?access_token={access_token}&refresh_token={refresh_token}&token_type=bearer"
        return RedirectResponse(url=callback_url, status_code=302)
        
    except ValueError as e:
        # OAuth provider error - redirect to frontend with error
        error_url = f"{settings.frontend_url}/auth/callback?error=oauth_failed&message={str(e)}"
        return RedirectResponse(url=error_url, status_code=302)
    except Exception as e:
        # Unexpected error - redirect to frontend with error
        error_url = f"{settings.frontend_url}/auth/callback?error=internal_error&message={str(e)}"
        return RedirectResponse(url=error_url, status_code=302)
