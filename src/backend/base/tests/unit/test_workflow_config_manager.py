"""Comprehensive unit tests for ConfigManager."""

import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open, Mock

import pytest
from pydantic import ValidationError

from langflow.cli.workflow.config.manager import ConfigManager, AIStudioConfig, GenesisConfig


class TestAIStudioConfig:
    """Test suite for AIStudioConfig model."""

    def test_ai_studio_config_defaults(self):
        """Test AIStudioConfig with default values."""
        config = AIStudioConfig()
        assert str(config.url) == "http://localhost:7860"
        assert config.api_key is None

    def test_ai_studio_config_custom_values(self):
        """Test AIStudioConfig with custom values."""
        config = AIStudioConfig(
            url="https://custom.ai-studio.com",
            api_key="test-api-key"
        )
        assert str(config.url) == "https://custom.ai-studio.com/"
        assert config.api_key == "test-api-key"

    def test_ai_studio_config_invalid_url(self):
        """Test AIStudioConfig with invalid URL."""
        with pytest.raises(ValidationError):
            AIStudioConfig(url="invalid-url")


class TestGenesisConfig:
    """Test suite for GenesisConfig model."""

    def test_genesis_config_defaults(self):
        """Test GenesisConfig with default values."""
        config = GenesisConfig()
        assert str(config.ai_studio.url) == "http://localhost:7860"
        assert config.default_project is None
        assert config.default_folder is None
        assert config.templates_path is None
        assert config.verbose is False

    def test_genesis_config_custom_values(self):
        """Test GenesisConfig with custom values."""
        config = GenesisConfig(
            ai_studio=AIStudioConfig(url="https://custom.com", api_key="key"),
            default_project="Test Project",
            default_folder="test-folder",
            templates_path=Path("/custom/templates"),
            verbose=True
        )
        assert str(config.ai_studio.url) == "https://custom.com/"
        assert config.ai_studio.api_key == "key"
        assert config.default_project == "Test Project"
        assert config.default_folder == "test-folder"
        assert config.templates_path == Path("/custom/templates")
        assert config.verbose is True


class TestConfigManager:
    """Test suite for ConfigManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = None

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir:
            # Clean up temp directory if created
            pass

    def test_init_creates_config_paths(self):
        """Test ConfigManager initialization creates proper paths."""
        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = Path("/tmp/test_home")

            manager = ConfigManager()

            assert manager.config_dir == Path("/tmp/test_home/.ai-studio")
            assert manager.config_file == Path("/tmp/test_home/.ai-studio/genesis-config.yaml")

    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="ai_studio:\n  url: http://test:8080\n  api_key: test-key")
    def test_load_config_from_file(self, mock_file, mock_exists):
        """Test loading configuration from file."""
        mock_exists.return_value = True

        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()

            assert str(manager.config.ai_studio.url) == "http://test:8080/"
            assert manager.config.ai_studio.api_key == "test-key"

    @patch('pathlib.Path.exists')
    def test_load_config_file_not_exists(self, mock_exists):
        """Test loading configuration when file doesn't exist."""
        mock_exists.return_value = False

        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()

            assert str(manager.config.ai_studio.url) == "http://localhost:7860"
            assert manager.config.ai_studio.api_key is None

    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="invalid: yaml: content: [")
    def test_load_config_invalid_yaml(self, mock_file, mock_exists):
        """Test loading configuration with invalid YAML."""
        mock_exists.return_value = True

        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()

            # Should fall back to defaults when YAML is invalid
            assert str(manager.config.ai_studio.url) == "http://localhost:7860"

    @patch.dict(os.environ, {
        'AI_STUDIO_URL': 'http://env-studio:9000',
        'AI_STUDIO_API_KEY': 'env-api-key',
        'GENESIS_DEFAULT_PROJECT': 'Env Project',
        'GENESIS_DEFAULT_FOLDER': 'env-folder',
        'GENESIS_TEMPLATES_PATH': '/env/templates',
        'GENESIS_VERBOSE': 'true'
    })
    @patch('pathlib.Path.exists')
    def test_load_from_environment(self, mock_exists):
        """Test loading configuration from environment variables."""
        mock_exists.return_value = False

        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()

            assert str(manager.config.ai_studio.url) == "http://env-studio:9000/"
            assert manager.config.ai_studio.api_key == "env-api-key"
            assert manager.config.default_project == "Env Project"
            assert manager.config.default_folder == "env-folder"
            assert str(manager.config.templates_path) == "/env/templates"
            assert manager.config.verbose is True

    @patch.dict(os.environ, {
        'LANGFLOW_URL': 'http://langflow:8080',
        'LANGFLOW_API_KEY': 'langflow-key',
        'GENESIS_API_KEY': 'genesis-key'
    })
    @patch('pathlib.Path.exists')
    def test_load_from_environment_alternative_vars(self, mock_exists):
        """Test loading from alternative environment variable names."""
        mock_exists.return_value = False

        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()

            assert str(manager.config.ai_studio.url) == "http://langflow:8080/"
            # genesis-key should override langflow-key due to precedence
            assert manager.config.ai_studio.api_key == "genesis-key"

    @patch('pathlib.Path.exists')
    def test_load_from_service(self, mock_exists):
        """Test loading configuration from running AI Studio service."""
        mock_exists.return_value = False

        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_settings = Mock()
            mock_settings.host = '0.0.0.0'
            mock_settings.port = 7860

            mock_service_instance = Mock()
            mock_service_instance.settings = mock_settings
            mock_service.return_value = mock_service_instance

            manager = ConfigManager()

            assert str(manager.config.ai_studio.url) == "http://localhost:7860"

    @patch('pathlib.Path.exists')
    def test_load_from_service_custom_host_port(self, mock_exists):
        """Test loading from service with custom host and port."""
        mock_exists.return_value = False

        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_settings = Mock()
            mock_settings.host = 'custom.host'
            mock_settings.port = 9000

            mock_service_instance = Mock()
            mock_service_instance.settings = mock_settings
            mock_service.return_value = mock_service_instance

            manager = ConfigManager()

            assert str(manager.config.ai_studio.url) == "http://custom.host:9000/"

    @patch('pathlib.Path.exists')
    def test_load_from_service_failure(self, mock_exists):
        """Test graceful handling when service is not available."""
        mock_exists.return_value = False

        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()

            # Should fall back to defaults
            assert str(manager.config.ai_studio.url) == "http://localhost:7860"

    def test_save_config(self):
        """Test saving configuration to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "genesis-config.yaml"

            with patch.object(ConfigManager, 'config_dir', config_dir), \
                 patch.object(ConfigManager, 'config_file', config_file), \
                 patch('langflow.services.deps.get_settings_service') as mock_service:

                mock_service.side_effect = Exception("Service not available")

                manager = ConfigManager()
                manager.config.ai_studio.url = "http://test:8080"
                manager.config.ai_studio.api_key = "test-key"
                manager.config.default_project = "Test Project"

                manager.save_config()

                assert config_file.exists()

                with open(config_file, 'r') as f:
                    saved_config = yaml.safe_load(f)

                assert saved_config['ai_studio']['url'] == "http://test:8080/"
                assert saved_config['ai_studio']['api_key'] == "test-key"
                assert saved_config['default_project'] == "Test Project"

    def test_get_config(self):
        """Test getting current configuration."""
        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()
            config = manager.get_config()

            assert isinstance(config, GenesisConfig)
            assert str(config.ai_studio.url) == "http://localhost:7860/"

    def test_get_config_reload(self):
        """Test get_config reloads if config is None."""
        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()
            manager.config = None

            config = manager.get_config()

            assert isinstance(config, GenesisConfig)
            assert manager.config is not None

    def test_update_config(self):
        """Test updating configuration values."""
        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()

            with patch.object(manager, 'save_config') as mock_save:
                manager.update_config(
                    default_project="New Project",
                    verbose=True,
                    ai_studio_url="http://new:8080",
                    ai_studio_api_key="new-key"
                )

                assert manager.config.default_project == "New Project"
                assert manager.config.verbose is True
                assert str(manager.config.ai_studio.url) == "http://new:8080/"
                assert manager.config.ai_studio.api_key == "new-key"
                mock_save.assert_called_once()

    def test_update_config_none_config(self):
        """Test update_config when config is None."""
        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()
            manager.config = None

            with patch.object(manager, 'save_config') as mock_save:
                manager.update_config(default_project="Test")

                assert manager.config is not None
                assert manager.config.default_project == "Test"
                mock_save.assert_called_once()

    def test_show_config(self):
        """Test configuration display formatting."""
        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()
            manager.config.ai_studio.api_key = "test-key"
            manager.config.default_project = "Test Project"

            output = manager.show_config()

            assert "Genesis CLI Configuration" in output
            assert "AI Studio URL: http://localhost:7860" in output
            assert "API Key: [Set]" in output
            assert "Default Project: Test Project" in output

    def test_show_config_no_api_key(self):
        """Test configuration display when no API key is set."""
        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()

            output = manager.show_config()

            assert "API Key: [Not Set]" in output

    def test_show_config_none_config(self):
        """Test show_config when config is None."""
        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()
            manager.config = None

            output = manager.show_config()

            assert "Genesis CLI Configuration" in output
            assert manager.config is not None

    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_import_genesis_agent_config_yaml(self, mock_file, mock_exists):
        """Test importing configuration from genesis-agent-cli YAML."""
        def exists_side_effect(path):
            return str(path).endswith('.genesis-agent.yaml')

        mock_exists.side_effect = exists_side_effect
        mock_file.return_value.read.return_value = """
genesis_studio:
  url: http://old-studio:8080
  api_key: old-api-key
"""

        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()

            with patch.object(manager, 'update_config') as mock_update:
                result = manager.import_genesis_agent_config()

                assert result is True
                mock_update.assert_called_once_with(
                    ai_studio_url="http://old-studio:8080",
                    ai_studio_api_key="old-api-key"
                )

    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_import_genesis_agent_config_env(self, mock_file, mock_exists):
        """Test importing configuration from .env file."""
        def exists_side_effect(path):
            return str(path).endswith('.env')

        mock_exists.side_effect = exists_side_effect
        mock_file.return_value.read.return_value = """
GENESIS_STUDIO_URL=http://env-studio:8080
GENESIS_STUDIO_API_KEY=env-api-key
# Comment line
GENESIS_API_KEY=env-genesis-key
OTHER_VAR=other_value
"""

        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()

            with patch.object(manager, 'update_config') as mock_update:
                result = manager.import_genesis_agent_config()

                assert result is True
                # Should be called multiple times for different env vars
                assert mock_update.call_count >= 1

    @patch('pathlib.Path.exists')
    def test_import_genesis_agent_config_no_files(self, mock_exists):
        """Test import when no config files exist."""
        mock_exists.return_value = False

        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()
            result = manager.import_genesis_agent_config()

            assert result is False

    @patch('pathlib.Path.exists')
    @patch('builtins.open', side_effect=Exception("File read error"))
    def test_import_genesis_agent_config_file_error(self, mock_file, mock_exists):
        """Test import graceful handling of file errors."""
        mock_exists.return_value = True

        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()
            result = manager.import_genesis_agent_config()

            assert result is False

    def test_ai_studio_url_property(self):
        """Test ai_studio_url property."""
        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()
            url = manager.ai_studio_url

            assert url == "http://localhost:7860/"

    def test_api_key_property(self):
        """Test api_key property."""
        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()
            manager.config.ai_studio.api_key = "test-key"

            api_key = manager.api_key
            assert api_key == "test-key"

    def test_api_key_property_none(self):
        """Test api_key property when no key is set."""
        with patch('langflow.services.deps.get_settings_service') as mock_service:
            mock_service.side_effect = Exception("Service not available")

            manager = ConfigManager()

            api_key = manager.api_key
            assert api_key is None


if __name__ == "__main__":
    pytest.main([__file__])