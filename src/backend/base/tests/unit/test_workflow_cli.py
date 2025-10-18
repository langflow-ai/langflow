"""Unit tests for workflow CLI commands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from click.testing import CliRunner

from langflow.cli.workflow.main import workflow
from langflow.cli.workflow.commands.export import export
from langflow.cli.workflow.utils.api_client import APIClient


class TestWorkflowCLI:
    """Test suite for workflow CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_workflow_command_help(self):
        """Test workflow command shows help."""
        result = self.runner.invoke(workflow, ['--help'])
        assert result.exit_code == 0
        assert 'Workflow specification management commands' in result.output

    @patch('langflow.cli.workflow.config.manager.ConfigManager')
    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_command_basic(self, mock_api_client, mock_config_manager):
        """Test basic export command functionality."""
        # Mock API client
        mock_client_instance = Mock()
        mock_api_client.return_value = mock_client_instance
        mock_client_instance.health_check_sync.return_value = True
        mock_client_instance.export_flow_sync.return_value = {
            'specification': {
                'id': 'urn:agent:genesis:test:flow:1.0.0',
                'name': 'Test Flow',
                'description': 'Test description',
                'components': {}
            },
            'success': True,
            'warnings': [],
            'statistics': {
                'components_converted': 0,
                'edges_converted': 0
            }
        }

        # Create temporary input file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            test_flow = {
                'name': 'Test Flow',
                'data': {
                    'nodes': [
                        {
                            'id': 'input1',
                            'data': {
                                'type': 'ChatInput',
                                'display_name': 'Input'
                            }
                        }
                    ],
                    'edges': [{'id': 'edge1', 'source': 'input1', 'target': 'output1'}]
                }
            }
            json.dump(test_flow, f)
            input_path = f.name

        try:
            # Create temporary output file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                output_path = f.name

            # Set up context object
            context_obj = {'config': mock_config_manager.return_value}

            # Test export command
            result = self.runner.invoke(export, [
                input_path,
                '--output', output_path,
                '--format', 'yaml'
            ], obj=context_obj)

            assert result.exit_code == 0
            assert 'Flow exported successfully!' in result.output
            mock_client_instance.export_flow_sync.assert_called_once()

        finally:
            # Clean up temporary files
            Path(input_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)

    @patch('langflow.cli.workflow.config.manager.ConfigManager')
    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_command_with_options(self, mock_api_client, mock_config_manager):
        """Test export command with various options."""
        # Mock API client
        mock_client_instance = Mock()
        mock_api_client.return_value = mock_client_instance
        mock_client_instance.health_check_sync.return_value = True
        mock_client_instance.export_flow_sync.return_value = {
            'specification': {
                'id': 'urn:agent:genesis:healthcare:custom-agent:1.0.0',
                'name': 'Custom Agent',
                'description': 'Custom description',
                'domain': 'healthcare',
                'components': {}
            },
            'success': True,
            'warnings': [],
            'statistics': {
                'components_converted': 2,
                'variables_preserved': 1
            }
        }

        # Create temporary input file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            test_flow = {
                'name': 'Original Flow',
                'data': {
                    'nodes': [
                        {
                            'id': 'agent1',
                            'data': {
                                'type': 'Agent',
                                'display_name': 'Agent'
                            }
                        }
                    ],
                    'edges': [{'id': 'edge1', 'source': 'input1', 'target': 'output1'}]
                }
            }
            json.dump(test_flow, f)
            input_path = f.name

        try:
            # Set up context object
            context_obj = {'config': mock_config_manager.return_value}

            # Test export command with options
            result = self.runner.invoke(export, [
                input_path,
                '--name', 'Custom Agent',
                '--description', 'Custom description',
                '--domain', 'healthcare',
                '--preserve-vars',
                '--include-metadata',
                '--format', 'json'
            ], obj=context_obj)

            assert result.exit_code == 0
            assert 'Flow exported successfully!' in result.output

            # Verify API was called with correct parameters
            call_args = mock_client_instance.export_flow_sync.call_args
            assert call_args[1]['name_override'] == 'Custom Agent'
            assert call_args[1]['description_override'] == 'Custom description'
            assert call_args[1]['domain_override'] == 'healthcare'
            assert call_args[1]['preserve_variables'] is True
            assert call_args[1]['include_metadata'] is True

        finally:
            # Clean up temporary files
            Path(input_path).unlink(missing_ok=True)

    @patch('langflow.cli.workflow.config.manager.ConfigManager')
    @patch('langflow.cli.workflow.commands.export.APIClient')
    def test_export_command_api_failure(self, mock_api_client, mock_config_manager):
        """Test export command when API is unavailable."""
        # Mock API client
        mock_client_instance = Mock()
        mock_api_client.return_value = mock_client_instance
        mock_client_instance.health_check_sync.return_value = False

        # Mock config manager
        mock_config_instance = Mock()
        mock_config_manager.return_value = mock_config_instance
        mock_config_instance.ai_studio_url = 'http://localhost:7860'

        # Create temporary input file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            test_flow = {'name': 'Test Flow', 'data': {'nodes': [{'id': 'input1', 'data': {'type': 'ChatInput'}}], 'edges': [{'id': 'edge1', 'source': 'input1', 'target': 'output1'}]}}
            json.dump(test_flow, f)
            input_path = f.name

        try:
            # Set up context object
            context_obj = {'config': mock_config_instance}

            # Test export command with API failure
            result = self.runner.invoke(export, [input_path], obj=context_obj)

            assert result.exit_code == 1
            assert 'Cannot connect to AI Studio' in result.output

        finally:
            # Clean up temporary files
            Path(input_path).unlink(missing_ok=True)

    def test_export_command_invalid_input(self):
        """Test export command with invalid input file."""
        result = self.runner.invoke(export, ['nonexistent_file.json'])
        assert result.exit_code != 0
        assert 'does not exist' in result.output or 'Error' in result.output


class TestAPIClient:
    """Test suite for API client export methods."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock config manager and its config
        mock_config_manager = Mock()
        mock_config = Mock()
        mock_config_manager.get_config.return_value = mock_config

        # Set up AI Studio config
        mock_ai_studio = Mock()
        mock_ai_studio.url = 'http://localhost:7860'
        mock_ai_studio.api_key = 'test-api-key'
        mock_config.ai_studio = mock_ai_studio

        self.api_client = APIClient(mock_config_manager)

    @patch('httpx.AsyncClient')
    def test_export_flow_success(self, mock_client):
        """Test successful flow export via API client."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            'specification': {'name': 'Test Flow'},
            'success': True
        }
        mock_response.raise_for_status.return_value = None

        # Mock async client properly
        mock_client_instance = Mock()

        # Make post return an awaitable
        async def mock_post(*args, **kwargs):
            return mock_response
        mock_client_instance.post = mock_post

        mock_client.return_value.__aenter__.return_value = mock_client_instance

        # Test flow data
        flow_data = {
            'name': 'Test Flow',
            'data': {'nodes': [{'id': 'input1', 'data': {'type': 'ChatInput'}}], 'edges': [{'id': 'edge1', 'source': 'input1', 'target': 'output1'}]}
        }

        # Call export_flow_sync
        result = self.api_client.export_flow_sync(flow_data)

        assert result['success'] is True
        assert 'specification' in result
        # Note: async post call assertion is complex, just verify result

    @patch('httpx.AsyncClient')
    def test_export_flows_batch_success(self, mock_client):
        """Test successful batch flow export via API client."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            'specifications': [
                {'name': 'Flow 1'},
                {'name': 'Flow 2'}
            ],
            'success': True,
            'total_processed': 2,
            'successful_exports': 2
        }
        mock_response.raise_for_status.return_value = None

        # Mock async client properly
        mock_client_instance = Mock()

        # Make post return an awaitable
        async def mock_post(*args, **kwargs):
            return mock_response
        mock_client_instance.post = mock_post

        mock_client.return_value.__aenter__.return_value = mock_client_instance

        # Test flow data
        flows = [
            {'name': 'Flow 1', 'data': {'nodes': [{'id': 'input1', 'data': {'type': 'ChatInput'}}], 'edges': [{'id': 'edge1', 'source': 'input1', 'target': 'output1'}]}},
            {'name': 'Flow 2', 'data': {'nodes': [{'id': 'input1', 'data': {'type': 'ChatInput'}}], 'edges': [{'id': 'edge1', 'source': 'input1', 'target': 'output1'}]}}
        ]

        # Call export_flows_batch_sync
        result = self.api_client.export_flows_batch_sync(flows)

        assert result['success'] is True
        assert result['total_processed'] == 2
        assert len(result['specifications']) == 2
        # Note: async post call assertion is complex, just verify result


if __name__ == "__main__":
    pytest.main([__file__])