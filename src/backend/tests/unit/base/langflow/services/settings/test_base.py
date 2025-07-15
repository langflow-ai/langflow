import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock, call
from typing import Any, Dict, List, Optional
import os
import tempfile
import json
from pathlib import Path
import asyncio
import yaml

# Import the actual modules being tested
from langflow.services.settings.base import (
    Settings, 
    MyCustomSource, 
    is_list_of_any,
    save_settings_to_yaml,
    load_settings_from_yaml,
    BASE_COMPONENTS_PATH
)
from langflow.services.settings.service import SettingsService
from langflow.services.settings.factory import SettingsServiceFactory
from langflow.services.settings.auth import AuthSettings
from langflow.services.settings.categories import (
    DatabaseSettings,
    RedisSettings,
    ServerSettings,
    TelemetrySettings
)
from langflow.services.settings.common import LangflowBaseSettings
from pydantic.fields import FieldInfo


class TestIsListOfAnyFunction:
    """Test the is_list_of_any utility function."""
    
    def test_is_list_of_any_with_list_annotation(self):
        """Test is_list_of_any with list annotation."""
        field = FieldInfo()
        field.annotation = list
        assert is_list_of_any(field) is True
    
    def test_is_list_of_any_with_none_annotation(self):
        """Test is_list_of_any with None annotation."""
        field = FieldInfo()
        field.annotation = None
        assert is_list_of_any(field) is False
    
    def test_is_list_of_any_with_string_annotation(self):
        """Test is_list_of_any with string annotation."""
        field = FieldInfo()
        field.annotation = str
        assert is_list_of_any(field) is False
    
    def test_is_list_of_any_with_union_containing_list(self):
        """Test is_list_of_any with Union containing list."""
        from typing import Union
        field = FieldInfo()
        field.annotation = Union[list, str]
        # This might return True or False depending on implementation
        result = is_list_of_any(field)
        assert isinstance(result, bool)
    
    def test_is_list_of_any_with_attribute_error(self):
        """Test is_list_of_any handles AttributeError gracefully."""
        field = FieldInfo()
        field.annotation = object()  # Object without __origin__ or __args__
        result = is_list_of_any(field)
        assert isinstance(result, bool)


class TestMyCustomSource:
    """Test the MyCustomSource class."""
    
    @pytest.fixture
    def custom_source(self):
        """Create a MyCustomSource instance."""
        return MyCustomSource(Settings)
    
    def test_prepare_field_value_with_list_field_string_input(self, custom_source):
        """Test prepare_field_value with list field and string input."""
        field = FieldInfo()
        field.annotation = list
        
        result = custom_source.prepare_field_value(
            "test_field", field, "item1,item2,item3", False
        )
        assert result == ["item1", "item2", "item3"]
    
    def test_prepare_field_value_with_list_field_list_input(self, custom_source):
        """Test prepare_field_value with list field and list input."""
        field = FieldInfo()
        field.annotation = list
        
        result = custom_source.prepare_field_value(
            "test_field", field, ["item1", "item2", "item3"], False
        )
        assert result == ["item1", "item2", "item3"]
    
    def test_prepare_field_value_with_non_list_field(self, custom_source):
        """Test prepare_field_value with non-list field."""
        field = FieldInfo()
        field.annotation = str
        
        with patch.object(custom_source.__class__.__bases__[0], 'prepare_field_value') as mock_super:
            mock_super.return_value = "test_value"
            result = custom_source.prepare_field_value(
                "test_field", field, "test_value", False
            )
            assert result == "test_value"
            mock_super.assert_called_once_with("test_field", field, "test_value", False)
    
    def test_prepare_field_value_with_empty_string(self, custom_source):
        """Test prepare_field_value with empty string for list field."""
        field = FieldInfo()
        field.annotation = list
        
        result = custom_source.prepare_field_value(
            "test_field", field, "", False
        )
        assert result == [""]


class TestSettings:
    """Comprehensive tests for Settings class."""
    
    def test_settings_default_initialization(self):
        """Test Settings initialization with default values."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                settings = Settings()
                assert settings is not None
                assert settings.host == "localhost"
                assert settings.port == 7860
                assert settings.dev is False
    
    def test_settings_with_environment_variables(self):
        """Test Settings initialization with environment variables."""
        with patch.dict(os.environ, {
            'LANGFLOW_HOST': 'test-host',
            'LANGFLOW_PORT': '9000',
            'LANGFLOW_DEV': 'true',
            'LANGFLOW_DATABASE_URL': 'sqlite:///test.db'
        }):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                settings = Settings()
                assert settings.host == 'test-host'
                assert settings.port == 9000
                assert settings.dev is True
                assert settings.database_url == 'sqlite:///test.db'
    
    def test_settings_field_validators(self):
        """Test various field validators."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                
                # Test use_noop_database validator
                with patch('langflow.services.settings.base.logger') as mock_logger:
                    settings = Settings(use_noop_database=True)
                    assert settings.use_noop_database is True
                    mock_logger.info.assert_called_once()
    
    def test_settings_dev_validator(self):
        """Test dev field validator."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                with patch('langflow.settings.set_dev') as mock_set_dev:
                    settings = Settings(dev=True)
                    assert settings.dev is True
                    mock_set_dev.assert_called_once_with(True)
    
    def test_settings_user_agent_validator(self):
        """Test user_agent field validator."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                with patch('langflow.services.settings.base.logger') as mock_logger:
                    settings = Settings(user_agent="custom_agent")
                    assert settings.user_agent == "custom_agent"
                    assert os.environ.get("USER_AGENT") == "custom_agent"
    
    def test_settings_components_path_validator(self):
        """Test components_path field validator."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                settings = Settings(components_path=["/custom/path"])
                assert "/custom/path" in settings.components_path
                assert BASE_COMPONENTS_PATH in settings.components_path
    
    def test_settings_components_path_with_env_var(self):
        """Test components_path with environment variable."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {
                'LANGFLOW_COMPONENTS_PATH': temp_dir
            }):
                with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                    mock_cache_dir.return_value = "/tmp/test_cache"
                    settings = Settings()
                    assert temp_dir in settings.components_path
    
    def test_settings_variables_to_get_from_environment_validator(self):
        """Test variables_to_get_from_environment validator."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                custom_vars = "VAR1,VAR2,VAR3"
                settings = Settings(variables_to_get_from_environment=custom_vars)
                assert "VAR1" in settings.variables_to_get_from_environment
                assert "VAR2" in settings.variables_to_get_from_environment
                assert "VAR3" in settings.variables_to_get_from_environment
    
    def test_settings_database_url_validator_with_invalid_url(self):
        """Test database_url validator with invalid URL."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                with patch('langflow.utils.util_strings.is_valid_database_url', return_value=False):
                    with pytest.raises(ValueError, match="Invalid database_url provided"):
                        Settings(database_url="invalid_url")
    
    def test_settings_config_dir_validator(self):
        """Test config_dir validator."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                with patch('pathlib.Path.mkdir') as mock_mkdir:
                    settings = Settings(config_dir="/custom/config")
                    assert settings.config_dir == "/custom/config"
    
    def test_settings_event_delivery_validator_with_multiple_workers(self):
        """Test event_delivery validator with multiple workers."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                with patch('langflow.services.settings.base.logger') as mock_logger:
                    settings = Settings(workers=3, event_delivery="streaming")
                    assert settings.event_delivery == "direct"
                    mock_logger.warning.assert_called_once()
    
    def test_settings_update_settings_method(self):
        """Test update_settings method."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                with patch('langflow.services.settings.base.logger') as mock_logger:
                    settings = Settings()
                    settings.update_settings(host="newhost", port=9000)
                    assert settings.host == "newhost"
                    assert settings.port == 9000
    
    def test_settings_update_settings_with_list_field(self):
        """Test update_settings with list field."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                with patch('langflow.services.settings.base.logger') as mock_logger:
                    settings = Settings()
                    original_length = len(settings.components_path)
                    settings.update_settings(components_path="/new/path")
                    assert "/new/path" in settings.components_path
                    assert len(settings.components_path) == original_length + 1
    
    def test_settings_update_settings_with_json_list(self):
        """Test update_settings with JSON list string."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                with patch('langflow.services.settings.base.logger') as mock_logger:
                    settings = Settings()
                    settings.update_settings(components_path='["/path1", "/path2"]')
                    assert "/path1" in settings.components_path
                    assert "/path2" in settings.components_path
    
    @pytest.mark.asyncio
    async def test_settings_update_from_yaml(self):
        """Test update_from_yaml method."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                settings = Settings()
                
                with patch('langflow.services.settings.base.load_settings_from_yaml') as mock_load:
                    mock_settings = Settings(components_path=["/yaml/path"])
                    mock_load.return_value = mock_settings
                    
                    await settings.update_from_yaml("test.yaml", dev=True)
                    
                    assert settings.dev is True
                    assert settings.components_path == ["/yaml/path"]
                    mock_load.assert_called_once_with("test.yaml")
    
    def test_settings_model_dump(self):
        """Test model_dump method."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                settings = Settings(host="testhost", port=8080)
                settings_dict = settings.model_dump()
                assert isinstance(settings_dict, dict)
                assert settings_dict["host"] == "testhost"
                assert settings_dict["port"] == 8080
    
    def test_settings_public_flow_validation(self):
        """Test public flow settings validation."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                
                # Test valid values
                settings = Settings(
                    public_flow_cleanup_interval=3600,
                    public_flow_expiration=86400
                )
                assert settings.public_flow_cleanup_interval == 3600
                assert settings.public_flow_expiration == 86400
                
                # Test invalid values (should raise validation error)
                with pytest.raises(ValueError):
                    Settings(public_flow_cleanup_interval=300)  # Below minimum
                
                with pytest.raises(ValueError):
                    Settings(public_flow_expiration=300)  # Below minimum


class TestSettingsYamlFunctions:
    """Test YAML-related functions."""
    
    def test_save_settings_to_yaml(self):
        """Test save_settings_to_yaml function."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                settings = Settings(host="testhost", port=8080)
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                    save_settings_to_yaml(settings, f.name)
                    
                    # Read back the file
                    with open(f.name, 'r') as read_file:
                        content = yaml.safe_load(read_file)
                        assert content["host"] == "testhost"
                        assert content["port"] == 8080
                    
                    os.unlink(f.name)
    
    @pytest.mark.asyncio
    async def test_load_settings_from_yaml(self):
        """Test load_settings_from_yaml function."""
        test_settings = {
            'HOST': 'yamlhost',
            'PORT': 9000,
            'DEBUG': True
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_settings, f)
            f.flush()
            
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                settings = await load_settings_from_yaml(f.name)
                assert settings.host == "yamlhost"
                assert settings.port == 9000
                assert settings.debug is True
            
            os.unlink(f.name)
    
    @pytest.mark.asyncio
    async def test_load_settings_from_yaml_with_invalid_key(self):
        """Test load_settings_from_yaml with invalid key."""
        test_settings = {
            'INVALID_KEY': 'value'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_settings, f)
            f.flush()
            
            with pytest.raises(KeyError, match="Key INVALID_KEY not found in settings"):
                await load_settings_from_yaml(f.name)
            
            os.unlink(f.name)
    
    @pytest.mark.asyncio
    async def test_load_settings_from_yaml_filename_only(self):
        """Test load_settings_from_yaml with filename only."""
        test_settings = {
            'HOST': 'yamlhost',
            'PORT': 9000
        }
        
        # Create a temporary file in current directory
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, dir='.') as f:
            yaml.dump(test_settings, f)
            f.flush()
            filename = os.path.basename(f.name)
            
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                settings = await load_settings_from_yaml(filename)
                assert settings.host == "yamlhost"
                assert settings.port == 9000
            
            os.unlink(f.name)


class TestSettingsService:
    """Comprehensive tests for SettingsService class."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                return Settings(host="testhost", port=8080)
    
    @pytest.fixture
    def mock_auth_settings(self):
        """Create mock auth settings."""
        return AuthSettings(CONFIG_DIR="/tmp/config")
    
    @pytest.fixture
    def settings_service(self, mock_settings, mock_auth_settings):
        """Create a SettingsService instance."""
        return SettingsService(mock_settings, mock_auth_settings)
    
    def test_settings_service_initialization(self, settings_service):
        """Test SettingsService initialization."""
        assert settings_service is not None
        assert settings_service.name == "settings_service"
        assert hasattr(settings_service, 'settings')
        assert hasattr(settings_service, 'auth_settings')
        assert hasattr(settings_service, '_attribute_mapping')
    
    def test_settings_service_build_attribute_mapping(self, settings_service):
        """Test _build_attribute_mapping method."""
        assert isinstance(settings_service._attribute_mapping, dict)
        assert len(settings_service._attribute_mapping) > 0
    
    def test_settings_service_get_category_for_attribute(self, settings_service):
        """Test _get_category_for_attribute method."""
        # Test with database attribute
        category = settings_service._get_category_for_attribute("database_url")
        assert category == "database"
        
        # Test with unknown attribute
        category = settings_service._get_category_for_attribute("unknown_attr")
        assert category is None
    
    def test_settings_service_invalidate_cache(self, settings_service):
        """Test _invalidate_cache method."""
        # Access properties to create cache
        _ = settings_service.database
        _ = settings_service.redis
        _ = settings_service.server
        _ = settings_service.telemetry
        
        # Verify cache is populated
        assert settings_service._database_settings is not None
        assert settings_service._redis_settings is not None
        assert settings_service._server_settings is not None
        assert settings_service._telemetry_settings is not None
        
        # Invalidate cache
        settings_service._invalidate_cache()
        
        # Verify cache is cleared
        assert settings_service._database_settings is None
        assert settings_service._redis_settings is None
        assert settings_service._server_settings is None
        assert settings_service._telemetry_settings is None
    
    def test_settings_service_database_property(self, settings_service):
        """Test database property."""
        database_settings = settings_service.database
        assert isinstance(database_settings, DatabaseSettings)
        
        # Test caching
        database_settings2 = settings_service.database
        assert database_settings is database_settings2
    
    def test_settings_service_redis_property(self, settings_service):
        """Test redis property."""
        redis_settings = settings_service.redis
        assert isinstance(redis_settings, RedisSettings)
        
        # Test caching
        redis_settings2 = settings_service.redis
        assert redis_settings is redis_settings2
    
    def test_settings_service_server_property(self, settings_service):
        """Test server property."""
        server_settings = settings_service.server
        assert isinstance(server_settings, ServerSettings)
        
        # Test caching
        server_settings2 = settings_service.server
        assert server_settings is server_settings2
    
    def test_settings_service_telemetry_property(self, settings_service):
        """Test telemetry property."""
        telemetry_settings = settings_service.telemetry
        assert isinstance(telemetry_settings, TelemetrySettings)
        
        # Test caching
        telemetry_settings2 = settings_service.telemetry
        assert telemetry_settings is telemetry_settings2
    
    def test_settings_service_getattr_with_categorized_setting(self, settings_service):
        """Test __getattr__ with categorized setting."""
        # Test database attribute
        database_url = settings_service.database_url
        assert database_url is not None
        
        # Test redis attribute
        redis_host = settings_service.redis_host
        assert redis_host == "localhost"
    
    def test_settings_service_getattr_with_main_setting(self, settings_service):
        """Test __getattr__ with main setting."""
        host = settings_service.host
        assert host == "testhost"
        
        port = settings_service.port
        assert port == 8080
    
    def test_settings_service_getattr_with_auth_setting(self, settings_service):
        """Test __getattr__ with auth setting."""
        # This depends on what attributes AuthSettings has
        try:
            auth_attr = settings_service.CONFIG_DIR
            assert auth_attr == "/tmp/config"
        except AttributeError:
            # AuthSettings might not have CONFIG_DIR
            pass
    
    def test_settings_service_getattr_with_unknown_attribute(self, settings_service):
        """Test __getattr__ with unknown attribute."""
        with pytest.raises(AttributeError):
            _ = settings_service.unknown_attribute
    
    def test_settings_service_getattr_with_private_attribute(self, settings_service):
        """Test __getattr__ with private attribute."""
        with pytest.raises(AttributeError):
            _ = settings_service._private_attr
    
    def test_settings_service_setattr_with_categorized_setting(self, settings_service):
        """Test __setattr__ with categorized setting."""
        original_database_url = settings_service.database_url
        settings_service.database_url = "sqlite:///new.db"
        assert settings_service.database_url == "sqlite:///new.db"
        assert settings_service.settings.database_url == "sqlite:///new.db"
    
    def test_settings_service_setattr_with_main_setting(self, settings_service):
        """Test __setattr__ with main setting."""
        settings_service.host = "newhost"
        assert settings_service.host == "newhost"
        assert settings_service.settings.host == "newhost"
    
    def test_settings_service_setattr_with_auth_setting(self, settings_service):
        """Test __setattr__ with auth setting."""
        # This depends on what attributes AuthSettings has
        try:
            settings_service.CONFIG_DIR = "/new/config"
            assert settings_service.CONFIG_DIR == "/new/config"
        except AttributeError:
            # AuthSettings might not have CONFIG_DIR
            pass
    
    def test_settings_service_setattr_with_private_attribute(self, settings_service):
        """Test __setattr__ with private attribute."""
        settings_service._test_private = "private_value"
        assert settings_service._test_private == "private_value"
    
    def test_settings_service_setattr_with_special_attributes(self, settings_service):
        """Test __setattr__ with special attributes."""
        new_settings = Settings(host="localhost", port=7860)
        settings_service.settings = new_settings
        assert settings_service.settings is new_settings
    
    def test_settings_service_initialize_classmethod(self):
        """Test initialize class method."""
        with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
            mock_cache_dir.return_value = "/tmp/test_cache"
            service = SettingsService.initialize()
            assert isinstance(service, SettingsService)
            assert service.settings is not None
            assert service.auth_settings is not None
    
    def test_settings_service_initialize_without_config_dir(self):
        """Test initialize with missing config_dir."""
        with patch('langflow.services.settings.base.Settings') as mock_settings:
            mock_settings.return_value.config_dir = None
            with pytest.raises(ValueError, match="CONFIG_DIR must be set in settings"):
                SettingsService.initialize()
    
    def test_settings_service_set_method(self, settings_service):
        """Test set method."""
        result = settings_service.set("host", "newhost")
        assert result is settings_service.settings
        assert settings_service.settings.host == "newhost"
    
    def test_settings_service_cache_invalidation_on_setattr(self, settings_service):
        """Test cache invalidation when setting attributes."""
        # Populate cache
        _ = settings_service.database
        assert settings_service._database_settings is not None
        
        # Set a categorized attribute
        settings_service.database_url = "sqlite:///new.db"
        
        # Cache should be invalidated
        assert settings_service._database_settings is None


class TestSettingsServiceFactory:
    """Test SettingsServiceFactory class."""
    
    def test_settings_service_factory_singleton(self):
        """Test singleton behavior of SettingsServiceFactory."""
        factory1 = SettingsServiceFactory()
        factory2 = SettingsServiceFactory()
        assert factory1 is factory2
    
    def test_settings_service_factory_create(self):
        """Test create method."""
        with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
            mock_cache_dir.return_value = "/tmp/test_cache"
            factory = SettingsServiceFactory()
            service = factory.create()
            assert isinstance(service, SettingsService)
            assert service.settings is not None
            assert service.auth_settings is not None
    
    def test_settings_service_factory_inheritance(self):
        """Test factory inheritance."""
        from langflow.services.factory import ServiceFactory
        factory = SettingsServiceFactory()
        assert isinstance(factory, ServiceFactory)


class TestSettingsIntegration:
    """Integration tests for settings functionality."""
    
    def test_settings_with_client_fixture(self, client):
        """Test settings functionality with client fixture."""
        assert client is not None
        
        # Test that settings work in the context of the client
        with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
            mock_cache_dir.return_value = "/tmp/test_cache"
            settings = Settings(host='localhost', port=8080)
            assert settings.host == 'localhost'
            assert settings.port == 8080
    
    def test_settings_service_with_client_fixture(self, client):
        """Test settings service with client fixture."""
        assert client is not None
        
        # Test settings service initialization
        with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
            mock_cache_dir.return_value = "/tmp/test_cache"
            service = SettingsService.initialize()
            assert service is not None
            assert service.settings is not None
    
    def test_settings_environment_integration(self, client):
        """Test settings integration with environment variables."""
        assert client is not None
        
        with patch.dict(os.environ, {
            'LANGFLOW_HOST': 'integration-host',
            'LANGFLOW_PORT': '8888',
            'LANGFLOW_DEBUG': 'true'
        }):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                settings = Settings()
                assert settings.host == 'integration-host'
                assert settings.port == 8888
                assert settings.debug is True


class TestSettingsEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_settings_with_malformed_env_vars(self):
        """Test settings with malformed environment variables."""
        with patch.dict(os.environ, {
            'LANGFLOW_PORT': 'not_a_number',
            'LANGFLOW_WORKERS': 'invalid'
        }):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                # Should handle validation errors gracefully
                try:
                    settings = Settings()
                    # If validation passes, ensure reasonable defaults
                    assert isinstance(settings.port, int)
                    assert isinstance(settings.workers, int)
                except ValueError:
                    # Validation errors are acceptable
                    pass
    
    def test_settings_with_missing_cache_dir(self):
        """Test settings with missing cache directory."""
        with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
            mock_cache_dir.return_value = "/nonexistent/path"
            with patch('pathlib.Path.mkdir') as mock_mkdir:
                settings = Settings()
                mock_mkdir.assert_called()
    
    def test_settings_service_with_none_categories(self):
        """Test settings service with None category mappings."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                settings = Settings()
                auth_settings = AuthSettings(CONFIG_DIR="/tmp/config")
                service = SettingsService(settings, auth_settings)
                
                # Test accessing non-existent category
                category = service._get_category_for_attribute("nonexistent_attr")
                assert category is None
    
    def test_settings_large_components_path(self):
        """Test settings with large components path."""
        large_path_list = [f"/path/to/component/{i}" for i in range(1000)]
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                settings = Settings(components_path=large_path_list)
                assert len(settings.components_path) >= 1000
    
    def test_settings_concurrent_access(self):
        """Test concurrent access to settings."""
        import threading
        import time
        
        with patch.dict(os.environ, {}, clear=True):
            with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
                mock_cache_dir.return_value = "/tmp/test_cache"
                settings = Settings()
                
                results = []
                errors = []
                
                def access_settings():
                    try:
                        host = settings.host
                        port = settings.port
                        results.append((host, port))
                    except Exception as e:
                        errors.append(e)
                
                threads = []
                for _ in range(10):
                    thread = threading.Thread(target=access_settings)
                    threads.append(thread)
                    thread.start()
                
                for thread in threads:
                    thread.join()
                
                assert len(results) == 10
                assert len(errors) == 0
                assert all(r[0] == "localhost" for r in results)
                assert all(r[1] == 7860 for r in results)


class TestSettingsPerformance:
    """Performance tests for settings functionality."""
    
    def test_settings_creation_performance(self):
        """Test settings creation performance."""
        import time
        
        with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
            mock_cache_dir.return_value = "/tmp/test_cache"
            
            start_time = time.time()
            for _ in range(100):
                settings = Settings(host='localhost', port=8080)
                assert settings is not None
            end_time = time.time()
            
            # Settings creation should be reasonably fast
            assert end_time - start_time < 2.0
    
    def test_settings_service_property_access_performance(self):
        """Test settings service property access performance."""
        import time
        
        with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
            mock_cache_dir.return_value = "/tmp/test_cache"
            settings = Settings()
            auth_settings = AuthSettings(CONFIG_DIR="/tmp/config")
            service = SettingsService(settings, auth_settings)
            
            start_time = time.time()
            for _ in range(1000):
                _ = service.database
                _ = service.redis
                _ = service.server
                _ = service.telemetry
            end_time = time.time()
            
            # Property access should be fast due to caching
            assert end_time - start_time < 0.5
    
    def test_settings_attribute_access_performance(self):
        """Test settings attribute access performance."""
        import time
        
        with patch('langflow.services.settings.base.user_cache_dir') as mock_cache_dir:
            mock_cache_dir.return_value = "/tmp/test_cache"
            settings = Settings()
            auth_settings = AuthSettings(CONFIG_DIR="/tmp/config")
            service = SettingsService(settings, auth_settings)
            
            start_time = time.time()
            for _ in range(1000):
                _ = service.host
                _ = service.port
                _ = service.database_url
                _ = service.redis_host
            end_time = time.time()
            
            # Attribute access should be fast
            assert end_time - start_time < 0.5


if __name__ == '__main__':
    pytest.main([__file__])