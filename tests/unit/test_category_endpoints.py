"""Unit tests for category API endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Category, CategoryTypeEnum


@pytest.mark.asyncio
async def test_create_category_success(test_client: AsyncClient):
    """Test successful category creation."""
    category_data = {
        "name": "Entertainment",
        "type": "expense"
    }
    
    response = await test_client.post("/categories", json=category_data)
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Entertainment"
    assert data["type"] == "expense"
    assert data["is_default"] is False
    assert "id" in data


@pytest.mark.asyncio
async def test_create_category_duplicate_name(test_client: AsyncClient, test_db: AsyncSession):
    """Test category creation with duplicate name."""
    # Create first category
    category = Category(name="Food", type=CategoryTypeEnum.EXPENSE, is_default=False)
    test_db.add(category)
    await test_db.commit()
    
    # Try to create duplicate
    category_data = {
        "name": "Food",
        "type": "expense"
    }
    
    response = await test_client.post("/categories", json=category_data)
    
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_categories_all(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing all categories."""
    # Create test categories
    categories = [
        Category(name="Food", type=CategoryTypeEnum.EXPENSE, is_default=False),
        Category(name="Travel", type=CategoryTypeEnum.EXPENSE, is_default=False),
        Category(name="Salary", type=CategoryTypeEnum.INCOME, is_default=False),
    ]
    for cat in categories:
        test_db.add(cat)
    await test_db.commit()
    
    response = await test_client.get("/categories")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    # Check ordering by name
    assert data[0]["name"] == "Food"
    assert data[1]["name"] == "Salary"
    assert data[2]["name"] == "Travel"


@pytest.mark.asyncio
async def test_list_categories_filtered_by_type(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing categories filtered by type."""
    # Create test categories
    categories = [
        Category(name="Food", type=CategoryTypeEnum.EXPENSE, is_default=False),
        Category(name="Travel", type=CategoryTypeEnum.EXPENSE, is_default=False),
        Category(name="Salary", type=CategoryTypeEnum.INCOME, is_default=False),
    ]
    for cat in categories:
        test_db.add(cat)
    await test_db.commit()
    
    # Filter by expense type
    response = await test_client.get("/categories?type=expense")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(cat["type"] == "expense" for cat in data)
    
    # Filter by income type
    response = await test_client.get("/categories?type=income")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["type"] == "income"


@pytest.mark.asyncio
async def test_update_category_success(test_client: AsyncClient, test_db: AsyncSession):
    """Test successful category update."""
    # Create category
    category = Category(name="Food", type=CategoryTypeEnum.EXPENSE, is_default=False)
    test_db.add(category)
    await test_db.commit()
    await test_db.refresh(category)
    
    # Update category
    update_data = {"name": "Dining"}
    response = await test_client.put(f"/categories/{category.id}", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Dining"
    assert data["id"] == category.id


@pytest.mark.asyncio
async def test_update_category_not_found(test_client: AsyncClient):
    """Test updating non-existent category."""
    update_data = {"name": "NewName"}
    response = await test_client.put("/categories/999", json=update_data)
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_category_duplicate_name(test_client: AsyncClient, test_db: AsyncSession):
    """Test updating category with duplicate name."""
    # Create two categories
    cat1 = Category(name="Food", type=CategoryTypeEnum.EXPENSE, is_default=False)
    cat2 = Category(name="Travel", type=CategoryTypeEnum.EXPENSE, is_default=False)
    test_db.add(cat1)
    test_db.add(cat2)
    await test_db.commit()
    await test_db.refresh(cat1)
    await test_db.refresh(cat2)
    
    # Try to update cat2 with cat1's name
    update_data = {"name": "Food"}
    response = await test_client.put(f"/categories/{cat2.id}", json=update_data)
    
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_category_success(test_client: AsyncClient, test_db: AsyncSession):
    """Test successful category deletion."""
    # Create category
    category = Category(name="Food", type=CategoryTypeEnum.EXPENSE, is_default=False)
    test_db.add(category)
    await test_db.commit()
    await test_db.refresh(category)
    
    # Delete category
    response = await test_client.delete(f"/categories/{category.id}")
    
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_category_not_found(test_client: AsyncClient):
    """Test deleting non-existent category."""
    response = await test_client.delete("/categories/999")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_default_category(test_client: AsyncClient, test_db: AsyncSession):
    """Test deleting default category should fail."""
    # Create default category
    category = Category(name="Food", type=CategoryTypeEnum.EXPENSE, is_default=True)
    test_db.add(category)
    await test_db.commit()
    await test_db.refresh(category)
    
    # Try to delete default category
    response = await test_client.delete(f"/categories/{category.id}")
    
    assert response.status_code == 404
    assert "default" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_category_validation_error(test_client: AsyncClient):
    """Test category creation with invalid data."""
    # Missing required field
    category_data = {
        "name": "Entertainment"
        # Missing 'type' field
    }
    
    response = await test_client.post("/categories", json=category_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_category_empty_name(test_client: AsyncClient):
    """Test category creation with empty name."""
    category_data = {
        "name": "",
        "type": "expense"
    }
    
    response = await test_client.post("/categories", json=category_data)
    
    assert response.status_code == 422  # Validation error
