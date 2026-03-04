"""Rate limiter service for authentication attempt tracking and account locking.

This service implements rate limiting for authentication operations to protect
against brute force attacks. It tracks failed sign-in attempts and password
reset requests, automatically locking accounts when thresholds are exceeded.

Requirements: 10.1, 10.4
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.rate_limit import RateLimitAttempt
from app.models.account_lock import AccountLock


class RateLimiterService:
    """Service for rate limiting authentication attempts.
    
    Provides methods for:
    - Tracking failed sign-in attempts
    - Locking accounts after excessive failures
    - Checking account lock status
    - Rate limiting password reset requests
    
    Configuration:
    - Sign-in: 5 attempts within 15 minutes triggers 15-minute lock
    - Password reset: 3 requests within 1 hour
    """
    
    # Rate limiting configuration
    SIGNIN_MAX_ATTEMPTS = 5
    SIGNIN_WINDOW_MINUTES = 15
    SIGNIN_LOCK_DURATION_MINUTES = 15
    
    PASSWORD_RESET_MAX_ATTEMPTS = 3
    PASSWORD_RESET_WINDOW_HOURS = 1
    
    async def check_signin_rate_limit(self, email: str, db: AsyncSession) -> bool:
        """Check if sign-in attempts exceed the rate limit.
        
        Counts failed sign-in attempts within the last 15 minutes.
        Returns True if the limit has been exceeded.
        
        Requirements: 10.1
        
        Args:
            email: User's email address
            db: Database session
            
        Returns:
            True if rate limit exceeded, False otherwise
        """
        # Calculate the time window
        window_start = datetime.now(timezone.utc) - timedelta(minutes=self.SIGNIN_WINDOW_MINUTES)
        
        # Count attempts within the window
        result = await db.execute(
            select(RateLimitAttempt).where(
                RateLimitAttempt.email == email,
                RateLimitAttempt.action == 'signin',
                RateLimitAttempt.created_at >= window_start
            )
        )
        attempts = result.scalars().all()
        
        return len(attempts) >= self.SIGNIN_MAX_ATTEMPTS
    
    async def record_failed_signin(self, email: str, db: AsyncSession) -> int:
        """Record a failed sign-in attempt and return the count.
        
        Creates a record of the failed attempt in the database and returns
        the total number of failed attempts within the rate limit window.
        
        Requirements: 10.1
        
        Args:
            email: User's email address
            db: Database session
            
        Returns:
            Number of failed attempts within the window
        """
        # Record the failed attempt
        attempt = RateLimitAttempt(
            email=email,
            action='signin',
            created_at=datetime.now(timezone.utc)
        )
        db.add(attempt)
        # Don't commit here - let the endpoint handle it
        
        # Count total attempts within the window
        window_start = datetime.now(timezone.utc) - timedelta(minutes=self.SIGNIN_WINDOW_MINUTES)
        result = await db.execute(
            select(RateLimitAttempt).where(
                RateLimitAttempt.email == email,
                RateLimitAttempt.action == 'signin',
                RateLimitAttempt.created_at >= window_start
            )
        )
        attempts = result.scalars().all()
        
        return len(attempts)
    
    async def lock_account(
        self,
        email: str,
        db: AsyncSession,
        duration_minutes: int = 15
    ) -> None:
        """Lock an account for a specified duration.
        
        Creates or updates an account lock record with the specified
        expiration time. The account will be locked until the expiration.
        
        Requirements: 10.1
        
        Args:
            email: User's email address
            db: Database session
            duration_minutes: Lock duration in minutes (default: 15)
        """
        locked_until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        
        # Check if a lock already exists
        result = await db.execute(
            select(AccountLock).where(AccountLock.email == email)
        )
        existing_lock = result.scalar_one_or_none()
        
        if existing_lock:
            # Update existing lock
            existing_lock.locked_until = locked_until
            existing_lock.created_at = datetime.now(timezone.utc)
        else:
            # Create new lock
            lock = AccountLock(
                email=email,
                locked_until=locked_until,
                created_at=datetime.now(timezone.utc)
            )
            db.add(lock)
        
        # Don't commit here - let the endpoint handle it
    
    async def is_account_locked(self, email: str, db: AsyncSession) -> bool:
        """Check if an account is currently locked.
        
        Queries the database for an active lock on the account.
        Automatically removes expired locks.
        
        Requirements: 10.1
        
        Args:
            email: User's email address
            db: Database session
            
        Returns:
            True if account is locked, False otherwise
        """
        now = datetime.now(timezone.utc)
        
        # Find lock record
        result = await db.execute(
            select(AccountLock).where(AccountLock.email == email)
        )
        lock = result.scalar_one_or_none()
        
        if not lock:
            return False
        
        # Ensure locked_until is timezone-aware for comparison
        locked_until = lock.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        
        # Check if lock has expired
        if locked_until <= now:
            # Lock has expired, remove it
            await db.delete(lock)
            await db.flush()  # Flush the delete but don't commit
            return False
        
        return True
    
    async def check_password_reset_rate_limit(self, email: str, db: AsyncSession) -> bool:
        """Check if password reset requests exceed the rate limit.
        
        Counts password reset requests within the last hour.
        Returns True if the limit (3 requests) has been exceeded.
        
        Requirements: 10.4
        
        Args:
            email: User's email address
            db: Database session
            
        Returns:
            True if rate limit exceeded, False otherwise
        """
        # Calculate the time window
        window_start = datetime.now(timezone.utc) - timedelta(hours=self.PASSWORD_RESET_WINDOW_HOURS)
        
        # Count attempts within the window
        result = await db.execute(
            select(RateLimitAttempt).where(
                RateLimitAttempt.email == email,
                RateLimitAttempt.action == 'password_reset',
                RateLimitAttempt.created_at >= window_start
            )
        )
        attempts = result.scalars().all()
        
        return len(attempts) >= self.PASSWORD_RESET_MAX_ATTEMPTS
    
    async def record_password_reset_attempt(self, email: str, db: AsyncSession) -> None:
        """Record a password reset request attempt.
        
        Creates a record of the password reset request in the database
        for rate limiting purposes.
        
        Requirements: 10.4
        
        Args:
            email: User's email address
            db: Database session
        """
        attempt = RateLimitAttempt(
            email=email,
            action='password_reset',
            created_at=datetime.now(timezone.utc)
        )
        db.add(attempt)
        # Don't commit here - let the endpoint handle it
    
    async def cleanup_expired_attempts(self, db: AsyncSession, days: int = 7) -> None:
        """Clean up old rate limit attempts from the database.
        
        Removes rate limit attempt records older than the specified number
        of days to prevent unbounded database growth.
        
        Args:
            db: Database session
            days: Number of days to retain records (default: 7)
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        await db.execute(
            delete(RateLimitAttempt).where(
                RateLimitAttempt.created_at < cutoff_date
            )
        )
        await db.flush()  # Flush the cleanup but don't commit
