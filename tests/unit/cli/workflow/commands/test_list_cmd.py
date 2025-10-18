"""Unit tests for the list command module."""

import json
import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

from langflow.cli.workflow.commands.list_cmd import (
    list_cmd,
    _list_flows,
    _list_templates,
    _list_components,
    _list_folders
)


class TestListCommand:
    """Test the list CLI command."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = Mock()
        self.mock_config.ai_studio_url = "http://localhost:7860"
        self.mock_api_client = Mock()

    @patch('langflow.cli.workflow.commands.list_cmd.APIClient')
    def test_list_connectivity_failure(self, mock_api_client_class):
        """Test list command with AI Studio connectivity failure."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = False

        result = self.runner.invoke(
            list_cmd,
            ["flows"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 1
        assert "Cannot connect to AI Studio" in result.output

    @patch('langflow.cli.workflow.commands.list_cmd.APIClient')
    @patch('langflow.cli.workflow.commands.list_cmd._list_flows')
    def test_list_flows_success(self, mock_list_flows, mock_api_client_class):
        """Test successful flows listing."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        result = self.runner.invoke(
            list_cmd,
            ["flows"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        mock_list_flows.assert_called_once_with(
            mock_api_client, None, None, 'table', 50, False
        )

    @patch('langflow.cli.workflow.commands.list_cmd.APIClient')
    @patch('langflow.cli.workflow.commands.list_cmd._list_templates')
    def test_list_templates_with_category(self, mock_list_templates, mock_api_client_class):
        """Test templates listing with category filter."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        result = self.runner.invoke(
            list_cmd,
            ["templates", "--category", "healthcare", "--format", "json"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        mock_list_templates.assert_called_once_with(
            mock_api_client, None, "healthcare", 'json', 50, False
        )

    @patch('langflow.cli.workflow.commands.list_cmd.APIClient')
    @patch('langflow.cli.workflow.commands.list_cmd._list_components')
    def test_list_components_with_filter(self, mock_list_components, mock_api_client_class):
        """Test components listing with filter."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        result = self.runner.invoke(
            list_cmd,
            ["components", "--filter", "agent", "--limit", "10"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        mock_list_components.assert_called_once_with(
            mock_api_client, "agent", 'table', 10, False
        )

    @patch('langflow.cli.workflow.commands.list_cmd.APIClient')
    @patch('langflow.cli.workflow.commands.list_cmd._list_folders')
    def test_list_folders_simple_format(self, mock_list_folders, mock_api_client_class):
        """Test folders listing with simple format."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        result = self.runner.invoke(
            list_cmd,
            ["folders", "--format", "simple"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 0
        mock_list_folders.assert_called_once_with(
            mock_api_client, None, 'simple', 50, False
        )

    @patch('langflow.cli.workflow.commands.list_cmd.APIClient')
    def test_list_unexpected_error(self, mock_api_client_class):
        """Test list command with unexpected error."""
        # Force an unexpected error by making config access fail
        result = self.runner.invoke(
            list_cmd,
            ["flows"],
            obj={}  # Missing config to trigger error
        )

        assert result.exit_code == 1
        assert "Unexpected error" in result.output

    @patch('langflow.cli.workflow.commands.list_cmd.APIClient')
    def test_list_unexpected_error_with_debug(self, mock_api_client_class):
        """Test list command with unexpected error and debug flag."""
        with patch("traceback.print_exc") as mock_traceback:
            result = self.runner.invoke(
                list_cmd,
                ["flows", "--debug"],
                obj={}  # Missing config to trigger error
            )

        assert result.exit_code == 1
        assert "Unexpected error" in result.output
        mock_traceback.assert_called_once()


class TestListFlows:
    """Test the _list_flows function."""

    def setup_method(self):
        """Setup test environment."""
        self.mock_api_client = Mock()
        self.sample_flows = [
            {
                "id": "flow-1",
                "name": "Test Flow 1",
                "description": "A test flow for healthcare",
                "updated_at": "2023-12-01T12:00:00Z",
                "folder_name": "Healthcare"
            },
            {
                "id": "flow-2",
                "name": "Test Flow 2",
                "description": "Another test flow with a very long description that exceeds the limit",
                "updated_at": "2023-12-02T12:00:00Z"
            }
        ]

    def test_list_flows_table_format(self):
        """Test listing flows in table format."""
        self.mock_api_client.get_flows_sync.return_value = {"flows": self.sample_flows}

        with patch("click.echo") as mock_echo:
            _list_flows(self.mock_api_client, None, None, "table", 50, False)

        # Verify success message was called
        mock_echo.assert_called()

    def test_list_flows_json_format(self):
        """Test listing flows in JSON format."""
        self.mock_api_client.get_flows_sync.return_value = {"flows": self.sample_flows}

        with patch("click.echo") as mock_echo:
            _list_flows(self.mock_api_client, None, None, "json", 50, False)

        # Verify JSON output - the second call contains the JSON data
        mock_echo.assert_called()
        call_args = mock_echo.call_args_list
        # Find the JSON call (the one that contains '[' or '{')
        json_output = None
        for call in call_args:
            output = call[0][0]
            if output.strip().startswith('[') or output.strip().startswith('{'):
                json_output = output
                break
        assert json_output is not None, "No JSON output found"
        parsed_json = json.loads(json_output)
        assert len(parsed_json) == 2

    def test_list_flows_simple_format(self):
        """Test listing flows in simple format."""
        self.mock_api_client.get_flows_sync.return_value = {"flows": self.sample_flows}

        with patch("click.echo") as mock_echo:
            _list_flows(self.mock_api_client, None, None, "simple", 50, False)

        # Verify simple output format
        mock_echo.assert_called()

    def test_list_flows_with_filter(self):
        """Test listing flows with name filter."""
        self.mock_api_client.get_flows_sync.return_value = {"flows": self.sample_flows}

        with patch("click.echo") as mock_echo:
            _list_flows(self.mock_api_client, "Test Flow 1", None, "json", 50, False)

        # Verify filtered output
        call_args = mock_echo.call_args_list
        # Find the JSON call (the one that contains '[' or '{')
        json_output = None
        for call in call_args:
            output = call[0][0]
            if output.strip().startswith('[') or output.strip().startswith('{'):
                json_output = output
                break
        assert json_output is not None, "No JSON output found"
        parsed_json = json.loads(json_output)
        assert len(parsed_json) == 1
        assert parsed_json[0]["name"] == "Test Flow 1"

    def test_list_flows_with_project_filter(self):
        """Test listing flows with project filter."""
        self.mock_api_client.get_flows_sync.return_value = {"flows": self.sample_flows}

        with patch("click.echo") as mock_echo:
            _list_flows(self.mock_api_client, None, "Healthcare", "json", 50, False)

        # Verify project filtering
        call_args = mock_echo.call_args_list
        # Find the JSON call (the one that contains '[' or '{')
        json_output = None
        for call in call_args:
            output = call[0][0]
            if output.strip().startswith('[') or output.strip().startswith('{'):
                json_output = output
                break
        assert json_output is not None, "No JSON output found"
        parsed_json = json.loads(json_output)
        assert len(parsed_json) == 1

    def test_list_flows_with_limit(self):
        """Test listing flows with limit."""
        self.mock_api_client.get_flows_sync.return_value = {"flows": self.sample_flows}

        with patch("click.echo") as mock_echo:
            _list_flows(self.mock_api_client, None, None, "json", 1, False)

        # Verify limit is applied
        call_args = mock_echo.call_args_list
        # Find the JSON call (the one that contains '[' or '{')
        json_output = None
        for call in call_args:
            output = call[0][0]
            if output.strip().startswith('[') or output.strip().startswith('{'):
                json_output = output
                break
        assert json_output is not None, "No JSON output found"
        parsed_json = json.loads(json_output)
        assert len(parsed_json) == 1

    def test_list_flows_no_flows(self):
        """Test listing flows when none exist."""
        self.mock_api_client.get_flows_sync.return_value = {"flows": []}

        with patch("click.echo") as mock_echo:
            _list_flows(self.mock_api_client, None, None, "table", 50, False)

        # Should call echo for info and warning messages even with empty results
        mock_echo.assert_called()
        # Verify warning message for no flows
        call_args = [call[0][0] for call in mock_echo.call_args_list]
        assert any("No flows found" in arg for arg in call_args)

    def test_list_flows_api_error(self):
        """Test listing flows with API error."""
        self.mock_api_client.get_flows_sync.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            _list_flows(self.mock_api_client, None, None, "table", 50, False)


class TestListTemplates:
    """Test the _list_templates function."""

    def setup_method(self):
        """Setup test environment."""
        self.mock_api_client = Mock()
        self.sample_templates = [
            {
                "file_path": "healthcare/medication-extractor.yaml",
                "name": "Medication Extractor",
                "kind": "agent",
                "description": "Extracts medication information from clinical notes"
            },
            {
                "file_path": "fraud-detection/transaction-analyzer.yaml",
                "name": "Transaction Analyzer",
                "kind": "agent",
                "description": "Analyzes transactions for fraud patterns with very long description"
            }
        ]

    def test_list_templates_table_format(self):
        """Test listing templates in table format."""
        self.mock_api_client.list_available_specifications_sync.return_value = {
            "specifications": self.sample_templates
        }

        with patch("click.echo") as mock_echo:
            _list_templates(self.mock_api_client, None, None, "table", 50, False)

        mock_echo.assert_called()

    def test_list_templates_with_filter(self):
        """Test listing templates with name filter."""
        self.mock_api_client.list_available_specifications_sync.return_value = {
            "specifications": self.sample_templates
        }

        with patch("click.echo") as mock_echo:
            _list_templates(self.mock_api_client, "Medication", None, "json", 50, False)

        # Verify filtered output
        call_args = mock_echo.call_args_list
        # Find the JSON call (the one that contains '[' or '{')
        json_output = None
        for call in call_args:
            output = call[0][0]
            if output.strip().startswith('[') or output.strip().startswith('{'):
                json_output = output
                break
        assert json_output is not None, "No JSON output found"
        parsed_json = json.loads(json_output)
        assert len(parsed_json) == 1
        assert parsed_json[0]["name"] == "Medication Extractor"

    def test_list_templates_with_category(self):
        """Test listing templates with category filter."""
        self.mock_api_client.list_available_specifications_sync.return_value = {
            "specifications": self.sample_templates
        }

        with patch("click.echo") as mock_echo:
            _list_templates(self.mock_api_client, None, "healthcare", "json", 50, False)

        # Verify category filtering
        call_args = mock_echo.call_args_list
        # Find the JSON call (the one that contains '[' or '{')
        json_output = None
        for call in call_args:
            output = call[0][0]
            if output.strip().startswith('[') or output.strip().startswith('{'):
                json_output = output
                break
        assert json_output is not None, "No JSON output found"
        parsed_json = json.loads(json_output)
        assert len(parsed_json) == 1

    def test_list_templates_no_templates(self):
        """Test listing templates when none exist."""
        self.mock_api_client.list_available_specifications_sync.return_value = {
            "specifications": []
        }

        with patch("click.echo") as mock_echo:
            _list_templates(self.mock_api_client, None, None, "table", 50, False)

        # Should call echo for info and warning messages even with empty results
        mock_echo.assert_called()
        # Verify warning message for no templates
        call_args = [call[0][0] for call in mock_echo.call_args_list]
        assert any("No templates found" in arg for arg in call_args)

    def test_list_templates_api_error(self):
        """Test listing templates with API error."""
        self.mock_api_client.list_available_specifications_sync.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            _list_templates(self.mock_api_client, None, None, "table", 50, False)


class TestListComponents:
    """Test the _list_components function."""

    def setup_method(self):
        """Setup test environment."""
        self.mock_api_client = Mock()
        self.sample_components = {
            "genesis:agent": {
                "component": "Agent",
                "description": "Main agent component",
                "is_tool": False
            },
            "genesis:llm": {
                "component": "ChatOpenAI",
                "description": "OpenAI language model",
                "is_tool": True
            }
        }

    def test_list_components_table_format(self):
        """Test listing components in table format."""
        self.mock_api_client.get_available_components_sync.return_value = {
            "components": self.sample_components
        }

        with patch("click.echo") as mock_echo:
            _list_components(self.mock_api_client, None, "table", 50, False)

        mock_echo.assert_called()

    def test_list_components_with_filter(self):
        """Test listing components with filter."""
        self.mock_api_client.get_available_components_sync.return_value = {
            "components": self.sample_components
        }

        with patch("click.echo") as mock_echo:
            _list_components(self.mock_api_client, "agent", "json", 50, False)

        # Verify filtered output
        call_args = mock_echo.call_args_list
        # Find the JSON call (the one that contains '[' or '{')
        json_output = None
        for call in call_args:
            output = call[0][0]
            if output.strip().startswith('[') or output.strip().startswith('{'):
                json_output = output
                break
        assert json_output is not None, "No JSON output found"
        parsed_json = json.loads(json_output)
        assert len(parsed_json) == 1
        assert parsed_json[0]["type"] == "genesis:agent"

    def test_list_components_no_components(self):
        """Test listing components when none exist."""
        self.mock_api_client.get_available_components_sync.return_value = {
            "components": {}
        }

        with patch("click.echo") as mock_echo:
            _list_components(self.mock_api_client, None, "table", 50, False)

        # Should call echo for info and warning messages even with empty results
        mock_echo.assert_called()
        # Verify warning message for no components
        call_args = [call[0][0] for call in mock_echo.call_args_list]
        assert any("No components found" in arg for arg in call_args)

    def test_list_components_api_error(self):
        """Test listing components with API error."""
        self.mock_api_client.get_available_components_sync.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            _list_components(self.mock_api_client, None, "table", 50, False)


class TestListFolders:
    """Test the _list_folders function."""

    def setup_method(self):
        """Setup test environment."""
        self.mock_api_client = Mock()
        self.sample_folders = [
            {
                "id": "folder-1",
                "name": "Healthcare",
                "description": "Healthcare related agents"
            },
            {
                "id": "folder-2",
                "name": "Fraud Detection",
                "description": "Fraud detection agents with very long description that exceeds limit"
            }
        ]

    def test_list_folders_table_format(self):
        """Test listing folders in table format."""
        self.mock_api_client.get_folders_sync.return_value = {"folders": self.sample_folders}

        with patch("click.echo") as mock_echo:
            _list_folders(self.mock_api_client, None, "table", 50, False)

        mock_echo.assert_called()

    def test_list_folders_with_filter(self):
        """Test listing folders with filter."""
        self.mock_api_client.get_folders_sync.return_value = {"folders": self.sample_folders}

        with patch("click.echo") as mock_echo:
            _list_folders(self.mock_api_client, "Healthcare", "json", 50, False)

        # Verify filtered output
        call_args = mock_echo.call_args_list
        # Find the JSON call (the one that contains '[' or '{')
        json_output = None
        for call in call_args:
            output = call[0][0]
            if output.strip().startswith('[') or output.strip().startswith('{'):
                json_output = output
                break
        assert json_output is not None, "No JSON output found"
        parsed_json = json.loads(json_output)
        assert len(parsed_json) == 1
        assert parsed_json[0]["name"] == "Healthcare"

    def test_list_folders_no_folders(self):
        """Test listing folders when none exist."""
        self.mock_api_client.get_folders_sync.return_value = {"folders": []}

        with patch("click.echo") as mock_echo:
            _list_folders(self.mock_api_client, None, "table", 50, False)

        # Should call echo for info and warning messages even with empty results
        mock_echo.assert_called()
        # Verify warning message for no folders
        call_args = [call[0][0] for call in mock_echo.call_args_list]
        assert any("No folders found" in arg for arg in call_args)

    def test_list_folders_api_error(self):
        """Test listing folders with API error."""
        self.mock_api_client.get_folders_sync.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            _list_folders(self.mock_api_client, None, "table", 50, False)