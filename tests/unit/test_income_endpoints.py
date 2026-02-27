"""Unit tests for income API endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from decimal import Decimal

from app.models.expense import Income


@pytest.mark.asyncio
async def test_create_income_success(test_client: AsyncClient):
    """Test successful income creation."""
    income_data = {
        "date": "2024-01-15",
        "amount": "5000.00",
        "category": "Salary",
        "notes": "Monthly salary"
    }
    
    response = await test_client.post("/income", json=income_data)
    
    assert response.status_code == 201
    data = response.json()
    assert data["date"] == "2024-01-15"
    assert data["amount"] == "5000.00"
    assert data["category"] == "Salary"
    assert data["notes"] == "Monthly salary"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_income_validation_error_missing_field(test_client: AsyncClient):
    """Test income creation with missing required field."""
    income_data = {
        "date": "2024-01-15",
        "amount": "5000.00"
        # Missing 'category' field
    }
    
    response = await test_client.post("/income", json=income_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_income_validation_error_negative_amount(test_client: AsyncClient):
    """Test income creation with negative amount."""
    income_data = {
        "date": "2024-01-15",
        "amount": "-5000.00",
        "category": "Salary"
    }
    
    response = await test_client.post("/income", json=income_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_get_income_success(test_client: AsyncClient, test_db: AsyncSession):
    """Test retrieving an income by ID."""
    # Create income
    income = Income(
        date=date(2024, 1, 15),
        amount=Decimal("5000.00"),
        category="Salary",
        notes="Monthly salary"
    )
    test_db.add(income)
    await test_db.commit()
    await test_db.refresh(income)
    
    # Get income
    response = await test_client.get(f"/income/{income.id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == income.id
    assert data["date"] == "2024-01-15"
    assert data["amount"] == "5000.00"
    assert data["category"] == "Salary"


@pytest.mark.asyncio
async def test_get_income_not_found(test_client: AsyncClient):
    """Test retrieving non-existent income."""
    response = await test_client.get("/income/999")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_income_empty(test_client: AsyncClient):
    """Test listing income when database is empty."""
    response = await test_client.get("/income")
    
    assert response.status_code == 200
    data = response.json()
    assert data["income"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 50


@pytest.mark.asyncio
async def test_list_income_with_data(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing income with data."""
    # Create test income records
    income_records = [
        Income(
            date=date(2024, 1, 15),
            amount=Decimal("5000.00"),
            category="Salary",
            notes="Monthly salary"
        ),
        Income(
            date=date(2024, 1, 20),
            amount=Decimal("500.00"),
            category="Cash",
            notes="Bonus"
        ),
    ]
    for inc in income_records:
        test_db.add(inc)
    await test_db.commit()
    
    response = await test_client.get("/income")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["income"]) == 2
    assert data["total"] == 2
    # Check ordering by date descending (most recent first)
    assert data["income"][0]["date"] == "2024-01-20"
    assert data["income"][1]["date"] == "2024-01-15"


@pytest.mark.asyncio
async def test_list_income_with_date_filter(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing income with date range filter."""
    # Create test income records
    income_records = [
        Income(
            date=date(2024, 1, 10),
            amount=Decimal("1000.00"),
            category="Cash",
        ),
        Income(
            date=date(2024, 1, 15),
            amount=Decimal("5000.00"),
            category="Salary",
        ),
        Income(
            date=date(2024, 1, 20),
            amount=Decimal("500.00"),
            category="Cash",
        ),
    ]
    for inc in income_records:
        test_db.add(inc)
    await test_db.commit()
    
    # Filter by date range
    response = await test_client.get("/income?start_date=2024-01-12&end_date=2024-01-18")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["income"]) == 1
    assert data["income"][0]["date"] == "2024-01-15"


@pytest.mark.asyncio
async def test_list_income_with_category_filter(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing income with category filter."""
    # Create test income records
    income_records = [
        Income(
            date=date(2024, 1, 15),
            amount=Decimal("5000.00"),
            category="Salary",
        ),
        Income(
            date=date(2024, 1, 16),
            amount=Decimal("500.00"),
            category="Cash",
        ),
    ]
    for inc in income_records:
        test_db.add(inc)
    await test_db.commit()
    
    # Filter by category
    response = await test_client.get("/income?categories=Salary")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["income"]) == 1
    assert data["income"][0]["category"] == "Salary"


@pytest.mark.asyncio
async def test_list_income_with_pagination(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing income with pagination."""
    # Create 5 test income records
    for i in range(5):
        income = Income(
            date=date(2024, 1, i + 1),
            amount=Decimal("1000.00"),
            category="Cash",
        )
        test_db.add(income)
    await test_db.commit()
    
    # Get first page with page_size=2
    response = await test_client.get("/income?page=1&page_size=2")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["income"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2


@pytest.mark.asyncio
async def test_update_income_success(test_client: AsyncClient, test_db: AsyncSession):
    """Test successful income update."""
    # Create income
    income = Income(
        date=date(2024, 1, 15),
        amount=Decimal("5000.00"),
        category="Salary",
        notes="Monthly salary"
    )
    test_db.add(income)
    await test_db.commit()
    await test_db.refresh(income)
    
    # Update income
    update_data = {
        "amount": "5500.00",
        "notes": "Salary with bonus"
    }
    response = await test_client.put(f"/income/{income.id}", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == "5500.00"
    assert data["notes"] == "Salary with bonus"
    assert data["category"] == "Salary"  # Unchanged


@pytest.mark.asyncio
async def test_update_income_not_found(test_client: AsyncClient):
    """Test updating non-existent income."""
    update_data = {"amount": "5500.00"}
    response = await test_client.put("/income/999", json=update_data)
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_income_validation_error(test_client: AsyncClient, test_db: AsyncSession):
    """Test updating income with invalid data."""
    # Create income
    income = Income(
        date=date(2024, 1, 15),
        amount=Decimal("5000.00"),
        category="Salary",
    )
    test_db.add(income)
    await test_db.commit()
    await test_db.refresh(income)
    
    # Try to update with negative amount
    update_data = {"amount": "-5500.00"}
    response = await test_client.put(f"/income/{income.id}", json=update_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_delete_income_success(test_client: AsyncClient, test_db: AsyncSession):
    """Test successful income deletion."""
    # Create income
    income = Income(
        date=date(2024, 1, 15),
        amount=Decimal("5000.00"),
        category="Salary",
    )
    test_db.add(income)
    await test_db.commit()
    await test_db.refresh(income)
    
    # Delete income
    response = await test_client.delete(f"/income/{income.id}")
    
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_income_not_found(test_client: AsyncClient):
    """Test deleting non-existent income."""
    response = await test_client.delete("/income/999")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_income_with_amount_range_filter(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing income with amount range filter."""
    # Create test income records
    income_records = [
        Income(
            date=date(2024, 1, 15),
            amount=Decimal("1000.00"),
            category="Cash",
        ),
        Income(
            date=date(2024, 1, 16),
            amount=Decimal("5000.00"),
            category="Salary",
        ),
        Income(
            date=date(2024, 1, 17),
            amount=Decimal("10000.00"),
            category="Salary",
        ),
    ]
    for inc in income_records:
        test_db.add(inc)
    await test_db.commit()
    
    # Filter by amount range
    response = await test_client.get("/income?min_amount=2000&max_amount=8000")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["income"]) == 1
    assert data["income"][0]["amount"] == "5000.00"


@pytest.mark.asyncio
async def test_list_income_with_multiple_categories(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing income with multiple category filters (OR logic)."""
    # Create test income records
    income_records = [
        Income(
            date=date(2024, 1, 15),
            amount=Decimal("5000.00"),
            category="Salary",
        ),
        Income(
            date=date(2024, 1, 16),
            amount=Decimal("500.00"),
            category="Cash",
        ),
        Income(
            date=date(2024, 1, 17),
            amount=Decimal("1000.00"),
            category="Other",
        ),
    ]
    for inc in income_records:
        test_db.add(inc)
    await test_db.commit()
    
    # Filter by multiple categories (OR logic)
    response = await test_client.get("/income?categories=Salary&categories=Cash")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["income"]) == 2
    categories = {inc["category"] for inc in data["income"]}
    assert categories == {"Salary", "Cash"}


@pytest.mark.asyncio
async def test_create_income_with_invalid_date_format(test_client: AsyncClient):
    """Test income creation with invalid date format."""
    income_data = {
        "date": "invalid-date",
        "amount": "5000.00",
        "category": "Salary",
    }
    
    response = await test_client.post("/income", json=income_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_list_income_with_invalid_date_range(test_client: AsyncClient):
    """Test listing income with end_date before start_date."""
    # This should trigger validation error
    response = await test_client.get("/income?start_date=2024-01-20&end_date=2024-01-10")
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_update_income_partial_update(test_client: AsyncClient, test_db: AsyncSession):
    """Test partial income update (only updating some fields)."""
    # Create income
    income = Income(
        date=date(2024, 1, 15),
        amount=Decimal("5000.00"),
        category="Salary",
        notes="Original note"
    )
    test_db.add(income)
    await test_db.commit()
    await test_db.refresh(income)
    
    # Update only notes field
    update_data = {"notes": "Updated note"}
    response = await test_client.put(f"/income/{income.id}", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["notes"] == "Updated note"
    # Other fields should remain unchanged
    assert data["amount"] == "5000.00"
    assert data["category"] == "Salary"


@pytest.mark.asyncio
async def test_list_income_pagination_second_page(test_client: AsyncClient, test_db: AsyncSession):
    """Test retrieving second page of income."""
    # Create 5 test income records
    for i in range(5):
        income = Income(
            date=date(2024, 1, i + 1),
            amount=Decimal("1000.00"),
            category="Cash",
        )
        test_db.add(income)
    await test_db.commit()
    
    # Get second page with page_size=2
    response = await test_client.get("/income?page=2&page_size=2")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["income"]) == 2
    assert data["total"] == 5
    assert data["page"] == 2
    assert data["page_size"] == 2


@pytest.mark.asyncio
async def test_create_income_with_zero_amount(test_client: AsyncClient):
    """Test income creation with zero amount (should fail)."""
    income_data = {
        "date": "2024-01-15",
        "amount": "0.00",
        "category": "Salary",
    }
    
    response = await test_client.post("/income", json=income_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_list_income_with_boundary_amount_filter(test_client: AsyncClient, test_db: AsyncSession):
    """Test amount range filter with boundary values (inclusive)."""
    # Create test income records
    income_records = [
        Income(
            date=date(2024, 1, 15),
            amount=Decimal("1000.00"),
            category="Cash",
        ),
        Income(
            date=date(2024, 1, 16),
            amount=Decimal("5000.00"),
            category="Salary",
        ),
        Income(
            date=date(2024, 1, 17),
            amount=Decimal("10000.00"),
            category="Salary",
        ),
    ]
    for inc in income_records:
        test_db.add(inc)
    await test_db.commit()
    
    # Filter with boundary values (should include 1000 and 5000)
    response = await test_client.get("/income?min_amount=1000&max_amount=5000")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["income"]) == 2
    amounts = {Decimal(inc["amount"]) for inc in data["income"]}
    assert amounts == {Decimal("1000.00"), Decimal("5000.00")}


@pytest.mark.asyncio
async def test_create_income_without_notes(test_client: AsyncClient):
    """Test income creation without optional notes field."""
    income_data = {
        "date": "2024-01-15",
        "amount": "5000.00",
        "category": "Salary"
    }
    
    response = await test_client.post("/income", json=income_data)
    
    assert response.status_code == 201
    data = response.json()
    assert data["notes"] is None


@pytest.mark.asyncio
async def test_list_income_with_multiple_filters(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing income with multiple filters (AND logic)."""
    # Create test income records
    income_records = [
        Income(
            date=date(2024, 1, 15),
            amount=Decimal("5000.00"),
            category="Salary",
        ),
        Income(
            date=date(2024, 1, 16),
            amount=Decimal("500.00"),
            category="Salary",
        ),
        Income(
            date=date(2024, 1, 17),
            amount=Decimal("5000.00"),
            category="Cash",
        ),
    ]
    for inc in income_records:
        test_db.add(inc)
    await test_db.commit()
    
    # Filter by category AND amount range
    response = await test_client.get("/income?categories=Salary&min_amount=1000")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["income"]) == 1
    assert data["income"][0]["category"] == "Salary"
    assert Decimal(data["income"][0]["amount"]) >= Decimal("1000.00")
