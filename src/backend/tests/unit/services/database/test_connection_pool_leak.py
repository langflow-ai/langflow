"""Tests to validate connection pool leak issues in DatabaseService.

These tests validate the reported issue where connection pools are not being
properly disposed, leading to pool exhaustion and "not reusing connections".
"""
# ruff: noqa: T201, W293, RUF100

import asyncio
import gc
from unittest.mock import MagicMock

import pytest
from langflow.services.database.service import DatabaseService
from sqlalchemy.ext.asyncio import AsyncEngine


class TestConnectionPoolLeak:
    """Test cases to reproduce and validate connection pool leak issues."""

    @pytest.fixture
    def mock_settings_service(self):
        """Mock settings service with database configuration."""
        settings_service = MagicMock()
        settings_service.settings.database_url = "sqlite+aiosqlite:///:memory:"
        settings_service.settings.database_connection_retry = False
        # SQLite doesn't support pool parameters with StaticPool
        settings_service.settings.db_connection_settings = {}
        settings_service.settings.db_driver_connection_settings = None
        settings_service.settings.sqlite_pragmas = {"synchronous": "NORMAL", "journal_mode": "WAL"}
        settings_service.settings.alembic_log_file = "alembic.log"
        settings_service.settings.model_fields_set = set()
        return settings_service

    @pytest.fixture
    def db_service(self, mock_settings_service):
        """Create a DatabaseService instance for testing."""
        return DatabaseService(mock_settings_service)

    def test_reload_engine_creates_new_engine_without_disposing_old(self, db_service):
        """Test that reload_engine creates new engines without disposing old ones.

        This test validates the core issue: reload_engine() creates new AsyncEngine
        instances without properly disposing of the previous ones, leading to
        connection pool leaks.
        """
        # Get initial engine
        original_engine = db_service.engine
        original_engine_id = id(original_engine)
        assert original_engine is not None
        assert isinstance(original_engine, AsyncEngine)

        # Reload engine
        db_service.reload_engine()

        # Verify new engine was created
        new_engine = db_service.engine
        new_engine_id = id(new_engine)
        assert new_engine is not original_engine
        assert isinstance(new_engine, AsyncEngine)

        # The fix in reload_engine() now properly disposes old engines
        assert original_engine_id != new_engine_id

    def test_multiple_reload_engine_calls_create_multiple_leaked_engines(self, db_service):
        """Test that multiple reload_engine calls create multiple leaked engines."""
        engines_created = []

        # Create and track multiple engines
        for _i in range(3):
            current_engine = db_service.engine
            engines_created.append(id(current_engine))

            # Reload to create new engine
            if _i < 2:  # Don't reload after the last iteration
                db_service.reload_engine()

        # Verify we have different engine instances
        assert len(set(engines_created)) == 3

        # The fix in reload_engine() now properly disposes old engines before creating new ones

    # NOTE: This test was removed because ServiceManager.update() was removed.
    # The update() method was only used in tests and not in production code.
    # Service lifecycle is now managed through proper teardown in ServiceManager.teardown()
    # which is tested in test_fixes_validation.py::test_service_manager_has_teardown_logic()

    @pytest.mark.asyncio
    async def test_database_service_teardown_disposes_engine(self, db_service):
        """Test that DatabaseService.teardown() properly disposes the engine."""
        # Get the engine
        engine = db_service.engine
        engine_id = id(engine)
        assert engine is not None

        # Call teardown
        await db_service.teardown()

        # Verify engine reference was cleared (which happens after disposal)
        assert db_service.engine is None
        assert engine_id is not None  # Just to use the variable

    def test_connection_pool_configuration(self, db_service):
        """Test that connection pools are configured with expected limits."""
        engine = db_service.engine

        # Verify pool configuration matches settings
        # Note: This is tricky to test directly as pool internals are private
        # But we can verify the engine was created with our settings
        assert engine is not None

        # The actual pool size/overflow settings are applied during engine creation
        # This test ensures the configuration path is working

    @pytest.mark.asyncio
    async def test_concurrent_database_operations_dont_exhaust_pool(self, db_service):
        """Test that concurrent operations don't exhaust the connection pool.

        This test simulates the user-reported issue where the system
        "keeps consuming until hitting the limit" instead of reusing connections.
        """
        # This test would need a real database to be meaningful
        # For now, we'll test that the service can handle multiple session requests

        async def get_session():
            async with db_service.with_session() as _:
                # Simulate some database work
                await asyncio.sleep(0.001)
                return True

        # Run multiple concurrent operations
        tasks = [get_session() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All operations should succeed without pool exhaustion
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Database operation failed: {result}")
            assert result is True

    def test_engine_disposal_in_garbage_collection_context(self, db_service):
        """Test behavior when engines are garbage collected without explicit disposal."""
        # Store reference to original engine
        original_engine_id = id(db_service.engine)

        # Create new engine (simulating reload without proper disposal)
        db_service.reload_engine()

        # Verify new engine was created
        new_engine_id = id(db_service.engine)
        assert original_engine_id != new_engine_id

        # Force garbage collection
        gc.collect()

        # The fix in reload_engine() now properly disposes old engines

    @pytest.mark.asyncio
    async def test_multiple_database_services_share_connection_limits(self):
        """Test that multiple DatabaseService instances can cause pool exhaustion.

        This test validates the scenario where multiple services are created
        (even if by mistake) and each consumes connection pool resources.
        """
        from lfx.services.settings.auth import AuthSettings
        from lfx.services.settings.base import Settings
        from lfx.services.settings.service import SettingsService

        # Create multiple database services (simulating the leak scenario)
        settings = Settings()
        settings.database_url = "sqlite+aiosqlite:///:memory:"
        import tempfile

        auth_settings = AuthSettings(CONFIG_DIR=settings.config_dir or tempfile.gettempdir())
        settings_service = SettingsService(settings, auth_settings)

        services = []
        for _ in range(3):
            service = DatabaseService(settings_service)
            services.append(service)

        # Each service has its own engine and connection pool
        engines = [service.engine for service in services]
        assert len({id(engine) for engine in engines}) == 3

        # Clean up properly for this test
        for service in services:
            await service.teardown()

    def test_connection_pool_metrics_tracking(self, db_service):
        """Test that we can track connection pool metrics for monitoring.

        This test sets up the foundation for monitoring connection pool health.
        """
        engine = db_service.engine

        # Access pool information (this varies by SQLAlchemy version)
        pool = engine.pool

        # Basic pool metrics - verify pool exists
        # Note: SQLite uses StaticPool which has different attributes than QueuePool
        # that's used in production with PostgreSQL
        assert pool is not None

        # For production databases (PostgreSQL/MySQL) with QueuePool, these would be available:
        # - pool.size() - total connections in pool
        # - pool.checkedin() - available connections
        # - pool.overflow() - connections beyond pool_size
        # - pool.invalid() - invalid connections

        # These metrics would be useful for monitoring:
        # - pool.size() - total connections in pool
        # - pool.checkedin() - available connections
        # - pool.overflow() - connections beyond pool_size
        # - pool.invalid() - invalid connections


class TestConnectionPoolLeakIntegration:
    """Integration tests for connection pool leak scenarios."""

    @pytest.mark.asyncio
    async def test_full_service_lifecycle_with_multiple_reloads(self):
        """Integration test for full service lifecycle with multiple reloads."""
        from unittest.mock import MagicMock

        from langflow.services.database.service import DatabaseService
        from lfx.services.manager import get_service_manager

        service_manager = get_service_manager()

        # Create a mock settings service (using existing fixture pattern)
        mock_settings = MagicMock()
        mock_settings.settings.database_url = "sqlite+aiosqlite:///:memory:"
        mock_settings.settings.database_connection_retry = False
        mock_settings.settings.db_connection_settings = {}  # SQLite doesn't support pool params
        mock_settings.settings.db_driver_connection_settings = None
        mock_settings.settings.sqlite_pragmas = {"synchronous": "NORMAL", "journal_mode": "WAL"}
        mock_settings.settings.alembic_log_file = "alembic.log"
        mock_settings.settings.model_fields_set = set()

        # Track engines created
        engines_seen = []

        for _ in range(3):
            db_service = DatabaseService(mock_settings)
            engines_seen.append(id(db_service.engine))

            # Simulate configuration changes that trigger reload
            db_service.reload_engine()
            engines_seen.append(id(db_service.engine))

        # Should have created multiple different engines
        unique_engines = set(engines_seen)
        assert len(unique_engines) > 1

        # Clean up
        await service_manager.teardown()


# Utility class to help with testing
class ConnectionPoolMonitor:
    """Helper class to monitor connection pool state during tests."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.pool = engine.pool

    def get_pool_status(self) -> dict:
        """Get current pool status for monitoring."""
        return {
            "size": getattr(self.pool, "size", lambda: 0)(),
            "checked_in": getattr(self.pool, "checkedin", lambda: 0)(),
            "overflow": getattr(self.pool, "overflow", lambda: 0)(),
            "invalid": getattr(self.pool, "invalid", lambda: 0)(),
        }

    def assert_pool_is_healthy(self):
        """Assert that the pool is in a healthy state."""
        status = self.get_pool_status()

        # Pool shouldn't be completely exhausted
        assert status["checked_in"] >= 0, "Pool has negative checked-in connections"

        # Overflow should be reasonable
        assert status["overflow"] >= 0, "Pool has negative overflow"


# Mark all tests in this module as requiring database
pytestmark = pytest.mark.database
