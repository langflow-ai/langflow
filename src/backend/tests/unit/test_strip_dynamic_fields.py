"""Tests for the _strip_dynamic_fields function in build_component_index.py."""

import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def strip_dynamic_fields_func():
    """Fixture to import and provide the _strip_dynamic_fields function."""
    script_path = Path(__file__).parent.parent.parent.parent.parent / "scripts" / "build_component_index.py"

    if not script_path.exists():
        pytest.skip(f"build_component_index.py not found at {script_path}")

    import importlib.util

    spec = importlib.util.spec_from_file_location("build_component_index", script_path)
    build_module = importlib.util.module_from_spec(spec)
    sys.modules["build_component_index"] = build_module
    spec.loader.exec_module(build_module)

    return build_module._strip_dynamic_fields


class TestStripDynamicFields:
    """Test cases for _strip_dynamic_fields function."""

    def test_removes_timestamp_from_dict(self, strip_dynamic_fields_func):
        """Test that timestamp field is removed from a dictionary."""
        data = {"name": "test", "timestamp": "2025-12-18 10:00:00", "value": 42}
        result = strip_dynamic_fields_func(data)
        assert "timestamp" not in result
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_preserves_non_dynamic_fields(self, strip_dynamic_fields_func):
        """Test that non-dynamic fields are preserved."""
        data = {"name": "component", "version": "1.0.0", "metadata": {"key": "value"}, "options": ["a", "b"]}
        result = strip_dynamic_fields_func(data)
        assert result["name"] == "component"
        assert result["version"] == "1.0.0"
        assert result["metadata"] == {"key": "value"}

    def test_removes_timestamp_from_nested_dict(self, strip_dynamic_fields_func):
        """Test that timestamp is removed from nested dictionaries."""
        data = {"level1": {"level2": {"timestamp": "2025-12-18 10:00:00", "data": "important"}}}
        result = strip_dynamic_fields_func(data)
        assert "timestamp" not in result["level1"]["level2"]
        assert result["level1"]["level2"]["data"] == "important"

    def test_removes_timestamp_from_list_items(self, strip_dynamic_fields_func):
        """Test that timestamp is removed from items in a list."""
        data = [
            {"timestamp": "2025-12-18 10:00:00", "id": 1},
            {"timestamp": "2025-12-18 10:00:01", "id": 2},
            {"id": 3},
        ]
        result = strip_dynamic_fields_func(data)
        assert all("timestamp" not in item for item in result)
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2
        assert result[2]["id"] == 3

    def test_handles_empty_dict(self, strip_dynamic_fields_func):
        """Test that empty dictionary is handled correctly."""
        result = strip_dynamic_fields_func({})
        assert result == {}

    def test_handles_empty_list(self, strip_dynamic_fields_func):
        """Test that empty list is handled correctly."""
        result = strip_dynamic_fields_func([])
        assert result == []

    def test_handles_primitives(self, strip_dynamic_fields_func):
        """Test that primitive types are returned unchanged."""
        assert strip_dynamic_fields_func("string") == "string"
        assert strip_dynamic_fields_func(42) == 42
        assert strip_dynamic_fields_func(3.14) == 3.14
        assert strip_dynamic_fields_func(None) is None

    def test_complex_nested_structure(self, strip_dynamic_fields_func):
        """Test with a complex nested structure similar to component metadata."""
        data = {
            "version": "1.7.0",
            "metadata": {"num_modules": 95, "num_components": 355},
            "entries": [
                [
                    "Model",
                    {
                        "AstraAssistantManager": {
                            "display_name": "Astra Assistant Manager",
                            "template": {
                                "model_name": {
                                    "value": {"data": {"timestamp": "2025-12-18 20:55:52 UTC"}},
                                    "options": ["gpt-4", "gpt-3.5-turbo"],
                                }
                            },
                        }
                    },
                ]
            ],
        }
        result = strip_dynamic_fields_func(data)
        assert result["version"] == "1.7.0"
        assert result["metadata"]["num_modules"] == 95
        model_value = result["entries"][0][1]["AstraAssistantManager"]["template"]["model_name"]["value"]["data"]
        assert "timestamp" not in model_value
        assert result["entries"][0][0] == "Model"

    def test_mixed_list_with_dicts_and_primitives(self, strip_dynamic_fields_func):
        """Test list containing both dictionaries and primitives."""
        data = [
            {"timestamp": "2025-12-18", "value": 1},
            "string_item",
            42,
            {"id": 2},
        ]
        result = strip_dynamic_fields_func(data)
        assert "timestamp" not in result[0]
        assert result[0]["value"] == 1
        assert result[1] == "string_item"
        assert result[2] == 42
        assert result[3] == {"id": 2}

    def test_multiple_timestamps_in_structure(self, strip_dynamic_fields_func):
        """Test that all timestamp fields at all levels are removed."""
        data = {
            "timestamp": "2025-12-18 10:00:00",
            "nested": {
                "timestamp": "2025-12-18 10:00:01",
                "deep": {"timestamp": "2025-12-18 10:00:02", "value": "keep_this"},
            },
            "items": [{"timestamp": "2025-12-18 10:00:03", "id": 1}],
        }
        result = strip_dynamic_fields_func(data)
        assert "timestamp" not in result
        assert "timestamp" not in result["nested"]
        assert "timestamp" not in result["nested"]["deep"]
        assert "timestamp" not in result["items"][0]
        assert result["nested"]["deep"]["value"] == "keep_this"
        assert result["items"][0]["id"] == 1

    def test_preserves_field_order_in_dict(self, strip_dynamic_fields_func):
        """Test that dictionary key order is preserved (Python 3.7+)."""
        data = {"aaa": 1, "bbb": 2, "timestamp": "remove_me", "ccc": 3}
        result = strip_dynamic_fields_func(data)
        keys = list(result.keys())
        assert "timestamp" not in keys
        assert keys == ["aaa", "bbb", "ccc"]

    def test_deeply_nested_list_of_dicts(self, strip_dynamic_fields_func):
        """Test deeply nested list containing dictionaries with timestamps."""
        data = {
            "items": [
                {
                    "nested_items": [
                        {"timestamp": "2025-12-18", "value": 1},
                        {"timestamp": "2025-12-18", "value": 2},
                    ]
                }
            ]
        }
        result = strip_dynamic_fields_func(data)
        nested_dicts = result["items"][0]["nested_items"]
        assert all("timestamp" not in d for d in nested_dicts)
        assert nested_dicts[0]["value"] == 1
        assert nested_dicts[1]["value"] == 2
