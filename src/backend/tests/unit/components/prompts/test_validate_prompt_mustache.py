"""Tests for validate_prompt function with mustache templates.

These tests ensure that complex mustache syntax is rejected during the "Check & Save"
validation phase, not just at runtime. This prevents users from saving templates that
are guaranteed to fail at runtime.

Regression test for: Complex mustache patterns like {{#section}}{{/section}} were being
accepted during save but causing "Complex mustache syntax is not allowed" errors at runtime.
"""

import pytest
from lfx.base.prompts.api_utils import validate_prompt


class TestValidatePromptMustache:
    """Test validate_prompt function with mustache templates."""

    def test_simple_variable_accepted(self):
        """Test that simple mustache variables are accepted."""
        result = validate_prompt("Hello {{name}}!", is_mustache=True)
        assert result == ["name"]

    def test_multiple_simple_variables_accepted(self):
        """Test that multiple simple variables are accepted."""
        result = validate_prompt("Hello {{first_name}} {{last_name}}!", is_mustache=True)
        assert sorted(result) == ["first_name", "last_name"]

    def test_underscore_variables_accepted(self):
        """Test that variables with underscores are accepted."""
        result = validate_prompt("{{user_name}} - {{_private}}", is_mustache=True)
        assert sorted(result) == ["_private", "user_name"]

    def test_numeric_suffix_variables_accepted(self):
        """Test that variables with numeric suffixes are accepted."""
        result = validate_prompt("{{var1}} {{var2}} {{price_100}}", is_mustache=True)
        assert sorted(result) == ["price_100", "var1", "var2"]

    def test_empty_template_accepted(self):
        """Test that empty template is accepted."""
        result = validate_prompt("", is_mustache=True)
        assert result == []

    def test_no_variables_accepted(self):
        """Test that template without variables is accepted."""
        result = validate_prompt("Hello World!", is_mustache=True)
        assert result == []

    # Regression tests for the bug: complex syntax should be rejected during validation
    # These patterns were previously accepted during "Check & Save" but failed at runtime

    def test_section_syntax_rejected(self):
        """Test that section syntax ({{#section}}{{/section}}) is rejected.

        This is the main regression test for the bug where closed sections were
        accepted during save but caused runtime errors.
        """
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_prompt("{{#section}}content{{/section}}", is_mustache=True)

    def test_conditional_syntax_rejected(self):
        """Test that conditional syntax is rejected."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_prompt("{{#if}}show this{{/if}}", is_mustache=True)

    def test_inverted_section_rejected(self):
        """Test that inverted section syntax ({{^section}}) is rejected."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_prompt("{{^empty}}not empty{{/empty}}", is_mustache=True)

    def test_unescaped_variable_rejected(self):
        """Test that unescaped variable syntax ({{&var}}) is rejected."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_prompt("{{&html_content}}", is_mustache=True)

    def test_triple_braces_rejected(self):
        """Test that triple braces ({{{var}}}) for unescaped HTML are rejected."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_prompt("{{{unescaped}}}", is_mustache=True)

    def test_partial_syntax_rejected(self):
        """Test that partial syntax ({{>partial}}) is rejected."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_prompt("{{>header}}", is_mustache=True)

    def test_comment_syntax_rejected(self):
        """Test that comment syntax ({{!comment}}) is rejected."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_prompt("{{!this is a comment}}", is_mustache=True)

    def test_current_context_rejected(self):
        """Test that current context syntax ({{.}}) is rejected."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_prompt("{{.}}", is_mustache=True)

    def test_nested_sections_rejected(self):
        """Test that nested sections are rejected."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_prompt("{{#outer}}{{#inner}}content{{/inner}}{{/outer}}", is_mustache=True)

    def test_loop_syntax_rejected(self):
        """Test that loop syntax is rejected (sections are used for loops in Mustache)."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_prompt("{{#items}}{{name}}{{/items}}", is_mustache=True)

    # Tests for invalid variable names

    def test_dot_notation_rejected(self):
        """Test that dot notation ({{user.name}}) is rejected."""
        with pytest.raises(ValueError, match="Invalid mustache variable"):
            validate_prompt("{{user.name}}", is_mustache=True)

    def test_spaces_in_variable_rejected(self):
        """Test that spaces in variable names are rejected."""
        with pytest.raises(ValueError, match="Invalid mustache variable"):
            validate_prompt("{{ variable with spaces }}", is_mustache=True)

    def test_variable_starting_with_number_rejected(self):
        """Test that variables starting with numbers are rejected."""
        with pytest.raises(ValueError, match="Invalid mustache variable"):
            validate_prompt("{{123abc}}", is_mustache=True)

    def test_empty_variable_rejected(self):
        """Test that empty variables ({{}}) are rejected."""
        with pytest.raises(ValueError, match="Invalid mustache variable"):
            validate_prompt("{{}}", is_mustache=True)

    def test_special_characters_rejected(self):
        """Test that special characters in variable names are rejected."""
        with pytest.raises(ValueError, match="Invalid mustache variable"):
            validate_prompt("{{price-$100}}", is_mustache=True)

    # Tests for malformed syntax (unclosed tags)

    def test_unclosed_section_rejected(self):
        """Test that unclosed section tags are rejected."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_prompt("{{#section}}", is_mustache=True)

    def test_unclosed_inverted_section_rejected(self):
        """Test that unclosed inverted section tags are rejected."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_prompt("{{^section}}", is_mustache=True)

    def test_closing_tag_without_opening_rejected(self):
        """Test that closing tags without opening are rejected."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_prompt("{{/section}}", is_mustache=True)

    # Tests for mixed content

    def test_simple_variable_with_text(self):
        """Test simple variable mixed with text content."""
        result = validate_prompt("Dear {{name}}, your order {{order_id}} is ready.", is_mustache=True)
        assert sorted(result) == ["name", "order_id"]

    def test_complex_syntax_mixed_with_simple_rejected(self):
        """Test that complex syntax mixed with simple variables is still rejected."""
        with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
            validate_prompt("Hello {{name}}! {{#show}}extra{{/show}}", is_mustache=True)
