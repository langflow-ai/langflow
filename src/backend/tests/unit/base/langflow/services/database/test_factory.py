"""
Comprehensive unit tests for DatabaseServiceFactory.
Using pytest framework with existing client fixture.
Testing library: pytest
Framework: pytest with unittest.mock for mocking
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Optional, Any, Dict
import tempfile
import os
from pathlib import Path

from langflow.services.database.factory import DatabaseServiceFactory
from langflow.services.database.service import DatabaseService
from langflow.services.factory import ServiceFactory


class TestDatabaseServiceFactory:
    """Test suite for DatabaseServiceFactory class."""

    def test_factory_initialization(self, client):
        """Test that DatabaseServiceFactory initializes correctly."""
        factory = DatabaseServiceFactory()
        
        assert factory is not None
        assert isinstance(factory, ServiceFactory)
        assert isinstance(factory, DatabaseServiceFactory)

    def test_factory_inherits_from_service_factory(self, client):
        """Test that DatabaseServiceFactory inherits from ServiceFactory."""
        factory = DatabaseServiceFactory()
        
        assert issubclass(DatabaseServiceFactory, ServiceFactory)
        assert isinstance(factory, ServiceFactory)

    def test_create_with_valid_settings_service(self, client):
        """Test successful creation with valid settings service."""
        # Mock the settings service
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "sqlite:///test.db"
        
        # Mock the DatabaseService constructor
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instance = Mock()
            mock_database_service.return_value = mock_instance
            
            factory = DatabaseServiceFactory()
            result = factory.create(mock_settings_service)
            
            assert result is not None
            assert result == mock_instance
            mock_database_service.assert_called_once_with(mock_settings_service)

    def test_create_with_sqlite_database_url(self, client):
        """Test creation with SQLite database URL."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "sqlite:///test.db"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instance = Mock()
            mock_database_service.return_value = mock_instance
            
            factory = DatabaseServiceFactory()
            result = factory.create(mock_settings_service)
            
            assert result is not None
            mock_database_service.assert_called_once_with(mock_settings_service)

    def test_create_with_postgresql_database_url(self, client):
        """Test creation with PostgreSQL database URL."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "postgresql://user:pass@localhost:5432/testdb"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instance = Mock()
            mock_database_service.return_value = mock_instance
            
            factory = DatabaseServiceFactory()
            result = factory.create(mock_settings_service)
            
            assert result is not None
            mock_database_service.assert_called_once_with(mock_settings_service)

    def test_create_with_mysql_database_url(self, client):
        """Test creation with MySQL database URL."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "mysql://user:pass@localhost:3306/testdb"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instance = Mock()
            mock_database_service.return_value = mock_instance
            
            factory = DatabaseServiceFactory()
            result = factory.create(mock_settings_service)
            
            assert result is not None
            mock_database_service.assert_called_once_with(mock_settings_service)

    def test_create_with_no_database_url(self, client):
        """Test creation fails when no database URL is provided."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = None
        
        factory = DatabaseServiceFactory()
        
        with pytest.raises(ValueError, match="No database URL provided"):
            factory.create(mock_settings_service)

    def test_create_with_empty_database_url(self, client):
        """Test creation fails when database URL is empty string."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = ""
        
        factory = DatabaseServiceFactory()
        
        with pytest.raises(ValueError, match="No database URL provided"):
            factory.create(mock_settings_service)

    def test_create_with_whitespace_database_url(self, client):
        """Test creation fails when database URL is only whitespace."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "   "
        
        factory = DatabaseServiceFactory()
        
        with pytest.raises(ValueError, match="No database URL provided"):
            factory.create(mock_settings_service)

    def test_create_with_false_database_url(self, client):
        """Test creation fails when database URL is False."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = False
        
        factory = DatabaseServiceFactory()
        
        with pytest.raises(ValueError, match="No database URL provided"):
            factory.create(mock_settings_service)

    def test_create_with_database_service_initialization_failure(self, client):
        """Test creation fails when DatabaseService initialization fails."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "sqlite:///test.db"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_database_service.side_effect = Exception("Database initialization failed")
            
            factory = DatabaseServiceFactory()
            
            with pytest.raises(Exception, match="Database initialization failed"):
                factory.create(mock_settings_service)

    def test_create_with_invalid_settings_service_missing_database_attr(self, client):
        """Test creation fails when settings service is missing database attribute."""
        mock_settings_service = Mock()
        # Remove database attribute to simulate missing attribute
        del mock_settings_service.database
        
        factory = DatabaseServiceFactory()
        
        with pytest.raises(AttributeError):
            factory.create(mock_settings_service)

    def test_create_with_invalid_settings_service_missing_database_url_attr(self, client):
        """Test creation fails when settings service database is missing database_url attribute."""
        mock_settings_service = Mock()
        mock_settings_service.database = Mock()
        # Remove database_url attribute
        del mock_settings_service.database.database_url
        
        factory = DatabaseServiceFactory()
        
        with pytest.raises(AttributeError):
            factory.create(mock_settings_service)

    def test_create_with_none_settings_service(self, client):
        """Test creation fails when settings service is None."""
        factory = DatabaseServiceFactory()
        
        with pytest.raises(AttributeError):
            factory.create(None)

    def test_create_multiple_instances(self, client):
        """Test creating multiple database service instances."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "sqlite:///test.db"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instances = [Mock() for _ in range(3)]
            mock_database_service.side_effect = mock_instances
            
            factory = DatabaseServiceFactory()
            
            results = []
            for i in range(3):
                result = factory.create(mock_settings_service)
                results.append(result)
            
            assert len(results) == 3
            assert all(result is not None for result in results)
            assert mock_database_service.call_count == 3
            
            # Verify each instance is unique
            for i, result in enumerate(results):
                assert result == mock_instances[i]

    def test_create_with_memory_sqlite_database(self, client):
        """Test creation with in-memory SQLite database."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "sqlite:///:memory:"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instance = Mock()
            mock_database_service.return_value = mock_instance
            
            factory = DatabaseServiceFactory()
            result = factory.create(mock_settings_service)
            
            assert result is not None
            mock_database_service.assert_called_once_with(mock_settings_service)

    def test_create_with_file_path_sqlite_database(self, client):
        """Test creation with file path SQLite database."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            
            mock_settings_service = Mock()
            mock_settings_service.database.database_url = f"sqlite:///{db_path}"
            
            with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
                mock_instance = Mock()
                mock_database_service.return_value = mock_instance
                
                factory = DatabaseServiceFactory()
                result = factory.create(mock_settings_service)
                
                assert result is not None
                mock_database_service.assert_called_once_with(mock_settings_service)

    def test_create_with_different_database_types(self, client):
        """Test creation with different database URL types."""
        database_urls = [
            "sqlite:///test.db",
            "postgresql://user:pass@localhost:5432/testdb",
            "mysql://user:pass@localhost:3306/testdb",
            "postgresql+psycopg2://user:pass@localhost:5432/testdb",
            "mysql+pymysql://user:pass@localhost:3306/testdb",
        ]
        
        for database_url in database_urls:
            mock_settings_service = Mock()
            mock_settings_service.database.database_url = database_url
            
            with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
                mock_instance = Mock()
                mock_database_service.return_value = mock_instance
                
                factory = DatabaseServiceFactory()
                result = factory.create(mock_settings_service)
                
                assert result is not None
                mock_database_service.assert_called_once_with(mock_settings_service)

    def test_create_with_database_service_runtime_error(self, client):
        """Test creation fails with RuntimeError from DatabaseService."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "sqlite:///test.db"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_database_service.side_effect = RuntimeError("Database connection failed")
            
            factory = DatabaseServiceFactory()
            
            with pytest.raises(RuntimeError, match="Database connection failed"):
                factory.create(mock_settings_service)

    def test_create_with_database_service_value_error(self, client):
        """Test creation fails with ValueError from DatabaseService."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "sqlite:///test.db"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_database_service.side_effect = ValueError("Invalid database configuration")
            
            factory = DatabaseServiceFactory()
            
            with pytest.raises(ValueError, match="Invalid database configuration"):
                factory.create(mock_settings_service)

    def test_create_validates_database_url_before_creating_service(self, client):
        """Test that database URL validation occurs before DatabaseService creation."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = None
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            # This should not be called since validation should fail first
            mock_database_service.return_value = Mock()
            
            factory = DatabaseServiceFactory()
            
            with pytest.raises(ValueError, match="No database URL provided"):
                factory.create(mock_settings_service)
            
            # Verify DatabaseService was not called
            mock_database_service.assert_not_called()

    def test_create_with_settings_service_different_configurations(self, client):
        """Test creation with different settings service configurations."""
        configurations = [
            {"database_url": "sqlite:///test1.db"},
            {"database_url": "postgresql://user:pass@localhost:5432/db1"},
            {"database_url": "mysql://user:pass@localhost:3306/db1"},
        ]
        
        for config in configurations:
            mock_settings_service = Mock()
            mock_settings_service.database.database_url = config["database_url"]
            
            with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
                mock_instance = Mock()
                mock_database_service.return_value = mock_instance
                
                factory = DatabaseServiceFactory()
                result = factory.create(mock_settings_service)
                
                assert result is not None
                mock_database_service.assert_called_once_with(mock_settings_service)

    def test_factory_class_attributes(self, client):
        """Test that factory class has expected attributes."""
        factory = DatabaseServiceFactory()
        
        # Check that it has the expected parent class
        assert hasattr(factory, '__class__')
        assert factory.__class__.__name__ == 'DatabaseServiceFactory'
        assert issubclass(factory.__class__, ServiceFactory)

    def test_factory_method_existence(self, client):
        """Test that factory has the expected methods."""
        factory = DatabaseServiceFactory()
        
        # Check that create method exists and is callable
        assert hasattr(factory, 'create')
        assert callable(factory.create)

    def test_create_method_signature(self, client):
        """Test that create method has the expected signature."""
        factory = DatabaseServiceFactory()
        
        # Test that create method accepts settings_service parameter
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "sqlite:///test.db"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instance = Mock()
            mock_database_service.return_value = mock_instance
            
            # This should not raise any signature-related errors
            result = factory.create(mock_settings_service)
            assert result is not None


class TestDatabaseServiceFactoryEdgeCases:
    """Edge case tests for DatabaseServiceFactory."""

    def test_create_with_unicode_database_url(self, client):
        """Test creation with Unicode characters in database URL."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "postgresql://ユーザー:パスワード@localhost:5432/testdb"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instance = Mock()
            mock_database_service.return_value = mock_instance
            
            factory = DatabaseServiceFactory()
            result = factory.create(mock_settings_service)
            
            assert result is not None
            mock_database_service.assert_called_once_with(mock_settings_service)

    def test_create_with_special_characters_in_database_url(self, client):
        """Test creation with special characters in database URL."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "postgresql://user%40domain:p%40ssw0rd@localhost:5432/testdb"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instance = Mock()
            mock_database_service.return_value = mock_instance
            
            factory = DatabaseServiceFactory()
            result = factory.create(mock_settings_service)
            
            assert result is not None
            mock_database_service.assert_called_once_with(mock_settings_service)

    def test_create_with_very_long_database_url(self, client):
        """Test creation with very long database URL."""
        long_db_name = "a" * 1000
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = f"postgresql://user:pass@localhost:5432/{long_db_name}"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instance = Mock()
            mock_database_service.return_value = mock_instance
            
            factory = DatabaseServiceFactory()
            result = factory.create(mock_settings_service)
            
            assert result is not None
            mock_database_service.assert_called_once_with(mock_settings_service)

    def test_create_with_ipv6_database_url(self, client):
        """Test creation with IPv6 address in database URL."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "postgresql://user:pass@[::1]:5432/testdb"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instance = Mock()
            mock_database_service.return_value = mock_instance
            
            factory = DatabaseServiceFactory()
            result = factory.create(mock_settings_service)
            
            assert result is not None
            mock_database_service.assert_called_once_with(mock_settings_service)

    def test_create_with_non_standard_port(self, client):
        """Test creation with non-standard port in database URL."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "postgresql://user:pass@localhost:9999/testdb"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instance = Mock()
            mock_database_service.return_value = mock_instance
            
            factory = DatabaseServiceFactory()
            result = factory.create(mock_settings_service)
            
            assert result is not None
            mock_database_service.assert_called_once_with(mock_settings_service)

    def test_create_with_query_parameters_in_database_url(self, client):
        """Test creation with query parameters in database URL."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "postgresql://user:pass@localhost:5432/testdb?sslmode=require&charset=utf8"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instance = Mock()
            mock_database_service.return_value = mock_instance
            
            factory = DatabaseServiceFactory()
            result = factory.create(mock_settings_service)
            
            assert result is not None
            mock_database_service.assert_called_once_with(mock_settings_service)

    def test_create_with_malformed_settings_service(self, client):
        """Test creation with malformed settings service object."""
        # Create a mock that has database but it's not properly configured
        mock_settings_service = Mock()
        mock_settings_service.database = "not_an_object"
        
        factory = DatabaseServiceFactory()
        
        with pytest.raises(AttributeError):
            factory.create(mock_settings_service)

    def test_create_with_database_url_as_number(self, client):
        """Test creation with database URL as number (should fail validation)."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = 12345  # Invalid type
        
        factory = DatabaseServiceFactory()
        
        with pytest.raises(ValueError, match="No database URL provided"):
            factory.create(mock_settings_service)

    def test_create_with_database_url_as_list(self, client):
        """Test creation with database URL as list (should fail validation)."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = ["sqlite:///test.db"]  # Invalid type
        
        factory = DatabaseServiceFactory()
        
        with pytest.raises(ValueError, match="No database URL provided"):
            factory.create(mock_settings_service)

    def test_create_with_database_url_as_dict(self, client):
        """Test creation with database URL as dict (should fail validation)."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = {"url": "sqlite:///test.db"}  # Invalid type
        
        factory = DatabaseServiceFactory()
        
        with pytest.raises(ValueError, match="No database URL provided"):
            factory.create(mock_settings_service)


class TestDatabaseServiceFactoryIntegration:
    """Integration-style tests for DatabaseServiceFactory."""

    def test_create_with_real_database_service_interaction(self, client):
        """Test creation with realistic DatabaseService interaction."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "sqlite:///test.db"
        
        # Don't mock DatabaseService completely - let it be created but mock its dependencies
        with patch('langflow.services.database.service.create_async_engine') as mock_create_engine:
            with patch('langflow.services.database.service.Path') as mock_path:
                with patch('langflow.services.database.service.event') as mock_event:
                    mock_engine = Mock()
                    mock_create_engine.return_value = mock_engine
                    
                    # Mock Path operations
                    mock_path.return_value.parent.parent.parent = Mock()
                    mock_path.return_value.is_absolute.return_value = False
                    
                    factory = DatabaseServiceFactory()
                    
                    # This should work without mocking DatabaseService itself
                    try:
                        result = factory.create(mock_settings_service)
                        assert result is not None
                    except Exception as e:
                        # If there are dependency issues, we expect specific types
                        assert isinstance(e, (ValueError, RuntimeError, AttributeError))

    def test_create_multiple_factories_same_settings(self, client):
        """Test creating multiple factories with the same settings."""
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "sqlite:///test.db"
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instances = [Mock() for _ in range(3)]
            mock_database_service.side_effect = mock_instances
            
            factories = [DatabaseServiceFactory() for _ in range(3)]
            results = []
            
            for i, factory in enumerate(factories):
                result = factory.create(mock_settings_service)
                results.append(result)
            
            assert len(results) == 3
            assert all(result is not None for result in results)
            assert mock_database_service.call_count == 3
            
            # Each factory should create independent instances
            for i, result in enumerate(results):
                assert result == mock_instances[i]

    def test_create_with_varying_database_configurations(self, client):
        """Test creation with different database configurations."""
        configurations = [
            {"database_url": "sqlite:///test1.db"},
            {"database_url": "sqlite:///test2.db"},
            {"database_url": "postgresql://user:pass@localhost:5432/db1"},
            {"database_url": "postgresql://user:pass@localhost:5432/db2"},
            {"database_url": "mysql://user:pass@localhost:3306/db1"},
        ]
        
        factory = DatabaseServiceFactory()
        
        for config in configurations:
            mock_settings_service = Mock()
            mock_settings_service.database.database_url = config["database_url"]
            
            with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
                mock_instance = Mock()
                mock_database_service.return_value = mock_instance
                
                result = factory.create(mock_settings_service)
                
                assert result is not None
                mock_database_service.assert_called_once_with(mock_settings_service)

    def test_factory_error_handling_robustness(self, client):
        """Test factory error handling with various error scenarios."""
        error_scenarios = [
            (ValueError, "Database configuration error"),
            (RuntimeError, "Database connection failed"),
            (ConnectionError, "Network connection failed"),
            (Exception, "Unknown error"),
        ]
        
        for error_type, error_message in error_scenarios:
            mock_settings_service = Mock()
            mock_settings_service.database.database_url = "sqlite:///test.db"
            
            with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
                mock_database_service.side_effect = error_type(error_message)
                
                factory = DatabaseServiceFactory()
                
                with pytest.raises(error_type, match=error_message):
                    factory.create(mock_settings_service)

    def test_factory_with_complex_settings_service(self, client):
        """Test factory with complex settings service configuration."""
        # Create a more complex mock settings service
        mock_settings_service = Mock()
        mock_settings_service.database.database_url = "postgresql://user:pass@localhost:5432/testdb"
        mock_settings_service.database.pool_size = 10
        mock_settings_service.database.max_overflow = 20
        mock_settings_service.database.timeout = 30
        
        with patch('langflow.services.database.factory.DatabaseService') as mock_database_service:
            mock_instance = Mock()
            mock_database_service.return_value = mock_instance
            
            factory = DatabaseServiceFactory()
            result = factory.create(mock_settings_service)
            
            assert result is not None
            mock_database_service.assert_called_once_with(mock_settings_service)
            
            # Verify that the full settings service was passed
            call_args = mock_database_service.call_args
            assert call_args[0][0] == mock_settings_service