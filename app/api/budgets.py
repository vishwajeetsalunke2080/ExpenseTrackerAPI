"""Budget API endpoints."""
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.budget_service import BudgetService
from app.schemas.budget import BudgetCreate, BudgetUpdate, BudgetResponse


router = APIRouter(prefix="/budgets", tags=["budgets"])


async def get_budget_service(
    db: AsyncSession = Depends(get_db)
) -> BudgetService:
    """Dependency injection for BudgetService.
    
    Args:
        db: Database session from dependency
        
    Returns:
        BudgetService instance
    """
    return BudgetService(db)


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_budget(
    budget: BudgetCreate,
    service: BudgetService = Depends(get_budget_service)
) -> BudgetResponse:
    """Create a new budget.
    
    Args:
        budget: Budget creation data
        service: Budget service instance
        
    Returns:
        Created budget with usage information
        
    Raises:
        HTTPException: 400 if overlapping budget exists, 422 if validation fails
        
    Requirements: 14.1, 14.2
    """
    try:
        return await service.create_budget(budget)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{budget_id}", response_model=BudgetResponse)
async def get_budget(
    budget_id: int,
    month: Optional[int] = None,
    year: Optional[int] = None,
    service: BudgetService = Depends(get_budget_service)
) -> BudgetResponse:
    """Retrieve a specific budget by ID with usage information for specified month.
    
    Args:
        budget_id: Budget ID to retrieve
        month: Optional month (1-12) to calculate usage for (defaults to current month)
        year: Optional year to calculate usage for (defaults to current year)
        service: Budget service instance
        
    Returns:
        Budget data with usage information for the specified month
        
    Raises:
        HTTPException: 404 if budget not found
        
    Requirements: 14.3, 15.1, 15.2, 15.3
    """
    budget = await service.get_budget(budget_id, month, year)
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget with id {budget_id} not found"
        )
    return budget


@router.get("", response_model=List[BudgetResponse])
async def list_budgets(
    category: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    service: BudgetService = Depends(get_budget_service)
) -> List[BudgetResponse]:
    """List budgets with optional filters and usage information for specified month.
    
    Filters:
    - category: Filter by specific category
    - month/year: Calculate usage for specific month (defaults to current month)
    
    Args:
        category: Optional category filter
        month: Optional month (1-12) to calculate usage for (defaults to current month)
        year: Optional year to calculate usage for (defaults to current year)
        service: Budget service instance
        
    Returns:
        List of budgets with usage information for the specified month
        
    Requirements: 14.3, 15.1, 15.2, 15.3
    """
    return await service.list_budgets(category, month, year)


@router.put("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: int,
    updates: BudgetUpdate,
    service: BudgetService = Depends(get_budget_service)
) -> BudgetResponse:
    """Update an existing budget.
    
    Args:
        budget_id: Budget ID to update
        updates: Budget update data
        service: Budget service instance
        
    Returns:
        Updated budget with recalculated usage
        
    Raises:
        HTTPException: 404 if budget not found, 422 if validation fails
        
    Requirements: 14.4
    """
    try:
        return await service.update_budget(budget_id, updates)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: int,
    service: BudgetService = Depends(get_budget_service)
) -> None:
    """Delete a budget.
    
    Args:
        budget_id: Budget ID to delete
        service: Budget service instance
        
    Raises:
        HTTPException: 404 if budget not found
        
    Requirements: 14.5
    """
    try:
        success = await service.delete_budget(budget_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Budget with id {budget_id} not found"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
