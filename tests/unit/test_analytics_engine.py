"""Unit tests for AnalyticsEngine."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.analytics_engine import AnalyticsEngine
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
import json


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    return AsyncMock()


@pytest.fixture
def mock_expense_service():
    """Create a mock ExpenseService."""
    return AsyncMock()


@pytest.fixture
def analytics_engine(mock_openai_client, mock_expense_service):
    """Create an AnalyticsEngine instance with mocked dependencies."""
    return AnalyticsEngine(mock_openai_client, mock_expense_service)


@pytest.mark.asyncio
async def test_analytics_engine_initialization(mock_openai_client, mock_expense_service):
    """Test that AnalyticsEngine can be initialized with required dependencies."""
    engine = AnalyticsEngine(mock_openai_client, mock_expense_service)
    
    assert engine.client == mock_openai_client
    assert engine.expense_service == mock_expense_service


@pytest.mark.asyncio
async def test_parse_query_extracts_time_period_and_aggregation(analytics_engine, mock_openai_client):
    """Test that _parse_query correctly extracts time period and aggregation type."""
    # Arrange
    query = "What are the spends for November separated by categories?"
    expected_response = {
        "time_period": {"start_date": "2024-11-01", "end_date": "2024-11-30"},
        "aggregation": "by_category"
    }
    
    # Mock the OpenAI response
    mock_message = ChatCompletionMessage(
        role="assistant",
        content=json.dumps(expected_response)
    )
    mock_choice = Choice(
        index=0,
        message=mock_message,
        finish_reason="stop"
    )
    mock_completion = ChatCompletion(
        id="test-id",
        model="gpt-4",
        object="chat.completion",
        created=1234567890,
        choices=[mock_choice]
    )
    mock_openai_client.chat.completions.create.return_value = mock_completion
    
    # Act
    result = await analytics_engine._parse_query(query)
    
    # Assert
    assert result == expected_response
    assert result["time_period"]["start_date"] == "2024-11-01"
    assert result["time_period"]["end_date"] == "2024-11-30"
    assert result["aggregation"] == "by_category"
    
    # Verify OpenAI was called with correct parameters
    mock_openai_client.chat.completions.create.assert_called_once()
    call_args = mock_openai_client.chat.completions.create.call_args
    assert call_args.kwargs["model"] == "gpt-4"
    assert call_args.kwargs["response_format"] == {"type": "json_object"}
    assert len(call_args.kwargs["messages"]) == 2
    assert call_args.kwargs["messages"][1]["content"] == query


@pytest.mark.asyncio
async def test_parse_query_extracts_categories_and_total(analytics_engine, mock_openai_client):
    """Test that _parse_query correctly extracts categories for total aggregation."""
    # Arrange
    query = "Show me total spending on Food and Travel"
    expected_response = {
        "categories": ["Food", "Travel"],
        "aggregation": "total"
    }
    
    # Mock the OpenAI response
    mock_message = ChatCompletionMessage(
        role="assistant",
        content=json.dumps(expected_response)
    )
    mock_choice = Choice(
        index=0,
        message=mock_message,
        finish_reason="stop"
    )
    mock_completion = ChatCompletion(
        id="test-id",
        model="gpt-4",
        object="chat.completion",
        created=1234567890,
        choices=[mock_choice]
    )
    mock_openai_client.chat.completions.create.return_value = mock_completion
    
    # Act
    result = await analytics_engine._parse_query(query)
    
    # Assert
    assert result == expected_response
    assert result["categories"] == ["Food", "Travel"]
    assert result["aggregation"] == "total"


@pytest.mark.asyncio
async def test_parse_query_extracts_accounts_and_time_period(analytics_engine, mock_openai_client):
    """Test that _parse_query correctly extracts accounts and time period."""
    # Arrange
    query = "How much did I spend using Card in December?"
    expected_response = {
        "time_period": {"start_date": "2024-12-01", "end_date": "2024-12-31"},
        "accounts": ["Card"],
        "aggregation": "total"
    }
    
    # Mock the OpenAI response
    mock_message = ChatCompletionMessage(
        role="assistant",
        content=json.dumps(expected_response)
    )
    mock_choice = Choice(
        index=0,
        message=mock_message,
        finish_reason="stop"
    )
    mock_completion = ChatCompletion(
        id="test-id",
        model="gpt-4",
        object="chat.completion",
        created=1234567890,
        choices=[mock_choice]
    )
    mock_openai_client.chat.completions.create.return_value = mock_completion
    
    # Act
    result = await analytics_engine._parse_query(query)
    
    # Assert
    assert result == expected_response
    assert result["time_period"]["start_date"] == "2024-12-01"
    assert result["time_period"]["end_date"] == "2024-12-31"
    assert result["accounts"] == ["Card"]
    assert result["aggregation"] == "total"


@pytest.mark.asyncio
async def test_parse_query_raises_value_error_on_failure(analytics_engine, mock_openai_client):
    """Test that _parse_query raises ValueError when OpenAI call fails."""
    # Arrange
    query = "Some unparseable query"
    mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
    
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await analytics_engine._parse_query(query)
    
    assert "Unable to parse query" in str(exc_info.value)
    assert "Please try rephrasing your question" in str(exc_info.value)


@pytest.mark.asyncio
async def test_parse_query_system_prompt_includes_examples(analytics_engine, mock_openai_client):
    """Test that the system prompt includes helpful examples."""
    # Arrange
    query = "Test query"
    expected_response = {"aggregation": "total"}
    
    # Mock the OpenAI response
    mock_message = ChatCompletionMessage(
        role="assistant",
        content=json.dumps(expected_response)
    )
    mock_choice = Choice(
        index=0,
        message=mock_message,
        finish_reason="stop"
    )
    mock_completion = ChatCompletion(
        id="test-id",
        model="gpt-4",
        object="chat.completion",
        created=1234567890,
        choices=[mock_choice]
    )
    mock_openai_client.chat.completions.create.return_value = mock_completion
    
    # Act
    await analytics_engine._parse_query(query)
    
    # Assert
    call_args = mock_openai_client.chat.completions.create.call_args
    system_message = call_args.kwargs["messages"][0]["content"]
    
    # Verify system prompt contains key instructions
    assert "time_period" in system_message
    assert "categories" in system_message
    assert "aggregation" in system_message
    assert "accounts" in system_message
    assert "by_category" in system_message
    assert "by_account" in system_message
    assert "by_month" in system_message
    assert "total" in system_message
    
    # Verify system prompt contains examples
    assert "Examples:" in system_message
    assert "What are the spends for November separated by categories?" in system_message


@pytest.mark.asyncio
async def test_format_results_category_aggregation(analytics_engine):
    """Test that _format_results correctly formats category aggregation results."""
    # Arrange
    query = "What are the spends for November separated by categories?"
    results = {
        'aggregation_type': 'by_category',
        'expenses': {
            'Food': 500.00,
            'Travel': 300.00,
            'Shopping': 200.00
        },
        'income': {
            'Salary': 5000.00
        },
        'total_expenses': 1000.00,
        'total_income': 5000.00
    }
    
    # Act
    formatted = await analytics_engine._format_results(results, query)
    
    # Assert
    assert formatted['query'] == query
    assert 'Total expenses: $1,000.00 across 3 categories' in formatted['summary']
    assert 'Total income: $5,000.00 across 1 categories' in formatted['summary']
    assert 'Expense Breakdown:' in formatted['breakdown']
    assert 'Food: $500.00 (50.0%)' in formatted['breakdown']
    assert 'Travel: $300.00 (30.0%)' in formatted['breakdown']
    assert 'Shopping: $200.00 (20.0%)' in formatted['breakdown']
    assert 'Income Breakdown:' in formatted['breakdown']
    assert 'Salary: $5,000.00 (100.0%)' in formatted['breakdown']
    assert formatted['data'] == results


@pytest.mark.asyncio
async def test_format_results_total_aggregation(analytics_engine):
    """Test that _format_results correctly formats total aggregation results."""
    # Arrange
    query = "What is my total spending?"
    results = {
        'aggregation_type': 'total',
        'total_expenses': 1500.50,
        'total_income': 5000.00,
        'net': 3499.50,
        'expense_count': 10,
        'income_count': 2
    }
    
    # Act
    formatted = await analytics_engine._format_results(results, query)
    
    # Assert
    assert formatted['query'] == query
    assert 'Total expenses: $1,500.50 (10 transactions)' in formatted['summary']
    assert 'Total income: $5,000.00 (2 transactions)' in formatted['summary']
    assert 'Net surplus: $3,499.50' in formatted['summary']
    assert formatted['data'] == results


@pytest.mark.asyncio
async def test_format_results_empty_results(analytics_engine):
    """Test that _format_results handles empty results gracefully."""
    # Arrange
    query = "Show me expenses for last year"
    results = {
        'aggregation_type': 'total',
        'total_expenses': 0,
        'total_income': 0,
        'net': 0,
        'expense_count': 0,
        'income_count': 0
    }
    
    # Act
    formatted = await analytics_engine._format_results(results, query)
    
    # Assert
    assert formatted['query'] == query
    assert formatted['summary'] == 'No transactions found for the specified criteria.'
    assert formatted['data'] == results


@pytest.mark.asyncio
async def test_format_results_monthly_aggregation(analytics_engine):
    """Test that _format_results correctly formats monthly aggregation results."""
    # Arrange
    query = "Show me monthly breakdown"
    results = {
        'aggregation_type': 'by_month',
        'data': [
            {'month': '2024-11', 'expenses': 1000.00, 'income': 5000.00, 'net': 4000.00},
            {'month': '2024-12', 'expenses': 1500.00, 'income': 5000.00, 'net': 3500.00}
        ],
        'total_expenses': 2500.00,
        'total_income': 10000.00
    }
    
    # Act
    formatted = await analytics_engine._format_results(results, query)
    
    # Assert
    assert formatted['query'] == query
    assert 'Total expenses: $2,500.00' in formatted['summary']
    assert 'Total income: $10,000.00' in formatted['summary']
    assert 'Net surplus: $7,500.00' in formatted['summary']
    assert 'over 2 months' in formatted['summary']
    assert 'Monthly Breakdown:' in formatted['breakdown']
    assert '2024-11: Expenses $1,000.00, Income $5,000.00, Net surplus $4,000.00' in formatted['breakdown']
    assert '2024-12: Expenses $1,500.00, Income $5,000.00, Net surplus $3,500.00' in formatted['breakdown']


@pytest.mark.asyncio
async def test_format_results_account_aggregation(analytics_engine):
    """Test that _format_results correctly formats account aggregation results."""
    # Arrange
    query = "Show me spending by account"
    results = {
        'aggregation_type': 'by_account',
        'accounts': {
            'Card': 800.00,
            'Cash': 300.00,
            'UPI': 200.00
        },
        'total': 1300.00
    }
    
    # Act
    formatted = await analytics_engine._format_results(results, query)
    
    # Assert
    assert formatted['query'] == query
    assert 'Total expenses: $1,300.00 across 3 accounts' in formatted['summary']
    assert 'Account Breakdown:' in formatted['breakdown']
    assert 'Card: $800.00 (61.5%)' in formatted['breakdown']
    assert 'Cash: $300.00 (23.1%)' in formatted['breakdown']
    assert 'UPI: $200.00 (15.4%)' in formatted['breakdown']



@pytest.mark.asyncio
async def test_parse_query_handles_json_decode_error(analytics_engine, mock_openai_client):
    """Test that _parse_query handles JSON decode errors with helpful message."""
    # Arrange
    query = "Some query"
    
    # Mock the OpenAI response with invalid JSON
    mock_message = ChatCompletionMessage(
        role="assistant",
        content="This is not valid JSON"
    )
    mock_choice = Choice(
        index=0,
        message=mock_message,
        finish_reason="stop"
    )
    mock_completion = ChatCompletion(
        id="test-id",
        model="gpt-4",
        object="chat.completion",
        created=1234567890,
        choices=[mock_choice]
    )
    mock_openai_client.chat.completions.create.return_value = mock_completion
    
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await analytics_engine._parse_query(query)
    
    assert "Unable to parse query - received invalid response format" in str(exc_info.value)
    assert "Please try rephrasing your question more clearly" in str(exc_info.value)
    assert "What are my expenses for November by category?" in str(exc_info.value)


@pytest.mark.asyncio
async def test_parse_query_handles_empty_parsed_result(analytics_engine, mock_openai_client):
    """Test that _parse_query handles empty parsed results with helpful message."""
    # Arrange
    query = "Some vague query"
    
    # Mock the OpenAI response with empty result
    mock_message = ChatCompletionMessage(
        role="assistant",
        content=json.dumps({})
    )
    mock_choice = Choice(
        index=0,
        message=mock_message,
        finish_reason="stop"
    )
    mock_completion = ChatCompletion(
        id="test-id",
        model="gpt-4",
        object="chat.completion",
        created=1234567890,
        choices=[mock_choice]
    )
    mock_openai_client.chat.completions.create.return_value = mock_completion
    
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await analytics_engine._parse_query(query)
    
    assert "Unable to understand your query" in str(exc_info.value)
    assert "Please include specific details" in str(exc_info.value)
    assert "A time period" in str(exc_info.value)
    assert "What you want to see" in str(exc_info.value)


@pytest.mark.asyncio
async def test_parse_query_handles_rate_limit_error(analytics_engine, mock_openai_client):
    """Test that _parse_query handles rate limit errors appropriately."""
    # Arrange
    query = "Some query"
    mock_openai_client.chat.completions.create.side_effect = Exception("Rate limit exceeded")
    
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await analytics_engine._parse_query(query)
    
    assert "Unable to process query due to service unavailability" in str(exc_info.value)
    assert "Please try again in a moment" in str(exc_info.value)


@pytest.mark.asyncio
async def test_process_query_handles_execution_errors(analytics_engine, mock_openai_client):
    """Test that process_query handles errors from _execute_analytics."""
    # Arrange
    query = "What are my expenses?"
    expected_response = {
        "time_period": {"start_date": "2024-11-01", "end_date": "2024-11-30"},
        "aggregation": "total"
    }
    
    # Mock successful parsing
    mock_message = ChatCompletionMessage(
        role="assistant",
        content=json.dumps(expected_response)
    )
    mock_choice = Choice(
        index=0,
        message=mock_message,
        finish_reason="stop"
    )
    mock_completion = ChatCompletion(
        id="test-id",
        model="gpt-4",
        object="chat.completion",
        created=1234567890,
        choices=[mock_choice]
    )
    mock_openai_client.chat.completions.create.return_value = mock_completion
    
    # Mock _execute_analytics to raise an error
    analytics_engine._execute_analytics = AsyncMock(side_effect=Exception("Database error"))
    
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await analytics_engine.process_query(query)
    
    assert "An error occurred while processing your query" in str(exc_info.value)
    assert "Please try rephrasing your question or simplifying your request" in str(exc_info.value)


@pytest.mark.asyncio
async def test_process_query_propagates_value_errors(analytics_engine, mock_openai_client):
    """Test that process_query propagates ValueError from _parse_query."""
    # Arrange
    query = "Some unparseable query"
    mock_openai_client.chat.completions.create.side_effect = Exception("Parse error")
    
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await analytics_engine.process_query(query)
    
    # Should get the error from _parse_query, not the generic wrapper
    assert "Unable to parse query" in str(exc_info.value)
    assert "Please try rephrasing your question more clearly" in str(exc_info.value)


# Integration-style unit tests for full process_query flow
# Requirements: 6.1, 6.2, 6.3, 6.4


@pytest.mark.asyncio
async def test_process_query_november_by_categories(analytics_engine, mock_openai_client, mock_expense_service):
    """
    Test example query: 'What are the spends for November separated by categories?'
    
    This tests the full flow from query parsing to result formatting.
    Requirements: 6.1, 6.2
    """
    # Arrange
    query = "What are the spends for November separated by categories?"
    
    # Mock OpenAI parsing response
    parsed_response = {
        "time_period": {"start_date": "2024-11-01", "end_date": "2024-11-30"},
        "aggregation": "by_category"
    }
    mock_message = ChatCompletionMessage(
        role="assistant",
        content=json.dumps(parsed_response)
    )
    mock_choice = Choice(index=0, message=mock_message, finish_reason="stop")
    mock_completion = ChatCompletion(
        id="test-id",
        model="gpt-4",
        object="chat.completion",
        created=1234567890,
        choices=[mock_choice]
    )
    mock_openai_client.chat.completions.create.return_value = mock_completion
    
    # Mock expense service to return sample expenses
    from decimal import Decimal
    from datetime import date
    
    class MockExpense:
        def __init__(self, date_val, amount, category, account):
            self.date = date_val
            self.amount = Decimal(str(amount))
            self.category = category
            self.account = account
    
    mock_expenses = [
        MockExpense(date(2024, 11, 5), 150.00, "Food", "Card"),
        MockExpense(date(2024, 11, 10), 200.00, "Travel", "Card"),
        MockExpense(date(2024, 11, 15), 100.00, "Food", "Cash"),
        MockExpense(date(2024, 11, 20), 50.00, "Shopping", "UPI"),
    ]
    
    mock_expense_service.list_expenses.return_value = (mock_expenses, len(mock_expenses))
    
    # Act
    result = await analytics_engine.process_query(query)
    
    # Assert
    assert result['query'] == query
    assert 'Total expenses: $500.00 across 3 categories' in result['summary']
    assert 'Expense Breakdown:' in result['breakdown']
    assert 'Food: $250.00 (50.0%)' in result['breakdown']
    assert 'Travel: $200.00 (40.0%)' in result['breakdown']
    assert 'Shopping: $50.00 (10.0%)' in result['breakdown']
    
    # Verify expense service was called with correct filters
    mock_expense_service.list_expenses.assert_called()
    call_args = mock_expense_service.list_expenses.call_args[0][0]
    assert call_args.start_date == date(2024, 11, 1)
    assert call_args.end_date == date(2024, 11, 30)


@pytest.mark.asyncio
async def test_process_query_unparseable_query_error(analytics_engine, mock_openai_client):
    """
    Test that unparseable queries return helpful error messages.
    
    Requirements: 6.4
    """
    # Arrange
    query = "asdfghjkl random gibberish xyz123"
    
    # Mock OpenAI to return empty result (unparseable)
    parsed_response = {}
    mock_message = ChatCompletionMessage(
        role="assistant",
        content=json.dumps(parsed_response)
    )
    mock_choice = Choice(index=0, message=mock_message, finish_reason="stop")
    mock_completion = ChatCompletion(
        id="test-id",
        model="gpt-4",
        object="chat.completion",
        created=1234567890,
        choices=[mock_choice]
    )
    mock_openai_client.chat.completions.create.return_value = mock_completion
    
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await analytics_engine.process_query(query)
    
    # Verify helpful error message
    error_message = str(exc_info.value)
    assert "Unable to understand your query" in error_message
    assert "Please include specific details" in error_message
    assert "time period" in error_message
    assert "Example queries:" in error_message


@pytest.mark.asyncio
async def test_process_query_empty_results(analytics_engine, mock_openai_client, mock_expense_service):
    """
    Test that queries with no matching expenses return appropriate empty result message.
    
    Requirements: 6.3
    """
    # Arrange
    query = "What are my expenses for January 2020?"
    
    # Mock OpenAI parsing response
    parsed_response = {
        "time_period": {"start_date": "2020-01-01", "end_date": "2020-01-31"},
        "aggregation": "total"
    }
    mock_message = ChatCompletionMessage(
        role="assistant",
        content=json.dumps(parsed_response)
    )
    mock_choice = Choice(index=0, message=mock_message, finish_reason="stop")
    mock_completion = ChatCompletion(
        id="test-id",
        model="gpt-4",
        object="chat.completion",
        created=1234567890,
        choices=[mock_choice]
    )
    mock_openai_client.chat.completions.create.return_value = mock_completion
    
    # Mock expense service to return empty list
    mock_expense_service.list_expenses.return_value = ([], 0)
    
    # Act
    result = await analytics_engine.process_query(query)
    
    # Assert
    assert result['query'] == query
    assert result['summary'] == 'No transactions found for the specified criteria.'
    assert result['data']['total_expenses'] == 0
    assert result['data']['expense_count'] == 0


@pytest.mark.asyncio
async def test_process_query_with_specific_categories(analytics_engine, mock_openai_client, mock_expense_service):
    """
    Test query with specific category filters.
    
    Requirements: 6.1, 6.2
    """
    # Arrange
    query = "Show me total spending on Food and Travel"
    
    # Mock OpenAI parsing response
    parsed_response = {
        "categories": ["Food", "Travel"],
        "aggregation": "total"
    }
    mock_message = ChatCompletionMessage(
        role="assistant",
        content=json.dumps(parsed_response)
    )
    mock_choice = Choice(index=0, message=mock_message, finish_reason="stop")
    mock_completion = ChatCompletion(
        id="test-id",
        model="gpt-4",
        object="chat.completion",
        created=1234567890,
        choices=[mock_choice]
    )
    mock_openai_client.chat.completions.create.return_value = mock_completion
    
    # Mock expense service
    from decimal import Decimal
    from datetime import date
    
    class MockExpense:
        def __init__(self, date_val, amount, category, account):
            self.date = date_val
            self.amount = Decimal(str(amount))
            self.category = category
            self.account = account
    
    mock_expenses = [
        MockExpense(date(2024, 11, 5), 150.00, "Food", "Card"),
        MockExpense(date(2024, 11, 10), 200.00, "Travel", "Card"),
    ]
    
    mock_expense_service.list_expenses.return_value = (mock_expenses, len(mock_expenses))
    
    # Act
    result = await analytics_engine.process_query(query)
    
    # Assert
    assert result['query'] == query
    assert 'Total expenses: $350.00' in result['summary']
    assert result['data']['total_expenses'] == Decimal('350.00')
    
    # Verify expense service was called with category filter
    mock_expense_service.list_expenses.assert_called()
    call_args = mock_expense_service.list_expenses.call_args[0][0]
    assert call_args.categories == ["Food", "Travel"]


@pytest.mark.asyncio
async def test_process_query_openai_api_error(analytics_engine, mock_openai_client):
    """
    Test that OpenAI API errors are handled gracefully.
    
    Requirements: 6.4
    """
    # Arrange
    query = "What are my expenses?"
    mock_openai_client.chat.completions.create.side_effect = Exception("API connection failed")
    
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await analytics_engine.process_query(query)
    
    # Verify helpful error message
    error_message = str(exc_info.value)
    assert "Unable to parse query" in error_message
    assert "Please try rephrasing your question" in error_message
