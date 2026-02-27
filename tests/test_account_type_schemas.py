"""Tests for AccountType Pydantic schemas"""
import pytest
from pydantic import ValidationError
from app.schemas.account_type import (
    AccountTypeBase,
    AccountTypeCreate,
    AccountTypeUpdate,
    AccountTypeResponse
)


def test_account_type_base_valid():
    """Test AccountTypeBase with valid data"""
    account = AccountTypeBase(name="Cash")
    assert account.name == "Cash"


def test_account_type_base_missing_name():
    """Test AccountTypeBase rejects missing name"""
    with pytest.raises(ValidationError) as exc_info:
        AccountTypeBase()
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("name",) for error in errors)


def test_account_type_base_empty_name():
    """Test AccountTypeBase rejects empty name"""
    with pytest.raises(ValidationError) as exc_info:
        AccountTypeBase(name="")
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("name",) for error in errors)


def test_account_type_base_name_max_length():
    """Test AccountTypeBase enforces max length of 100"""
    with pytest.raises(ValidationError):
        AccountTypeBase(name="A" * 101)


def test_account_type_create_inherits_base():
    """Test AccountTypeCreate inherits from AccountTypeBase"""
    account = AccountTypeCreate(name="Card")
    assert account.name == "Card"


def test_account_type_update_all_optional():
    """Test AccountTypeUpdate has all optional fields"""
    update = AccountTypeUpdate()
    assert update.name is None


def test_account_type_update_with_name():
    """Test AccountTypeUpdate with name provided"""
    update = AccountTypeUpdate(name="Updated Account")
    assert update.name == "Updated Account"


def test_account_type_update_validates_min_length():
    """Test AccountTypeUpdate validates min length when name is provided"""
    with pytest.raises(ValidationError):
        AccountTypeUpdate(name="")


def test_account_type_response_with_all_fields():
    """Test AccountTypeResponse includes id and is_default"""
    account = AccountTypeResponse(
        id=1,
        name="Cash",
        is_default=True
    )
    assert account.id == 1
    assert account.name == "Cash"
    assert account.is_default is True


def test_account_type_response_non_default():
    """Test AccountTypeResponse with non-default account"""
    account = AccountTypeResponse(
        id=2,
        name="Credit Card",
        is_default=False
    )
    assert account.id == 2
    assert account.name == "Credit Card"
    assert account.is_default is False
