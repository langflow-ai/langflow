"""Tests for langflow.schema.dotdict module."""

import pytest
from langflow.schema.dotdict import dotdict


class TestDotDict:
    def test_dot_access(self):
        d = dotdict({"name": "test", "value": 42})
        assert d.name == "test"
        assert d.value == 42

    def test_bracket_access(self):
        d = dotdict({"key": "val"})
        assert d["key"] == "val"

    def test_dot_set(self):
        d = dotdict()
        d.name = "hello"
        assert d["name"] == "hello"

    def test_dot_delete(self):
        d = dotdict({"key": "val"})
        del d.key
        assert "key" not in d

    def test_delete_missing_raises(self):
        d = dotdict()
        with pytest.raises(AttributeError, match="has no attribute"):
            del d.nonexistent

    def test_missing_attr_returns_empty_dotdict(self):
        d = dotdict({"a": 1})
        # __missing__ returns an empty dotdict for missing keys via __getattr__
        result = d.nonexistent
        assert isinstance(result, dotdict)
        assert len(result) == 0

    def test_missing_key_returns_empty_dotdict(self):
        d = dotdict()
        result = d["nonexistent"]
        assert isinstance(result, dotdict)
        assert len(result) == 0

    def test_nested_dict_auto_converted(self):
        d = dotdict({"nested": {"inner": "value"}})
        assert isinstance(d.nested, dotdict)
        assert d.nested.inner == "value"

    def test_set_nested_dict_auto_converted(self):
        d = dotdict()
        d.nested = {"inner": "value"}
        assert isinstance(d["nested"], dotdict)
        assert d.nested.inner == "value"

    def test_already_dotdict_not_rewrapped(self):
        inner = dotdict({"x": 1})
        d = dotdict({"nested": inner})
        assert d.nested is inner

    def test_is_dict_subclass(self):
        d = dotdict({"a": 1})
        assert isinstance(d, dict)

    def test_deep_nesting(self):
        d = dotdict({"a": {"b": {"c": {"d": "deep"}}}})
        assert d.a.b.c.d == "deep"

    def test_items_and_keys(self):
        d = dotdict({"x": 1, "y": 2})
        assert set(d.keys()) == {"x", "y"}
        assert dict(d.items()) == {"x": 1, "y": 2}

    def test_update(self):
        d = dotdict({"a": 1})
        d.update({"b": 2})
        assert d.b == 2
