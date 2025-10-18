"""Unit tests for the validate command module."""

import json
import pytest
import yaml
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from click.testing import CliRunner

from langflow.cli.workflow.commands.validate import validate


class TestValidateCommand:
    """Test the validate CLI command."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = Mock()
        self.mock_config.ai_studio_url = "http://localhost:7860"
        self.mock_api_client = Mock()

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_success(self, mock_api_client_class):
        """Test successful validation."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "summary": {
                "error_count": 0,
                "warning_count": 0,
                "suggestion_count": 0
            },
            "validation_phases": {
                "schema_validation": True,
                "component_validation": True,
                "semantic_validation": True
            }
        }
        mock_api_client.validate_spec_sync.return_value = validation_result

        # Create a temporary file with the spec content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(spec_content)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
            assert "Status: ✅ VALID" in result.output or "✅ Validation passed" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_with_errors(self, mock_api_client_class):
        """Test validation with errors."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: InvalidType
"""

        validation_result = {
            "valid": False,
            "errors": [
                {"message": "Invalid component type: InvalidType", "line": 5, "severity": "error"}
            ],
            "warnings": [],
            "suggestions": [],
            "summary": {
                "error_count": 1,
                "warning_count": 0,
                "suggestion_count": 0
            }
        }
        mock_api_client.validate_spec_sync.return_value = validation_result

        # Create a temporary file with the spec content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(spec_content)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
            assert "Status: ❌ INVALID" in result.output or "Validation failed" in result.output
            assert "Errors: 1" in result.output
            assert "Invalid component type: InvalidType" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_detailed_mode(self, mock_api_client_class):
        """Test validation with detailed mode."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "summary": {
                "error_count": 0,
                "warning_count": 0,
                "suggestion_count": 0
            },
            "validation_phases": {
                "schema_validation": True,
                "component_validation": True,
                "semantic_validation": True
            }
        }
        mock_api_client.validate_spec_sync.return_value = validation_result

        # Create a temporary file with the spec content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(spec_content)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path, "--detailed"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
            # Verify detailed validation was called
            mock_api_client.validate_spec_sync.assert_called_once_with(spec_content, detailed=True)
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_quick_mode(self, mock_api_client_class):
        """Test validation with quick mode."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "summary": {
                "error_count": 0,
                "warning_count": 0,
                "suggestion_count": 0
            }
        }
        mock_api_client.validate_spec_sync.return_value = validation_result

        # Create a temporary file with the spec content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(spec_content)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path, "--quick"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
            # Verify quick validation was called
            mock_api_client.validate_spec_sync.assert_called_once_with(spec_content, detailed=False)
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_json_format(self, mock_api_client_class):
        """Test validation with JSON output format."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "summary": {
                "error_count": 0,
                "warning_count": 0,
                "suggestion_count": 0
            }
        }
        mock_api_client.validate_spec_sync.return_value = validation_result

        # Create a temporary file with the spec content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(spec_content)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path, "--format", "json"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
            # JSON format should include format indicator or be parseable
            assert '"valid": true' in result.output or "Status: ✅ VALID" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_table_format(self, mock_api_client_class):
        """Test validation with table output format."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "summary": {
                "error_count": 0,
                "warning_count": 0,
                "suggestion_count": 0
            }
        }
        mock_api_client.validate_spec_sync.return_value = validation_result

        # Create a temporary file with the spec content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(spec_content)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path, "--format", "table"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_with_warnings(self, mock_api_client_class):
        """Test validation with warnings."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [
                {"message": "Component could be optimized", "line": 4, "severity": "warning"}
            ],
            "suggestions": [],
            "summary": {
                "error_count": 0,
                "warning_count": 1,
                "suggestion_count": 0
            }
        }
        mock_api_client.validate_spec_sync.return_value = validation_result

        # Create a temporary file with the spec content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(spec_content)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
            assert "Warnings: 1" in result.output
            assert "Component could be optimized" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_with_suggestions(self, mock_api_client_class):
        """Test validation with suggestions."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": [
                {"message": "Consider adding more descriptive component names", "line": 4, "severity": "info"}
            ],
            "summary": {
                "error_count": 0,
                "warning_count": 0,
                "suggestion_count": 1
            }
        }
        mock_api_client.validate_spec_sync.return_value = validation_result

        # Create a temporary file with the spec content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(spec_content)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
            assert "Suggestions: 1" in result.output
            assert "Consider adding more descriptive component names" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_with_debug(self, mock_api_client_class):
        """Test validation with debug flag."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "summary": {
                "error_count": 0,
                "warning_count": 0,
                "suggestion_count": 0
            }
        }
        mock_api_client.validate_spec_sync.return_value = validation_result

        # Create a temporary file with the spec content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(spec_content)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path, "--debug"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 0
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_file_read_error(self, mock_api_client_class):
        """Test validation with file read error."""
        # Create a temporary file and then delete it to simulate read error
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write("test content")
            temp_file_path = temp_file.name

        # Delete the file to cause a read error
        os.unlink(temp_file_path)

        result = self.runner.invoke(
            validate,
            [temp_file_path],
            obj={'config': self.mock_config}
        )

        assert result.exit_code == 2
        # Click should handle the file existence check

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_invalid_yaml(self, mock_api_client_class):
        """Test validation with invalid YAML."""
        invalid_yaml = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
    invalid: [unclosed bracket
"""

        # Create a temporary file with invalid YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(invalid_yaml)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
            assert "Invalid YAML format" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_connectivity_failure(self, mock_api_client_class):
        """Test validation with AI Studio connectivity failure."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = False

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        # Create a temporary file with the spec content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(spec_content)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
            assert "Cannot connect to AI Studio" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_api_error(self, mock_api_client_class):
        """Test validation with API error."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.validate_spec_sync.side_effect = Exception("API Error")

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        # Create a temporary file with the spec content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(spec_content)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
            assert "Validation request failed: API Error" in result.output
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    @patch('traceback.print_exc')
    def test_validate_api_error_with_debug(self, mock_traceback, mock_api_client_class):
        """Test validation with API error and debug flag."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.validate_spec_sync.side_effect = Exception("API Error")

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        # Create a temporary file with the spec content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(spec_content)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path, "--debug"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
            assert "Validation request failed: API Error" in result.output
            assert mock_traceback.call_count >= 1
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    @patch('traceback.print_exc')
    def test_validate_unexpected_error_with_debug(self, mock_traceback, mock_api_client_class):
        """Test validation with unexpected error and debug flag."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True
        mock_api_client.validate_spec_sync.side_effect = RuntimeError("Unexpected error")

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: Agent
"""

        # Create a temporary file with the spec content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(spec_content)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path, "--debug"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
            assert "Validation request failed: Unexpected error" in result.output
            assert mock_traceback.call_count >= 1
        finally:
            os.unlink(temp_file_path)

    @patch('langflow.cli.workflow.commands.validate.APIClient')
    def test_validate_table_format_with_errors(self, mock_api_client_class):
        """Test validation with table format and errors."""
        mock_api_client = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_api_client.health_check_sync.return_value = True

        spec_content = """
name: Test Agent
description: A test agent
components:
  - id: agent
    type: InvalidType
"""

        validation_result = {
            "valid": False,
            "errors": [
                {"message": "Invalid component type: InvalidType", "line": 5, "severity": "error"}
            ],
            "warnings": [
                {"message": "Component name could be more descriptive", "line": 4, "severity": "warning"}
            ],
            "suggestions": [],
            "summary": {
                "error_count": 1,
                "warning_count": 1,
                "suggestion_count": 0
            }
        }
        mock_api_client.validate_spec_sync.return_value = validation_result

        # Create a temporary file with the spec content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(spec_content)
            temp_file_path = temp_file.name

        try:
            result = self.runner.invoke(
                validate,
                [temp_file_path, "--format", "table"],
                obj={'config': self.mock_config}
            )

            assert result.exit_code == 1
            assert "Invalid component type: InvalidType" in result.output
            assert "Component name could be more descriptive" in result.output
        finally:
            os.unlink(temp_file_path)