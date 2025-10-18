"""Unit tests for the export command module."""

import json
import pytest
import yaml
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from click.testing import CliRunner

from langflow.cli.workflow.commands.export import export


class TestExportCommand:
    """Test the export CLI command."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = Mock()
        self.mock_config.ai_studio_url = "http://localhost:7860"
        self.mock_api_client = Mock()

        # Sample Langflow data
        self.sample_flow_data = {
            "name": "Test Flow",
            "description": "A test flow",
            "data": {
                "nodes": [
                    {"id": "node1", "type": "Agent", "data": {"type": "Agent"}},
                    {"id": "node2", "type": "LLM", "data": {"type": "LLM"}}
                ],
                "edges": [
                    {"id": "edge1", "source": "node1", "target": "node2"}
                ]
            }
        }

        # Sample Genesis specification
        self.sample_genesis_spec = {
            "name": "Test Agent",
            "description": "Converted from Langflow",
            "domain": "converted",
            "components": {
                "agent": {"type": "Agent", "id": "agent"},
                "llm": {"type": "LLM", "id": "llm"}
            }
        }

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_success_yaml(self, mock_api_client_class):
        """Test successful export to YAML format."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        export_result = {
            "specification": self.sample_genesis_spec,
            "statistics": {
                "components_converted": 2,
                "edges_converted": 1,
                "variables_preserved": 0
            },
            "warnings": []
        }
        mock_api_client.export_flow_sync.return_value = export_result

        # Create a temporary file with the flow data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(self.sample_flow_data, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
            assert "Flow exported successfully!" in result.output
            assert "Specification: Test Agent" in result.output
            assert "Components: 2" in result.output

            # Verify API call
            mock_api_client.export_flow_sync.assert_called_once_with(
                flow_data=self.sample_flow_data,
                preserve_variables=False,
                include_metadata=False,
                name_override=None,
                description_override=None,
                domain_override="converted"
            )
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_success_json(self, mock_api_client_class):
        """Test successful export to JSON format."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        export_result = {
            "specification": self.sample_genesis_spec,
            "warnings": []
        }
        mock_api_client.export_flow_sync.return_value = export_result

        # Create a temporary file with the flow data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(self.sample_flow_data, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path, "--format", "json"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
            assert "Flow exported successfully!" in result.output
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_with_custom_options(self, mock_api_client_class):
        """Test export with custom name, description, and domain."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        export_result = {
            "specification": self.sample_genesis_spec,
            "warnings": []
        }
        mock_api_client.export_flow_sync.return_value = export_result

        # Create a temporary file with the flow data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(self.sample_flow_data, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [
                    temp_file_path,
                    "--name", "Custom Agent",
                    "--description", "Custom description",
                    "--domain", "healthcare"
                ],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
            assert "Flow exported successfully!" in result.output

            # Verify API call with custom parameters
            mock_api_client.export_flow_sync.assert_called_once_with(
                flow_data=self.sample_flow_data,
                preserve_variables=False,
                include_metadata=False,
                name_override="Custom Agent",
                description_override="Custom description",
                domain_override="healthcare"
            )
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_with_preserve_vars(self, mock_api_client_class):
        """Test export with preserve variables flag."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        export_result = {
            "specification": self.sample_genesis_spec,
            "warnings": []
        }
        mock_api_client.export_flow_sync.return_value = export_result

        # Create a temporary file with the flow data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(self.sample_flow_data, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path, "--preserve-vars"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0

            # Verify preserve_variables flag
            mock_api_client.export_flow_sync.assert_called_once_with(
                flow_data=self.sample_flow_data,
                preserve_variables=True,
                include_metadata=False,
                name_override=None,
                description_override=None,
                domain_override="converted"
            )
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_with_metadata(self, mock_api_client_class):
        """Test export with metadata flag."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        export_result = {
            "specification": self.sample_genesis_spec,
            "warnings": []
        }
        mock_api_client.export_flow_sync.return_value = export_result

        # Create a temporary file with the flow data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(self.sample_flow_data, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path, "--include-metadata"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0

            # Verify include_metadata flag
            mock_api_client.export_flow_sync.assert_called_once_with(
                flow_data=self.sample_flow_data,
                preserve_variables=False,
                include_metadata=True,
                name_override=None,
                description_override=None,
                domain_override="converted"
            )
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_with_custom_output(self, mock_api_client_class):
        """Test export with custom output path."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        export_result = {
            "specification": self.sample_genesis_spec,
            "warnings": []
        }
        mock_api_client.export_flow_sync.return_value = export_result

        # Create a temporary file with the flow data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(self.sample_flow_data, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path, "--output", "output.yaml"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
            assert "Saving specification to: output.yaml" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_with_debug(self, mock_api_client_class):
        """Test export with debug flag."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        export_result = {
            "specification": self.sample_genesis_spec,
            "statistics": {
                "components_converted": 2,
                "edges_converted": 1,
                "variables_preserved": 0
            },
            "warnings": []
        }
        mock_api_client.export_flow_sync.return_value = export_result

        # Create a temporary file with the flow data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(self.sample_flow_data, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path, "--debug"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
            assert "Conversion Statistics:" in result.output
            assert "Components converted: 2" in result.output
            assert "Edges converted: 1" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_with_warnings(self, mock_api_client_class):
        """Test export with warnings from API."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        export_result = {
            "specification": self.sample_genesis_spec,
            "warnings": [
                "Some components could not be converted",
                "Variable mapping incomplete"
            ]
        }
        mock_api_client.export_flow_sync.return_value = export_result

        # Create a temporary file with the flow data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(self.sample_flow_data, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
            assert "Export warnings:" in result.output
            assert "Some components could not be converted" in result.output
            assert "Variable mapping incomplete" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_with_agent_goal(self, mock_api_client_class):
        """Test export with agent goal in specification."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        spec_with_goal = self.sample_genesis_spec.copy()
        spec_with_goal["agentGoal"] = "Help users with healthcare tasks"

        export_result = {
            "specification": spec_with_goal,
            "warnings": []
        }
        mock_api_client.export_flow_sync.return_value = export_result

        # Create a temporary file with the flow data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(self.sample_flow_data, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
            assert "Goal: Help users with healthcare tasks" in result.output
        finally:
            os.unlink(temp_file_path)

    def test_export_file_not_found(self):
        """Test export with non-existent file."""
        result = self.runner.invoke(
            export,
            ["nonexistent.json"],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 2
        # Click should handle the file existence check

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_invalid_json(self, mock_api_client_class):
        """Test export with invalid JSON input."""
        invalid_json = "invalid json content"

        # Create a temporary file with invalid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_file.write(invalid_json)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_invalid_flow_format(self, mock_api_client_class):
        """Test export with invalid flow format (not dict)."""
        # Create a temporary file with invalid flow format
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(["not", "a", "dict"], temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
            assert "Invalid Langflow file format" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_missing_nodes_edges(self, mock_api_client_class):
        """Test export with missing nodes or edges."""
        incomplete_flow = {
            "name": "Test Flow",
            "data": {
                "nodes": [],
                "edges": []
            }
        }

        # Create a temporary file with incomplete flow
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(incomplete_flow, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
            assert "Invalid flow: missing nodes or edges" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_connectivity_failure(self, mock_api_client_class):
        """Test export with AI Studio connectivity failure."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = False

        # Create a temporary file with flow data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(self.sample_flow_data, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
            assert "Cannot connect to AI Studio" in result.output
            assert "API connection required for flow export" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_api_error(self, mock_api_client_class):
        """Test export with API error."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.export_flow_sync.side_effect = Exception("API Error")

        # Create a temporary file with flow data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(self.sample_flow_data, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
            assert "Export failed: API Error" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    @patch('traceback.print_exc')
    def test_export_api_error_with_debug(self, mock_traceback, mock_api_client_class):
        """Test export with API error and debug flag."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.export_flow_sync.side_effect = Exception("API Error")

        # Create a temporary file with flow data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(self.sample_flow_data, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path, "--debug"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
            assert "Export failed: API Error" in result.output
            assert mock_traceback.call_count >= 1
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_no_specification_returned(self, mock_api_client_class):
        """Test export when API returns no specification."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        export_result = {
            "specification": None,
            "warnings": []
        }
        mock_api_client.export_flow_sync.return_value = export_result

        # Create a temporary file with flow data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(self.sample_flow_data, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
            assert "Export failed: No specification returned" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.export.APIClient')
    @patch('traceback.print_exc')
    def test_export_unexpected_error_with_debug(self, mock_traceback, mock_api_client_class):
        """Test export with unexpected error and debug flag."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.export_flow_sync.side_effect = RuntimeError("Unexpected error")

        # Create a temporary file with flow data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(self.sample_flow_data, temp_file)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                export,
                [temp_file_path, "--debug"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
            assert "Export failed: Unexpected error" in result.output
            assert mock_traceback.call_count >= 1
        finally:
            os.unlink(temp_file_path)