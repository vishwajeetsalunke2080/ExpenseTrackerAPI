"""Shared test fixtures for the test suite."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator
import os

# Set test environment variables before importing app modules
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"  # Use different DB for tests
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-min-32-characters-long"
os.environ["JWT_ALGORITHM"] = "HS256"

from app.database import Base, get_db
try:
    from app.cache import get_redis
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
from main import app


@pytest_asyncio.fixture
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session (alias for test_db)."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    
    async with async_session() as session:
        yield session
        # Rollback any uncommitted changes after the test
        await session.rollback()
    
    # Clean all tables after each test to ensure isolation
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture
async def test_client(test_db) -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client with database overrides."""
    async def override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    if REDIS_AVAILABLE:
        # Only override redis if it's available
        try:
            redis_client = await anext(redis_client_fixture())
            async def override_get_redis():
                return redis_client
            app.dependency_overrides[get_redis] = override_get_redis
        except:
            pass
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator:
    """Create a test Redis client using fakeredis (only if redis is available)."""
    if not REDIS_AVAILABLE:
        pytest.skip("Redis not available")
    
    import fakeredis.aioredis
    
    client = fakeredis.aioredis.FakeRedis(
        decode_responses=True
    )
    
    # Clear test database before each test
    await client.flushdb()
    
    yield client
    
    # Clean up after test
    await client.flushdb()
    await client.aclose()
