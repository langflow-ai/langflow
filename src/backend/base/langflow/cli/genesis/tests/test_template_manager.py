"""Tests for TemplateManager."""

import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

from langflow.cli.genesis.utils.template_manager import TemplateManager


class TestTemplateManager:
    """Test cases for TemplateManager."""

    def test_init_with_default_path(self):
        """Test initialization with default templates path."""
        manager = TemplateManager()
        assert manager.templates_path.name == "genesis"

    def test_init_with_custom_path(self):
        """Test initialization with custom templates path."""
        custom_path = Path("/custom/templates")
        manager = TemplateManager(custom_path)
        assert manager.templates_path == custom_path

    def test_substitute_variables_simple(self):
        """Test simple variable substitution."""
        manager = TemplateManager()
        content = "name: {agent_name}\ntemperature: {temperature}"
        variables = {"agent_name": "Test Agent", "temperature": 0.7}

        result = manager._substitute_variables(content, variables)
        expected = "name: Test Agent\ntemperature: 0.7"
        assert result == expected

    def test_substitute_variables_complex(self):
        """Test complex variable substitution with different types."""
        manager = TemplateManager()
        content = "config: {config}\nenabled: {enabled}"
        variables = {
            "config": {"model": "gpt-4", "temperature": 0.5},
            "enabled": True
        }

        result = manager._substitute_variables(content, variables)
        assert '"model": "gpt-4"' in result
        assert "enabled: true" in result

    @patch.dict('os.environ', {'TEST_ENV': 'test_value'})
    def test_substitute_environment_variables(self):
        """Test environment variable substitution."""
        manager = TemplateManager()
        content = "api_key: ${TEST_ENV}\nother: ${MISSING_ENV}"

        result = manager._substitute_variables(content, {})
        assert "api_key: test_value" in result
        assert "other: " in result  # Missing env vars become empty string

    def test_apply_tweaks(self):
        """Test component configuration tweaks."""
        manager = TemplateManager()
        content = """
components:
  - id: agent-1
    type: genesis:agent
    config:
      temperature: 0.3
      model: gpt-3.5-turbo
  - id: agent-2
    type: genesis:agent
    config:
      temperature: 0.5
"""
        tweaks = {
            "agent-1.config.temperature": 0.8,
            "agent-1.config.model": "gpt-4",
            "agent-2.new_field": "new_value"
        }

        result = manager._apply_tweaks(content, tweaks)
        result_dict = yaml.safe_load(result)

        assert result_dict['components'][0]['config']['temperature'] == 0.8
        assert result_dict['components'][0]['config']['model'] == "gpt-4"
        assert result_dict['components'][1]['new_field'] == "new_value"

    def test_validate_template_valid(self):
        """Test template validation for valid template."""
        manager = TemplateManager()
        content = """
name: Test Agent
description: A test agent
components:
  - id: input
    type: genesis:chat_input
  - id: agent
    type: genesis:agent
"""

        result = manager.validate_template(content)
        assert result['valid'] is True
        assert len(result['errors']) == 0

    def test_validate_template_invalid(self):
        """Test template validation for invalid template."""
        manager = TemplateManager()
        content = """
name: Test Agent
# Missing description and components
"""

        result = manager.validate_template(content)
        assert result['valid'] is False
        assert "Missing required field: description" in result['errors']
        assert "Missing required field: components" in result['errors']

    def test_validate_template_malformed_yaml(self):
        """Test template validation for malformed YAML."""
        manager = TemplateManager()
        content = """
name: Test Agent
description: A test agent
components:
  - id: input
    type: genesis:chat_input
    invalid: [unclosed list
"""

        result = manager.validate_template(content)
        assert result['valid'] is False
        assert "Invalid YAML" in result['errors'][0]

    def test_get_template_variables(self):
        """Test extraction of template variables."""
        manager = TemplateManager()
        content = """
name: {agent_name}
config:
  api_key: ${API_KEY}
  temperature: {temperature}
  model: ${MODEL_NAME}
"""

        variables = manager.get_template_variables(content)
        expected = ["API_KEY", "MODEL_NAME", "agent_name", "temperature"]
        assert sorted(variables) == sorted(expected)

    def test_apply_variable_substitution_complete(self):
        """Test complete variable substitution workflow."""
        manager = TemplateManager()
        content = """
name: {agent_name}
config:
  temperature: {temperature}
  api_key: ${API_KEY}
components:
  - id: agent
    type: genesis:agent
    config:
      model: {model}
"""
        variables = {
            "agent_name": "Test Agent",
            "temperature": 0.7,
            "model": "gpt-4"
        }
        tweaks = {
            "agent.config.temperature": 0.9
        }

        with patch.dict('os.environ', {'API_KEY': 'test_key'}):
            result = manager.apply_variable_substitution(content, variables, tweaks)

        # Check variable substitution
        assert "name: Test Agent" in result
        assert "api_key: test_key" in result

        # Check tweaks were applied
        result_dict = yaml.safe_load(result)
        assert result_dict['components'][0]['config']['temperature'] == 0.9