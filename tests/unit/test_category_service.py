"""Unit tests for CategoryService."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.category_service import CategoryService
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryType
from app.models.expense import Category, CategoryTypeEnum


@pytest.mark.asyncio
async def test_create_category_success(db_session: AsyncSession):
    """Test successful category creation."""
    service = CategoryService(db_session)
    
    category_data = CategoryCreate(name="Entertainment", type=CategoryType.EXPENSE)
    result = await service.create_category(category_data)
    
    assert result.id is not None
    assert result.name == "Entertainment"
    assert result.type == CategoryType.EXPENSE
    assert result.is_default is False


@pytest.mark.asyncio
async def test_create_category_duplicate_name(db_session: AsyncSession):
    """Test that duplicate category names are rejected."""
    service = CategoryService(db_session)
    
    # Create first category
    category_data = CategoryCreate(name="Entertainment", type=CategoryType.EXPENSE)
    await service.create_category(category_data)
    
    # Try to create duplicate
    with pytest.raises(ValueError, match="already exists"):
        await service.create_category(category_data)


@pytest.mark.asyncio
async def test_get_category_success(db_session: AsyncSession):
    """Test retrieving a category by ID."""
    service = CategoryService(db_session)
    
    # Create category
    category_data = CategoryCreate(name="Entertainment", type=CategoryType.EXPENSE)
    created = await service.create_category(category_data)
    
    # Retrieve it
    result = await service.get_category(created.id)
    
    assert result is not None
    assert result.id == created.id
    assert result.name == "Entertainment"


@pytest.mark.asyncio
async def test_get_category_not_found(db_session: AsyncSession):
    """Test retrieving non-existent category returns None."""
    service = CategoryService(db_session)
    
    result = await service.get_category(99999)
    
    assert result is None


@pytest.mark.asyncio
async def test_list_categories_all(db_session: AsyncSession):
    """Test listing all categories."""
    service = CategoryService(db_session)
    
    # Create multiple categories
    await service.create_category(CategoryCreate(name="Entertainment", type=CategoryType.EXPENSE))
    await service.create_category(CategoryCreate(name="Utilities", type=CategoryType.EXPENSE))
    await service.create_category(CategoryCreate(name="Bonus", type=CategoryType.INCOME))
    
    # List all
    result = await service.list_categories()
    
    assert len(result) >= 3
    names = [cat.name for cat in result]
    assert "Entertainment" in names
    assert "Utilities" in names
    assert "Bonus" in names


@pytest.mark.asyncio
async def test_list_categories_filtered_by_type(db_session: AsyncSession):
    """Test listing categories filtered by type."""
    service = CategoryService(db_session)
    
    # Create categories of different types
    await service.create_category(CategoryCreate(name="Entertainment", type=CategoryType.EXPENSE))
    await service.create_category(CategoryCreate(name="Utilities", type=CategoryType.EXPENSE))
    await service.create_category(CategoryCreate(name="Bonus", type=CategoryType.INCOME))
    
    # List only expense categories
    expense_result = await service.list_categories(CategoryType.EXPENSE)
    expense_names = [cat.name for cat in expense_result]
    
    assert "Entertainment" in expense_names
    assert "Utilities" in expense_names
    assert "Bonus" not in expense_names
    
    # List only income categories
    income_result = await service.list_categories(CategoryType.INCOME)
    income_names = [cat.name for cat in income_result]
    
    assert "Bonus" in income_names
    assert "Entertainment" not in income_names


@pytest.mark.asyncio
async def test_update_category_success(db_session: AsyncSession):
    """Test updating a category name."""
    service = CategoryService(db_session)
    
    # Create category
    category_data = CategoryCreate(name="Entertainment", type=CategoryType.EXPENSE)
    created = await service.create_category(category_data)
    
    # Update it
    updates = CategoryUpdate(name="Fun")
    result = await service.update_category(created.id, updates)
    
    assert result.id == created.id
    assert result.name == "Fun"
    assert result.type == CategoryType.EXPENSE


@pytest.mark.asyncio
async def test_update_category_not_found(db_session: AsyncSession):
    """Test updating non-existent category raises error."""
    service = CategoryService(db_session)
    
    updates = CategoryUpdate(name="NewName")
    
    with pytest.raises(ValueError, match="not found"):
        await service.update_category(99999, updates)


@pytest.mark.asyncio
async def test_update_category_duplicate_name(db_session: AsyncSession):
    """Test updating to duplicate name is rejected."""
    service = CategoryService(db_session)
    
    # Create two categories
    cat1 = await service.create_category(CategoryCreate(name="Entertainment", type=CategoryType.EXPENSE))
    cat2 = await service.create_category(CategoryCreate(name="Utilities", type=CategoryType.EXPENSE))
    
    # Try to update cat2 to have same name as cat1
    updates = CategoryUpdate(name="Entertainment")
    
    with pytest.raises(ValueError, match="already exists"):
        await service.update_category(cat2.id, updates)


@pytest.mark.asyncio
async def test_delete_category_success(db_session: AsyncSession):
    """Test deleting a non-default category."""
    service = CategoryService(db_session)
    
    # Create category
    category_data = CategoryCreate(name="Entertainment", type=CategoryType.EXPENSE)
    created = await service.create_category(category_data)
    
    # Delete it
    result = await service.delete_category(created.id)
    
    assert result is True
    
    # Verify it's gone
    retrieved = await service.get_category(created.id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_delete_category_not_found(db_session: AsyncSession):
    """Test deleting non-existent category raises error."""
    service = CategoryService(db_session)
    
    with pytest.raises(ValueError, match="not found"):
        await service.delete_category(99999)


@pytest.mark.asyncio
async def test_delete_default_category_rejected(db_session: AsyncSession):
    """Test that default categories cannot be deleted."""
    service = CategoryService(db_session)
    
    # Initialize defaults
    await service.initialize_defaults()
    
    # Try to find and delete a default category
    categories = await service.list_categories()
    default_category = next((cat for cat in categories if cat.is_default), None)
    
    assert default_category is not None
    
    with pytest.raises(ValueError, match="Cannot delete default category"):
        await service.delete_category(default_category.id)


@pytest.mark.asyncio
async def test_initialize_defaults(db_session: AsyncSession):
    """Test initializing default categories."""
    service = CategoryService(db_session)
    
    # Initialize defaults
    await service.initialize_defaults()
    
    # Check expense defaults
    expense_categories = await service.list_categories(CategoryType.EXPENSE)
    expense_names = [cat.name for cat in expense_categories]
    
    assert "Food" in expense_names
    assert "Travel" in expense_names
    assert "Groceries" in expense_names
    assert "Shopping" in expense_names
    assert "Other Expense" in expense_names
    
    # Check income defaults
    income_categories = await service.list_categories(CategoryType.INCOME)
    income_names = [cat.name for cat in income_categories]
    
    assert "Salary" in income_names
    assert "Cash" in income_names
    assert "Other Income" in income_names
    
    # Verify they're marked as default
    for cat in expense_categories + income_categories:
        if cat.name in ["Food", "Travel", "Groceries", "Shopping", "Other Expense", "Salary", "Cash", "Other Income"]:
            assert cat.is_default is True


@pytest.mark.asyncio
async def test_initialize_defaults_idempotent(db_session: AsyncSession):
    """Test that initializing defaults multiple times doesn't create duplicates."""
    service = CategoryService(db_session)
    
    # Initialize twice
    await service.initialize_defaults()
    await service.initialize_defaults()
    
    # Count categories
    all_categories = await service.list_categories()
    
    # Should have exactly 8 defaults (5 expense + 3 income)
    default_categories = [cat for cat in all_categories if cat.is_default]
    assert len(default_categories) == 8
