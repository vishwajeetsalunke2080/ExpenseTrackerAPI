"""Database configuration and session management."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator

# Import settings to get DATABASE_URL
from app.config import settings

# Database URL from settings
DATABASE_URL = settings.database_url

# Create async engine with connection pool settings
# SQLite doesn't support pool settings, so we conditionally apply them
if "sqlite" in DATABASE_URL.lower():
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
    )
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,  # Set to False in production
        future=True,
        pool_size=20,  # Maximum number of connections to keep in the pool
        max_overflow=10,  # Maximum number of connections that can be created beyond pool_size
        pool_timeout=30,  # Seconds to wait before giving up on getting a connection
        pool_recycle=3600,  # Recycle connections after 1 hour to prevent stale connections
        pool_pre_ping=True,  # Test connections before using them to catch closed connections
    )

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables.
    
    Creates all tables defined in the models if they don't exist.
    Must be called after all models are imported.
    """
    # Import all models to ensure they're registered with Base.metadata
    from app.models import Expense, Income, Category, AccountType, Budget, User, OAuthAccount, RefreshToken, EmailVerificationToken, PasswordResetToken, AuthLog, RateLimitAttempt, AccountLock
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def initialize_default_categories(db: AsyncSession) -> None:
    """
    Initialize default categories for expenses and income.
    
    Creates default expense categories: Food, Travel, Groceries, Shopping, Other
    Creates default income categories: Salary, Cash, Other Income
    
    Only inserts categories that don't already exist (checks by name).
    
    Args:
        db: Database session
        
    Requirements: 11.6, 11.7
    """
    from sqlalchemy import select
    from app.models import Category, CategoryTypeEnum
    
    # Define default categories
    default_expense_categories = ["Food", "Travel", "Groceries", "Shopping", "Other"]
    default_income_categories = ["Salary", "Cash", "Other Income"]
    
    # Check and insert expense categories
    for category_name in default_expense_categories:
        result = await db.execute(
            select(Category).where(Category.name == category_name)
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            category = Category(
                name=category_name,
                type=CategoryTypeEnum.EXPENSE,
                is_default=True
            )
            db.add(category)
    
    # Check and insert income categories
    for category_name in default_income_categories:
        result = await db.execute(
            select(Category).where(Category.name == category_name)
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            category = Category(
                name=category_name,
                type=CategoryTypeEnum.INCOME,
                is_default=True
            )
            db.add(category)
    
    await db.commit()


async def initialize_default_account_types(db: AsyncSession) -> None:
    """
    Initialize default account types.
    
    Creates default account types: Cash, Card, UPI
    
    Only inserts account types that don't already exist (checks by name).
    
    Args:
        db: Database session
        
    Requirements: 12.6
    """
    from sqlalchemy import select
    from app.models import AccountType
    
    # Define default account types
    default_account_types = ["Cash", "Card", "UPI"]
    
    # Check and insert account types
    for account_name in default_account_types:
        result = await db.execute(
            select(AccountType).where(AccountType.name == account_name)
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            account_type = AccountType(
                name=account_name,
                is_default=True
            )
            db.add(account_type)
    
    await db.commit()
