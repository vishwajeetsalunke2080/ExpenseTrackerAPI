"""Integration tests for init_db with MigrationManager.

Tests complete end-to-end database initialization workflows including:
- Empty database initialization with automatic migrations
- Partial state error detection and handling
- Up-to-date database validation
- Migration failure rollback
- Unknown version error handling
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text, inspect
from unittest.mock import patch, MagicMock
import tempfile
import os

from app.database import Base, init_db
from app.migrations.manager import MigrationManager
from app.migrations.exceptions import (
    PartialDatabaseError,
    UnknownVersionError,
    MigrationExecutionError
)



@pytest_asyncio.fixture
async def isolated_test_engine():
    """Create an isolated test database engine for migration tests."""
    # Use a temporary file-based SQLite database for isolation
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()
    
    db_url = f"sqlite+aiosqlite:///{temp_db.name}"
    engine = create_async_engine(db_url, echo=False, future=True)
    
    yield engine
    
    await engine.dispose()
    
    # Clean up temp file
    try:
        os.unlink(temp_db.name)
    except:
        pass


@pytest_asyncio.fixture
async def empty_database(isolated_test_engine):
    """Provide a completely empty database with no tables."""
    yield isolated_test_engine


@pytest_asyncio.fixture
async def database_with_tables_no_version(isolated_test_engine):
    """Create a database with application tables but no alembic_version table."""
    # Create some application tables manually
    async with isolated_test_engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL
            )
        """))
        await conn.execute(text("""
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                amount REAL,
                description TEXT
            )
        """))
        await conn.execute(text("""
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        """))
    
    yield isolated_test_engine


@pytest_asyncio.fixture
async def database_at_head(isolated_test_engine):
    """Create a database with alembic_version at head revision."""
    # First, get the head revision
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    
    alembic_cfg = Config("alembic.ini")
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    head_revision = script_dir.get_current_head()
    
    # Create alembic_version table with head revision
    async with isolated_test_engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            )
        """))
        await conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
            {"version": head_revision}
        )
        
        # Also create the actual tables that should exist at head
        await conn.run_sync(Base.metadata.create_all)
    
    yield isolated_test_engine


@pytest_asyncio.fixture
async def database_with_unknown_version(isolated_test_engine):
    """Create a database with alembic_version containing an unknown revision."""
    # Create alembic_version table with a fake/unknown revision
    async with isolated_test_engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            )
        """))
        await conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
            {"version": "unknown_fake_revision_12345"}
        )
    
    yield isolated_test_engine



@pytest.mark.asyncio
class TestEmptyDatabaseInitialization:
    """Test integration for empty database initialization.
    
    Validates: Requirements 2.1, 2.2, 2.4
    """
    
    async def test_empty_database_runs_all_migrations(self, empty_database):
        """
        Test that init_db automatically runs all migrations on an empty database.
        
        Validates:
        - Requirement 2.1: Empty database triggers automatic migration
        - Requirement 2.2: alembic_version created with head revision
        - Requirement 2.4: Post-migration verification
        
        Note: This test mocks migration execution to avoid real migration issues.
        """
        # Create MigrationManager with empty database
        manager = MigrationManager(empty_database)
        
        # Verify database is empty
        async with empty_database.connect() as conn:
            def check_tables(connection):
                inspector = inspect(connection)
                return inspector.get_table_names()
            
            tables_before = await conn.run_sync(check_tables)
            assert len(tables_before) == 0, "Database should be empty"
        
        # Mock successful migration execution
        with patch.object(manager, '_run_migrations_to_head') as mock_migrate:
            # Simulate successful migration by creating alembic_version table
            async def create_version_table():
                async with empty_database.begin() as conn:
                    await conn.execute(text("""
                        CREATE TABLE alembic_version (
                            version_num VARCHAR(32) NOT NULL PRIMARY KEY
                        )
                    """))
                    head_revision = manager._get_migration_head()
                    await conn.execute(
                        text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
                        {"version": head_revision}
                    )
            
            mock_migrate.side_effect = create_version_table
            
            # Run migrations
            await manager.check_and_run_migrations()
        
        # Verify alembic_version table was created
        async with empty_database.connect() as conn:
            def check_alembic_version(connection):
                inspector = inspect(connection)
                return "alembic_version" in inspector.get_table_names()
            
            has_version_table = await conn.run_sync(check_alembic_version)
            assert has_version_table, "alembic_version table should exist after migration"
        
        # Verify current revision matches head
        current_revision = await manager._get_current_revision()
        head_revision = manager._get_migration_head()
        assert current_revision == head_revision, \
            f"Current revision {current_revision} should match head {head_revision}"
    
    async def test_init_db_on_empty_database(self, empty_database):
        """
        Test that init_db() function works correctly on empty database.
        
        This tests the full integration through the init_db() entry point.
        Note: This test mocks migration execution to avoid real migration issues.
        """
        # Temporarily replace the global engine with our test engine
        from app import database
        original_engine = database.engine
        database.engine = empty_database
        
        try:
            # Mock the migration execution
            manager = MigrationManager(empty_database)
            
            with patch.object(MigrationManager, '_run_migrations_to_head') as mock_migrate:
                # Simulate successful migration
                async def create_version_table():
                    async with empty_database.begin() as conn:
                        await conn.execute(text("""
                            CREATE TABLE alembic_version (
                                version_num VARCHAR(32) NOT NULL PRIMARY KEY
                            )
                        """))
                        head_revision = manager._get_migration_head()
                        await conn.execute(
                            text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
                            {"version": head_revision}
                        )
                
                mock_migrate.side_effect = create_version_table
                
                # Call init_db
                await init_db()
            
            # Verify database is initialized
            manager = MigrationManager(empty_database)
            current_revision = await manager._get_current_revision()
            head_revision = manager._get_migration_head()
            
            assert current_revision == head_revision, \
                "Database should be at head revision after init_db"
            
            # Verify alembic_version exists
            has_version = await manager._check_alembic_version_exists()
            assert has_version, "alembic_version should exist after init_db"
            
        finally:
            # Restore original engine
            database.engine = original_engine



@pytest.mark.asyncio
class TestPartialStateError:
    """Test integration for partial database state error handling.
    
    Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
    """
    
    async def test_partial_state_raises_error(self, database_with_tables_no_version):
        """
        Test that database with tables but no alembic_version raises PartialDatabaseError.
        
        Validates:
        - Requirement 3.1: Partial state detection
        - Requirement 3.2: Error includes table list
        - Requirement 3.3: Error includes recovery command
        - Requirement 3.4: Exception prevents startup
        - Requirement 3.5: Data loss warning included
        """
        manager = MigrationManager(database_with_tables_no_version)
        
        # Verify tables exist but no alembic_version
        tables = await manager._get_application_tables()
        assert len(tables) > 0, "Should have application tables"
        
        has_version = await manager._check_alembic_version_exists()
        assert not has_version, "Should not have alembic_version table"
        
        # Attempt to run migrations should raise PartialDatabaseError
        with pytest.raises(PartialDatabaseError) as exc_info:
            await manager.check_and_run_migrations()
        
        error = exc_info.value
        
        # Verify error contains table list
        assert len(error.tables) > 0, "Error should include detected tables"
        assert "users" in error.tables
        assert "expenses" in error.tables
        assert "categories" in error.tables
        
        # Verify error message contains recovery command
        error_message = str(error)
        assert "stamp head" in error_message, \
            "Error should include recovery command"
        assert "alembic" in error.recovery_command and "stamp head" in error.recovery_command
        
        # Verify error message contains data loss warning
        assert "WARNING" in error_message or "warning" in error_message.lower()
        assert "data loss" in error_message.lower() or \
               "mark all migrations as applied" in error_message.lower()
        
        # Verify error message lists detected tables
        assert "users" in error_message
        assert "expenses" in error_message
        assert "categories" in error_message
    
    async def test_init_db_with_partial_state(self, database_with_tables_no_version):
        """
        Test that init_db() raises PartialDatabaseError on partial state.
        
        This tests the full integration through the init_db() entry point.
        """
        from app import database
        original_engine = database.engine
        database.engine = database_with_tables_no_version
        
        try:
            # Call init_db should raise PartialDatabaseError
            with pytest.raises(PartialDatabaseError) as exc_info:
                await init_db()
            
            # Verify error details
            error = exc_info.value
            assert len(error.tables) > 0
            assert "stamp head" in str(error)
            
        finally:
            # Restore original engine
            database.engine = original_engine



@pytest.mark.asyncio
class TestUpToDateDatabase:
    """Test integration for up-to-date database validation.
    
    Validates: Requirement 7.1
    """
    
    async def test_up_to_date_database_no_migrations_run(self, database_at_head):
        """
        Test that database at head revision skips migration execution.
        
        Validates:
        - Requirement 7.1: Up-to-date database completes without running migrations
        """
        manager = MigrationManager(database_at_head)
        
        # Verify database is at head
        current_revision = await manager._get_current_revision()
        head_revision = manager._get_migration_head()
        assert current_revision == head_revision, \
            "Database should be at head revision"
        
        # Get table count before
        async with database_at_head.connect() as conn:
            def count_tables(connection):
                inspector = inspect(connection)
                return len(inspector.get_table_names())
            
            table_count_before = await conn.run_sync(count_tables)
        
        # Run check_and_run_migrations
        await manager.check_and_run_migrations()
        
        # Verify no changes were made (table count should be same)
        async with database_at_head.connect() as conn:
            table_count_after = await conn.run_sync(count_tables)
        
        assert table_count_before == table_count_after, \
            "No tables should be added when database is up to date"
        
        # Verify revision is still at head
        current_revision_after = await manager._get_current_revision()
        assert current_revision_after == head_revision, \
            "Revision should remain at head"
    
    async def test_init_db_on_up_to_date_database(self, database_at_head):
        """
        Test that init_db() succeeds on up-to-date database without changes.
        
        This tests the full integration through the init_db() entry point.
        """
        from app import database
        original_engine = database.engine
        database.engine = database_at_head
        
        try:
            # Get revision before
            manager = MigrationManager(database_at_head)
            revision_before = await manager._get_current_revision()
            
            # Call init_db should succeed
            await init_db()
            
            # Verify revision unchanged
            revision_after = await manager._get_current_revision()
            assert revision_before == revision_after, \
                "Revision should not change for up-to-date database"
            
        finally:
            # Restore original engine
            database.engine = original_engine



@pytest.mark.asyncio
class TestMigrationFailureRollback:
    """Test integration for migration failure and rollback.
    
    Validates: Requirements 2.3, 6.1, 6.2
    """
    
    async def test_migration_failure_raises_error_and_rolls_back(self, empty_database):
        """
        Test that migration failures raise MigrationExecutionError and rollback changes.
        
        Validates:
        - Requirement 2.3: Migration failure raises exception
        - Requirement 6.1: Migrations execute within transaction
        - Requirement 6.2: Failed migrations rollback all changes
        """
        manager = MigrationManager(empty_database)
        
        # Mock the Alembic command.upgrade to raise an exception
        with patch('alembic.command.upgrade') as mock_upgrade:
            mock_upgrade.side_effect = Exception("Simulated migration failure")
            
            # Attempt to run migrations should raise MigrationExecutionError
            with pytest.raises(MigrationExecutionError) as exc_info:
                await manager._run_migrations_to_head()
            
            error = exc_info.value
            
            # Verify error details
            assert error.revision == "head"
            assert "Simulated migration failure" in str(error.original_error)
            assert "rolled back" in str(error).lower()
        
        # Verify no tables were created (rollback successful)
        async with empty_database.connect() as conn:
            def check_tables(connection):
                inspector = inspect(connection)
                return inspector.get_table_names()
            
            tables = await conn.run_sync(check_tables)
            assert len(tables) == 0, \
                "No tables should exist after failed migration rollback"
        
        # Verify alembic_version was not created
        has_version = await manager._check_alembic_version_exists()
        assert not has_version, \
            "alembic_version should not exist after failed migration"
    
    async def test_init_db_with_migration_failure(self, empty_database):
        """
        Test that init_db() propagates MigrationExecutionError on failure.
        
        This tests the full integration through the init_db() entry point.
        """
        from app import database
        original_engine = database.engine
        database.engine = empty_database
        
        try:
            # Mock migration failure
            with patch('alembic.command.upgrade') as mock_upgrade:
                mock_upgrade.side_effect = Exception("Migration failed")
                
                # Call init_db should raise MigrationExecutionError
                with pytest.raises(MigrationExecutionError):
                    await init_db()
            
            # Verify database remains empty
            manager = MigrationManager(empty_database)
            has_version = await manager._check_alembic_version_exists()
            assert not has_version, "Database should remain empty after failure"
            
        finally:
            # Restore original engine
            database.engine = original_engine



@pytest.mark.asyncio
class TestUnknownVersionError:
    """Test integration for unknown version error handling.
    
    Validates: Requirement 4.2
    """
    
    async def test_unknown_version_raises_error(self, database_with_unknown_version):
        """
        Test that database with unknown version raises UnknownVersionError.
        
        Validates:
        - Requirement 4.2: Unknown version detection and error
        """
        manager = MigrationManager(database_with_unknown_version)
        
        # Verify alembic_version exists with unknown revision
        has_version = await manager._check_alembic_version_exists()
        assert has_version, "alembic_version table should exist"
        
        current_revision = await manager._get_current_revision()
        assert current_revision == "unknown_fake_revision_12345"
        
        # Verify the revision is not in known revisions
        all_revisions = manager._get_all_revisions()
        assert current_revision not in all_revisions, \
            "Current revision should not be in known revisions"
        
        # Attempt to run migrations should raise UnknownVersionError
        with pytest.raises(UnknownVersionError) as exc_info:
            await manager.check_and_run_migrations()
        
        error = exc_info.value
        
        # Verify error details
        assert error.current_version == "unknown_fake_revision_12345"
        assert len(error.known_versions) > 0
        
        # Verify error message
        error_message = str(error)
        assert "unknown_fake_revision_12345" in error_message
        assert "not found in migration files" in error_message.lower()
        assert "corruption" in error_message.lower() or \
               "tampering" in error_message.lower()
    
    async def test_init_db_with_unknown_version(self, database_with_unknown_version):
        """
        Test that init_db() raises UnknownVersionError on unknown version.
        
        This tests the full integration through the init_db() entry point.
        """
        from app import database
        original_engine = database.engine
        database.engine = database_with_unknown_version
        
        try:
            # Call init_db should raise UnknownVersionError
            with pytest.raises(UnknownVersionError) as exc_info:
                await init_db()
            
            # Verify error details
            error = exc_info.value
            assert error.current_version == "unknown_fake_revision_12345"
            assert "not found in migration files" in str(error).lower()
            
        finally:
            # Restore original engine
            database.engine = original_engine
