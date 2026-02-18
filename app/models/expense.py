"""SQLAlchemy models for expense tracking entities."""
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Boolean, Enum, Index
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
    date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    account = Column(String(100), nullable=False, index=True)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Composite index for common query patterns
    __table_args__ = (
        Index('ix_expenses_date_category', 'date', 'category'),
        Index('ix_expenses_date_account', 'date', 'account'),
    )


class Income(Base):
    """Income model for tracking income transactions."""
    __tablename__ = "income"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Composite index for common query patterns
    __table_args__ = (
        Index('ix_income_date_category', 'date', 'category'),
    )


class Category(Base):
    """Category model for expense and income classification."""
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    type = Column(Enum(CategoryTypeEnum), nullable=False, index=True)
    is_default = Column(Boolean, default=False, nullable=False)


class AccountType(Base):
    """Account type model for payment methods."""
    __tablename__ = "account_types"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    is_default = Column(Boolean, default=False, nullable=False)


class Budget(Base):
    """Budget model for monthly spending limits that apply to every month."""
    __tablename__ = "budgets"
    
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=False, index=True, unique=True)  # One budget per category
    amount_limit = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
