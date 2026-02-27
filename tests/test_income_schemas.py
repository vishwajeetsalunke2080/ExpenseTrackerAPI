import pytest
from datetime import date
from decimal import Decimal
from pydantic import ValidationError
from app.schemas.income import IncomeBase, IncomeCreate, IncomeUpdate, IncomeResponse


def test_income_base_valid():
    """Test IncomeBase with valid data"""
    income = IncomeBase(
        date=date(2024, 1, 15),
        amount=Decimal("5000.00"),
        category="Salary",
        notes="Monthly salary"
    )
    assert income.date == date(2024, 1, 15)
    assert income.amount == Decimal("5000.00")
    assert income.category == "Salary"
    assert income.notes == "Monthly salary"


def test_income_base_without_notes():
    """Test IncomeBase without optional notes field"""
    income = IncomeBase(
        date=date(2024, 1, 15),
        amount=Decimal("5000.00"),
        category="Salary"
    )
    assert income.notes is None


def test_income_base_negative_amount():
    """Test IncomeBase rejects negative amounts"""
    with pytest.raises(ValidationError) as exc_info:
        IncomeBase(
            date=date(2024, 1, 15),
            amount=Decimal("-100.00"),
            category="Salary"
        )
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("amount",) for error in errors)


def test_income_base_zero_amount():
    """Test IncomeBase rejects zero amounts"""
    with pytest.raises(ValidationError) as exc_info:
        IncomeBase(
            date=date(2024, 1, 15),
            amount=Decimal("0.00"),
            category="Salary"
        )
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("amount",) for error in errors)


def test_income_base_missing_required_fields():
    """Test IncomeBase rejects missing required fields"""
    with pytest.raises(ValidationError) as exc_info:
        IncomeBase(
            date=date(2024, 1, 15),
            amount=Decimal("5000.00")
        )
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("category",) for error in errors)


def test_income_base_empty_category():
    """Test IncomeBase rejects empty category"""
    with pytest.raises(ValidationError) as exc_info:
        IncomeBase(
            date=date(2024, 1, 15),
            amount=Decimal("5000.00"),
            category=""
        )
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("category",) for error in errors)


def test_income_base_max_length_validation():
    """Test IncomeBase enforces max length constraints"""
    # Category max length is 100
    with pytest.raises(ValidationError):
        IncomeBase(
            date=date(2024, 1, 15),
            amount=Decimal("5000.00"),
            category="A" * 101
        )
    
    # Notes max length is 500
    with pytest.raises(ValidationError):
        IncomeBase(
            date=date(2024, 1, 15),
            amount=Decimal("5000.00"),
            category="Salary",
            notes="A" * 501
        )


def test_income_create_inherits_from_base():
    """Test IncomeCreate has same validation as IncomeBase"""
    income = IncomeCreate(
        date=date(2024, 1, 15),
        amount=Decimal("5000.00"),
        category="Salary"
    )
    assert income.date == date(2024, 1, 15)
    assert income.amount == Decimal("5000.00")


def test_income_update_all_fields_optional():
    """Test IncomeUpdate allows all fields to be optional"""
    update = IncomeUpdate()
    assert update.date is None
    assert update.amount is None
    assert update.category is None
    assert update.notes is None


def test_income_update_partial():
    """Test IncomeUpdate with partial data"""
    update = IncomeUpdate(
        amount=Decimal("6000.00"),
        notes="Updated notes"
    )
    assert update.amount == Decimal("6000.00")
    assert update.notes == "Updated notes"
    assert update.date is None
    assert update.category is None


def test_income_update_validates_positive_amount():
    """Test IncomeUpdate validates positive amounts when provided"""
    with pytest.raises(ValidationError) as exc_info:
        IncomeUpdate(amount=Decimal("-100.00"))
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("amount",) for error in errors)


def test_income_update_validates_min_length():
    """Test IncomeUpdate validates min length when fields are provided"""
    with pytest.raises(ValidationError):
        IncomeUpdate(category="")


def test_income_response_includes_id_and_timestamps():
    """Test IncomeResponse includes id and timestamp fields"""
    response = IncomeResponse(
        id=1,
        date=date(2024, 1, 15),
        amount=Decimal("5000.00"),
        category="Salary",
        notes="Monthly salary",
        created_at=date(2024, 1, 15),
        updated_at=date(2024, 1, 15)
    )
    assert response.id == 1
    assert response.created_at == date(2024, 1, 15)
    assert response.updated_at == date(2024, 1, 15)
