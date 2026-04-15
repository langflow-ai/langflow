"""Tests for JSON schema utilities, including self-referential schema handling."""

from unittest.mock import patch

import pytest
from lfx.io.schema import flatten_schema
from lfx.schema.json_schema import create_input_schema_from_json_schema


class TestCreateInputSchemaFromJsonSchema:
    """Tests for create_input_schema_from_json_schema."""

    def test_simple_flat_schema(self):
        """A simple flat schema should build successfully."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "A name"},
                "count": {"type": "integer"},
            },
            "required": ["name"],
        }
        model = create_input_schema_from_json_schema(schema)
        assert model is not None
        instance = model(name="hello")
        assert instance.name == "hello"  # type: ignore[attr-defined]
        assert instance.count is None  # type: ignore[attr-defined]

    def test_schema_with_defs(self):
        """A schema with $defs and $ref should resolve correctly."""
        schema = {
            "type": "object",
            "$defs": {
                "Address": {
                    "type": "object",
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                    },
                    "required": ["street"],
                }
            },
            "properties": {
                "address": {"$ref": "#/$defs/Address"},
            },
            "required": ["address"],
        }
        model = create_input_schema_from_json_schema(schema)
        assert model is not None

    def test_self_referential_schema_does_not_recurse(self):
        """A self-referential schema (tree node) must not cause infinite recursion."""
        schema = {
            "type": "object",
            "$defs": {
                "TreeNode": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "children": {
                            "type": "array",
                            "items": {"$ref": "#/$defs/TreeNode"},
                        },
                    },
                    "required": ["value"],
                }
            },
            "properties": {
                "root": {"$ref": "#/$defs/TreeNode"},
            },
            "required": ["root"],
        }
        # Must not raise RecursionError or any other exception
        model = create_input_schema_from_json_schema(schema)
        assert model is not None

    def test_circular_ref_chain_does_not_loop(self):
        """A circular $ref chain (A → B → A) must not cause infinite recursion."""
        schema = {
            "type": "object",
            "$defs": {
                "A": {"$ref": "#/$defs/B"},
                "B": {"$ref": "#/$defs/A"},
            },
            "properties": {
                "field": {"$ref": "#/$defs/A"},
            },
        }
        # Must not raise RecursionError
        model = create_input_schema_from_json_schema(schema)
        assert model is not None

    def test_directly_self_referential_def(self):
        """A $def that directly references itself must not cause infinite recursion."""
        schema = {
            "type": "object",
            "$defs": {
                "Node": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "integer"},
                        "next": {"$ref": "#/$defs/Node"},
                    },
                    "required": ["value"],
                }
            },
            "properties": {
                "head": {"$ref": "#/$defs/Node"},
            },
            "required": ["head"],
        }
        model = create_input_schema_from_json_schema(schema)
        assert model is not None

    def test_self_referential_fallback_type(self):
        """Self-referential field should fall back to dict, not disappear."""
        schema = {
            "type": "object",
            "$defs": {
                "Node": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "integer"},
                        "next": {"$ref": "#/$defs/Node"},
                    },
                    "required": ["value"],
                }
            },
            "properties": {"head": {"$ref": "#/$defs/Node"}},
            "required": ["head"],
        }
        model = create_input_schema_from_json_schema(schema)
        # Verify the model can be instantiated with nested data
        instance = model(head={"value": 1, "next": {"value": 2}})
        assert instance.head is not None

    def test_self_referential_logs_warning(self):
        """Self-referential detection should emit a warning."""
        schema = {
            "type": "object",
            "$defs": {
                "Node": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "next": {"$ref": "#/$defs/Node"},
                    },
                }
            },
            "properties": {"head": {"$ref": "#/$defs/Node"}},
        }
        with patch("lfx.schema.json_schema.logger") as mock_logger:
            create_input_schema_from_json_schema(schema)
            # At least one warning about self-referential should be logged
            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            assert any("Self-referential" in call or "self-referential" in call for call in warning_calls)

    def test_schema_with_defs_instantiation(self):
        """A schema with $defs should produce a model that can be instantiated."""
        schema = {
            "type": "object",
            "$defs": {
                "Address": {
                    "type": "object",
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                    },
                    "required": ["street"],
                }
            },
            "properties": {
                "address": {"$ref": "#/$defs/Address"},
            },
            "required": ["address"],
        }
        model = create_input_schema_from_json_schema(schema)
        instance = model(address={"street": "123 Main St"})
        assert instance.address is not None

    def test_non_object_root_raises(self):
        """A root schema that is not type 'object' should raise ValueError."""
        schema = {"type": "array", "items": {"type": "string"}}
        with pytest.raises(ValueError, match="Root schema must be type 'object'"):
            create_input_schema_from_json_schema(schema)


class TestFlattenSchema:
    """Tests for flatten_schema self-referential handling."""

    def test_flat_schema_passthrough(self):
        """An already-flat schema should be returned unchanged."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }
        result = flatten_schema(schema)
        assert result is schema  # Fast path: returns the same object

    def test_self_referential_schema_does_not_recurse(self):
        """A self-referential schema must not cause infinite recursion in _walk."""
        schema = {
            "type": "object",
            "$defs": {
                "TreeNode": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "children": {
                            "type": "array",
                            "items": {"$ref": "#/$defs/TreeNode"},
                        },
                    },
                }
            },
            "properties": {
                "root": {"$ref": "#/$defs/TreeNode"},
            },
        }
        # Must not raise RecursionError
        result = flatten_schema(schema)
        assert result is not None
        assert "properties" in result
        # The non-recursive leaf "root.value" should be present
        assert "root.value" in result["properties"]

    def test_circular_ref_in_flatten_does_not_loop(self):
        """A circular $ref chain must not loop in _resolve_if_ref."""
        schema = {
            "type": "object",
            "$defs": {
                "A": {"$ref": "#/$defs/B"},
                "B": {"$ref": "#/$defs/A"},
            },
            "properties": {
                "field": {"$ref": "#/$defs/A"},
            },
        }
        # Must not raise RecursionError or loop infinitely
        result = flatten_schema(schema)
        assert result is not None

    def test_flatten_self_ref_preserves_non_recursive_fields(self):
        """Non-recursive fields of a self-referential schema should still appear."""
        schema = {
            "type": "object",
            "$defs": {
                "Node": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "next": {"$ref": "#/$defs/Node"},
                    },
                }
            },
            "properties": {"head": {"$ref": "#/$defs/Node"}},
        }
        result = flatten_schema(schema)
        # The non-recursive leaf "head.value" must NOT be lost
        assert "head.value" in result["properties"]

    def test_flatten_self_ref_logs_warning(self):
        """Self-referential detection in flatten_schema should emit a warning."""
        schema = {
            "type": "object",
            "$defs": {
                "Node": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "next": {"$ref": "#/$defs/Node"},
                    },
                }
            },
            "properties": {"head": {"$ref": "#/$defs/Node"}},
        }
        with patch("lfx.io.schema.logger") as mock_logger:
            flatten_schema(schema)
            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            assert any("circular" in call.lower() or "self-referential" in call.lower() for call in warning_calls)

    def test_flatten_missing_def_logs_warning(self):
        """A $ref pointing to a nonexistent $def should log a warning."""
        schema = {
            "type": "object",
            "$defs": {},
            "properties": {
                "field": {"$ref": "#/$defs/NonExistent"},
            },
        }
        with patch("lfx.io.schema.logger") as mock_logger:
            flatten_schema(schema)
            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            assert any("not found" in call.lower() for call in warning_calls)
