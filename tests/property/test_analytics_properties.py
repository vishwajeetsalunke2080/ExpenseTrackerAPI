"""Property-based tests for AnalyticsEngine.

These tests verify correctness properties for natural language query parsing
and analytics execution using Hypothesis.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
import json

from app.services.analytics_engine import AnalyticsEngine
from app.services.expense_service import ExpenseService
from app.services.income_service import IncomeService


# Custom strategies for generating natural language queries
@st.composite
def query_with_time_period(draw):
    """Generate queries with time periods."""
    year = draw(st.integers(min_value=2020, max_value=2030))
    month = draw(st.integers(min_value=1, max_value=12))
    
    # Generate different query formats
    query_format = draw(st.sampled_from([
        f"What are my expenses for {month}/{year}?",
        f"Show me spending for month {month} of {year}",
        f"Total expenses in {year}-{month:02d}",
    ]))
    
    return query_format, year, month


@st.composite
def query_with_categories(draw):
    """Generate queries with category mentions."""
    categories = draw(st.lists(
        st.sampled_from(['Food', 'Travel', 'Groceries', 'Shopping', 'Entertainment']),
        min_size=1,
        max_size=3,
        unique=True
    ))
    
    if len(categories) == 1:
        query = f"Show me spending on {categories[0]}"
    else:
        query = f"What are my expenses for {' and '.join(categories)}?"
    
    return query, categories


@st.composite
def query_with_aggregation(draw):
    """Generate queries with aggregation requests."""
    aggregation_type = draw(st.sampled_from([
        'by_category',
        'by_account',
        'by_month',
        'total'
    ]))
    
    query_templates = {
        'by_category': "Show me spending separated by categories",
        'by_account': "Break down expenses by account",
        'by_month': "Show monthly spending breakdown",
        'total': "What is my total spending?"
    }
    
    return query_templates[aggregation_type], aggregation_type


@st.composite
def query_with_accounts(draw):
    """Generate queries with account mentions."""
    accounts = draw(st.lists(
        st.sampled_from(['Cash', 'Card', 'UPI']),
        min_size=1,
        max_size=2,
        unique=True
    ))
    
    if len(accounts) == 1:
        query = f"How much did I spend using {accounts[0]}?"
    else:
        query = f"Show expenses from {' and '.join(accounts)}"
    
    return query, accounts


@st.composite
def complex_query(draw):
    """Generate complex queries with multiple parameters."""
    year = draw(st.integers(min_value=2020, max_value=2030))
    month = draw(st.integers(min_value=1, max_value=12))
    categories = draw(st.lists(
        st.sampled_from(['Food', 'Travel', 'Groceries']),
        min_size=1,
        max_size=2,
        unique=True
    ))
    aggregation = draw(st.sampled_from(['by_category', 'total']))
    
    if aggregation == 'by_category':
        query = f"What are the spends for {month}/{year} separated by categories?"
    else:
        query = f"Total spending on {' and '.join(categories)} in {month}/{year}"
    
    return query, year, month, categories, aggregation


# Property 14: Natural language query parameter extraction
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(query_data=query_with_time_period())
async def test_property_14_query_parameter_extraction_time_period(query_data):
    """
    **Validates: Requirements 6.1**
    
    Property 14: Natural language query parameter extraction
    
    For any natural language query containing time periods, the Analytics Engine
    should extract these parameters into a structured format that can be used for querying.
    """
    query, year, month = query_data
    
    # Mock OpenAI client to return structured response
    mock_openai = AsyncMock()
    mock_expense_service = MagicMock(spec=ExpenseService)
    
    # Create expected parsed response
    start_date = date(year, month, 1)
    # Get last day of month
    if month == 12:
        end_date = date(year, 12, 31)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    
    parsed_response = {
        "time_period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        "aggregation": "total"
    }
    
    # Mock the OpenAI response
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = json.dumps(parsed_response)
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_completion)
    
    # Create analytics engine
    engine = AnalyticsEngine(mock_openai, mock_expense_service)
    
    # Parse the query
    result = await engine._parse_query(query)
    
    # Verify that time_period was extracted
    assert 'time_period' in result, "Query should extract time_period"
    assert 'start_date' in result['time_period'], "time_period should contain start_date"
    assert 'end_date' in result['time_period'], "time_period should contain end_date"
    
    # Verify dates are in ISO format (can be parsed)
    start = date.fromisoformat(result['time_period']['start_date'])
    end = date.fromisoformat(result['time_period']['end_date'])
    
    # Verify dates are valid (start <= end)
    assert start <= end, "start_date should be before or equal to end_date"


@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(query_data=query_with_categories())
async def test_property_14_query_parameter_extraction_categories(query_data):
    """
    **Validates: Requirements 6.1**
    
    Property 14: Natural language query parameter extraction
    
    For any natural language query containing categories, the Analytics Engine
    should extract these parameters into a structured format.
    """
    query, categories = query_data
    
    # Mock OpenAI client
    mock_openai = AsyncMock()
    mock_expense_service = MagicMock(spec=ExpenseService)
    
    parsed_response = {
        "categories": categories,
        "aggregation": "total"
    }
    
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = json.dumps(parsed_response)
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_completion)
    
    engine = AnalyticsEngine(mock_openai, mock_expense_service)
    result = await engine._parse_query(query)
    
    # Verify categories were extracted
    assert 'categories' in result, "Query should extract categories"
    assert isinstance(result['categories'], list), "categories should be a list"
    assert len(result['categories']) > 0, "categories list should not be empty"


@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(query_data=query_with_aggregation())
async def test_property_14_query_parameter_extraction_aggregation(query_data):
    """
    **Validates: Requirements 6.1**
    
    Property 14: Natural language query parameter extraction
    
    For any natural language query containing aggregation requests, the Analytics Engine
    should extract the aggregation type into a structured format.
    """
    query, aggregation_type = query_data
    
    # Mock OpenAI client
    mock_openai = AsyncMock()
    mock_expense_service = MagicMock(spec=ExpenseService)
    
    parsed_response = {
        "aggregation": aggregation_type
    }
    
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = json.dumps(parsed_response)
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_completion)
    
    engine = AnalyticsEngine(mock_openai, mock_expense_service)
    result = await engine._parse_query(query)
    
    # Verify aggregation was extracted
    assert 'aggregation' in result, "Query should extract aggregation type"
    assert result['aggregation'] in ['by_category', 'by_account', 'by_month', 'by_week', 'by_day', 'total'], \
        "aggregation should be a valid type"


@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(query_data=query_with_accounts())
async def test_property_14_query_parameter_extraction_accounts(query_data):
    """
    **Validates: Requirements 6.1**
    
    Property 14: Natural language query parameter extraction
    
    For any natural language query containing account mentions, the Analytics Engine
    should extract these parameters into a structured format.
    """
    query, accounts = query_data
    
    # Mock OpenAI client
    mock_openai = AsyncMock()
    mock_expense_service = MagicMock(spec=ExpenseService)
    
    parsed_response = {
        "accounts": accounts,
        "aggregation": "total"
    }
    
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = json.dumps(parsed_response)
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_completion)
    
    engine = AnalyticsEngine(mock_openai, mock_expense_service)
    result = await engine._parse_query(query)
    
    # Verify accounts were extracted
    assert 'accounts' in result, "Query should extract accounts"
    assert isinstance(result['accounts'], list), "accounts should be a list"
    assert len(result['accounts']) > 0, "accounts list should not be empty"


@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(query_data=complex_query())
async def test_property_14_query_parameter_extraction_complex(query_data):
    """
    **Validates: Requirements 6.1**
    
    Property 14: Natural language query parameter extraction
    
    For any natural language query containing multiple parameters (time periods,
    categories, aggregation), the Analytics Engine should extract all parameters
    into a structured format.
    """
    query, year, month, categories, aggregation = query_data
    
    # Mock OpenAI client
    mock_openai = AsyncMock()
    mock_expense_service = MagicMock(spec=ExpenseService)
    
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year, 12, 31)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    
    parsed_response = {
        "time_period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        "categories": categories if aggregation == 'total' else None,
        "aggregation": aggregation
    }
    
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = json.dumps(parsed_response)
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_completion)
    
    engine = AnalyticsEngine(mock_openai, mock_expense_service)
    result = await engine._parse_query(query)
    
    # Verify at least one parameter was extracted
    has_params = (
        'time_period' in result or
        'categories' in result or
        'aggregation' in result or
        'accounts' in result
    )
    assert has_params, "Query should extract at least one parameter"
    
    # If time_period is present, verify it's valid
    if 'time_period' in result and result['time_period']:
        assert 'start_date' in result['time_period']
        assert 'end_date' in result['time_period']
        start = date.fromisoformat(result['time_period']['start_date'])
        end = date.fromisoformat(result['time_period']['end_date'])
        assert start <= end, "start_date should be before or equal to end_date"
    
    # If categories is present, verify it's a list
    if 'categories' in result and result['categories']:
        assert isinstance(result['categories'], list)
        assert len(result['categories']) > 0
    
    # If aggregation is present, verify it's valid
    if 'aggregation' in result and result['aggregation']:
        assert result['aggregation'] in ['by_category', 'by_account', 'by_month', 'by_week', 'by_day', 'total']


# Property 15: Category aggregation correctness
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    expenses_data=st.lists(
        st.fixed_dictionaries({
            'date': st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
            'amount': st.decimals(min_value=Decimal('0.01'), max_value=Decimal('9999.99'), places=2),
            'category': st.sampled_from(['Food', 'Travel', 'Groceries', 'Shopping', 'Entertainment', 'Other']),
            'account': st.sampled_from(['Cash', 'Card', 'UPI']),
            'notes': st.text(max_size=100)
        }),
        min_size=1,
        max_size=50
    )
)
async def test_property_15_category_aggregation_correctness(expenses_data, db_session):
    """
    **Validates: Requirements 6.2**
    
    Property 15: Category aggregation correctness
    
    For any collection of expenses, when requesting a category-based spending breakdown,
    the sum of amounts for each category should equal the total of all expenses,
    and each expense should be counted exactly once.
    """
    from app.models.expense import Expense
    from app.services.analytics_engine import AnalyticsEngine
    from app.services.expense_service import ExpenseService
    from app.services.cache_service import CacheService
    from unittest.mock import MagicMock
    
    # Create expenses in the database
    created_expenses = []
    for expense_data in expenses_data:
        expense = Expense(
            date=expense_data['date'],
            amount=expense_data['amount'],
            category=expense_data['category'],
            account=expense_data['account'],
            notes=expense_data['notes']
        )
        db_session.add(expense)
        created_expenses.append(expense)
    
    await db_session.commit()
    
    # Refresh to get IDs
    for expense in created_expenses:
        await db_session.refresh(expense)
    
    # Create mock cache service
    mock_cache = MagicMock(spec=CacheService)
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock()
    
    # Create expense service
    expense_service = ExpenseService(db_session, mock_cache)
    
    # Create analytics engine (OpenAI client not needed for this test)
    mock_openai = MagicMock()
    engine = AnalyticsEngine(mock_openai, expense_service)
    
    # Perform category aggregation
    result = engine._aggregate_by_category(created_expenses, [])
    
    # Calculate expected total from original data
    expected_total = sum(Decimal(str(e['amount'])) for e in expenses_data)
    
    # Verify the aggregation results
    assert 'expenses' in result, "Result should contain 'expenses' key"
    assert 'total_expenses' in result, "Result should contain 'total_expenses' key"
    
    # Verify that sum of category amounts equals total
    category_sum = sum(Decimal(str(amt)) for amt in result['expenses'].values())
    actual_total = Decimal(str(result['total_expenses']))
    
    # Allow for small floating point differences (within 0.01)
    assert abs(category_sum - expected_total) < Decimal('0.01'), \
        f"Sum of category amounts ({category_sum}) should equal total expenses ({expected_total})"
    
    assert abs(actual_total - expected_total) < Decimal('0.01'), \
        f"Total expenses ({actual_total}) should equal sum of all expenses ({expected_total})"
    
    # Verify each expense is counted exactly once by checking category totals
    expected_by_category = {}
    for expense_data in expenses_data:
        category = expense_data['category']
        if category not in expected_by_category:
            expected_by_category[category] = Decimal('0')
        expected_by_category[category] += Decimal(str(expense_data['amount']))
    
    # Verify all categories are present and amounts match
    for category, expected_amount in expected_by_category.items():
        assert category in result['expenses'], f"Category '{category}' should be in results"
        actual_amount = Decimal(str(result['expenses'][category]))
        assert abs(actual_amount - expected_amount) < Decimal('0.01'), \
            f"Category '{category}' amount ({actual_amount}) should equal expected ({expected_amount})"
    
    # Verify no extra categories in result
    assert set(result['expenses'].keys()) == set(expected_by_category.keys()), \
        "Result should contain exactly the categories present in expenses"


# Property 16: Time-based aggregation correctness
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    expenses_data=st.lists(
        st.fixed_dictionaries({
            'date': st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
            'amount': st.decimals(min_value=Decimal('0.01'), max_value=Decimal('9999.99'), places=2),
            'category': st.sampled_from(['Food', 'Travel', 'Groceries', 'Shopping', 'Entertainment', 'Other']),
            'account': st.sampled_from(['Cash', 'Card', 'UPI']),
            'notes': st.text(max_size=100)
        }),
        min_size=1,
        max_size=50
    ),
    aggregation_type=st.sampled_from(['by_month', 'by_week', 'by_day'])
)
async def test_property_16_time_based_aggregation_correctness(expenses_data, aggregation_type, db_session):
    """
    **Validates: Requirements 6.3**
    
    Property 16: Time-based aggregation correctness
    
    For any collection of expenses and any time period grouping (month, week, day),
    each expense should appear in exactly one time bucket, and the sum across all
    buckets should equal the total of all expenses.
    """
    from app.models.expense import Expense
    from app.services.analytics_engine import AnalyticsEngine
    from app.services.expense_service import ExpenseService
    from app.services.cache_service import CacheService
    from unittest.mock import MagicMock
    
    # Create expenses in the database
    created_expenses = []
    for expense_data in expenses_data:
        expense = Expense(
            date=expense_data['date'],
            amount=expense_data['amount'],
            category=expense_data['category'],
            account=expense_data['account'],
            notes=expense_data['notes']
        )
        db_session.add(expense)
        created_expenses.append(expense)
    
    await db_session.commit()
    
    # Refresh to get IDs
    for expense in created_expenses:
        await db_session.refresh(expense)
    
    # Create mock cache service
    mock_cache = MagicMock(spec=CacheService)
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock()
    
    # Create expense service
    expense_service = ExpenseService(db_session, mock_cache)
    
    # Create analytics engine (OpenAI client not needed for this test)
    mock_openai = MagicMock()
    engine = AnalyticsEngine(mock_openai, expense_service)
    
    # Perform time-based aggregation
    if aggregation_type == 'by_month':
        result = engine._aggregate_by_month(created_expenses, [])
    elif aggregation_type == 'by_week':
        result = engine._aggregate_by_week(created_expenses)
    elif aggregation_type == 'by_day':
        result = engine._aggregate_by_day(created_expenses)
    
    # Calculate expected total from original data
    expected_total = sum(Decimal(str(e['amount'])) for e in expenses_data)
    
    # Verify the aggregation results
    assert 'data' in result, "Result should contain 'data' key"
    assert 'aggregation_type' in result, "Result should contain 'aggregation_type' key"
    assert result['aggregation_type'] == aggregation_type, f"Aggregation type should be {aggregation_type}"
    
    # Verify that sum of all time bucket amounts equals total
    if aggregation_type == 'by_month':
        bucket_sum = sum(Decimal(str(item['expenses'])) for item in result['data'])
        assert 'total_expenses' in result, "Result should contain 'total_expenses' key"
        actual_total = Decimal(str(result['total_expenses']))
    else:
        bucket_sum = sum(Decimal(str(item['amount'])) for item in result['data'])
        assert 'total' in result, "Result should contain 'total' key"
        actual_total = Decimal(str(result['total']))
    
    # Allow for small floating point differences (within 0.01)
    assert abs(bucket_sum - expected_total) < Decimal('0.01'), \
        f"Sum of time bucket amounts ({bucket_sum}) should equal total expenses ({expected_total})"
    
    assert abs(actual_total - expected_total) < Decimal('0.01'), \
        f"Total expenses ({actual_total}) should equal sum of all expenses ({expected_total})"
    
    # Verify each expense appears in exactly one time bucket
    # Build expected buckets based on aggregation type
    expected_by_bucket = {}
    for expense_data in expenses_data:
        expense_date = expense_data['date']
        if aggregation_type == 'by_month':
            bucket_key = expense_date.strftime('%Y-%m')
        elif aggregation_type == 'by_week':
            bucket_key = expense_date.strftime('%Y-W%W')
        elif aggregation_type == 'by_day':
            bucket_key = expense_date.isoformat()
        
        if bucket_key not in expected_by_bucket:
            expected_by_bucket[bucket_key] = Decimal('0')
        expected_by_bucket[bucket_key] += Decimal(str(expense_data['amount']))
    
    # Verify all buckets are present and amounts match
    actual_buckets = {}
    for item in result['data']:
        if aggregation_type == 'by_month':
            bucket_key = item['month']
            amount = Decimal(str(item['expenses']))
        elif aggregation_type == 'by_week':
            bucket_key = item['week']
            amount = Decimal(str(item['amount']))
        elif aggregation_type == 'by_day':
            bucket_key = item['date']
            amount = Decimal(str(item['amount']))
        
        actual_buckets[bucket_key] = amount
    
    # Verify all expected buckets are present
    for bucket_key, expected_amount in expected_by_bucket.items():
        assert bucket_key in actual_buckets, f"Bucket '{bucket_key}' should be in results"
        actual_amount = actual_buckets[bucket_key]
        assert abs(actual_amount - expected_amount) < Decimal('0.01'), \
            f"Bucket '{bucket_key}' amount ({actual_amount}) should equal expected ({expected_amount})"
    
    # Verify no extra buckets in result
    assert set(actual_buckets.keys()) == set(expected_by_bucket.keys()), \
        "Result should contain exactly the time buckets present in expenses"
    
    # Verify count: number of buckets should be <= number of expenses
    # (multiple expenses can be in the same bucket, but each expense is in exactly one bucket)
    assert len(result['data']) <= len(expenses_data), \
        "Number of time buckets should not exceed number of expenses"
