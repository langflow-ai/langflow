"""Tests for mustache template processing in the Message class.

Note: Our mustache implementation only supports simple variable substitution
for security reasons. Complex features like conditionals, loops, and sections
are not supported.

The implementation also supports global variable references using the {{@variable}}
syntax, which are resolved at runtime from the user's global variables.
"""

import pytest
from lfx.schema.message import Message
from lfx.utils.mustache_security import (
    extract_global_variable_names,
    safe_mustache_render,
    validate_mustache_template,
)


class TestMustacheTemplateProcessing:
    """Test mustache template processing in the Message class."""

    def test_format_text_mustache_basic(self):
        """Test basic mustache template formatting."""
        message = Message(template="Hello {{name}}!", variables={"name": "World"})
        result = message.format_text(template_format="mustache")

        assert result == "Hello World!"
        assert message.text == "Hello World!"

    def test_format_text_mustache_multiple_variables(self):
        """Test mustache template with multiple variables."""
        message = Message(
            template="Hello {{name}}! You are {{age}} years old.", variables={"name": "Alice", "age": "25"}
        )
        result = message.format_text(template_format="mustache")

        assert result == "Hello Alice! You are 25 years old."

    def test_format_text_mustache_missing_variable(self):
        """Test mustache template with missing variable."""
        message = Message(template="Hello {{name}}! You are {{age}} years old.", variables={"name": "Bob"})
        result = message.format_text(template_format="mustache")

        # Missing variables should render as empty strings
        assert result == "Hello Bob! You are  years old."

    def test_format_text_mustache_no_variables(self):
        """Test mustache template with no variables."""
        message = Message(template="Hello World!", variables={})
        result = message.format_text(template_format="mustache")

        assert result == "Hello World!"

    def test_format_text_mustache_empty_template(self):
        """Test mustache template with empty template."""
        message = Message(template="", variables={"name": "Test"})
        result = message.format_text(template_format="mustache")

        assert result == ""

    def test_format_text_mustache_with_numeric_values(self):
        """Test mustache template with numeric values."""
        message = Message(
            template="Price: ${{price}}, Quantity: {{quantity}}", variables={"price": 19.99, "quantity": 3}
        )
        result = message.format_text(template_format="mustache")

        assert result == "Price: $19.99, Quantity: 3"

    def test_format_text_mustache_with_newlines(self):
        """Test mustache template with newlines."""
        message = Message(
            template="Line 1: {{line1}}\nLine 2: {{line2}}", variables={"line1": "First", "line2": "Second"}
        )
        result = message.format_text(template_format="mustache")

        assert result == "Line 1: First\nLine 2: Second"

    def test_format_text_mustache_with_empty_string_variable(self):
        """Test mustache template with empty string variable."""
        message = Message(template="Hello {{name}}!", variables={"name": ""})
        result = message.format_text(template_format="mustache")

        assert result == "Hello !"

    def test_format_text_mustache_with_none_variable(self):
        """Test mustache template with None variable."""
        message = Message(template="Hello {{name}}!", variables={"name": None})
        result = message.format_text(template_format="mustache")

        # None should render as empty string
        assert result == "Hello !"

    async def test_from_template_and_variables_mustache(self):
        """Test from_template_and_variables with mustache format."""
        message = await Message.from_template_and_variables(
            template="Hello {{name}}!", template_format="mustache", name="World"
        )

        assert isinstance(message, Message)
        assert message.text == "Hello World!"
        assert message.template == "Hello {{name}}!"
        assert message.variables == {"name": "World"}

    async def test_from_template_and_variables_mustache_no_variables(self):
        """Test from_template_and_variables with no variables."""
        message = await Message.from_template_and_variables(template="Static message", template_format="mustache")

        assert isinstance(message, Message)
        assert message.text == "Static message"
        assert message.variables == {}

    def test_format_text_mustache_preserves_original_variables(self):
        """Test that format_text doesn't modify the original variables."""
        original_variables = {"name": "Test", "age": 25}
        message = Message(template="Hello {{name}}, age {{age}}!", variables=original_variables.copy())

        result = message.format_text(template_format="mustache")

        assert result == "Hello Test, age 25!"
        assert message.variables == original_variables

    def test_format_text_mustache_with_zero_values(self):
        """Test mustache template with zero values."""
        message = Message(template="Count: {{count}}, Price: {{price}}", variables={"count": 0, "price": 0.0})
        result = message.format_text(template_format="mustache")

        assert result == "Count: 0, Price: 0.0"

    def test_mustache_security_rejects_conditionals(self):
        """Test that conditional syntax is rejected for security."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_mustache_template("{{#show}}Hello{{/show}}")

    def test_mustache_security_rejects_inverted_sections(self):
        """Test that inverted section syntax is rejected for security."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_mustache_template("{{^items}}No items{{/items}}")

    def test_mustache_security_rejects_loops(self):
        """Test that loop syntax is rejected for security."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_mustache_template("{{#items}}{{.}}{{/items}}")

    def test_mustache_security_rejects_unescaped_variables(self):
        """Test that unescaped variable syntax is rejected for security."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_mustache_template("{{&variable}}")

    def test_mustache_security_rejects_partials(self):
        """Test that partial syntax is rejected for security."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_mustache_template("{{>partial}}")

    def test_mustache_security_rejects_comments(self):
        """Test that comment syntax is rejected for security."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_mustache_template("{{!comment}}")

    def test_mustache_security_allows_simple_variables(self):
        """Test that simple variables are allowed."""
        # Should not raise
        validate_mustache_template("Hello {{name}}!")
        validate_mustache_template("{{var1}} and {{var2}}")

    def test_mustache_security_rejects_dot_notation(self):
        """Test that dot notation is NOT allowed."""
        with pytest.raises(ValueError, match="Invalid mustache variable"):
            validate_mustache_template("{{user.name}}")
        with pytest.raises(ValueError, match="Invalid mustache variable"):
            validate_mustache_template("{{company.ceo.name}}")

    def test_format_text_defaults_to_f_string(self):
        """Test that format_text defaults to f-string format."""
        message = Message(template="Hello {name}!", variables={"name": "World"})
        result = message.format_text()  # No template_format specified

        assert result == "Hello World!"


class TestGlobalVariableReferences:
    """Test global variable reference support in mustache templates ({{@variable}} syntax)."""

    def test_extract_global_variable_names_basic(self):
        """Test extracting global variable names from a template."""
        template = "Hello {{@name}}!"
        result = extract_global_variable_names(template)

        assert result == ["name"]

    def test_extract_global_variable_names_multiple(self):
        """Test extracting multiple global variable names."""
        template = "Hello {{@greeting}}, {{@name}}! Welcome to {{@company}}."
        result = extract_global_variable_names(template)

        assert sorted(result) == ["company", "greeting", "name"]

    def test_extract_global_variable_names_mixed_with_regular(self):
        """Test that only global variables (with @) are extracted."""
        template = "Hello {{name}}, your API key is {{@api_key}}."
        result = extract_global_variable_names(template)

        # Should only extract the global variable reference
        assert result == ["api_key"]

    def test_extract_global_variable_names_empty_template(self):
        """Test extracting global variables from empty template."""
        result = extract_global_variable_names("")

        assert result == []

    def test_extract_global_variable_names_no_globals(self):
        """Test extracting global variables when there are none."""
        template = "Hello {{name}}, you are {{age}} years old."
        result = extract_global_variable_names(template)

        assert result == []

    def test_validate_mustache_allows_global_variables(self):
        """Test that global variable syntax is allowed."""
        # Should not raise
        validate_mustache_template("Hello {{@name}}!")
        validate_mustache_template("{{@var1}} and {{@var2}}")
        validate_mustache_template("Mix of {{regular}} and {{@global}}")

    def test_safe_mustache_render_with_global_variables(self):
        """Test rendering a template with global variables."""
        template = "Hello {{@name}}!"
        global_variables = {"name": "World"}

        result = safe_mustache_render(template, {}, global_variables)

        assert result == "Hello World!"

    def test_safe_mustache_render_mixed_variables(self):
        """Test rendering a template with both regular and global variables."""
        template = "Hello {{user}}, your API key is {{@api_key}}."
        variables = {"user": "Alice"}
        global_variables = {"api_key": "sk-12345"}

        result = safe_mustache_render(template, variables, global_variables)

        assert result == "Hello Alice, your API key is sk-12345."

    def test_safe_mustache_render_missing_global_variable(self):
        """Test rendering when global variable is missing."""
        template = "Hello {{@name}}!"
        global_variables = {}

        result = safe_mustache_render(template, {}, global_variables)

        # Missing global variables should render as empty strings
        assert result == "Hello !"

    def test_safe_mustache_render_global_variables_none(self):
        """Test rendering when global_variables is None."""
        template = "Hello {{@name}}!"

        result = safe_mustache_render(template, {}, None)

        # Should render empty string for the global variable
        assert result == "Hello !"

    def test_format_text_with_global_variables(self):
        """Test Message.format_text with global variables."""
        message = Message(template="Hello {{@name}}!", variables={})
        global_variables = {"name": "World"}

        result = message.format_text(template_format="mustache", global_variables=global_variables)

        assert result == "Hello World!"
        assert message.text == "Hello World!"

    def test_format_text_mixed_with_global_variables(self):
        """Test Message.format_text with both regular and global variables."""
        message = Message(template="Hello {{user}}, your key is {{@api_key}}.", variables={"user": "Bob"})
        global_variables = {"api_key": "secret123"}

        result = message.format_text(template_format="mustache", global_variables=global_variables)

        assert result == "Hello Bob, your key is secret123."

    async def test_from_template_and_variables_with_global_variables(self):
        """Test from_template_and_variables with global variables."""
        global_variables = {"api_key": "my-secret-key"}
        message = await Message.from_template_and_variables(
            template="API Key: {{@api_key}}", template_format="mustache", global_variables=global_variables
        )

        assert isinstance(message, Message)
        assert message.text == "API Key: my-secret-key"

    async def test_from_template_and_variables_mixed(self):
        """Test from_template_and_variables with both regular and global variables."""
        global_variables = {"api_key": "sk-12345"}
        message = await Message.from_template_and_variables(
            template="Hello {{user}}, your key is {{@api_key}}.",
            template_format="mustache",
            global_variables=global_variables,
            user="Alice",
        )

        assert isinstance(message, Message)
        assert message.text == "Hello Alice, your key is sk-12345."

    def test_global_variable_duplicate_names(self):
        """Test that duplicate global variable references are handled correctly."""
        template = "Key 1: {{@api_key}}, Key 2: {{@api_key}}"
        result = extract_global_variable_names(template)

        # Should only appear once
        assert result == ["api_key"]

    def test_global_variable_with_underscores(self):
        """Test global variables with underscores in names."""
        template = "{{@my_long_variable_name}}"
        result = extract_global_variable_names(template)

        assert result == ["my_long_variable_name"]

    def test_global_variable_with_numbers(self):
        """Test global variables with numbers in names."""
        template = "{{@var1}} and {{@var_2}}"
        result = extract_global_variable_names(template)

        assert sorted(result) == ["var1", "var_2"]

    def test_safe_mustache_render_global_overrides_regular(self):
        """Test that global and regular variables are kept separate."""
        template = "Regular: {{name}}, Global: {{@name}}"
        variables = {"name": "regular_value"}
        global_variables = {"name": "global_value"}

        result = safe_mustache_render(template, variables, global_variables)

        # Both should resolve to their respective values
        assert result == "Regular: regular_value, Global: global_value"
