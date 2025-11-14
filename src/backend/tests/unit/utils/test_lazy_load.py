import pytest
from langflow.utils.lazy_load import LazyLoadDictBase


class TestLazyLoadDictBase:
    """Test cases for LazyLoadDictBase class."""

    class ConcreteLazyLoad(LazyLoadDictBase):
        """Concrete implementation for testing."""

        def __init__(self, build_dict_return="__default__", get_type_dict_return=None):
            super().__init__()
            if build_dict_return == "__default__":
                self.build_dict_return = {"test": "value"}
            else:
                self.build_dict_return = build_dict_return
            self.get_type_dict_return = get_type_dict_return or {"type": "dict"}
            self.build_dict_call_count = 0

        def _build_dict(self):
            self.build_dict_call_count += 1
            return self.build_dict_return

        def get_type_dict(self):
            return self.get_type_dict_return

    def test_lazy_load_dict_base_initialization(self):
        """Test proper initialization of LazyLoadDictBase."""
        lazy_load = self.ConcreteLazyLoad()

        assert lazy_load._all_types_dict is None
        assert lazy_load.build_dict_call_count == 0

    def test_all_types_dict_lazy_loading(self):
        """Test that all_types_dict is loaded lazily."""
        test_dict = {"key1": "value1", "key2": "value2"}
        lazy_load = self.ConcreteLazyLoad(build_dict_return=test_dict)

        # First access should trigger _build_dict
        result = lazy_load.all_types_dict

        assert result == test_dict
        assert lazy_load.build_dict_call_count == 1
        assert lazy_load._all_types_dict == test_dict

    def test_all_types_dict_caching(self):
        """Test that all_types_dict is cached after first access."""
        test_dict = {"cached": "value"}
        lazy_load = self.ConcreteLazyLoad(build_dict_return=test_dict)

        # First access
        result1 = lazy_load.all_types_dict
        # Second access
        result2 = lazy_load.all_types_dict

        assert result1 == test_dict
        assert result2 == test_dict
        assert result1 is result2  # Same object reference
        assert lazy_load.build_dict_call_count == 1  # Only called once

    def test_all_types_dict_multiple_accesses(self):
        """Test multiple accesses to all_types_dict property."""
        test_dict = {"multi": "access", "test": "value"}
        lazy_load = self.ConcreteLazyLoad(build_dict_return=test_dict)

        # Multiple accesses
        for _ in range(5):
            result = lazy_load.all_types_dict
            assert result == test_dict

        # _build_dict should only be called once
        assert lazy_load.build_dict_call_count == 1

    def test_build_dict_not_implemented_error(self):
        """Test that _build_dict raises NotImplementedError in base class."""
        base = LazyLoadDictBase()

        with pytest.raises(NotImplementedError):
            base._build_dict()

    def test_get_type_dict_not_implemented_error(self):
        """Test that get_type_dict raises NotImplementedError in base class."""
        base = LazyLoadDictBase()

        with pytest.raises(NotImplementedError):
            base.get_type_dict()

    def test_get_type_dict_implementation(self):
        """Test that get_type_dict works correctly in concrete implementation."""
        type_dict = {"component": "type", "data": "structure"}
        lazy_load = self.ConcreteLazyLoad(get_type_dict_return=type_dict)

        result = lazy_load.get_type_dict()

        assert result == type_dict

    def test_all_types_dict_with_empty_dict(self):
        """Test all_types_dict with empty dictionary from _build_dict."""
        lazy_load = self.ConcreteLazyLoad(build_dict_return={})

        result = lazy_load.all_types_dict

        assert result == {}
        assert lazy_load.build_dict_call_count == 1

    def test_all_types_dict_with_none_from_build_dict(self):
        """Test all_types_dict when _build_dict returns None."""
        lazy_load = self.ConcreteLazyLoad(build_dict_return=None)

        result = lazy_load.all_types_dict

        assert result is None
        assert lazy_load.build_dict_call_count == 1

    def test_all_types_dict_with_complex_data(self):
        """Test all_types_dict with complex nested data structures."""
        complex_dict = {
            "components": {"llm": ["OpenAI", "Anthropic"], "tools": {"python": "PythonTool", "api": "APITool"}},
            "metadata": {"version": "1.0", "updated": "2023-01-01"},
        }
        lazy_load = self.ConcreteLazyLoad(build_dict_return=complex_dict)

        result = lazy_load.all_types_dict

        assert result == complex_dict
        assert result["components"]["llm"] == ["OpenAI", "Anthropic"]
        assert result["components"]["tools"]["python"] == "PythonTool"
        assert lazy_load.build_dict_call_count == 1

    def test_inheritance_behavior(self):
        """Test that inheritance works properly."""

        class CustomLazyLoad(LazyLoadDictBase):
            def _build_dict(self):
                return {"custom": "implementation"}

            def get_type_dict(self):
                return {"custom": "type_dict"}

        custom = CustomLazyLoad()

        assert custom.all_types_dict == {"custom": "implementation"}
        assert custom.get_type_dict() == {"custom": "type_dict"}

    def test_all_types_dict_property_behavior(self):
        """Test that all_types_dict behaves as a proper property."""
        lazy_load = self.ConcreteLazyLoad(build_dict_return={"prop": "test"})

        # Check that it's a property and not a method
        assert hasattr(type(lazy_load), "all_types_dict")
        assert isinstance(type(lazy_load).all_types_dict, property)

        # Accessing it should return the value, not a method
        result = lazy_load.all_types_dict
        assert callable(result) is False
        assert result == {"prop": "test"}

    def test_state_consistency(self):
        """Test that internal state remains consistent."""
        lazy_load = self.ConcreteLazyLoad(build_dict_return={"state": "test"})

        # Initially _all_types_dict should be None
        assert lazy_load._all_types_dict is None

        # After first access, it should be set
        result = lazy_load.all_types_dict
        assert lazy_load._all_types_dict is not None
        assert lazy_load._all_types_dict == {"state": "test"}

        # The returned value should be the same as internal state
        assert result is lazy_load._all_types_dict

    def test_manual_dict_assignment(self):
        """Test behavior when _all_types_dict is manually assigned."""
        lazy_load = self.ConcreteLazyLoad(build_dict_return={"build": "dict"})

        # Manually assign the dict
        manual_dict = {"manual": "assignment"}
        lazy_load._all_types_dict = manual_dict

        # Should return the manually assigned dict, not call _build_dict
        result = lazy_load.all_types_dict

        assert result == manual_dict
        assert lazy_load.build_dict_call_count == 0  # _build_dict not called
