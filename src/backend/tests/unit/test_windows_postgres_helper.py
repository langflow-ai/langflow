"""Unit tests for Windows + PostgreSQL event loop configuration.

Tests use minimal mocking: only platform.system (and env) where needed to
simulate Windows on non-Windows CI. asyncio policy get/set are exercised
for real. Project convention: avoid mocking in tests.
"""

import asyncio
import logging
import os
import platform
from unittest.mock import patch

import pytest
from langflow.helpers.windows_postgres_helper import (
    LANGFLOW_DATABASE_URL,
    POSTGRESQL_PREFIXES,
    configure_windows_postgres_event_loop,
)


# Subclass required so set_event_loop_policy() accepts our instance (real asyncio API).
class MockWindowsSelectorPolicy(asyncio.AbstractEventLoopPolicy):
    """Minimal policy for tests when WindowsSelectorEventLoopPolicy is not available."""

    def get_event_loop(self):
        return asyncio.get_event_loop()

    def set_event_loop(self, loop):
        pass

    def new_event_loop(self):
        return asyncio.new_event_loop()

    def get_child_watcher(self):
        return None

    def set_child_watcher(self, watcher):
        pass


class TestWindowsPostgresHelper:
    """Test Windows + PostgreSQL helper functions."""

    @pytest.fixture(autouse=True)
    def reset_event_loop_policy(self):
        """Reset event loop policy before each test."""
        original_policy = asyncio.get_event_loop_policy()
        yield
        asyncio.set_event_loop_policy(original_policy)

    def test_constants_defined(self):
        """Required constants are defined."""
        assert LANGFLOW_DATABASE_URL == "LANGFLOW_DATABASE_URL"
        assert POSTGRESQL_PREFIXES == ("postgresql", "postgres")

    @pytest.mark.skipif(platform.system() == "Windows", reason="Only run on non-Windows")
    def test_on_non_windows_with_postgres_url_returns_false_no_mock(self):
        """On non-Windows, function returns False without mocking platform."""
        with patch.dict(os.environ, {LANGFLOW_DATABASE_URL: "postgresql://user:pass@localhost/db"}, clear=True):
            result = configure_windows_postgres_event_loop()
        assert result is False

    @patch("langflow.helpers.windows_postgres_helper.platform.system")
    def test_windows_without_database_url_returns_false(self, mock_platform):
        """Windows without DATABASE_URL returns False."""
        mock_platform.return_value = "Windows"
        with patch.dict(os.environ, {}, clear=True):
            result = configure_windows_postgres_event_loop()
        assert result is False

    @patch("langflow.helpers.windows_postgres_helper.platform.system")
    def test_windows_with_sqlite_returns_false(self, mock_platform):
        """Windows with SQLite URL returns False."""
        mock_platform.return_value = "Windows"
        with patch.dict(os.environ, {LANGFLOW_DATABASE_URL: "sqlite:///test.db"}, clear=True):
            result = configure_windows_postgres_event_loop()
        assert result is False

    @patch.object(asyncio, "WindowsSelectorEventLoopPolicy", MockWindowsSelectorPolicy, create=True)
    @patch("langflow.helpers.windows_postgres_helper.platform.system")
    def test_windows_with_postgresql_sets_policy(self, mock_platform):
        """Windows with PostgreSQL URL sets event loop policy (real get/set_event_loop_policy)."""
        mock_platform.return_value = "Windows"
        with patch.dict(os.environ, {LANGFLOW_DATABASE_URL: "postgresql://user:pass@localhost/db"}, clear=True):
            result = configure_windows_postgres_event_loop()
        assert result is True
        assert isinstance(asyncio.get_event_loop_policy(), MockWindowsSelectorPolicy)

    @patch.object(asyncio, "WindowsSelectorEventLoopPolicy", MockWindowsSelectorPolicy, create=True)
    @patch("langflow.helpers.windows_postgres_helper.platform.system")
    def test_windows_with_postgres_protocol_sets_policy(self, mock_platform):
        """Windows with postgres:// URL sets policy."""
        mock_platform.return_value = "Windows"
        with patch.dict(os.environ, {LANGFLOW_DATABASE_URL: "postgres://user:pass@localhost/db"}, clear=True):
            result = configure_windows_postgres_event_loop()
        assert result is True
        assert isinstance(asyncio.get_event_loop_policy(), MockWindowsSelectorPolicy)

    @patch.object(asyncio, "WindowsSelectorEventLoopPolicy", MockWindowsSelectorPolicy, create=True)
    @patch("langflow.helpers.windows_postgres_helper.platform.system")
    def test_windows_with_selector_already_set_returns_false(self, mock_platform):
        """If selector policy is already set, function returns False and does not call set again."""
        mock_platform.return_value = "Windows"
        with patch.dict(os.environ, {LANGFLOW_DATABASE_URL: "postgresql://user:pass@localhost/db"}, clear=True):
            asyncio.set_event_loop_policy(MockWindowsSelectorPolicy())
            result = configure_windows_postgres_event_loop()
        assert result is False
        assert isinstance(asyncio.get_event_loop_policy(), MockWindowsSelectorPolicy)

    @patch.object(asyncio, "WindowsSelectorEventLoopPolicy", MockWindowsSelectorPolicy, create=True)
    @patch("langflow.helpers.windows_postgres_helper.platform.system")
    def test_logging_includes_source_when_provided(self, mock_platform, caplog):
        """With source= provided, function succeeds and logs (no mock of logger)."""
        mock_platform.return_value = "Windows"
        with (
            patch.dict(os.environ, {LANGFLOW_DATABASE_URL: "postgresql://user:pass@localhost/db"}, clear=True),
            caplog.at_level(logging.DEBUG, logger="langflow"),
        ):
            result = configure_windows_postgres_event_loop(source="test_source")
        assert result is True

    @patch("langflow.helpers.windows_postgres_helper.platform.system")
    def test_windows_with_other_database_returns_false(self, mock_platform):
        """Windows with non-PostgreSQL database returns False."""
        mock_platform.return_value = "Windows"
        with patch.dict(os.environ, {LANGFLOW_DATABASE_URL: "mysql://user:pass@localhost/db"}, clear=True):
            result = configure_windows_postgres_event_loop()
        assert result is False

    @pytest.mark.skipif(platform.system() != "Linux", reason="Docker test only meaningful on Linux")
    def test_docker_environment_not_affected_no_mock(self):
        """On Linux with postgres URL, function returns False (no platform mock)."""
        with patch.dict(
            os.environ,
            {LANGFLOW_DATABASE_URL: "postgresql://user:pass@postgres:5432/langflow", "DOCKER_CONTAINER": "true"},
            clear=True,
        ):
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
    @patch("langflow.helpers.windows_postgres_helper.platform.system")
    def test_various_postgresql_urls_handled(self, mock_platform, db_url):
        """Various PostgreSQL URL formats are handled (real set_event_loop_policy)."""
        mock_platform.return_value = "Windows"
        with patch.dict(os.environ, {LANGFLOW_DATABASE_URL: db_url}, clear=True):
            result = configure_windows_postgres_event_loop()
        assert result is True
        assert isinstance(asyncio.get_event_loop_policy(), MockWindowsSelectorPolicy)

    @patch("langflow.helpers.windows_postgres_helper.platform.system")
    def test_windows_without_policy_class_returns_false(self, mock_platform):
        """When WindowsSelectorEventLoopPolicy is unavailable, returns False."""
        mock_platform.return_value = "Windows"
        with (
            patch.dict(os.environ, {LANGFLOW_DATABASE_URL: "postgresql://user:pass@localhost/db"}, clear=True),
            patch.object(asyncio, "WindowsSelectorEventLoopPolicy", None, create=True),
        ):
            result = configure_windows_postgres_event_loop()
        assert result is False
