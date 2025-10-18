"""Unit tests for the ConfigManager class."""

import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import pytest

from langflow.cli.workflow.config.manager import ConfigManager, AIStudioConfig, GenesisConfig


class TestAIStudioConfig:
    """Test the AIStudioConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AIStudioConfig()
        assert str(config.url) == "http://localhost:7860"
        assert config.api_key is None

    def test_custom_values(self):
        """Test configuration with custom values."""
        config = AIStudioConfig(
            url="https://studio.example.com",
            api_key="test-key"
        )
        assert str(config.url) == "https://studio.example.com/"
        assert config.api_key == "test-key"


class TestGenesisConfig:
    """Test the GenesisConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = GenesisConfig()
        assert "localhost" in str(config.ai_studio.url)
        assert config.default_project is None
        assert config.default_folder is None
        assert config.templates_path is None
        assert config.verbose is False

    def test_custom_values(self):
        """Test configuration with custom values."""
        config = GenesisConfig(
            default_project="Test Project",
            default_folder="test-folder",
            verbose=True
        )
        assert config.default_project == "Test Project"
        assert config.default_folder == "test-folder"
        assert config.verbose is True


class TestConfigManager:
    """Test the ConfigManager class."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / ".ai-studio"
        self.config_file = self.config_dir / "genesis-config.yaml"

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_init_creates_config_paths(self, mock_home):
        """Test ConfigManager initialization creates correct paths."""
        mock_home.return_value = Path(self.temp_dir)

        with patch.object(ConfigManager, '_load_config'):
            manager = ConfigManager()

        assert manager.config_dir == Path(self.temp_dir) / ".ai-studio"
        assert manager.config_file == Path(self.temp_dir) / ".ai-studio" / "genesis-config.yaml"

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_ensure_config_dir_creates_directory(self, mock_home):
        """Test _ensure_config_dir creates configuration directory."""
        mock_home.return_value = Path(self.temp_dir)

        with patch.object(ConfigManager, '_load_config'):
            manager = ConfigManager()

        manager._ensure_config_dir()
        assert manager.config_dir.exists()

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_load_config_from_file(self, mock_home):
        """Test loading configuration from existing file."""
        mock_home.return_value = Path(self.temp_dir)

        # Create config data
        config_data = {
            "ai_studio": {
                "url": "http://custom:8080",
                "api_key": "test-key"
            },
            "default_project": "Test Project",
            "verbose": True
        }

        # Mock file reading
        with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
            with patch.object(Path, 'exists', return_value=True):
                manager = ConfigManager()

        assert str(manager.config.ai_studio.url) == "http://custom:8080/"
        assert manager.config.ai_studio.api_key == "test-key"
        assert manager.config.default_project == "Test Project"
        assert manager.config.verbose is True

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_load_config_no_file(self, mock_home):
        """Test loading configuration when no file exists."""
        mock_home.return_value = Path(self.temp_dir)

        with patch.object(Path, 'exists', return_value=False):
            with patch.object(ConfigManager, '_load_from_environment'):
                with patch.object(ConfigManager, '_load_from_service'):
                    manager = ConfigManager()

        # Should use defaults
        assert str(manager.config.ai_studio.url) == "http://localhost:7860"
        assert manager.config.ai_studio.api_key is None

    @patch('langflow.cli.workflow.config.manager.Path.home')
    @patch.dict('os.environ', {
        'AI_STUDIO_URL': 'http://env:9000',
        'AI_STUDIO_API_KEY': 'env-key',
        'GENESIS_DEFAULT_PROJECT': 'Env Project',
        'GENESIS_VERBOSE': 'true'
    })
    def test_load_from_environment(self, mock_home):
        """Test loading configuration from environment variables."""
        mock_home.return_value = Path(self.temp_dir)

        with patch.object(Path, 'exists', return_value=False):
            with patch.object(ConfigManager, '_load_from_service'):
                manager = ConfigManager()

        assert str(manager.config.ai_studio.url) == "http://env:9000/"
        assert manager.config.ai_studio.api_key == "env-key"
        assert manager.config.default_project == "Env Project"
        assert manager.config.verbose is True

    @patch('langflow.cli.workflow.config.manager.Path.home')
    @patch.dict('os.environ', {
        'LANGFLOW_URL': 'http://langflow:7860',
        'LANGFLOW_API_KEY': 'langflow-key'
    })
    def test_load_from_environment_langflow_vars(self, mock_home):
        """Test loading configuration from Langflow environment variables."""
        mock_home.return_value = Path(self.temp_dir)

        with patch.object(Path, 'exists', return_value=False):
            with patch.object(ConfigManager, '_load_from_service'):
                manager = ConfigManager()

        assert str(manager.config.ai_studio.url) == "http://langflow:7860/"
        assert manager.config.ai_studio.api_key == "langflow-key"

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_load_from_service(self, mock_home):
        """Test loading configuration from AI Studio service."""
        mock_home.return_value = Path(self.temp_dir)

        # Mock settings service
        mock_settings = Mock()
        mock_settings.host = "service-host"
        mock_settings.port = 8888

        mock_settings_service = Mock()
        mock_settings_service.settings = mock_settings

        with patch('langflow.cli.workflow.config.manager.get_settings_service', return_value=mock_settings_service):
            with patch.object(Path, 'exists', return_value=False):
                manager = ConfigManager()

        assert str(manager.config.ai_studio.url) == "http://service-host:8888/"

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_load_from_service_localhost_conversion(self, mock_home):
        """Test service configuration with localhost conversion."""
        mock_home.return_value = Path(self.temp_dir)

        mock_settings = Mock()
        mock_settings.host = "0.0.0.0"
        mock_settings.port = 7860

        mock_settings_service = Mock()
        mock_settings_service.settings = mock_settings

        with patch('langflow.cli.workflow.config.manager.get_settings_service', return_value=mock_settings_service):
            with patch.object(Path, 'exists', return_value=False):
                manager = ConfigManager()

        assert str(manager.config.ai_studio.url) == "http://localhost:7860/"

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_load_from_service_error_handling(self, mock_home):
        """Test service configuration with error handling."""
        mock_home.return_value = Path(self.temp_dir)

        with patch('langflow.cli.workflow.config.manager.get_settings_service', side_effect=Exception("Service error")):
            with patch.object(Path, 'exists', return_value=False):
                manager = ConfigManager()

        # Should fallback to defaults
        assert str(manager.config.ai_studio.url) == "http://localhost:7860"

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_save_config(self, mock_home):
        """Test saving configuration to file."""
        mock_home.return_value = Path(self.temp_dir)

        with patch.object(ConfigManager, '_load_config'):
            manager = ConfigManager()
            manager.config = GenesisConfig(
                default_project="Test Project",
                verbose=True
            )

        with patch("builtins.open", mock_open()) as mock_file:
            with patch.object(manager, '_ensure_config_dir'):
                manager.save_config()

        mock_file.assert_called_once_with(manager.config_file, 'w')

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_get_config(self, mock_home):
        """Test getting current configuration."""
        mock_home.return_value = Path(self.temp_dir)

        with patch.object(ConfigManager, '_load_config'):
            manager = ConfigManager()
            manager.config = None

        with patch.object(manager, '_load_config') as mock_load:
            config = manager.get_config()
            mock_load.assert_called_once()

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_update_config(self, mock_home):
        """Test updating configuration values."""
        mock_home.return_value = Path(self.temp_dir)

        with patch.object(ConfigManager, '_load_config'):
            manager = ConfigManager()
            manager.config = GenesisConfig()

        with patch.object(manager, 'save_config') as mock_save:
            manager.update_config(
                default_project="New Project",
                ai_studio_url="http://new:8080"
            )

        assert manager.config.default_project == "New Project"
        assert str(manager.config.ai_studio.url) == "http://new:8080"
        mock_save.assert_called_once()

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_show_config(self, mock_home):
        """Test showing configuration as formatted string."""
        mock_home.return_value = Path(self.temp_dir)

        with patch.object(ConfigManager, '_load_config'):
            manager = ConfigManager()
            manager.config = GenesisConfig(
                default_project="Test Project",
                verbose=True
            )
            manager.config.ai_studio.api_key = "test-key"

        config_str = manager.show_config()

        assert "Genesis CLI Configuration" in config_str
        assert "AI Studio URL:" in config_str
        assert "[Set]" in config_str  # API key is set
        assert "Test Project" in config_str

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_show_config_no_api_key(self, mock_home):
        """Test showing configuration without API key."""
        mock_home.return_value = Path(self.temp_dir)

        with patch.object(ConfigManager, '_load_config'):
            manager = ConfigManager()
            manager.config = GenesisConfig()

        config_str = manager.show_config()
        assert "[Not Set]" in config_str  # API key is not set

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_import_genesis_agent_config_yaml(self, mock_home):
        """Test importing from genesis-agent-cli YAML config."""
        mock_home.return_value = Path(self.temp_dir)

        old_config = {
            "genesis_studio": {
                "url": "http://old:8080",
                "api_key": "old-key"
            }
        }

        with patch.object(ConfigManager, '_load_config'):
            manager = ConfigManager()

        # Mock file existence and content
        with patch.object(Path, 'exists', return_value=True):
            with patch("builtins.open", mock_open(read_data=yaml.dump(old_config))):
                with patch.object(manager, 'update_config') as mock_update:
                    result = manager.import_genesis_agent_config()

        assert result is True
        # Verify that update_config was called with correct parameters
        assert mock_update.call_count >= 1
        mock_update.assert_called_with(
            ai_studio_url="http://old:8080",
            ai_studio_api_key="old-key"
        )

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_import_genesis_agent_config_env(self, mock_home):
        """Test importing from .env file."""
        mock_home.return_value = Path(self.temp_dir)

        env_content = """
GENESIS_STUDIO_URL=http://env:9000
GENESIS_API_KEY=env-key
# Comment line
IRRELEVANT_VAR=ignore
"""

        with patch.object(ConfigManager, '_load_config'):
            manager = ConfigManager()

        # Mock multiple path checks, .env file exists
        def path_exists_side_effect():
            return True

        with patch.object(Path, 'exists', side_effect=path_exists_side_effect):
            with patch("builtins.open", mock_open(read_data=env_content)):
                with patch.object(manager, 'update_config') as mock_update:
                    result = manager.import_genesis_agent_config()

        assert result is True
        # Should be called twice - once for URL, once for API key
        assert mock_update.call_count == 2

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_import_genesis_agent_config_not_found(self, mock_home):
        """Test importing when no config files found."""
        mock_home.return_value = Path(self.temp_dir)

        with patch.object(ConfigManager, '_load_config'):
            manager = ConfigManager()

        with patch.object(Path, 'exists', return_value=False):
            result = manager.import_genesis_agent_config()

        assert result is False

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_import_genesis_agent_config_error(self, mock_home):
        """Test importing with file read error."""
        mock_home.return_value = Path(self.temp_dir)

        with patch.object(ConfigManager, '_load_config'):
            manager = ConfigManager()

        with patch.object(Path, 'exists', return_value=True):
            with patch("builtins.open", side_effect=Exception("Read error")):
                result = manager.import_genesis_agent_config()

        assert result is False

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_ai_studio_url_property(self, mock_home):
        """Test ai_studio_url property."""
        mock_home.return_value = Path(self.temp_dir)

        with patch.object(ConfigManager, '_load_config'):
            manager = ConfigManager()
            manager.config = GenesisConfig()

        with patch.object(manager, 'get_config', return_value=manager.config):
            url = manager.ai_studio_url
            assert url == "http://localhost:7860"

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_api_key_property(self, mock_home):
        """Test api_key property."""
        mock_home.return_value = Path(self.temp_dir)

        with patch.object(ConfigManager, '_load_config'):
            manager = ConfigManager()
            manager.config = GenesisConfig()
            manager.config.ai_studio.api_key = "test-key"

        with patch.object(manager, 'get_config', return_value=manager.config):
            api_key = manager.api_key
            assert api_key == "test-key"

    @patch('langflow.cli.workflow.config.manager.Path.home')
    def test_load_config_invalid_yaml(self, mock_home):
        """Test loading configuration with invalid YAML."""
        mock_home.return_value = Path(self.temp_dir)

        invalid_yaml = "invalid: yaml: [unclosed"

        with patch("builtins.open", mock_open(read_data=invalid_yaml)):
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(ConfigManager, '_load_from_environment'):
                    with patch.object(ConfigManager, '_load_from_service'):
                        manager = ConfigManager()

        # Should fallback to defaults when YAML is invalid
        assert str(manager.config.ai_studio.url) == "http://localhost:7860"