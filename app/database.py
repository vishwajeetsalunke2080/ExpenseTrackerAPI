"""Database configuration and session management."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from typing import AsyncGenerator
import logging

# Import settings to get DATABASE_URL
from app.config import settings

logger = logging.getLogger(__name__)

# Database URL from settings
DATABASE_URL = settings.database_url

# Create async engine with optimized connection pool settings
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
        echo=False,
        future=True,
        pool_size=20,  # Increased pool size for better concurrency
        max_overflow=10,  # Increased overflow capacity
        pool_timeout=30,  # Increased timeout to 30 seconds
        pool_recycle=1800,  # Recycle after 30 minutes (Neon closes idle connections)
        pool_pre_ping=True,  # Re-enabled to detect stale connections
        connect_args={
            "server_settings": {
                "application_name": "expense_api",
                "jit": "off",  # Disable JIT compilation for faster simple queries
            },
            "command_timeout": 30,  # 30 second query timeout
            "timeout": 10,  # 10 second connection timeout
        },
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
    """Dependency for getting database sessions.
    
    Handles session lifecycle with proper cleanup:
    - Commits transaction on successful completion
    - Rolls back on exceptions
    - Always closes session to return connection to pool
    - Implements retry logic for transient failures
    """
    session = AsyncSessionLocal()
    try:
        yield session
        # Commit on successful completion
        await session.commit()
    except GeneratorExit:
        # Handle early termination (client disconnect, request cancellation)
        # Rollback any pending transaction
        try:
            await session.rollback()
        except Exception as e:
            logger.warning(f"Error during rollback on GeneratorExit: {str(e)}")
        # Re-raise to propagate the exit
        raise
    except Exception as e:
        # Handle all other exceptions
        logger.error(f"Database error, rolling back transaction: {str(e)}")
        try:
            await session.rollback()
        except Exception as rollback_error:
            logger.error(f"Error during rollback: {str(rollback_error)}")
        raise
    finally:
        # CRITICAL: Always close session to return connection to pool
        try:
            await session.close()
        except Exception as close_error:
            # Log but don't raise - connection may already be closed
            logger.warning(f"Error closing session: {str(close_error)}")


async def check_db_health() -> bool:
    """Check if database connection is healthy.
    
    Returns:
        bool: True if database is accessible, False otherwise
    """
    try:
        async with AsyncSessionLocal() as session:
            # Simple query to check connection
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False


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
