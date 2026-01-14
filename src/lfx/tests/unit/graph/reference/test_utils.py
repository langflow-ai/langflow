# src/lfx/tests/unit/graph/reference/test_utils.py
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


def test_traverse_missing_key_returns_none():
    data = {"name": "John"}
    result = traverse_dot_path(data, "age")
    assert result is None


def test_traverse_invalid_index_returns_none():
    data = {"items": ["a", "b"]}
    result = traverse_dot_path(data, "items[10]")
    assert result is None


def test_traverse_empty_path():
    data = {"name": "John"}
    result = traverse_dot_path(data, "")
    assert result == data


def test_traverse_none_data():
    result = traverse_dot_path(None, "name")
    assert result is None


def test_traverse_deeply_nested():
    data = {"a": {"b": {"c": {"d": "value"}}}}
    result = traverse_dot_path(data, "a.b.c.d")
    assert result == "value"


def test_traverse_rejects_dunder_attributes():
    """Security: prevent access to __class__, __dict__, etc."""

    class TestObj:
        name = "test"

    obj = TestObj()
    # Should return None for dunder attributes
    result = traverse_dot_path(obj, "__class__")
    assert result is None
    result = traverse_dot_path(obj, "__dict__")
    assert result is None


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
    result = traverse_dot_path(obj, "_secret")
    assert result is None


def test_traverse_allows_underscore_in_dict_keys():
    """Dict keys with underscores should still work."""
    data = {"_private_key": "value", "__dunder_key__": "value2"}  # pragma: allowlist secret
    result = traverse_dot_path(data, "_private_key")
    assert result == "value"
    result = traverse_dot_path(data, "__dunder_key__")
    assert result == "value2"
