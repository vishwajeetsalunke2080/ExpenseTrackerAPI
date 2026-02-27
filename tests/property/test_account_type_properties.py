"""Property-based tests for account type service.

Feature: expense-tracking-api
"""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
import re
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.services.account_type_service import AccountTypeService
from app.schemas.account_type import AccountTypeCreate
from app.database import Base


# Feature: expense-tracking-api, Property 23: Account type creation uniqueness
@pytest.mark.asyncio
@settings(
    max_examples=25,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    account_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=32, max_codepoint=126))
)
async def test_property_23_account_type_creation_uniqueness(account_name):
    """
    Property 23: Account type creation uniqueness
    **Validates: Requirements 12.1, 12.2**
    
    For any account type name, attempting to create an account type with a duplicate name
    should be rejected, and creating an account type with a unique name should succeed and be retrievable.
    
    This test verifies that:
    1. An account type with a unique name can be created successfully
    2. The created account type can be retrieved by ID
    3. Attempting to create a duplicate account type with the same name is rejected
    4. The uniqueness constraint is enforced
    """
    # Create a fresh database for each test iteration
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    
    async with async_session() as db_session:
        # Initialize account type service
        account_service = AccountTypeService(db_session)
        
        # Create account type data
        account_data = AccountTypeCreate(
            name=account_name
        )
        
        # Test 1: Create account type with unique name should succeed
        created_account = await account_service.create_account_type(account_data)
        
        assert created_account is not None, "Account type creation should succeed"
        assert created_account.name == account_name, "Created account type name should match input"
        assert created_account.id is not None, "Created account type should have an ID"
        assert created_account.is_default is False, "User-created account type should not be default"
        
        # Test 2: Retrieve the created account type by ID
        retrieved_account = await account_service.get_account_type(created_account.id)
        
        assert retrieved_account is not None, "Account type should be retrievable by ID"
        assert retrieved_account.id == created_account.id, "Retrieved account type ID should match"
        assert retrieved_account.name == account_name, "Retrieved account type name should match"
        
        # Test 3: Attempting to create a duplicate account type should be rejected
        duplicate_account_data = AccountTypeCreate(
            name=account_name
        )
        
        # Use re.escape to handle special regex characters in account name
        escaped_name = re.escape(account_name)
        with pytest.raises(ValueError, match=f"Account type with name '{escaped_name}' already exists"):
            await account_service.create_account_type(duplicate_account_data)
        
        # Verify only one account type with this name exists in the database
        all_accounts = await account_service.list_account_types()
        accounts_with_name = [acc for acc in all_accounts if acc.name == account_name]
        assert len(accounts_with_name) == 1, (
            f"Only one account type with name '{account_name}' should exist, "
            f"but found {len(accounts_with_name)}"
        )
    
    # Clean up
    await engine.dispose()


# Feature: expense-tracking-api, Property 24: Account type CRUD round-trip
@pytest.mark.asyncio
@settings(
    max_examples=25,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    account_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=32, max_codepoint=126))
)
async def test_property_24_account_type_crud_round_trip(account_name):
    """
    Property 24: Account type CRUD round-trip
    **Validates: Requirements 12.1, 12.3**
    
    For any valid account type data, creating the account type and then retrieving it
    should return an account type with equivalent field values.
    
    This test verifies that:
    1. An account type can be created with valid data
    2. The created account type can be retrieved by ID
    3. All field values match between creation and retrieval
    4. The round-trip preserves data integrity
    """
    # Create a fresh database for each test iteration
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    
    async with async_session() as db_session:
        # Initialize account type service
        account_service = AccountTypeService(db_session)
        
        # Create account type data
        account_data = AccountTypeCreate(
            name=account_name
        )
        
        # Create the account type
        created_account = await account_service.create_account_type(account_data)
        
        # Verify creation succeeded
        assert created_account is not None, "Account type creation should succeed"
        assert created_account.id is not None, "Created account type should have an ID"
        
        # Retrieve the account type by ID
        retrieved_account = await account_service.get_account_type(created_account.id)
        
        # Verify retrieval succeeded
        assert retrieved_account is not None, "Account type should be retrievable by ID"
        
        # Verify all field values match (round-trip equivalence)
        assert retrieved_account.id == created_account.id, "Account type ID should match"
        assert retrieved_account.name == account_name, "Account type name should match input"
        assert retrieved_account.is_default == created_account.is_default, "is_default flag should match"
        assert retrieved_account.is_default is False, "User-created account type should not be default"
        
        # Verify the retrieved account type matches the created account type exactly
        assert retrieved_account.name == created_account.name, "Retrieved name should match created name"
    
    # Clean up
    await engine.dispose()
