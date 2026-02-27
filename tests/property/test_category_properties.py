"""Property-based tests for category service.

Feature: expense-tracking-api
"""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
import re
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.services.category_service import CategoryService
from app.schemas.category import CategoryCreate, CategoryType
from app.database import Base


# Feature: expense-tracking-api, Property 21: Category creation uniqueness
@pytest.mark.asyncio
@settings(
    max_examples=25,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    category_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
    category_type=st.sampled_from([CategoryType.EXPENSE, CategoryType.INCOME])
)
async def test_property_21_category_creation_uniqueness(category_name, category_type):
    """
    Property 21: Category creation uniqueness
    **Validates: Requirements 11.1, 11.2**
    
    For any category name and type, attempting to create a category with a duplicate name
    should be rejected, and creating a category with a unique name should succeed and be retrievable.
    
    This test verifies that:
    1. A category with a unique name can be created successfully
    2. The created category can be retrieved by ID
    3. Attempting to create a duplicate category with the same name is rejected
    4. The uniqueness constraint is enforced regardless of category type
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
        # Initialize category service
        category_service = CategoryService(db_session)
        
        # Create category data
        category_data = CategoryCreate(
            name=category_name,
            type=category_type
        )
        
        # Test 1: Create category with unique name should succeed
        created_category = await category_service.create_category(category_data)
        
        assert created_category is not None, "Category creation should succeed"
        assert created_category.name == category_name, "Created category name should match input"
        assert created_category.type == category_type, "Created category type should match input"
        assert created_category.id is not None, "Created category should have an ID"
        assert created_category.is_default is False, "User-created category should not be default"
        
        # Test 2: Retrieve the created category by ID
        retrieved_category = await category_service.get_category(created_category.id)
        
        assert retrieved_category is not None, "Category should be retrievable by ID"
        assert retrieved_category.id == created_category.id, "Retrieved category ID should match"
        assert retrieved_category.name == category_name, "Retrieved category name should match"
        assert retrieved_category.type == category_type, "Retrieved category type should match"
        
        # Test 3: Attempting to create a duplicate category should be rejected
        duplicate_category_data = CategoryCreate(
            name=category_name,
            type=category_type
        )
        
        # Use re.escape to handle special regex characters in category name
        escaped_name = re.escape(category_name)
        with pytest.raises(ValueError, match=f"Category with name '{escaped_name}' already exists"):
            await category_service.create_category(duplicate_category_data)
        
        # Test 4: Verify uniqueness is enforced across types (same name, different type should also fail)
        # Category names must be unique regardless of type
        opposite_type = CategoryType.INCOME if category_type == CategoryType.EXPENSE else CategoryType.EXPENSE
        duplicate_different_type = CategoryCreate(
            name=category_name,
            type=opposite_type
        )
        
        with pytest.raises(ValueError, match=f"Category with name '{escaped_name}' already exists"):
            await category_service.create_category(duplicate_different_type)
        
        # Verify only one category with this name exists in the database
        all_categories = await category_service.list_categories()
        categories_with_name = [cat for cat in all_categories if cat.name == category_name]
        assert len(categories_with_name) == 1, (
            f"Only one category with name '{category_name}' should exist, "
            f"but found {len(categories_with_name)}"
        )
    
    # Clean up
    await engine.dispose()


# Feature: expense-tracking-api, Property 22: Category CRUD round-trip
@pytest.mark.asyncio
@settings(
    max_examples=25,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    category_name=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
    category_type=st.sampled_from([CategoryType.EXPENSE, CategoryType.INCOME])
)
async def test_property_22_category_crud_round_trip(category_name, category_type):
    """
    Property 22: Category CRUD round-trip
    **Validates: Requirements 11.1, 11.3**
    
    For any valid category data, creating the category and then retrieving it
    should return a category with equivalent field values.
    
    This test verifies that:
    1. A category can be created with valid data
    2. The created category can be retrieved by ID
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
        # Initialize category service
        category_service = CategoryService(db_session)
        
        # Create category data
        category_data = CategoryCreate(
            name=category_name,
            type=category_type
        )
        
        # Create the category
        created_category = await category_service.create_category(category_data)
        
        # Verify creation succeeded
        assert created_category is not None, "Category creation should succeed"
        assert created_category.id is not None, "Created category should have an ID"
        
        # Retrieve the category by ID
        retrieved_category = await category_service.get_category(created_category.id)
        
        # Verify retrieval succeeded
        assert retrieved_category is not None, "Category should be retrievable by ID"
        
        # Verify all field values match (round-trip equivalence)
        assert retrieved_category.id == created_category.id, "Category ID should match"
        assert retrieved_category.name == category_name, "Category name should match input"
        assert retrieved_category.type == category_type, "Category type should match input"
        assert retrieved_category.is_default == created_category.is_default, "is_default flag should match"
        assert retrieved_category.is_default is False, "User-created category should not be default"
        
        # Verify the retrieved category matches the created category exactly
        assert retrieved_category.name == created_category.name, "Retrieved name should match created name"
        assert retrieved_category.type == created_category.type, "Retrieved type should match created type"
    
    # Clean up
    await engine.dispose()
