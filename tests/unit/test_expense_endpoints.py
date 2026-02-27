"""Unit tests for expense API endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from decimal import Decimal

from app.models.expense import Expense


@pytest.mark.asyncio
async def test_create_expense_success(test_client: AsyncClient):
    """Test successful expense creation."""
    expense_data = {
        "date": "2024-01-15",
        "amount": "50.00",
        "category": "Food",
        "account": "Cash",
        "notes": "Lunch"
    }
    
    response = await test_client.post("/expenses", json=expense_data)
    
    assert response.status_code == 201
    data = response.json()
    assert data["date"] == "2024-01-15"
    assert data["amount"] == "50.00"
    assert data["category"] == "Food"
    assert data["account"] == "Cash"
    assert data["notes"] == "Lunch"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_expense_validation_error_missing_field(test_client: AsyncClient):
    """Test expense creation with missing required field."""
    expense_data = {
        "date": "2024-01-15",
        "amount": "50.00",
        "category": "Food"
        # Missing 'account' field
    }
    
    response = await test_client.post("/expenses", json=expense_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_expense_validation_error_negative_amount(test_client: AsyncClient):
    """Test expense creation with negative amount."""
    expense_data = {
        "date": "2024-01-15",
        "amount": "-50.00",
        "category": "Food",
        "account": "Cash"
    }
    
    response = await test_client.post("/expenses", json=expense_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_get_expense_success(test_client: AsyncClient, test_db: AsyncSession):
    """Test retrieving an expense by ID."""
    # Create expense
    expense = Expense(
        date=date(2024, 1, 15),
        amount=Decimal("50.00"),
        category="Food",
        account="Cash",
        notes="Lunch"
    )
    test_db.add(expense)
    await test_db.commit()
    await test_db.refresh(expense)
    
    # Get expense
    response = await test_client.get(f"/expenses/{expense.id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == expense.id
    assert data["date"] == "2024-01-15"
    assert data["amount"] == "50.00"
    assert data["category"] == "Food"


@pytest.mark.asyncio
async def test_get_expense_not_found(test_client: AsyncClient):
    """Test retrieving non-existent expense."""
    response = await test_client.get("/expenses/999")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_expenses_empty(test_client: AsyncClient):
    """Test listing expenses when database is empty."""
    response = await test_client.get("/expenses")
    
    assert response.status_code == 200
    data = response.json()
    assert data["expenses"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 50


@pytest.mark.asyncio
async def test_list_expenses_with_data(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing expenses with data."""
    # Create test expenses
    expenses = [
        Expense(
            date=date(2024, 1, 15),
            amount=Decimal("50.00"),
            category="Food",
            account="Cash",
            notes="Lunch"
        ),
        Expense(
            date=date(2024, 1, 16),
            amount=Decimal("100.00"),
            category="Travel",
            account="Card",
            notes="Taxi"
        ),
    ]
    for exp in expenses:
        test_db.add(exp)
    await test_db.commit()
    
    response = await test_client.get("/expenses")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["expenses"]) == 2
    assert data["total"] == 2
    # Check ordering by date descending (most recent first)
    assert data["expenses"][0]["date"] == "2024-01-16"
    assert data["expenses"][1]["date"] == "2024-01-15"


@pytest.mark.asyncio
async def test_list_expenses_with_date_filter(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing expenses with date range filter."""
    # Create test expenses
    expenses = [
        Expense(
            date=date(2024, 1, 10),
            amount=Decimal("50.00"),
            category="Food",
            account="Cash"
        ),
        Expense(
            date=date(2024, 1, 15),
            amount=Decimal("100.00"),
            category="Travel",
            account="Card"
        ),
        Expense(
            date=date(2024, 1, 20),
            amount=Decimal("75.00"),
            category="Food",
            account="Cash"
        ),
    ]
    for exp in expenses:
        test_db.add(exp)
    await test_db.commit()
    
    # Filter by date range
    response = await test_client.get("/expenses?start_date=2024-01-12&end_date=2024-01-18")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["expenses"]) == 1
    assert data["expenses"][0]["date"] == "2024-01-15"


@pytest.mark.asyncio
async def test_list_expenses_with_category_filter(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing expenses with category filter."""
    # Create test expenses
    expenses = [
        Expense(
            date=date(2024, 1, 15),
            amount=Decimal("50.00"),
            category="Food",
            account="Cash"
        ),
        Expense(
            date=date(2024, 1, 16),
            amount=Decimal("100.00"),
            category="Travel",
            account="Card"
        ),
    ]
    for exp in expenses:
        test_db.add(exp)
    await test_db.commit()
    
    # Filter by category
    response = await test_client.get("/expenses?categories=Food")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["expenses"]) == 1
    assert data["expenses"][0]["category"] == "Food"


@pytest.mark.asyncio
async def test_list_expenses_with_pagination(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing expenses with pagination."""
    # Create 5 test expenses
    for i in range(5):
        expense = Expense(
            date=date(2024, 1, i + 1),
            amount=Decimal("50.00"),
            category="Food",
            account="Cash"
        )
        test_db.add(expense)
    await test_db.commit()
    
    # Get first page with page_size=2
    response = await test_client.get("/expenses?page=1&page_size=2")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["expenses"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2


@pytest.mark.asyncio
async def test_update_expense_success(test_client: AsyncClient, test_db: AsyncSession):
    """Test successful expense update."""
    # Create expense
    expense = Expense(
        date=date(2024, 1, 15),
        amount=Decimal("50.00"),
        category="Food",
        account="Cash",
        notes="Lunch"
    )
    test_db.add(expense)
    await test_db.commit()
    await test_db.refresh(expense)
    
    # Update expense
    update_data = {
        "amount": "75.00",
        "notes": "Dinner"
    }
    response = await test_client.put(f"/expenses/{expense.id}", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == "75.00"
    assert data["notes"] == "Dinner"
    assert data["category"] == "Food"  # Unchanged


@pytest.mark.asyncio
async def test_update_expense_not_found(test_client: AsyncClient):
    """Test updating non-existent expense."""
    update_data = {"amount": "75.00"}
    response = await test_client.put("/expenses/999", json=update_data)
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_expense_validation_error(test_client: AsyncClient, test_db: AsyncSession):
    """Test updating expense with invalid data."""
    # Create expense
    expense = Expense(
        date=date(2024, 1, 15),
        amount=Decimal("50.00"),
        category="Food",
        account="Cash"
    )
    test_db.add(expense)
    await test_db.commit()
    await test_db.refresh(expense)
    
    # Try to update with negative amount
    update_data = {"amount": "-75.00"}
    response = await test_client.put(f"/expenses/{expense.id}", json=update_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_delete_expense_success(test_client: AsyncClient, test_db: AsyncSession):
    """Test successful expense deletion."""
    # Create expense
    expense = Expense(
        date=date(2024, 1, 15),
        amount=Decimal("50.00"),
        category="Food",
        account="Cash"
    )
    test_db.add(expense)
    await test_db.commit()
    await test_db.refresh(expense)
    
    # Delete expense
    response = await test_client.delete(f"/expenses/{expense.id}")
    
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_expense_not_found(test_client: AsyncClient):
    """Test deleting non-existent expense."""
    response = await test_client.delete("/expenses/999")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_expenses_with_amount_range_filter(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing expenses with amount range filter."""
    # Create test expenses
    expenses = [
        Expense(
            date=date(2024, 1, 15),
            amount=Decimal("25.00"),
            category="Food",
            account="Cash"
        ),
        Expense(
            date=date(2024, 1, 16),
            amount=Decimal("50.00"),
            category="Travel",
            account="Card"
        ),
        Expense(
            date=date(2024, 1, 17),
            amount=Decimal("100.00"),
            category="Food",
            account="Cash"
        ),
    ]
    for exp in expenses:
        test_db.add(exp)
    await test_db.commit()
    
    # Filter by amount range
    response = await test_client.get("/expenses?min_amount=40&max_amount=80")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["expenses"]) == 1
    assert data["expenses"][0]["amount"] == "50.00"


@pytest.mark.asyncio
async def test_list_expenses_with_account_filter(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing expenses with account filter."""
    # Create test expenses
    expenses = [
        Expense(
            date=date(2024, 1, 15),
            amount=Decimal("50.00"),
            category="Food",
            account="Cash"
        ),
        Expense(
            date=date(2024, 1, 16),
            amount=Decimal("100.00"),
            category="Travel",
            account="Card"
        ),
    ]
    for exp in expenses:
        test_db.add(exp)
    await test_db.commit()
    
    # Filter by account - use query string format for list parameters
    response = await test_client.get("/expenses?accounts=Card")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["expenses"]) == 1
    assert data["expenses"][0]["account"] == "Card"


@pytest.mark.asyncio
async def test_list_expenses_with_multiple_filters(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing expenses with multiple filters (AND logic)."""
    # Create test expenses
    expenses = [
        Expense(
            date=date(2024, 1, 15),
            amount=Decimal("50.00"),
            category="Food",
            account="Cash"
        ),
        Expense(
            date=date(2024, 1, 16),
            amount=Decimal("100.00"),
            category="Food",
            account="Card"
        ),
        Expense(
            date=date(2024, 1, 17),
            amount=Decimal("75.00"),
            category="Travel",
            account="Cash"
        ),
    ]
    for exp in expenses:
        test_db.add(exp)
    await test_db.commit()
    
    # Filter by category AND account - use query string format for list parameters
    response = await test_client.get("/expenses?categories=Food&accounts=Cash")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["expenses"]) == 1
    assert data["expenses"][0]["category"] == "Food"
    assert data["expenses"][0]["account"] == "Cash"



@pytest.mark.asyncio
async def test_list_expenses_with_multiple_categories(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing expenses with multiple category filters (OR logic)."""
    # Create test expenses
    expenses = [
        Expense(
            date=date(2024, 1, 15),
            amount=Decimal("50.00"),
            category="Food",
            account="Cash"
        ),
        Expense(
            date=date(2024, 1, 16),
            amount=Decimal("100.00"),
            category="Travel",
            account="Card"
        ),
        Expense(
            date=date(2024, 1, 17),
            amount=Decimal("75.00"),
            category="Shopping",
            account="Cash"
        ),
    ]
    for exp in expenses:
        test_db.add(exp)
    await test_db.commit()
    
    # Filter by multiple categories (OR logic)
    response = await test_client.get("/expenses?categories=Food&categories=Travel")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["expenses"]) == 2
    categories = {exp["category"] for exp in data["expenses"]}
    assert categories == {"Food", "Travel"}


@pytest.mark.asyncio
async def test_create_expense_with_invalid_date_format(test_client: AsyncClient):
    """Test expense creation with invalid date format."""
    expense_data = {
        "date": "invalid-date",
        "amount": "50.00",
        "category": "Food",
        "account": "Cash"
    }
    
    response = await test_client.post("/expenses", json=expense_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_list_expenses_with_invalid_date_range(test_client: AsyncClient):
    """Test listing expenses with end_date before start_date."""
    # This should trigger validation error
    response = await test_client.get("/expenses?start_date=2024-01-20&end_date=2024-01-10")
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_update_expense_partial_update(test_client: AsyncClient, test_db: AsyncSession):
    """Test partial expense update (only updating some fields)."""
    # Create expense
    expense = Expense(
        date=date(2024, 1, 15),
        amount=Decimal("50.00"),
        category="Food",
        account="Cash",
        notes="Original note"
    )
    test_db.add(expense)
    await test_db.commit()
    await test_db.refresh(expense)
    
    # Update only notes field
    update_data = {"notes": "Updated note"}
    response = await test_client.put(f"/expenses/{expense.id}", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["notes"] == "Updated note"
    # Other fields should remain unchanged
    assert data["amount"] == "50.00"
    assert data["category"] == "Food"
    assert data["account"] == "Cash"


@pytest.mark.asyncio
async def test_list_expenses_pagination_second_page(test_client: AsyncClient, test_db: AsyncSession):
    """Test retrieving second page of expenses."""
    # Create 5 test expenses
    for i in range(5):
        expense = Expense(
            date=date(2024, 1, i + 1),
            amount=Decimal("50.00"),
            category="Food",
            account="Cash"
        )
        test_db.add(expense)
    await test_db.commit()
    
    # Get second page with page_size=2
    response = await test_client.get("/expenses?page=2&page_size=2")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["expenses"]) == 2
    assert data["total"] == 5
    assert data["page"] == 2
    assert data["page_size"] == 2


@pytest.mark.asyncio
async def test_create_expense_with_zero_amount(test_client: AsyncClient):
    """Test expense creation with zero amount (should fail)."""
    expense_data = {
        "date": "2024-01-15",
        "amount": "0.00",
        "category": "Food",
        "account": "Cash"
    }
    
    response = await test_client.post("/expenses", json=expense_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_list_expenses_with_boundary_amount_filter(test_client: AsyncClient, test_db: AsyncSession):
    """Test amount range filter with boundary values (inclusive)."""
    # Create test expenses
    expenses = [
        Expense(
            date=date(2024, 1, 15),
            amount=Decimal("50.00"),
            category="Food",
            account="Cash"
        ),
        Expense(
            date=date(2024, 1, 16),
            amount=Decimal("100.00"),
            category="Travel",
            account="Card"
        ),
        Expense(
            date=date(2024, 1, 17),
            amount=Decimal("150.00"),
            category="Food",
            account="Cash"
        ),
    ]
    for exp in expenses:
        test_db.add(exp)
    await test_db.commit()
    
    # Filter with boundary values (should include 50 and 100)
    response = await test_client.get("/expenses?min_amount=50&max_amount=100")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["expenses"]) == 2
    amounts = {Decimal(exp["amount"]) for exp in data["expenses"]}
    assert amounts == {Decimal("50.00"), Decimal("100.00")}
