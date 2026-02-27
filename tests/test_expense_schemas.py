import pytest
from datetime import date
from decimal import Decimal
from pydantic import ValidationError
from app.schemas.expense import ExpenseBase, ExpenseCreate, ExpenseUpdate, ExpenseResponse


def test_expense_base_valid():
    """Test ExpenseBase with valid data"""
    expense = ExpenseBase(
        date=date(2024, 1, 15),
        amount=Decimal("100.50"),
        category="Food",
        account="Cash",
        notes="Lunch"
    )
    assert expense.date == date(2024, 1, 15)
    assert expense.amount == Decimal("100.50")
    assert expense.category == "Food"
    assert expense.account == "Cash"
    assert expense.notes == "Lunch"


def test_expense_base_without_notes():
    """Test ExpenseBase without optional notes field"""
    expense = ExpenseBase(
        date=date(2024, 1, 15),
        amount=Decimal("100.50"),
        category="Food",
        account="Cash"
    )
    assert expense.notes is None


def test_expense_base_negative_amount():
    """Test ExpenseBase rejects negative amounts"""
    with pytest.raises(ValidationError) as exc_info:
        ExpenseBase(
            date=date(2024, 1, 15),
            amount=Decimal("-10.00"),
            category="Food",
            account="Cash"
        )
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("amount",) for error in errors)


def test_expense_base_zero_amount():
    """Test ExpenseBase rejects zero amounts"""
    with pytest.raises(ValidationError) as exc_info:
        ExpenseBase(
            date=date(2024, 1, 15),
            amount=Decimal("0.00"),
            category="Food",
            account="Cash"
        )
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("amount",) for error in errors)


def test_expense_base_missing_required_fields():
    """Test ExpenseBase rejects missing required fields"""
    with pytest.raises(ValidationError) as exc_info:
        ExpenseBase(
            date=date(2024, 1, 15),
            amount=Decimal("100.50")
        )
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("category",) for error in errors)
    assert any(error["loc"] == ("account",) for error in errors)


def test_expense_base_empty_category():
    """Test ExpenseBase rejects empty category"""
    with pytest.raises(ValidationError) as exc_info:
        ExpenseBase(
            date=date(2024, 1, 15),
            amount=Decimal("100.50"),
            category="",
            account="Cash"
        )
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("category",) for error in errors)


def test_expense_base_empty_account():
    """Test ExpenseBase rejects empty account"""
    with pytest.raises(ValidationError) as exc_info:
        ExpenseBase(
            date=date(2024, 1, 15),
            amount=Decimal("100.50"),
            category="Food",
            account=""
        )
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("account",) for error in errors)


def test_expense_base_max_length_validation():
    """Test ExpenseBase enforces max length constraints"""
    # Category max length is 100
    with pytest.raises(ValidationError):
        ExpenseBase(
            date=date(2024, 1, 15),
            amount=Decimal("100.50"),
            category="A" * 101,
            account="Cash"
        )
    
    # Account max length is 100
    with pytest.raises(ValidationError):
        ExpenseBase(
            date=date(2024, 1, 15),
            amount=Decimal("100.50"),
            category="Food",
            account="A" * 101
        )
    
    # Notes max length is 500
    with pytest.raises(ValidationError):
        ExpenseBase(
            date=date(2024, 1, 15),
            amount=Decimal("100.50"),
            category="Food",
            account="Cash",
            notes="A" * 501
        )


def test_expense_create_inherits_from_base():
    """Test ExpenseCreate has same validation as ExpenseBase"""
    expense = ExpenseCreate(
        date=date(2024, 1, 15),
        amount=Decimal("100.50"),
        category="Food",
        account="Cash"
    )
    assert expense.date == date(2024, 1, 15)
    assert expense.amount == Decimal("100.50")


def test_expense_update_all_fields_optional():
    """Test ExpenseUpdate allows all fields to be optional"""
    update = ExpenseUpdate()
    assert update.date is None
    assert update.amount is None
    assert update.category is None
    assert update.account is None
    assert update.notes is None


def test_expense_update_partial():
    """Test ExpenseUpdate with partial data"""
    update = ExpenseUpdate(
        amount=Decimal("200.00"),
        notes="Updated notes"
    )
    assert update.amount == Decimal("200.00")
    assert update.notes == "Updated notes"
    assert update.date is None
    assert update.category is None


def test_expense_update_validates_positive_amount():
    """Test ExpenseUpdate validates positive amounts when provided"""
    with pytest.raises(ValidationError) as exc_info:
        ExpenseUpdate(amount=Decimal("-50.00"))
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("amount",) for error in errors)


def test_expense_update_validates_min_length():
    """Test ExpenseUpdate validates min length when fields are provided"""
    with pytest.raises(ValidationError):
        ExpenseUpdate(category="")
    
    with pytest.raises(ValidationError):
        ExpenseUpdate(account="")


def test_expense_response_includes_id_and_timestamps():
    """Test ExpenseResponse includes id and timestamp fields"""
    response = ExpenseResponse(
        id=1,
        date=date(2024, 1, 15),
        amount=Decimal("100.50"),
        category="Food",
        account="Cash",
        notes="Lunch",
        created_at=date(2024, 1, 15),
        updated_at=date(2024, 1, 15)
    )
    assert response.id == 1
    assert response.created_at == date(2024, 1, 15)
    assert response.updated_at == date(2024, 1, 15)
