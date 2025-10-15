"""Tests for mustache security utilities."""

import pytest
from langflow.utils.mustache_security import safe_mustache_render, validate_mustache_template


class TestMustacheSecurity:
    """Test mustache security functions."""

    def test_validate_accepts_simple_variables(self):
        """Test that simple variables are accepted."""
        # Should not raise
        validate_mustache_template("Hello {{name}}!")
        validate_mustache_template("{{user_name}} - {{user_email}}")
        validate_mustache_template("Price: {{price_100}}")
        validate_mustache_template("")
        validate_mustache_template("No variables here")

    def test_validate_rejects_complex_syntax(self):
        """Test that complex mustache syntax is rejected."""
        # Conditionals
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_mustache_template("{{#if}}content{{/if}}")

        # Inverted sections
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_mustache_template("{{^empty}}not empty{{/empty}}")

        # Unescaped
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_mustache_template("{{&html}}")

        # Partials
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_mustache_template("{{>header}}")

        # Comments
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_mustache_template("{{!comment}}")

        # Current context
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_mustache_template("{{.}}")

    def test_validate_rejects_invalid_variable_names(self):
        """Test that invalid variable names are rejected."""
        # Spaces in variable names
        with pytest.raises(ValueError, match="Invalid mustache variable"):
            validate_mustache_template("{{ name with spaces }}")

        # Starting with numbers
        with pytest.raises(ValueError, match="Invalid mustache variable"):
            validate_mustache_template("{{123invalid}}")

        # Special characters
        with pytest.raises(ValueError, match="Invalid mustache variable"):
            validate_mustache_template("{{price-$100}}")

        # Empty variables
        with pytest.raises(ValueError, match="Invalid mustache variable"):
            validate_mustache_template("{{}}")

        # Dot notation (not supported)
        with pytest.raises(ValueError, match="Invalid mustache variable"):
            validate_mustache_template("{{user.name}}")

    def test_safe_render_simple_variables(self):
        """Test safe rendering of simple variables."""
        template = "Hello {{name}}! You are {{age}} years old."
        variables = {"name": "Alice", "age": 25}
        result = safe_mustache_render(template, variables)
        assert result == "Hello Alice! You are 25 years old."

    def test_safe_render_missing_variables(self):
        """Test rendering with missing variables."""
        template = "Hello {{name}}! Your score is {{score}}."
        variables = {"name": "Charlie"}
        result = safe_mustache_render(template, variables)
        assert result == "Hello Charlie! Your score is ."

    def test_safe_render_none_values(self):
        """Test rendering with None values."""
        template = "Name: {{name}}, Age: {{age}}"
        variables = {"name": None, "age": None}
        result = safe_mustache_render(template, variables)
        assert result == "Name: , Age: "

    def test_safe_render_numeric_values(self):
        """Test rendering with numeric values."""
        template = "Price: ${{price}}, Quantity: {{qty}}"
        variables = {"price": 19.99, "qty": 3}
        result = safe_mustache_render(template, variables)
        assert result == "Price: $19.99, Quantity: 3"

    def test_safe_render_rejects_complex_syntax(self):
        """Test that safe_render rejects complex syntax."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            safe_mustache_render("{{#if}}test{{/if}}", {"if": True})

    def test_safe_render_multiple_variables(self):
        """Test rendering with multiple variables."""
        template = "{{greeting}} {{name}}, welcome to {{place}}!"
        variables = {"greeting": "Hello", "name": "Alice", "place": "Langflow"}
        result = safe_mustache_render(template, variables)
        assert result == "Hello Alice, welcome to Langflow!"

    def test_safe_render_underscore_variables(self):
        """Test rendering with underscore variable names."""
        template = "Private: {{_private_var}}, Public: {{public_var}}"
        variables = {"_private_var": "secret", "public_var": "visible"}
        result = safe_mustache_render(template, variables)
        assert result == "Private: secret, Public: visible"

    def test_safe_render_empty_string_values(self):
        """Test rendering with empty string values."""
        template = "Start{{middle}}End"
        variables = {"middle": ""}
        result = safe_mustache_render(template, variables)
        assert result == "StartEnd"
