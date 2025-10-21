"""Unit tests for the TemplateManager class."""

import json
import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import pytest

from langflow.cli.workflow.utils.template_manager import TemplateManager


class TestTemplateManager:
    """Test the TemplateManager class."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.templates_path = Path(self.temp_dir) / "templates"
        self.templates_path.mkdir(exist_ok=True)

        # Create sample template files
        self.sample_template1 = {
            "name": "Healthcare Agent",
            "description": "Processes healthcare data",
            "kind": "agent",
            "domain": "healthcare",
            "version": "1.0.0",
            "agentGoal": "Process patient data",
            "components": [
                {"id": "agent1", "type": "Agent"},
                {"id": "llm1", "type": "LLM"}
            ]
        }

        self.sample_template2 = {
            "name": "Fraud Detection",
            "description": "Detects fraudulent transactions",
            "kind": "agent",
            "domain": "finance",
            "version": "2.0.0",
            "components": [
                {"id": "detector", "type": "Classifier"}
            ]
        }

        # Write sample templates
        healthcare_dir = self.templates_path / "healthcare"
        healthcare_dir.mkdir(exist_ok=True)
        with open(healthcare_dir / "agent.yaml", "w") as f:
            yaml.dump(self.sample_template1, f)

        fraud_dir = self.templates_path / "fraud-detection"
        fraud_dir.mkdir(exist_ok=True)
        with open(fraud_dir / "detector.yaml", "w") as f:
            yaml.dump(self.sample_template2, f)

        # Create metadata file
        metadata = {
            "healthcare": {
                "description": "Healthcare domain templates",
                "author": "Test Author"
            }
        }
        with open(self.templates_path / "metadata.yaml", "w") as f:
            yaml.dump(metadata, f)

        self.template_manager = TemplateManager(self.templates_path)

    def test_init_with_custom_path(self):
        """Test TemplateManager initialization with custom path."""
        manager = TemplateManager(self.templates_path)
        assert manager.templates_path == self.templates_path

    def test_init_with_default_path(self):
        """Test TemplateManager initialization with default path."""
        with patch('langflow.cli.workflow.utils.template_manager.Path') as mock_path_class:
            # Mock the __file__ path calculation
            mock_file_path = Mock()
            mock_file_path.parent.parent.parent.parent = Path("/default/path")

            # Mock Path(__file__)
            mock_path_class.return_value = mock_file_path

            # Mock the division operations to return a proper path
            mock_file_path.__truediv__ = Mock(return_value=mock_file_path)

            manager = TemplateManager()

            # Verify that the path construction was called
            mock_path_class.assert_called_once()
            assert manager.templates_path is not None

    def test_list_templates(self):
        """Test listing all templates."""
        templates = self.template_manager.list_templates()

        assert len(templates) == 2

        # Check healthcare template
        healthcare_template = next(t for t in templates if t['name'] == 'Healthcare Agent')
        assert healthcare_template['description'] == 'Processes healthcare data'
        assert healthcare_template['kind'] == 'agent'
        assert healthcare_template['domain'] == 'healthcare'
        assert healthcare_template['components_count'] == 2
        assert 'healthcare' in healthcare_template['category']

        # Check fraud detection template
        fraud_template = next(t for t in templates if t['name'] == 'Fraud Detection')
        assert fraud_template['description'] == 'Detects fraudulent transactions'
        assert fraud_template['kind'] == 'agent'
        assert fraud_template['domain'] == 'finance'
        assert fraud_template['components_count'] == 1

    def test_list_templates_with_category_filter(self):
        """Test listing templates with category filter."""
        templates = self.template_manager.list_templates(category="healthcare")

        assert len(templates) == 1
        assert templates[0]['name'] == 'Healthcare Agent'

    def test_list_templates_no_templates_path(self):
        """Test listing templates when templates path doesn't exist."""
        nonexistent_path = Path(self.temp_dir) / "nonexistent"
        manager = TemplateManager(nonexistent_path)

        templates = manager.list_templates()
        assert templates == []

    def test_list_templates_invalid_yaml(self):
        """Test listing templates with invalid YAML file."""
        invalid_dir = self.templates_path / "invalid"
        invalid_dir.mkdir(exist_ok=True)

        with open(invalid_dir / "invalid.yaml", "w") as f:
            f.write("invalid: yaml: [unclosed")

        templates = self.template_manager.list_templates()
        # Should only return valid templates
        assert len(templates) == 2

    def test_load_template_relative_path(self):
        """Test loading template from relative path."""
        content = self.template_manager.load_template("healthcare/agent.yaml")

        loaded_template = yaml.safe_load(content)
        assert loaded_template['name'] == 'Healthcare Agent'

    def test_load_template_absolute_path(self):
        """Test loading template from absolute path."""
        absolute_path = self.templates_path / "healthcare" / "agent.yaml"
        content = self.template_manager.load_template(str(absolute_path))

        loaded_template = yaml.safe_load(content)
        assert loaded_template['name'] == 'Healthcare Agent'

    def test_load_template_not_found(self):
        """Test loading non-existent template."""
        with pytest.raises(FileNotFoundError):
            self.template_manager.load_template("nonexistent/template.yaml")

    def test_apply_variable_substitution_no_variables(self):
        """Test variable substitution with no variables."""
        content = "name: Test Template"
        result = self.template_manager.apply_variable_substitution(content)
        assert result == content

    def test_apply_variable_substitution_with_variables(self):
        """Test variable substitution with variables."""
        content = "name: {agent_name}\ntemperature: {temperature}\nverbose: {verbose}"
        variables = {
            "agent_name": "Custom Agent",
            "temperature": 0.7,
            "verbose": True
        }

        result = self.template_manager.apply_variable_substitution(content, variables)

        assert "Custom Agent" in result
        assert "0.7" in result
        assert "true" in result  # Boolean converted to lowercase

    def test_apply_variable_substitution_with_env_vars(self):
        """Test variable substitution with environment variables."""
        content = "api_key: ${API_KEY}\nurl: ${BASE_URL}\nname: {dummy_var}"

        with patch.dict('os.environ', {'API_KEY': 'test-key', 'BASE_URL': 'http://test'}):
            # Need to pass at least one variable to trigger substitution
            result = self.template_manager.apply_variable_substitution(content, {"dummy_var": "test"})

        assert "test-key" in result
        assert "http://test" in result
        assert "test" in result

    def test_apply_variable_substitution_with_tweaks(self):
        """Test variable substitution with component tweaks."""
        content = """
name: Test Agent
components:
  - id: agent
    type: Agent
    config:
      temperature: 0.5
  - id: llm
    type: LLM
    model: gpt-3.5
"""
        tweaks = {
            "agent.config.temperature": 0.8,
            "llm.model": "gpt-4"
        }

        result = self.template_manager.apply_variable_substitution(content, tweaks=tweaks)

        modified_template = yaml.safe_load(result)
        assert modified_template['components'][0]['config']['temperature'] == 0.8
        assert modified_template['components'][1]['model'] == "gpt-4"

    def test_apply_variable_substitution_complex_values(self):
        """Test variable substitution with complex JSON values."""
        content = "config: {config_json}\nlist: {list_value}"
        variables = {
            "config_json": {"nested": {"value": 42}},
            "list_value": ["item1", "item2"]
        }

        result = self.template_manager.apply_variable_substitution(content, variables)

        assert '{"nested": {"value": 42}}' in result
        assert '["item1", "item2"]' in result

    def test_substitute_variables(self):
        """Test _substitute_variables method directly."""
        content = "name: {name}\nvalue: {value}"
        variables = {"name": "Test", "value": 123}

        result = self.template_manager._substitute_variables(content, variables)

        assert result == "name: Test\nvalue: 123"

    def test_apply_tweaks_invalid_yaml(self):
        """Test _apply_tweaks with invalid YAML."""
        content = "invalid yaml: [unclosed"
        tweaks = {"component.field": "value"}

        result = self.template_manager._apply_tweaks(content, tweaks)

        # Should return original content on error
        assert result == content

    def test_apply_tweaks_no_components(self):
        """Test _apply_tweaks with spec that has no components."""
        content = "name: Test\ndescription: Test spec"
        tweaks = {"component.field": "value"}

        result = self.template_manager._apply_tweaks(content, tweaks)

        # Should return original content if no components
        assert result == content

    def test_apply_tweaks_nested_fields(self):
        """Test _apply_tweaks with nested field paths."""
        content = """
name: Test Agent
components:
  - id: agent
    type: Agent
"""
        tweaks = {
            "agent.config.nested.field": "deep_value"
        }

        result = self.template_manager._apply_tweaks(content, tweaks)

        modified_template = yaml.safe_load(result)
        assert modified_template['components'][0]['config']['nested']['field'] == "deep_value"

    def test_validate_template_valid(self):
        """Test template validation with valid template."""
        content = yaml.dump(self.sample_template1)
        result = self.template_manager.validate_template(content)

        assert result['valid'] is True
        assert len(result['errors']) == 0

    def test_validate_template_missing_fields(self):
        """Test template validation with missing required fields."""
        content = yaml.dump({"description": "Missing name"})
        result = self.template_manager.validate_template(content)

        assert result['valid'] is False
        assert any("Missing required field: name" in error for error in result['errors'])

    def test_validate_template_empty(self):
        """Test template validation with empty content."""
        result = self.template_manager.validate_template("")

        assert result['valid'] is False
        assert "Empty template" in result['errors']

    def test_validate_template_invalid_yaml(self):
        """Test template validation with invalid YAML."""
        content = "invalid: yaml: [unclosed"
        result = self.template_manager.validate_template(content)

        assert result['valid'] is False
        assert any("Invalid YAML" in error for error in result['errors'])

    def test_validate_template_invalid_components(self):
        """Test template validation with invalid components structure."""
        template = {
            "name": "Test",
            "description": "Test",
            "components": "not a list"
        }
        content = yaml.dump(template)
        result = self.template_manager.validate_template(content)

        assert result['valid'] is False
        assert any("Components must be a list" in error for error in result['errors'])

    def test_validate_template_component_missing_id(self):
        """Test template validation with component missing ID."""
        template = {
            "name": "Test",
            "description": "Test",
            "components": [
                {"type": "Agent"}  # Missing id
            ]
        }
        content = yaml.dump(template)
        result = self.template_manager.validate_template(content)

        assert result['valid'] is False
        assert any("missing required 'id' field" in error for error in result['errors'])

    def test_create_template_from_spec(self):
        """Test creating template from specification content."""
        spec_content = yaml.dump(self.sample_template1)
        template_path = "test/new-template.yaml"
        metadata = {
            "created_at": "2023-12-01",
            "category": "test",
            "author": "Test Author"
        }

        with patch("builtins.open", mock_open()) as mock_file:
            result = self.template_manager.create_template_from_spec(
                spec_content, template_path, metadata
            )

        assert result is True
        mock_file.assert_called_once()

    def test_create_template_from_spec_error(self):
        """Test creating template with file write error."""
        spec_content = yaml.dump(self.sample_template1)
        template_path = "test/new-template.yaml"

        with patch("builtins.open", side_effect=Exception("Write error")):
            result = self.template_manager.create_template_from_spec(
                spec_content, template_path
            )

        assert result is False

    def test_get_template_variables(self):
        """Test extracting template variables."""
        content = """
name: {agent_name}
api_key: ${API_KEY}
config:
  temperature: {temperature}
  url: ${BASE_URL}
"""

        variables = self.template_manager.get_template_variables(content)

        expected_vars = ["agent_name", "temperature", "API_KEY", "BASE_URL"]
        assert set(variables) == set(expected_vars)
        assert variables == sorted(expected_vars)  # Should be sorted

    def test_get_template_variables_no_variables(self):
        """Test extracting variables from template with no variables."""
        content = "name: Static Template\ndescription: No variables here"

        variables = self.template_manager.get_template_variables(content)
        assert variables == []

    def test_find_template_by_name_exact_match(self):
        """Test finding template by exact name match."""
        template_path = self.template_manager.find_template_by_name("Healthcare Agent")

        assert template_path is not None
        assert "healthcare/agent.yaml" in template_path

    def test_find_template_by_name_fuzzy_match(self):
        """Test finding template by fuzzy name match."""
        template_path = self.template_manager.find_template_by_name("fraud")

        assert template_path is not None
        assert "fraud-detection/detector.yaml" in template_path

    def test_find_template_by_name_not_found(self):
        """Test finding template when name doesn't match."""
        template_path = self.template_manager.find_template_by_name("Nonexistent Template")

        assert template_path is None

    def test_find_template_by_name_case_insensitive(self):
        """Test finding template with case insensitive matching."""
        template_path = self.template_manager.find_template_by_name("HEALTHCARE AGENT")

        assert template_path is not None
        assert "healthcare/agent.yaml" in template_path

    def test_apply_tweaks_invalid_tweak_key(self):
        """Test applying tweaks with invalid tweak key format."""
        content = yaml.dump({
            "name": "Test",
            "components": [{"id": "agent", "type": "Agent"}]
        })
        tweaks = {
            "invalid_key": "value"  # No dot in key
        }

        result = self.template_manager._apply_tweaks(content, tweaks)

        # Should ignore invalid keys and return modified YAML
        assert "name: Test" in result

    def test_apply_tweaks_component_not_found(self):
        """Test applying tweaks to non-existent component."""
        content = yaml.dump({
            "name": "Test",
            "components": [{"id": "agent", "type": "Agent"}]
        })
        tweaks = {
            "nonexistent.field": "value"
        }

        result = self.template_manager._apply_tweaks(content, tweaks)

        # Should ignore tweaks for non-existent components
        modified_template = yaml.safe_load(result)
        assert len(modified_template['components']) == 1
        assert modified_template['components'][0]['id'] == 'agent'