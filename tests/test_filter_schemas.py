import pytest
from datetime import date
from decimal import Decimal
from pydantic import ValidationError
from app.schemas.filter import ExpenseFilter


def test_expense_filter_defaults():
    """Test ExpenseFilter with default values."""
    filter_model = ExpenseFilter()
    
    assert filter_model.start_date is None
    assert filter_model.end_date is None
    assert filter_model.categories is None
    assert filter_model.accounts is None
    assert filter_model.min_amount is None
    assert filter_model.max_amount is None
    assert filter_model.page == 1
    assert filter_model.page_size == 50


def test_expense_filter_with_date_range():
    """Test ExpenseFilter with valid date range."""
    filter_model = ExpenseFilter(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31)
    )
    
    assert filter_model.start_date == date(2024, 1, 1)
    assert filter_model.end_date == date(2024, 12, 31)


def test_expense_filter_invalid_date_range():
    """Test ExpenseFilter rejects end_date before start_date."""
    with pytest.raises(ValidationError) as exc_info:
        ExpenseFilter(
            start_date=date(2024, 12, 31),
            end_date=date(2024, 1, 1)
        )
    
    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0]['loc'] == ('end_date',)
    assert 'end_date must be after or equal to start_date' in errors[0]['msg']


def test_expense_filter_equal_dates():
    """Test ExpenseFilter allows equal start and end dates."""
    filter_model = ExpenseFilter(
        start_date=date(2024, 6, 15),
        end_date=date(2024, 6, 15)
    )
    
    assert filter_model.start_date == date(2024, 6, 15)
    assert filter_model.end_date == date(2024, 6, 15)


def test_expense_filter_with_categories():
    """Test ExpenseFilter with category list."""
    filter_model = ExpenseFilter(
        categories=["Food", "Travel", "Shopping"]
    )
    
    assert filter_model.categories == ["Food", "Travel", "Shopping"]


def test_expense_filter_with_accounts():
    """Test ExpenseFilter with account list."""
    filter_model = ExpenseFilter(
        accounts=["Cash", "Card", "UPI"]
    )
    
    assert filter_model.accounts == ["Cash", "Card", "UPI"]


def test_expense_filter_with_amount_range():
    """Test ExpenseFilter with amount range."""
    filter_model = ExpenseFilter(
        min_amount=Decimal("10.00"),
        max_amount=Decimal("100.00")
    )
    
    assert filter_model.min_amount == Decimal("10.00")
    assert filter_model.max_amount == Decimal("100.00")


def test_expense_filter_pagination_defaults():
    """Test ExpenseFilter pagination defaults."""
    filter_model = ExpenseFilter()
    
    assert filter_model.page == 1
    assert filter_model.page_size == 50


def test_expense_filter_custom_pagination():
    """Test ExpenseFilter with custom pagination."""
    filter_model = ExpenseFilter(page=3, page_size=25)
    
    assert filter_model.page == 3
    assert filter_model.page_size == 25


def test_expense_filter_page_minimum():
    """Test ExpenseFilter rejects page less than 1."""
    with pytest.raises(ValidationError) as exc_info:
        ExpenseFilter(page=0)
    
    errors = exc_info.value.errors()
    assert any(error['loc'] == ('page',) for error in errors)


def test_expense_filter_page_size_minimum():
    """Test ExpenseFilter rejects page_size less than 1."""
    with pytest.raises(ValidationError) as exc_info:
        ExpenseFilter(page_size=0)
    
    errors = exc_info.value.errors()
    assert any(error['loc'] == ('page_size',) for error in errors)


def test_expense_filter_page_size_maximum():
    """Test ExpenseFilter rejects page_size greater than 100."""
    with pytest.raises(ValidationError) as exc_info:
        ExpenseFilter(page_size=101)
    
    errors = exc_info.value.errors()
    assert any(error['loc'] == ('page_size',) for error in errors)


def test_expense_filter_page_size_boundary():
    """Test ExpenseFilter accepts page_size at boundaries."""
    filter_min = ExpenseFilter(page_size=1)
    assert filter_min.page_size == 1
    
    filter_max = ExpenseFilter(page_size=100)
    assert filter_max.page_size == 100


def test_expense_filter_all_filters():
    """Test ExpenseFilter with all filters specified."""
    filter_model = ExpenseFilter(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        categories=["Food", "Travel"],
        accounts=["Cash", "Card"],
        min_amount=Decimal("5.00"),
        max_amount=Decimal("500.00"),
        page=2,
        page_size=25
    )
    
    assert filter_model.start_date == date(2024, 1, 1)
    assert filter_model.end_date == date(2024, 12, 31)
    assert filter_model.categories == ["Food", "Travel"]
    assert filter_model.accounts == ["Cash", "Card"]
    assert filter_model.min_amount == Decimal("5.00")
    assert filter_model.max_amount == Decimal("500.00")
    assert filter_model.page == 2
    assert filter_model.page_size == 25


def test_expense_filter_empty_lists():
    """Test ExpenseFilter with empty category and account lists."""
    filter_model = ExpenseFilter(
        categories=[],
        accounts=[]
    )
    
    assert filter_model.categories == []
    assert filter_model.accounts == []
