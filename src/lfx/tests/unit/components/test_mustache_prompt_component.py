"""Tests for MustachePromptComponent."""

import pytest

from lfx.components.processing.mustache_prompt import MustachePromptComponent


class TestMustachePromptComponent:
    """Test the MustachePromptComponent."""

    def test_update_template_extracts_mustache_variables(self):
        """Test that _update_template correctly extracts mustache variables."""
        component = MustachePromptComponent()

        frontend_node = {
            "template": {"template": {"value": "Hello {{name}}!"}},
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        # Check that 'name' was added to custom_fields
        assert "template" in result["custom_fields"]
        assert "name" in result["custom_fields"]["template"]

        # Check that 'name' field was added to template
        assert "name" in result["template"]
        assert result["template"]["name"]["name"] == "name"
        assert result["template"]["name"]["display_name"] == "name"

    def test_update_template_with_multiple_variables(self):
        """Test template with multiple mustache variables."""
        component = MustachePromptComponent()

        frontend_node = {
            "template": {"template": {"value": "{{greeting}} {{name}}, you are {{age}} years old!"}},
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        # Check all variables were extracted
        assert "greeting" in result["custom_fields"]["template"]
        assert "name" in result["custom_fields"]["template"]
        assert "age" in result["custom_fields"]["template"]

        # Check fields were created
        assert "greeting" in result["template"]
        assert "name" in result["template"]
        assert "age" in result["template"]

    def test_update_template_with_dot_notation(self):
        """Test template with dot notation variables."""
        component = MustachePromptComponent()

        frontend_node = {
            "template": {"template": {"value": "User: {{user.name}} ({{user.email}})"}},
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        # Check that dot notation variables were extracted
        # Note: These should be treated as separate variables
        assert len(result["custom_fields"]["template"]) > 0

    def test_update_template_no_variables(self):
        """Test template with no variables."""
        component = MustachePromptComponent()

        frontend_node = {
            "template": {"template": {"value": "Hello World!"}},
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        # Should have empty custom_fields
        assert result["custom_fields"]["template"] == []

    def test_update_template_rejects_complex_syntax(self):
        """Test that complex mustache syntax is rejected."""
        component = MustachePromptComponent()

        # Test conditional syntax
        frontend_node = {
            "template": {"template": {"value": "{{#show}}Hello{{/show}}"}},
            "custom_fields": {},
        }

        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            component._update_template(frontend_node)

    async def test_build_prompt_basic(self):
        """Test that build_prompt creates a message with mustache template."""
        component = MustachePromptComponent()
        component._attributes = {
            "template": "Hello {{name}}!",
            "name": "World",
        }

        result = await component.build_prompt()

        assert result.text == "Hello World!"
        assert result.template == "Hello {{name}}!"
        assert "name" in result.variables

    async def test_build_prompt_multiple_variables(self):
        """Test build_prompt with multiple variables."""
        component = MustachePromptComponent()
        component._attributes = {
            "template": "{{greeting}} {{name}}!",
            "greeting": "Hello",
            "name": "World",
        }

        result = await component.build_prompt()

        assert result.text == "Hello World!"

    async def test_build_prompt_missing_variable(self):
        """Test build_prompt with missing variable."""
        component = MustachePromptComponent()
        component._attributes = {
            "template": "Hello {{name}}!",
            # name is missing
        }

        result = await component.build_prompt()

        # Missing variables should render as empty string
        assert result.text == "Hello !"

    async def test_update_frontend_node(self):
        """Test update_frontend_node processes template correctly."""
        component = MustachePromptComponent()

        new_node = {
            "template": {"template": {"value": "Hello {{name}}!"}},
            "custom_fields": {},
        }

        current_node = {
            "template": {"template": {"value": ""}},
        }

        result = await component.update_frontend_node(new_node, current_node)

        # Check that variables were extracted
        assert "name" in result["custom_fields"]["template"]
        assert "name" in result["template"]
