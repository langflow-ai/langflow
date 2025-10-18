"""Unit tests for the create command module."""

import json
import pytest
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from click.testing import CliRunner

from langflow.cli.workflow.commands.create import (
    create,
    load_variables_from_file,
    parse_cli_variables,
    parse_cli_tweaks
)


class TestLoadVariablesFromFile:
    """Test the load_variables_from_file function."""

    def test_load_json_file(self):
        """Test loading variables from JSON file."""
        json_data = {"key1": "value1", "key2": 42}
        with patch("builtins.open", mock_open(read_data=json.dumps(json_data))):
            result = load_variables_from_file("/path/to/file.json")
            assert result == json_data

    def test_load_yaml_file(self):
        """Test loading variables from YAML file."""
        yaml_data = {"key1": "value1", "key2": 42}
        with patch("builtins.open", mock_open(read_data=yaml.dump(yaml_data))):
            result = load_variables_from_file("/path/to/file.yaml")
            assert result == yaml_data

    def test_load_empty_yaml_file(self):
        """Test loading variables from empty YAML file."""
        with patch("builtins.open", mock_open(read_data="")):
            result = load_variables_from_file("/path/to/file.yaml")
            assert result == {}

    def test_load_file_not_found(self):
        """Test loading variables from non-existent file."""
        with patch("builtins.open", side_effect=FileNotFoundError()):
            with pytest.raises(FileNotFoundError):
                load_variables_from_file("/path/to/nonexistent.json")


class TestParseCliVariables:
    """Test the parse_cli_variables function."""

    def test_parse_simple_variables(self):
        """Test parsing simple key=value variables."""
        var_list = ("key1=value1", "key2=value2")
        result = parse_cli_variables(var_list)
        assert result == {"key1": "value1", "key2": "value2"}

    def test_parse_json_values(self):
        """Test parsing variables with JSON values."""
        var_list = ("key1=42", "key2=true", "key3={\"nested\": \"value\"}")
        result = parse_cli_variables(var_list)
        assert result == {"key1": 42, "key2": True, "key3": {"nested": "value"}}

    def test_parse_invalid_format(self):
        """Test parsing variables with invalid format."""
        var_list = ("invalid_format",)
        with pytest.raises(ValueError, match="Invalid variable format"):
            parse_cli_variables(var_list)

    def test_parse_equals_in_value(self):
        """Test parsing variables with equals sign in value."""
        var_list = ("url=http://example.com:8080/api?param=value",)
        result = parse_cli_variables(var_list)
        assert result == {"url": "http://example.com:8080/api?param=value"}


class TestParseCliTweaks:
    """Test the parse_cli_tweaks function."""

    def test_parse_simple_tweaks(self):
        """Test parsing simple component tweaks."""
        tweak_list = ("agent.temperature=0.5", "llm.model=gpt-4")
        result = parse_cli_tweaks(tweak_list)
        assert result == {"agent.temperature": 0.5, "llm.model": "gpt-4"}

    def test_parse_nested_tweaks(self):
        """Test parsing nested component tweaks."""
        tweak_list = ("agent.config.temperature=0.7", "llm.config.max_tokens=100")
        result = parse_cli_tweaks(tweak_list)
        assert result == {"agent.config.temperature": 0.7, "llm.config.max_tokens": 100}

    def test_parse_invalid_format(self):
        """Test parsing tweaks with invalid format."""
        tweak_list = ("invalid_format",)
        with pytest.raises(ValueError, match="Invalid tweak format"):
            parse_cli_tweaks(tweak_list)

    def test_parse_json_values(self):
        """Test parsing tweaks with JSON values."""
        tweak_list = ("agent.config={\"temp\": 0.8}",)
        result = parse_cli_tweaks(tweak_list)
        assert result == {"agent.config": {"temp": 0.8}}


class TestCreateCommand:
    """Test the create CLI command."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = Mock()
        self.mock_config.ai_studio_url = "http://localhost:7860"
        self.mock_api_client = Mock()

    @patch('langflow.cli.workflow.commands.create.APIClient')
    def test_create_missing_template(self, mock_api_client_class):
        """Test create command without template parameter."""
        result = self.runner.invoke(create, [], obj={'config': self.mock_config})
        assert result.exit_code == 1
        assert "Template file or library name is required" in result.output

    @patch('langflow.cli.workflow.commands.create.APIClient')
    @patch('langflow.cli.workflow.commands.create.Path')
    def test_create_from_local_file(self, mock_path, mock_api_client_class):
        """Test create command from local template file."""
        # Setup mocks
        mock_template_path = Mock()
        mock_template_path.exists.return_value = True
        mock_template_path.name = "test-template.yaml"
        mock_template_path.stem = "test-template"
        mock_path.return_value = mock_template_path

        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client

        # Mock file content
        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""
        # Mock validation result
        mock_api_client.validate_spec_sync.return_value = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        # Mock conversion result
        mock_api_client.convert_spec_sync.return_value = {
            "flow": {
                "name": "Test Agent",
                "data": {"nodes": [], "edges": []},
                "description": "A test agent"
            }
        }

        # Mock flow creation
        mock_api_client.create_flow_sync.return_value = {"id": "flow-123"}
        mock_api_client.health_check_sync.return_value = True

        with patch("builtins.open", mock_open(read_data=spec_content)):
            result = self.runner.invoke(
                create,
                ["-t", "test-template.yaml"],
                obj={'config': self.mock_config}
            )

        assert result.exit_code == 0
        assert "Flow created successfully!" in result.output
        mock_api_client.validate_spec_sync.assert_called_once()
        mock_api_client.convert_spec_sync.assert_called_once()
        mock_api_client.create_flow_sync.assert_called_once()

    @patch('langflow.cli.workflow.commands.create.APIClient')
    @patch('langflow.cli.workflow.commands.create.Path')
    def test_create_validate_only(self, mock_path, mock_api_client_class):
        """Test create command with validate-only flag."""
        # Setup mocks
        mock_template_path = Mock()
        mock_template_path.exists.return_value = True
        mock_template_path.name = "test-template.yaml"
        mock_path.return_value = mock_template_path

        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        mock_api_client.validate_spec_sync.return_value = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        with patch("builtins.open", mock_open(read_data=spec_content)):
            result = self.runner.invoke(
                create,
                ["-t", "test-template.yaml", "--validate-only"],
                obj={'config': self.mock_config}
            )

        assert result.exit_code == 0
        assert "Validation complete (--validate-only flag set)" in result.output
        mock_api_client.validate_spec_sync.assert_called_once()
        mock_api_client.convert_spec_sync.assert_not_called()
        mock_api_client.create_flow_sync.assert_not_called()

    @patch('langflow.cli.workflow.commands.create.APIClient')
    @patch('langflow.cli.workflow.commands.create.Path')
    def test_create_validation_failure(self, mock_path, mock_api_client_class):
        """Test create command with validation failure."""
        mock_template_path = Mock()
        mock_template_path.exists.return_value = True
        mock_template_path.name = "test-template.yaml"
        mock_path.return_value = mock_template_path

        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client

        spec_content = """
name: Test Agent
description: A test agent
components: []
"""

        mock_api_client.validate_spec_sync.return_value = {
            "valid": False,
            "errors": [
                {"message": "No components defined", "component_id": "", "field": ""},
                "Missing required field"
            ],
            "warnings": []
        }

        with patch("builtins.open", mock_open(read_data=spec_content)):
            result = self.runner.invoke(
                create,
                ["-t", "test-template.yaml"],
                obj={'config': self.mock_config}
            )

        assert result.exit_code == 1
        assert "Specification validation failed" in result.output
        assert "No components defined" in result.output
        assert "Missing required field" in result.output

    @patch('langflow.cli.workflow.commands.create.APIClient')
    def test_create_with_variables_from_file(self, mock_api_client_class):
        """Test create command with variables from file."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        var_content = '{"api_key": "test-key", "temperature": 0.7}'

        mock_api_client.validate_spec_sync.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_api_client.convert_spec_sync.return_value = {
            "flow": {"name": "Test Agent", "data": {"nodes": [], "edges": []}}
        }
        mock_api_client.create_flow_sync.return_value = {"id": "flow-123"}
        mock_api_client.health_check_sync.return_value = True

        # Create actual temporary files since click.Path(exists=True) validates file existence
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as template_file:
            template_file.write(spec_content)
            template_file_path = template_file.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as vars_file:
            vars_file.write(var_content)
            vars_file_path = vars_file.name

        try:
            result = self.runner.invoke(
                create,
                ["-t", template_file_path, "--var-file", vars_file_path],
                obj={'config': self.mock_config}
            )
        finally:
            os.unlink(template_file_path)
            os.unlink(vars_file_path)

        assert result.exit_code == 0
        # Check that variables were passed to convert_spec
        mock_api_client.convert_spec_sync.assert_called_once()
        call_args = mock_api_client.convert_spec_sync.call_args
        assert call_args[1]['variables'] == {"api_key": "test-key", "temperature": 0.7}

    @patch('langflow.cli.workflow.commands.create.APIClient')
    @patch('langflow.cli.workflow.commands.create.Path')
    def test_create_with_cli_variables(self, mock_path, mock_api_client_class):
        """Test create command with CLI variables."""
        mock_template_path = Mock()
        mock_template_path.exists.return_value = True
        mock_template_path.name = "test-template.yaml"
        mock_template_path.stem = "test-template"
        mock_path.return_value = mock_template_path

        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        mock_api_client.validate_spec_sync.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_api_client.convert_spec_sync.return_value = {
            "flow": {"name": "Test Agent", "data": {"nodes": [], "edges": []}}
        }
        mock_api_client.create_flow_sync.return_value = {"id": "flow-123"}
        mock_api_client.health_check_sync.return_value = True

        with patch("builtins.open", mock_open(read_data=spec_content)):
            result = self.runner.invoke(
                create,
                ["-t", "test-template.yaml", "--var", "key1=value1", "--var", "key2=42"],
                obj={'config': self.mock_config}
            )

        assert result.exit_code == 0
        mock_api_client.convert_spec_sync.assert_called_once()
        call_args = mock_api_client.convert_spec_sync.call_args
        assert call_args[1]['variables'] == {"key1": "value1", "key2": 42}

    @patch('langflow.cli.workflow.commands.create.APIClient')
    @patch('langflow.cli.workflow.commands.create.Path')
    def test_create_with_tweaks(self, mock_path, mock_api_client_class):
        """Test create command with component tweaks."""
        mock_template_path = Mock()
        mock_template_path.exists.return_value = True
        mock_template_path.name = "test-template.yaml"
        mock_template_path.stem = "test-template"
        mock_path.return_value = mock_template_path

        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        mock_api_client.validate_spec_sync.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_api_client.convert_spec_sync.return_value = {
            "flow": {"name": "Test Agent", "data": {"nodes": [], "edges": []}}
        }
        mock_api_client.create_flow_sync.return_value = {"id": "flow-123"}
        mock_api_client.health_check_sync.return_value = True

        with patch("builtins.open", mock_open(read_data=spec_content)):
            result = self.runner.invoke(
                create,
                ["-t", "test-template.yaml", "--tweak", "agent.temperature=0.8"],
                obj={'config': self.mock_config}
            )

        assert result.exit_code == 0
        mock_api_client.convert_spec_sync.assert_called_once()
        call_args = mock_api_client.convert_spec_sync.call_args
        assert call_args[1]['tweaks'] == {"agent.temperature": 0.8}

    @patch('langflow.cli.workflow.commands.create.APIClient')
    @patch('langflow.cli.workflow.commands.create.Path')
    def test_create_save_to_file(self, mock_path, mock_api_client_class):
        """Test create command with output to file."""
        mock_template_path = Mock()
        mock_template_path.exists.return_value = True
        mock_template_path.name = "test-template.yaml"
        mock_template_path.stem = "test-template"
        mock_path.return_value = mock_template_path

        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        flow_data = {
            "name": "Test Agent",
            "data": {"nodes": [], "edges": []}
        }

        mock_api_client.validate_spec_sync.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_api_client.convert_spec_sync.return_value = {"flow": flow_data}

        with patch("builtins.open", mock_open(read_data=spec_content)) as mock_file:
            result = self.runner.invoke(
                create,
                ["-t", "test-template.yaml", "-o", "output.json"],
                obj={'config': self.mock_config}
            )

        assert result.exit_code == 0
        assert "Flow saved successfully!" in result.output
        # Verify file was written
        write_calls = [call for call in mock_file.return_value.write.call_args_list]
        assert len(write_calls) > 0

    @patch('langflow.cli.workflow.commands.create.APIClient')
    def test_create_from_library_template(self, mock_api_client_class):
        """Test create command from library template."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client

        mock_api_client.create_flow_from_library_sync.return_value = {
            "success": True,
            "flow_id": "flow-123",
            "flow_name": "Healthcare Agent"
        }

        with patch('langflow.cli.workflow.commands.create.Path') as mock_path:
            mock_template_path = Mock()
            mock_template_path.exists.return_value = False
            mock_path.return_value = mock_template_path

            result = self.runner.invoke(
                create,
                ["-t", "healthcare/eligibility-checker"],
                obj={'config': self.mock_config}
            )

        assert result.exit_code == 0
        assert "Flow created from library template" in result.output
        mock_api_client.create_flow_from_library_sync.assert_called_once_with(
            "healthcare/eligibility-checker", None
        )

    @patch('langflow.cli.workflow.commands.create.APIClient')
    def test_create_library_template_validate_only_error(self, mock_api_client_class):
        """Test create command from library template with validate-only flag (should fail)."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client

        with patch('langflow.cli.workflow.commands.create.Path') as mock_path:
            mock_template_path = Mock()
            mock_template_path.exists.return_value = False
            mock_path.return_value = mock_template_path

            result = self.runner.invoke(
                create,
                ["-t", "healthcare/eligibility-checker", "--validate-only"],
                obj={'config': self.mock_config}
            )

        assert result.exit_code == 1
        assert "Library templates cannot be validated without creating" in result.output

    @patch('langflow.cli.workflow.commands.create.APIClient')
    @patch('langflow.cli.workflow.commands.create.Path')
    def test_create_connectivity_check_failure(self, mock_path, mock_api_client_class):
        """Test create command with AI Studio connectivity failure."""
        mock_template_path = Mock()
        mock_template_path.exists.return_value = True
        mock_template_path.name = "test-template.yaml"
        mock_path.return_value = mock_template_path

        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        mock_api_client.validate_spec_sync.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_api_client.health_check_sync.return_value = False

        with patch("builtins.open", mock_open(read_data=spec_content)):
            result = self.runner.invoke(
                create,
                ["-t", "test-template.yaml"],
                obj={'config': self.mock_config}
            )

        assert result.exit_code == 1
        assert "Cannot connect to AI Studio" in result.output

    @patch('langflow.cli.workflow.commands.create.APIClient')
    @patch('langflow.cli.workflow.commands.create.Path')
    def test_create_with_debug_flag(self, mock_path, mock_api_client_class):
        """Test create command with debug flag enabled."""
        mock_template_path = Mock()
        mock_template_path.exists.return_value = True
        mock_template_path.name = "test-template.yaml"
        mock_template_path.stem = "test-template"
        mock_path.return_value = mock_template_path

        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        mock_api_client.validate_spec_sync.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_api_client.convert_spec_sync.return_value = {
            "flow": {"name": "Test Agent", "data": {"nodes": [], "edges": []}}
        }
        mock_api_client.create_flow_sync.return_value = {"id": "flow-123"}
        mock_api_client.health_check_sync.return_value = True

        with patch("builtins.open", mock_open(read_data=spec_content)):
            result = self.runner.invoke(
                create,
                ["-t", "test-template.yaml", "--var", "key1=value1", "--debug"],
                obj={'config': self.mock_config}
            )

        assert result.exit_code == 0
        assert "Variables:" in result.output

    @patch('langflow.cli.workflow.commands.create.APIClient')
    @patch('langflow.cli.workflow.commands.create.Path')
    def test_create_file_not_found(self, mock_path, mock_api_client_class):
        """Test create command with non-existent template file."""
        mock_template_path = Mock()
        mock_template_path.exists.return_value = False
        mock_path.return_value = mock_template_path

        result = self.runner.invoke(
            create,
            ["-t", "nonexistent.yaml"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 1
        assert "Template file not found" in result.output

    @patch('langflow.cli.workflow.commands.create.APIClient')
    @patch('langflow.cli.workflow.commands.create.Path')
    def test_create_with_warnings(self, mock_path, mock_api_client_class):
        """Test create command with validation warnings."""
        mock_template_path = Mock()
        mock_template_path.exists.return_value = True
        mock_template_path.name = "test-template.yaml"
        mock_template_path.stem = "test-template"
        mock_path.return_value = mock_template_path

        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        mock_api_client.validate_spec_sync.return_value = {
            "valid": True,
            "errors": [],
            "warnings": [
                {"message": "This is a warning", "component_id": "agent"},
                "Simple warning"
            ]
        }
        mock_api_client.convert_spec_sync.return_value = {
            "flow": {"name": "Test Agent", "data": {"nodes": [], "edges": []}}
        }
        mock_api_client.create_flow_sync.return_value = {"id": "flow-123"}
        mock_api_client.health_check_sync.return_value = True

        with patch("builtins.open", mock_open(read_data=spec_content)):
            result = self.runner.invoke(
                create,
                ["-t", "test-template.yaml"],
                obj={'config': self.mock_config}
            )

        assert result.exit_code == 0
        assert "Validation warnings:" in result.output
        assert "This is a warning" in result.output
        assert "Simple warning" in result.output