"""Tests for database service pool class validation."""

from unittest.mock import MagicMock, patch

import sqlalchemy as sa
from langflow.services.database.service import DatabaseService


class TestPoolClassValidation:
    """Test cases for pool class validation in DatabaseService."""

    @patch("langflow.services.database.service.create_async_engine")
    def test_null_pool_class_validation(self, mock_create_engine):
        """Test that NullPool can be validated without instantiation errors."""
        # Create a mock settings service
        mock_settings_service = MagicMock()
        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql://user:pass@localhost/db"
        mock_settings.db_connection_settings = {"poolclass": "NullPool"}
        mock_settings.pool_size = None
        mock_settings.max_overflow = None
        mock_settings.model_fields_set = set()
        mock_settings_service.settings = mock_settings

        # Create DatabaseService instance
        # This should not raise "Pool.__init__() missing 1 required positional argument: 'creator'"
        db_service = DatabaseService(mock_settings_service)

        # Verify that create_async_engine was called with NullPool class
        assert mock_create_engine.called
        call_kwargs = mock_create_engine.call_args[1]
        assert "poolclass" in call_kwargs
        assert call_kwargs["poolclass"] == sa.pool.NullPool

    @patch("langflow.services.database.service.create_async_engine")
    def test_static_pool_class_validation(self, mock_create_engine):
        """Test that StaticPool can be validated without instantiation errors."""
        mock_settings_service = MagicMock()
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///:memory:"
        mock_settings.db_connection_settings = {"poolclass": "StaticPool"}
        mock_settings.pool_size = None
        mock_settings.max_overflow = None
        mock_settings.model_fields_set = set()
        mock_settings_service.settings = mock_settings

        # This should not raise instantiation errors
        db_service = DatabaseService(mock_settings_service)

        # Verify that create_async_engine was called with StaticPool class
        assert mock_create_engine.called
        call_kwargs = mock_create_engine.call_args[1]
        assert "poolclass" in call_kwargs
        assert call_kwargs["poolclass"] == sa.pool.StaticPool

    @patch("langflow.services.database.service.create_async_engine")
    @patch("langflow.services.database.service.logger")
    def test_invalid_pool_class_logs_error(self, mock_logger, mock_create_engine):
        """Test that invalid pool class name logs an error."""
        mock_settings_service = MagicMock()
        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql://user:pass@localhost/db"
        mock_settings.db_connection_settings = {"poolclass": "InvalidPoolClass"}
        mock_settings.pool_size = None
        mock_settings.max_overflow = None
        mock_settings.model_fields_set = set()
        mock_settings_service.settings = mock_settings

        # This should log an error but not crash
        db_service = DatabaseService(mock_settings_service)

        # Verify that error was logged
        assert mock_logger.error.called
        error_call_args = mock_logger.error.call_args[0][0]
        assert "Invalid poolclass" in error_call_args
        assert "InvalidPoolClass" in error_call_args

        # Verify that poolclass was NOT passed to create_async_engine
        call_kwargs = mock_create_engine.call_args[1]
        # The invalid poolclass should not be in the kwargs, or if it is, it should be the string not a class
        if "poolclass" in call_kwargs:
            assert call_kwargs["poolclass"] == "InvalidPoolClass"

    @patch("langflow.services.database.service.create_async_engine")
    def test_queue_pool_class_validation(self, mock_create_engine):
        """Test that QueuePool (default) can be validated."""
        mock_settings_service = MagicMock()
        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql://user:pass@localhost/db"
        mock_settings.db_connection_settings = {"poolclass": "QueuePool"}
        mock_settings.pool_size = None
        mock_settings.max_overflow = None
        mock_settings.model_fields_set = set()
        mock_settings_service.settings = mock_settings

        # This should work without errors
        db_service = DatabaseService(mock_settings_service)

        # Verify that create_async_engine was called with QueuePool class
        assert mock_create_engine.called
        call_kwargs = mock_create_engine.call_args[1]
        assert "poolclass" in call_kwargs
        assert call_kwargs["poolclass"] == sa.pool.QueuePool
