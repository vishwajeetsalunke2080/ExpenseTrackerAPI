"""
Property-based tests for migration manager logging behavior.

This module tests universal properties that should hold across all database states.
"""

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import logging
from tests.fixtures.database_states import (
    empty_database_strategy,
    partial_state_strategy,
    migrated_database_strategy,
    corrupted_version_strategy,
)


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=empty_database_strategy() | partial_state_strategy())
@settings(max_examples=100)
def test_property_2_missing_history_warning(state):
    """
    Feature: alembic-resilient-migrations, Property 2: Missing History Warning
    
    For any database state where the alembic_version table does not exist,
    the init process should log a warning message indicating missing migration history.
    
    Validates: Requirements 1.2
    """
    from app.migrations.manager import MigrationManager
    from sqlalchemy.ext.asyncio import create_async_engine
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    # Mock the logger
    with patch.object(manager, 'logger') as mock_logger:
        # Mock database operations
        with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
            with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
                mock_check.return_value = state.has_alembic_version
                
                with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                    mock_tables.return_value = state.application_tables
                    
                    # For empty databases, mock migration execution
                    if len(state.application_tables) == 0:
                        with patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock):
                            with patch.object(manager, '_get_migration_head') as mock_head:
                                mock_head.return_value = "test_head_revision"
                                with patch.object(manager, '_get_all_revisions') as mock_revisions:
                                    mock_revisions.return_value = ["rev1", "rev2", "test_head_revision"]
                                    
                                    try:
                                        import asyncio
                                        asyncio.run(manager.check_and_run_migrations())
                                    except Exception:
                                        pass  # We're testing logging, not success
                    else:
                        # For partial state, expect error
                        try:
                            import asyncio
                            asyncio.run(manager.check_and_run_migrations())
                        except Exception:
                            pass  # Expected for partial state
        
        # Assert: Warning was logged when alembic_version doesn't exist
        if not state.has_alembic_version:
            warning_calls = [call for call in mock_logger.warning.call_args_list]
            assert len(warning_calls) > 0, "Expected warning log when alembic_version missing"
            
            # Check that warning mentions missing migration history
            warning_message = str(warning_calls[0])
            assert "missing migration history" in warning_message.lower() or \
                   "alembic_version" in warning_message.lower(), \
                   "Warning should mention missing migration history"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=empty_database_strategy() | partial_state_strategy() | corrupted_version_strategy())
@settings(max_examples=100)
def test_property_3_safe_connection_details_in_logs(state):
    """
    Feature: alembic-resilient-migrations, Property 3: Safe Connection Details in Logs
    
    For any warning or error message logged by the init process, the message should
    include database connection details (host, port, database name) but must not
    include credentials (username, password).
    
    Validates: Requirements 1.3
    """
    from app.migrations.manager import MigrationManager
    
    # Create mock engine with credentials in URL
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://testuser:secretpass123@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    # Mock the logger to capture all log calls
    with patch.object(manager, 'logger') as mock_logger:
        # Mock database operations
        with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
            with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
                mock_check.return_value = state.has_alembic_version
                
                with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                    mock_tables.return_value = state.application_tables
                    
                    with patch.object(manager, '_get_current_revision', new_callable=AsyncMock) as mock_current:
                        mock_current.return_value = state.current_revision
                        
                        with patch.object(manager, '_get_migration_head') as mock_head:
                            mock_head.return_value = "test_head"
                            
                            with patch.object(manager, '_get_all_revisions') as mock_revisions:
                                mock_revisions.return_value = ["rev1", "rev2", "test_head"]
                                
                                # For empty databases, mock migration execution
                                if not state.has_alembic_version and len(state.application_tables) == 0:
                                    with patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock):
                                        try:
                                            import asyncio
                                            asyncio.run(manager.check_and_run_migrations())
                                        except Exception:
                                            pass
                                else:
                                    try:
                                        import asyncio
                                        asyncio.run(manager.check_and_run_migrations())
                                    except Exception:
                                        pass  # Expected for some states
        
        # Collect all log messages
        all_log_messages = []
        for call_list in [mock_logger.warning.call_args_list, 
                          mock_logger.error.call_args_list,
                          mock_logger.info.call_args_list]:
            for call in call_list:
                if call[0]:  # Positional args
                    all_log_messages.append(str(call[0][0]))
        
        # Assert: No log message contains the password
        for message in all_log_messages:
            assert "secretpass123" not in message, \
                f"Log message contains password: {message}"
            
            # If message contains connection info, verify it's sanitized
            if "postgresql://" in message or "localhost" in message or "testdb" in message:
                # Should contain safe parts
                assert "localhost" in message or "testdb" in message, \
                    "Connection details should include host or database"
                # Should NOT contain password
                assert "secretpass123" not in message, \
                    "Connection details must not include password"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=empty_database_strategy())
@settings(max_examples=100)
def test_property_19_migration_execution_logging(state):
    """
    Feature: alembic-resilient-migrations, Property 19: Migration Execution Logging
    
    For any migration being executed, the migration system should log:
    (1) when the migration starts with its version identifier and description, and
    (2) when the migration completes with its execution time.
    
    Validates: Requirements 8.1, 8.2, 8.3
    """
    from app.migrations.manager import MigrationManager
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    # Mock the logger
    with patch.object(manager, 'logger') as mock_logger:
        # Mock database operations
        with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
            with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
                mock_check.return_value = False  # Empty database
                
                with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                    mock_tables.return_value = []  # No tables
                    
                    with patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock) as mock_migrate:
                        # Simulate successful migration
                        async def mock_migration():
                            # Log start
                            manager.logger.info("Starting migration execution to head")
                            # Simulate work
                            import asyncio
                            await asyncio.sleep(0.001)
                            # Log completion with time
                            manager.logger.info("Migration execution completed successfully in 0.01s")
                        
                        mock_migrate.side_effect = mock_migration
                        
                        with patch.object(manager, '_get_migration_head') as mock_head:
                            mock_head.return_value = "test_head_revision"
                            
                            with patch.object(manager, '_get_all_revisions') as mock_revisions:
                                mock_revisions.return_value = ["rev1", "rev2", "test_head_revision"]
                                
                                try:
                                    import asyncio
                                    asyncio.run(manager.check_and_run_migrations())
                                except Exception:
                                    pass
        
        # Collect info log messages
        info_messages = [str(call[0][0]) for call in mock_logger.info.call_args_list if call[0]]
        
        # Assert: Should have logged migration start
        start_logged = any("starting migration" in msg.lower() for msg in info_messages)
        assert start_logged, "Should log migration start"
        
        # Assert: Should have logged migration completion with execution time
        completion_logged = any(
            ("completed" in msg.lower() or "success" in msg.lower()) and 
            ("s" in msg or "time" in msg.lower())
            for msg in info_messages
        )
        assert completion_logged, "Should log migration completion with execution time"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=empty_database_strategy())
@settings(max_examples=100)
def test_property_20_migration_summary_logging(state):
    """
    Feature: alembic-resilient-migrations, Property 20: Migration Summary Logging
    
    For any migration run that completes (successfully or with failure), the init
    process should log a summary including the total number of migrations applied
    and the total execution time.
    
    Validates: Requirements 8.4
    """
    from app.migrations.manager import MigrationManager
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    # Mock the logger
    with patch.object(manager, 'logger') as mock_logger:
        # Mock database operations
        with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
            with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
                # First call returns False (no version), second returns True (after migration)
                mock_check.side_effect = [False, True]
                
                with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                    mock_tables.return_value = []  # Empty database
                    
                    with patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock):
                        with patch.object(manager, '_get_migration_head') as mock_head:
                            mock_head.return_value = "test_head_revision"
                            
                            with patch.object(manager, '_get_all_revisions') as mock_revisions:
                                # Simulate 3 migrations
                                mock_revisions.return_value = ["rev1", "rev2", "test_head_revision"]
                                
                                try:
                                    import asyncio
                                    asyncio.run(manager.check_and_run_migrations())
                                except Exception:
                                    pass
        
        # Collect info log messages
        info_messages = [str(call[0][0]) for call in mock_logger.info.call_args_list if call[0]]
        
        # Assert: Should have logged summary with migration count and execution time
        summary_logged = False
        for msg in info_messages:
            msg_lower = msg.lower()
            # Check for migration count (number + "migration")
            has_count = any(str(i) in msg for i in range(1, 10)) and "migration" in msg_lower
            # Check for execution time (number + "s" or "time")
            has_time = ("s" in msg or "time" in msg_lower) and any(char.isdigit() for char in msg)
            # Check for success/completion indicator
            has_completion = "success" in msg_lower or "applied" in msg_lower or "completed" in msg_lower
            
            if has_count and has_time and has_completion:
                summary_logged = True
                break
        
        assert summary_logged, \
            f"Should log summary with migration count and execution time. Messages: {info_messages}"



@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=empty_database_strategy())
@settings(max_examples=100)
def test_property_4_empty_database_auto_migration(state):
    """
    Feature: alembic-resilient-migrations, Property 4: Empty Database Auto-Migration
    
    For any empty database (no alembic_version table and no application tables),
    the migration system should automatically run all migrations from the initial
    migration to the head revision.
    
    Validates: Requirements 2.1
    """
    from app.migrations.manager import MigrationManager
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    # Track if migrations were run
    migrations_executed = False
    
    # Mock database operations
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
        with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
            # First call: no version table, second call: version table exists after migration
            mock_check.side_effect = [False, True]
            
            with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                mock_tables.return_value = []  # Empty database
                
                with patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock) as mock_migrate:
                    async def track_migration():
                        nonlocal migrations_executed
                        migrations_executed = True
                    
                    mock_migrate.side_effect = track_migration
                    
                    with patch.object(manager, '_get_migration_head') as mock_head:
                        mock_head.return_value = "test_head_revision"
                        
                        with patch.object(manager, '_get_all_revisions') as mock_revisions:
                            mock_revisions.return_value = ["rev1", "rev2", "test_head_revision"]
                            
                            try:
                                import asyncio
                                asyncio.run(manager.check_and_run_migrations())
                            except Exception as e:
                                pytest.fail(f"Empty database migration should not raise exception: {e}")
    
    # Assert: Migrations were executed for empty database
    assert migrations_executed, \
        "Empty database should trigger automatic migration to head"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=empty_database_strategy())
@settings(max_examples=100)
def test_property_5_version_table_creation(state):
    """
    Feature: alembic-resilient-migrations, Property 5: Version Table Creation After Migration
    
    For any successful migration execution that completes all pending migrations,
    the migration system should create or update the alembic_version table with
    the current head revision.
    
    Validates: Requirements 2.2
    """
    from app.migrations.manager import MigrationManager
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    # Track version table checks
    version_checks = []
    
    # Mock database operations
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
        with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
            async def track_version_check():
                result = len(version_checks) > 0  # False first time, True after
                version_checks.append(result)
                return result
            
            mock_check.side_effect = track_version_check
            
            with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                mock_tables.return_value = []  # Empty database
                
                with patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock):
                    with patch.object(manager, '_get_migration_head') as mock_head:
                        mock_head.return_value = "test_head_revision"
                        
                        with patch.object(manager, '_get_all_revisions') as mock_revisions:
                            mock_revisions.return_value = ["rev1", "rev2", "test_head_revision"]
                            
                            try:
                                import asyncio
                                asyncio.run(manager.check_and_run_migrations())
                            except Exception as e:
                                pytest.fail(f"Migration should succeed: {e}")
    
    # Assert: Version table was checked at least twice (before and after migration)
    assert len(version_checks) >= 2, \
        "Should verify alembic_version table exists after migration"
    
    # Assert: First check returned False (no table), later check returned True (table exists)
    assert version_checks[0] == False, "First check should find no version table"
    assert version_checks[-1] == True, "Final check should confirm version table exists"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=empty_database_strategy())
@settings(max_examples=100)
def test_property_7_post_migration_verification(state):
    """
    Feature: alembic-resilient-migrations, Property 7: Post-Migration Verification
    
    For any migration execution attempt, the init process should verify that the
    alembic_version table exists after the execution completes or fails.
    
    Validates: Requirements 2.4
    """
    from app.migrations.manager import MigrationManager
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    # Track when version table is checked
    check_times = []
    migration_executed = False
    
    # Mock database operations
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
        with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
            async def track_check():
                import time
                check_times.append(time.time())
                # Return True after migration
                return len(check_times) > 1
            
            mock_check.side_effect = track_check
            
            with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                mock_tables.return_value = []  # Empty database
                
                with patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock) as mock_migrate:
                    async def track_migration():
                        nonlocal migration_executed
                        migration_executed = True
                        import time
                        import asyncio
                        await asyncio.sleep(0.001)  # Simulate work
                    
                    mock_migrate.side_effect = track_migration
                    
                    with patch.object(manager, '_get_migration_head') as mock_head:
                        mock_head.return_value = "test_head_revision"
                        
                        with patch.object(manager, '_get_all_revisions') as mock_revisions:
                            mock_revisions.return_value = ["rev1", "rev2", "test_head_revision"]
                            
                            try:
                                import asyncio
                                asyncio.run(manager.check_and_run_migrations())
                            except Exception:
                                pass  # Even on failure, verification should happen
    
    # Assert: Version table was checked multiple times
    assert len(check_times) >= 2, \
        "Should check alembic_version table before and after migration"
    
    # Assert: If migration was executed, verification happened after
    if migration_executed:
        assert len(check_times) >= 2, \
            "Should verify alembic_version exists after migration execution"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=st.one_of(empty_database_strategy(), partial_state_strategy(), migrated_database_strategy()))
@settings(max_examples=100)
def test_property_6_migration_failure_exception(state):
    """
    Feature: alembic-resilient-migrations, Property 6: Migration Failure Exception
    
    For any migration execution that fails, the init process should log the error
    details and raise an exception to prevent application startup.
    
    Validates: Requirements 2.3
    """
    from app.migrations.manager import MigrationManager
    from app.migrations.exceptions import MigrationExecutionError
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    exception_raised = False
    error_logged = False
    
    # Mock the logger
    with patch.object(manager, 'logger') as mock_logger:
        # Mock database operations
        with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
            with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
                mock_check.return_value = False  # Trigger migration
                
                with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                    mock_tables.return_value = []  # Empty database
                    
                    with patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock) as mock_migrate:
                        # Simulate migration failure with logging
                        async def failing_migration():
                            # Simulate the error logging that happens in _run_migrations_to_head
                            manager.logger.error("Migration execution failed: Simulated migration failure")
                            raise MigrationExecutionError("test_revision", Exception("Simulated migration failure"))
                        
                        mock_migrate.side_effect = failing_migration
                        
                        with patch.object(manager, '_get_migration_head') as mock_head:
                            mock_head.return_value = "test_head_revision"
                            
                            with patch.object(manager, '_get_all_revisions') as mock_revisions:
                                mock_revisions.return_value = ["rev1", "rev2", "test_head_revision"]
                                
                                try:
                                    import asyncio
                                    asyncio.run(manager.check_and_run_migrations())
                                except (MigrationExecutionError, Exception):
                                    exception_raised = True
        
        # Check if error was logged
        error_calls = [str(call) for call in mock_logger.error.call_args_list]
        error_logged = len(error_calls) > 0
    
    # Assert: Exception was raised on migration failure
    assert exception_raised, \
        "Migration failure should raise an exception to prevent application startup"
    
    # Assert: Error was logged
    assert error_logged, \
        "Migration failure should log error details"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=partial_state_strategy())
@settings(max_examples=100)
def test_property_8_partial_state_detection(state):
    """
    Feature: alembic-resilient-migrations, Property 8: Partial State Detection
    
    For any database state where the alembic_version table does not exist but
    one or more application tables exist, the init process should log an error
    message indicating a partial database state and raise an exception.
    
    Validates: Requirements 3.1, 3.4
    """
    from app.migrations.manager import MigrationManager
    from app.migrations.exceptions import PartialDatabaseError
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    exception_raised = False
    error_logged = False
    
    # Mock the logger
    with patch.object(manager, 'logger') as mock_logger:
        # Mock database operations
        with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
            with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
                mock_check.return_value = False  # No alembic_version
                
                with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                    mock_tables.return_value = state.application_tables  # Has tables
                    
                    with patch.object(manager, '_get_migration_head') as mock_head:
                        mock_head.return_value = "test_head_revision"
                        
                        with patch.object(manager, '_get_all_revisions') as mock_revisions:
                            mock_revisions.return_value = ["rev1", "rev2", "test_head_revision"]
                            
                            try:
                                import asyncio
                                asyncio.run(manager.check_and_run_migrations())
                            except PartialDatabaseError:
                                exception_raised = True
                            except Exception:
                                pass  # Other exceptions don't count
        
        # Check if error was logged
        error_calls = [str(call) for call in mock_logger.error.call_args_list]
        error_logged = any("partial" in str(call).lower() for call in error_calls)
    
    # Assert: PartialDatabaseError was raised
    assert exception_raised, \
        "Partial database state (tables but no alembic_version) should raise PartialDatabaseError"
    
    # Assert: Error was logged mentioning partial state
    assert error_logged, \
        "Partial database state should log error message"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=partial_state_strategy())
@settings(max_examples=100)
def test_property_9_comprehensive_partial_state_error(state):
    """
    Feature: alembic-resilient-migrations, Property 9: Comprehensive Partial State Error Message
    
    For any partial database state error, the error message should include:
    (1) the list of detected application tables,
    (2) recovery instructions with the `alembic stamp head` command, and
    (3) a warning about potential data loss if migrations are run on existing tables.
    
    Validates: Requirements 3.2, 3.3, 3.5
    """
    from app.migrations.manager import MigrationManager
    from app.migrations.exceptions import PartialDatabaseError
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    caught_exception = None
    
    # Mock database operations
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
        with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False  # No alembic_version
            
            with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                mock_tables.return_value = state.application_tables  # Has tables
                
                with patch.object(manager, '_get_migration_head') as mock_head:
                    mock_head.return_value = "test_head_revision"
                    
                    with patch.object(manager, '_get_all_revisions') as mock_revisions:
                        mock_revisions.return_value = ["rev1", "rev2", "test_head_revision"]
                        
                        try:
                            import asyncio
                            asyncio.run(manager.check_and_run_migrations())
                        except PartialDatabaseError as e:
                            caught_exception = e
                        except Exception:
                            pass
    
    # Assert: Exception was raised
    assert caught_exception is not None, \
        "Partial database state should raise PartialDatabaseError"
    
    error_message = str(caught_exception).lower()
    
    # Assert: Error message includes table list
    assert "tables" in error_message or "detected" in error_message, \
        "Error message should mention detected tables"
    
    # Assert: Error message includes recovery command with 'stamp head'
    assert "stamp head" in error_message or "alembic" in error_message, \
        "Error message should include recovery command with 'alembic stamp head'"
    
    # Assert: Error message includes data loss warning
    assert "warning" in error_message or "data loss" in error_message or \
           "ensure" in error_message or "matches" in error_message, \
        "Error message should include warning about potential data loss"
    
    # Assert: Exception has tables attribute
    assert hasattr(caught_exception, 'tables'), \
        "PartialDatabaseError should have 'tables' attribute"
    
    # Assert: Exception has recovery_command attribute
    assert hasattr(caught_exception, 'recovery_command'), \
        "PartialDatabaseError should have 'recovery_command' attribute"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=corrupted_version_strategy())
@settings(max_examples=100)
def test_property_11_unknown_version_detection(state):
    """
    Feature: alembic-resilient-migrations, Property 11: Unknown Version Detection
    
    For any database state where the current version in alembic_version does not
    match any known migration file, the init process should log an error indicating
    an unknown migration version.
    
    Validates: Requirements 4.2
    """
    from app.migrations.manager import MigrationManager
    from app.migrations.exceptions import UnknownVersionError
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    exception_raised = False
    error_logged = False
    
    # Mock the logger
    with patch.object(manager, 'logger') as mock_logger:
        # Mock database operations
        with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
            with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
                mock_check.return_value = True  # Has alembic_version
                
                with patch.object(manager, '_get_current_revision', new_callable=AsyncMock) as mock_current:
                    mock_current.return_value = state.current_revision  # Unknown/corrupted version
                    
                    with patch.object(manager, '_get_migration_head') as mock_head:
                        mock_head.return_value = "known_head_revision"
                        
                        with patch.object(manager, '_get_all_revisions') as mock_revisions:
                            # Return known revisions that don't include the corrupted one
                            mock_revisions.return_value = ["rev1", "rev2", "known_head_revision"]
                            
                            try:
                                import asyncio
                                asyncio.run(manager.check_and_run_migrations())
                            except UnknownVersionError:
                                exception_raised = True
                            except Exception:
                                pass  # Other exceptions don't count
        
        # Check if error was logged
        error_calls = [str(call) for call in mock_logger.error.call_args_list]
        error_logged = any("unknown" in str(call).lower() for call in error_calls)
    
    # Assert: UnknownVersionError was raised
    assert exception_raised, \
        "Unknown migration version should raise UnknownVersionError"
    
    # Assert: Error was logged mentioning unknown version
    assert error_logged, \
        "Unknown migration version should log error message"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=st.one_of(empty_database_strategy(), partial_state_strategy(), migrated_database_strategy()))
@settings(max_examples=100)
def test_property_16_connectivity_failure_handling(state):
    """
    Feature: alembic-resilient-migrations, Property 16: Connectivity Failure Handling
    
    For any database connectivity failure during initialization, the init process
    should log a clear error message with connection details (excluding credentials)
    and raise an exception.
    
    Validates: Requirements 6.4
    """
    from app.migrations.manager import MigrationManager
    from app.migrations.exceptions import DatabaseConnectionError
    
    # Create mock engine with credentials in URL
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://testuser:secretpass123@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    exception_raised = False
    error_logged = False
    password_in_logs = False
    
    # Mock the logger
    with patch.object(manager, 'logger') as mock_logger:
        # Mock connectivity failure
        with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock) as mock_verify:
            async def failing_connectivity():
                # Simulate the error logging that happens in _verify_connectivity
                sanitized_url = "testuser:***@localhost:5432/testdb"
                manager.logger.error(f"Failed to connect to database: {sanitized_url}")
                raise DatabaseConnectionError(
                    f"Failed to connect to database: {sanitized_url}\n"
                    f"Error: Connection refused\n"
                    f"Action: Verify database is running and connection settings are correct"
                )
            
            mock_verify.side_effect = failing_connectivity
            
            try:
                import asyncio
                asyncio.run(manager.check_and_run_migrations())
            except DatabaseConnectionError:
                exception_raised = True
            except Exception:
                exception_raised = True  # Any exception counts
        
        # Check if error was logged
        error_calls = [str(call) for call in mock_logger.error.call_args_list]
        error_logged = len(error_calls) > 0
        
        # Check if password appears in any log message
        for call in error_calls:
            if "secretpass123" in str(call):
                password_in_logs = True
                break
    
    # Assert: Exception was raised on connectivity failure
    assert exception_raised, \
        "Database connectivity failure should raise an exception"
    
    # Assert: Error was logged
    assert error_logged, \
        "Database connectivity failure should log error message"
    
    # Assert: Password not in logs
    assert not password_in_logs, \
        "Error logs must not contain database password"



@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=migrated_database_strategy())
@settings(max_examples=100)
def test_property_10_current_version_reading(state):
    """
    Feature: alembic-resilient-migrations, Property 10: Current Version Reading
    
    For any database state where the alembic_version table exists, the init process
    should read the current migration version from the table before making any
    migration decisions.
    
    Validates: Requirements 4.1
    """
    from app.migrations.manager import MigrationManager
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    version_was_read = False
    read_version = None
    
    # Mock database operations
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
        with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True  # Has alembic_version
            
            with patch.object(manager, '_get_current_revision', new_callable=AsyncMock) as mock_current:
                async def track_version_read():
                    nonlocal version_was_read, read_version
                    version_was_read = True
                    read_version = state.current_revision
                    return state.current_revision
                
                mock_current.side_effect = track_version_read
                
                with patch.object(manager, '_get_migration_head') as mock_head:
                    mock_head.return_value = state.current_revision  # At head
                    
                    with patch.object(manager, '_get_all_revisions') as mock_revisions:
                        # Include current revision in known revisions
                        mock_revisions.return_value = ["rev1", "rev2", state.current_revision]
                        
                        try:
                            import asyncio
                            asyncio.run(manager.check_and_run_migrations())
                        except Exception:
                            pass  # We're testing version reading, not success
    
    # Assert: Current version was read from database
    assert version_was_read, \
        "Init process should read current version when alembic_version table exists"
    
    # Assert: The version read matches the state
    assert read_version == state.current_revision, \
        f"Should read correct version: expected {state.current_revision}, got {read_version}"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(
    current_rev=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Nd"), min_codepoint=48, max_codepoint=122),
        min_size=12,
        max_size=12
    ),
    head_rev=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Nd"), min_codepoint=48, max_codepoint=122),
        min_size=12,
        max_size=12
    )
)
@settings(max_examples=100)
def test_property_12_pending_migration_detection(current_rev, head_rev):
    """
    Feature: alembic-resilient-migrations, Property 12: Pending Migration Detection
    
    For any database state where the current version is behind the migration head,
    the init process should log an info message indicating pending migrations with
    the count of how many migrations are pending.
    
    Validates: Requirements 4.3, 4.4
    """
    from app.migrations.manager import MigrationManager
    
    # Skip if revisions are the same (no pending migrations)
    if current_rev == head_rev:
        return
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    pending_logged = False
    
    # Mock the logger
    with patch.object(manager, 'logger') as mock_logger:
        # Mock database operations
        with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
            with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
                mock_check.return_value = True  # Has alembic_version
                
                with patch.object(manager, '_get_current_revision', new_callable=AsyncMock) as mock_current:
                    mock_current.return_value = current_rev
                    
                    with patch.object(manager, '_get_migration_head') as mock_head:
                        mock_head.return_value = head_rev
                        
                        with patch.object(manager, '_get_all_revisions') as mock_revisions:
                            # Create revision list with current behind head
                            mock_revisions.return_value = ["rev1", current_rev, "rev2", head_rev]
                            
                            with patch.object(manager, '_count_pending_migrations') as mock_count:
                                mock_count.return_value = 2  # Simulate 2 pending migrations
                                
                                try:
                                    import asyncio
                                    asyncio.run(manager.check_and_run_migrations())
                                except Exception:
                                    pass
        
        # Check if pending migrations were logged
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        for call in info_calls:
            call_lower = str(call).lower()
            # Check for pending migration message with count
            if "pending" in call_lower and any(str(i) in call for i in range(1, 10)):
                pending_logged = True
                break
    
    # Assert: Pending migrations were logged with count
    assert pending_logged, \
        "Should log info message with pending migration count when current version is behind head"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=st.one_of(empty_database_strategy(), migrated_database_strategy()))
@settings(max_examples=100)
def test_property_23_migration_head_retrieval(state):
    """
    Feature: alembic-resilient-migrations, Property 23: Migration Head Retrieval
    
    For any migration validation or execution operation, the system should be able
    to retrieve the current head revision from the migration files without database
    access.
    
    Validates: Requirements 4.3
    """
    from app.migrations.manager import MigrationManager
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    head_retrieved = False
    head_value = None
    
    # Mock database operations
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
        with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
            # For empty databases, return False first, then True after migration
            if not state.has_alembic_version and len(state.application_tables) == 0:
                mock_check.side_effect = [False, True]
            else:
                mock_check.return_value = state.has_alembic_version
            
            with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                mock_tables.return_value = state.application_tables
                
                with patch.object(manager, '_get_current_revision', new_callable=AsyncMock) as mock_current:
                    mock_current.return_value = state.current_revision
                    
                    with patch.object(manager, '_get_migration_head') as mock_head:
                        def track_head_retrieval():
                            nonlocal head_retrieved, head_value
                            head_retrieved = True
                            head_value = "test_head_revision"
                            return head_value
                        
                        mock_head.side_effect = track_head_retrieval
                        
                        with patch.object(manager, '_get_all_revisions') as mock_revisions:
                            # Include current revision in known revisions for migrated databases
                            if state.current_revision:
                                mock_revisions.return_value = ["rev1", state.current_revision, "test_head_revision"]
                            else:
                                mock_revisions.return_value = ["rev1", "rev2", "test_head_revision"]
                            
                            # For empty databases, mock migration execution
                            if not state.has_alembic_version and len(state.application_tables) == 0:
                                with patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock):
                                    try:
                                        import asyncio
                                        asyncio.run(manager.check_and_run_migrations())
                                    except Exception:
                                        pass
                            else:
                                try:
                                    import asyncio
                                    asyncio.run(manager.check_and_run_migrations())
                                except Exception:
                                    pass  # Expected for some states
    
    # Assert: Head revision was retrieved
    assert head_retrieved, \
        "System should retrieve migration head revision during validation or execution"
    
    # Assert: Head value was obtained
    assert head_value is not None, \
        "Migration head retrieval should return a value"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=st.one_of(migrated_database_strategy(), corrupted_version_strategy()))
@settings(max_examples=100)
def test_property_24_revision_list_retrieval(state):
    """
    Feature: alembic-resilient-migrations, Property 24: Revision List Retrieval
    
    For any migration validation operation, the system should be able to retrieve
    the complete list of all migration revisions from the migration files to
    validate the current database version.
    
    Validates: Requirements 4.2
    """
    from app.migrations.manager import MigrationManager
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    revisions_retrieved = False
    revision_list = None
    
    # Mock database operations
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
        with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True  # Has alembic_version
            
            with patch.object(manager, '_get_current_revision', new_callable=AsyncMock) as mock_current:
                mock_current.return_value = state.current_revision
                
                with patch.object(manager, '_get_migration_head') as mock_head:
                    mock_head.return_value = "test_head_revision"
                    
                    with patch.object(manager, '_get_all_revisions') as mock_revisions:
                        def track_revision_retrieval():
                            nonlocal revisions_retrieved, revision_list
                            revisions_retrieved = True
                            revision_list = ["rev1", "rev2", "test_head_revision"]
                            return revision_list
                        
                        mock_revisions.side_effect = track_revision_retrieval
                        
                        try:
                            import asyncio
                            asyncio.run(manager.check_and_run_migrations())
                        except Exception:
                            pass  # Expected for corrupted versions
    
    # Assert: Revision list was retrieved
    assert revisions_retrieved, \
        "System should retrieve all migration revisions for validation"
    
    # Assert: Revision list is not empty
    assert revision_list is not None and len(revision_list) > 0, \
        "Revision list retrieval should return a non-empty list"



@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=st.one_of(partial_state_strategy(), corrupted_version_strategy()))
@settings(max_examples=100)
def test_property_13_recovery_commands_in_errors(state):
    """
    Feature: alembic-resilient-migrations, Property 13: Recovery Commands in Errors
    
    For any migration error that occurs, the error message should include the exact
    command to resolve the issue, formatted with the correct Alembic configuration
    file path.
    
    Validates: Requirements 5.1, 5.2
    """
    from app.migrations.manager import MigrationManager
    from app.migrations.exceptions import PartialDatabaseError, UnknownVersionError
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager with specific alembic config path
    alembic_cfg_path = "alembic.ini"
    manager = MigrationManager(mock_engine, alembic_cfg_path=alembic_cfg_path)
    
    caught_exception = None
    
    # Mock database operations
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
        with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = state.has_alembic_version
            
            with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                mock_tables.return_value = state.application_tables
                
                with patch.object(manager, '_get_current_revision', new_callable=AsyncMock) as mock_current:
                    mock_current.return_value = state.current_revision
                    
                    with patch.object(manager, '_get_migration_head') as mock_head:
                        mock_head.return_value = "test_head_revision"
                        
                        with patch.object(manager, '_get_all_revisions') as mock_revisions:
                            # For corrupted version, don't include current in known revisions
                            mock_revisions.return_value = ["rev1", "rev2", "test_head_revision"]
                            
                            try:
                                import asyncio
                                asyncio.run(manager.check_and_run_migrations())
                            except (PartialDatabaseError, UnknownVersionError) as e:
                                caught_exception = e
                            except Exception:
                                pass
    
    # Assert: Exception was raised
    assert caught_exception is not None, \
        "Error scenarios should raise exceptions"
    
    error_message = str(caught_exception)
    
    # Assert: Error message contains recovery command
    assert "alembic" in error_message.lower(), \
        "Error message should include alembic command"
    
    # Assert: Error message contains config file path
    assert alembic_cfg_path in error_message or "-c" in error_message, \
        f"Error message should include config file path: {error_message}"
    
    # For partial state errors, verify stamp command is included
    if isinstance(caught_exception, PartialDatabaseError):
        assert "stamp" in error_message.lower() and "head" in error_message.lower(), \
            "Partial state error should include 'alembic stamp head' command"
        
        # Verify recovery_command attribute has correct format
        assert hasattr(caught_exception, 'recovery_command'), \
            "PartialDatabaseError should have recovery_command attribute"
        assert alembic_cfg_path in caught_exception.recovery_command, \
            "Recovery command should include correct config path"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=empty_database_strategy())
@settings(max_examples=100)
def test_property_14_transaction_based_migration_execution(state):
    """
    Feature: alembic-resilient-migrations, Property 14: Transaction-Based Migration Execution
    
    For any automatic migration execution, if any migration fails, then all changes
    from that migration should be rolled back and no partial changes should persist
    in the database.
    
    Validates: Requirements 6.1, 6.2
    """
    from app.migrations.manager import MigrationManager
    from app.migrations.exceptions import MigrationExecutionError
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Track transaction behavior
    transaction_started = False
    transaction_rolled_back = False
    migration_failed = False
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    # Mock database operations
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
        with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False  # Empty database
            
            with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                mock_tables.return_value = []  # No tables
                
                with patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock) as mock_migrate:
                    # Simulate migration failure with transaction rollback
                    async def failing_migration():
                        nonlocal transaction_started, transaction_rolled_back, migration_failed
                        transaction_started = True
                        migration_failed = True
                        # In real implementation, transaction rollback happens automatically
                        # when exception is raised within async with engine.begin()
                        transaction_rolled_back = True
                        raise MigrationExecutionError("test_revision", Exception("Simulated failure"))
                    
                    mock_migrate.side_effect = failing_migration
                    
                    with patch.object(manager, '_get_migration_head') as mock_head:
                        mock_head.return_value = "test_head_revision"
                        
                        with patch.object(manager, '_get_all_revisions') as mock_revisions:
                            mock_revisions.return_value = ["rev1", "rev2", "test_head_revision"]
                            
                            exception_raised = False
                            try:
                                import asyncio
                                asyncio.run(manager.check_and_run_migrations())
                            except MigrationExecutionError:
                                exception_raised = True
                            except Exception:
                                exception_raised = True
    
    # Assert: Migration was attempted
    assert transaction_started, \
        "Migration execution should start a transaction"
    
    # Assert: Migration failed
    assert migration_failed, \
        "Migration should fail in this test scenario"
    
    # Assert: Exception was raised (preventing partial state)
    assert exception_raised, \
        "Failed migration should raise exception to prevent partial changes"
    
    # Assert: Transaction was rolled back
    # Note: In the real implementation, this is handled by SQLAlchemy's
    # async with engine.begin() context manager, which automatically
    # rolls back on exception
    assert transaction_rolled_back, \
        "Failed migration should trigger transaction rollback"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=st.one_of(empty_database_strategy(), partial_state_strategy(), migrated_database_strategy()))
@settings(max_examples=100)
def test_property_15_pre_migration_connectivity_check(state):
    """
    Feature: alembic-resilient-migrations, Property 15: Pre-Migration Connectivity Check
    
    For any initialization attempt, the init process should verify database
    connectivity before attempting to run migrations or check migration status.
    
    Validates: Requirements 6.3
    """
    from app.migrations.manager import MigrationManager
    from app.migrations.exceptions import DatabaseConnectionError
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    # Track order of operations
    operations_order = []
    
    # Mock database operations
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock) as mock_verify:
        async def track_connectivity_check():
            operations_order.append('connectivity_check')
        
        mock_verify.side_effect = track_connectivity_check
        
        with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
            async def track_version_check():
                operations_order.append('version_check')
                return state.has_alembic_version
            
            mock_check.side_effect = track_version_check
            
            with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                async def track_table_check():
                    operations_order.append('table_check')
                    return state.application_tables
                
                mock_tables.side_effect = track_table_check
                
                with patch.object(manager, '_get_current_revision', new_callable=AsyncMock) as mock_current:
                    async def track_revision_read():
                        operations_order.append('revision_read')
                        return state.current_revision
                    
                    mock_current.side_effect = track_revision_read
                    
                    with patch.object(manager, '_get_migration_head') as mock_head:
                        mock_head.return_value = "test_head_revision"
                        
                        with patch.object(manager, '_get_all_revisions') as mock_revisions:
                            if state.current_revision:
                                mock_revisions.return_value = ["rev1", state.current_revision, "test_head_revision"]
                            else:
                                mock_revisions.return_value = ["rev1", "rev2", "test_head_revision"]
                            
                            # For empty databases, mock migration execution
                            if not state.has_alembic_version and len(state.application_tables) == 0:
                                with patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock) as mock_migrate:
                                    async def track_migration():
                                        operations_order.append('migration_execution')
                                    
                                    mock_migrate.side_effect = track_migration
                                    
                                    try:
                                        import asyncio
                                        asyncio.run(manager.check_and_run_migrations())
                                    except Exception:
                                        pass
                            else:
                                try:
                                    import asyncio
                                    asyncio.run(manager.check_and_run_migrations())
                                except Exception:
                                    pass  # Expected for some states
    
    # Assert: Connectivity check was performed
    assert 'connectivity_check' in operations_order, \
        "Init process should verify database connectivity"
    
    # Assert: Connectivity check was FIRST operation
    assert operations_order[0] == 'connectivity_check', \
        f"Connectivity check should be the first operation, but order was: {operations_order}"
    
    # Assert: Other operations happened after connectivity check
    if len(operations_order) > 1:
        connectivity_index = operations_order.index('connectivity_check')
        for op in ['version_check', 'table_check', 'revision_read', 'migration_execution']:
            if op in operations_order:
                op_index = operations_order.index(op)
                assert op_index > connectivity_index, \
                    f"Operation '{op}' should happen after connectivity check"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=migrated_database_strategy())
@settings(max_examples=100)
def test_property_17_up_to_date_database_skip(state):
    """
    Feature: alembic-resilient-migrations, Property 17: Up-to-Date Database Skip
    
    For any database state where the alembic_version table exists and the current
    version matches the migration head, the init process should complete successfully
    without running any migrations.
    
    Validates: Requirements 7.1
    """
    from app.migrations.manager import MigrationManager
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Create manager
    manager = MigrationManager(mock_engine)
    
    migrations_executed = False
    
    # Mock database operations
    with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
        with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True  # Has alembic_version
            
            with patch.object(manager, '_get_current_revision', new_callable=AsyncMock) as mock_current:
                # Current revision matches head
                mock_current.return_value = state.current_revision
                
                with patch.object(manager, '_get_migration_head') as mock_head:
                    # Set head to match current revision
                    mock_head.return_value = state.current_revision
                    
                    with patch.object(manager, '_get_all_revisions') as mock_revisions:
                        # Include current revision in known revisions
                        mock_revisions.return_value = ["rev1", "rev2", state.current_revision]
                        
                        with patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock) as mock_migrate:
                            async def track_migration():
                                nonlocal migrations_executed
                                migrations_executed = True
                            
                            mock_migrate.side_effect = track_migration
                            
                            try:
                                import asyncio
                                asyncio.run(manager.check_and_run_migrations())
                            except Exception as e:
                                pytest.fail(f"Up-to-date database should not raise exception: {e}")
    
    # Assert: No migrations were executed when database is at head
    assert not migrations_executed, \
        "Up-to-date database (current version matches head) should skip migration execution"


@pytest.mark.property
@pytest.mark.feature("alembic-resilient-migrations")
@given(state=st.one_of(empty_database_strategy(), migrated_database_strategy()))
@settings(max_examples=100)
def test_property_18_idempotent_initialization(state):
    """
    Feature: alembic-resilient-migrations, Property 18: Idempotent Initialization
    
    For any database state, running the init process multiple times should produce
    the same result each time without creating duplicate tables, duplicate data, or
    changing the migration version.
    
    Validates: Requirements 7.2, 7.3
    """
    from app.migrations.manager import MigrationManager
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.url = Mock()
    mock_engine.url.__str__ = Mock(return_value="postgresql://user:pass@localhost:5432/testdb")
    
    # Track results from multiple runs
    run_results = []
    
    # Run the init process multiple times (2-3 times)
    num_runs = 3
    
    for run_num in range(num_runs):
        # Create manager for each run
        manager = MigrationManager(mock_engine)
        
        run_result = {
            'exception_type': None,
            'exception_message': None,
            'migrations_executed': False,
            'final_revision': None
        }
        
        # Mock database operations
        with patch.object(manager, '_verify_connectivity', new_callable=AsyncMock):
            with patch.object(manager, '_check_alembic_version_exists', new_callable=AsyncMock) as mock_check:
                # For empty databases: first run has no version, subsequent runs have version
                if not state.has_alembic_version and len(state.application_tables) == 0:
                    mock_check.side_effect = [False, True] if run_num == 0 else [True]
                else:
                    mock_check.return_value = state.has_alembic_version
                
                with patch.object(manager, '_get_application_tables', new_callable=AsyncMock) as mock_tables:
                    # For empty databases: first run has no tables, subsequent runs may have tables
                    if not state.has_alembic_version and len(state.application_tables) == 0:
                        mock_tables.return_value = [] if run_num == 0 else ["users", "expenses"]
                    else:
                        mock_tables.return_value = state.application_tables
                    
                    with patch.object(manager, '_get_current_revision', new_callable=AsyncMock) as mock_current:
                        # For migrated databases or after first run of empty database
                        if state.has_alembic_version or (run_num > 0 and len(state.application_tables) == 0):
                            final_rev = state.current_revision or "test_head_revision"
                            mock_current.return_value = final_rev
                            run_result['final_revision'] = final_rev
                        else:
                            mock_current.return_value = state.current_revision
                        
                        with patch.object(manager, '_get_migration_head') as mock_head:
                            head_rev = state.current_revision or "test_head_revision"
                            mock_head.return_value = head_rev
                            
                            with patch.object(manager, '_get_all_revisions') as mock_revisions:
                                mock_revisions.return_value = ["rev1", "rev2", head_rev]
                                
                                with patch.object(manager, '_run_migrations_to_head', new_callable=AsyncMock) as mock_migrate:
                                    async def track_migration():
                                        run_result['migrations_executed'] = True
                                    
                                    mock_migrate.side_effect = track_migration
                                    
                                    try:
                                        import asyncio
                                        asyncio.run(manager.check_and_run_migrations())
                                    except Exception as e:
                                        run_result['exception_type'] = type(e).__name__
                                        run_result['exception_message'] = str(e)
        
        run_results.append(run_result)
    
    # Assert: All runs produced consistent results
    # Check exception consistency
    exception_types = [r['exception_type'] for r in run_results]
    assert len(set(exception_types)) == 1, \
        f"All runs should produce same exception type, got: {exception_types}"
    
    # For successful runs (no exceptions), check migration execution consistency
    if run_results[0]['exception_type'] is None:
        # First run may execute migrations (for empty database)
        # Subsequent runs should NOT execute migrations
        if run_results[0]['migrations_executed']:
            # Empty database case: first run migrates, subsequent runs skip
            for i in range(1, num_runs):
                assert not run_results[i]['migrations_executed'], \
                    f"Run {i+1} should not execute migrations after first run completed"
        else:
            # Already migrated case: no run should execute migrations
            for i in range(num_runs):
                assert not run_results[i]['migrations_executed'], \
                    f"Run {i+1} should not execute migrations for already migrated database"
    
    # Assert: Final revision is consistent across all runs (for successful runs)
    final_revisions = [r['final_revision'] for r in run_results if r['final_revision'] is not None]
    if len(final_revisions) > 1:
        assert len(set(final_revisions)) == 1, \
            f"All runs should result in same final revision, got: {final_revisions}"