"""Unit tests for the config command module."""

import json
import pytest
import yaml
from pathlib import Path
from unittest.mock import Mock, patch
from click.testing import CliRunner

from langflow.cli.workflow.commands.config import (
    config,
    show_config,
    set_config,
    import_config,
    test_config,
    reset_config
)


class TestConfigCommand:
    """Test the config CLI command group."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config_manager = Mock()
        self.mock_config_manager.ai_studio_url = "http://localhost:7860"
        self.mock_config_manager.api_key = "test-api-key"

    def test_config_group_help(self):
        """Test config group help message."""
        result = self.runner.invoke(config, ["--help"])
        assert result.exit_code == 0
        assert "Manage Genesis CLI configuration" in result.output


class TestShowConfig:
    """Test the show config command."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config_manager = Mock()
        self.mock_config = Mock()
        self.mock_config.model_dump.return_value = {
            "ai_studio": {
                "url": "http://localhost:7860",
                "api_key": "test-key"
            },
            "default_project": None,
            "verbose": False
        }
        self.mock_config_manager.get_config.return_value = self.mock_config
        self.mock_config_manager.show_config.return_value = "Test config output"

    def test_show_config_table_format(self):
        """Test show config with table format (default)."""
        result = self.runner.invoke(
            show_config,
            [],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 0
        assert "Test config output" in result.output
        self.mock_config_manager.show_config.assert_called_once()

    def test_show_config_json_format(self):
        """Test show config with JSON format."""
        result = self.runner.invoke(
            show_config,
            ["--format", "json"],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 0
        # Verify it's valid JSON - config JSON output is clean without surrounding messages
        parsed_json = json.loads(result.output)
        assert "ai_studio" in parsed_json

    def test_show_config_yaml_format(self):
        """Test show config with YAML format."""
        result = self.runner.invoke(
            show_config,
            ["--format", "yaml"],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 0
        # Should contain YAML structure
        assert "ai_studio:" in result.output

    def test_show_config_error(self):
        """Test show config with error."""
        self.mock_config_manager.show_config.side_effect = Exception("Config error")

        result = self.runner.invoke(
            show_config,
            [],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 1
        assert "Failed to show configuration" in result.output


class TestSetConfig:
    """Test the set config command."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config_manager = Mock()

    def test_set_config_string_value(self):
        """Test setting a string configuration value."""
        result = self.runner.invoke(
            set_config,
            ["ai_studio_url", "http://new-url:8080"],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 0
        assert "Configuration updated" in result.output
        self.mock_config_manager.update_config.assert_called_once_with(
            ai_studio_url="http://new-url:8080"
        )

    def test_set_config_boolean_true(self):
        """Test setting a boolean configuration value to true."""
        result = self.runner.invoke(
            set_config,
            ["verbose", "true"],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 0
        assert "Configuration updated" in result.output
        self.mock_config_manager.update_config.assert_called_once_with(verbose=True)

    def test_set_config_boolean_false(self):
        """Test setting a boolean configuration value to false."""
        result = self.runner.invoke(
            set_config,
            ["verbose", "false"],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 0
        assert "Configuration updated" in result.output
        self.mock_config_manager.update_config.assert_called_once_with(verbose=False)

    def test_set_config_api_key(self):
        """Test setting API key configuration."""
        result = self.runner.invoke(
            set_config,
            ["ai_studio_api_key", "new-api-key"],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 0
        assert "Configuration updated" in result.output
        self.mock_config_manager.update_config.assert_called_once_with(
            ai_studio_api_key="new-api-key"
        )

    def test_set_config_error(self):
        """Test set config with error."""
        self.mock_config_manager.update_config.side_effect = Exception("Update error")

        result = self.runner.invoke(
            set_config,
            ["test_key", "test_value"],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 1
        assert "Failed to set configuration" in result.output


class TestImportConfig:
    """Test the import config command."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config_manager = Mock()
        self.mock_config_manager.show_config.return_value = "Imported config"

    def test_import_config_success(self):
        """Test successful config import."""
        self.mock_config_manager.import_genesis_agent_config.return_value = True

        result = self.runner.invoke(
            import_config,
            [],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 0
        assert "Configuration imported successfully" in result.output
        assert "Imported config" in result.output
        self.mock_config_manager.import_genesis_agent_config.assert_called_once()

    def test_import_config_not_found(self):
        """Test config import when no config found."""
        self.mock_config_manager.import_genesis_agent_config.return_value = False

        result = self.runner.invoke(
            import_config,
            [],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 0
        assert "No genesis-agent-cli configuration found" in result.output
        assert "~/.genesis-agent.yaml" in result.output

    def test_import_config_from_file_not_implemented(self):
        """Test import from specific file (not implemented)."""
        # Create a temporary file for testing
        with self.runner.isolated_filesystem():
            Path("test-config.yaml").touch()

            result = self.runner.invoke(
                import_config,
                ["--from-file", "test-config.yaml"],
                obj={'config': self.mock_config_manager}
            )

        assert result.exit_code == 0
        assert "Import from specific file not yet implemented" in result.output

    def test_import_config_error(self):
        """Test import config with error."""
        self.mock_config_manager.import_genesis_agent_config.side_effect = Exception("Import error")

        result = self.runner.invoke(
            import_config,
            [],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 1
        assert "Failed to import configuration" in result.output


class TestTestConfig:
    """Test the test config command."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config_manager = Mock()
        self.mock_config_manager.ai_studio_url = "http://localhost:7860"
        self.mock_config_manager.api_key = "test-api-key"

    @patch('langflow.cli.workflow.utils.api_client.APIClient')
    def test_test_config_success_with_api_key(self, mock_api_client_class):
        """Test successful config test with API key."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.get_available_components_sync.return_value = {"components": {}}

        result = self.runner.invoke(
            test_config,
            [],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 0
        assert "Successfully connected to AI Studio" in result.output
        assert "API key authentication successful" in result.output

    @patch('langflow.cli.workflow.utils.api_client.APIClient')
    def test_test_config_success_no_api_key(self, mock_api_client_class):
        """Test successful config test without API key."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        self.mock_config_manager.api_key = None

        result = self.runner.invoke(
            test_config,
            [],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 0
        assert "Successfully connected to AI Studio" in result.output
        assert "No API key configured" in result.output

    @patch('langflow.cli.workflow.utils.api_client.APIClient')
    def test_test_config_connection_failure(self, mock_api_client_class):
        """Test config test with connection failure."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = False

        result = self.runner.invoke(
            test_config,
            [],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 1
        assert "Failed to connect to AI Studio" in result.output
        assert "AI Studio is running" in result.output

    @patch('langflow.cli.workflow.utils.api_client.APIClient')
    def test_test_config_api_key_failure(self, mock_api_client_class):
        """Test config test with API key authentication failure."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.get_available_components_sync.side_effect = Exception("Auth failed")

        result = self.runner.invoke(
            test_config,
            [],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 0
        assert "Successfully connected to AI Studio" in result.output
        assert "API key authentication failed" in result.output

    @patch('langflow.cli.workflow.utils.api_client.APIClient')
    def test_test_config_unexpected_error(self, mock_api_client_class):
        """Test config test with unexpected error."""
        mock_api_client_class.side_effect = Exception("Unexpected error")

        result = self.runner.invoke(
            test_config,
            [],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 1
        assert "Configuration test failed" in result.output


class TestResetConfig:
    """Test the reset config command."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config_manager = Mock()
        self.mock_config_file = Mock()
        self.mock_config_file.exists.return_value = True
        self.mock_config_manager.config_file = self.mock_config_file
        self.mock_config_manager.show_config.return_value = "Default config"

    def test_reset_config_with_confirm_flag(self):
        """Test reset config with confirm flag."""
        result = self.runner.invoke(
            reset_config,
            ["--confirm"],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 0
        assert "Configuration reset to defaults" in result.output
        assert "Default config" in result.output
        self.mock_config_file.unlink.assert_called_once()
        self.mock_config_manager._load_config.assert_called_once()

    def test_reset_config_with_confirmation_yes(self):
        """Test reset config with user confirmation (yes)."""
        result = self.runner.invoke(
            reset_config,
            [],
            obj={'config': self.mock_config_manager},
            input='y\n'
        )

        assert result.exit_code == 0
        assert "Configuration reset to defaults" in result.output
        self.mock_config_file.unlink.assert_called_once()

    def test_reset_config_with_confirmation_no(self):
        """Test reset config with user confirmation (no)."""
        result = self.runner.invoke(
            reset_config,
            [],
            obj={'config': self.mock_config_manager},
            input='n\n'
        )

        assert result.exit_code == 0
        assert "Configuration reset cancelled" in result.output
        self.mock_config_file.unlink.assert_not_called()

    def test_reset_config_no_file_exists(self):
        """Test reset config when config file doesn't exist."""
        self.mock_config_file.exists.return_value = False

        result = self.runner.invoke(
            reset_config,
            ["--confirm"],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 0
        assert "Configuration reset to defaults" in result.output
        self.mock_config_file.unlink.assert_not_called()
        self.mock_config_manager._load_config.assert_called_once()

    def test_reset_config_error(self):
        """Test reset config with error."""
        self.mock_config_file.unlink.side_effect = Exception("Delete error")

        result = self.runner.invoke(
            reset_config,
            ["--confirm"],
            obj={'config': self.mock_config_manager}
        )

        assert result.exit_code == 1
        assert "Failed to reset configuration" in result.output