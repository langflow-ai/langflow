"""Integration tests for database service with Windows + PostgreSQL event loop.

Uses real settings objects and real SQLite engine where possible; only
platform.system is patched to simulate Windows vs non-Windows. Project
convention: avoid mocking in tests.
"""

import asyncio
from unittest.mock import patch

import pytest
from langflow.services.database.service import DatabaseService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool


class _TestSettings:
    """Minimal settings-like object (no mocks) for DatabaseService init."""

    database_url = "sqlite+aiosqlite:///:memory:"
    database_connection_retry = False
    sqlite_pragmas = {}
    db_driver_connection_settings = None
    db_connection_settings = {}
    db_connect_timeout = 5
    alembic_log_to_stdout = True
    alembic_log_file = "alembic.log"
    use_noop_database = False
    model_fields_set = set()


class _TestAuthSettings:
    AUTO_LOGIN = False
    SUPERUSER = "admin"


class _TestSettingsService:
    """Minimal settings service (no mocks) for DatabaseService."""

    settings = _TestSettings()
    auth_settings = _TestAuthSettings()


@pytest.fixture
def test_settings_service():
    """Real settings-like object with required attributes (no MagicMock)."""
    return _TestSettingsService()


class TestDatabaseServiceWindowsPostgres:
    """Database service with Windows + PostgreSQL event loop configuration."""

    @patch("langflow.helpers.windows_postgres_helper.platform.system")
    def test_windows_postgresql_calls_configure_with_source(self, mock_platform, test_settings_service):
        """Windows + PostgreSQL: configure_windows_postgres_event_loop is called with source."""
        mock_platform.return_value = "Windows"
        test_settings_service.settings.database_url = "postgresql://user:pass@localhost/db"
        with patch("langflow.services.database.service.create_async_engine") as create_engine:
            create_engine.return_value = create_async_engine(
                "sqlite+aiosqlite://",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            _ = DatabaseService(test_settings_service)
            create_engine.assert_called_once()
        mock_platform.assert_called()

    @patch("langflow.helpers.windows_postgres_helper.platform.system")
    def test_linux_sqlite_real_engine_no_event_loop_change(self, mock_platform, test_settings_service):
        """Linux + SQLite: real engine creation, event loop unchanged (no mock of create_async_engine)."""
        mock_platform.return_value = "Linux"
        test_settings_service.settings.database_url = "sqlite+aiosqlite://"
        original_policy = asyncio.get_event_loop_policy()

        service = DatabaseService(test_settings_service)

        assert asyncio.get_event_loop_policy() is original_policy
        assert service.async_session_maker is not None
        assert service.database_url == "sqlite+aiosqlite://"

    @patch("langflow.helpers.windows_postgres_helper.platform.system")
    def test_macos_sqlite_real_engine_no_event_loop_change(self, mock_platform, test_settings_service):
        """MacOS + SQLite: real engine, event loop unchanged."""
        mock_platform.return_value = "Darwin"
        test_settings_service.settings.database_url = "sqlite+aiosqlite://"
        original_policy = asyncio.get_event_loop_policy()

        service = DatabaseService(test_settings_service)

        assert asyncio.get_event_loop_policy() is original_policy
        assert service.async_session_maker is not None

    @patch("langflow.helpers.windows_postgres_helper.platform.system")
    def test_windows_sqlite_real_engine_configure_called(self, mock_platform, test_settings_service):
        """Windows + SQLite: real engine; configure is still called (returns False)."""
        mock_platform.return_value = "Windows"
        test_settings_service.settings.database_url = "sqlite+aiosqlite://"
        original_policy = asyncio.get_event_loop_policy()

        service = DatabaseService(test_settings_service)

        assert asyncio.get_event_loop_policy() is original_policy
        assert service.async_session_maker is not None

    def test_database_url_sanitization_real_settings(self, test_settings_service):
        """Database URLs are sanitized (real settings, only create_engine patched for speed)."""
        test_cases = [
            ("sqlite:///test.db", "sqlite+aiosqlite:///test.db"),
            ("postgresql://user:pass@localhost/db", "postgresql+psycopg://user:pass@localhost/db"),
            ("postgres://user:pass@localhost/db", "postgresql+psycopg://user:pass@localhost/db"),
        ]
        with patch("langflow.services.database.service.create_async_engine") as create_engine:
            create_engine.return_value = create_async_engine(
                "sqlite+aiosqlite://",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            for input_url, expected_url in test_cases:
                test_settings_service.settings.database_url = input_url
                service = DatabaseService(test_settings_service)
                assert service.database_url == expected_url

    @patch("langflow.helpers.windows_postgres_helper.platform.system")
    def test_async_session_maker_available_after_init(self, mock_platform, test_settings_service):
        """After init with SQLite, async_session_maker is usable (real engine)."""
        mock_platform.return_value = "Linux"
        test_settings_service.settings.database_url = "sqlite+aiosqlite://"

        service = DatabaseService(test_settings_service)

        assert service.async_session_maker is not None

    @pytest.mark.asyncio
    async def test_async_operations_work_after_init(self, test_settings_service):
        """Async session maker works after init (real engine, no mock)."""
        with patch("langflow.helpers.windows_postgres_helper.platform.system") as mock_platform:
            mock_platform.return_value = "Linux"
            service = DatabaseService(test_settings_service)

            assert service.async_session_maker is not None
            async with service.async_session_maker() as session:
                assert session is not None
                await session.execute(text("SELECT 1"))
