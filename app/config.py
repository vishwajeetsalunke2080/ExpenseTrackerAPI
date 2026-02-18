"""Application configuration using Pydantic settings."""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional
import os
from pathlib import Path

# Get the FastAPI directory (parent of app directory)
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = ConfigDict(
        env_file=str(ENV_FILE),
        case_sensitive=False,
        extra="ignore"
    )
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./expense_tracker.db"
    
    # Redis Cache
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_minutes: int = 15
    
    # Groq (LLM Provider)
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    
    # API
    api_title: str = "Expense Tracking API"
    api_version: str = "1.0.0"


# Global settings instance
settings = Settings()
