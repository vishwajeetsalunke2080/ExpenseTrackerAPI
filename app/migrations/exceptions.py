"""
Custom exception classes for migration management.

This module defines exceptions for various migration error scenarios.
"""


class MigrationError(Exception):
    """Base exception for migration-related errors."""
    pass



class PartialDatabaseError(MigrationError):
    """
    Raised when database has tables but no migration history.
    
    This is a dangerous state that requires manual intervention to prevent
    data loss or migration failures.
    """
    
    def __init__(self, tables: list[str], recovery_command: str):
        self.tables = tables
        self.recovery_command = recovery_command
        message = (
            f"Database has {len(tables)} application tables but no migration history. "
            f"This is a partial database state that requires manual recovery.\n\n"
            f"Detected tables: {', '.join(tables)}\n\n"
            f"To recover, run: {recovery_command}\n\n"
            f"WARNING: This will mark all migrations as applied. "
            f"Ensure your database schema matches the current migration head."
        )
        super().__init__(message)



class UnknownVersionError(MigrationError):
    """
    Raised when the current migration version is not found in migration files.
    
    This indicates corruption or manual tampering with the alembic_version table.
    """
    
    def __init__(self, current_version: str, known_versions: list[str], recovery_command: str = None):
        self.current_version = current_version
        self.known_versions = known_versions
        self.recovery_command = recovery_command
        
        message = (
            f"Current migration version '{current_version}' is not found in migration files. "
            f"This indicates database corruption or manual tampering.\n\n"
            f"Known versions: {', '.join(known_versions[-5:]) if known_versions else 'none'}\n\n"
        )
        
        if recovery_command:
            message += (
                f"To recover, you can:\n"
                f"1. Restore the correct version: {recovery_command}\n"
                f"2. Or investigate and fix the alembic_version table manually\n\n"
            )
        else:
            message += "Manual intervention required.\n"
        
        super().__init__(message)



class MigrationExecutionError(MigrationError):
    """
    Raised when migration execution fails.
    
    Contains details about which migration failed and the underlying error.
    """
    
    def __init__(self, revision: str, original_error: Exception):
        self.revision = revision
        self.original_error = original_error
        message = (
            f"Migration to revision '{revision}' failed: {str(original_error)}\n\n"
            f"All changes have been rolled back. "
            f"Check the migration file and database state."
        )
        super().__init__(message)



class DatabaseConnectionError(MigrationError):
    """Raised when database connection fails during migration operations."""
    pass
