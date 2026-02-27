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
    
    # Groq (LLM Provider)
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    
    # API
    api_title: str = "Expense Tracking API"
    api_version: str = "1.0.0"
    
    # Frontend Configuration
    frontend_url: str = "http://localhost:3000"
    
    # Email Service Configuration
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@yourapp.com"
    smtp_from_name: str = "Your App Name"
    
    # OAuth Configuration
    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/oauth/google/callback"
    
    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/auth/oauth/github/callback"
    
    # JWT Configuration (RS256 with RSA keys)
    jwt_algorithm: str = "RS256"
    jwt_private_key_path: str = "private_key.pem"
    jwt_public_key_path: str = "public_key.pem"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    
    @property
    def jwt_private_key(self) -> str:
        """Load RSA private key from file."""
        key_path = BASE_DIR / self.jwt_private_key_path
        if not key_path.exists():
            raise FileNotFoundError(
                f"JWT private key not found at {key_path}. "
                "Run 'python generate_rsa_keys.py' to generate keys."
            )
        with open(key_path, "r") as f:
            return f.read()
    
    @property
    def jwt_public_key(self) -> str:
        """Load RSA public key from file."""
        key_path = BASE_DIR / self.jwt_public_key_path
        if not key_path.exists():
            raise FileNotFoundError(
                f"JWT public key not found at {key_path}. "
                "Run 'python generate_rsa_keys.py' to generate keys."
            )
        with open(key_path, "r") as f:
            return f.read()


# Global settings instance
settings = Settings()
