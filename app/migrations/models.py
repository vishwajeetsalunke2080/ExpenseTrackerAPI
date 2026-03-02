"""
Data models for migration management.

This module defines dataclasses that represent database states and migration results.
"""

from dataclasses import dataclass, field


@dataclass
class DatabaseState:
    """Represents the current state of the database."""
    
    has_alembic_version: bool
    current_revision: str | None
    head_revision: str
    application_tables: list[str]
    pending_migrations: int
    
    @property
    def is_empty(self) -> bool:
        """Database has no tables at all."""
        return not self.has_alembic_version and len(self.application_tables) == 0
    
    @property
    def is_partial_state(self) -> bool:
        """Database has tables but no migration history (dangerous)."""
        return not self.has_alembic_version and len(self.application_tables) > 0
    
    @property
    def is_up_to_date(self) -> bool:
        """Database is fully migrated to head."""
        return (
            self.has_alembic_version and
            self.current_revision == self.head_revision
        )
    
    @property
    def needs_migration(self) -> bool:
        """Database needs migrations to reach head."""
        return (
            self.has_alembic_version and
            self.current_revision != self.head_revision and
            self.pending_migrations > 0
        )


@dataclass
class MigrationResult:
    """Result of a migration operation."""
    
    success: bool
    migrations_applied: int
    execution_time: float
    final_revision: str
    errors: list[str] = field(default_factory=list)
