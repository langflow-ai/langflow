# src/lfx/tests/unit/graph/reference/test_utils.py
import pytest
from lfx.graph.reference.utils import traverse_dot_path


def test_traverse_simple_key():
    data = {"name": "John"}
    result = traverse_dot_path(data, "name")
    assert result == "John"


def test_traverse_nested_key():
    data = {"user": {"name": "John"}}
    result = traverse_dot_path(data, "user.name")
    assert result == "John"


def test_traverse_array_index():
    data = {"items": ["a", "b", "c"]}
    result = traverse_dot_path(data, "items[1]")
    assert result == "b"


def test_traverse_nested_array():
    data = {"users": [{"name": "John"}, {"name": "Jane"}]}
    result = traverse_dot_path(data, "users[1].name")
    assert result == "Jane"


def test_traverse_missing_key_raises():
    data = {"name": "John"}
    with pytest.raises(ValueError, match="Key 'age' not found in dict"):
        traverse_dot_path(data, "age")


def test_traverse_invalid_index_raises():
    data = {"items": ["a", "b"]}
    with pytest.raises(ValueError, match="Index 10 out of range"):
        traverse_dot_path(data, "items[10]")


def test_traverse_empty_path():
    data = {"name": "John"}
    result = traverse_dot_path(data, "")
    assert result == data


def test_traverse_none_data_raises():
    with pytest.raises(ValueError, match="Cannot traverse path 'name' on None value"):
        traverse_dot_path(None, "name")


def test_traverse_deeply_nested():
    data = {"a": {"b": {"c": {"d": "value"}}}}
    result = traverse_dot_path(data, "a.b.c.d")
    assert result == "value"


def test_traverse_rejects_dunder_attributes():
    """Security: prevent access to __class__, __dict__, etc."""

    class TestObj:
        name = "test"

    obj = TestObj()
    with pytest.raises(ValueError, match="private attribute"):
        traverse_dot_path(obj, "__class__")
    with pytest.raises(ValueError, match="private attribute"):
        traverse_dot_path(obj, "__dict__")


def test_traverse_rejects_private_attributes():
    """Security: prevent access to _private attributes."""

    class TestObj:
        name = "public"
        _secret = "private"  # noqa: S105  # pragma: allowlist secret

    obj = TestObj()
    # Public attribute works
    result = traverse_dot_path(obj, "name")
    assert result == "public"
    # Private attribute is blocked
    with pytest.raises(ValueError, match="private attribute"):
        traverse_dot_path(obj, "_secret")


def test_traverse_allows_underscore_in_dict_keys():
    """Dict keys with underscores should still work."""
    data = {"_private_key": "value", "__dunder_key__": "value2"}  # pragma: allowlist secret
    result = traverse_dot_path(data, "_private_key")
    assert result == "value"
    result = traverse_dot_path(data, "__dunder_key__")
    assert result == "value2"


def test_traverse_none_intermediate_raises():
    """Traversing through an intermediate None value should raise."""
    data = {"user": None}
    with pytest.raises(ValueError, match="Cannot traverse 'name' on None value"):
        traverse_dot_path(data, "user.name")


def test_traverse_index_on_non_list_raises():
    """Array index on a non-list should raise."""
    data = {"value": "not a list"}
    with pytest.raises(ValueError, match="Index 0 out of range"):
        traverse_dot_path(data, "value[0]")


def test_traverse_attribute_not_found_raises():
    """Accessing a missing attribute on an object should raise."""

    class TestObj:
        name = "test"

    obj = TestObj()
    with pytest.raises(ValueError, match="Attribute 'missing' not found"):
        traverse_dot_path(obj, "missing")
