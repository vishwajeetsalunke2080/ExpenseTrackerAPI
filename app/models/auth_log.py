"""SQLAlchemy model for authentication logging."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from app.database import Base


class AuthLog(Base):
    """Authentication log model for security auditing.
    
    Records all authentication attempts including sign-in, sign-up,
    password reset, and other authentication-related actions.
    
    Requirements: 10.3
    """
    __tablename__ = "auth_logs"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User reference (nullable for failed attempts where user doesn't exist)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Authentication details
    email = Column(String(255), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)  # 'signin', 'signup', 'password_reset', etc.
    success = Column(Boolean, nullable=False, index=True)
    
    # Request metadata
    ip_address = Column(String(45), nullable=False)  # IPv6 max length is 45
    user_agent = Column(String(500), nullable=True)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index('ix_auth_logs_user_action', 'user_id', 'action'),
        Index('ix_auth_logs_email_action', 'email', 'action'),
        Index('ix_auth_logs_success_created', 'success', 'created_at'),
    )
