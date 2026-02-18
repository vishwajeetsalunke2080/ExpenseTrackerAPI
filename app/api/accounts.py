"""Account type API endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.account_type_service import AccountTypeService
from app.schemas.account_type import AccountTypeCreate, AccountTypeUpdate, AccountTypeResponse


router = APIRouter(prefix="/accounts", tags=["accounts"])


async def get_account_service(db: AsyncSession = Depends(get_db)) -> AccountTypeService:
    """Dependency injection for AccountTypeService.
    
    Args:
        db: Database session from dependency
        
    Returns:
        AccountTypeService instance
    """
    return AccountTypeService(db)


@router.post("", response_model=AccountTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_account_type(
    account: AccountTypeCreate,
    service: AccountTypeService = Depends(get_account_service)
) -> AccountTypeResponse:
    """Create a new account type.
    
    Args:
        account: Account type creation data
        service: Account type service instance
        
    Returns:
        Created account type
        
    Raises:
        HTTPException: 400 if account type name already exists
    """
    try:
        return await service.create_account_type(account)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("", response_model=List[AccountTypeResponse])
async def list_account_types(
    service: AccountTypeService = Depends(get_account_service)
) -> List[AccountTypeResponse]:
    """List all account types.
    
    Args:
        service: Account type service instance
        
    Returns:
        List of account types ordered by name
    """
    return await service.list_account_types()


@router.put("/{account_id}", response_model=AccountTypeResponse)
async def update_account_type(
    account_id: int,
    updates: AccountTypeUpdate,
    service: AccountTypeService = Depends(get_account_service)
) -> AccountTypeResponse:
    """Update an account type.
    
    Args:
        account_id: Account type ID to update
        updates: Account type update data
        service: Account type service instance
        
    Returns:
        Updated account type
        
    Raises:
        HTTPException: 404 if account type not found, 400 if duplicate name
    """
    try:
        return await service.update_account_type(account_id, updates)
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account_type(
    account_id: int,
    service: AccountTypeService = Depends(get_account_service)
) -> None:
    """Delete an account type.
    
    Args:
        account_id: Account type ID to delete
        service: Account type service instance
        
    Raises:
        HTTPException: 404 if account type not found or is default
    """
    try:
        await service.delete_account_type(account_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
