"""Tests for poolclass resolution in DatabaseService."""

from unittest.mock import patch

import sqlalchemy as sa
from langflow.services.database.service import DatabaseService
from sqlalchemy.pool import NullPool, QueuePool, StaticPool


class TestDatabaseServicePoolclassResolution:
    """Test the _resolve_poolclass method in DatabaseService."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a minimal DatabaseService instance without triggering engine creation
        self.db_service = DatabaseService.__new__(DatabaseService)
        self.db_service.database_url = "sqlite:///:memory:"

    def test_resolve_poolclass_string_names(self):
        """Test that string pool class names resolve correctly."""
        assert self.db_service._resolve_poolclass("NullPool") is NullPool
        assert self.db_service._resolve_poolclass("StaticPool") is StaticPool
        assert self.db_service._resolve_poolclass("QueuePool") is QueuePool

    def test_resolve_poolclass_class_objects(self):
        """Test that pool class objects are accepted directly."""
        assert self.db_service._resolve_poolclass(NullPool) is NullPool
        assert self.db_service._resolve_poolclass(StaticPool) is StaticPool
        assert self.db_service._resolve_poolclass(QueuePool) is QueuePool

    def test_resolve_poolclass_full_module_paths(self):
        """Test that full module paths resolve correctly."""
        assert self.db_service._resolve_poolclass("sqlalchemy.pool.NullPool") is NullPool
        assert self.db_service._resolve_poolclass("sqlalchemy.pool.StaticPool") is StaticPool
        assert self.db_service._resolve_poolclass("sqlalchemy.pool.QueuePool") is QueuePool

    def test_resolve_poolclass_invalid_string(self):
        """Test that invalid string names return None."""
        assert self.db_service._resolve_poolclass("InvalidPool") is None
        assert self.db_service._resolve_poolclass("NonExistentPool") is None

    def test_resolve_poolclass_invalid_module_path(self):
        """Test that invalid module paths return None."""
        assert self.db_service._resolve_poolclass("nonexistent.module.Pool") is None
        assert self.db_service._resolve_poolclass("sqlalchemy.invalid.Pool") is None

    def test_resolve_poolclass_non_string_non_type(self):
        """Test that non-string, non-type values return None."""
        assert self.db_service._resolve_poolclass(123) is None
        assert self.db_service._resolve_poolclass([]) is None
        assert self.db_service._resolve_poolclass({}) is None
        assert self.db_service._resolve_poolclass(None) is None

    def test_resolve_poolclass_non_pool_class(self):
        """Test that non-pool classes return None."""

        class NotAPool:
            pass

        assert self.db_service._resolve_poolclass(NotAPool) is None

    def test_resolve_poolclass_builtin_types(self):
        """Test that builtin types return None."""
        assert self.db_service._resolve_poolclass(str) is None
        assert self.db_service._resolve_poolclass(int) is None
        assert self.db_service._resolve_poolclass(list) is None


def test_pool_classes_available_in_sqlalchemy():
    """Test that the pool classes we expect are actually available in sqlalchemy."""
    # This is a sanity check to ensure our assumptions are correct
    assert hasattr(sa, "NullPool")
    assert hasattr(sa, "StaticPool")
    assert hasattr(sa, "QueuePool")

    # Verify they are actually pool classes
    assert issubclass(sa.NullPool, sa.pool.Pool)
    assert issubclass(sa.StaticPool, sa.pool.Pool)
    assert issubclass(sa.QueuePool, sa.pool.Pool)


@patch("langflow.services.database.service.create_async_engine")
def test_poolclass_integration_with_create_engine(mock_create_engine):
    """Test that poolclass resolution integrates correctly with create_async_engine."""
    # Create a minimal service instance
    service = DatabaseService.__new__(DatabaseService)
    service.database_url = "sqlite:///:memory:"

    # Mock _build_connection_kwargs to return specific poolclass
    with (
        patch.object(service, "_build_connection_kwargs", return_value={"poolclass": "NullPool"}),
        patch.object(service, "_get_connect_args", return_value={}),
    ):
        service._create_engine()

    # Verify create_async_engine was called with NullPool class
    mock_create_engine.assert_called_once()
    call_kwargs = mock_create_engine.call_args[1]
    assert call_kwargs["poolclass"] is NullPool


@patch("langflow.services.database.service.create_async_engine")
@patch("langflow.services.database.service.logger")
def test_poolclass_error_handling(mock_logger, mock_create_engine):
    """Test that invalid poolclass values are handled gracefully."""
    # Create a minimal service instance
    service = DatabaseService.__new__(DatabaseService)
    service.database_url = "sqlite:///:memory:"

    # Test with invalid poolclass
    with (
        patch.object(service, "_build_connection_kwargs", return_value={"poolclass": "InvalidPool"}),
        patch.object(service, "_get_connect_args", return_value={}),
    ):
        service._create_engine()

    # Should log error
    mock_logger.error.assert_called_once()
    assert "Invalid poolclass 'InvalidPool' specified" in mock_logger.error.call_args[0][0]

    # Should call create_async_engine without poolclass
    mock_create_engine.assert_called_once()
    call_kwargs = mock_create_engine.call_args[1]
    assert "poolclass" not in call_kwargs
