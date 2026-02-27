"""Tests for Category Pydantic schemas"""
import pytest
from pydantic import ValidationError
from app.schemas.category import (
    CategoryType,
    CategoryBase,
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse
)


def test_category_type_enum():
    """Test CategoryType enum has correct values"""
    assert CategoryType.EXPENSE == "expense"
    assert CategoryType.INCOME == "income"


def test_category_base_valid():
    """Test CategoryBase with valid data"""
    category = CategoryBase(
        name="Food",
        type=CategoryType.EXPENSE
    )
    assert category.name == "Food"
    assert category.type == CategoryType.EXPENSE


def test_category_base_missing_name():
    """Test CategoryBase rejects missing name"""
    with pytest.raises(ValidationError) as exc_info:
        CategoryBase(
            type=CategoryType.EXPENSE
        )
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("name",) for error in errors)


def test_category_base_empty_name():
    """Test CategoryBase rejects empty name"""
    with pytest.raises(ValidationError) as exc_info:
        CategoryBase(
            name="",
            type=CategoryType.EXPENSE
        )
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("name",) for error in errors)


def test_category_base_name_max_length():
    """Test CategoryBase enforces max length of 100"""
    with pytest.raises(ValidationError):
        CategoryBase(
            name="A" * 101,
            type=CategoryType.EXPENSE
        )


def test_category_base_invalid_type():
    """Test CategoryBase rejects invalid type"""
    with pytest.raises(ValidationError):
        CategoryBase(
            name="Food",
            type="invalid_type"
        )


def test_category_create_inherits_base():
    """Test CategoryCreate inherits from CategoryBase"""
    category = CategoryCreate(
        name="Travel",
        type=CategoryType.EXPENSE
    )
    assert category.name == "Travel"
    assert category.type == CategoryType.EXPENSE


def test_category_update_all_optional():
    """Test CategoryUpdate has all optional fields"""
    update = CategoryUpdate()
    assert update.name is None


def test_category_update_with_name():
    """Test CategoryUpdate with name provided"""
    update = CategoryUpdate(name="Updated Name")
    assert update.name == "Updated Name"


def test_category_update_validates_min_length():
    """Test CategoryUpdate validates min length when name is provided"""
    with pytest.raises(ValidationError):
        CategoryUpdate(name="")


def test_category_response_with_all_fields():
    """Test CategoryResponse includes id and is_default"""
    category = CategoryResponse(
        id=1,
        name="Food",
        type=CategoryType.EXPENSE,
        is_default=True
    )
    assert category.id == 1
    assert category.name == "Food"
    assert category.type == CategoryType.EXPENSE
    assert category.is_default is True


def test_category_response_income_type():
    """Test CategoryResponse with income type"""
    category = CategoryResponse(
        id=2,
        name="Salary",
        type=CategoryType.INCOME,
        is_default=False
    )
    assert category.id == 2
    assert category.name == "Salary"
    assert category.type == CategoryType.INCOME
    assert category.is_default is False
