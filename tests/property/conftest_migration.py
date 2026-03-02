"""Minimal conftest for migration property tests that don't need redis."""
import pytest
import os

# Set minimal test environment variables
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-min-32-characters-long"
os.environ["JWT_ALGORITHM"] = "HS256"
