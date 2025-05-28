from pathlib import Path
from unittest import mock

import pytest
from langflow.utils.validate import (
    create_class,
    create_function,
    execute_function,
    extract_function_name,
    validate_code,
)
from requests.exceptions import MissingSchema


def test_create_function():
    code = """
from pathlib import Path

def my_function(x: str) -> Path:
    return Path(x)
"""

    function_name = extract_function_name(code)
    function = create_function(code, function_name)
    result = function("test")
    assert result == Path("test")


def test_validate_code():
    # Test case with a valid import and function
    code1 = """
import math

def square(x):
    return x ** 2
"""
    errors1 = validate_code(code1)
    assert errors1 == {"imports": {"errors": []}, "function": {"errors": []}}

    # Test case with an invalid import and valid function
    code2 = """
import non_existent_module

def square(x):
    return x ** 2
"""
    errors2 = validate_code(code2)
    assert errors2 == {
        "imports": {"errors": ["No module named 'non_existent_module'"]},
        "function": {"errors": []},
    }

    # Test case with a valid import and invalid function syntax
    code3 = """
import math

def square(x)
    return x ** 2
"""
    errors3 = validate_code(code3)
    assert errors3 == {
        "imports": {"errors": []},
        "function": {"errors": ["expected ':' (<unknown>, line 4)"]},
    }


def test_execute_function_success():
    code = """
import math

def my_function(x):
    return math.sin(x) + 1
    """
    result = execute_function(code, "my_function", 0.5)
    assert result == 1.479425538604203


def test_execute_function_missing_module():
    code = """
import some_missing_module

def my_function(x):
    return some_missing_module.some_function(x)
    """
    with pytest.raises(ModuleNotFoundError):
        execute_function(code, "my_function", 0.5)


def test_execute_function_missing_function():
    code = """
import math

def my_function(x):
    return math.some_missing_function(x)
    """
    with pytest.raises(AttributeError):
        execute_function(code, "my_function", 0.5)


def test_execute_function_missing_schema():
    code = """
import requests

def my_function(x):
    return requests.get(x).text
    """
    with mock.patch("requests.get", side_effect=MissingSchema), pytest.raises(MissingSchema):
        execute_function(code, "my_function", "invalid_url")


def test_create_class():
    code = """
from langflow.custom import CustomComponent

class ExternalClass:
    def __init__(self, value):
        self.value = value

class MyComponent(CustomComponent):
    def build(self):
        return ExternalClass("test")
"""
    class_name = "MyComponent"
    created_class = create_class(code, class_name)
    instance = created_class()
    result = instance.build()
    assert result.value == "test"


def test_create_class_module_import():
    code = """
from langflow.custom import CustomComponent
from PIL import ImageDraw

class ExternalClass:
    def __init__(self, value):
        self.value = value

class MyComponent(CustomComponent):
    def build(self):
        return ExternalClass("test")
"""
    class_name = "MyComponent"
    created_class = create_class(code, class_name)
    instance = created_class()
    result = instance.build()
    assert result.value == "test"


def test_create_class_with_multiple_external_classes():
    code = """
from langflow.custom import CustomComponent

class ExternalClass1:
    def __init__(self, value):
        self.value = value

class ExternalClass2:
    def __init__(self, value):
        self.value = value

class MyComponent(CustomComponent):
    def build(self):
        return ExternalClass1("test1"), ExternalClass2("test2")
"""
    class_name = "MyComponent"
    created_class = create_class(code, class_name)
    instance = created_class()
    result1, result2 = instance.build()
    assert result1.value == "test1"
    assert result2.value == "test2"


def test_create_class_with_external_variables_and_functions():
    code = """
from langflow.custom import CustomComponent

external_variable = "external_value"

def external_function():
    return "external_function_value"

class MyComponent(CustomComponent):
    def build(self):
        return external_variable, external_function()
"""
    class_name = "MyComponent"
    created_class = create_class(code, class_name)
    instance = created_class()
    result_variable, result_function = instance.build()
    assert result_variable == "external_value"
    assert result_function == "external_function_value"


def test_class_constructor_caching():
    """Test that class constructors are properly cached."""
    from langflow.utils.validate import clear_class_constructor_cache, get_cache_stats

    # Clear cache to start fresh
    clear_class_constructor_cache()
    initial_stats = get_cache_stats()
    assert initial_stats["cache_size"] == 0

    code = """
from langflow.custom import CustomComponent

class CachedComponent(CustomComponent):
    def build(self):
        return "cached_result"
"""
    class_name = "CachedComponent"

    # First call should create and cache
    created_class1 = create_class(code, class_name)
    stats_after_first = get_cache_stats()
    assert stats_after_first["cache_size"] == 1

    # Second call with same code should use cache
    created_class2 = create_class(code, class_name)
    stats_after_second = get_cache_stats()
    assert stats_after_second["cache_size"] == 1  # Should not increase

    # Both should produce working instances
    instance1 = created_class1()
    instance2 = created_class2()
    assert instance1.build() == "cached_result"
    assert instance2.build() == "cached_result"

    # Different code should create new cache entry
    different_code = """
from langflow.custom import CustomComponent

class DifferentComponent(CustomComponent):
    def build(self):
        return "different_result"
"""
    created_class3 = create_class(different_code, "DifferentComponent")
    stats_after_different = get_cache_stats()
    assert stats_after_different["cache_size"] == 2

    # Verify the third class works correctly too
    instance3 = created_class3()
    assert instance3.build() == "different_result"


def test_cache_cleanup():
    """Test that cache cleanup works when cache size limit is reached."""
    from langflow.utils.validate import _CACHE_MAX_SIZE, clear_class_constructor_cache, get_cache_stats

    # Clear cache and set a small cache size for testing
    clear_class_constructor_cache()

    # Test with a small cache size by temporarily modifying the max size
    original_max_size = _CACHE_MAX_SIZE

    try:
        # Set max size to 3 for testing
        import langflow.utils.validate as validate_module

        validate_module._CACHE_MAX_SIZE = 3

        # Create 5 different components (more than cache size)
        for i in range(5):
            code = f"""
from langflow.custom import CustomComponent

class TestComponent{i}(CustomComponent):
    def build(self):
        return "result_{i}"
"""
            create_class(code, f"TestComponent{i}")

        # Cache should not exceed max size due to cleanup
        final_stats = get_cache_stats()
        assert final_stats["cache_size"] <= 3

    finally:
        # Restore original max size
        validate_module._CACHE_MAX_SIZE = original_max_size
        clear_class_constructor_cache()
