"""Unit tests for account type API endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import AccountType


@pytest.mark.asyncio
async def test_create_account_type_success(test_client: AsyncClient):
    """Test successful account type creation."""
    account_data = {
        "name": "Bank Transfer"
    }
    
    response = await test_client.post("/accounts", json=account_data)
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Bank Transfer"
    assert data["is_default"] is False
    assert "id" in data


@pytest.mark.asyncio
async def test_create_account_type_duplicate_name(test_client: AsyncClient, test_db: AsyncSession):
    """Test account type creation with duplicate name."""
    # Create first account type
    account = AccountType(name="Cash", is_default=False)
    test_db.add(account)
    await test_db.commit()
    
    # Try to create duplicate
    account_data = {
        "name": "Cash"
    }
    
    response = await test_client.post("/accounts", json=account_data)
    
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_account_types(test_client: AsyncClient, test_db: AsyncSession):
    """Test listing all account types."""
    # Create test account types
    accounts = [
        AccountType(name="Cash", is_default=False),
        AccountType(name="Card", is_default=False),
        AccountType(name="UPI", is_default=False),
    ]
    for acc in accounts:
        test_db.add(acc)
    await test_db.commit()
    
    response = await test_client.get("/accounts")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    # Check ordering by name
    assert data[0]["name"] == "Card"
    assert data[1]["name"] == "Cash"
    assert data[2]["name"] == "UPI"


@pytest.mark.asyncio
async def test_list_account_types_empty(test_client: AsyncClient):
    """Test listing account types when none exist."""
    response = await test_client.get("/accounts")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0
    assert data == []


@pytest.mark.asyncio
async def test_update_account_type_success(test_client: AsyncClient, test_db: AsyncSession):
    """Test successful account type update."""
    # Create account type
    account = AccountType(name="Cash", is_default=False)
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)
    
    # Update account type
    update_data = {"name": "Cash Payment"}
    response = await test_client.put(f"/accounts/{account.id}", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Cash Payment"
    assert data["id"] == account.id


@pytest.mark.asyncio
async def test_update_account_type_not_found(test_client: AsyncClient):
    """Test updating non-existent account type."""
    update_data = {"name": "NewName"}
    response = await test_client.put("/accounts/999", json=update_data)
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_account_type_duplicate_name(test_client: AsyncClient, test_db: AsyncSession):
    """Test updating account type with duplicate name."""
    # Create two account types
    acc1 = AccountType(name="Cash", is_default=False)
    acc2 = AccountType(name="Card", is_default=False)
    test_db.add(acc1)
    test_db.add(acc2)
    await test_db.commit()
    await test_db.refresh(acc1)
    await test_db.refresh(acc2)
    
    # Try to update acc2 with acc1's name
    update_data = {"name": "Cash"}
    response = await test_client.put(f"/accounts/{acc2.id}", json=update_data)
    
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_account_type_success(test_client: AsyncClient, test_db: AsyncSession):
    """Test successful account type deletion."""
    # Create account type
    account = AccountType(name="Cash", is_default=False)
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)
    
    # Delete account type
    response = await test_client.delete(f"/accounts/{account.id}")
    
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_account_type_not_found(test_client: AsyncClient):
    """Test deleting non-existent account type."""
    response = await test_client.delete("/accounts/999")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_default_account_type(test_client: AsyncClient, test_db: AsyncSession):
    """Test deleting default account type should fail."""
    # Create default account type
    account = AccountType(name="Cash", is_default=True)
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)
    
    # Try to delete default account type
    response = await test_client.delete(f"/accounts/{account.id}")
    
    assert response.status_code == 404
    assert "default" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_account_type_validation_error(test_client: AsyncClient):
    """Test account type creation with invalid data."""
    # Missing required field
    account_data = {}
    
    response = await test_client.post("/accounts", json=account_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_account_type_empty_name(test_client: AsyncClient):
    """Test account type creation with empty name."""
    account_data = {
        "name": ""
    }
    
    response = await test_client.post("/accounts", json=account_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_account_type_name_too_long(test_client: AsyncClient):
    """Test account type creation with name exceeding max length."""
    account_data = {
        "name": "A" * 101  # Max length is 100
    }
    
    response = await test_client.post("/accounts", json=account_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_update_account_type_empty_name(test_client: AsyncClient, test_db: AsyncSession):
    """Test updating account type with empty name."""
    # Create account type
    account = AccountType(name="Cash", is_default=False)
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)
    
    # Try to update with empty name
    update_data = {"name": ""}
    response = await test_client.put(f"/accounts/{account.id}", json=update_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_account_type_persistence_after_creation(test_client: AsyncClient):
    """Test that created account type persists and can be retrieved."""
    # Create account type
    account_data = {"name": "Digital Wallet"}
    create_response = await test_client.post("/accounts", json=account_data)
    assert create_response.status_code == 201
    created_id = create_response.json()["id"]
    
    # List all account types and verify it exists
    list_response = await test_client.get("/accounts")
    assert list_response.status_code == 200
    account_types = list_response.json()
    
    # Find the created account type
    found = False
    for acc in account_types:
        if acc["id"] == created_id:
            found = True
            assert acc["name"] == "Digital Wallet"
            assert acc["is_default"] is False
            break
    
    assert found, "Created account type not found in list"


@pytest.mark.asyncio
async def test_account_type_update_persistence(test_client: AsyncClient, test_db: AsyncSession):
    """Test that updated account type persists correctly."""
    # Create account type
    account = AccountType(name="Cash", is_default=False)
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)
    
    # Update account type
    update_data = {"name": "Cash Payment"}
    update_response = await test_client.put(f"/accounts/{account.id}", json=update_data)
    assert update_response.status_code == 200
    
    # List all account types and verify the update persisted
    list_response = await test_client.get("/accounts")
    assert list_response.status_code == 200
    account_types = list_response.json()
    
    # Find the updated account type
    found = False
    for acc in account_types:
        if acc["id"] == account.id:
            found = True
            assert acc["name"] == "Cash Payment"
            break
    
    assert found, "Updated account type not found in list"


@pytest.mark.asyncio
async def test_account_type_deletion_removes_from_list(test_client: AsyncClient, test_db: AsyncSession):
    """Test that deleted account type is removed from list."""
    # Create account type
    account = AccountType(name="Cash", is_default=False)
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)
    account_id = account.id
    
    # Delete account type
    delete_response = await test_client.delete(f"/accounts/{account_id}")
    assert delete_response.status_code == 204
    
    # List all account types and verify it's gone
    list_response = await test_client.get("/accounts")
    assert list_response.status_code == 200
    account_types = list_response.json()
    
    # Verify the deleted account type is not in the list
    for acc in account_types:
        assert acc["id"] != account_id, "Deleted account type still appears in list"
