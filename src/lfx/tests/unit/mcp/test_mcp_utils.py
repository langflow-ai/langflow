"""Tests for MCP utilities."""

import pytest
from pydantic import BaseModel

from lfx.base.mcp.util import (
    create_input_schema_from_json_schema,
    get_unique_name,
    sanitize_mcp_name,
    validate_headers,
)


class TestValidateHeaders:
    """Test the validate_headers function."""

    def test_empty_headers(self):
        """Test with empty headers."""
        assert validate_headers({}) == {}
        assert validate_headers(None) == {}

    def test_valid_headers(self):
        """Test with valid headers."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer token123",
            "X-API-Key": "my-api-key",
        }
        result = validate_headers(headers)
        assert result == {
            "content-type": "application/json",
            "authorization": "Bearer token123",
            "x-api-key": "my-api-key",
        }

    def test_case_insensitive_headers(self):
        """Test that headers are normalized to lowercase."""
        headers = {
            "CONTENT-TYPE": "text/plain",
            "content-type": "application/json",  # Duplicate with different case
        }
        result = validate_headers(headers)
        # Should keep only one, normalized to lowercase
        assert "content-type" in result

    def test_invalid_header_names(self):
        """Test headers with invalid names are skipped."""
        headers = {
            "Valid-Header": "value",
            "Invalid Header": "value",  # Space not allowed
            "Invalid\nHeader": "value",  # Newline not allowed
            "": "value",  # Empty name
            "123-Invalid": "value",  # Valid according to RFC 7230
        }
        result = validate_headers(headers)
        assert "valid-header" in result
        assert "invalid header" not in result
        assert "invalid\nheader" not in result
        assert "" not in result
        assert "123-invalid" in result  # Numbers are allowed

    def test_header_injection_prevention(self):
        """Test that header injection attempts are prevented."""
        headers = {
            "Safe-Header": "safe value",
            "Injection-Header": "value\r\nX-Evil: injected",
            "Newline-Header": "value\nwith newline",
        }
        result = validate_headers(headers)
        assert "safe-header" in result
        assert "injection-header" not in result
        assert "newline-header" not in result

    def test_control_character_removal(self):
        """Test that control characters are removed from values."""
        headers = {
            "Header1": "value\x00with\x01null",
            "Header2": "value\twith\ttab",  # Tab should be preserved
            "Header3": "value with spaces",  # Spaces should be preserved
        }
        result = validate_headers(headers)
        assert result["header1"] == "valuewithnull"
        assert result["header2"] == "value\twith\ttab"
        assert result["header3"] == "value with spaces"

    def test_non_string_headers_skipped(self):
        """Test that non-string headers are skipped."""
        headers = {
            "string": "value",
            123: "numeric key",  # Should be skipped
            "list": ["not", "a", "string"],  # Should be skipped
        }
        result = validate_headers(headers)
        assert "string" in result
        assert 123 not in result
        assert "list" not in result

    def test_empty_value_after_sanitization(self):
        """Test headers that become empty after sanitization are skipped."""
        headers = {
            "Empty": "",
            "OnlySpaces": "   ",
            "OnlyControl": "\x00\x01\x02",
        }
        result = validate_headers(headers)
        assert len(result) == 0


class TestSanitizeMCPName:
    """Test the sanitize_mcp_name function."""

    def test_empty_name(self):
        """Test with empty or whitespace names."""
        assert sanitize_mcp_name("") == ""
        assert sanitize_mcp_name("   ") == ""
        assert sanitize_mcp_name(None) == ""

    def test_simple_names(self):
        """Test with simple alphanumeric names."""
        assert sanitize_mcp_name("HelloWorld") == "helloworld"
        assert sanitize_mcp_name("test123") == "test123"
        assert sanitize_mcp_name("CamelCase") == "camelcase"

    def test_special_characters(self):
        """Test with special characters."""
        assert sanitize_mcp_name("hello-world") == "hello_world"
        assert sanitize_mcp_name("hello world") == "hello_world"
        assert sanitize_mcp_name("hello@world!") == "helloworld"
        assert sanitize_mcp_name("test.file.name") == "testfilename"

    def test_emoji_removal(self):
        """Test that emojis are removed."""
        assert sanitize_mcp_name("Hello 😊 World") == "hello_world"
        assert sanitize_mcp_name("🚀 Rocket Launch") == "rocket_launch"
        assert sanitize_mcp_name("Test 🔥🎉🌟") == "test"

    def test_diacritic_removal(self):
        """Test that diacritics are removed."""
        assert sanitize_mcp_name("café") == "cafe"
        assert sanitize_mcp_name("naïve") == "naive"
        assert sanitize_mcp_name("Zürich") == "zurich"

    def test_multiple_underscores(self):
        """Test that multiple underscores are collapsed."""
        assert sanitize_mcp_name("hello___world") == "hello_world"
        assert sanitize_mcp_name("test   multiple   spaces") == "test_multiple_spaces"

    def test_numeric_prefix(self):
        """Test that numeric prefixes get underscore prepended."""
        assert sanitize_mcp_name("123test") == "_123test"
        assert sanitize_mcp_name("1_test") == "_1_test"

    def test_max_length(self):
        """Test that names are truncated to max length."""
        long_name = "a" * 100
        result = sanitize_mcp_name(long_name, max_length=10)
        assert len(result) == 10
        assert result == "aaaaaaaaaa"

        # Test truncation doesn't end with underscore
        result = sanitize_mcp_name("test_" + "a" * 100, max_length=5)
        assert result == "test"  # Trailing underscore removed

    def test_default_max_length(self):
        """Test default max length of 46."""
        long_name = "a" * 100
        result = sanitize_mcp_name(long_name)
        assert len(result) == 46

    def test_complex_names(self):
        """Test with complex real-world names."""
        assert sanitize_mcp_name("My Awesome Tool! 🎉") == "my_awesome_tool"
        assert sanitize_mcp_name("API-Key-Generator v2.0") == "api_key_generator_v2_0"
        assert sanitize_mcp_name("__leading__underscores__") == "leading_underscores"


class TestGetUniqueName:
    """Test the get_unique_name function."""

    def test_no_conflict(self):
        """Test when name doesn't exist in set."""
        existing = {"tool1", "tool2"}
        assert get_unique_name("tool3", 10, existing) == "tool3"

    def test_simple_conflict(self):
        """Test when name exists, should append _1."""
        existing = {"tool"}
        assert get_unique_name("tool", 10, existing) == "tool_1"

    def test_multiple_conflicts(self):
        """Test with multiple existing conflicts."""
        existing = {"tool", "tool_1", "tool_2"}
        assert get_unique_name("tool", 10, existing) == "tool_3"

    def test_truncation_with_conflict(self):
        """Test truncation when adding suffix."""
        existing = {"toolname"}
        # With max_length=8, "toolname_1" would be too long
        # So it should truncate to "tooln_1"
        result = get_unique_name("toolname", 8, existing)
        assert result == "tooln_1"
        assert len(result) <= 8

    def test_many_conflicts(self):
        """Test with many conflicts to ensure counter works."""
        existing = {f"test_{i}" for i in range(20)}
        existing.add("test")
        result = get_unique_name("test", 10, existing)
        assert result == "test_20"


class TestCreateInputSchemaFromJsonSchema:
    """Test the create_input_schema_from_json_schema function."""

    def test_simple_object_schema(self):
        """Test creating a model from a simple object schema."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "User name"},
                "age": {"type": "integer", "description": "User age"},
            },
            "required": ["name"],
        }

        model = create_input_schema_from_json_schema(schema)

        # Test the model class
        assert issubclass(model, BaseModel)

        # Test creating an instance
        instance = model(name="Alice", age=30)
        assert instance.name == "Alice"
        assert instance.age == 30

        # Test optional field
        instance2 = model(name="Bob")
        assert instance2.name == "Bob"
        assert instance2.age is None

    def test_nested_object_schema(self):
        """Test creating a model with nested objects."""
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                    },
                    "required": ["name"],
                },
                "settings": {
                    "type": "object",
                    "properties": {
                        "theme": {"type": "string", "default": "light"},
                    },
                },
            },
            "required": ["user"],
        }

        model = create_input_schema_from_json_schema(schema)

        # Test creating instance with nested data
        instance = model(
            user={"name": "Alice", "email": "alice@example.com"},
            settings={"theme": "dark"},
        )
        assert instance.user.name == "Alice"
        assert instance.user.email == "alice@example.com"
        assert instance.settings.theme == "dark"

    def test_array_schema(self):
        """Test creating a model with array types."""
        schema = {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tags",
                },
                "scores": {
                    "type": "array",
                    "items": {"type": "number"},
                },
            },
        }

        model = create_input_schema_from_json_schema(schema)

        instance = model(tags=["python", "testing"], scores=[9.5, 8.0])
        assert instance.tags == ["python", "testing"]
        assert instance.scores == [9.5, 8.0]

    def test_nullable_types_with_anyof(self):
        """Test handling of nullable types using anyOf."""
        schema = {
            "type": "object",
            "properties": {
                "optional_string": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                    "description": "Optional string field",
                },
            },
        }

        model = create_input_schema_from_json_schema(schema)

        # Test with value
        instance1 = model(optional_string="hello")
        assert instance1.optional_string == "hello"

        # Test with None
        instance2 = model(optional_string=None)
        assert instance2.optional_string is None

        # Test without field (should default to None)
        instance3 = model()
        assert instance3.optional_string is None

    def test_ref_resolution(self):
        """Test resolution of $ref references."""
        schema = {
            "type": "object",
            "$defs": {
                "Address": {
                    "type": "object",
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                    },
                    "required": ["city"],
                },
            },
            "properties": {
                "home_address": {"$ref": "#/$defs/Address"},
                "work_address": {"$ref": "#/$defs/Address"},
            },
        }

        model = create_input_schema_from_json_schema(schema)

        instance = model(
            home_address={"street": "123 Main St", "city": "Boston"},
            work_address={"city": "Cambridge"},
        )
        assert instance.home_address.city == "Boston"
        assert instance.work_address.city == "Cambridge"
        assert instance.work_address.street is None

    def test_all_primitive_types(self):
        """Test all primitive JSON schema types."""
        schema = {
            "type": "object",
            "properties": {
                "string_field": {"type": "string"},
                "number_field": {"type": "number"},
                "integer_field": {"type": "integer"},
                "boolean_field": {"type": "boolean"},
                "object_field": {"type": "object"},
                "array_field": {"type": "array"},
            },
        }

        model = create_input_schema_from_json_schema(schema)

        instance = model(
            string_field="text",
            number_field=3.14,
            integer_field=42,
            boolean_field=True,
            object_field={"key": "value"},
            array_field=[1, 2, 3],
        )
        assert instance.string_field == "text"
        assert instance.number_field == 3.14
        assert instance.integer_field == 42
        assert instance.boolean_field is True
        assert instance.object_field == {"key": "value"}
        assert instance.array_field == [1, 2, 3]

    def test_error_on_non_object_root(self):
        """Test that non-object root schemas raise ValueError."""
        schema = {"type": "string"}

        with pytest.raises(ValueError, match="Root schema must be type 'object'"):
            create_input_schema_from_json_schema(schema)

    def test_default_values(self):
        """Test handling of default values."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "default": "Anonymous"},
                "count": {"type": "integer", "default": 0},
            },
        }

        model = create_input_schema_from_json_schema(schema)

        # Test with defaults
        instance = model()
        assert instance.name == "Anonymous"
        assert instance.count == 0

        # Test overriding defaults
        instance2 = model(name="Alice", count=5)
        assert instance2.name == "Alice"
        assert instance2.count == 5
