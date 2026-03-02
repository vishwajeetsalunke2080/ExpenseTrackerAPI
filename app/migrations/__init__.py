"""
Database migration management module.

This module provides resilient database migration handling that gracefully
manages missing or incomplete Alembic migration history.
"""

from app.migrations.exceptions import (
    MigrationError,
    PartialDatabaseError,
    UnknownVersionError,
    MigrationExecutionError,
    DatabaseConnectionError,
)
from app.migrations.models import DatabaseState, MigrationResult
from app.migrations.manager import MigrationManager

__all__ = [
    "MigrationError",
    "PartialDatabaseError",
    "UnknownVersionError",
    "MigrationExecutionError",
    "DatabaseConnectionError",
    "DatabaseState",
    "MigrationResult",
    "MigrationManager",
]
