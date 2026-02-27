"""SQLAlchemy model for account locking."""
from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func
from app.database import Base


class AccountLock(Base):
    """Account lock model for temporary account lockouts.
    
    Records account locks due to excessive failed authentication attempts.
    Accounts are locked for a specified duration (typically 15 minutes).
    
    Requirements: 10.1, 10.4
    """
    __tablename__ = "account_locks"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Account lock details
    email = Column(String(255), unique=True, nullable=False, index=True)
    locked_until = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
