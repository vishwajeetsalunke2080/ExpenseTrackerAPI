"""Unit tests for database initialization functions."""
import pytest
from sqlalchemy import select
from app.database import initialize_default_categories, initialize_default_account_types
from app.models import Category, CategoryTypeEnum, AccountType


@pytest.mark.asyncio
async def test_initialize_default_categories_creates_all_defaults(db_session):
    """Test that initialize_default_categories creates all default categories."""
    # Initialize categories
    await initialize_default_categories(db_session)
    
    # Verify expense categories
    result = await db_session.execute(
        select(Category).where(Category.type == CategoryTypeEnum.EXPENSE)
    )
    expense_categories = result.scalars().all()
    expense_names = {cat.name for cat in expense_categories}
    
    assert "Food" in expense_names
    assert "Travel" in expense_names
    assert "Groceries" in expense_names
    assert "Shopping" in expense_names
    assert "Other" in expense_names
    
    # Verify income categories
    result = await db_session.execute(
        select(Category).where(Category.type == CategoryTypeEnum.INCOME)
    )
    income_categories = result.scalars().all()
    income_names = {cat.name for cat in income_categories}
    
    assert "Salary" in income_names
    assert "Cash" in income_names
    assert "Other Income" in income_names
    
    # Verify all are marked as default
    result = await db_session.execute(select(Category))
    all_categories = result.scalars().all()
    assert all(cat.is_default for cat in all_categories)


@pytest.mark.asyncio
async def test_initialize_default_categories_idempotent(db_session):
    """Test that initialize_default_categories can be called multiple times without duplicates."""
    # Initialize categories twice
    await initialize_default_categories(db_session)
    await initialize_default_categories(db_session)
    
    # Count categories
    result = await db_session.execute(select(Category))
    all_categories = result.scalars().all()
    
    # Should have exactly 8 categories (5 expense + 3 income)
    assert len(all_categories) == 8
    
    # Verify no duplicates by name
    names = [cat.name for cat in all_categories]
    assert len(names) == len(set(names))


@pytest.mark.asyncio
async def test_initialize_default_categories_skips_existing(db_session):
    """Test that initialize_default_categories skips categories that already exist."""
    # Create one category manually
    existing_category = Category(
        name="Food",
        type=CategoryTypeEnum.EXPENSE,
        is_default=False  # Not marked as default
    )
    db_session.add(existing_category)
    await db_session.commit()
    
    # Initialize categories
    await initialize_default_categories(db_session)
    
    # Verify Food category still exists and wasn't duplicated
    result = await db_session.execute(
        select(Category).where(Category.name == "Food")
    )
    food_categories = result.scalars().all()
    
    assert len(food_categories) == 1
    assert food_categories[0].is_default is False  # Original value preserved


@pytest.mark.asyncio
async def test_initialize_default_account_types_creates_all_defaults(db_session):
    """Test that initialize_default_account_types creates all default account types."""
    # Initialize account types
    await initialize_default_account_types(db_session)
    
    # Verify account types
    result = await db_session.execute(select(AccountType))
    account_types = result.scalars().all()
    account_names = {acc.name for acc in account_types}
    
    assert "Cash" in account_names
    assert "Card" in account_names
    assert "UPI" in account_names
    
    # Verify all are marked as default
    assert all(acc.is_default for acc in account_types)


@pytest.mark.asyncio
async def test_initialize_default_account_types_idempotent(db_session):
    """Test that initialize_default_account_types can be called multiple times without duplicates."""
    # Initialize account types twice
    await initialize_default_account_types(db_session)
    await initialize_default_account_types(db_session)
    
    # Count account types
    result = await db_session.execute(select(AccountType))
    all_account_types = result.scalars().all()
    
    # Should have exactly 3 account types
    assert len(all_account_types) == 3
    
    # Verify no duplicates by name
    names = [acc.name for acc in all_account_types]
    assert len(names) == len(set(names))


@pytest.mark.asyncio
async def test_initialize_default_account_types_skips_existing(db_session):
    """Test that initialize_default_account_types skips account types that already exist."""
    # Create one account type manually
    existing_account = AccountType(
        name="Cash",
        is_default=False  # Not marked as default
    )
    db_session.add(existing_account)
    await db_session.commit()
    
    # Initialize account types
    await initialize_default_account_types(db_session)
    
    # Verify Cash account type still exists and wasn't duplicated
    result = await db_session.execute(
        select(AccountType).where(AccountType.name == "Cash")
    )
    cash_accounts = result.scalars().all()
    
    assert len(cash_accounts) == 1
    assert cash_accounts[0].is_default is False  # Original value preserved


@pytest.mark.asyncio
async def test_initialize_both_functions_together(db_session):
    """Test that both initialization functions work correctly when called together."""
    # Initialize both
    await initialize_default_categories(db_session)
    await initialize_default_account_types(db_session)
    
    # Verify categories
    result = await db_session.execute(select(Category))
    categories = result.scalars().all()
    assert len(categories) == 8
    
    # Verify account types
    result = await db_session.execute(select(AccountType))
    account_types = result.scalars().all()
    assert len(account_types) == 3
