"""Health check endpoints."""
from fastapi import APIRouter, status
from typing import Dict, Any
from datetime import datetime, timezone

from app.database import check_db_health

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=Dict[str, Any])
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint.
    
    Returns:
        Dictionary with health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "expense-api"
    }


@router.get("/db", response_model=Dict[str, Any])
async def database_health_check() -> Dict[str, Any]:
    """Database health check endpoint.
    
    Returns:
        Dictionary with database health status
    """
    db_healthy = await check_db_health()
    
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
