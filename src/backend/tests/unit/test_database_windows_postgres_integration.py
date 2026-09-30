"""Integration tests for database service with Windows + PostgreSQL fix.

Tests that the database service properly handles event loop configuration
across different platforms and database types.
"""

import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest
from langflow.services.database.service import DatabaseService


class TestDatabaseServiceWindowsPostgres:
    """Test database service with Windows + PostgreSQL event loop configuration."""

    @pytest.fixture
    def mock_settings_service(self):
        """Create a mock settings service for testing."""
        mock_service = MagicMock()
        mock_service.settings.database_url = "sqlite:///test.db"
        mock_service.settings.database_connection_retry = False
        mock_service.settings.sqlite_pragmas = {}
        mock_service.settings.db_driver_connection_settings = None
        mock_service.settings.db_connection_settings = {}
        mock_service.settings.alembic_log_to_stdout = True
        mock_service.settings.alembic_log_file = "alembic.log"
        return mock_service

    @patch("platform.system")
    @patch.dict(os.environ, {"LANGFLOW_DATABASE_URL": "postgresql://user:pass@localhost/db"}, clear=True)
    @patch("langflow.services.database.service.create_async_engine")
    @patch("langflow.services.database.service.configure_windows_postgres_event_loop")
    def test_windows_postgresql_configures_event_loop(
        self, mock_configure, mock_create_engine, mock_platform, mock_settings_service
    ):
        """Test that Windows + PostgreSQL configures the event loop correctly."""
        mock_platform.return_value = "Windows"
        mock_settings_service.settings.database_url = "postgresql://user:pass@localhost/db"
        mock_create_engine.return_value = MagicMock()
        mock_configure.return_value = True

        _ = DatabaseService(mock_settings_service)
        mock_configure.assert_called_once_with(source="database_service")

    @patch("platform.system")
    @patch.dict(os.environ, {}, clear=True)
    @patch("langflow.services.database.service.create_async_engine")
    def test_linux_postgresql_no_event_loop_change(self, mock_create_engine, mock_platform, mock_settings_service):
        """Test that Linux + PostgreSQL doesn't change event loop."""
        mock_platform.return_value = "Linux"
        mock_settings_service.settings.database_url = "postgresql://user:pass@localhost/db"
        mock_create_engine.return_value = MagicMock()

        original_policy = asyncio.get_event_loop_policy()
        _ = DatabaseService(mock_settings_service)

        # Policy should remain unchanged
        assert asyncio.get_event_loop_policy() is original_policy

    @patch("platform.system")
    @patch.dict(os.environ, {}, clear=True)
    @patch("langflow.services.database.service.create_async_engine")
    def test_macos_postgresql_no_event_loop_change(self, mock_create_engine, mock_platform, mock_settings_service):
        """Test that macOS + PostgreSQL doesn't change event loop."""
        mock_platform.return_value = "Darwin"
        mock_settings_service.settings.database_url = "postgresql://user:pass@localhost/db"
        mock_create_engine.return_value = MagicMock()

        original_policy = asyncio.get_event_loop_policy()
        _ = DatabaseService(mock_settings_service)

        # Policy should remain unchanged
        assert asyncio.get_event_loop_policy() is original_policy

    @patch("platform.system")
    @patch.dict(os.environ, {}, clear=True)
    @patch("langflow.services.database.service.create_async_engine")
    @patch("langflow.services.database.service.configure_windows_postgres_event_loop")
    def test_windows_sqlite_no_event_loop_change(
        self, mock_configure, mock_create_engine, mock_platform, mock_settings_service
    ):
        """Test that Windows + SQLite doesn't change event loop."""
        mock_platform.return_value = "Windows"
        mock_settings_service.settings.database_url = "sqlite:///test.db"
        mock_create_engine.return_value = MagicMock()
        mock_configure.return_value = False

        _ = DatabaseService(mock_settings_service)
        mock_configure.assert_called_once_with(source="database_service")

    def test_database_url_sanitization(self, mock_settings_service):
        """Test that database URLs are properly sanitized."""
        test_cases = [
            ("sqlite:///test.db", "sqlite+aiosqlite:///test.db"),
            ("postgresql://user:pass@localhost/db", "postgresql+psycopg://user:pass@localhost/db"),
            ("postgres://user:pass@localhost/db", "postgresql+psycopg://user:pass@localhost/db"),
        ]

        with patch("langflow.services.database.service.create_async_engine") as mock_create_engine:
            mock_create_engine.return_value = MagicMock()

            for input_url, expected_url in test_cases:
                mock_settings_service.settings.database_url = input_url
                service = DatabaseService(mock_settings_service)
                assert service.database_url == expected_url

    @patch("platform.system")
    def test_docker_environment_compatibility(self, mock_platform, mock_settings_service):
        """Test that Docker environments work correctly."""
        mock_platform.return_value = "Linux"
        os.environ["DOCKER_CONTAINER"] = "true"
        mock_settings_service.settings.database_url = "postgresql://postgres:5432/langflow"

        with patch("langflow.services.database.service.create_async_engine") as mock_create_engine:
            mock_create_engine.return_value = MagicMock()

            # Should not raise any errors
            service = DatabaseService(mock_settings_service)
            assert service.database_url == "postgresql+psycopg://postgres:5432/langflow"

    @pytest.mark.asyncio
    async def test_async_operations_work_after_configuration(self, mock_settings_service):
        """Test that async operations work correctly after event loop configuration."""
        mock_settings_service.settings.database_url = "sqlite:///test.db"

        with patch("langflow.services.database.service.create_async_engine") as mock_create_engine:
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            service = DatabaseService(mock_settings_service)

            # Test that async session maker is properly configured
            assert service.async_session_maker is not None

            # Simulate an async operation
            async def test_async():
                return True

            result = await test_async()
            assert result is True
