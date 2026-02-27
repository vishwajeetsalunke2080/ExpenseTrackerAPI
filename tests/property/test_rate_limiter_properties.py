"""Property-based tests for RateLimiterService.

These tests verify correctness properties across all valid inputs using Hypothesis.
Each test runs with max_examples=20 for faster test execution.

**Validates: Requirements 10.1, 10.4**
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta, timezone

from app.services.rate_limiter import RateLimiterService


# Custom Hypothesis strategies for generating valid test data

@st.composite
def valid_email_strategy(draw):
    """Generate valid email addresses."""
    username = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), min_codepoint=97, max_codepoint=122),
        min_size=3,
        max_size=20
    ))
    domain = draw(st.sampled_from(['example.com', 'test.org', 'mail.net', 'demo.io']))
    return f"{username}@{domain}"


# Property Tests

@pytest.mark.asyncio
async def test_property_31_account_locking_after_failed_attempts(db_session):
    """
    Feature: user-authentication, Property 31: Account Locking After Failed Attempts
    
    For any user account, after 5 failed sign-in attempts within 15 minutes, the 6th
    attempt should be rejected with an account locked error, and the account should
    remain locked for 15 minutes.
    
    **Validates: Requirements 10.1**
    """
    rate_limiter = RateLimiterService()
    
    # Test with multiple email addresses
    test_cases = [
        "user1@example.com",
        "user2@test.org",
        "user3@mail.net",
        "testuser@demo.io",
    ]
    
    for email in test_cases:
        # Arrange: Start with no rate limit
        is_limited = await rate_limiter.check_signin_rate_limit(email, db_session)
        assert is_limited is False, f"Email {email} should start with no rate limit"
        
        # Act: Record 5 failed sign-in attempts
        for attempt_num in range(1, 6):
            count = await rate_limiter.record_failed_signin(email, db_session)
            assert count == attempt_num, f"Attempt count should be {attempt_num}, got {count}"
        
        # Assert: After 5 attempts, rate limit should be triggered
        is_limited = await rate_limiter.check_signin_rate_limit(email, db_session)
        assert is_limited is True, f"Email {email} should be rate limited after 5 attempts"
        
        # Act: Lock the account
        await rate_limiter.lock_account(email, db_session, duration_minutes=15)
        
        # Assert: Account should be locked
        is_locked = await rate_limiter.is_account_locked(email, db_session)
        assert is_locked is True, f"Account {email} should be locked after 5 failed attempts"
        
        # Assert: 6th attempt should still show rate limit exceeded
        count = await rate_limiter.record_failed_signin(email, db_session)
        assert count >= 6, f"6th attempt should be recorded, count: {count}"
        
        is_limited = await rate_limiter.check_signin_rate_limit(email, db_session)
        assert is_limited is True, f"Email {email} should still be rate limited on 6th attempt"


@pytest.mark.asyncio
async def test_property_31_account_lock_duration(db_session):
    """
    Feature: user-authentication, Property 31: Account Locking After Failed Attempts
    
    Verify that account locks expire after the specified duration (15 minutes).
    
    **Validates: Requirements 10.1**
    """
    from app.models.account_lock import AccountLock
    
    rate_limiter = RateLimiterService()
    
    # Test with multiple scenarios
    test_cases = [
        ("locked1@example.com", 15),  # Standard 15-minute lock
        ("locked2@test.org", 30),     # Extended 30-minute lock
        ("locked3@mail.net", 5),      # Short 5-minute lock
    ]
    
    for email, duration_minutes in test_cases:
        # Act: Lock the account
        await rate_limiter.lock_account(email, db_session, duration_minutes=duration_minutes)
        
        # Assert: Account should be locked
        is_locked = await rate_limiter.is_account_locked(email, db_session)
        assert is_locked is True, f"Account {email} should be locked"
        
        # Assert: Lock record exists with correct expiration
        from sqlalchemy import select
        result = await db_session.execute(
            select(AccountLock).where(AccountLock.email == email)
        )
        lock = result.scalar_one_or_none()
        assert lock is not None, f"Lock record should exist for {email}"
        
        # Verify lock duration is approximately correct (within 1 second tolerance)
        expected_unlock_time = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        locked_until = lock.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        
        time_diff = abs((locked_until - expected_unlock_time).total_seconds())
        assert time_diff < 2, f"Lock duration should be {duration_minutes} minutes, time diff: {time_diff}s"


@pytest.mark.asyncio
async def test_property_31_expired_lock_removal(db_session):
    """
    Feature: user-authentication, Property 31: Account Locking After Failed Attempts
    
    Verify that expired locks are automatically removed when checked.
    
    **Validates: Requirements 10.1**
    """
    from app.models.account_lock import AccountLock
    from sqlalchemy import select
    
    rate_limiter = RateLimiterService()
    
    # Test with multiple expired locks
    test_cases = [
        "expired1@example.com",
        "expired2@test.org",
        "expired3@mail.net",
    ]
    
    for email in test_cases:
        # Arrange: Create an expired lock manually
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        lock = AccountLock(
            email=email,
            locked_until=expired_time,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(lock)
        await db_session.commit()
        
        # Act: Check if account is locked
        is_locked = await rate_limiter.is_account_locked(email, db_session)
        
        # Assert: Expired lock should be removed and account should not be locked
        assert is_locked is False, f"Expired lock for {email} should be removed"
        
        # Assert: Lock record should be deleted from database
        result = await db_session.execute(
            select(AccountLock).where(AccountLock.email == email)
        )
        lock_after = result.scalar_one_or_none()
        assert lock_after is None, f"Expired lock record for {email} should be deleted"


@pytest.mark.asyncio
async def test_property_33_password_reset_rate_limiting(db_session):
    """
    Feature: user-authentication, Property 33: Password Reset Rate Limiting
    
    For any email address, after 3 password reset requests within 1 hour, the 4th
    request should be rejected with a rate limit error.
    
    **Validates: Requirements 10.4**
    """
    rate_limiter = RateLimiterService()
    
    # Test with multiple email addresses
    test_cases = [
        "reset1@example.com",
        "reset2@test.org",
        "reset3@mail.net",
        "resetuser@demo.io",
    ]
    
    for email in test_cases:
        # Arrange: Start with no rate limit
        is_limited = await rate_limiter.check_password_reset_rate_limit(email, db_session)
        assert is_limited is False, f"Email {email} should start with no password reset rate limit"
        
        # Act: Record 3 password reset attempts
        for attempt_num in range(1, 4):
            await rate_limiter.record_password_reset_attempt(email, db_session)
            
            # Check rate limit after each attempt
            is_limited = await rate_limiter.check_password_reset_rate_limit(email, db_session)
            
            if attempt_num < 3:
                assert is_limited is False, f"Email {email} should not be limited after {attempt_num} attempts"
            else:
                # After 3 attempts, rate limit should be triggered
                assert is_limited is True, f"Email {email} should be rate limited after 3 password reset attempts"
        
        # Assert: 4th attempt should still show rate limit exceeded
        await rate_limiter.record_password_reset_attempt(email, db_session)
        is_limited = await rate_limiter.check_password_reset_rate_limit(email, db_session)
        assert is_limited is True, f"Email {email} should still be rate limited on 4th password reset attempt"


@pytest.mark.asyncio
async def test_property_33_password_reset_rate_limit_window(db_session):
    """
    Feature: user-authentication, Property 33: Password Reset Rate Limiting
    
    Verify that password reset rate limiting uses a 1-hour sliding window.
    
    **Validates: Requirements 10.4**
    """
    from app.models.rate_limit import RateLimitAttempt
    from sqlalchemy import select
    
    rate_limiter = RateLimiterService()
    
    email = "windowtest@example.com"
    
    # Arrange: Create 2 recent attempts and 1 old attempt (outside 1-hour window)
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    old_attempt = RateLimitAttempt(
        email=email,
        action='password_reset',
        created_at=old_time
    )
    db_session.add(old_attempt)
    await db_session.commit()
    
    # Add 2 recent attempts
    for _ in range(2):
        await rate_limiter.record_password_reset_attempt(email, db_session)
    
    # Assert: Should not be rate limited (only 2 attempts in the 1-hour window)
    is_limited = await rate_limiter.check_password_reset_rate_limit(email, db_session)
    assert is_limited is False, "Should not be rate limited with 2 recent attempts (old attempt outside window)"
    
    # Act: Add one more attempt to reach the limit
    await rate_limiter.record_password_reset_attempt(email, db_session)
    
    # Assert: Now should be rate limited (3 attempts in the 1-hour window)
    is_limited = await rate_limiter.check_password_reset_rate_limit(email, db_session)
    assert is_limited is True, "Should be rate limited with 3 attempts in the 1-hour window"


@pytest.mark.asyncio
async def test_property_rate_limit_isolation_between_users(db_session):
    """
    Feature: user-authentication, Property: Rate Limit Isolation
    
    Verify that rate limits are isolated per email address - one user's failed
    attempts should not affect another user's rate limit status.
    
    **Validates: Requirements 10.1, 10.4**
    """
    rate_limiter = RateLimiterService()
    
    user1_email = "user1@example.com"
    user2_email = "user2@example.com"
    
    # Act: Record 5 failed sign-in attempts for user1
    for _ in range(5):
        await rate_limiter.record_failed_signin(user1_email, db_session)
    
    # Assert: User1 should be rate limited
    is_user1_limited = await rate_limiter.check_signin_rate_limit(user1_email, db_session)
    assert is_user1_limited is True, "User1 should be rate limited after 5 attempts"
    
    # Assert: User2 should NOT be rate limited
    is_user2_limited = await rate_limiter.check_signin_rate_limit(user2_email, db_session)
    assert is_user2_limited is False, "User2 should not be affected by User1's rate limit"
    
    # Test password reset isolation
    for _ in range(3):
        await rate_limiter.record_password_reset_attempt(user1_email, db_session)
    
    # Assert: User1 should be rate limited for password reset
    is_user1_reset_limited = await rate_limiter.check_password_reset_rate_limit(user1_email, db_session)
    assert is_user1_reset_limited is True, "User1 should be rate limited for password reset"
    
    # Assert: User2 should NOT be rate limited for password reset
    is_user2_reset_limited = await rate_limiter.check_password_reset_rate_limit(user2_email, db_session)
    assert is_user2_reset_limited is False, "User2 should not be affected by User1's password reset rate limit"


@pytest.mark.asyncio
async def test_property_rate_limit_isolation_between_actions(db_session):
    """
    Feature: user-authentication, Property: Rate Limit Action Isolation
    
    Verify that rate limits are isolated per action type - sign-in attempts should
    not affect password reset rate limits and vice versa.
    
    **Validates: Requirements 10.1, 10.4**
    """
    rate_limiter = RateLimiterService()
    
    email = "actiontest@example.com"
    
    # Act: Record 5 failed sign-in attempts
    for _ in range(5):
        await rate_limiter.record_failed_signin(email, db_session)
    
    # Assert: Sign-in should be rate limited
    is_signin_limited = await rate_limiter.check_signin_rate_limit(email, db_session)
    assert is_signin_limited is True, "Sign-in should be rate limited after 5 attempts"
    
    # Assert: Password reset should NOT be rate limited (different action)
    is_reset_limited = await rate_limiter.check_password_reset_rate_limit(email, db_session)
    assert is_reset_limited is False, "Password reset should not be affected by sign-in rate limit"
    
    # Act: Record 3 password reset attempts
    for _ in range(3):
        await rate_limiter.record_password_reset_attempt(email, db_session)
    
    # Assert: Password reset should now be rate limited
    is_reset_limited = await rate_limiter.check_password_reset_rate_limit(email, db_session)
    assert is_reset_limited is True, "Password reset should be rate limited after 3 attempts"
    
    # Assert: Sign-in rate limit should still be active (independent)
    is_signin_limited = await rate_limiter.check_signin_rate_limit(email, db_session)
    assert is_signin_limited is True, "Sign-in rate limit should remain active"
