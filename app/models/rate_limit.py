"""SQLAlchemy model for rate limiting attempts."""
from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func
from app.database import Base


class RateLimitAttempt(Base):
    """Rate limit attempt model for tracking authentication attempts.
    
    Records authentication attempts (sign-in, password reset) to enable
    rate limiting and brute force protection.
    
    Requirements: 10.1, 10.4
    """
    __tablename__ = "rate_limit_attempts"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Rate limiting details
    email = Column(String(255), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)  # 'signin', 'password_reset'
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Composite indexes for efficient querying
    __table_args__ = (
        Index('ix_rate_limit_email_action_created', 'email', 'action', 'created_at'),
    )
