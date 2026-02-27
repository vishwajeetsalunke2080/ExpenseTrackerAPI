"""Unit tests for RateLimiterService.

Tests the rate limiting functionality for authentication attempts
and account locking mechanisms.

Requirements: 10.1, 10.4
"""
import pytest
from datetime import datetime, timedelta, timezone
from app.services.rate_limiter import RateLimiterService
from app.models.rate_limit import RateLimitAttempt
from app.models.account_lock import AccountLock


@pytest.mark.asyncio
class TestRateLimiterService:
    """Test suite for RateLimiterService."""
    
    async def test_check_signin_rate_limit_no_attempts(self, db_session):
        """Test rate limit check with no previous attempts."""
        service = RateLimiterService()
        
        result = await service.check_signin_rate_limit("test@example.com", db_session)
        
        assert result is False
    
    async def test_record_failed_signin(self, db_session):
        """Test recording a failed sign-in attempt."""
        service = RateLimiterService()
        
        count = await service.record_failed_signin("test@example.com", db_session)
        
        assert count == 1
    
    async def test_check_signin_rate_limit_under_threshold(self, db_session):
        """Test rate limit check with attempts under threshold."""
        service = RateLimiterService()
        
        # Record 4 failed attempts (under the 5 attempt limit)
        for _ in range(4):
            await service.record_failed_signin("test@example.com", db_session)
        
        result = await service.check_signin_rate_limit("test@example.com", db_session)
        
        assert result is False
    
    async def test_check_signin_rate_limit_at_threshold(self, db_session):
        """Test rate limit check with attempts at threshold."""
        service = RateLimiterService()
        
        # Record 5 failed attempts (at the 5 attempt limit)
        for _ in range(5):
            await service.record_failed_signin("test@example.com", db_session)
        
        result = await service.check_signin_rate_limit("test@example.com", db_session)
        
        assert result is True
    
    async def test_check_signin_rate_limit_over_threshold(self, db_session):
        """Test rate limit check with attempts over threshold."""
        service = RateLimiterService()
        
        # Record 6 failed attempts (over the 5 attempt limit)
        for _ in range(6):
            await service.record_failed_signin("test@example.com", db_session)
        
        result = await service.check_signin_rate_limit("test@example.com", db_session)
        
        assert result is True
    
    async def test_lock_account(self, db_session):
        """Test locking an account."""
        service = RateLimiterService()
        
        await service.lock_account("test@example.com", db_session, duration_minutes=15)
        
        # Verify lock was created
        is_locked = await service.is_account_locked("test@example.com", db_session)
        assert is_locked is True
    
    async def test_is_account_locked_no_lock(self, db_session):
        """Test checking lock status when no lock exists."""
        service = RateLimiterService()
        
        is_locked = await service.is_account_locked("test@example.com", db_session)
        
        assert is_locked is False
    
    async def test_is_account_locked_expired_lock(self, db_session):
        """Test checking lock status with expired lock."""
        service = RateLimiterService()
        
        # Create an expired lock manually
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        lock = AccountLock(
            email="test@example.com",
            locked_until=expired_time,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(lock)
        await db_session.commit()
        
        is_locked = await service.is_account_locked("test@example.com", db_session)
        
        assert is_locked is False
    
    async def test_lock_account_updates_existing(self, db_session):
        """Test that locking an already locked account updates the lock."""
        service = RateLimiterService()
        
        # Create initial lock
        await service.lock_account("test@example.com", db_session, duration_minutes=5)
        
        # Update lock with longer duration
        await service.lock_account("test@example.com", db_session, duration_minutes=30)
        
        # Verify lock still exists
        is_locked = await service.is_account_locked("test@example.com", db_session)
        assert is_locked is True
    
    async def test_check_password_reset_rate_limit_no_attempts(self, db_session):
        """Test password reset rate limit with no attempts."""
        service = RateLimiterService()
        
        result = await service.check_password_reset_rate_limit("test@example.com", db_session)
        
        assert result is False
    
    async def test_check_password_reset_rate_limit_under_threshold(self, db_session):
        """Test password reset rate limit under threshold."""
        service = RateLimiterService()
        
        # Record 2 password reset attempts (under the 3 attempt limit)
        for _ in range(2):
            await service.record_password_reset_attempt("test@example.com", db_session)
        
        result = await service.check_password_reset_rate_limit("test@example.com", db_session)
        
        assert result is False
    
    async def test_check_password_reset_rate_limit_at_threshold(self, db_session):
        """Test password reset rate limit at threshold."""
        service = RateLimiterService()
        
        # Record 3 password reset attempts (at the 3 attempt limit)
        for _ in range(3):
            await service.record_password_reset_attempt("test@example.com", db_session)
        
        result = await service.check_password_reset_rate_limit("test@example.com", db_session)
        
        assert result is True
    
    async def test_record_password_reset_attempt(self, db_session):
        """Test recording a password reset attempt."""
        service = RateLimiterService()
        
        await service.record_password_reset_attempt("test@example.com", db_session)
        
        # Verify attempt was recorded
        result = await service.check_password_reset_rate_limit("test@example.com", db_session)
        assert result is False  # Should be under limit with just 1 attempt
    
    async def test_rate_limit_isolation_between_emails(self, db_session):
        """Test that rate limits are isolated per email address."""
        service = RateLimiterService()
        
        # Record attempts for first email
        for _ in range(5):
            await service.record_failed_signin("user1@example.com", db_session)
        
        # Check rate limit for different email
        result = await service.check_signin_rate_limit("user2@example.com", db_session)
        
        assert result is False
    
    async def test_rate_limit_isolation_between_actions(self, db_session):
        """Test that rate limits are isolated per action type."""
        service = RateLimiterService()
        
        # Record signin attempts
        for _ in range(5):
            await service.record_failed_signin("test@example.com", db_session)
        
        # Check password reset rate limit (different action)
        result = await service.check_password_reset_rate_limit("test@example.com", db_session)
        
        assert result is False
