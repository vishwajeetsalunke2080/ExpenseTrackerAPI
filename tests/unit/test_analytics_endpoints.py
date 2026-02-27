"""Unit tests for analytics API endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import date
from decimal import Decimal

from app.models.expense import Expense
from app.services.analytics_engine import AnalyticsEngine
from app.api.analytics import get_analytics_engine


@pytest.mark.asyncio
async def test_analytics_query_success(test_client: AsyncClient, test_db: AsyncSession):
    """Test successful analytics query processing.
    
    Requirements: 6.1, 6.4
    """
    # Create test expenses
    expenses = [
        Expense(
            date=date(2024, 11, 5),
            amount=Decimal("50.00"),
            category="Food",
            account="Card",
            notes="Lunch"
        ),
        Expense(
            date=date(2024, 11, 10),
            amount=Decimal("100.00"),
            category="Travel",
            account="Card",
            notes="Gas"
        ),
        Expense(
            date=date(2024, 11, 15),
            amount=Decimal("75.00"),
            category="Food",
            account="Cash",
            notes="Groceries"
        ),
    ]
    for expense in expenses:
        test_db.add(expense)
    await test_db.commit()
    
    # Mock the _parse_query method at the class level
    original_parse = AnalyticsEngine._parse_query
    
    async def mock_parse_query(self, query: str):
        return {
            "time_period": {"start_date": "2024-11-01", "end_date": "2024-11-30"},
            "aggregation": "by_category"
        }
    
    AnalyticsEngine._parse_query = mock_parse_query
    
    try:
        # Make request
        response = await test_client.post(
            "/analytics/query",
            params={"query": "What are the spends for November separated by categories?"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "query" in data
        assert "summary" in data
        assert "data" in data
        
        # Check data content
        assert data["data"]["aggregation_type"] == "by_category"
        assert "expenses" in data["data"]
        assert "Food" in data["data"]["expenses"]
        assert "Travel" in data["data"]["expenses"]
        
        # Verify amounts
        assert data["data"]["expenses"]["Food"] == 125.00  # 50 + 75
        assert data["data"]["expenses"]["Travel"] == 100.00
    finally:
        # Restore original method
        AnalyticsEngine._parse_query = original_parse


@pytest.mark.asyncio
async def test_analytics_query_total_aggregation(test_client: AsyncClient, test_db: AsyncSession):
    """Test analytics query with total aggregation.
    
    Requirements: 6.1
    """
    # Create test expenses
    expenses = [
        Expense(
            date=date(2024, 12, 1),
            amount=Decimal("50.00"),
            category="Food",
            account="Card",
            notes="Lunch"
        ),
        Expense(
            date=date(2024, 12, 5),
            amount=Decimal("100.00"),
            category="Travel",
            account="Card",
            notes="Gas"
        ),
    ]
    for expense in expenses:
        test_db.add(expense)
    await test_db.commit()
    
    # Mock the _parse_query method at the class level
    original_parse = AnalyticsEngine._parse_query
    
    async def mock_parse_query(self, query: str):
        return {
            "time_period": {"start_date": "2024-12-01", "end_date": "2024-12-31"},
            "aggregation": "total"
        }
    
    AnalyticsEngine._parse_query = mock_parse_query
    
    try:
        # Make request
        response = await test_client.post(
            "/analytics/query",
            params={"query": "What are my total expenses for December?"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert data["data"]["aggregation_type"] == "total"
        assert data["data"]["total_expenses"] == 150.00
        assert data["data"]["expense_count"] == 2
    finally:
        # Restore original method
        AnalyticsEngine._parse_query = original_parse


@pytest.mark.asyncio
async def test_analytics_query_empty_results(test_client: AsyncClient, test_db: AsyncSession):
    """Test analytics query with no matching expenses.
    
    Requirements: 6.1
    """
    # Don't create any expenses
    
    # Mock the _parse_query method at the class level
    original_parse = AnalyticsEngine._parse_query
    
    async def mock_parse_query(self, query: str):
        return {
            "time_period": {"start_date": "2024-11-01", "end_date": "2024-11-30"},
            "aggregation": "by_category"
        }
    
    AnalyticsEngine._parse_query = mock_parse_query
    
    try:
        # Make request
        response = await test_client.post(
            "/analytics/query",
            params={"query": "What are the spends for November separated by categories?"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Check that it handles empty results gracefully
        assert "summary" in data
        assert "No transactions found" in data["summary"]
    finally:
        # Restore original method
        AnalyticsEngine._parse_query = original_parse


@pytest.mark.asyncio
async def test_analytics_query_invalid_query_too_short(test_client: AsyncClient):
    """Test analytics query with query string that's too short.
    
    Requirements: 6.4
    """
    # Query is less than 5 characters (minimum length)
    response = await test_client.post(
        "/analytics/query",
        params={"query": "test"}
    )
    
    # Should return validation error
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analytics_query_unparseable_query(test_client: AsyncClient, test_db: AsyncSession):
    """Test analytics query that cannot be parsed by LLM.
    
    Requirements: 6.4
    """
    # Mock the _parse_query method at the class level to raise ValueError
    original_parse = AnalyticsEngine._parse_query
    
    async def mock_parse_query(self, query: str):
        raise ValueError(
            "Unable to understand your query. Please include specific details about what you want to know."
        )
    
    AnalyticsEngine._parse_query = mock_parse_query
    
    try:
        # Make request with vague query
        response = await test_client.post(
            "/analytics/query",
            params={"query": "random gibberish that makes no sense"}
        )
        
        # Should return 400 error with helpful message
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "unable to understand" in data["detail"].lower() or "query" in data["detail"].lower()
    finally:
        # Restore original method
        AnalyticsEngine._parse_query = original_parse


@pytest.mark.asyncio
async def test_analytics_query_openai_error(test_client: AsyncClient, test_db: AsyncSession):
    """Test analytics query when OpenAI service fails.
    
    Requirements: 6.4
    """
    # Mock the _parse_query method at the class level to raise an exception
    original_parse = AnalyticsEngine._parse_query
    
    async def mock_parse_query(self, query: str):
        raise Exception("API key invalid")
    
    AnalyticsEngine._parse_query = mock_parse_query
    
    try:
        # Make request
        response = await test_client.post(
            "/analytics/query",
            params={"query": "What are my expenses for November?"}
        )
        
        # Should return 400 error with helpful message
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        # Should suggest query reformulation
        assert any(keyword in data["detail"].lower() for keyword in ["unable", "error", "try"])
    finally:
        # Restore original method
        AnalyticsEngine._parse_query = original_parse


@pytest.mark.asyncio
async def test_analytics_query_by_account(test_client: AsyncClient, test_db: AsyncSession):
    """Test analytics query with account-based aggregation.
    
    Requirements: 6.1
    """
    # Create test expenses
    expenses = [
        Expense(
            date=date(2024, 11, 5),
            amount=Decimal("50.00"),
            category="Food",
            account="Card",
            notes="Lunch"
        ),
        Expense(
            date=date(2024, 11, 10),
            amount=Decimal("100.00"),
            category="Travel",
            account="Card",
            notes="Gas"
        ),
        Expense(
            date=date(2024, 11, 15),
            amount=Decimal("75.00"),
            category="Food",
            account="Cash",
            notes="Groceries"
        ),
    ]
    for expense in expenses:
        test_db.add(expense)
    await test_db.commit()
    
    # Mock the _parse_query method at the class level
    original_parse = AnalyticsEngine._parse_query
    
    async def mock_parse_query(self, query: str):
        return {
            "time_period": {"start_date": "2024-11-01", "end_date": "2024-11-30"},
            "aggregation": "by_account"
        }
    
    AnalyticsEngine._parse_query = mock_parse_query
    
    try:
        # Make request
        response = await test_client.post(
            "/analytics/query",
            params={"query": "Show me spending by account for November"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert data["data"]["aggregation_type"] == "by_account"
        assert "accounts" in data["data"]
        assert "Card" in data["data"]["accounts"]
        assert "Cash" in data["data"]["accounts"]
        
        # Verify amounts
        assert data["data"]["accounts"]["Card"] == 150.00  # 50 + 100
        assert data["data"]["accounts"]["Cash"] == 75.00
    finally:
        # Restore original method
        AnalyticsEngine._parse_query = original_parse


@pytest.mark.asyncio
async def test_analytics_query_with_category_filter(test_client: AsyncClient, test_db: AsyncSession):
    """Test analytics query with specific category filter.
    
    Requirements: 6.1
    """
    # Create test expenses
    expenses = [
        Expense(
            date=date(2024, 11, 5),
            amount=Decimal("50.00"),
            category="Food",
            account="Card",
            notes="Lunch"
        ),
        Expense(
            date=date(2024, 11, 10),
            amount=Decimal("100.00"),
            category="Travel",
            account="Card",
            notes="Gas"
        ),
        Expense(
            date=date(2024, 11, 15),
            amount=Decimal("75.00"),
            category="Food",
            account="Cash",
            notes="Groceries"
        ),
    ]
    for expense in expenses:
        test_db.add(expense)
    await test_db.commit()
    
    # Mock the _parse_query method at the class level with category filter
    original_parse = AnalyticsEngine._parse_query
    
    async def mock_parse_query(self, query: str):
        return {
            "categories": ["Food"],
            "aggregation": "total"
        }
    
    AnalyticsEngine._parse_query = mock_parse_query
    
    try:
        # Make request
        response = await test_client.post(
            "/analytics/query",
            params={"query": "How much did I spend on Food?"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Check that only Food expenses are included
        assert data["data"]["aggregation_type"] == "total"
        assert data["data"]["total_expenses"] == 125.00  # 50 + 75 (only Food)
        assert data["data"]["expense_count"] == 2
    finally:
        # Restore original method
        AnalyticsEngine._parse_query = original_parse


@pytest.mark.asyncio
async def test_analytics_query_missing_query_parameter(test_client: AsyncClient):
    """Test analytics query without query parameter.
    
    Requirements: 6.4
    """
    # Make request without query parameter
    response = await test_client.post("/analytics/query")
    
    # Should return validation error
    assert response.status_code == 422
