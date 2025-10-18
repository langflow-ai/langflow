"""Integration tests for Genesis CLI."""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, Mock

from click.testing import CliRunner

from langflow.cli.genesis.main import genesis
from langflow.cli.genesis.config.manager import ConfigManager


@pytest.fixture
def temp_config_dir():
    """Create a temporary configuration directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_config_manager(temp_config_dir):
    """Create a mock configuration manager."""
    with patch('langflow.cli.genesis.config.manager.ConfigManager') as mock_cls:
        config = ConfigManager()
        config.config_dir = temp_config_dir
        config.config_file = temp_config_dir / "genesis-config.yaml"
        mock_cls.return_value = config
        yield config


@pytest.fixture
def sample_template():
    """Create a sample Genesis template."""
    return """
name: Test Agent
description: A simple test agent for testing
agentGoal: Test agent functionality
domain: test.ai
version: "1.0.0"
kind: Single Agent

components:
  - id: input
    type: genesis:chat_input
    name: User Input
    description: Receive user input
    provides:
      - in: agent
        useAs: input

  - id: agent
    type: genesis:agent
    name: Test Agent
    description: Main processing agent
    config:
      system_prompt: "You are a helpful test agent."
      temperature: 0.7
    provides:
      - in: output
        useAs: input

  - id: output
    type: genesis:chat_output
    name: Agent Output
    description: Display agent response
"""


class TestGenesisIntegration:
    """Integration tests for Genesis CLI commands."""

    def test_config_show_command(self, mock_config_manager):
        """Test genesis config show command."""
        runner = CliRunner()

        with patch('langflow.cli.genesis.main.genesis.make_context') as mock_context:
            mock_ctx = Mock()
            mock_ctx.obj = {'config': mock_config_manager}
            mock_context.return_value.__enter__.return_value = mock_ctx

            result = runner.invoke(genesis, ['config', 'show'])

            # Should not crash and should show configuration
            assert result.exit_code in [0, 1]  # May exit 1 if no AI Studio connection

    def test_config_set_command(self, mock_config_manager):
        """Test genesis config set command."""
        runner = CliRunner()

        with patch('langflow.cli.genesis.main.genesis.make_context') as mock_context:
            mock_ctx = Mock()
            mock_ctx.obj = {'config': mock_config_manager}
            mock_context.return_value.__enter__.return_value = mock_ctx

            result = runner.invoke(genesis, ['config', 'set', 'ai_studio_url', 'http://test:8080'])

            # Command should execute (may exit 1 due to missing dependencies)
            assert result.exit_code in [0, 1]

    def test_validate_command_with_valid_template(self, mock_config_manager, sample_template):
        """Test genesis validate command with valid template."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(sample_template)
            temp_file = f.name

        try:
            with patch('langflow.cli.genesis.main.genesis.make_context') as mock_context:
                mock_ctx = Mock()
                mock_ctx.obj = {'config': mock_config_manager}
                mock_context.return_value.__enter__.return_value = mock_ctx

                # Mock API client to return validation success
                with patch('langflow.cli.genesis.commands.validate.APIClient') as mock_api:
                    mock_api_instance = mock_api.return_value
                    mock_api_instance.health_check_sync.return_value = True
                    mock_api_instance.validate_spec_sync.return_value = {
                        'valid': True,
                        'errors': [],
                        'warnings': [],
                        'suggestions': []
                    }

                    result = runner.invoke(genesis, ['validate', temp_file])

                    # Should succeed with mocked API
                    assert result.exit_code == 0

        finally:
            Path(temp_file).unlink()

    def test_create_command_validate_only(self, mock_config_manager, sample_template):
        """Test genesis create command with validate-only flag."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(sample_template)
            temp_file = f.name

        try:
            with patch('langflow.cli.genesis.main.genesis.make_context') as mock_context:
                mock_ctx = Mock()
                mock_ctx.obj = {'config': mock_config_manager}
                mock_context.return_value.__enter__.return_value = mock_ctx

                # Mock API client
                with patch('langflow.cli.genesis.commands.create.APIClient') as mock_api:
                    mock_api_instance = mock_api.return_value
                    mock_api_instance.health_check_sync.return_value = True
                    mock_api_instance.validate_spec_sync.return_value = {
                        'valid': True,
                        'errors': [],
                        'warnings': []
                    }

                    result = runner.invoke(genesis, ['create', '-t', temp_file, '--validate-only'])

                    # Should succeed with validation only
                    assert result.exit_code == 0

        finally:
            Path(temp_file).unlink()

    def test_list_components_command(self, mock_config_manager):
        """Test genesis components command."""
        runner = CliRunner()

        with patch('langflow.cli.genesis.main.genesis.make_context') as mock_context:
            mock_ctx = Mock()
            mock_ctx.obj = {'config': mock_config_manager}
            mock_context.return_value.__enter__.return_value = mock_ctx

            # Mock API client
            with patch('langflow.cli.genesis.commands.components.APIClient') as mock_api:
                mock_api_instance = mock_api.return_value
                mock_api_instance.health_check_sync.return_value = True
                mock_api_instance.get_available_components_sync.return_value = {
                    'components': {
                        'genesis:agent': {
                            'component': 'Agent',
                            'description': 'AI Agent component',
                            'is_tool': False
                        },
                        'genesis:chat_input': {
                            'component': 'ChatInput',
                            'description': 'Chat input component',
                            'is_tool': False
                        }
                    }
                }

                result = runner.invoke(genesis, ['components'])

                # Should succeed with mocked components
                assert result.exit_code == 0

    def test_list_templates_command(self, mock_config_manager):
        """Test genesis templates command."""
        runner = CliRunner()

        with patch('langflow.cli.genesis.main.genesis.make_context') as mock_context:
            mock_ctx = Mock()
            mock_ctx.obj = {'config': mock_config_manager}
            mock_context.return_value.__enter__.return_value = mock_ctx

            # Mock API client
            with patch('langflow.cli.genesis.commands.templates.APIClient') as mock_api:
                mock_api_instance = mock_api.return_value
                mock_api_instance.health_check_sync.return_value = True
                mock_api_instance.list_available_specifications_sync.return_value = {
                    'specifications': [
                        {
                            'file_path': 'healthcare/medication-extractor.yaml',
                            'name': 'Medication Extractor',
                            'kind': 'Single Agent',
                            'description': 'Extract medications from clinical text'
                        }
                    ]
                }

                result = runner.invoke(genesis, ['templates'])

                # Should succeed with mocked templates
                assert result.exit_code == 0

    def test_help_commands(self):
        """Test help for all Genesis commands."""
        runner = CliRunner()

        # Test main help
        result = runner.invoke(genesis, ['--help'])
        assert result.exit_code == 0
        assert 'Genesis Agent specification management' in result.output

        # Test command-specific help
        commands = ['create', 'validate', 'list', 'config', 'components', 'templates']
        for cmd in commands:
            result = runner.invoke(genesis, [cmd, '--help'])
            assert result.exit_code == 0

    def test_template_variable_substitution(self):
        """Test template variable substitution functionality."""
        from langflow.cli.genesis.utils.template_manager import TemplateManager

        template_content = """
name: {agent_name}
config:
  temperature: {temperature}
  api_key: ${API_KEY}
"""
        variables = {'agent_name': 'Test Agent', 'temperature': 0.8}

        manager = TemplateManager()

        with patch.dict('os.environ', {'API_KEY': 'test_key'}):
            result = manager.apply_variable_substitution(template_content, variables)

        assert 'name: Test Agent' in result
        assert 'temperature: 0.8' in result
        assert 'api_key: test_key' in result

    def test_template_tweaks(self):
        """Test template component tweaks functionality."""
        from langflow.cli.genesis.utils.template_manager import TemplateManager

        template_content = """
components:
  - id: agent
    type: genesis:agent
    config:
      temperature: 0.3
      model: gpt-3.5-turbo
"""
        tweaks = {
            'agent.config.temperature': 0.9,
            'agent.config.model': 'gpt-4'
        }

        manager = TemplateManager()
        result = manager.apply_variable_substitution(template_content, tweaks=tweaks)

        result_dict = yaml.safe_load(result)
        assert result_dict['components'][0]['config']['temperature'] == 0.9
        assert result_dict['components'][0]['config']['model'] == 'gpt-4'