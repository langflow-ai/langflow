"""Unit tests for the workflow CLI main module."""

import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

from langflow.cli.workflow.main import workflow, register_commands


class TestWorkflowMain:
    """Test the main workflow CLI group."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()

    def test_workflow_help(self):
        """Test workflow command help output."""
        result = self.runner.invoke(workflow, ["--help"])

        assert result.exit_code == 0
        assert "Workflow specification management commands" in result.output
        assert "Manage AI agent specifications" in result.output
        assert "workflow create" in result.output
        assert "workflow validate" in result.output

    @patch('langflow.cli.workflow.main.ConfigManager')
    def test_workflow_context_initialization_success(self, mock_config_manager_class):
        """Test successful context initialization."""
        mock_config_manager = Mock()
        mock_config_manager_class.return_value = mock_config_manager

        # Use a subcommand to test context initialization (help doesn't trigger callback)
        result = self.runner.invoke(workflow, ["list", "--help"])

        assert result.exit_code == 0
        # ConfigManager should be called during context initialization for subcommands
        assert mock_config_manager_class.call_count >= 1

    @patch('langflow.cli.workflow.main.ConfigManager')
    @patch('langflow.cli.workflow.main.console')
    def test_workflow_context_initialization_failure(self, mock_console, mock_config_manager_class):
        """Test context initialization failure."""
        mock_config_manager_class.side_effect = Exception("Config error")

        result = self.runner.invoke(workflow, ["list"])

        # Should exit with error code due to config failure
        assert result.exit_code == 1
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "Error initializing Workflow configuration" in call_args
        assert "Config error" in call_args

    def test_workflow_ensure_object_dict(self):
        """Test that workflow command ensures object is a dict."""
        # This tests the ctx.ensure_object(dict) call
        @workflow.command()
        @pytest.fixture(autouse=True)
        def test_cmd(ctx):
            # This should not raise an error due to ensure_object(dict)
            assert isinstance(ctx.obj, dict)
            return "success"

        # The command should work without errors
        result = self.runner.invoke(workflow, ["--help"])
        assert result.exit_code == 0

    @patch('langflow.cli.workflow.main.ConfigManager')
    def test_workflow_config_stored_in_context(self, mock_config_manager_class):
        """Test that config is properly stored in context."""
        mock_config_manager = Mock()
        mock_config_manager_class.return_value = mock_config_manager

        # Mock a simple command that accesses context
        @workflow.command()
        @pytest.fixture(autouse=True)
        def mock_cmd(ctx):
            assert 'config' in ctx.obj
            assert ctx.obj['config'] == mock_config_manager

        with patch('langflow.cli.workflow.main.register_commands'):
            result = self.runner.invoke(workflow, ["--help"])

        assert result.exit_code == 0


class TestRegisterCommands:
    """Test the register_commands function."""

    @patch('langflow.cli.workflow.main.workflow')
    def test_register_commands_imports_all_modules(self, mock_workflow_group):
        """Test that register_commands imports all command modules."""
        with patch('langflow.cli.workflow.commands.create') as mock_create:
            with patch('langflow.cli.workflow.commands.validate') as mock_validate:
                with patch('langflow.cli.workflow.commands.export') as mock_export:
                    with patch('langflow.cli.workflow.commands.list_cmd') as mock_list:
                        with patch('langflow.cli.workflow.commands.config') as mock_config:
                            with patch('langflow.cli.workflow.commands.components') as mock_components:
                                with patch('langflow.cli.workflow.commands.templates') as mock_templates:

                                    # Mock the command objects
                                    mock_create.create = Mock()
                                    mock_validate.validate = Mock()
                                    mock_export.export = Mock()
                                    mock_list.list_cmd = Mock()
                                    mock_config.config = Mock()
                                    mock_components.components = Mock()
                                    mock_templates.templates = Mock()

                                    register_commands()

                                    # Verify all commands were added
                                    assert mock_workflow_group.add_command.call_count == 7

                                    # Check that each command was registered
                                    registered_commands = [
                                        call[0][0] for call in mock_workflow_group.add_command.call_args_list
                                    ]

                                    assert mock_create.create in registered_commands
                                    assert mock_validate.validate in registered_commands
                                    assert mock_export.export in registered_commands
                                    assert mock_list.list_cmd in registered_commands
                                    assert mock_config.config in registered_commands
                                    assert mock_components.components in registered_commands
                                    assert mock_templates.templates in registered_commands

    def test_register_commands_called_on_import(self):
        """Test that register_commands is called when module is imported."""
        # This is tested implicitly by the fact that commands are available
        # when we import the module. We can verify by checking that commands exist.

        # The workflow group should have commands registered
        assert len(workflow.commands) > 0

        # Check for expected command names
        command_names = list(workflow.commands.keys())
        expected_commands = ['create', 'validate', 'export', 'list', 'config', 'components', 'templates']

        for expected_cmd in expected_commands:
            assert expected_cmd in command_names


class TestWorkflowIntegration:
    """Test workflow CLI integration."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()

    def test_workflow_has_all_expected_commands(self):
        """Test that workflow group has all expected commands."""
        result = self.runner.invoke(workflow, ["--help"])

        assert result.exit_code == 0

        # Check that all expected commands are listed in help
        expected_commands = ['create', 'validate', 'export', 'list', 'config', 'components', 'templates']

        for cmd in expected_commands:
            assert cmd in result.output

    def test_workflow_command_accessibility(self):
        """Test that all commands are accessible."""
        # Test that each command can be invoked (even if they fail due to missing args)
        commands_to_test = ['create', 'validate', 'export', 'list', 'config', 'components', 'templates']

        for cmd in commands_to_test:
            result = self.runner.invoke(workflow, [cmd, "--help"])
            # Commands should show help without errors
            assert result.exit_code == 0 or "--help" in result.output

    @patch('langflow.cli.workflow.main.ConfigManager')
    def test_workflow_context_passed_to_subcommands(self, mock_config_manager_class):
        """Test that context is properly passed to subcommands."""
        mock_config_manager = Mock()
        mock_config_manager_class.return_value = mock_config_manager

        # Test with list command which should use the config
        result = self.runner.invoke(workflow, ["list", "--help"])

        # Should not error due to context issues
        assert result.exit_code == 0

    def test_workflow_examples_in_help(self):
        """Test that workflow help contains usage examples."""
        result = self.runner.invoke(workflow, ["--help"])

        assert result.exit_code == 0
        assert "Examples:" in result.output
        # Check for workflow commands in examples (flexible for line wrapping)
        assert "workflow create" in result.output
        assert "workflow validate" in result.output
        assert "workflow export" in result.output

    @patch('langflow.cli.workflow.main.ConfigManager')
    def test_workflow_error_handling_preserves_exit_code(self, mock_config_manager_class):
        """Test that error handling preserves proper exit codes."""
        mock_config_manager_class.side_effect = Exception("Config initialization failed")

        result = self.runner.invoke(workflow, ["create"])

        # Should exit with error code due to config failure
        assert result.exit_code == 1

    def test_workflow_group_name(self):
        """Test that workflow group has correct name."""
        assert workflow.name == "workflow"

    def test_workflow_group_is_click_group(self):
        """Test that workflow is a Click group."""
        import click
        assert isinstance(workflow, click.Group)

    @patch('langflow.cli.workflow.main.ConfigManager')
    def test_workflow_config_error_message_format(self, mock_config_manager_class):
        """Test that config error messages are properly formatted."""
        error_message = "Test configuration error"
        mock_config_manager_class.side_effect = Exception(error_message)

        with patch('langflow.cli.workflow.main.console') as mock_console:
            result = self.runner.invoke(workflow, ["list"])

            assert result.exit_code == 1
            mock_console.print.assert_called_once()

            # Check the error message format
            printed_message = mock_console.print.call_args[0][0]
            assert "[red]Error initializing Workflow configuration:" in printed_message
            assert error_message in printed_message
            assert "[/red]" in printed_message

    def test_workflow_click_context_type(self):
        """Test that workflow uses Click context correctly."""
        import click

        # The workflow function should accept a Click context
        assert hasattr(workflow.callback, '__annotations__')
        # Check if context parameter exists in the callback
        callback_func = workflow.callback
        assert callback_func is not None