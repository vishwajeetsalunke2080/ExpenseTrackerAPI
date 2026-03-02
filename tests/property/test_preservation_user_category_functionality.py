"""
Property-based tests for preservation of user category and account type functionality.

**Validates: Requirements 3.1, 3.2, 3.3, 3.5**

These tests verify that authenticated user operations for categories and account types
remain unchanged after the bugfix. They test the non-buggy code paths where user_id
is properly provided (isBugCondition returns false).

IMPORTANT: These tests should PASS on unfixed code to establish baseline behavior.
After implementing the fix, these tests should still PASS to confirm no regressions.
"""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, and_

from app.models.user import User
from app.models.expense import Category, CategoryTypeEnum, AccountType
from app.services.category_service import CategoryService
from app.services.account_type_service import AccountTypeService
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryType
from app.schemas.account_type import AccountTypeCreate, AccountTypeUpdate
from app.database import Base


# Strategy for generating valid category names
category_name_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters='\x00\n\r\t')
).filter(lambda x: x.strip())

# Strategy for generating valid email addresses
email_strategy = st.emails()



@pytest.mark.asyncio
@settings(
    max_examples=5,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    user_email=email_strategy,
    category_name=category_name_strategy,
    category_type=st.sampled_from([CategoryType.EXPENSE, CategoryType.INCOME])
)
async def test_property_preservation_category_creation_with_user_id(
    user_email, category_name, category_type
):
    """
    Property 2: Preservation - Category Creation with User ID
    
    For any authenticated user, creating a category should succeed and associate
    the category with the correct user_id. This is the non-buggy code path where
    user context is available.
    
    **Validates: Requirements 3.2, 3.3**
    """
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
        # Create a test user (authenticated user context)
        user = User(
            email=user_email,
            password_hash="hashed_password",
            is_active=True,
            is_verified=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Initialize category service with user context
        category_service = CategoryService(db_session, user)
        
        # Create category data
        category_data = CategoryCreate(
            name=category_name,
            type=category_type
        )
        
        # Act: Create category (should succeed with user_id)
        created_category = await category_service.create_category(category_data)
        
        # Assert: Category created successfully with correct user_id
        assert created_category is not None, "Category creation should succeed"
        assert created_category.name == category_name, "Category name should match"
        assert created_category.type == category_type, "Category type should match"
        assert created_category.is_default is False, "User-created category should not be default"
        
        # Verify in database that user_id is set correctly
        result = await db_session.execute(
            select(Category).where(Category.id == created_category.id)
        )
        db_category = result.scalar_one()
        assert db_category.user_id == user.id, "Category should have correct user_id"
    
    await engine.dispose()



@pytest.mark.asyncio
@settings(
    max_examples=5,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    user_email=email_strategy,
    category_name=category_name_strategy,
    category_type=st.sampled_from([CategoryType.EXPENSE, CategoryType.INCOME])
)
async def test_property_preservation_category_list_user_scoped(
    user_email, category_name, category_type
):
    """
    Property 2: Preservation - Category List Returns User-Scoped Categories
    
    For any authenticated user, GET /categories should return only categories
    belonging to that user, maintaining user isolation.
    
    **Validates: Requirements 3.1, 3.2**
    """
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
        # Create two users
        user1 = User(
            email=user_email,
            password_hash="hashed_password",
            is_active=True,
            is_verified=True
        )
        user2 = User(
            email=f"other_{user_email}",
            password_hash="hashed_password",
            is_active=True,
            is_verified=True
        )
        db_session.add(user1)
        db_session.add(user2)
        await db_session.commit()
        await db_session.refresh(user1)
        await db_session.refresh(user2)
        
        # Create category for user1
        category_service_user1 = CategoryService(db_session, user1)
        category_data = CategoryCreate(name=category_name, type=category_type)
        created_category = await category_service_user1.create_category(category_data)
        
        # Create category for user2 with different name
        category_service_user2 = CategoryService(db_session, user2)
        other_category_data = CategoryCreate(
            name=f"other_{category_name}",
            type=category_type
        )
        await category_service_user2.create_category(other_category_data)
        
        # Act: List categories for user1
        user1_categories = await category_service_user1.list_categories()
        
        # Assert: User1 sees only their own category
        assert len(user1_categories) == 1, "User should see only their own categories"
        assert user1_categories[0].id == created_category.id, "Should return user's category"
        assert user1_categories[0].name == category_name, "Category name should match"
        
        # Act: List categories for user2
        user2_categories = await category_service_user2.list_categories()
        
        # Assert: User2 sees only their own category
        assert len(user2_categories) == 1, "User should see only their own categories"
        assert user2_categories[0].name == f"other_{category_name}", "Should return user2's category"
    
    await engine.dispose()



@pytest.mark.asyncio
@settings(
    max_examples=5,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    user_email=email_strategy,
    original_name=category_name_strategy,
    updated_name=category_name_strategy,
    category_type=st.sampled_from([CategoryType.EXPENSE, CategoryType.INCOME])
)
async def test_property_preservation_category_update_user_owned(
    user_email, original_name, updated_name, category_type
):
    """
    Property 2: Preservation - Category Update Respects User Ownership
    
    For any authenticated user, PUT /categories/{id} should only update categories
    owned by that user, maintaining user isolation.
    
    **Validates: Requirements 3.2, 3.3**
    """
    assume(original_name != updated_name)
    
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
        # Create two users
        user1 = User(
            email=user_email,
            password_hash="hashed_password",
            is_active=True,
            is_verified=True
        )
        user2 = User(
            email=f"other_{user_email}",
            password_hash="hashed_password",
            is_active=True,
            is_verified=True
        )
        db_session.add(user1)
        db_session.add(user2)
        await db_session.commit()
        await db_session.refresh(user1)
        await db_session.refresh(user2)
        
        # Create category for user1
        category_service_user1 = CategoryService(db_session, user1)
        category_data = CategoryCreate(name=original_name, type=category_type)
        created_category = await category_service_user1.create_category(category_data)
        
        # Act: User1 updates their own category (should succeed)
        update_data = CategoryUpdate(name=updated_name)
        updated_category = await category_service_user1.update_category(
            created_category.id, update_data
        )
        
        # Assert: Update succeeded
        assert updated_category.name == updated_name, "Category name should be updated"
        assert updated_category.id == created_category.id, "Category ID should remain same"
        
        # Act: User2 tries to update user1's category (should fail)
        category_service_user2 = CategoryService(db_session, user2)
        with pytest.raises(ValueError, match="not found"):
            await category_service_user2.update_category(
                created_category.id, CategoryUpdate(name="hacked")
            )
    
    await engine.dispose()



@pytest.mark.asyncio
@settings(
    max_examples=5,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    user_email=email_strategy,
    category_name=category_name_strategy,
    category_type=st.sampled_from([CategoryType.EXPENSE, CategoryType.INCOME])
)
async def test_property_preservation_category_delete_user_owned(
    user_email, category_name, category_type
):
    """
    Property 2: Preservation - Category Delete Respects User Ownership
    
    For any authenticated user, DELETE /categories/{id} should only delete categories
    owned by that user, maintaining user isolation.
    
    **Validates: Requirements 3.2, 3.3**
    """
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
        # Create two users
        user1 = User(
            email=user_email,
            password_hash="hashed_password",
            is_active=True,
            is_verified=True
        )
        user2 = User(
            email=f"other_{user_email}",
            password_hash="hashed_password",
            is_active=True,
            is_verified=True
        )
        db_session.add(user1)
        db_session.add(user2)
        await db_session.commit()
        await db_session.refresh(user1)
        await db_session.refresh(user2)
        
        # Create category for user1
        category_service_user1 = CategoryService(db_session, user1)
        category_data = CategoryCreate(name=category_name, type=category_type)
        created_category = await category_service_user1.create_category(category_data)
        
        # Act: User2 tries to delete user1's category (should fail)
        category_service_user2 = CategoryService(db_session, user2)
        with pytest.raises(ValueError, match="not found"):
            await category_service_user2.delete_category(created_category.id)
        
        # Verify category still exists
        result = await db_session.execute(
            select(Category).where(Category.id == created_category.id)
        )
        still_exists = result.scalar_one_or_none()
        assert still_exists is not None, "Category should still exist after failed delete"
        
        # Act: User1 deletes their own category (should succeed)
        delete_result = await category_service_user1.delete_category(created_category.id)
        assert delete_result is True, "Delete should succeed for owner"
        
        # Verify category is deleted
        result = await db_session.execute(
            select(Category).where(Category.id == created_category.id)
        )
        deleted = result.scalar_one_or_none()
        assert deleted is None, "Category should be deleted"
    
    await engine.dispose()



@pytest.mark.asyncio
@settings(
    max_examples=5,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    user_email=email_strategy,
    account_name=category_name_strategy
)
async def test_property_preservation_account_type_creation_with_user_id(
    user_email, account_name
):
    """
    Property 2: Preservation - Account Type Creation with User ID
    
    For any authenticated user, creating an account type should succeed and associate
    the account type with the correct user_id.
    
    **Validates: Requirements 3.1, 3.5**
    """
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
        # Create a test user
        user = User(
            email=user_email,
            password_hash="hashed_password",
            is_active=True,
            is_verified=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Initialize account type service with user context
        account_service = AccountTypeService(db_session, user)
        
        # Create account type data
        account_data = AccountTypeCreate(name=account_name)
        
        # Act: Create account type (should succeed with user_id)
        created_account = await account_service.create_account_type(account_data)
        
        # Assert: Account type created successfully with correct user_id
        assert created_account is not None, "Account type creation should succeed"
        assert created_account.name == account_name, "Account type name should match"
        assert created_account.is_default is False, "User-created account type should not be default"
        
        # Verify in database that user_id is set correctly
        result = await db_session.execute(
            select(AccountType).where(AccountType.id == created_account.id)
        )
        db_account = result.scalar_one()
        assert db_account.user_id == user.id, "Account type should have correct user_id"
    
    await engine.dispose()



@pytest.mark.asyncio
@settings(
    max_examples=5,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    user_email=email_strategy,
    account_name=category_name_strategy
)
async def test_property_preservation_account_type_user_isolation(
    user_email, account_name
):
    """
    Property 2: Preservation - Account Type User Isolation
    
    For any authenticated users, account type operations should maintain user isolation.
    User A cannot access User B's account types.
    
    **Validates: Requirements 3.1, 3.5**
    """
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
        # Create two users
        user1 = User(
            email=user_email,
            password_hash="hashed_password",
            is_active=True,
            is_verified=True
        )
        user2 = User(
            email=f"other_{user_email}",
            password_hash="hashed_password",
            is_active=True,
            is_verified=True
        )
        db_session.add(user1)
        db_session.add(user2)
        await db_session.commit()
        await db_session.refresh(user1)
        await db_session.refresh(user2)
        
        # Create account type for user1
        account_service_user1 = AccountTypeService(db_session, user1)
        account_data = AccountTypeCreate(name=account_name)
        created_account = await account_service_user1.create_account_type(account_data)
        
        # Create account type for user2 with different name
        account_service_user2 = AccountTypeService(db_session, user2)
        other_account_data = AccountTypeCreate(name=f"other_{account_name}")
        await account_service_user2.create_account_type(other_account_data)
        
        # Act: List account types for user1
        user1_accounts = await account_service_user1.list_account_types()
        
        # Assert: User1 sees only their own account type
        assert len(user1_accounts) == 1, "User should see only their own account types"
        assert user1_accounts[0].id == created_account.id, "Should return user's account type"
        assert user1_accounts[0].name == account_name, "Account type name should match"
        
        # Act: List account types for user2
        user2_accounts = await account_service_user2.list_account_types()
        
        # Assert: User2 sees only their own account type
        assert len(user2_accounts) == 1, "User should see only their own account types"
        assert user2_accounts[0].name == f"other_{account_name}", "Should return user2's account type"
        
        # Act: User2 tries to access user1's account type (should fail)
        retrieved = await account_service_user2.get_account_type(created_account.id)
        assert retrieved is None, "User2 should not be able to access user1's account type"
    
    await engine.dispose()



@pytest.mark.asyncio
@settings(
    max_examples=5,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    user_email=email_strategy,
    category_name=category_name_strategy
)
async def test_property_preservation_category_filtering_by_type(
    user_email, category_name
):
    """
    Property 2: Preservation - Category Filtering by Type
    
    For any authenticated user, filtering categories by type (expense/income)
    should continue to work correctly.
    
    **Validates: Requirements 3.1, 3.2**
    """
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
        # Create a test user
        user = User(
            email=user_email,
            password_hash="hashed_password",
            is_active=True,
            is_verified=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Initialize category service
        category_service = CategoryService(db_session, user)
        
        # Create expense category
        expense_data = CategoryCreate(
            name=f"expense_{category_name}",
            type=CategoryType.EXPENSE
        )
        expense_category = await category_service.create_category(expense_data)
        
        # Create income category
        income_data = CategoryCreate(
            name=f"income_{category_name}",
            type=CategoryType.INCOME
        )
        income_category = await category_service.create_category(income_data)
        
        # Act: List all categories
        all_categories = await category_service.list_categories()
        assert len(all_categories) == 2, "Should have 2 categories total"
        
        # Act: Filter by expense type
        expense_categories = await category_service.list_categories(CategoryType.EXPENSE)
        assert len(expense_categories) == 1, "Should have 1 expense category"
        assert expense_categories[0].id == expense_category.id, "Should return expense category"
        assert expense_categories[0].type == CategoryType.EXPENSE, "Type should be expense"
        
        # Act: Filter by income type
        income_categories = await category_service.list_categories(CategoryType.INCOME)
        assert len(income_categories) == 1, "Should have 1 income category"
        assert income_categories[0].id == income_category.id, "Should return income category"
        assert income_categories[0].type == CategoryType.INCOME, "Type should be income"
    
    await engine.dispose()
