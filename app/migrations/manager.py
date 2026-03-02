"""
Migration manager for handling Alembic migrations programmatically.

This module provides the MigrationManager class that detects database states
and executes migrations safely.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncEngine


class MigrationManager:
    """
    Manages Alembic migration detection, validation, and execution.
    
    This class provides programmatic access to Alembic operations and
    implements the logic for detecting and handling various database states.
    """
    
    def __init__(self, engine: AsyncEngine, alembic_cfg_path: str = "alembic.ini"):
        """
        Initialize the migration manager.
        
        Args:
            engine: SQLAlchemy async engine for database operations
            alembic_cfg_path: Path to alembic.ini configuration file
        """
        self.engine = engine
        self.alembic_cfg_path = alembic_cfg_path
        self.logger = logging.getLogger(__name__)

    
    async def _verify_connectivity(self) -> None:
        """
        Verify database connectivity before migration operations.
        
        Raises:
            DatabaseConnectionError: When database is unreachable
        """
        from app.migrations.exceptions import DatabaseConnectionError
        from sqlalchemy import text
        
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as e:
            # Sanitize connection URL to exclude credentials
            db_url = str(self.engine.url)
            # Remove password from URL
            if "@" in db_url:
                parts = db_url.split("@")
                if ":" in parts[0]:
                    user_part = parts[0].split(":")[0]
                    sanitized_url = f"{user_part}:***@{parts[1]}"
                else:
                    sanitized_url = db_url
            else:
                sanitized_url = db_url
            
            self.logger.error(
                f"Failed to connect to database: {sanitized_url}",
                extra={"error": str(e)}
            )
            raise DatabaseConnectionError(
                f"Failed to connect to database: {sanitized_url}\n"
                f"Error: {str(e)}\n"
                f"Action: Verify database is running and connection settings are correct"
            )

    
    async def _check_alembic_version_exists(self) -> bool:
        """
        Check if the alembic_version table exists in the database.
        
        Returns:
            bool: True if table exists, False otherwise
        """
        from sqlalchemy import inspect
        
        async with self.engine.connect() as conn:
            # Use inspector to check table existence
            def check_table(connection):
                inspector = inspect(connection)
                return "alembic_version" in inspector.get_table_names()
            
            return await conn.run_sync(check_table)

    
    async def _get_application_tables(self) -> list[str]:
        """
        Get list of application tables in the database.
        
        Excludes the alembic_version table from the results.
        
        Returns:
            list[str]: List of table names
        """
        from sqlalchemy import inspect
        
        async with self.engine.connect() as conn:
            def get_tables(connection):
                inspector = inspect(connection)
                all_tables = inspector.get_table_names()
                # Exclude alembic_version table
                return [table for table in all_tables if table != "alembic_version"]
            
            return await conn.run_sync(get_tables)

    
    async def _get_current_revision(self) -> str | None:
        """
        Get the current migration revision from alembic_version table.
        
        Returns:
            str | None: Current revision ID or None if table is empty
        """
        from sqlalchemy import text
        
        async with self.engine.connect() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.fetchone()
            return row[0] if row else None

    
    def _get_migration_head(self) -> str:
        """
        Get the head (latest) migration revision from migration files.
        
        Returns:
            str: Head revision ID
        """
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        
        alembic_cfg = Config(self.alembic_cfg_path)
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        return script_dir.get_current_head()

    
    def _get_all_revisions(self) -> list[str]:
        """
        Get all migration revision IDs from migration files.
        
        Returns:
            list[str]: List of revision IDs in order
        """
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        
        alembic_cfg = Config(self.alembic_cfg_path)
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        
        revisions = []
        for revision in script_dir.walk_revisions():
            revisions.append(revision.revision)
        
        return list(reversed(revisions))  # Return in chronological order

    
    def _count_pending_migrations(self, current: str, head: str) -> int:
        """
        Count how many migrations are between current and head.
        
        Args:
            current: Current revision ID
            head: Head revision ID
        
        Returns:
            int: Number of pending migrations
        """
        if current == head:
            return 0
        
        all_revisions = self._get_all_revisions()
        
        try:
            current_idx = all_revisions.index(current)
            head_idx = all_revisions.index(head)
            return head_idx - current_idx
        except ValueError:
            # If revision not found, return 0
            return 0

    
    async def _run_migrations_to_head(self) -> None:
        """
        Run all pending migrations to bring database to head revision.
        
        Uses Alembic's programmatic API to execute migrations within
        a transaction. Rolls back on failure.
        
        Raises:
            MigrationExecutionError: If any migration fails
        """
        from app.migrations.exceptions import MigrationExecutionError
        from alembic.config import Config
        from alembic import command
        import time
        
        alembic_cfg = Config(self.alembic_cfg_path)
        
        # Suppress Alembic's default logging to use our own
        alembic_cfg.set_main_option("sqlalchemy.url", str(self.engine.url))
        
        start_time = time.time()
        
        try:
            self.logger.info("Starting migration execution to head")
            
            # Run migrations synchronously (Alembic doesn't support async)
            def run_upgrade(connection):
                alembic_cfg.attributes["connection"] = connection
                command.upgrade(alembic_cfg, "head")
            
            async with self.engine.begin() as conn:
                await conn.run_sync(run_upgrade)
            
            execution_time = time.time() - start_time
            self.logger.info(
                f"Migration execution completed successfully in {execution_time:.2f}s"
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(
                f"Migration execution failed after {execution_time:.2f}s: {str(e)}"
            )
            raise MigrationExecutionError("head", e)

    
    def _format_recovery_command(self, command: str) -> str:
        """
        Format a recovery command with the correct alembic.ini path.
        
        Args:
            command: Base command (e.g., "stamp head")
        
        Returns:
            str: Full command with config path
        """
        return f"alembic -c {self.alembic_cfg_path} {command}"

    
    async def check_and_run_migrations(self) -> None:
        """
        Main entry point for migration checking and execution.
        
        Detects database state and takes appropriate action:
        - Empty database: Run all migrations
        - Partial state: Raise error with recovery instructions
        - Existing migrations: Validate and log status
        
        Raises:
            PartialDatabaseError: When tables exist but no migration history
            UnknownVersionError: When current version is not in migration files
            MigrationExecutionError: When migration execution fails
            DatabaseConnectionError: When database is unreachable
        """
        # Step 1: Verify connectivity
        await self._verify_connectivity()
        
        # Step 2: Check if alembic_version table exists
        has_alembic_version = await self._check_alembic_version_exists()
        
        if not has_alembic_version:
            # Sanitize URL for logging
            db_url = str(self.engine.url)
            if "@" in db_url:
                parts = db_url.split("@")
                if ":" in parts[0]:
                    user_part = parts[0].split(":")[0]
                    sanitized_url = f"{user_part}:***@{parts[1]}"
                else:
                    sanitized_url = db_url
            else:
                sanitized_url = db_url
            
            self.logger.warning(
                f"Missing migration history (alembic_version table not found) "
                f"for database: {sanitized_url}"
            )

            
            # Step 3: Check for application tables
            application_tables = await self._get_application_tables()
            
            if len(application_tables) == 0:
                # Empty database - run all migrations
                self.logger.info("Empty database detected, running all migrations to head")
                import time
                start_time = time.time()
                
                await self._run_migrations_to_head()
                
                # Verify alembic_version was created
                has_version_after = await self._check_alembic_version_exists()
                if not has_version_after:
                    self.logger.error("Migration completed but alembic_version table not found")
                    raise Exception("Migration verification failed")
                
                execution_time = time.time() - start_time
                head_revision = self._get_migration_head()
                all_revisions = self._get_all_revisions()
                migration_count = len(all_revisions)
                
                self.logger.info(
                    f"Successfully applied {migration_count} migrations to head "
                    f"revision {head_revision} in {execution_time:.2f}s"
                )
                return

            
            # Partial state - tables exist but no migration history
            from app.migrations.exceptions import PartialDatabaseError
            
            recovery_command = self._format_recovery_command("stamp head")
            self.logger.error(
                f"Partial database state detected: {len(application_tables)} tables "
                f"found but no migration history"
            )
            raise PartialDatabaseError(application_tables, recovery_command)

        
        # alembic_version exists - validate migration history
        from app.migrations.exceptions import UnknownVersionError
        
        current_revision = await self._get_current_revision()
        head_revision = self._get_migration_head()
        all_revisions = self._get_all_revisions()
        
        # Check if current version is known
        if current_revision and current_revision not in all_revisions:
            self.logger.error(
                f"Unknown migration version '{current_revision}' found in database"
            )
            recovery_command = self._format_recovery_command("stamp head")
            raise UnknownVersionError(current_revision, all_revisions, recovery_command)
        
        # Check if migrations are pending
        if current_revision == head_revision:
            self.logger.info(
                f"Database is up to date at revision {current_revision}"
            )
        else:
            pending_count = self._count_pending_migrations(current_revision, head_revision)
            self.logger.info(
                f"Database at revision {current_revision}, "
                f"{pending_count} pending migrations to reach head {head_revision}"
            )
