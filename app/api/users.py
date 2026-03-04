"""
User profile management routes.

This module provides API endpoints for authenticated users to view and update
their profile information, change passwords, and manage sessions.

Requirements: 9.1, 9.2, 9.3, 9.4, 8.4, 8.5
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.schemas.auth import UserResponse, UserUpdateRequest, ChangePasswordRequest
from app.services.auth_service import AuthService
from app.services.token_service import TokenService
from app.services.email_service import EmailService
from app.config import settings


router = APIRouter(prefix="/users", tags=["users"])
security = HTTPBearer()


def get_auth_service() -> AuthService:
    """Dependency to get AuthService instance."""
    return AuthService()


def get_token_service() -> TokenService:
    """Dependency to get TokenService instance."""
    return TokenService(
        private_key=settings.jwt_private_key,
        public_key=settings.jwt_public_key,
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )


def get_email_service() -> EmailService:
    """Dependency to get EmailService instance."""
    return EmailService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    token_service: TokenService = Depends(get_token_service)
) -> User:
    """
    Dependency to extract and validate the current authenticated user.
    
    Extracts the JWT token from the Authorization header, validates it,
    and returns the corresponding user from the database.
    
    Args:
        credentials: HTTP Bearer credentials containing the token
        db: Database session
        token_service: Token service for JWT validation
        
    Returns:
        User: The authenticated user
        
    Raises:
        HTTPException: 401 if token is missing, invalid, or user not found
        
    Requirements: 6.4, 6.5
    """
    token = credentials.credentials
    
    try:
        # Decode and validate token
        payload = token_service.decode_access_token(token)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Fetch user from database
        result = await db.execute(
            select(User).where(User.id == int(user_id))
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
        
    except ValueError as e:
        # Token decoding failed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get the current authenticated user's profile.
    
    Returns user information excluding sensitive data (password hash, tokens).
    
    Args:
        current_user: The authenticated user (from dependency)
        
    Returns:
        UserResponse: User profile data
        
    Requirements: 9.1
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_profile(
    update_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
    token_service: TokenService = Depends(get_token_service)
):
    """
    Update the current authenticated user's profile.
    
    Allows updating full_name and email. If email is changed, the user's
    is_verified status is set to False and a new verification email is sent.
    
    Args:
        update_data: Profile update data
        current_user: The authenticated user (from dependency)
        db: Database session
        email_service: Email service for sending verification emails
        token_service: Token service for generating verification tokens
        
    Returns:
        UserResponse: Updated user profile data
        
    Requirements: 9.2, 9.3
    """
    email_changed = False
    
    # Update full_name if provided
    if update_data.full_name is not None:
        current_user.full_name = update_data.full_name
    
    # Update email if provided and different from current
    if update_data.email is not None and update_data.email != current_user.email:
        # Check if new email already exists
        result = await db.execute(
            select(User).where(User.email == update_data.email)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Update email and mark as unverified
        current_user.email = update_data.email
        current_user.is_verified = False
        email_changed = True
    
    # Commit changes to database
    db.add(current_user)
    # Don't commit here - let get_db dependency handle it
    await db.refresh(current_user)
    
    # Send verification email if email was changed
    if email_changed:
        verification_token = token_service.generate_verification_token()
        await email_service.send_verification_email(
            current_user.email,
            verification_token
        )
    
    return current_user


@router.post("/me/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Change the current authenticated user's password.
    
    Requires the current password for verification before updating to the new password.
    
    Args:
        password_data: Current and new password data
        current_user: The authenticated user (from dependency)
        db: Database session
        auth_service: Auth service for password verification and hashing
        
    Returns:
        dict: Success message
        
    Raises:
        HTTPException: 400 if current password is incorrect
        
    Requirements: 9.4
    """
    # Verify current password
    if not auth_service.verify_password(
        password_data.current_password,
        current_user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Hash and update new password
    current_user.password_hash = auth_service.hash_password(
        password_data.new_password
    )
    
    # Commit changes to database
    db.add(current_user)
    # Don't commit here - let get_db dependency handle it
    
    return {"message": "Password changed successfully"}


@router.post("/me/revoke-all-sessions", status_code=status.HTTP_200_OK)
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    token_service: TokenService = Depends(get_token_service)
):
    """
    Revoke all active sessions (refresh tokens) for the current user.
    
    This invalidates all refresh tokens, requiring the user to sign in again
    on all devices. Useful for security purposes if the user suspects
    unauthorized access.
    
    Args:
        current_user: The authenticated user (from dependency)
        db: Database session
        token_service: Token service for revoking tokens
        
    Returns:
        dict: Success message
        
    Requirements: 8.4, 8.5
    """
    await token_service.revoke_all_user_tokens(current_user.id, db)
    
    return {"message": "All sessions revoked successfully"}
