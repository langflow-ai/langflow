"""Tests for PromptComponent with f-string and double brackets syntax."""

from lfx.components.models_and_agents.prompt import PromptComponent


class TestPromptComponent:
    """Test the PromptComponent."""

    def test_update_template_single_variable(self):
        """Test template update with a single variable."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "Hello {name}!"},
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        assert "name" in result["custom_fields"]["template"]
        assert "name" in result["template"]

    def test_update_template_multiple_variables(self):
        """Test template with multiple variables."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "{greeting} {name}!"},
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        assert "greeting" in result["custom_fields"]["template"]
        assert "name" in result["custom_fields"]["template"]

    def test_update_template_duplicate_variables(self):
        """Test template with duplicate variables only creates one field."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "Hello {name}! How are you {name}?"},
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        assert result["custom_fields"]["template"].count("name") == 1
        assert "name" in result["template"]

    def test_update_template_no_variables(self):
        """Test template with no variables."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "Hello World!"},
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        assert len(result["custom_fields"].get("template", [])) == 0

    def test_update_template_escaped_braces(self):
        """Test template with escaped braces doesn't create variables."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "Result: {{not_a_var}} but {real_var} works"},
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        # Only {real_var} should be extracted
        assert "real_var" in result["custom_fields"]["template"]
        # {{not_a_var}} should NOT be extracted in f-string mode
        assert "not_a_var" not in result["custom_fields"]["template"]

    async def test_build_prompt_basic(self):
        """Test building a basic prompt."""
        component = PromptComponent()
        component._attributes = {
            "template": "Hello {name}!",
            "name": "World",
        }

        result = await component.build_prompt()

        assert result.text == "Hello World!"
        assert result.template == "Hello {name}!"

    async def test_build_prompt_multiple_variables(self):
        """Test building prompt with multiple variables."""
        component = PromptComponent()
        component._attributes = {
            "template": "{greeting} {name}! You are {age} years old.",
            "greeting": "Hello",
            "name": "Alice",
            "age": "25",
        }

        result = await component.build_prompt()

        assert result.text == "Hello Alice! You are 25 years old."

    async def test_update_frontend_node(self):
        """Test update_frontend_node processes template correctly."""
        component = PromptComponent()

        new_node = {
            "template": {
                "template": {"value": "Hello {name}!"},
            },
            "custom_fields": {},
        }

        current_node = {
            "template": {"template": {"value": ""}},
        }

        result = await component.update_frontend_node(new_node, current_node)

        assert "name" in result["custom_fields"]["template"]
        assert "name" in result["template"]

    async def test_update_frontend_node_creates_variable_fields(self):
        """Test that update_frontend_node creates fields for template variables."""
        component = PromptComponent()

        new_node = {
            "template": {
                "template": {"value": "Hello {name} and {greeting}!"},
            },
            "custom_fields": {},
        }

        current_node = {
            "template": {"template": {"value": ""}},
        }

        result = await component.update_frontend_node(new_node, current_node)

        # Both variables should be in custom_fields
        assert "name" in result["custom_fields"]["template"]
        assert "greeting" in result["custom_fields"]["template"]


class TestPromptComponentDoubleBrackets:
    """Test the PromptComponent with double brackets (mustache) syntax."""

    def test_update_template_double_brackets_single_variable(self):
        """Test template update with a single double-bracket variable."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "Hello {{name}}!"},
                "use_double_brackets": {"value": True},
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        assert "name" in result["custom_fields"]["template"]
        assert "name" in result["template"]

    def test_update_template_double_brackets_multiple_variables(self):
        """Test template with multiple double-bracket variables."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "{{greeting}} {{name}}!"},
                "use_double_brackets": {"value": True},
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        assert "greeting" in result["custom_fields"]["template"]
        assert "name" in result["custom_fields"]["template"]

    def test_update_template_double_brackets_no_variables(self):
        """Test double-bracket template with no variables."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "Hello World!"},
                "use_double_brackets": {"value": True},
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        assert len(result["custom_fields"].get("template", [])) == 0

    def test_update_template_double_brackets_ignores_single_braces(self):
        """Test that double-bracket mode ignores single-brace variables."""
        component = PromptComponent()

        frontend_node = {
            "template": {
                "template": {"value": "Hello {single} and {{double}}!"},
                "use_double_brackets": {"value": True},
            },
            "custom_fields": {},
        }

        result = component._update_template(frontend_node)

        # Only {{double}} should be extracted in double-bracket mode
        assert "double" in result["custom_fields"]["template"]
        # {single} should NOT be extracted
        assert "single" not in result["custom_fields"].get("template", [])

    async def test_build_prompt_double_brackets_basic(self):
        """Test building a basic prompt with double brackets."""
        component = PromptComponent()
        component.use_double_brackets = True
        component._attributes = {
            "template": "Hello {{name}}!",
            "name": "World",
            "use_double_brackets": True,
        }

        result = await component.build_prompt()

        assert result.text == "Hello World!"

    async def test_build_prompt_double_brackets_multiple_variables(self):
        """Test building prompt with multiple double-bracket variables."""
        component = PromptComponent()
        component.use_double_brackets = True
        component._attributes = {
            "template": "{{greeting}} {{name}}! You are {{age}} years old.",
            "greeting": "Hello",
            "name": "Alice",
            "age": "25",
            "use_double_brackets": True,
        }

        result = await component.build_prompt()

        assert result.text == "Hello Alice! You are 25 years old."

    async def test_build_prompt_default_is_single_brackets(self):
        """Test that default mode uses single brackets (f-string)."""
        component = PromptComponent()
        # Don't set use_double_brackets - should default to False
        component._attributes = {
            "template": "Hello {name}!",
            "name": "World",
        }

        result = await component.build_prompt()

        assert result.text == "Hello World!"

    async def test_update_frontend_node_double_brackets(self):
        """Test update_frontend_node processes double-bracket template correctly."""
        component = PromptComponent()

        new_node = {
            "template": {
                "template": {"value": "Hello {{name}}!"},
                "use_double_brackets": {"value": True},
            },
            "custom_fields": {},
        }

        current_node = {
            "template": {"template": {"value": ""}},
        }

        result = await component.update_frontend_node(new_node, current_node)

        assert "name" in result["custom_fields"]["template"]
        assert "name" in result["template"]

    def test_update_build_config_switches_to_mustache(self):
        """Test that update_build_config switches field type when enabling double brackets."""
        component = PromptComponent()

        build_config = {
            "template": {"type": "prompt", "value": "Hello {{name}}!"},
            "custom_fields": {"template": []},
        }

        result = component.update_build_config(build_config, field_value=True, field_name="use_double_brackets")

        assert result["template"]["type"] == "mustache"

    def test_update_build_config_switches_to_fstring(self):
        """Test that update_build_config switches field type when disabling double brackets."""
        component = PromptComponent()

        build_config = {
            "template": {"type": "MustachePrompt", "value": "Hello {name}!"},
            "custom_fields": {"template": []},
        }

        result = component.update_build_config(build_config, field_value=False, field_name="use_double_brackets")

        assert result["template"]["type"] == "prompt"
