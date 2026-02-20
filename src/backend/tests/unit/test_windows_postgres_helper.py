"""Unit tests for Windows + PostgreSQL event loop configuration.

These tests ensure the fix works correctly across all platforms:
- Windows with PostgreSQL (applies fix)
- Windows with SQLite (no fix)
- Linux (no fix)
- macOS (no fix)
- Docker (no fix)
"""

import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest
from langflow.helpers.windows_postgres_helper import (
    LANGFLOW_DATABASE_URL,
    POSTGRESQL_PREFIXES,
    configure_windows_postgres_event_loop,
)

# Mock class for asyncio.WindowsSelectorEventLoopPolicy (only exists on Windows)
MockWindowsSelectorPolicy = type("WindowsSelectorEventLoopPolicy", (), {})


class TestWindowsPostgresHelper:
    """Test Windows + PostgreSQL helper functions."""

    @pytest.fixture(autouse=True)
    def reset_event_loop_policy(self):
        """Reset event loop policy before each test."""
        original_policy = asyncio.get_event_loop_policy()
        yield
        asyncio.set_event_loop_policy(original_policy)

    def test_constants_defined(self):
        """Test that required constants are properly defined."""
        assert LANGFLOW_DATABASE_URL == "LANGFLOW_DATABASE_URL"
        assert POSTGRESQL_PREFIXES == ("postgresql", "postgres")

    @patch("platform.system")
    @patch.dict(os.environ, {}, clear=True)
    def test_non_windows_returns_false(self, mock_platform):
        """Test that non-Windows systems return False and don't change event loop."""
        for system in ["Linux", "Darwin", "FreeBSD"]:
            mock_platform.return_value = system
            os.environ[LANGFLOW_DATABASE_URL] = "postgresql://user:pass@localhost/db"

            result = configure_windows_postgres_event_loop()

            assert result is False

    @patch("platform.system")
    @patch.dict(os.environ, {}, clear=True)
    def test_windows_without_database_url_returns_false(self, mock_platform):
        """Test Windows without DATABASE_URL returns False."""
        mock_platform.return_value = "Windows"

        result = configure_windows_postgres_event_loop()

        assert result is False

    @patch("platform.system")
    @patch.dict(os.environ, {"LANGFLOW_DATABASE_URL": "sqlite:///test.db"}, clear=True)
    def test_windows_with_sqlite_returns_false(self, mock_platform):
        """Test Windows with SQLite returns False and doesn't change event loop."""
        mock_platform.return_value = "Windows"

        result = configure_windows_postgres_event_loop()

        assert result is False

    @patch.object(asyncio, "WindowsSelectorEventLoopPolicy", MockWindowsSelectorPolicy, create=True)
    @patch("platform.system")
    @patch.dict(os.environ, {"LANGFLOW_DATABASE_URL": "postgresql://user:pass@localhost/db"}, clear=True)
    @patch("asyncio.get_event_loop_policy")
    @patch("asyncio.set_event_loop_policy")
    def test_windows_with_postgresql_sets_policy(self, mock_set_policy, mock_get_policy, mock_platform):
        """Test Windows with PostgreSQL sets WindowsSelectorEventLoopPolicy."""
        mock_platform.return_value = "Windows"
        mock_policy = MagicMock()
        mock_get_policy.return_value = mock_policy

        result = configure_windows_postgres_event_loop()

        assert result is True
        mock_set_policy.assert_called_once()
        args = mock_set_policy.call_args[0]
        assert len(args) == 1
        assert "WindowsSelectorEventLoopPolicy" in str(args[0].__class__)

    @patch.object(asyncio, "WindowsSelectorEventLoopPolicy", MockWindowsSelectorPolicy, create=True)
    @patch("platform.system")
    @patch.dict(os.environ, {"LANGFLOW_DATABASE_URL": "postgres://user:pass@localhost/db"}, clear=True)
    @patch("asyncio.get_event_loop_policy")
    @patch("asyncio.set_event_loop_policy")
    def test_windows_with_postgres_protocol_sets_policy(self, mock_set_policy, mock_get_policy, mock_platform):
        """Test Windows with 'postgres://' (deprecated) protocol also works."""
        mock_platform.return_value = "Windows"
        mock_policy = MagicMock()
        mock_get_policy.return_value = mock_policy

        result = configure_windows_postgres_event_loop()

        assert result is True
        mock_set_policy.assert_called_once()

    @patch.object(asyncio, "WindowsSelectorEventLoopPolicy", MockWindowsSelectorPolicy, create=True)
    @patch("platform.system")
    @patch.dict(os.environ, {"LANGFLOW_DATABASE_URL": "postgresql://user:pass@localhost/db"}, clear=True)
    @patch("asyncio.get_event_loop_policy")
    @patch("asyncio.set_event_loop_policy")
    def test_windows_with_selector_already_set_returns_false(self, mock_set_policy, mock_get_policy, mock_platform):
        """Test that if WindowsSelectorEventLoopPolicy is already set, returns False."""
        mock_platform.return_value = "Windows"
        mock_policy = MagicMock(spec=MockWindowsSelectorPolicy)
        mock_get_policy.return_value = mock_policy

        result = configure_windows_postgres_event_loop()

        assert result is False
        mock_set_policy.assert_not_called()

    @patch.object(asyncio, "WindowsSelectorEventLoopPolicy", MockWindowsSelectorPolicy, create=True)
    @patch("platform.system")
    @patch.dict(os.environ, {"LANGFLOW_DATABASE_URL": "postgresql://user:pass@localhost/db"}, clear=True)
    @patch("asyncio.get_event_loop_policy")
    @patch("asyncio.set_event_loop_policy")
    @patch("langflow.helpers.windows_postgres_helper.logger")
    def test_logging_includes_source_when_provided(self, mock_logger, mock_set_policy, mock_get_policy, mock_platform):  # noqa: ARG002
        """Test that source is included in log context when provided."""
        mock_platform.return_value = "Windows"
        mock_policy = MagicMock()
        mock_get_policy.return_value = mock_policy

        result = configure_windows_postgres_event_loop(source="test_source")

        assert result is True
        mock_logger.debug.assert_called_once_with(
            "Windows PostgreSQL event loop configured",
            extra={
                "event_loop": "WindowsSelectorEventLoop",
                "reason": "psycopg_compatibility",
                "source": "test_source",
            },
        )

    @patch("platform.system")
    @patch.dict(os.environ, {"LANGFLOW_DATABASE_URL": "mysql://user:pass@localhost/db"}, clear=True)
    def test_windows_with_other_database_returns_false(self, mock_platform):
        """Test Windows with non-PostgreSQL database returns False."""
        mock_platform.return_value = "Windows"

        result = configure_windows_postgres_event_loop()

        assert result is False

    @patch("platform.system")
    def test_docker_environment_not_affected(self, mock_platform):
        """Test that Docker environments (typically Linux) are not affected."""
        mock_platform.return_value = "Linux"
        os.environ[LANGFLOW_DATABASE_URL] = "postgresql://user:pass@postgres:5432/langflow"
        os.environ["DOCKER_CONTAINER"] = "true"

        original_policy = asyncio.get_event_loop_policy()
        result = configure_windows_postgres_event_loop()

        assert result is False
        assert asyncio.get_event_loop_policy() is original_policy

    @pytest.mark.parametrize(
        "db_url",
        [
            "postgresql://localhost/test",
            "postgresql+psycopg://localhost/test",
            "postgresql+asyncpg://localhost/test",
            "postgres://localhost/test",
        ],
    )
    @patch.object(asyncio, "WindowsSelectorEventLoopPolicy", MockWindowsSelectorPolicy, create=True)
    @patch("platform.system")
    @patch("asyncio.get_event_loop_policy")
    @patch("asyncio.set_event_loop_policy")
    def test_various_postgresql_urls_handled(self, mock_set_policy, mock_get_policy, mock_platform, db_url):
        """Test that various PostgreSQL URL formats are handled correctly."""
        mock_platform.return_value = "Windows"
        mock_policy = MagicMock()
        mock_get_policy.return_value = mock_policy

        with patch.dict(os.environ, {LANGFLOW_DATABASE_URL: db_url}, clear=True):
            result = configure_windows_postgres_event_loop()

        assert result is True
        mock_set_policy.assert_called_once()

    @patch("platform.system")
    @patch.dict(os.environ, {"LANGFLOW_DATABASE_URL": "postgresql://user:pass@localhost/db"}, clear=True)
    def test_windows_without_policy_class_returns_false(self, mock_platform):
        """Test that if WindowsSelectorEventLoopPolicy class is unavailable, returns False."""
        mock_platform.return_value = "Windows"

        with patch.object(asyncio, "WindowsSelectorEventLoopPolicy", None, create=True):
            result = configure_windows_postgres_event_loop()

        assert result is False
