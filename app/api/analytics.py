"""Analytics API endpoints."""
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from groq import AsyncGroq

from app.database import get_db
from app.config import settings
from app.services.analytics_engine import AnalyticsEngine
from app.services.expense_service import ExpenseService
from app.services.income_service import IncomeService
from app.middleware.auth import get_current_user
from app.models.user import User


router = APIRouter(prefix="/analytics", tags=["analytics"])


async def get_analytics_engine(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AnalyticsEngine:
    """Dependency injection for AnalyticsEngine.
    
    Args:
        db: Database session from dependency
        current_user: Authenticated user from dependency
        
    Returns:
        AnalyticsEngine instance
    """
    # Initialize Groq client
    groq_client = AsyncGroq(api_key=settings.groq_api_key)
    
    # Initialize services with user context
    expense_service = ExpenseService(db, current_user)
    income_service = IncomeService(db, current_user)
    
    return AnalyticsEngine(groq_client, expense_service, income_service, current_user, model=settings.groq_model)


@router.post("/query", response_model=Dict[str, Any])
async def natural_language_query(
    query: str = Query(..., min_length=5, description="Natural language query about spending patterns"),
    analytics: AnalyticsEngine = Depends(get_analytics_engine)
) -> Dict[str, Any]:
    """Process natural language analytics query.
    
    Args:
        query: Natural language query string (minimum 5 characters)
        analytics: Analytics engine instance
        
    Returns:
        Dictionary containing query results with formatted analytics data
        
    Raises:
        HTTPException: 400 if query cannot be parsed or understood
    """
    try:
        return await analytics.process_query(query)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
