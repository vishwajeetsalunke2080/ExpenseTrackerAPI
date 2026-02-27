"""Authentication API routes.

This module implements all authentication-related endpoints including:
- User registration (signup)
- User sign-in with credentials
- Token refresh
- Sign-out
- Email verification
- Password reset flow

Requirements: 1.1, 1.2, 2.1, 2.2, 4.1, 5.1, 5.4, 7.3, 7.5, 8.1
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.schemas.auth import (
    SignupRequest,
    SigninRequest,
    RefreshRequest,
    PasswordResetRequest,
    TokenResponse,
    UserResponse
)
from app.services.auth_service import AuthService
from app.services.token_service import TokenService
from app.services.email_service import EmailService
from app.services.rate_limiter import RateLimiterService
from app.models.auth_log import AuthLog
from app.models.user import User
from app.config import settings
from sqlalchemy import select

router = APIRouter(prefix="/auth", tags=["authentication"])


def get_token_service() -> TokenService:
    """Create TokenService instance with configuration."""
    return TokenService(
        private_key=settings.jwt_private_key,
        public_key=settings.jwt_public_key,
        algorithm=settings.jwt_algorithm
    )


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> Optional[str]:
    """Extract user agent from request."""
    return request.headers.get("User-Agent")


async def log_auth_attempt(
    db: AsyncSession,
    email: str,
    action: str,
    success: bool,
    ip_address: str,
    user_agent: Optional[str] = None,
    user_id: Optional[int] = None
) -> None:
    """Log an authentication attempt. Requirements: 10.3"""
    log_entry = AuthLog(
        user_id=user_id,
        email=email,
        action=action,
        success=success,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(log_entry)
    await db.commit()



@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    user_data: SignupRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user account.
    
    Requirements: 1.1, 1.2, 1.5
    """
    auth_service = AuthService()
    email_service = EmailService()
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    try:
        user = await auth_service.create_user(
            email=user_data.email,
            password=user_data.password,
            db=db,
            full_name=user_data.full_name
        )
        
        result = await db.execute(select(User).where(User.id == user.id))
        user = result.scalar_one()
        
        from app.models.email_verification import EmailVerificationToken
        token_result = await db.execute(
            select(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == user.id)
            .order_by(EmailVerificationToken.created_at.desc())
            .limit(1)
        )
        verification_token = token_result.scalar_one_or_none()
        
        if verification_token:
            try:
                await email_service.send_verification_email(
                    email=user.email,
                    token=verification_token.token
                )
            except Exception:
                pass
        
        await log_auth_attempt(
            db=db, email=user.email, action="signup", success=True,
            ip_address=ip_address, user_agent=user_agent, user_id=user.id
        )
        
        return user
        
    except ValueError as e:
        await log_auth_attempt(
            db=db, email=user_data.email, action="signup", success=False,
            ip_address=ip_address, user_agent=user_agent
        )
        
        error_msg = str(e)
        if "already exists" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )



@router.post("/signin", response_model=TokenResponse)
async def signin(
    credentials: SigninRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Sign in with email and password.
    
    Requirements: 2.1, 2.2, 2.6, 10.1
    """
    auth_service = AuthService()
    token_service = get_token_service()
    rate_limiter = RateLimiterService()
    email_service = EmailService()
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    if await rate_limiter.is_account_locked(credentials.email, db):
        await log_auth_attempt(
            db=db, email=credentials.email, action="signin", success=False,
            ip_address=ip_address, user_agent=user_agent
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account temporarily locked due to multiple failed attempts"
        )
    
    if await rate_limiter.check_signin_rate_limit(credentials.email, db):
        await rate_limiter.lock_account(credentials.email, db)
        try:
            await email_service.send_account_locked_email(credentials.email)
        except Exception:
            pass
        
        await log_auth_attempt(
            db=db, email=credentials.email, action="signin", success=False,
            ip_address=ip_address, user_agent=user_agent
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Account has been temporarily locked."
        )
    
    try:
        user = await auth_service.authenticate_user(
            email=credentials.email,
            password=credentials.password,
            db=db
        )
        
        if not user:
            await rate_limiter.record_failed_signin(credentials.email, db)
            await log_auth_attempt(
                db=db, email=credentials.email, action="signin", success=False,
                ip_address=ip_address, user_agent=user_agent
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        access_token = token_service.generate_access_token(user.id, user.email)
        refresh_token = await token_service.generate_refresh_token(user.id, db)
        
        await log_auth_attempt(
            db=db, email=user.email, action="signin", success=True,
            ip_address=ip_address, user_agent=user_agent, user_id=user.id
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=900
        )
        
    except ValueError as e:
        if "verification required" in str(e).lower():
            await log_auth_attempt(
                db=db, email=credentials.email, action="signin", success=False,
                ip_address=ip_address, user_agent=user_agent
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email verification required. Please check your email."
            )
        raise



@router.post("/signout", status_code=status.HTTP_204_NO_CONTENT)
async def signout(
    refresh_token: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    """Sign out by revoking refresh token.
    
    Requirements: 8.1
    """
    token_service = get_token_service()
    
    try:
        await token_service.revoke_refresh_token(refresh_token, db)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token"
        )
    
    return None


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token.
    
    Requirements: 4.1, 4.3
    """
    token_service = get_token_service()
    
    try:
        new_access_token, new_refresh_token = await token_service.refresh_access_token(
            refresh_data.refresh_token,
            db
        )
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=900
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )



@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    request: Request,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Verify email address using verification token.
    
    Requirements: 7.3
    """
    auth_service = AuthService()
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    success = await auth_service.verify_email(token, db)
    
    if not success:
        await log_auth_attempt(
            db=db, email="unknown", action="email_verification", success=False,
            ip_address=ip_address, user_agent=user_agent
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    # Get user email from token for logging
    from app.models.email_verification import EmailVerificationToken
    token_result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token == token)
    )
    verification_token = token_result.scalar_one_or_none()
    
    if verification_token:
        user_result = await db.execute(
            select(User).where(User.id == verification_token.user_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            await log_auth_attempt(
                db=db, email=user.email, action="email_verification", success=True,
                ip_address=ip_address, user_agent=user_agent, user_id=user.id
            )
    
    return {"message": "Email verified successfully"}


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(
    email: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    """Resend verification email.
    
    Requirements: 7.5
    """
    auth_service = AuthService()
    email_service = EmailService()
    
    token = await auth_service.resend_verification_email(email, db)
    
    if token:
        try:
            await email_service.send_verification_email(email, token)
        except Exception:
            pass
    
    return {"message": "If the email exists and is unverified, a verification email has been sent"}



@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    request: Request,
    email: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    """Initiate password reset process.
    
    Requirements: 5.1, 10.4
    """
    auth_service = AuthService()
    email_service = EmailService()
    rate_limiter = RateLimiterService()
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    if await rate_limiter.check_password_reset_rate_limit(email, db):
        await log_auth_attempt(
            db=db, email=email, action="password_reset_request", success=False,
            ip_address=ip_address, user_agent=user_agent
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset requests. Please try again later."
        )
    
    await rate_limiter.record_password_reset_attempt(email, db)
    
    token = await auth_service.initiate_password_reset(email, db)
    
    # Log the attempt - always log as success to avoid user enumeration
    # Get user_id if user exists
    user_id = None
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    if user:
        user_id = user.id
    
    await log_auth_attempt(
        db=db, email=email, action="password_reset_request", success=True,
        ip_address=ip_address, user_agent=user_agent, user_id=user_id
    )
    
    if token:
        try:
            await email_service.send_password_reset_email(email, token)
        except Exception:
            pass
    
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request: Request,
    reset_data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Complete password reset using reset token.
    
    Requirements: 5.4, 5.6
    """
    auth_service = AuthService()
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    try:
        success = await auth_service.reset_password(
            token=reset_data.token,
            new_password=reset_data.new_password,
            db=db
        )
        
        if not success:
            await log_auth_attempt(
                db=db, email="unknown", action="password_reset", success=False,
                ip_address=ip_address, user_agent=user_agent
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        # Get user email from token for logging
        from app.models.password_reset import PasswordResetToken
        token_result = await db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token == reset_data.token)
        )
        reset_token = token_result.scalar_one_or_none()
        
        if reset_token:
            user_result = await db.execute(
                select(User).where(User.id == reset_token.user_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                await log_auth_attempt(
                    db=db, email=user.email, action="password_reset", success=True,
                    ip_address=ip_address, user_agent=user_agent, user_id=user.id
                )
        
        return {"message": "Password reset successfully"}
        
    except ValueError as e:
        await log_auth_attempt(
            db=db, email="unknown", action="password_reset", success=False,
            ip_address=ip_address, user_agent=user_agent
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
