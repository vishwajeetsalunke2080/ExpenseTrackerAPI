"""
Expense Tracking and Analytics API

A FastAPI-based web service for managing personal or business expenses with
full CRUD operations, advanced filtering, and AI-powered analytics.
"""
from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

# Load environment variables
load_dotenv()

# Import configuration
from app.config import settings
from app.database import init_db, AsyncSessionLocal, initialize_default_categories, initialize_default_account_types

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
    """
    logger.info("Starting up Expense Tracking API...")
    logger.info(f"Database URL: {settings.database_url[:50]}...")  # Log first 50 chars for security
    
    # Initialize database tables
    try:
        await init_db()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Default categories and account types are now created per-user during signup
    # No longer initializing system-wide defaults at startup
    logger.info("Skipping system-wide default initialization (user-specific defaults created at signup)")
    
    logger.info("Startup complete")
    
    yield
    
    # Shutdown: cleanup resources
    logger.info("Shutting down...")
    logger.info("Shutdown complete")


# Create FastAPI application with configuration from settings
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Expense Tracking and Analytics API with AI-powered insights",
    lifespan=lifespan
)


# Configure CORS middleware for authentication endpoints
# Requirements: 6.1, 6.2, 6.3, 6.4
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],  # Frontend origins
    allow_credentials=True,  # Allow cookies for token storage
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers including Authorization
    expose_headers=["*"]  # Expose all headers to frontend
)


# Add authentication middleware for route protection
# Requirements: 6.1, 6.2, 6.3, 6.4, 6.6
from app.middleware.auth import AuthMiddleware

app.add_middleware(
    AuthMiddleware,
    public_paths=[
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/auth/signup",
        "/auth/signin",
        "/auth/oauth/.*",
        "/auth/forgot-password",
        "/auth/reset-password",
        "/auth/verify-email",
        "/auth/resend-verification",
        "/auth/refresh"
    ]
)


# Global exception handlers
from app.exceptions.auth_exceptions import (
    AuthException,
    InvalidCredentialsError,
    EmailNotVerifiedError,
    TokenExpiredError,
    TokenInvalidError,
    AccountLockedError,
    RateLimitError,
    ValidationError as AuthValidationError,
    UserNotFoundError,
    DuplicateEmailError,
    TokenRevokedError,
    PasswordStrengthError,
    OAuthProviderError
)


@app.exception_handler(AuthException)
async def auth_exception_handler(request: Request, exc: AuthException):
    """
    Handle all authentication-related exceptions.
    
    Returns consistent JSON error responses with detail, error_code, and timestamp.
    Logs all exceptions with full context for debugging and security monitoring.
    """
    # Log with appropriate level based on status code
    log_message = f"Auth error on {request.url.path}: {exc.error_code} - {exc.message}"
    
    if exc.status_code >= 500:
        logger.error(log_message, exc_info=True)
    elif exc.status_code == 429:  # Rate limit
        logger.warning(log_message)
    elif exc.status_code in (401, 403):  # Unauthorized/Forbidden
        logger.info(log_message)
    else:
        logger.warning(log_message)
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


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
from app.api.auth import router as auth_router
from app.api.oauth import router as oauth_router
from app.api.users import router as users_router
from app.api.categories import router as categories_router
from app.api.accounts import router as accounts_router
from app.api.expenses import router as expenses_router
from app.api.income import router as income_router
from app.api.budgets import router as budgets_router
from app.api.analytics import router as analytics_router
from app.api.balance_carryforward import router as balance_router

app.include_router(auth_router)
app.include_router(oauth_router)
app.include_router(users_router)
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