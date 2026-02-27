"""SQLAlchemy model for OAuth account linking."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class OAuthAccount(Base):
    """OAuth account model for linking users with external OAuth providers.
    
    Stores OAuth provider information and tokens for users who authenticate
    via OAuth providers (e.g., Google, GitHub). Each user can have multiple
    OAuth accounts from different providers.
    
    Requirements: 3.4, 3.6
    """
    __tablename__ = "oauth_accounts"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to User
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # OAuth provider information
    provider = Column(String(50), nullable=False, index=True)  # e.g., 'google', 'github'
    provider_user_id = Column(String(255), nullable=False)  # User ID from the OAuth provider
    
    # OAuth tokens (optional, may be stored for API access)
    access_token = Column(String(500), nullable=True)
    refresh_token = Column(String(500), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamp fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationship to User
    user = relationship("User", back_populates="oauth_accounts")
    
    # Constraints and indexes
    __table_args__ = (
        # Unique constraint: one provider account can only be linked to one user
        UniqueConstraint('provider', 'provider_user_id', name='uq_provider_user'),
        # Index for common queries
        Index('ix_oauth_accounts_user_provider', 'user_id', 'provider'),
    )
