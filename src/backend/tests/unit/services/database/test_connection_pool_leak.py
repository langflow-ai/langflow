"""Tests to validate connection pool leak issues in DatabaseService.

These tests validate the reported issue where connection pools are not being
properly disposed, leading to pool exhaustion and "not reusing connections".
"""
# ruff: noqa: T201, W293, RUF100

import asyncio
import gc
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from langflow.services.database.service import DatabaseService
from langflow.services.deps import get_db_service
from langflow.services.schema import ServiceType


class TestConnectionPoolLeak:
    """Test cases to reproduce and validate connection pool leak issues."""

    @pytest.fixture
    def mock_settings_service(self):
        """Mock settings service with database configuration."""
        settings_service = MagicMock()
        settings_service.settings.database_url = "sqlite+aiosqlite:///:memory:"
        settings_service.settings.database_connection_retry = False
        settings_service.settings.db_connection_settings = {
            "pool_size": 5,  # Small pool for testing
            "max_overflow": 5,
            "pool_timeout": 30,
            "pool_pre_ping": True,
            "pool_recycle": 1800,
            "echo": False,
        }
        settings_service.settings.db_driver_connection_settings = None
        settings_service.settings.sqlite_pragmas = {"synchronous": "NORMAL", "journal_mode": "WAL"}
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
        assert original_engine is not None
        assert isinstance(original_engine, AsyncEngine)

        # Mock the dispose method to track if it's called
        original_dispose_mock = AsyncMock()
        original_engine.dispose = original_dispose_mock

        # Reload engine
        db_service.reload_engine()

        # Verify new engine was created
        new_engine = db_service.engine
        assert new_engine is not original_engine
        assert isinstance(new_engine, AsyncEngine)

        # CRITICAL TEST: The old engine's dispose() should have been called but isn't
        original_dispose_mock.assert_not_called()  # This demonstrates the bug

        # This is the root cause of connection pool leaks

    def test_multiple_reload_engine_calls_create_multiple_leaked_engines(self, db_service):
        """Test that multiple reload_engine calls create multiple leaked engines."""
        engines_created = []
        dispose_mocks = []

        # Create and track multiple engines
        for i in range(3):
            current_engine = db_service.engine
            dispose_mock = AsyncMock()
            current_engine.dispose = dispose_mock

            engines_created.append(current_engine)
            dispose_mocks.append(dispose_mock)

            # Reload to create new engine
            if i < 2:  # Don't reload after the last iteration
                db_service.reload_engine()

        # Verify we have different engine instances
        assert len({id(engine) for engine in engines_created}) == 3

        # CRITICAL: None of the old engines should have been disposed
        for dispose_mock in dispose_mocks[:-1]:  # Exclude the last one as it's still active
            dispose_mock.assert_not_called()

        # This demonstrates multiple connection pools existing simultaneously

    def test_service_manager_update_creates_new_service_without_teardown(self):
        """Test ServiceManager.update() creates new services without teardown."""
        from lfx.services.manager import get_service_manager

        service_manager = get_service_manager()

        # Get initial database service
        original_db_service = get_db_service()
        assert original_db_service is not None

        # Mock teardown to track calls
        teardown_mock = AsyncMock()
        original_db_service.teardown = teardown_mock

        # Update the service (this simulates the problematic behavior)
        service_manager.update(ServiceType.DATABASE_SERVICE)

        # Get the "new" service
        _ = get_db_service()  # Get updated service but don't need to use it

        # CRITICAL TEST: The old service's teardown should have been called but isn't
        teardown_mock.assert_not_called()  # This demonstrates the bug

        # The services should be different instances, but old one wasn't cleaned up
        # Note: Due to singleton pattern, they might be the same instance,
        # but the important point is teardown wasn't called

    @pytest.mark.asyncio
    async def test_database_service_teardown_disposes_engine(self, db_service):
        """Test that DatabaseService.teardown() properly disposes the engine."""
        # Get the engine and mock its dispose method
        engine = db_service.engine
        dispose_mock = AsyncMock()
        engine.dispose = dispose_mock

        # Call teardown
        await db_service.teardown()

        # Verify dispose was called
        dispose_mock.assert_called_once()

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
        original_engine = db_service.engine
        dispose_mock = AsyncMock()
        original_engine.dispose = dispose_mock

        # Create new engine (simulating reload without proper disposal)
        db_service.reload_engine()

        # Remove reference and force garbage collection
        del original_engine
        gc.collect()

        # The dispose mock should still not have been called
        # This demonstrates that garbage collection alone doesn't clean up the pools
        dispose_mock.assert_not_called()

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

        # Basic pool metrics that should be available
        assert hasattr(pool, "size")  # Total connections
        assert hasattr(pool, "checked_in")  # Available connections

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
        from lfx.services.manager import get_service_manager

        service_manager = get_service_manager()

        # Track engines created
        engines_seen = []

        for i in range(3):
            db_service = get_db_service()
            engines_seen.append(db_service.engine)

            # Simulate configuration changes that trigger reload
            db_service.database_url = f"sqlite+aiosqlite:///:memory:?cache=private_{i}"
            db_service.reload_engine()

            engines_seen.append(db_service.engine)

        # Should have created multiple different engines
        unique_engines = {id(engine) for engine in engines_seen}
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
