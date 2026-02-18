"""
Expense Tracking and Analytics API

A FastAPI-based web service for managing personal or business expenses with
full CRUD operations, advanced filtering, AI-powered analytics, and caching.
"""
from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging

# Load environment variables
load_dotenv()

# Import configuration
from app.config import settings
from app.database import init_db, AsyncSessionLocal, initialize_default_categories, initialize_default_account_types
from app.cache import close_redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for application startup and shutdown.
    
    Handles:
    - Database initialization and table creation
    - Default categories and account types initialization
    - Redis connection cleanup on shutdown
    """
    logger.info("Starting up Expense Tracking API...")
    
    # Initialize database tables
    try:
        await init_db()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Initialize default categories and account types
    try:
        async with AsyncSessionLocal() as session:
            await initialize_default_categories(session)
            await initialize_default_account_types(session)
        logger.info("Default categories and account types initialized")
    except Exception as e:
        logger.error(f"Failed to initialize defaults: {e}")
        raise
    
    logger.info("Startup complete")
    
    yield
    
    # Shutdown: cleanup resources
    logger.info("Shutting down...")
    try:
        await close_redis()
        logger.info("Redis connection closed")
    except Exception as e:
        logger.error(f"Error closing Redis connection: {e}")
    
    logger.info("Shutdown complete")


# Create FastAPI application with configuration from settings
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Expense Tracking and Analytics API with AI-powered insights",
    lifespan=lifespan
)


# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic validation errors (422).
    
    Returns field-level error details for better debugging.
    """
    field_errors = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"][1:]) if len(error["loc"]) > 1 else str(error["loc"][0])
        if field not in field_errors:
            field_errors[field] = []
        field_errors[field].append(error["msg"])
    
    logger.warning(f"Validation error on {request.url.path}: {field_errors}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "error_code": "VALIDATION_ERROR",
            "field_errors": field_errors
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle unexpected exceptions (500).
    
    Logs the full error for debugging while returning a generic message to users.
    """
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal error occurred",
            "error_code": "INTERNAL_ERROR"
        }
    )


# Include API routers
from app.api.categories import router as categories_router
from app.api.accounts import router as accounts_router
from app.api.expenses import router as expenses_router
from app.api.income import router as income_router
from app.api.budgets import router as budgets_router
from app.api.analytics import router as analytics_router
from app.api.balance_carryforward import router as balance_router

app.include_router(categories_router)
app.include_router(accounts_router)
app.include_router(expenses_router)
app.include_router(income_router)
app.include_router(budgets_router)
app.include_router(analytics_router)
app.include_router(balance_router)


@app.get("/", tags=["health"])
async def root():
    """Health check endpoint."""
    return {
        "message": "Expense Tracking API is running",
        "version": settings.api_version,
        "status": "healthy"
    }