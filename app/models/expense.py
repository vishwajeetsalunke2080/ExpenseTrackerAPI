"""SQLAlchemy models for expense tracking entities."""
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Boolean, Enum, Index, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class CategoryTypeEnum(enum.Enum):
    """Enum for category types."""
    EXPENSE = "expense"
    INCOME = "income"


class Expense(Base):
    """Expense model for tracking spending transactions."""
    __tablename__ = "expenses"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    account = Column(String(100), nullable=False, index=True)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="expenses")
    
    # Composite indexes for common query patterns with user isolation
    __table_args__ = (
        Index('ix_expenses_user_date', 'user_id', 'date'),
        Index('ix_expenses_user_category', 'user_id', 'category'),
        Index('ix_expenses_user_account', 'user_id', 'account'),
        Index('ix_expenses_user_date_category', 'user_id', 'date', 'category'),
    )


class Income(Base):
    """Income model for tracking income transactions."""
    __tablename__ = "income"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="income")
    
    # Composite indexes for common query patterns with user isolation
    __table_args__ = (
        Index('ix_income_user_date', 'user_id', 'date'),
        Index('ix_income_user_category', 'user_id', 'category'),
        Index('ix_income_user_date_category', 'user_id', 'date', 'category'),
    )


class Category(Base):
    """Category model for expense and income classification."""
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    type = Column(Enum(CategoryTypeEnum), nullable=False, index=True)
    is_default = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="categories")
    
    # Composite indexes and unique constraint for user-scoped category names
    __table_args__ = (
        Index('ix_categories_user_name', 'user_id', 'name'),
        Index('ix_categories_user_type', 'user_id', 'type'),
        UniqueConstraint('user_id', 'name', name='uq_categories_user_name'),
    )


class AccountType(Base):
    """Account type model for payment methods."""
    __tablename__ = "account_types"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    is_default = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="account_types")
    
    # Composite index and unique constraint for user-scoped account type names
    __table_args__ = (
        Index('ix_account_types_user_name', 'user_id', 'name'),
        UniqueConstraint('user_id', 'name', name='uq_account_types_user_name'),
    )


class Budget(Base):
    """Budget model for monthly spending limits that apply to every month."""
    __tablename__ = "budgets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    amount_limit = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="budgets")
    
    # Composite index and unique constraint: one budget per category per user
    __table_args__ = (
        Index('ix_budgets_user_category', 'user_id', 'category'),
        UniqueConstraint('user_id', 'category', name='uq_budgets_user_category'),
    )
