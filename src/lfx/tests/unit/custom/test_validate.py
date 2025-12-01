"""Tests for validate_code - code validation with type detection."""

from __future__ import annotations

import ast

from lfx.custom.validate import _detect_code_type, validate_code


class TestValidateCodeTypeDetection:
    """Tests for code type detection in validate_code."""

    def test_detects_function_code(self):
        """validate_code detects function-based components."""
        code = """
def greet(name: str) -> str:
    return f"Hello, {name}!"
"""
        result = validate_code(code)

        assert result["detected_type"] == "function"
        assert result["function_name"] == "greet"
        assert result["class_name"] is None
        assert result["imports"]["errors"] == []
        assert result["function"]["errors"] == []

    def test_detects_async_function_code(self):
        """validate_code detects async function-based components."""
        code = """
async def async_greet(name: str) -> str:
    return f"Hello, {name}!"
"""
        result = validate_code(code)

        assert result["detected_type"] == "function"
        assert result["function_name"] == "async_greet"

    def test_detects_class_code(self):
        """validate_code detects class-based components."""
        code = """
from lfx.custom.custom_component.component import Component

class MyComponent(Component):
    def process(self) -> str:
        return "hello"
"""
        result = validate_code(code)

        assert result["detected_type"] == "class"
        assert result["class_name"] == "MyComponent"
        assert result["function_name"] is None

    def test_detects_lc_class_code(self):
        """validate_code detects LC-prefixed class components."""
        code = """
from lfx.base import LCModelComponent

class MyModel(LCModelComponent):
    def build_model(self):
        pass
"""
        result = validate_code(code)

        assert result["detected_type"] == "class"
        assert result["class_name"] == "MyModel"

    def test_prefers_class_over_function(self):
        """When both class and function are present, prefers class."""
        code = """
from lfx.custom.custom_component.component import Component

def helper_function():
    return "helper"

class MyComponent(Component):
    def process(self) -> str:
        return helper_function()
"""
        result = validate_code(code)

        assert result["detected_type"] == "class"
        assert result["class_name"] == "MyComponent"

    def test_returns_unknown_for_no_code(self):
        """validate_code returns unknown for code with no function or class."""
        code = """
x = 5
y = 10
"""
        result = validate_code(code)

        assert result["detected_type"] == "unknown"
        assert result["function_name"] is None
        assert result["class_name"] is None

    def test_returns_unknown_for_empty_code(self):
        """validate_code returns unknown for empty code."""
        code = ""
        result = validate_code(code)

        assert result["detected_type"] == "unknown"

    def test_handles_syntax_error(self):
        """validate_code handles syntax errors gracefully."""
        code = "def broken("
        result = validate_code(code)

        assert result["detected_type"] == "unknown"
        assert len(result["function"]["errors"]) > 0


class TestValidateCodeErrors:
    """Tests for error detection in validate_code."""

    def test_detects_import_errors(self):
        """validate_code detects missing module imports."""
        code = """
import nonexistent_module_xyz

def process():
    return nonexistent_module_xyz.something()
"""
        result = validate_code(code)

        assert len(result["imports"]["errors"]) > 0
        assert "nonexistent_module_xyz" in result["imports"]["errors"][0]

    def test_valid_function_no_errors(self):
        """validate_code returns no errors for valid function."""
        code = """
def add(a: int, b: int) -> int:
    return a + b
"""
        result = validate_code(code)

        assert result["imports"]["errors"] == []
        assert result["function"]["errors"] == []
        assert result["detected_type"] == "function"
        assert result["function_name"] == "add"


class TestDetectCodeType:
    """Tests for _detect_code_type helper function."""

    def test_detects_simple_function(self):
        """_detect_code_type detects simple function."""
        code = "def foo(): pass"
        tree = ast.parse(code)
        detected_type, name = _detect_code_type(tree)

        assert detected_type == "function"
        assert name == "foo"

    def test_detects_async_function(self):
        """_detect_code_type detects async function."""
        code = "async def async_foo(): pass"
        tree = ast.parse(code)
        detected_type, name = _detect_code_type(tree)

        assert detected_type == "function"
        assert name == "async_foo"

    def test_detects_component_class(self):
        """_detect_code_type detects Component class."""
        code = "class MyComp(Component): pass"
        tree = ast.parse(code)
        detected_type, name = _detect_code_type(tree)

        assert detected_type == "class"
        assert name == "MyComp"

    def test_ignores_non_component_class(self):
        """_detect_code_type ignores non-Component classes."""
        code = """
class Helper:
    pass

def my_func():
    pass
"""
        tree = ast.parse(code)
        detected_type, name = _detect_code_type(tree)

        # Should detect the function, not the non-Component class
        assert detected_type == "function"
        assert name == "my_func"

    def test_returns_first_function(self):
        """_detect_code_type returns the first function when multiple exist."""
        code = """
def first():
    pass

def second():
    pass
"""
        tree = ast.parse(code)
        detected_type, name = _detect_code_type(tree)

        assert detected_type == "function"
        assert name == "first"

    def test_returns_unknown_for_empty(self):
        """_detect_code_type returns unknown for empty module."""
        code = ""
        tree = ast.parse(code)
        detected_type, name = _detect_code_type(tree)

        assert detected_type == "unknown"
        assert name is None
