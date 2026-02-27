"""SQLAlchemy model for password reset tokens."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class PasswordResetToken(Base):
    """Password reset token model for secure password recovery.
    
    Stores time-limited tokens for password reset functionality.
    Tokens expire after 1 hour and can only be used once.
    
    Requirements: 5.1, 5.3, 5.4
    """
    __tablename__ = "password_reset_tokens"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Token fields
    token = Column(String(255), unique=True, nullable=False, index=True)
    
    # Timestamp fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Status field
    used = Column(Boolean, default=False, nullable=False)
    
    # Relationship
    user = relationship("User", backref="password_reset_tokens")
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_password_reset_tokens_token_used', 'token', 'used'),
        Index('ix_password_reset_tokens_expires_at_used', 'expires_at', 'used'),
    )
