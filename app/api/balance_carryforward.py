"""Balance carryforward API endpoints."""
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.balance_carryforward_service import BalanceCarryforwardService
from app.schemas.income import IncomeResponse


router = APIRouter(prefix="/balance", tags=["balance"])


async def get_carryforward_service(
    db: AsyncSession = Depends(get_db)
) -> BalanceCarryforwardService:
    """Dependency injection for BalanceCarryforwardService.
    
    Args:
        db: Database session from dependency
        
    Returns:
        BalanceCarryforwardService instance
    """
    return BalanceCarryforwardService(db)


@router.post("/carryforward", response_model=IncomeResponse, status_code=status.HTTP_201_CREATED)
async def carryforward_balance(
    from_month: int = Query(..., ge=1, le=12, description="Source month (1-12)"),
    from_year: int = Query(..., ge=2000, le=2100, description="Source year"),
    service: BalanceCarryforwardService = Depends(get_carryforward_service)
) -> IncomeResponse:
    """Carry forward balance from specified month to the next month as savings.
    
    Creates an income entry in the next month with the net balance (income - expenses)
    from the specified month.
    
    Args:
        from_month: Source month to calculate balance from (1-12)
        from_year: Source year
        service: Balance carryforward service instance
        
    Returns:
        Created income entry for the carryforward
        
    Raises:
        HTTPException: 400 if carryforward already exists or balance is negative
    """
    try:
        return await service.carryforward_balance(from_month, from_year)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/carryforward/auto", response_model=IncomeResponse, status_code=status.HTTP_201_CREATED)
async def auto_carryforward_previous_month(
    service: BalanceCarryforwardService = Depends(get_carryforward_service)
) -> IncomeResponse:
    """Automatically carry forward balance from previous month to current month.
    
    Calculates the net balance from the previous month and creates an income entry
    for the current month.
    
    Args:
        service: Balance carryforward service instance
        
    Returns:
        Created income entry for the carryforward
        
    Raises:
        HTTPException: 400 if carryforward already exists or balance is negative
    """
    try:
        return await service.auto_carryforward_previous_month()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/monthly-summary", response_model=Dict[str, Any])
async def get_monthly_balance(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2000, le=2100, description="Year"),
    service: BalanceCarryforwardService = Depends(get_carryforward_service)
) -> Dict[str, Any]:
    """Get monthly balance summary.
    
    Args:
        month: Month (1-12)
        year: Year
        service: Balance carryforward service instance
        
    Returns:
        Dictionary with balance information
    """
    balance = await service.calculate_monthly_balance(month, year)
    has_carryforward = await service.has_carryforward_for_month(month, year)
    
    # Calculate next month
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    has_next_carryforward = await service.has_carryforward_for_month(next_month, next_year)
    
    return {
        "month": month,
        "year": year,
        "net_balance": float(balance),
        "can_carryforward": balance > 0 and not has_next_carryforward,
        "already_carried_forward": has_next_carryforward
    }
