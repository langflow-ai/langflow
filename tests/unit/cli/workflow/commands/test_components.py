"""Unit tests for the components command module."""

import json
import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

from langflow.cli.workflow.commands.components import components


class TestComponentsCommand:
    """Test the components CLI command."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = Mock()
        self.mock_config.ai_studio_url = "http://localhost:7860"

        self.sample_components = {
            "genesis:agent": {
                "component": "Agent",
                "description": "Main agent component for Genesis",
                "is_tool": False,
                "category": "agents",
                "parameters": {
                    "model": "string",
                    "temperature": "float"
                },
                "langflow_component": "langflow.components.agents.Agent"
            },
            "genesis:llm": {
                "component": "ChatOpenAI",
                "description": "OpenAI language model integration",
                "is_tool": True,
                "category": "tools",
                "parameters": {
                    "api_key": "string",
                    "model": "string"
                },
                "langflow_component": "langflow.components.llms.ChatOpenAI"
            },
            "genesis:healthcare:patient_data": {
                "component": "PatientDataProcessor",
                "description": "Healthcare patient data processing component",
                "is_tool": False,
                "category": "healthcare",
                "parameters": {
                    "data_format": "string"
                },
                "langflow_component": "langflow.components.healthcare.PatientDataProcessor"
            }
        }

    @patch('langflow.cli.workflow.commands.components.APIClient')
    def test_components_list_all_table_format(self, mock_api_client_class):
        """Test listing all components in table format."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.get_available_components_sync.return_value = {
            "components": self.sample_components
        }

        result = self.runner.invoke(
            components,
            [],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        assert "genesis:agent" in result.output
        assert "genesis:llm" in result.output
        mock_api_client.get_available_components_sync.assert_called_once()

    @patch('langflow.cli.workflow.commands.components.APIClient')
    def test_components_list_json_format(self, mock_api_client_class):
        """Test listing components in JSON format."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.get_available_components_sync.return_value = {
            "components": self.sample_components
        }

        result = self.runner.invoke(
            components,
            ["--format", "json"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        # Verify JSON output is valid - extract JSON array from mixed output
        output_lines = result.output.strip().split('\n')
        json_lines = []
        in_json = False
        for line in output_lines:
            if line.strip().startswith('['):
                in_json = True
                json_lines.append(line)
            elif in_json and (line.strip().startswith(']') or line.strip().endswith(']')):
                json_lines.append(line)
                break
            elif in_json:
                json_lines.append(line)

        json_output = '\n'.join(json_lines)
        parsed_json = json.loads(json_output)
        assert len(parsed_json) == 3

    @patch('langflow.cli.workflow.commands.components.APIClient')
    def test_components_search_filter(self, mock_api_client_class):
        """Test searching components with filter."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.get_available_components_sync.return_value = {
            "components": self.sample_components
        }

        result = self.runner.invoke(
            components,
            ["--search", "agent", "--format", "json"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        # Should only return components with "agent" in the name
        output_lines = result.output.strip().split('\n')
        json_lines = []
        in_json = False
        for line in output_lines:
            if line.strip().startswith('['):
                in_json = True
                json_lines.append(line)
            elif in_json and (line.strip().startswith(']') or line.strip().endswith(']')):
                json_lines.append(line)
                break
            elif in_json:
                json_lines.append(line)

        json_output = '\n'.join(json_lines)
        parsed_json = json.loads(json_output)
        assert len(parsed_json) == 1
        assert "agent" in parsed_json[0]["type"].lower()

    @patch('langflow.cli.workflow.commands.components.APIClient')
    def test_components_category_filter(self, mock_api_client_class):
        """Test filtering components by category."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.get_available_components_sync.return_value = {
            "components": self.sample_components
        }

        result = self.runner.invoke(
            components,
            ["--category", "healthcare", "--format", "json"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        # Should only return healthcare components
        output_lines = result.output.strip().split('\n')
        json_lines = []
        in_json = False
        for line in output_lines:
            if line.strip().startswith('['):
                in_json = True
                json_lines.append(line)
            elif in_json and (line.strip().startswith(']') or line.strip().endswith(']')):
                json_lines.append(line)
                break
            elif in_json:
                json_lines.append(line)

        json_output = '\n'.join(json_lines)
        parsed_json = json.loads(json_output)
        assert len(parsed_json) == 1
        assert "healthcare" in parsed_json[0]["type"]

    @patch('langflow.cli.workflow.commands.components.APIClient')
    def test_components_detailed_info(self, mock_api_client_class):
        """Test showing detailed component information."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.get_available_components_sync.return_value = {
            "components": self.sample_components
        }
        mock_api_client.get_component_mapping_sync.return_value = {
            "langflow_component": "langflow.components.agents.Agent",
            "is_tool": False,
            "input_field": "input",
            "output_field": "output",
            "output_types": ["text"],
            "config": {"model": "string", "temperature": "float"}
        }

        result = self.runner.invoke(
            components,
            ["--info", "genesis:agent"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        assert "Component: genesis:agent" in result.output
        assert "genesis:agent" in result.output
        assert "Langflow Component:" in result.output
        assert "Configuration:" in result.output

    @patch('langflow.cli.workflow.commands.components.APIClient')
    def test_components_info_not_found(self, mock_api_client_class):
        """Test showing info for non-existent component."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.get_available_components_sync.return_value = {
            "components": self.sample_components
        }
        mock_api_client.get_component_mapping_sync.side_effect = Exception("Component not found")

        result = self.runner.invoke(
            components,
            ["--info", "nonexistent:component"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 1
        assert "Component not found" in result.output

    @patch('langflow.cli.workflow.commands.components.APIClient')
    def test_components_simple_format(self, mock_api_client_class):
        """Test listing components in simple format."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.get_available_components_sync.return_value = {
            "components": self.sample_components
        }

        result = self.runner.invoke(
            components,
            ["--format", "simple"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        assert "genesis:agent" in result.output
        assert "genesis:llm" in result.output

    @patch('langflow.cli.workflow.commands.components.APIClient')
    def test_components_connectivity_failure(self, mock_api_client_class):
        """Test components command with connectivity failure."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = False

        result = self.runner.invoke(
            components,
            [],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 1
        assert "Cannot connect to AI Studio" in result.output

    @patch('langflow.cli.workflow.commands.components.APIClient')
    def test_components_api_error(self, mock_api_client_class):
        """Test components command with API error."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.get_available_components_sync.side_effect = Exception("API Error")

        result = self.runner.invoke(
            components,
            [],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 1
        assert "Failed to list components" in result.output

    @patch('langflow.cli.workflow.commands.components.APIClient')
    def test_components_api_error_with_debug(self, mock_api_client_class):
        """Test components command with API error and debug flag."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.get_available_components_sync.side_effect = Exception("API Error")

        with patch("traceback.print_exc") as mock_traceback:
            result = self.runner.invoke(
                components,
                ["--debug"],
                obj={'config': self.mock_config}
            )

        assert result.exit_code == 1
        assert "Failed to list components" in result.output
        mock_traceback.assert_called_once()

    @patch('langflow.cli.workflow.commands.components.APIClient')
    def test_components_no_components_found(self, mock_api_client_class):
        """Test components command when no components found."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.get_available_components_sync.return_value = {
            "components": {}
        }

        result = self.runner.invoke(
            components,
            [],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        assert "No components found" in result.output

    @patch('langflow.cli.workflow.commands.components.APIClient')
    def test_components_unexpected_error(self, mock_api_client_class):
        """Test components command with unexpected error."""
        # Force an unexpected error by making config access fail
        result = self.runner.invoke(
            components,
            [],
            obj={}  # Missing config to trigger error
        )

        assert result.exit_code == 1
        assert "Unexpected error" in result.output

    @patch('langflow.cli.workflow.commands.components.APIClient')
    def test_components_unexpected_error_with_debug(self, mock_api_client_class):
        """Test components command with unexpected error and debug flag."""
        with patch("traceback.print_exc") as mock_traceback:
            result = self.runner.invoke(
                components,
                ["--debug"],
                obj={}  # Missing config to trigger error
            )

        assert result.exit_code == 1
        assert "Unexpected error" in result.output
        mock_traceback.assert_called_once()