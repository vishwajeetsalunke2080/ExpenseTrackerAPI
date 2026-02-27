"""SQLAlchemy model for email verification token management."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class EmailVerificationToken(Base):
    """Email verification token model for user email verification.
    
    Stores verification tokens that are sent to users during registration
    to verify their email addresses. Tokens expire after 24 hours and can
    only be used once. Each token is linked to a specific user.
    
    Requirements: 7.1, 7.3, 7.6
    """
    __tablename__ = "email_verification_tokens"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to User
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Token data
    token = Column(String(500), unique=True, nullable=False, index=True)
    
    # Token status
    used = Column(Boolean, default=False, nullable=False)
    
    # Timestamp fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_email_verification_tokens_token_used', 'token', 'used'),
        Index('ix_email_verification_tokens_user_used', 'user_id', 'used'),
        Index('ix_email_verification_tokens_expires_at_used', 'expires_at', 'used'),
    )
