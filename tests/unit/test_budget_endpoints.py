"""Unit tests for budget API endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from decimal import Decimal

from app.models.expense import Budget, Expense


@pytest.mark.asyncio
async def test_create_budget_success(test_client: AsyncClient):
    """Test successful budget creation with usage information."""
    budget_data = {
        "category": "Food",
        "amount_limit": "500.00",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }
    
    response = await test_client.post("/budgets", json=budget_data)
    
    assert response.status_code == 201
    data = response.json()
    assert data["category"] == "Food"
    assert data["amount_limit"] == "500.00"
    assert data["start_date"] == "2024-01-01"
    assert data["end_date"] == "2024-01-31"
    assert "id" in data
    assert "usage" in data
    assert data["usage"]["amount_spent"] == "0.00"
    assert data["usage"]["amount_limit"] == "500.00"
    assert Decimal(data["usage"]["percentage_used"]) == Decimal("0.00")
    assert data["usage"]["is_over_budget"] is False


@pytest.mark.asyncio
async def test_create_budget_with_expenses(test_client: AsyncClient, test_db: AsyncSession):
    """Test budget creation with existing expenses shows correct usage."""
    # Create expenses in Food category
    expenses = [
        Expense(
            date=date(2024, 1, 15),
            amount=Decimal("50.00"),
            category="Food",
            account="Cash"
        ),
        Expense(
            date=date(2024, 1, 20),
            amount=Decimal("75.00"),
            category="Food",
            account="Card"
        ),
    ]
    for exp in expenses:
        test_db.add(exp)
    await test_db.commit()
    
    # Create budget
    budget_data = {
        "category": "Food",
        "amount_limit": "500.00",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }
    
    response = await test_client.post("/budgets", json=budget_data)
    
    assert response.status_code == 201
    data = response.json()
    assert data["usage"]["amount_spent"] == "125.00"
    assert data["usage"]["percentage_used"] == "25.00"
    assert data["usage"]["is_over_budget"] is False


@pytest.mark.asyncio
async def test_create_budget_validation_error_missing_field(test_client: AsyncClient):
    """Test budget creation with missing required field."""
    budget_data = {
        "category": "Food",
        "amount_limit": "500.00",
        "start_date": "2024-01-01"
        # Missing 'end_date' field
    }
    
    response = await test_client.post("/budgets", json=budget_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_budget_validation_error_negative_amount(test_client: AsyncClient):
    """Test budget creation with negative amount limit."""
    budget_data = {
        "category": "Food",
        "amount_limit": "-500.00",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }
    
    response = await test_client.post("/budgets", json=budget_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_budget_validation_error_zero_amount(test_client: AsyncClient):
    """Test budget creation with zero amount limit."""
    budget_data = {
        "category": "Food",
        "amount_limit": "0.00",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }
    
    response = await test_client.post("/budgets", json=budget_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_budget_validation_error_end_before_start(test_client: AsyncClient):
    """Test budget creation with end_date before start_date."""
    budget_data = {
        "category": "Food",
        "amount_limit": "500.00",
        "start_date": "2024-01-31",
        "end_date": "2024-01-01"
    }
    
    response = await test_client.post("/budgets", json=budget_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_budget_overlap_error(test_client: AsyncClient, test_db: AsyncSession):
    """Test budget creation with overlapping period for same category."""
    # Create existing budget
    existing_budget = Budget(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    test_db.add(existing_budget)
    await test_db.commit()
    
    # Try to create overlapping budget
    budget_data = {
        "category": "Food",
        "amount_limit": "600.00",
        "start_date": "2024-01-15",
        "end_date": "2024-02-15"
    }
    
    response = await test_client.post("/budgets", json=budget_data)
    
    assert response.status_code == 400
    assert "overlapping" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_budget_no_overlap_different_category(test_client: AsyncClient, test_db: AsyncSession):
    """Test budget creation with same period but different category succeeds."""
    # Create existing budget for Food
    existing_budget = Budget(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    test_db.add(existing_budget)
    await test_db.commit()
    
    # Create budget for Travel (different category, same period)
    budget_data = {
        "category": "Travel",
        "amount_limit": "600.00",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }
    
    response = await test_client.post("/budgets", json=budget_data)
    
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_get_budget_success(test_client: AsyncClient, test_db: AsyncSession):
    """Test retrieving a budget by ID with usage information."""
    # Create budget
    budget = Budget(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    test_db.add(budget)
    await test_db.commit()
    await test_db.refresh(budget)
    
    # Get budget
    response = await test_client.get(f"/budgets/{budget.id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == budget.id
    assert data["category"] == "Food"
    assert data["amount_limit"] == "500.00"
    assert "usage" in data


@pytest.mark.asyncio
async def test_get_budget_not_found(test_client: AsyncClient):
    """Test retrieving non-existent budget."""
    response = await test_client.get("/budgets/999")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_budgets_empty(test_client: AsyncClient):
    """Test listing budgets when database is empty."""
    response = await test_client.get("/budgets")
    
    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_list_budgets_with_data(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing budgets with data."""
    # Create test budgets
    budgets = [
        Budget(
            category="Food",
            amount_limit=Decimal("500.00"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        ),
        Budget(
            category="Travel",
            amount_limit=Decimal("1000.00"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        ),
    ]
    for budget in budgets:
        test_db.add(budget)
    await test_db.commit()
    
    response = await test_client.get("/budgets")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Each budget should have usage information
    for budget in data:
        assert "usage" in budget


@pytest.mark.asyncio
async def test_list_budgets_with_category_filter(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing budgets filtered by category."""
    # Create test budgets
    budgets = [
        Budget(
            category="Food",
            amount_limit=Decimal("500.00"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        ),
        Budget(
            category="Travel",
            amount_limit=Decimal("1000.00"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        ),
    ]
    for budget in budgets:
        test_db.add(budget)
    await test_db.commit()
    
    # Filter by category
    response = await test_client.get("/budgets?category=Food")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["category"] == "Food"


@pytest.mark.asyncio
async def test_list_budgets_with_date_range_filter(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing budgets filtered by date range."""
    # Create test budgets
    budgets = [
        Budget(
            category="Food",
            amount_limit=Decimal("500.00"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        ),
        Budget(
            category="Travel",
            amount_limit=Decimal("1000.00"),
            start_date=date(2024, 2, 1),
            end_date=date(2024, 2, 28)
        ),
    ]
    for budget in budgets:
        test_db.add(budget)
    await test_db.commit()
    
    # Filter by date range (should return budgets active during this period)
    response = await test_client.get("/budgets?start_date=2024-01-15&end_date=2024-01-20")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["category"] == "Food"


@pytest.mark.asyncio
async def test_update_budget_success(test_client: AsyncClient, test_db: AsyncSession):
    """Test successful budget update with recalculated usage."""
    # Create budget
    budget = Budget(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    test_db.add(budget)
    await test_db.commit()
    await test_db.refresh(budget)
    
    # Update budget
    update_data = {
        "amount_limit": "750.00"
    }
    response = await test_client.put(f"/budgets/{budget.id}", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["amount_limit"] == "750.00"
    assert data["category"] == "Food"  # Unchanged
    assert data["usage"]["amount_limit"] == "750.00"


@pytest.mark.asyncio
async def test_update_budget_not_found(test_client: AsyncClient):
    """Test updating non-existent budget."""
    update_data = {"amount_limit": "750.00"}
    response = await test_client.put("/budgets/999", json=update_data)
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_budget_validation_error(test_client: AsyncClient, test_db: AsyncSession):
    """Test updating budget with invalid data."""
    # Create budget
    budget = Budget(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    test_db.add(budget)
    await test_db.commit()
    await test_db.refresh(budget)
    
    # Try to update with negative amount
    update_data = {"amount_limit": "-750.00"}
    response = await test_client.put(f"/budgets/{budget.id}", json=update_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_delete_budget_success(test_client: AsyncClient, test_db: AsyncSession):
    """Test successful budget deletion."""
    # Create budget
    budget = Budget(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    test_db.add(budget)
    await test_db.commit()
    await test_db.refresh(budget)
    
    # Delete budget
    response = await test_client.delete(f"/budgets/{budget.id}")
    
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_budget_not_found(test_client: AsyncClient):
    """Test deleting non-existent budget."""
    response = await test_client.delete("/budgets/999")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_budget_usage_calculation_with_expenses(test_client: AsyncClient, test_db: AsyncSession):
    """Test budget usage calculation includes expenses in category and period."""
    # Create budget
    budget = Budget(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    test_db.add(budget)
    
    # Create expenses - some in budget period, some outside
    expenses = [
        Expense(
            date=date(2024, 1, 15),
            amount=Decimal("100.00"),
            category="Food",
            account="Cash"
        ),
        Expense(
            date=date(2024, 1, 20),
            amount=Decimal("150.00"),
            category="Food",
            account="Card"
        ),
        Expense(
            date=date(2024, 2, 5),  # Outside budget period
            amount=Decimal("50.00"),
            category="Food",
            account="Cash"
        ),
        Expense(
            date=date(2024, 1, 10),
            amount=Decimal("75.00"),
            category="Travel",  # Different category
            account="Cash"
        ),
    ]
    for exp in expenses:
        test_db.add(exp)
    await test_db.commit()
    await test_db.refresh(budget)
    
    # Get budget
    response = await test_client.get(f"/budgets/{budget.id}")
    
    assert response.status_code == 200
    data = response.json()
    # Should only count Food expenses in January (100 + 150 = 250)
    assert data["usage"]["amount_spent"] == "250.00"
    assert Decimal(data["usage"]["percentage_used"]) == Decimal("50.00")
    assert data["usage"]["is_over_budget"] is False


@pytest.mark.asyncio
async def test_budget_over_budget_flag(test_client: AsyncClient, test_db: AsyncSession):
    """Test budget over-budget flag when expenses exceed limit."""
    # Create budget
    budget = Budget(
        category="Food",
        amount_limit=Decimal("100.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    test_db.add(budget)
    
    # Create expenses exceeding budget
    expenses = [
        Expense(
            date=date(2024, 1, 15),
            amount=Decimal("75.00"),
            category="Food",
            account="Cash"
        ),
        Expense(
            date=date(2024, 1, 20),
            amount=Decimal("50.00"),
            category="Food",
            account="Card"
        ),
    ]
    for exp in expenses:
        test_db.add(exp)
    await test_db.commit()
    await test_db.refresh(budget)
    
    # Get budget
    response = await test_client.get(f"/budgets/{budget.id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["usage"]["amount_spent"] == "125.00"
    assert data["usage"]["percentage_used"] == "125.00"
    assert data["usage"]["is_over_budget"] is True


@pytest.mark.asyncio
async def test_update_budget_partial_update(test_client: AsyncClient, test_db: AsyncSession):
    """Test partial budget update (only updating some fields)."""
    # Create budget
    budget = Budget(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    test_db.add(budget)
    await test_db.commit()
    await test_db.refresh(budget)
    
    # Update only category field
    update_data = {"category": "Travel"}
    response = await test_client.put(f"/budgets/{budget.id}", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Travel"
    # Other fields should remain unchanged
    assert data["amount_limit"] == "500.00"
    assert data["start_date"] == "2024-01-01"
    assert data["end_date"] == "2024-01-31"


@pytest.mark.asyncio
async def test_list_budgets_with_multiple_filters(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing budgets with category and date range filters."""
    # Create test budgets
    budgets = [
        Budget(
            category="Food",
            amount_limit=Decimal("500.00"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        ),
        Budget(
            category="Food",
            amount_limit=Decimal("600.00"),
            start_date=date(2024, 2, 1),
            end_date=date(2024, 2, 28)
        ),
        Budget(
            category="Travel",
            amount_limit=Decimal("1000.00"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        ),
    ]
    for budget in budgets:
        test_db.add(budget)
    await test_db.commit()
    
    # Filter by category AND date range
    response = await test_client.get("/budgets?category=Food&start_date=2024-01-15&end_date=2024-01-20")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["category"] == "Food"
    assert data[0]["start_date"] == "2024-01-01"


@pytest.mark.asyncio
async def test_budget_usage_with_no_expenses(test_client: AsyncClient, test_db: AsyncSession):
    """Test budget usage calculation when no expenses exist."""
    # Create budget
    budget = Budget(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    test_db.add(budget)
    await test_db.commit()
    await test_db.refresh(budget)
    
    # Get budget
    response = await test_client.get(f"/budgets/{budget.id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["usage"]["amount_spent"] == "0.00"
    assert Decimal(data["usage"]["percentage_used"]) == Decimal("0.00")
    assert data["usage"]["is_over_budget"] is False


@pytest.mark.asyncio
async def test_budget_usage_recalculation_after_expense_creation(test_client: AsyncClient, test_db: AsyncSession):
    """Test budget usage is recalculated when new expenses are created.
    
    Validates Requirement 15.4: Automatic recalculation on expense mutations.
    """
    # Create budget first
    budget = Budget(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    test_db.add(budget)
    await test_db.commit()
    await test_db.refresh(budget)
    
    # Verify initial usage is zero
    response = await test_client.get(f"/budgets/{budget.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["usage"]["amount_spent"] == "0.00"
    
    # Create expense via API
    expense_data = {
        "date": "2024-01-15",
        "amount": "100.00",
        "category": "Food",
        "account": "Cash",
        "notes": "Groceries"
    }
    expense_response = await test_client.post("/expenses", json=expense_data)
    assert expense_response.status_code == 201
    
    # Get budget again - usage should be recalculated
    response = await test_client.get(f"/budgets/{budget.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["usage"]["amount_spent"] == "100.00"
    assert Decimal(data["usage"]["percentage_used"]) == Decimal("20.00")
    assert data["usage"]["is_over_budget"] is False
    
    # Create another expense
    expense_data2 = {
        "date": "2024-01-20",
        "amount": "150.00",
        "category": "Food",
        "account": "Card",
        "notes": "Restaurant"
    }
    expense_response2 = await test_client.post("/expenses", json=expense_data2)
    assert expense_response2.status_code == 201
    
    # Get budget again - usage should reflect both expenses
    response = await test_client.get(f"/budgets/{budget.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["usage"]["amount_spent"] == "250.00"
    assert Decimal(data["usage"]["percentage_used"]) == Decimal("50.00")
    assert data["usage"]["is_over_budget"] is False


@pytest.mark.asyncio
async def test_budget_usage_recalculation_after_expense_deletion(test_client: AsyncClient, test_db: AsyncSession):
    """Test budget usage is recalculated when expenses are deleted.
    
    Validates Requirement 15.4: Automatic recalculation on expense mutations.
    """
    # Create budget
    budget = Budget(
        category="Food",
        amount_limit=Decimal("500.00"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
    test_db.add(budget)
    
    # Create expenses
    expense1 = Expense(
        date=date(2024, 1, 15),
        amount=Decimal("100.00"),
        category="Food",
        account="Cash"
    )
    expense2 = Expense(
        date=date(2024, 1, 20),
        amount=Decimal("150.00"),
        category="Food",
        account="Card"
    )
    test_db.add(expense1)
    test_db.add(expense2)
    await test_db.commit()
    await test_db.refresh(budget)
    await test_db.refresh(expense1)
    
    # Verify initial usage
    response = await test_client.get(f"/budgets/{budget.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["usage"]["amount_spent"] == "250.00"
    
    # Delete one expense via API
    delete_response = await test_client.delete(f"/expenses/{expense1.id}")
    assert delete_response.status_code == 204
    
    # Get budget again - usage should be recalculated
    response = await test_client.get(f"/budgets/{budget.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["usage"]["amount_spent"] == "150.00"
    assert Decimal(data["usage"]["percentage_used"]) == Decimal("30.00")
    assert data["usage"]["is_over_budget"] is False
