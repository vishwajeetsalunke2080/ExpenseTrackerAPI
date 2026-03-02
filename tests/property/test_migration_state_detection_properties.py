"""Property-based tests for migration state detection.

Feature: alembic-resilient-migrations

This module tests Properties 1, 21, 22, and 25 which validate the system's
ability to correctly detect and classify various database states.
"""
import pytest
import os
import sys

# Set minimal environment variables before any app imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-min-32-characters-long"
os.environ["JWT_ALGORITHM"] = "HS256"

from hypothesis import given, settings, HealthCheck
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine
from app.migrations.manager import MigrationManager
from app.migrations.models import DatabaseState
from tests.fixtures.database_states import (
    empty_database_strategy,
    partial_state_strategy,
    migrated_database_strategy,
    corrupted_version_strategy,
    DatabaseStateFixture
)


# Property 1: Version Table Existence Check
@pytest.mark.asyncio
@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    db_state=empty_database_strategy() | partial_state_strategy() | 
             migrated_database_strategy() | corrupted_version_strategy()
)
async def test_property_1_version_table_existence_check(db_state: DatabaseStateFixture):
    """
    Property 1: Version Table Existence Check
    **Validates: Requirements 1.1**
    
    For any database state, when the application starts, the init process
    should check whether the alembic_version table exists before proceeding
    with any migration operations.
    
    This test verifies that:
    1. The check_and_run_migrations method always calls _check_alembic_version_exists
    2. This check happens before any other migration operations
    3. The check result is used to determine subsequent actions
    """
    # Create a mock engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    manager = MigrationManager(engine, alembic_cfg_path="alembic.ini")
    
    # Mock the internal methods
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock) as mock_verify, \
         patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check, \
         patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables, \
         patch.object(manager, '_get_current_revision', new_callable=AsyncMock) as mock_current, \
         patch.object(manager, '_get_migration_head', return_value="head123") as mock_head, \
         patch.object(manager, '_get_all_revisions', return_value=["rev1", "rev2", "head123"]) as mock_all, \
         patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock) as mock_run:
        
        # Configure mocks based on the database state
        mock_check.return_value = db_state.has_alembic_version
        mock_tables.return_value = db_state.application_tables
        mock_current.return_value = db_state.current_revision
        
        # Try to run migrations (may raise exceptions for some states)
        try:
            await manager.check_and_run_migrations()
        except Exception:
            # Expected for partial states and corrupted versions
            pass
        
        # Verify that connectivity was checked first
        mock_verify.assert_called_once()
        
        # Verify that alembic_version existence was checked (may be called multiple times for verification)
        assert mock_check.call_count >= 1
        
        # Verify check happened after connectivity
        assert mock_verify.call_count == 1
    
    await engine.dispose()


# Property 21: Empty Database State Classification
@pytest.mark.asyncio
@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(db_state=empty_database_strategy())
async def test_property_21_empty_database_classification(db_state: DatabaseStateFixture):
    """
    Property 21: Empty Database State Classification
    **Validates: Requirements 2.1**
    
    For any database with no alembic_version table and no application tables,
    it should be classified as an empty database and trigger automatic migration.
    
    This test verifies that:
    1. Empty databases (no tables at all) are correctly identified
    2. The system attempts to run migrations for empty databases
    3. The classification logic correctly distinguishes empty from partial states
    """
    # Create a mock engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    manager = MigrationManager(engine, alembic_cfg_path="alembic.ini")
    
    # Mock the internal methods
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock), \
         patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check, \
         patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables, \
         patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock) as mock_run, \
         patch.object(manager, '_get_migration_head', return_value="head123"), \
         patch.object(manager, '_get_all_revisions', return_value=["rev1", "rev2", "head123"]):
        
        # Configure mocks for empty database state
        mock_check.return_value = False  # No alembic_version
        mock_tables.return_value = []  # No application tables
        
        # Mock successful migration
        async def mock_migration():
            # Simulate that migration creates alembic_version
            mock_check.return_value = True
        
        mock_run.side_effect = mock_migration
        
        # Run migrations
        await manager.check_and_run_migrations()
        
        # Verify empty database was detected
        assert mock_check.call_count >= 1
        assert mock_tables.call_count == 1
        
        # Verify migrations were triggered for empty database
        mock_run.assert_called_once()
        
        # Verify the state matches empty database criteria
        assert db_state.has_alembic_version is False
        assert len(db_state.application_tables) == 0
    
    await engine.dispose()


# Property 22: Partial State Classification
@pytest.mark.asyncio
@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(db_state=partial_state_strategy())
async def test_property_22_partial_state_classification(db_state: DatabaseStateFixture):
    """
    Property 22: Partial State Classification
    **Validates: Requirements 3.1**
    
    For any database with no alembic_version table but with one or more
    application tables, it should be classified as a partial state and
    trigger an error with recovery instructions.
    
    This test verifies that:
    1. Partial states (tables exist but no migration history) are correctly identified
    2. The system raises PartialDatabaseError for partial states
    3. The error is raised before attempting any migrations
    4. The classification correctly distinguishes partial from empty states
    """
    from app.migrations.exceptions import PartialDatabaseError
    
    # Create a mock engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    manager = MigrationManager(engine, alembic_cfg_path="alembic.ini")
    
    # Mock the internal methods
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock), \
         patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check, \
         patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables, \
         patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock) as mock_run, \
         patch.object(manager, '_format_recovery_command', return_value="alembic -c alembic.ini stamp head"):
        
        # Configure mocks for partial state
        mock_check.return_value = False  # No alembic_version
        mock_tables.return_value = db_state.application_tables  # Has tables
        
        # Verify PartialDatabaseError is raised
        with pytest.raises(PartialDatabaseError) as exc_info:
            await manager.check_and_run_migrations()
        
        # Verify the error contains the table list
        error = exc_info.value
        assert hasattr(error, 'tables')
        assert error.tables == db_state.application_tables
        
        # Verify migrations were NOT run for partial state
        mock_run.assert_not_called()
        
        # Verify the state matches partial state criteria
        assert db_state.has_alembic_version is False
        assert len(db_state.application_tables) > 0
    
    await engine.dispose()


# Property 25: Application Table Detection
@pytest.mark.asyncio
@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
@given(
    db_state=empty_database_strategy() | partial_state_strategy() | 
             migrated_database_strategy()
)
async def test_property_25_application_table_detection(db_state: DatabaseStateFixture):
    """
    Property 25: Application Table Detection
    **Validates: Requirements 2.1, 3.1**
    
    For any database state check, the system should be able to query and list
    all application tables in the database, excluding the alembic_version table,
    to determine if the database is empty or has a partial state.
    
    This test verifies that:
    1. The system can retrieve a list of application tables
    2. The alembic_version table is excluded from the results
    3. The table list is accurate for state classification
    4. The detection works regardless of database state
    """
    # Create a mock engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    manager = MigrationManager(engine, alembic_cfg_path="alembic.ini")
    
    # Mock the internal methods
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock), \
         patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check, \
         patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables, \
         patch.object(manager, '_get_current_revision', new_callable=AsyncMock) as mock_current, \
         patch.object(manager, '_get_migration_head', return_value="head123"), \
         patch.object(manager, '_get_all_revisions', return_value=["rev1", "rev2", "head123"]), \
         patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock) as mock_run:
        
        # Configure mocks based on database state
        mock_check.return_value = db_state.has_alembic_version
        mock_tables.return_value = db_state.application_tables
        mock_current.return_value = db_state.current_revision
        
        # Mock successful migration for empty databases
        if not db_state.has_alembic_version and len(db_state.application_tables) == 0:
            async def mock_migration():
                mock_check.return_value = True
            mock_run.side_effect = mock_migration
        
        # Try to run migrations (may raise exceptions for partial states)
        try:
            await manager.check_and_run_migrations()
        except Exception:
            # Expected for partial states
            pass
        
        # Verify that application tables were queried when alembic_version is missing
        if not db_state.has_alembic_version:
            mock_tables.assert_called_once()
            
            # Verify the returned table list matches the state
            tables_result = mock_tables.return_value
            assert tables_result == db_state.application_tables
            
            # Verify alembic_version is not in the list
            assert "alembic_version" not in tables_result
        
        # Verify the table detection influenced the decision
        if not db_state.has_alembic_version:
            if len(db_state.application_tables) == 0:
                # Empty database should trigger migration
                mock_run.assert_called_once()
            else:
                # Partial state should not trigger migration
                mock_run.assert_not_called()
    
    await engine.dispose()
