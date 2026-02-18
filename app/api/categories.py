"""Category API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.category_service import CategoryService
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse, CategoryType


router = APIRouter(prefix="/categories", tags=["categories"])


async def get_category_service(db: AsyncSession = Depends(get_db)) -> CategoryService:
    """Dependency injection for CategoryService.
    
    Args:
        db: Database session from dependency
        
    Returns:
        CategoryService instance
    """
    return CategoryService(db)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category: CategoryCreate,
    service: CategoryService = Depends(get_category_service)
) -> CategoryResponse:
    """Create a new category.
    
    Args:
        category: Category creation data
        service: Category service instance
        
    Returns:
        Created category
        
    Raises:
        HTTPException: 400 if category name already exists
    """
    try:
        return await service.create_category(category)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("", response_model=List[CategoryResponse])
async def list_categories(
    type: Optional[CategoryType] = None,
    service: CategoryService = Depends(get_category_service)
) -> List[CategoryResponse]:
    """List all categories, optionally filtered by type.
    
    Args:
        type: Optional filter by category type (expense or income)
        service: Category service instance
        
    Returns:
        List of categories
    """
    return await service.list_categories(type)


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    updates: CategoryUpdate,
    service: CategoryService = Depends(get_category_service)
) -> CategoryResponse:
    """Update a category.
    
    Args:
        category_id: Category ID to update
        updates: Category update data
        service: Category service instance
        
    Returns:
        Updated category
        
    Raises:
        HTTPException: 404 if category not found, 400 if duplicate name
    """
    try:
        return await service.update_category(category_id, updates)
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


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    service: CategoryService = Depends(get_category_service)
) -> None:
    """Delete a category.
    
    Args:
        category_id: Category ID to delete
        service: Category service instance
        
    Raises:
        HTTPException: 404 if category not found or is default
    """
    try:
        await service.delete_category(category_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
