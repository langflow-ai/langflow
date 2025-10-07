"""Tests for PromptComponent with both f-string and mustache modes."""

import pytest

from lfx.components.processing.prompt import PromptComponent
from lfx.inputs.input_mixin import FieldTypes


class TestPromptComponent:
    """Test the PromptComponent with both modes."""

    # Mode switching tests
    def test_update_build_config_changes_to_mustache(self):
        """Test that mode change to {{variable}} changes template field type to mustache."""
        component = PromptComponent()
        build_config = {"template": {"type": "prompt"}}

        result = component.update_build_config(build_config, "{{variable}}", "mode")

        assert result["template"]["type"] == FieldTypes.MUSTACHE_PROMPT.value

    def test_update_build_config_changes_to_fstring(self):
        """Test that mode change to {variable} changes template field type to prompt."""
        component = PromptComponent()
        build_config = {"template": {"type": "mustache"}}

        result = component.update_build_config(build_config, "{variable}", "mode")

        assert result["template"]["type"] == FieldTypes.PROMPT.value

    def test_update_build_config_ignores_other_fields(self):
        """Test that update_build_config ignores non-mode fields."""
        component = PromptComponent()
        build_config = {"template": {"type": "prompt"}}

        result = component.update_build_config(build_config, "some value", "other_field")

        assert result["template"]["type"] == "prompt"  # Unchanged

    # F-string mode tests
    def test_update_template_fstring_mode(self):
        """Test template update with f-string mode."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "Hello {name}!"},
                "mode": {"value": "{variable}"},
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        assert "name" in result["custom_fields"]["template"]
        assert "name" in result["template"]

    def test_update_template_fstring_multiple_variables(self):
        """Test f-string template with multiple variables."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "{greeting} {name}!"},
                "mode": {"value": "{variable}"},
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        assert "greeting" in result["custom_fields"]["template"]
        assert "name" in result["custom_fields"]["template"]

    # Mustache mode tests
    def test_update_template_mustache_mode(self):
        """Test template update with mustache mode."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "Hello {{name}}!"},
                "mode": {"value": "{{variable}}"},
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        assert "name" in result["custom_fields"]["template"]
        assert "name" in result["template"]

    def test_update_template_mustache_multiple_variables(self):
        """Test mustache template with multiple variables."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "{{greeting}} {{name}}!"},
                "mode": {"value": "{{variable}}"},
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        assert "greeting" in result["custom_fields"]["template"]
        assert "name" in result["custom_fields"]["template"]

    def test_update_template_mustache_dot_notation(self):
        """Test mustache template with dot notation."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "User: {{user.name}}"},
                "mode": {"value": "{{variable}}"},
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        # Should extract the dotted variable
        assert len(result["custom_fields"]["template"]) > 0

    def test_update_template_mustache_rejects_complex_syntax(self):
        """Test that mustache mode rejects complex syntax."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "{{#show}}Hello{{/show}}"},
                "mode": {"value": "{{variable}}"},
            },
            "custom_fields": {},
        }

        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            component._update_template(frontend_node)

    def test_update_template_defaults_to_fstring(self):
        """Test that template defaults to f-string mode when mode is missing."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "Hello {name}!"},
                # mode is missing
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        assert "name" in result["custom_fields"]["template"]

    # Build prompt tests
    async def test_build_prompt_fstring_mode(self):
        """Test building prompt with f-string mode."""
        component = PromptComponent()
        component.mode = "{variable}"
        component._attributes = {
            "template": "Hello {name}!",
            "name": "World",
        }

        result = await component.build_prompt()

        assert result.text == "Hello World!"
        assert result.template == "Hello {name}!"

    async def test_build_prompt_mustache_mode(self):
        """Test building prompt with mustache mode."""
        component = PromptComponent()
        component.mode = "{{variable}}"
        component._attributes = {
            "template": "Hello {{name}}!",
            "name": "World",
        }

        result = await component.build_prompt()

        assert result.text == "Hello World!"
        assert result.template == "Hello {{name}}!"

    async def test_build_prompt_mustache_missing_variable(self):
        """Test mustache mode with missing variable."""
        component = PromptComponent()
        component.mode = "{{variable}}"
        component._attributes = {
            "template": "Hello {{name}}!",
            # name is missing
        }

        result = await component.build_prompt()

        assert result.text == "Hello !"

    async def test_build_prompt_defaults_to_fstring(self):
        """Test that build_prompt defaults to f-string mode."""
        component = PromptComponent()
        # Don't set mode - should default
        component._attributes = {
            "template": "Hello {name}!",
            "name": "World",
        }

        result = await component.build_prompt()

        assert result.text == "Hello World!"

    # Update frontend node tests
    async def test_update_frontend_node_fstring_mode(self):
        """Test update_frontend_node with f-string mode."""
        component = PromptComponent()

        new_node = {
            "template": {
                "template": {"value": "Hello {name}!"},
                "mode": {"value": "{variable}"},
            },
            "custom_fields": {},
        }

        current_node = {
            "template": {"template": {"value": ""}},
        }

        result = await component.update_frontend_node(new_node, current_node)

        assert "name" in result["custom_fields"]["template"]

    async def test_update_frontend_node_mustache_mode(self):
        """Test update_frontend_node with mustache mode."""
        component = PromptComponent()

        new_node = {
            "template": {
                "template": {"value": "Hello {{name}}!"},
                "mode": {"value": "{{variable}}"},
            },
            "custom_fields": {},
        }

        current_node = {
            "template": {"template": {"value": ""}},
        }

        result = await component.update_frontend_node(new_node, current_node)

        assert "name" in result["custom_fields"]["template"]

    async def test_update_frontend_node_mustache_rejects_complex(self):
        """Test that update_frontend_node rejects complex mustache syntax."""
        component = PromptComponent()

        new_node = {
            "template": {
                "template": {"value": "{{#show}}Hello{{/show}}"},
                "mode": {"value": "{{variable}}"},
            },
            "custom_fields": {},
        }

        current_node = {
            "template": {"template": {"value": ""}},
        }

        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            await component.update_frontend_node(new_node, current_node)
