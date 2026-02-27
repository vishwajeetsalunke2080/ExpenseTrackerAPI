"""
Authentication request and response schemas.

This module defines Pydantic models for authentication-related API requests
and responses, including validation rules for email format, password strength,
and other security requirements.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator
import re


class SignupRequest(BaseModel):
    """
    Request schema for user registration.
    
    Validates:
    - Email format (using EmailStr)
    - Password minimum length (8 characters)
    - Password strength (uppercase, lowercase, number)
    
    Requirements: 1.1, 1.3
    """
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """
        Validate password meets security requirements.
        
        Password must contain:
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        
        Requirement: 1.3
        """
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        return v


class SigninRequest(BaseModel):
    """
    Request schema for user sign-in.
    
    Validates:
    - Email format (using EmailStr)
    - Password is provided
    
    Requirements: 2.1
    """
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """
    Request schema for refreshing access tokens.
    
    Validates:
    - Refresh token is provided
    
    Requirements: 4.1
    """
    refresh_token: str


class PasswordResetRequest(BaseModel):
    """
    Request schema for completing password reset.
    
    Validates:
    - Reset token is provided
    - New password minimum length (8 characters)
    - New password strength (uppercase, lowercase, number)
    
    Requirements: 5.4
    """
    token: str
    new_password: str = Field(..., min_length=8)
    
    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """
        Validate new password meets security requirements.
        
        Password must contain:
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        
        Requirement: 5.4, 9.5
        """
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        return v


class ChangePasswordRequest(BaseModel):
    """
    Request schema for changing password while authenticated.
    
    Validates:
    - Current password is provided
    - New password minimum length (8 characters)
    - New password strength (uppercase, lowercase, number)
    
    Requirements: 9.4
    """
    current_password: str
    new_password: str = Field(..., min_length=8)
    
    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """
        Validate new password meets security requirements.
        
        Password must contain:
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        
        Requirement: 9.4, 9.5
        """
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        return v


class UserUpdateRequest(BaseModel):
    """
    Request schema for updating user profile.
    
    Validates:
    - Email format (if provided)
    - Full name (optional)
    
    Note: Email changes trigger reverification (handled in route logic).
    
    Requirements: 9.2, 9.3
    """
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class TokenResponse(BaseModel):
    """
    Response schema for authentication tokens.
    
    Returns access token and refresh token after successful authentication.
    
    Fields:
    - access_token: JWT token for accessing protected resources (15 min expiry)
    - refresh_token: Token for obtaining new access tokens (7 day expiry)
    - token_type: Always "bearer" for JWT tokens
    - expires_in: Access token expiration time in seconds (900 = 15 minutes)
    
    Requirements: 2.1
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes in seconds


class UserResponse(BaseModel):
    """
    Response schema for user profile information.
    
    Returns user data excluding sensitive fields (password_hash, tokens).
    
    Fields:
    - id: User's unique identifier
    - email: User's email address
    - full_name: User's full name (optional)
    - is_verified: Whether user has verified their email
    - created_at: Account creation timestamp
    - last_login_at: Last successful login timestamp (optional)
    
    Requirements: 9.1
    """
    id: int
    email: str
    full_name: Optional[str]
    is_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True
