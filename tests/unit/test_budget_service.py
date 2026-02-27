"""Unit tests for BudgetService."""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.budget_service import BudgetService
from app.schemas.budget import BudgetCreate, BudgetUpdate
from app.models.expense import Budget, Expense


@pytest.mark.asyncio
async def test_create_budget_success(db_session: AsyncSession):
    """Test creating a budget successfully."""
    service = BudgetService(db_session)
    
    budget_data = BudgetCreate(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    
    result = await service.create_budget(budget_data)
    
    assert result.id is not None
    assert result.category == "Food"
    assert result.amount_limit == Decimal("500.00")
    assert result.start_date == date(2024, 1, 1)
    assert result.end_date == date(2024, 1, 31)
    assert result.usage.amount_spent == Decimal("0.00")
    assert result.usage.percentage_used == Decimal("0.00")
    assert result.usage.is_over_budget is False


@pytest.mark.asyncio
async def test_create_budget_overlap_detection(db_session: AsyncSession):
    """Test that overlapping budgets are rejected."""
    service = BudgetService(db_session)
    
    # Create first budget
    budget_data1 = BudgetCreate(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    await service.create_budget(budget_data1)
    
    # Try to create overlapping budget
    budget_data2 = BudgetCreate(
        category="Food",
        amount_limit=Decimal("600.00"),
        start_date=date(2024, 1, 15),
        end_date=date(2024, 2, 15)
    )
    
    with pytest.raises(ValueError, match="already exists for overlapping period"):
        await service.create_budget(budget_data2)


@pytest.mark.asyncio
async def test_get_budget(db_session: AsyncSession):
    """Test retrieving a budget by ID."""
    service = BudgetService(db_session)
    
    # Create budget
    budget_data = BudgetCreate(
        category="Travel",
        amount_limit=Decimal("1000.00"),
        start_date=date(2024, 2, 1),
        end_date=date(2024, 2, 29)
    )
    created = await service.create_budget(budget_data)
    
    # Retrieve budget
    result = await service.get_budget(created.id)
    
    assert result is not None
    assert result.id == created.id
    assert result.category == "Travel"
    assert result.amount_limit == Decimal("1000.00")


@pytest.mark.asyncio
async def test_get_budget_not_found(db_session: AsyncSession):
    """Test retrieving a non-existent budget."""
    service = BudgetService(db_session)
    
    result = await service.get_budget(99999)
    
    assert result is None


@pytest.mark.asyncio
async def test_list_budgets_no_filter(db_session: AsyncSession):
    """Test listing all budgets without filters."""
    service = BudgetService(db_session)
    
    # Create multiple budgets
    await service.create_budget(BudgetCreate(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    ))
    await service.create_budget(BudgetCreate(
        category="Travel",
        amount_limit=Decimal("1000.00"),
        start_date=date(2024, 2, 1),
        end_date=date(2024, 2, 29)
    ))
    
    results = await service.list_budgets()
    
    assert len(results) == 2


@pytest.mark.asyncio
async def test_list_budgets_filter_by_category(db_session: AsyncSession):
    """Test listing budgets filtered by category."""
    service = BudgetService(db_session)
    
    # Create budgets
    await service.create_budget(BudgetCreate(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    ))
    await service.create_budget(BudgetCreate(
        category="Travel",
        amount_limit=Decimal("1000.00"),
        start_date=date(2024, 2, 1),
        end_date=date(2024, 2, 29)
    ))
    
    results = await service.list_budgets(category="Food")
    
    assert len(results) == 1
    assert results[0].category == "Food"


@pytest.mark.asyncio
async def test_update_budget(db_session: AsyncSession):
    """Test updating a budget."""
    service = BudgetService(db_session)
    
    # Create budget
    budget_data = BudgetCreate(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    created = await service.create_budget(budget_data)
    
    # Update budget
    updates = BudgetUpdate(amount_limit=Decimal("600.00"))
    result = await service.update_budget(created.id, updates)
    
    assert result.amount_limit == Decimal("600.00")
    assert result.category == "Food"


@pytest.mark.asyncio
async def test_update_budget_not_found(db_session: AsyncSession):
    """Test updating a non-existent budget."""
    service = BudgetService(db_session)
    
    updates = BudgetUpdate(amount_limit=Decimal("600.00"))
    
    with pytest.raises(ValueError, match="not found"):
        await service.update_budget(99999, updates)


@pytest.mark.asyncio
async def test_delete_budget(db_session: AsyncSession):
    """Test deleting a budget."""
    service = BudgetService(db_session)
    
    # Create budget
    budget_data = BudgetCreate(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    created = await service.create_budget(budget_data)
    
    # Delete budget
    result = await service.delete_budget(created.id)
    
    assert result is True
    
    # Verify it's deleted
    retrieved = await service.get_budget(created.id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_delete_budget_not_found(db_session: AsyncSession):
    """Test deleting a non-existent budget."""
    service = BudgetService(db_session)
    
    with pytest.raises(ValueError, match="not found"):
        await service.delete_budget(99999)


@pytest.mark.asyncio
async def test_calculate_usage_no_expenses(db_session: AsyncSession):
    """Test budget usage calculation with no expenses."""
    service = BudgetService(db_session)
    
    budget_data = BudgetCreate(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    result = await service.create_budget(budget_data)
    
    assert result.usage.amount_spent == Decimal("0.00")
    assert result.usage.percentage_used == Decimal("0.00")
    assert result.usage.is_over_budget is False


@pytest.mark.asyncio
async def test_calculate_usage_with_expenses(db_session: AsyncSession):
    """Test budget usage calculation with expenses."""
    service = BudgetService(db_session)
    
    # Create budget
    budget_data = BudgetCreate(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    created = await service.create_budget(budget_data)
    
    # Add expenses
    expense1 = Expense(
        date=date(2024, 1, 10),
        amount=Decimal("150.00"),
        category="Food",
        account="Cash",
        notes="Groceries"
    )
    expense2 = Expense(
        date=date(2024, 1, 20),
        amount=Decimal("100.00"),
        category="Food",
        account="Card",
        notes="Restaurant"
    )
    db_session.add(expense1)
    db_session.add(expense2)
    await db_session.commit()
    
    # Retrieve budget with updated usage
    result = await service.get_budget(created.id)
    
    assert result.usage.amount_spent == Decimal("250.00")
    assert result.usage.percentage_used == Decimal("50.00")
    assert result.usage.is_over_budget is False


@pytest.mark.asyncio
async def test_calculate_usage_over_budget(db_session: AsyncSession):
    """Test budget usage calculation when over budget."""
    service = BudgetService(db_session)
    
    # Create budget
    budget_data = BudgetCreate(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    created = await service.create_budget(budget_data)
    
    # Add expenses that exceed budget
    expense = Expense(
        date=date(2024, 1, 10),
        amount=Decimal("600.00"),
        category="Food",
        account="Cash",
        notes="Big purchase"
    )
    db_session.add(expense)
    await db_session.commit()
    
    # Retrieve budget with updated usage
    result = await service.get_budget(created.id)
    
    assert result.usage.amount_spent == Decimal("600.00")
    assert result.usage.percentage_used == Decimal("120.00")
    assert result.usage.is_over_budget is True
