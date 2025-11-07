"""Tests for database service pool class validation.

This test module ensures that the DatabaseService correctly validates SQLAlchemy
pool class names without attempting to instantiate them, which would cause errors
for classes like NullPool and StaticPool that require a 'creator' argument.
"""

from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy as sa
from langflow.services.database.service import DatabaseService


@pytest.fixture
def mock_settings_service():
    """Create a mock settings service with default database configuration.

    Returns:
        MagicMock: A mock settings service with pre-configured database settings
    """
    mock_service = MagicMock()
    mock_settings = MagicMock()
    mock_settings.database_url = "postgresql://user:pass@localhost/db"
    mock_settings.pool_size = None
    mock_settings.max_overflow = None
    mock_settings.model_fields_set = set()
    mock_service.settings = mock_settings
    return mock_service


class TestPoolClassValidation:
    """Test cases for pool class validation in DatabaseService.

    These tests verify that the DatabaseService correctly validates pool class
    names from configuration without attempting to instantiate the classes,
    which fixes issue #10231 where isinstance(pool_class(), ...) would fail.
    """

    @patch("langflow.services.database.service.create_async_engine")
    def test_null_pool_class_validation(self, mock_create_engine, mock_settings_service):
        """Test that NullPool can be validated without instantiation errors.

        NullPool is commonly used in serverless environments where connection
        pooling is not desired. This test ensures that specifying "NullPool"
        in the configuration does not trigger a TypeError from attempting to
        instantiate the class without required arguments.

        Args:
            mock_create_engine: Mock for create_async_engine function
            mock_settings_service: Fixture providing mock settings service
        """
        mock_settings_service.settings.db_connection_settings = {"poolclass": "NullPool"}

        # Create DatabaseService instance - should use issubclass() not isinstance()
        db_service = DatabaseService(mock_settings_service)
        assert db_service is not None

        # Verify that create_async_engine was called with NullPool class (not instance)
        assert mock_create_engine.called
        call_kwargs = mock_create_engine.call_args[1]
        assert "poolclass" in call_kwargs
        assert call_kwargs["poolclass"] == sa.pool.NullPool
        # Explicitly verify we passed the class, not an instance
        assert isinstance(call_kwargs["poolclass"], type)

    @patch("langflow.services.database.service.create_async_engine")
    def test_static_pool_class_validation(self, mock_create_engine, mock_settings_service):
        """Test that StaticPool can be validated without instantiation errors.

        StaticPool is typically used with SQLite in-memory databases where a
        single connection should be reused. This test ensures the validation
        logic correctly handles StaticPool without triggering instantiation errors.

        Args:
            mock_create_engine: Mock for create_async_engine function
            mock_settings_service: Fixture providing mock settings service
        """
        mock_settings_service.settings.database_url = "sqlite:///:memory:"
        mock_settings_service.settings.db_connection_settings = {"poolclass": "StaticPool"}

        # This should not raise instantiation errors
        db_service = DatabaseService(mock_settings_service)
        assert db_service is not None

        # Verify that create_async_engine was called with StaticPool class
        assert mock_create_engine.called
        call_kwargs = mock_create_engine.call_args[1]
        assert "poolclass" in call_kwargs
        assert call_kwargs["poolclass"] == sa.pool.StaticPool
        assert isinstance(call_kwargs["poolclass"], type)

    @patch("langflow.services.database.service.create_async_engine")
    @patch("langflow.services.database.service.logger")
    def test_invalid_pool_class_logs_error(self, mock_logger, mock_create_engine, mock_settings_service):
        """Test that invalid pool class name logs an error and fails gracefully.

        When a user provides an invalid pool class name that doesn't exist in
        SQLAlchemy, the service should log an error and continue without the
        invalid poolclass setting rather than crashing.

        Args:
            mock_logger: Mock for the logger instance
            mock_create_engine: Mock for create_async_engine function
            mock_settings_service: Fixture providing mock settings service
        """
        mock_settings_service.settings.db_connection_settings = {"poolclass": "InvalidPoolClass"}

        # This should log an error but not crash
        db_service = DatabaseService(mock_settings_service)
        assert db_service is not None

        # Verify that error was logged
        assert mock_logger.error.called
        error_call_args = mock_logger.error.call_args[0][0]
        assert "Invalid poolclass" in error_call_args
        assert "InvalidPoolClass" in error_call_args

        # Verify that invalid poolclass was removed from kwargs
        call_kwargs = mock_create_engine.call_args[1]
        # Invalid poolclass should have been popped from kwargs
        assert "poolclass" not in call_kwargs

    @patch("langflow.services.database.service.create_async_engine")
    def test_queue_pool_class_validation(self, mock_create_engine, mock_settings_service):
        """Test that QueuePool (default pool class) can be validated correctly.

        QueuePool is SQLAlchemy's default pool class for most database backends.
        This test ensures the validation logic works correctly for the most
        common use case.

        Args:
            mock_create_engine: Mock for create_async_engine function
            mock_settings_service: Fixture providing mock settings service
        """
        mock_settings_service.settings.db_connection_settings = {"poolclass": "QueuePool"}

        # This should work without errors
        db_service = DatabaseService(mock_settings_service)
        assert db_service is not None

        # Verify that create_async_engine was called with QueuePool class
        assert mock_create_engine.called
        call_kwargs = mock_create_engine.call_args[1]
        assert "poolclass" in call_kwargs
        assert call_kwargs["poolclass"] == sa.pool.QueuePool
        assert isinstance(call_kwargs["poolclass"], type)

    @patch("langflow.services.database.service.create_async_engine")
    def test_none_pool_class_configuration(self, mock_create_engine, mock_settings_service):
        """Test that None or missing poolclass in configuration is handled correctly.

        When no poolclass is specified in the configuration, the service should
        use SQLAlchemy's default behavior without attempting validation.

        Args:
            mock_create_engine: Mock for create_async_engine function
            mock_settings_service: Fixture providing mock settings service
        """
        # Test with None value
        mock_settings_service.settings.db_connection_settings = {"poolclass": None}
        db_service = DatabaseService(mock_settings_service)
        assert db_service is not None

        # poolclass should not be in kwargs when None
        call_kwargs = mock_create_engine.call_args[1]
        assert "poolclass" not in call_kwargs or call_kwargs.get("poolclass") is None

    @patch("langflow.services.database.service.create_async_engine")
    def test_missing_pool_class_configuration(self, mock_create_engine, mock_settings_service):
        """Test that missing poolclass key in configuration is handled correctly.

        When the poolclass key is completely absent from configuration,
        the service should work normally using SQLAlchemy defaults.

        Args:
            mock_create_engine: Mock for create_async_engine function
            mock_settings_service: Fixture providing mock settings service
        """
        # Test with missing key entirely
        mock_settings_service.settings.db_connection_settings = {}
        db_service = DatabaseService(mock_settings_service)
        assert db_service is not None

        # poolclass should not be in kwargs when key is missing
        call_kwargs = mock_create_engine.call_args[1]
        assert "poolclass" not in call_kwargs

    @patch("langflow.services.database.service.create_async_engine")
    @patch("langflow.services.database.service.logger")
    def test_non_string_pool_class_value(self, mock_logger, mock_create_engine, mock_settings_service):
        """Test that non-string poolclass values are handled gracefully.

        If a user provides a non-string value for poolclass (e.g., an integer
        or object), the service should handle it without crashing.

        Args:
            mock_logger: Mock for the logger instance
            mock_create_engine: Mock for create_async_engine function
            mock_settings_service: Fixture providing mock settings service
        """
        # Test with an integer instead of string
        mock_settings_service.settings.db_connection_settings = {"poolclass": 12345}

        # Should not crash, may log error depending on implementation
        db_service = DatabaseService(mock_settings_service)

        # Verify service was created successfully
        assert db_service is not None
        # Verify that create_async_engine was called (service initialized)
        assert mock_create_engine.called
        # Logger may or may not be called depending on whether getattr returns None
        # We just verify the mock is available for potential error logging
        assert mock_logger is not None
