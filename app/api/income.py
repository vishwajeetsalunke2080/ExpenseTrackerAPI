"""Income API endpoints."""
from typing import Dict, Any, Optional, List
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from app.database import get_db
from app.services.income_service import IncomeService
from app.schemas.income import IncomeCreate, IncomeUpdate, IncomeResponse
from app.schemas.filter import ExpenseFilter
from app.middleware.auth import get_current_user
from app.models.user import User


router = APIRouter(prefix="/income", tags=["income"])


async def get_income_service(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> IncomeService:
    """Dependency injection for IncomeService.
    
    Args:
        db: Database session from dependency
        current_user: Authenticated user from dependency
        
    Returns:
        IncomeService instance
    """
    return IncomeService(db, current_user)


@router.post("", response_model=IncomeResponse, status_code=status.HTTP_201_CREATED)
async def create_income(
    income: IncomeCreate,
    service: IncomeService = Depends(get_income_service)
) -> IncomeResponse:
    """Create a new income record.
    
    Args:
        income: Income creation data
        service: Income service instance
        
    Returns:
        Created income
        
    Raises:
        HTTPException: 422 if validation fails
    """
    return await service.create_income(income)


@router.get("/{income_id}", response_model=IncomeResponse)
async def get_income(
    income_id: int,
    service: IncomeService = Depends(get_income_service)
) -> IncomeResponse:
    """Retrieve a specific income by ID.
    
    Args:
        income_id: Income ID to retrieve
        service: Income service instance
        
    Returns:
        Income data
        
    Raises:
        HTTPException: 404 if income not found or not owned
    """
    income = await service.get_income(income_id)
    if not income:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Income not found"
        )
    return income


@router.get("", response_model=Dict[str, Any])
async def list_income(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    categories: Optional[List[str]] = Query(None),
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    service: IncomeService = Depends(get_income_service)
) -> Dict[str, Any]:
    """List income records with filtering and pagination.
    
    Args:
        start_date: Filter by start date (inclusive)
        end_date: Filter by end date (inclusive)
        categories: Filter by categories (OR logic)
        min_amount: Filter by minimum amount (inclusive)
        max_amount: Filter by maximum amount (inclusive)
        page: Page number (minimum 1)
        page_size: Items per page (1-100)
        service: Income service instance
        
    Returns:
        Dictionary containing income list, total count, page, and page_size
        
    Raises:
        HTTPException: 422 if filter validation fails
    """
    # Create filter object with validation
    try:
        filters = ExpenseFilter(
            start_date=start_date,
            end_date=end_date,
            categories=categories,
            accounts=None,  # Income doesn't use accounts
            min_amount=min_amount,
            max_amount=max_amount,
            page=page,
            page_size=page_size
        )
    except (ValueError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    
    income_records, total = await service.list_income(filters)
    return {
        "income": income_records,
        "total": total,
        "page": filters.page,
        "page_size": filters.page_size
    }


@router.put("/{income_id}", response_model=IncomeResponse)
async def update_income(
    income_id: int,
    updates: IncomeUpdate,
    service: IncomeService = Depends(get_income_service)
) -> IncomeResponse:
    """Update an existing income record.
    
    Args:
        income_id: Income ID to update
        updates: Income update data
        service: Income service instance
        
    Returns:
        Updated income
        
    Raises:
        HTTPException: 404 if income not found or not owned
    """
    try:
        return await service.update_income(income_id, updates)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Income not found"
        )


@router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_income(
    income_id: int,
    service: IncomeService = Depends(get_income_service)
) -> None:
    """Delete an income record.
    
    Args:
        income_id: Income ID to delete
        service: Income service instance
        
    Raises:
        HTTPException: 404 if income not found or not owned
    """
    try:
        success = await service.delete_income(income_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Income not found"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Income not found"
        )
