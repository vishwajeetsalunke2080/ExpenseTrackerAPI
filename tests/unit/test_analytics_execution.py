"""Unit tests for AnalyticsEngine _execute_analytics method."""
import pytest
from unittest.mock import AsyncMock
from datetime import date
from decimal import Decimal
from app.services.analytics_engine import AnalyticsEngine
from app.schemas.expense import ExpenseResponse
from app.schemas.income import IncomeResponse


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    return AsyncMock()


@pytest.fixture
def mock_expense_service():
    """Create a mock ExpenseService."""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_income_service():
    """Create a mock IncomeService."""
    service = AsyncMock()
    return service


@pytest.fixture
def analytics_engine(mock_openai_client, mock_expense_service, mock_income_service):
    """Create an AnalyticsEngine instance with mocked dependencies."""
    return AnalyticsEngine(mock_openai_client, mock_expense_service, mock_income_service)


@pytest.mark.asyncio
async def test_execute_analytics_by_category(analytics_engine, mock_expense_service, mock_income_service):
    """Test category-based aggregation."""
    # Arrange
    parsed_query = {
        "time_period": {"start_date": "2024-11-01", "end_date": "2024-11-30"},
        "aggregation": "by_category"
    }
    
    # Mock expense data
    expenses = [
        ExpenseResponse(
            id=1, date=date(2024, 11, 5), amount=Decimal("100.00"),
            category="Food", account="Card", notes="",
            created_at=date(2024, 11, 5), updated_at=date(2024, 11, 5)
        ),
        ExpenseResponse(
            id=2, date=date(2024, 11, 10), amount=Decimal("50.00"),
            category="Food", account="Cash", notes="",
            created_at=date(2024, 11, 10), updated_at=date(2024, 11, 10)
        ),
        ExpenseResponse(
            id=3, date=date(2024, 11, 15), amount=Decimal("200.00"),
            category="Travel", account="Card", notes="",
            created_at=date(2024, 11, 15), updated_at=date(2024, 11, 15)
        )
    ]
    
    # Mock income data
    income_records = [
        IncomeResponse(
            id=1, date=date(2024, 11, 1), amount=Decimal("5000.00"),
            category="Salary", notes="",
            created_at=date(2024, 11, 1), updated_at=date(2024, 11, 1)
        )
    ]
    
    mock_expense_service.list_expenses.return_value = (expenses, len(expenses))
    mock_income_service.list_income.return_value = (income_records, len(income_records))
    
    # Act
    result = await analytics_engine._execute_analytics(parsed_query)
    
    # Assert
    assert result['aggregation_type'] == 'by_category'
    assert result['expenses']['Food'] == 150.0  # 100 + 50
    assert result['expenses']['Travel'] == 200.0
    assert result['income']['Salary'] == 5000.0
    assert result['total_expenses'] == 350.0
    assert result['total_income'] == 5000.0


@pytest.mark.asyncio
async def test_execute_analytics_by_account(analytics_engine, mock_expense_service, mock_income_service):
    """Test account-based aggregation."""
    # Arrange
    parsed_query = {
        "aggregation": "by_account"
    }
    
    # Mock expense data
    expenses = [
        ExpenseResponse(
            id=1, date=date(2024, 11, 5), amount=Decimal("100.00"),
            category="Food", account="Card", notes="",
            created_at=date(2024, 11, 5), updated_at=date(2024, 11, 5)
        ),
        ExpenseResponse(
            id=2, date=date(2024, 11, 10), amount=Decimal("50.00"),
            category="Food", account="Cash", notes="",
            created_at=date(2024, 11, 10), updated_at=date(2024, 11, 10)
        ),
        ExpenseResponse(
            id=3, date=date(2024, 11, 15), amount=Decimal("200.00"),
            category="Travel", account="Card", notes="",
            created_at=date(2024, 11, 15), updated_at=date(2024, 11, 15)
        )
    ]
    
    mock_expense_service.list_expenses.return_value = (expenses, len(expenses))
    mock_income_service.list_income.return_value = ([], 0)
    
    # Act
    result = await analytics_engine._execute_analytics(parsed_query)
    
    # Assert
    assert result['aggregation_type'] == 'by_account'
    assert result['accounts']['Card'] == 300.0  # 100 + 200
    assert result['accounts']['Cash'] == 50.0
    assert result['total'] == 350.0


@pytest.mark.asyncio
async def test_execute_analytics_by_month(analytics_engine, mock_expense_service, mock_income_service):
    """Test month-based aggregation."""
    # Arrange
    parsed_query = {
        "aggregation": "by_month"
    }
    
    # Mock expense data across multiple months
    expenses = [
        ExpenseResponse(
            id=1, date=date(2024, 11, 5), amount=Decimal("100.00"),
            category="Food", account="Card", notes="",
            created_at=date(2024, 11, 5), updated_at=date(2024, 11, 5)
        ),
        ExpenseResponse(
            id=2, date=date(2024, 12, 10), amount=Decimal("200.00"),
            category="Food", account="Cash", notes="",
            created_at=date(2024, 12, 10), updated_at=date(2024, 12, 10)
        )
    ]
    
    # Mock income data
    income_records = [
        IncomeResponse(
            id=1, date=date(2024, 11, 1), amount=Decimal("5000.00"),
            category="Salary", notes="",
            created_at=date(2024, 11, 1), updated_at=date(2024, 11, 1)
        ),
        IncomeResponse(
            id=2, date=date(2024, 12, 1), amount=Decimal("5500.00"),
            category="Salary", notes="",
            created_at=date(2024, 12, 1), updated_at=date(2024, 12, 1)
        )
    ]
    
    mock_expense_service.list_expenses.return_value = (expenses, len(expenses))
    mock_income_service.list_income.return_value = (income_records, len(income_records))
    
    # Act
    result = await analytics_engine._execute_analytics(parsed_query)
    
    # Assert
    assert result['aggregation_type'] == 'by_month'
    assert len(result['data']) == 2
    assert result['data'][0]['month'] == '2024-11'
    assert result['data'][0]['expenses'] == 100.0
    assert result['data'][0]['income'] == 5000.0
    assert result['data'][0]['net'] == 4900.0
    assert result['data'][1]['month'] == '2024-12'
    assert result['data'][1]['expenses'] == 200.0
    assert result['data'][1]['income'] == 5500.0
    assert result['total_expenses'] == 300.0
    assert result['total_income'] == 10500.0


@pytest.mark.asyncio
async def test_execute_analytics_total(analytics_engine, mock_expense_service, mock_income_service):
    """Test total aggregation."""
    # Arrange
    parsed_query = {
        "aggregation": "total"
    }
    
    # Mock expense data
    expenses = [
        ExpenseResponse(
            id=1, date=date(2024, 11, 5), amount=Decimal("100.00"),
            category="Food", account="Card", notes="",
            created_at=date(2024, 11, 5), updated_at=date(2024, 11, 5)
        ),
        ExpenseResponse(
            id=2, date=date(2024, 11, 10), amount=Decimal("50.00"),
            category="Food", account="Cash", notes="",
            created_at=date(2024, 11, 10), updated_at=date(2024, 11, 10)
        )
    ]
    
    # Mock income data
    income_records = [
        IncomeResponse(
            id=1, date=date(2024, 11, 1), amount=Decimal("5000.00"),
            category="Salary", notes="",
            created_at=date(2024, 11, 1), updated_at=date(2024, 11, 1)
        )
    ]
    
    mock_expense_service.list_expenses.return_value = (expenses, len(expenses))
    mock_income_service.list_income.return_value = (income_records, len(income_records))
    
    # Act
    result = await analytics_engine._execute_analytics(parsed_query)
    
    # Assert
    assert result['aggregation_type'] == 'total'
    assert result['total_expenses'] == 150.0
    assert result['total_income'] == 5000.0
    assert result['net'] == 4850.0
    assert result['expense_count'] == 2
    assert result['income_count'] == 1


@pytest.mark.asyncio
async def test_execute_analytics_with_filters(analytics_engine, mock_expense_service, mock_income_service):
    """Test that filters are properly passed to services."""
    # Arrange
    parsed_query = {
        "time_period": {"start_date": "2024-11-01", "end_date": "2024-11-30"},
        "categories": ["Food", "Travel"],
        "accounts": ["Card"],
        "aggregation": "total"
    }
    
    mock_expense_service.list_expenses.return_value = ([], 0)
    mock_income_service.list_income.return_value = ([], 0)
    
    # Act
    await analytics_engine._execute_analytics(parsed_query)
    
    # Assert - verify the service was called with correct filters
    call_args = mock_expense_service.list_expenses.call_args
    filters = call_args[0][0]
    
    assert filters.start_date == date(2024, 11, 1)
    assert filters.end_date == date(2024, 11, 30)
    assert filters.categories == ["Food", "Travel"]
    assert filters.accounts == ["Card"]
    assert filters.page_size == 100  # Max allowed by ExpenseFilter
