"""Integration test for application startup initialization."""
import pytest
from sqlalchemy import select
from app.models import Category, AccountType, CategoryTypeEnum
from app.database import initialize_default_categories, initialize_default_account_types


@pytest.mark.asyncio
async def test_startup_initializes_defaults(test_db):
    """Test that initialization functions work correctly when called during startup."""
    # Manually call initialization functions (simulating what happens in lifespan)
    await initialize_default_categories(test_db)
    await initialize_default_account_types(test_db)
    
    # Verify categories were initialized
    result = await test_db.execute(select(Category))
    categories = result.scalars().all()
    
    # Should have 8 categories (5 expense + 3 income)
    assert len(categories) == 8
    
    category_names = {cat.name for cat in categories}
    
    # Verify expense categories
    assert "Food" in category_names
    assert "Travel" in category_names
    assert "Groceries" in category_names
    assert "Shopping" in category_names
    assert "Other" in category_names
    
    # Verify income categories
    assert "Salary" in category_names
    assert "Cash" in category_names
    assert "Other Income" in category_names
    
    # Verify account types were initialized
    result = await test_db.execute(select(AccountType))
    account_types = result.scalars().all()
    
    # Should have 3 account types
    assert len(account_types) == 3
    
    account_names = {acc.name for acc in account_types}
    assert "Cash" in account_names
    assert "Card" in account_names
    assert "UPI" in account_names


@pytest.mark.asyncio
async def test_api_responds_after_initialization(test_client):
    """Test that the API responds correctly after initialization."""
    # Make a simple request to verify the app is working
    response = await test_client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "status" in data
    assert data["status"] == "healthy"
