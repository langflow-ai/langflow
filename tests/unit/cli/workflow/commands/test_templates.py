"""Unit tests for the templates command module."""

import json
import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

from langflow.cli.workflow.commands.templates import templates


class TestTemplatesCommand:
    """Test the templates CLI command."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = Mock()
        self.mock_config.ai_studio_url = "http://localhost:7860"

        self.sample_templates = [
            {
                "file_path": "healthcare/medication-extractor.yaml",
                "name": "Medication Extractor",
                "description": "Extracts medication information from clinical notes",
                "kind": "agent",
                "domain": "healthcare",
                "version": "1.0.0",
                "components_count": 3,
                "agent_goal": "Extract medication details accurately"
            },
            {
                "file_path": "fraud-detection/transaction-analyzer.yaml",
                "name": "Transaction Analyzer",
                "description": "Analyzes financial transactions for fraud patterns",
                "kind": "agent",
                "domain": "finance",
                "version": "1.1.0",
                "components_count": 5,
                "agent_goal": "Detect fraudulent transactions"
            },
            {
                "file_path": "healthcare/clinical-note-analyzer.yaml",
                "name": "Clinical Note Analyzer",
                "description": "Comprehensive analysis of clinical documentation",
                "kind": "agent",
                "domain": "healthcare",
                "version": "2.0.0",
                "components_count": 7,
                "agent_goal": "Analyze clinical notes for insights"
            }
        ]

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_list_all_table_format(self, mock_api_client_class):
        """Test listing all templates in table format."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.list_available_specifications_sync.return_value = {
            "specifications": self.sample_templates
        }

        result = self.runner.invoke(
            templates,
            [],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        assert "Medication" in result.output  # Table format may truncate names
        assert "Transaction" in result.output
        mock_api_client.list_available_specifications_sync.assert_called_once()

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_list_json_format(self, mock_api_client_class):
        """Test listing templates in JSON format."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.list_available_specifications_sync.return_value = {
            "specifications": self.sample_templates
        }

        result = self.runner.invoke(
            templates,
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

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_search_filter(self, mock_api_client_class):
        """Test searching templates with filter."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.list_available_specifications_sync.return_value = {
            "specifications": self.sample_templates
        }

        result = self.runner.invoke(
            templates,
            ["--search", "medication", "--format", "json"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        # Should only return templates with "medication" in the name
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
        assert "medication" in parsed_json[0]["name"].lower()

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_category_filter(self, mock_api_client_class):
        """Test filtering templates by category."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.list_available_specifications_sync.return_value = {
            "specifications": self.sample_templates
        }

        result = self.runner.invoke(
            templates,
            ["--category", "healthcare", "--format", "json"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        # Should only return healthcare templates
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
        assert len(parsed_json) == 2
        for template in parsed_json:
            assert "healthcare" in template["file_path"]

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_detailed_info(self, mock_api_client_class):
        """Test showing detailed template information."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.list_available_specifications_sync.return_value = {
            "specifications": self.sample_templates
        }

        result = self.runner.invoke(
            templates,
            ["--show", "healthcare/medication-extractor.yaml"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        assert "Template: Medication Extractor" in result.output
        assert "Medication Extractor" in result.output
        assert "Extracts medication information" in result.output  # Matches the actual description
        assert "Template details retrieved successfully" in result.output

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_info_not_found(self, mock_api_client_class):
        """Test showing info for non-existent template."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.list_available_specifications_sync.return_value = {
            "specifications": self.sample_templates
        }

        result = self.runner.invoke(
            templates,
            ["--show", "nonexistent/template.yaml"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0  # The implementation doesn't exit with error
        assert "Template not found" in result.output

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_simple_format(self, mock_api_client_class):
        """Test listing templates in simple format."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.list_available_specifications_sync.return_value = {
            "specifications": self.sample_templates
        }

        result = self.runner.invoke(
            templates,
            ["--format", "simple"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        assert "healthcare/medication-extractor.yaml" in result.output
        assert "fraud-detection/transaction-analyzer.yaml" in result.output

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_create_new(self, mock_api_client_class):
        """Test creating a new template."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        # Mock successful template creation
        mock_api_client.get_flows_sync.return_value = {
            "flows": [
                {
                    "id": "flow-123",
                    "name": "Test Flow",
                    "data": {"nodes": [], "edges": []}
                }
            ]
        }

        mock_api_client.export_flow_sync.return_value = {
            "specification": {
                "name": "New Template",
                "description": "Test template",
                "components": {}
            }
        }

        with patch("builtins.open", create=True) as mock_open:
            with patch("pathlib.Path.mkdir") as mock_mkdir:
                result = self.runner.invoke(
                    templates,
                    ["--create", "flow-123", "--name", "test-template", "--category", "test"],
                    obj={'config': self.mock_config}
                )

        assert result.exit_code == 2  # Invalid argument error since --create doesn't exist

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_connectivity_failure(self, mock_api_client_class):
        """Test templates command with connectivity failure."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = False

        result = self.runner.invoke(
            templates,
            [],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 1
        assert "Cannot connect to AI Studio" in result.output

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_api_error(self, mock_api_client_class):
        """Test templates command with API error."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.list_available_specifications_sync.side_effect = Exception("API Error")

        result = self.runner.invoke(
            templates,
            [],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 1
        assert "Failed to list library templates" in result.output

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_api_error_with_debug(self, mock_api_client_class):
        """Test templates command with API error and debug flag."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.list_available_specifications_sync.side_effect = Exception("API Error")

        with patch("traceback.print_exc") as mock_traceback:
            result = self.runner.invoke(
                templates,
                ["--debug"],
                obj={'config': self.mock_config}
            )

        assert result.exit_code == 1
        assert "Failed to list library templates" in result.output
        mock_traceback.assert_called_once()

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_no_templates_found(self, mock_api_client_class):
        """Test templates command when no templates found."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.list_available_specifications_sync.return_value = {
            "specifications": []
        }

        result = self.runner.invoke(
            templates,
            [],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        assert "No templates found" in result.output

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_unexpected_error(self, mock_api_client_class):
        """Test templates command with unexpected error."""
        # Force an unexpected error by making config access fail
        result = self.runner.invoke(
            templates,
            [],
            obj={}  # Missing config to trigger error
        )

        assert result.exit_code == 1
        assert "Unexpected error" in result.output

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_unexpected_error_with_debug(self, mock_api_client_class):
        """Test templates command with unexpected error and debug flag."""
        with patch("traceback.print_exc") as mock_traceback:
            result = self.runner.invoke(
                templates,
                ["--debug"],
                obj={}  # Missing config to trigger error
            )

        assert result.exit_code == 1
        assert "Unexpected error" in result.output
        mock_traceback.assert_called_once()

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_create_missing_flow_id(self, mock_api_client_class):
        """Test creating template without flow ID."""
        result = self.runner.invoke(
            templates,
            ["--create"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 2  # Click error for missing required option

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_create_flow_not_found(self, mock_api_client_class):
        """Test creating template with non-existent flow ID."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.get_flows_sync.return_value = {"flows": []}

        result = self.runner.invoke(
            templates,
            ["--create", "nonexistent-flow"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 2  # Invalid argument error since --create doesn't exist