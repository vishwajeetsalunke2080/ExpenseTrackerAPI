"""Database configuration and session management."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator
import ssl

# Import settings to get DATABASE_URL
from app.config import settings

# Database URL from settings
DATABASE_URL = settings.database_url

# Create SSL context for Neon database (disable SSL verification for testing)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Create async engine with connection pool settings
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to False in production
    future=True,
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=5,  # Number of connections to maintain
    max_overflow=10,  # Additional connections when pool is full
    connect_args={
        "timeout": 120,  # Connection timeout in seconds
        "command_timeout": 60,  # Command execution timeout
        "server_settings": {
            "application_name": "expense_api"
        },
        "ssl": ssl_context  # SSL context for secure connection
    }
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
    """Initialize database tables and run migrations.
    
    This function:
    1. Checks and runs Alembic migrations if needed
    2. Creates any tables not managed by migrations (fallback)
    3. Validates database state
    
    Raises:
        PartialDatabaseError: When manual recovery is needed
        UnknownVersionError: When migration history is corrupted
        MigrationExecutionError: When migration execution fails
        DatabaseConnectionError: When database is unreachable
    """
    from app.migrations.manager import MigrationManager
    
    # Import all models to ensure they're registered with Base.metadata
    from app.models import (
        Expense, Income, Category, AccountType, Budget, User,
        OAuthAccount, RefreshToken, EmailVerificationToken,
        PasswordResetToken, AuthLog, RateLimitAttempt, AccountLock
    )
    
    # Check and run migrations
    migration_manager = MigrationManager(engine)
    await migration_manager.check_and_run_migrations()
    
    # Fallback: create any tables not managed by migrations
    # This is safe because create_all() is idempotent
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)




