"""SQLAlchemy model for refresh token management."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class RefreshToken(Base):
    """Refresh token model for JWT token management.
    
    Stores refresh tokens that allow users to obtain new access tokens
    without re-authentication. Tokens can be revoked for security purposes.
    Each token has an expiration time and revocation status.
    
    Requirements: 2.5, 4.1, 4.3, 4.4, 8.1, 8.2
    """
    __tablename__ = "refresh_tokens"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to User
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Token data
    token = Column(String(500), unique=True, nullable=False, index=True)
    
    # Token status
    is_revoked = Column(Boolean, default=False, nullable=False, index=True)
    
    # Timestamp fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Relationship to User
    user = relationship("User", back_populates="refresh_tokens")
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_refresh_tokens_token_revoked', 'token', 'is_revoked'),
        Index('ix_refresh_tokens_user_revoked', 'user_id', 'is_revoked'),
        Index('ix_refresh_tokens_expires_at_revoked', 'expires_at', 'is_revoked'),
    )
