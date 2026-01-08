"""Tests for mustache template processing in the Message class.

Note: Our mustache implementation only supports simple variable substitution
for security reasons. Complex features like conditionals, loops, and sections
are not supported.
"""

import pytest
from lfx.schema.message import Message
from lfx.utils.mustache_security import validate_mustache_template


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
