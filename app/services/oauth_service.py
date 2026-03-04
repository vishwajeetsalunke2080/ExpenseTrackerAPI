"""OAuth service for OAuth 2.0 provider integration.

This service handles OAuth authentication flows for external providers
(Google, GitHub). It manages authorization URL generation, token exchange,
user information retrieval, and user account creation/linking.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""
import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.oauth_account import OAuthAccount
from app.services.user_onboarding_service import UserOnboardingService


class OAuthService:
    """Service for managing OAuth 2.0 authentication flows.
    
    Supports multiple OAuth providers (Google, GitHub) and handles:
    - Authorization URL generation with state parameter
    - Authorization code exchange for access tokens
    - User information retrieval from provider APIs
    - User account creation or linking with OAuth accounts
    """
    
    # OAuth provider configurations
    PROVIDERS = {
        "google": {
            "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
            "scope": "openid email profile",
        },
        "github": {
            "authorization_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "userinfo_url": "https://api.github.com/user",
            "scope": "read:user user:email",
        }
    }
    
    def __init__(
        self,
        provider: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str
    ):
        """Initialize OAuthService for a specific provider.
        
        Args:
            provider: OAuth provider name ('google' or 'github')
            client_id: OAuth client ID from provider
            client_secret: OAuth client secret from provider
            redirect_uri: Callback URL for OAuth redirect
            
        Raises:
            ValueError: If provider is not supported
        """
        if provider not in self.PROVIDERS:
            raise ValueError(f"Unsupported OAuth provider: {provider}")
        
        self.provider = provider
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.config = self.PROVIDERS[provider]
    
    def get_authorization_url(self, state: str) -> str:
        """Generate OAuth authorization URL for user redirect.
        
        Creates the authorization URL with required parameters including
        client_id, redirect_uri, scope, and state for CSRF protection.
        
        Args:
            state: Random state parameter for CSRF protection
            
        Returns:
            str: Complete authorization URL for redirecting user
            
        Requirements: 3.1, 3.2
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.config["scope"],
            "state": state,
            "response_type": "code",
        }
        
        # Add provider-specific parameters
        if self.provider == "google":
            params["access_type"] = "offline"
            params["prompt"] = "consent"
        
        # Build query string
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        authorization_url = f"{self.config['authorization_url']}?{query_string}"
        
        return authorization_url

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token.
        
        Calls the provider's token endpoint to exchange the authorization
        code for an access token and optional refresh token.
        
        Args:
            code: Authorization code from OAuth callback
            
        Returns:
            Dict containing access_token, token_type, expires_in, and
            optionally refresh_token and scope
            
        Raises:
            httpx.HTTPError: If token exchange request fails
            ValueError: If provider returns an error
            
        Requirements: 3.3
        """
        token_data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        
        headers = {
            "Accept": "application/json",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.config["token_url"],
                data=token_data,
                headers=headers,
                timeout=10.0
            )
            response.raise_for_status()
            
            token_response = response.json()
            
            # Check for error in response
            if "error" in token_response:
                raise ValueError(f"OAuth token error: {token_response.get('error_description', token_response['error'])}")
            
            return token_response
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Fetch user information from OAuth provider.
        
        Uses the access token to retrieve user profile information from
        the provider's userinfo endpoint.
        
        Args:
            access_token: OAuth access token
            
        Returns:
            Dict containing user information (id, email, name, etc.)
            The exact fields depend on the provider.
            
        Raises:
            httpx.HTTPError: If userinfo request fails
            
        Requirements: 3.3
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.config["userinfo_url"],
                headers=headers,
                timeout=10.0
            )
            response.raise_for_status()
            
            user_info = response.json()
            
            # Normalize user info across providers
            normalized_info = self._normalize_user_info(user_info)
            
            return normalized_info
    
    def _normalize_user_info(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize user information from different providers.
        
        Converts provider-specific user info formats to a common structure.
        
        Args:
            user_info: Raw user info from provider
            
        Returns:
            Dict with normalized fields: provider_user_id, email, name
        """
        if self.provider == "google":
            return {
                "provider_user_id": user_info.get("id"),
                "email": user_info.get("email"),
                "name": user_info.get("name"),
                "verified_email": user_info.get("verified_email", False),
            }
        elif self.provider == "github":
            return {
                "provider_user_id": str(user_info.get("id")),
                "email": user_info.get("email"),
                "name": user_info.get("name") or user_info.get("login"),
                "verified_email": True,  # GitHub emails are verified
            }
        else:
            # Fallback for unknown providers
            return {
                "provider_user_id": str(user_info.get("id")),
                "email": user_info.get("email"),
                "name": user_info.get("name"),
                "verified_email": False,
            }
    
    async def authenticate_or_create_user(
        self,
        provider_user_id: str,
        email: str,
        name: Optional[str],
        access_token: str,
        refresh_token: Optional[str],
        expires_in: Optional[int],
        db: AsyncSession
    ) -> User:
        """Authenticate existing user or create new user from OAuth.
        
        Checks if an OAuth account exists for the provider and user ID.
        If it exists, returns the linked user. If not, checks if a user
        with the email exists and links the OAuth account, or creates
        a new user with the OAuth account.
        
        TRANSACTION BOUNDARY: All operations (user creation, OAuth account creation,
        default data initialization) occur within a single transaction managed by
        the get_db() dependency. The transaction commits on success or rolls back
        on any failure, ensuring ACID atomicity.
        
        Args:
            provider_user_id: User ID from OAuth provider
            email: User's email from OAuth provider
            name: User's name from OAuth provider (optional)
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            expires_in: Token expiration time in seconds (optional)
            db: Database session
            
        Returns:
            User: The authenticated or newly created user
            
        Requirements: 3.4, 3.5, 3.6
        """
        # Calculate token expiration time
        expires_at = None
        if expires_in:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        
        # Check if OAuth account already exists
        result = await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == self.provider,
                OAuthAccount.provider_user_id == provider_user_id
            )
        )
        oauth_account = result.scalar_one_or_none()
        
        if oauth_account:
            # OAuth account exists, update tokens and return user
            oauth_account.access_token = access_token
            oauth_account.refresh_token = refresh_token
            oauth_account.expires_at = expires_at
            oauth_account.updated_at = datetime.now(timezone.utc)
            
            # Eagerly load the user to avoid lazy loading issues
            user_result = await db.execute(
                select(User).where(User.id == oauth_account.user_id)
            )
            user = user_result.scalar_one()
            
            user.last_login_at = datetime.now(timezone.utc)
            # Don't commit here - let the endpoint handle it
            
            return user
        
        # OAuth account doesn't exist, check if user with email exists
        user_result = await db.execute(
            select(User).where(User.email == email)
        )
        user = user_result.scalar_one_or_none()
        
        if user:
            # User exists, link OAuth account
            # TRANSACTION BOUNDARY: OAuth account creation occurs within existing transaction
            try:
                new_oauth_account = OAuthAccount(
                    user_id=user.id,
                    provider=self.provider,
                    provider_user_id=provider_user_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at
                )
                
                db.add(new_oauth_account)
                
                # Mark user as verified if OAuth provider verified the email
                if not user.is_verified:
                    user.is_verified = True
                
                user.last_login_at = datetime.now(timezone.utc)
                
                # Don't commit here - let the endpoint handle it
                await db.refresh(user)
                
                return user
            except IntegrityError:
                # Race condition: Another request created the OAuth account
                # Roll back and query for the existing OAuth account
                await db.rollback()
                
                result = await db.execute(
                    select(OAuthAccount).where(
                        OAuthAccount.provider == self.provider,
                        OAuthAccount.provider_user_id == provider_user_id
                    )
                )
                oauth_account = result.scalar_one()
                
                # Load and return the user
                user_result = await db.execute(
                    select(User).where(User.id == oauth_account.user_id)
                )
                user = user_result.scalar_one()
                
                return user
        
        # User doesn't exist, create new user with OAuth account
        # TRANSACTION BOUNDARY: User creation, OAuth account creation, and default data
        # initialization all occur atomically within a single transaction
        try:
            new_user = User(
                email=email,
                full_name=name,
                password_hash=None,  # OAuth-only user, no password
                is_verified=True,  # OAuth providers verify emails
                is_active=True
            )
            
            db.add(new_user)
            await db.flush()  # Flush to get user.id for onboarding and OAuth account
            
            # Initialize default categories and account types for new user
            onboarding_service = UserOnboardingService(db)
            await onboarding_service.initialize_user_defaults(new_user.id)
            
            # Create OAuth account linked to new user
            new_oauth_account = OAuthAccount(
                user_id=new_user.id,
                provider=self.provider,
                provider_user_id=provider_user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at
            )
            
            db.add(new_oauth_account)
            
            # Refresh user to ensure all relationships are loaded
            await db.refresh(new_user)
            
            return new_user
        except IntegrityError:
            # Race condition: Another request created the user or OAuth account
            # Roll back and query for the existing OAuth account
            await db.rollback()
            
            result = await db.execute(
                select(OAuthAccount).where(
                    OAuthAccount.provider == self.provider,
                    OAuthAccount.provider_user_id == provider_user_id
                )
            )
            oauth_account = result.scalar_one()
            
            # Load and return the user
            user_result = await db.execute(
                select(User).where(User.id == oauth_account.user_id)
            )
            user = user_result.scalar_one()
            
            return user
