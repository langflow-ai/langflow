"""Integration tests for the Workflow CLI end-to-end workflows."""

import json
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import pytest
from click.testing import CliRunner

from langflow.cli.workflow.main import workflow


class TestWorkflowCLIIntegration:
    """Integration tests for end-to-end workflow CLI operations."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()

        # Sample specification for testing
        self.sample_spec = {
            "name": "Integration Test Agent",
            "description": "An agent for integration testing",
            "kind": "agent",
            "domain": "testing",
            "version": "1.0.0",
            "agentGoal": "Test end-to-end CLI workflows",
            "components": [
                {
                    "id": "agent",
                    "type": "Agent",
                    "config": {
                        "temperature": 0.7,
                        "model": "gpt-4"
                    }
                },
                {
                    "id": "llm",
                    "type": "LLM",
                    "config": {
                        "api_key": "{api_key}",
                        "model": "gpt-4"
                    }
                }
            ],
            "connections": [
                {
                    "from": "agent",
                    "to": "llm"
                }
            ]
        }

        # Sample flow data
        self.sample_flow = {
            "name": "Test Flow",
            "description": "Integration test flow",
            "data": {
                "nodes": [
                    {
                        "id": "node1",
                        "type": "Agent",
                        "data": {"type": "Agent", "config": {}}
                    },
                    {
                        "id": "node2",
                        "type": "LLM",
                        "data": {"type": "LLM", "config": {}}
                    }
                ],
                "edges": [
                    {
                        "id": "edge1",
                        "source": "node1",
                        "target": "node2"
                    }
                ]
            }
        }

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_workflow_success(self, mock_api_client_class):
        """Test successful validation workflow."""
        # Setup mocks
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.validate_spec_sync.return_value = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }

        # Create temporary spec file
        spec_file = Path(self.temp_dir) / "test_spec.yaml"
        with open(spec_file, "w") as f:
            yaml.dump(self.sample_spec, f)

        # Run validation command
        result = self.runner.invoke(workflow, ["validate", str(spec_file)])

        assert result.exit_code == 0
        assert "Validation passed!" in result.output

    @patch('langflow.cli.workflow.commands.create.APIClient')
    def test_create_validate_export_workflow(self, mock_api_client_class):
        """Test complete create -> validate -> export workflow."""
        # Setup mocks for create command
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        # Mock validation
        mock_api_client.validate_spec_sync.return_value = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        # Mock conversion
        mock_api_client.convert_spec_sync.return_value = {
            "flow": self.sample_flow
        }

        # Mock flow creation
        mock_api_client.create_flow_sync.return_value = {
            "id": "flow-123",
            "name": "Integration Test Agent"
        }

        # Create temporary spec file
        spec_file = Path(self.temp_dir) / "test_spec.yaml"
        with open(spec_file, "w") as f:
            yaml.dump(self.sample_spec, f)

        # Step 1: Create flow from spec
        result = self.runner.invoke(
            workflow,
            ["create", "-t", str(spec_file), "--var", "api_key=test-key"]
        )

        assert result.exit_code == 0
        assert "Flow created successfully!" in result.output
        assert "Flow ID: flow-123" in result.output

    @patch('langflow.cli.workflow.commands.create.APIClient')
    def test_create_with_output_file_workflow(self, mock_api_client_class):
        """Test create workflow with output to file."""
        # Setup mocks
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        mock_api_client.validate_spec_sync.return_value = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        mock_api_client.convert_spec_sync.return_value = {
            "flow": self.sample_flow
        }

        # Create temporary spec file
        spec_file = Path(self.temp_dir) / "test_spec.yaml"
        output_file = Path(self.temp_dir) / "output_flow.json"

        with open(spec_file, "w") as f:
            yaml.dump(self.sample_spec, f)

        # Run create command with output
        with patch("builtins.open", mock_open()) as mock_file:
            result = self.runner.invoke(
                workflow,
                ["create", "-t", str(spec_file), "-o", str(output_file)]
            )

        assert result.exit_code == 0
        assert "Flow saved successfully!" in result.output
        mock_file.assert_called()

    @patch('langflow.cli.workflow.commands.list_cmd.APIClient')
    def test_list_resources_workflow(self, mock_api_client_class):
        """Test listing different resource types."""
        # Setup mocks
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        # Mock flows
        mock_api_client.get_flows_sync.return_value = {
            "flows": [
                {
                    "id": "flow-1",
                    "name": "Test Flow 1",
                    "description": "First test flow",
                    "updated_at": "2023-12-01T12:00:00Z"
                }
            ]
        }

        # Mock templates
        mock_api_client.list_available_specifications_sync.return_value = {
            "specifications": [
                {
                    "file_path": "healthcare/agent.yaml",
                    "name": "Healthcare Agent",
                    "description": "Healthcare processing agent",
                    "kind": "agent"
                }
            ]
        }

        # Test listing flows
        result = self.runner.invoke(workflow, ["list", "flows"])
        assert result.exit_code == 0
        assert "Test Flow 1" in result.output

        # Test listing templates
        result = self.runner.invoke(workflow, ["list", "templates"])
        assert result.exit_code == 0
        assert "Healthcare Agent" in result.output

    @patch('langflow.cli.workflow.commands.config.APIClient')
    def test_config_management_workflow(self, mock_api_client_class):
        """Test configuration management workflow."""
        # Setup mocks
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.get_available_components_sync.return_value = {"components": {}}

        # Test showing config
        result = self.runner.invoke(workflow, ["config", "show"])
        assert result.exit_code == 0
        assert "Genesis CLI Configuration" in result.output

        # Test setting config value
        result = self.runner.invoke(
            workflow,
            ["config", "set", "ai_studio_url", "http://test:8080"]
        )
        assert result.exit_code == 0
        assert "Configuration updated" in result.output

        # Test config connection test
        result = self.runner.invoke(workflow, ["config", "test"])
        assert result.exit_code == 0
        assert "Successfully connected to AI Studio" in result.output

    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_workflow_success(self, mock_api_client_class):
        """Test successful export workflow."""
        # Setup mocks
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        mock_api_client.export_flow_sync.return_value = {
            "specification": self.sample_spec,
            "statistics": {
                "components_converted": 2,
                "edges_converted": 1,
                "variables_preserved": 1
            },
            "warnings": []
        }

        # Create temporary flow file
        flow_file = Path(self.temp_dir) / "test_flow.json"
        output_file = Path(self.temp_dir) / "exported_spec.yaml"

        with open(flow_file, "w") as f:
            json.dump(self.sample_flow, f)

        # Run export command
        with patch("builtins.open", mock_open()) as mock_file:
            result = self.runner.invoke(
                workflow,
                ["export", str(flow_file), "-o", str(output_file), "--preserve-vars"]
            )

        assert result.exit_code == 0
        assert "Flow exported successfully!" in result.output

    @patch('langflow.cli.workflow.commands.components.APIClient')
    def test_components_information_workflow(self, mock_api_client_class):
        """Test components information workflow."""
        # Setup mocks
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        mock_api_client.get_available_components_sync.return_value = {
            "components": {
                "genesis:agent": {
                    "component": "Agent",
                    "description": "Main agent component",
                    "is_tool": False,
                    "parameters": {
                        "temperature": "float",
                        "model": "string"
                    }
                }
            }
        }

        # Test listing components
        result = self.runner.invoke(workflow, ["components"])
        assert result.exit_code == 0
        assert "genesis:agent" in result.output

        # Test component details
        result = self.runner.invoke(workflow, ["components", "--info", "genesis:agent"])
        assert result.exit_code == 0
        assert "Component Details" in result.output

    @patch('langflow.cli.workflow.commands.templates.APIClient')
    def test_templates_workflow(self, mock_api_client_class):
        """Test templates management workflow."""
        # Setup mocks
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        mock_api_client.list_available_specifications_sync.return_value = {
            "specifications": [
                {
                    "file_path": "healthcare/medication-extractor.yaml",
                    "name": "Medication Extractor",
                    "description": "Extracts medication information",
                    "kind": "agent",
                    "domain": "healthcare",
                    "components_count": 3
                }
            ]
        }

        # Test listing templates
        result = self.runner.invoke(workflow, ["templates"])
        assert result.exit_code == 0
        assert "Medication Extractor" in result.output

        # Test template search
        result = self.runner.invoke(
            workflow,
            ["templates", "--search", "medication", "--category", "healthcare"]
        )
        assert result.exit_code == 0
        assert "Medication Extractor" in result.output

    def test_error_handling_workflow(self):
        """Test error handling in various scenarios."""
        # Test with non-existent file
        result = self.runner.invoke(
            workflow,
            ["validate", "/nonexistent/file.yaml"]
        )
        assert result.exit_code != 0

        # Test with invalid command
        result = self.runner.invoke(workflow, ["nonexistent-command"])
        assert result.exit_code != 0

    @patch('langflow.cli.workflow.commands.create.APIClient')
    def test_variable_substitution_workflow(self, mock_api_client_class):
        """Test variable substitution in create workflow."""
        # Setup mocks
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        mock_api_client.validate_spec_sync.return_value = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        mock_api_client.convert_spec_sync.return_value = {
            "flow": self.sample_flow
        }

        mock_api_client.create_flow_sync.return_value = {
            "id": "flow-123"
        }

        # Create spec with variables
        spec_with_vars = self.sample_spec.copy()
        spec_with_vars["components"][1]["config"]["api_key"] = "{api_key}"

        spec_file = Path(self.temp_dir) / "variable_spec.yaml"
        with open(spec_file, "w") as f:
            yaml.dump(spec_with_vars, f)

        # Create variables file
        variables = {"api_key": "test-api-key-123"}
        var_file = Path(self.temp_dir) / "variables.json"
        with open(var_file, "w") as f:
            json.dump(variables, f)

        # Run create with variables
        result = self.runner.invoke(
            workflow,
            [
                "create",
                "-t", str(spec_file),
                "--var-file", str(var_file),
                "--var", "additional_var=value"
            ]
        )

        assert result.exit_code == 0
        assert "Flow created successfully!" in result.output

        # Verify that convert_spec was called with variables
        mock_api_client.convert_spec_sync.assert_called_once()
        call_args = mock_api_client.convert_spec_sync.call_args
        assert call_args[1]['variables'] is not None

    @patch('langflow.cli.workflow.commands.create.APIClient')
    def test_library_template_workflow(self, mock_api_client_class):
        """Test using library templates in create workflow."""
        # Setup mocks
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client

        mock_api_client.create_flow_from_library_sync.return_value = {
            "success": True,
            "flow_id": "library-flow-123",
            "flow_name": "Healthcare Agent"
        }

        # Test creating from library template
        result = self.runner.invoke(
            workflow,
            ["create", "-t", "healthcare/medication-extractor"]
        )

        assert result.exit_code == 0
        assert "Flow created from library template" in result.output
        assert "library-flow-123" in result.output

    def test_help_system_integration(self):
        """Test help system integration across commands."""
        # Test main help
        result = self.runner.invoke(workflow, ["--help"])
        assert result.exit_code == 0
        assert "Workflow specification management commands" in result.output

        # Test individual command help
        commands = ["create", "validate", "export", "list", "config", "components", "templates"]

        for cmd in commands:
            result = self.runner.invoke(workflow, [cmd, "--help"])
            assert result.exit_code == 0
            assert f"{cmd}" in result.output.lower()

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_different_output_formats_workflow(self, mock_api_client_class):
        """Test different output formats across commands."""
        # Setup mocks
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        mock_api_client.validate_spec_sync.return_value = validation_result

        # Create temporary spec file
        spec_file = Path(self.temp_dir) / "test_spec.yaml"
        with open(spec_file, "w") as f:
            yaml.dump(self.sample_spec, f)

        # Test different output formats for validation
        formats = ["table", "json", "report"]

        for fmt in formats:
            result = self.runner.invoke(
                workflow,
                ["validate", str(spec_file), "--format", fmt]
            )
            assert result.exit_code == 0

    @patch('langflow.cli.workflow.commands.create.APIClient')
    def test_error_propagation_workflow(self, mock_api_client_class):
        """Test error propagation through workflow steps."""
        # Setup mocks for failure scenarios
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = False

        # Create temporary spec file
        spec_file = Path(self.temp_dir) / "test_spec.yaml"
        with open(spec_file, "w") as f:
            yaml.dump(self.sample_spec, f)

        # Test connectivity failure
        result = self.runner.invoke(
            workflow,
            ["create", "-t", str(spec_file)]
        )

        assert result.exit_code == 1
        assert "Cannot connect to AI Studio" in result.output