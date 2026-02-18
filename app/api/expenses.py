"""Expense API endpoints."""
from typing import Dict, Any, Optional, List
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from app.database import get_db
from app.cache import get_redis
from app.services.expense_service import ExpenseService
from app.services.cache_service import CacheService
from app.schemas.expense import ExpenseCreate, ExpenseUpdate, ExpenseResponse
from app.schemas.filter import ExpenseFilter


router = APIRouter(prefix="/expenses", tags=["expenses"])


async def get_expense_service(
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
) -> ExpenseService:
    """Dependency injection for ExpenseService.
    
    Args:
        db: Database session from dependency
        redis_client: Redis client from dependency
        
    Returns:
        ExpenseService instance
    """
    cache_service = CacheService(redis_client)
    return ExpenseService(db, cache_service)


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    expense: ExpenseCreate,
    service: ExpenseService = Depends(get_expense_service)
) -> ExpenseResponse:
    """Create a new expense.
    
    Args:
        expense: Expense creation data
        service: Expense service instance
        
    Returns:
        Created expense
        
    Raises:
        HTTPException: 422 if validation fails
    """
    return await service.create_expense(expense)


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: int,
    service: ExpenseService = Depends(get_expense_service)
) -> ExpenseResponse:
    """Retrieve a specific expense by ID.
    
    Args:
        expense_id: Expense ID to retrieve
        service: Expense service instance
        
    Returns:
        Expense data
        
    Raises:
        HTTPException: 404 if expense not found
    """
    expense = await service.get_expense(expense_id)
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense with id {expense_id} not found"
        )
    return expense


@router.get("", response_model=Dict[str, Any])
async def list_expenses(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    categories: Optional[List[str]] = Query(None),
    accounts: Optional[List[str]] = Query(None),
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    service: ExpenseService = Depends(get_expense_service)
) -> Dict[str, Any]:
    """List expenses with filtering and pagination.
    
    Args:
        start_date: Filter by start date (inclusive)
        end_date: Filter by end date (inclusive)
        categories: Filter by categories (OR logic)
        accounts: Filter by accounts (OR logic)
        min_amount: Filter by minimum amount (inclusive)
        max_amount: Filter by maximum amount (inclusive)
        page: Page number (minimum 1)
        page_size: Items per page (1-100)
        service: Expense service instance
        
    Returns:
        Dictionary containing expenses list, total count, page, and page_size
        
    Raises:
        HTTPException: 422 if filter validation fails
    """
    # Create filter object with validation
    try:
        filters = ExpenseFilter(
            start_date=start_date,
            end_date=end_date,
            categories=categories,
            accounts=accounts,
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
    
    expenses, total = await service.list_expenses(filters)
    return {
        "expenses": expenses,
        "total": total,
        "page": filters.page,
        "page_size": filters.page_size
    }


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: int,
    updates: ExpenseUpdate,
    service: ExpenseService = Depends(get_expense_service)
) -> ExpenseResponse:
    """Update an existing expense.
    
    Args:
        expense_id: Expense ID to update
        updates: Expense update data
        service: Expense service instance
        
    Returns:
        Updated expense
        
    Raises:
        HTTPException: 404 if expense not found, 422 if validation fails
    """
    try:
        return await service.update_expense(expense_id, updates)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: int,
    service: ExpenseService = Depends(get_expense_service)
) -> None:
    """Delete an expense.
    
    Args:
        expense_id: Expense ID to delete
        service: Expense service instance
        
    Raises:
        HTTPException: 404 if expense not found
    """
    try:
        success = await service.delete_expense(expense_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Expense with id {expense_id} not found"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
