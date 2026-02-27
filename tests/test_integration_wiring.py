"""Integration tests for verifying all components are wired together correctly."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models import Category, AccountType, Expense, Income, Budget


@pytest.mark.asyncio
async def test_database_initialization_on_startup(test_db):
    """
    Test that database tables are created and defaults are initialized on startup.
    
    Validates: Requirements 10.1, 10.2
    """
    # Initialize defaults (simulating startup)
    from app.database import initialize_default_categories, initialize_default_account_types
    await initialize_default_categories(test_db)
    await initialize_default_account_types(test_db)
    
    # Verify categories table exists and has defaults
    result = await test_db.execute(select(Category))
    categories = result.scalars().all()
    assert len(categories) >= 8  # At least 5 expense + 3 income defaults
    
    # Verify account types table exists and has defaults
    result = await test_db.execute(select(AccountType))
    account_types = result.scalars().all()
    assert len(account_types) >= 3  # At least 3 defaults (Cash, Card, UPI)


@pytest.mark.asyncio
async def test_all_routers_registered(test_client):
    """
    Test that all API routers are registered and accessible.
    
    Validates: Requirements 10.1
    """
    # Test categories endpoint
    response = await test_client.get("/categories")
    assert response.status_code == 200
    
    # Test accounts endpoint
    response = await test_client.get("/accounts")
    assert response.status_code == 200
    
    # Test expenses endpoint
    response = await test_client.get("/expenses")
    assert response.status_code == 200
    
    # Test income endpoint
    response = await test_client.get("/income")
    assert response.status_code == 200
    
    # Test budgets endpoint
    response = await test_client.get("/budgets")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dependency_injection_works(test_client):
    """
    Test that dependency injection is working for all services.
    
    Creates an expense to verify ExpenseService, CacheService, and database
    are all properly injected and working together.
    
    Validates: Requirements 10.1
    """
    # Create an expense (tests ExpenseService with CacheService and DB)
    expense_data = {
        "date": "2024-01-15",
        "amount": "50.00",
        "category": "Food",
        "account": "Cash",
        "notes": "Test expense"
    }
    
    response = await test_client.post("/expenses", json=expense_data)
    assert response.status_code == 201
    created_expense = response.json()
    assert created_expense["amount"] == "50.00"
    
    # Retrieve the expense (tests caching)
    expense_id = created_expense["id"]
    response = await test_client.get(f"/expenses/{expense_id}")
    assert response.status_code == 200
    assert response.json()["id"] == expense_id


@pytest.mark.asyncio
async def test_cache_service_integration(test_client):
    """
    Test that cache service is properly integrated with expense operations.
    
    Validates: Requirements 7.1, 7.2, 7.3
    """
    # Create an expense
    expense_data = {
        "date": "2024-01-20",
        "amount": "100.00",
        "category": "Shopping",
        "account": "Card",
        "notes": "Cache test"
    }
    
    response = await test_client.post("/expenses", json=expense_data)
    assert response.status_code == 201
    expense_id = response.json()["id"]
    
    # First retrieval (should cache)
    response1 = await test_client.get(f"/expenses/{expense_id}")
    assert response1.status_code == 200
    
    # Second retrieval (should hit cache)
    response2 = await test_client.get(f"/expenses/{expense_id}")
    assert response2.status_code == 200
    assert response1.json() == response2.json()
    
    # Update expense (should invalidate cache)
    update_data = {"amount": "150.00"}
    response = await test_client.put(f"/expenses/{expense_id}", json=update_data)
    assert response.status_code == 200
    
    # Retrieve again (should get fresh data)
    response3 = await test_client.get(f"/expenses/{expense_id}")
    assert response3.status_code == 200
    assert response3.json()["amount"] == "150.00"


@pytest.mark.asyncio
async def test_error_handlers_registered(test_client):
    """
    Test that global error handlers are properly registered.
    
    Validates: Requirements 8.3
    """
    # Test validation error handler (422)
    invalid_expense = {
        "date": "2024-01-15",
        "amount": "-50.00",  # Invalid: negative amount
        "category": "Food",
        "account": "Cash"
    }
    
    response = await test_client.post("/expenses", json=invalid_expense)
    assert response.status_code == 422
    error_data = response.json()
    assert "detail" in error_data
    assert "error_code" in error_data
    assert error_data["error_code"] == "VALIDATION_ERROR"
    
    # Test 404 error handler
    response = await test_client.get("/expenses/999999")
    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_configuration_loaded(test_client):
    """
    Test that configuration is properly loaded from environment variables.
    
    Validates: Requirements 10.1, 10.2
    """
    # Test that the app is using configuration from settings
    response = await test_client.get("/")
    assert response.status_code == 200
    data = response.json()
    
    # Should have version from settings
    assert "version" in data
    assert data["version"] == "1.0.0"  # From .env file


@pytest.mark.asyncio
async def test_full_crud_workflow_with_all_services(test_client):
    """
    Test a complete CRUD workflow that exercises all major services.
    
    This test verifies:
    - CategoryService
    - AccountTypeService
    - ExpenseService
    - IncomeService
    - BudgetService
    - CacheService
    - Database integration
    
    Validates: Requirements 10.1
    """
    # 1. Create a custom category
    category_data = {"name": "Integration Test Category", "type": "expense"}
    response = await test_client.post("/categories", json=category_data)
    assert response.status_code == 201
    
    # 2. Create a custom account type
    account_data = {"name": "Integration Test Account"}
    response = await test_client.post("/accounts", json=account_data)
    assert response.status_code == 201
    
    # 3. Create an expense using the custom category and account
    expense_data = {
        "date": "2024-02-01",
        "amount": "200.00",
        "category": "Integration Test Category",
        "account": "Integration Test Account",
        "notes": "Full workflow test"
    }
    response = await test_client.post("/expenses", json=expense_data)
    assert response.status_code == 201
    expense_id = response.json()["id"]
    
    # 4. Create an income record
    income_data = {
        "date": "2024-02-01",
        "amount": "1000.00",
        "category": "Salary",
        "notes": "Monthly salary"
    }
    response = await test_client.post("/income", json=income_data)
    assert response.status_code == 201
    
    # 5. Create a budget for the category
    budget_data = {
        "category": "Integration Test Category",
        "amount_limit": "500.00",
        "start_date": "2024-02-01",
        "end_date": "2024-02-28"
    }
    response = await test_client.post("/budgets", json=budget_data)
    assert response.status_code == 201
    budget = response.json()
    
    # Budget should show usage from the expense we created
    assert budget["usage"]["amount_spent"] == "200.00"
    # Percentage may have varying decimal places
    assert float(budget["usage"]["percentage_used"]) == 40.0
    
    # 6. Update the expense
    update_data = {"amount": "250.00"}
    response = await test_client.put(f"/expenses/{expense_id}", json=update_data)
    assert response.status_code == 200
    
    # 7. Verify budget usage updated
    budget_id = budget["id"]
    response = await test_client.get(f"/budgets/{budget_id}")
    assert response.status_code == 200
    updated_budget = response.json()
    assert updated_budget["usage"]["amount_spent"] == "250.00"
    
    # 8. Delete the expense
    response = await test_client.delete(f"/expenses/{expense_id}")
    assert response.status_code == 204
    
    # 9. Verify expense is gone
    response = await test_client.get(f"/expenses/{expense_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_health_check_endpoint(test_client):
    """
    Test that the health check endpoint is working.
    
    Validates: Requirements 10.1
    """
    response = await test_client.get("/")
    assert response.status_code == 200
    data = response.json()
    
    assert "message" in data
    assert "version" in data
    assert "status" in data
    assert data["status"] == "healthy"
    assert "Expense Tracking API" in data["message"]
