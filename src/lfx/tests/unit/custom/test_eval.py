"""Tests for eval_custom_component_code - handling both class and function components."""

from __future__ import annotations

import pytest
from lfx.base.functions import FunctionComponent
from lfx.custom.eval import (
    _create_function_component_class,
    _has_component_decorator,
    _is_function_code,
    eval_custom_component_code,
)


class TestIsFunctionCode:
    """Tests for _is_function_code detection."""

    def test_simple_function_is_detected(self):
        """Simple function definition is detected as function code."""
        code = """
def my_func(text: str) -> str:
    return text.upper()
"""
        assert _is_function_code(code) is True

    def test_async_function_is_detected(self):
        """Async function definition is detected as function code."""
        code = """
async def my_async_func(text: str) -> str:
    return text.upper()
"""
        assert _is_function_code(code) is True

    def test_function_with_decorator_is_detected(self):
        """Function with @component decorator is detected as function code."""
        code = """
from lfx.base.functions import component

@component
def my_func(text: str) -> str:
    return text.upper()
"""
        assert _is_function_code(code) is True

    def test_component_class_is_not_function_code(self):
        """Component class is not detected as function code."""
        code = """
from lfx.custom.custom_component.component import Component

class MyComponent(Component):
    def process(self) -> str:
        return "hello"
"""
        assert _is_function_code(code) is False

    def test_lc_component_class_is_not_function_code(self):
        """LC-prefixed Component class is not detected as function code."""
        code = """
from lfx.base import LCModelComponent

class MyModel(LCModelComponent):
    def process(self) -> str:
        return "hello"
"""
        assert _is_function_code(code) is False

    def test_invalid_syntax_returns_false(self):
        """Invalid Python syntax returns False."""
        code = "def broken("
        assert _is_function_code(code) is False

    def test_empty_code_returns_false(self):
        """Empty code returns False."""
        code = ""
        assert _is_function_code(code) is False

    def test_only_imports_returns_false(self):
        """Code with only imports (no function) returns False."""
        code = """
import os
from typing import List
"""
        assert _is_function_code(code) is False

    def test_indented_function_is_detected(self):
        """Indented function (as from serialization) is detected."""
        code = """
    def my_func(text: str) -> str:
        return text.upper()
"""
        assert _is_function_code(code) is True


class TestCreateFunctionComponentClass:
    """Tests for _create_function_component_class."""

    def test_creates_wrapper_class(self):
        """Creates a FunctionComponent wrapper class."""
        code = """
def my_func(text: str) -> str:
    return text.upper()
"""
        cls = _create_function_component_class(code)
        assert "FunctionComponent_my_func" in cls.__name__

    def test_wrapper_creates_function_component_instance(self):
        """Wrapper class creates FunctionComponent instances."""
        code = """
def my_func(text: str) -> str:
    return text.upper()
"""
        cls = _create_function_component_class(code)
        instance = cls()
        assert isinstance(instance, FunctionComponent)

    def test_wrapper_has_correct_inputs(self):
        """Wrapper instance has inputs from function signature."""
        code = """
def process(text: str, count: int = 5) -> str:
    return text * count
"""
        cls = _create_function_component_class(code)
        instance = cls()
        assert len(instance.inputs) == 2
        assert instance.inputs[0].name == "text"
        assert instance.inputs[1].name == "count"

    def test_wrapper_has_output(self):
        """Wrapper instance has output."""
        code = """
def my_func(text: str) -> str:
    return text.upper()
"""
        cls = _create_function_component_class(code)
        instance = cls()
        assert len(instance.outputs) == 1
        assert instance.outputs[0].name == "result"

    def test_raises_on_no_function(self):
        """Raises ValueError when no function found."""
        code = """
x = 5
y = 10
"""
        with pytest.raises(ValueError, match="No function found"):
            _create_function_component_class(code)

    def test_raises_on_multiple_functions_no_decorator(self):
        """Raises ValueError when multiple functions exist and none is decorated."""
        code = """
def first_func(a: int) -> int:
    return a

def second_func(b: str) -> str:
    return b
"""
        with pytest.raises(ValueError, match="Multiple functions found"):
            _create_function_component_class(code)

    def test_picks_decorated_function_among_multiple(self):
        """Picks the decorated function when multiple functions exist."""
        code = """
from lfx.base.functions import component

def helper(x: int) -> int:
    return x * 2

@component
def main_func(text: str) -> str:
    return text.upper()
"""
        cls = _create_function_component_class(code)
        instance = cls()
        # Should have picked main_func which has text param
        assert instance.inputs[0].name == "text"
        assert "main_func" in cls.__name__

    def test_raises_on_multiple_decorated_functions(self):
        """Raises ValueError when multiple functions have @component."""
        code = """
from lfx.base.functions import component

@component
def first_func(a: int) -> int:
    return a

@component
def second_func(b: str) -> str:
    return b
"""
        with pytest.raises(ValueError, match="Multiple functions with @component"):
            _create_function_component_class(code)

    def test_single_function_implicit_component(self):
        """Single function is used implicitly without decorator."""
        code = """
def only_func(value: str) -> str:
    return value.lower()
"""
        cls = _create_function_component_class(code)
        instance = cls()
        assert instance.inputs[0].name == "value"
        assert "only_func" in cls.__name__

    def test_decorated_function_with_args(self):
        """Picks function with @component(display_name=...) decorator."""
        code = """
from lfx.base.functions import component

def helper(x: int) -> int:
    return x

@component(display_name="Custom Name")
def main_func(text: str) -> str:
    return text
"""
        cls = _create_function_component_class(code)
        assert "main_func" in cls.__name__


class TestEvalCustomComponentCode:
    """Tests for eval_custom_component_code entry point."""

    def test_pure_function_creates_function_component(self):
        """Pure function code creates FunctionComponent."""
        code = """
def my_func(text: str) -> str:
    return text.upper()
"""
        cls = eval_custom_component_code(code)
        instance = cls()
        assert isinstance(instance, FunctionComponent)

    def test_decorated_function_creates_function_component(self):
        """Function with @component creates FunctionComponent."""
        code = """
from lfx.base.functions import component

@component
def my_func(text: str) -> str:
    return text.upper()
"""
        cls = eval_custom_component_code(code)
        instance = cls()
        assert isinstance(instance, FunctionComponent)

    def test_component_class_creates_class_component(self):
        """Component class code creates class-based component."""
        code = """
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.template.field.base import Output

class MyComponent(Component):
    inputs = [MessageTextInput(name="text", display_name="Text")]
    outputs = [Output(display_name="Result", name="result", method="process")]

    def process(self) -> str:
        return self.text
"""
        cls = eval_custom_component_code(code)
        assert cls.__name__ == "MyComponent"
        instance = cls()
        assert not isinstance(instance, FunctionComponent)

    @pytest.mark.asyncio
    async def test_function_component_can_execute(self):
        """FunctionComponent from eval can execute."""
        code = """
def double(text: str) -> str:
    return text * 2
"""
        cls = eval_custom_component_code(code)
        instance = cls()
        instance.set(text="hello")
        result = await instance.invoke_function()
        assert result == "hellohello"

    @pytest.mark.asyncio
    async def test_async_function_component_can_execute(self):
        """Async FunctionComponent from eval can execute."""
        code = """
async def async_upper(text: str) -> str:
    return text.upper()
"""
        cls = eval_custom_component_code(code)
        instance = cls()
        instance.set(text="hello")
        result = await instance.invoke_function()
        assert result == "HELLO"


class TestEvalRoundTrip:
    """Tests for serialization round-trip through eval."""

    def test_function_component_round_trip(self):
        """FunctionComponent can be serialized and recreated via eval."""
        from lfx.base.functions import component

        @component
        def my_func(text: str) -> str:
            return text.upper()

        # Get the stored code
        my_func.set_class_code()
        stored_code = my_func._code

        # Recreate via eval
        cls = eval_custom_component_code(stored_code)
        instance = cls()

        # Should have same structure
        assert len(instance.inputs) == len(my_func.inputs)
        assert instance.inputs[0].name == my_func.inputs[0].name

    def test_multiple_param_function_round_trip(self):
        """Function with multiple params round-trips correctly."""
        from lfx.base.functions import component

        @component
        def format_text(prefix: str, text: str, suffix: str = "!") -> str:
            return f"{prefix}{text}{suffix}"

        format_text.set_class_code()
        stored_code = format_text._code

        cls = eval_custom_component_code(stored_code)
        instance = cls()

        assert len(instance.inputs) == 3
        param_names = [inp.name for inp in instance.inputs]
        assert "prefix" in param_names
        assert "text" in param_names
        assert "suffix" in param_names


class TestHasComponentDecorator:
    """Tests for _has_component_decorator helper."""

    def test_simple_decorator(self):
        """Detects @component decorator."""
        import ast

        code = """
@component
def my_func(x: str) -> str:
    return x
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        assert _has_component_decorator(func_node) is True

    def test_decorator_with_args(self):
        """Detects @component(display_name='test') decorator."""
        import ast

        code = """
@component(display_name="test")
def my_func(x: str) -> str:
    return x
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        assert _has_component_decorator(func_node) is True

    def test_no_decorator(self):
        """Returns False for function without decorator."""
        import ast

        code = """
def my_func(x: str) -> str:
    return x
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        assert _has_component_decorator(func_node) is False

    def test_other_decorator(self):
        """Returns False for function with non-component decorator."""
        import ast

        code = """
@staticmethod
def my_func(x: str) -> str:
    return x
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        assert _has_component_decorator(func_node) is False

    def test_module_qualified_decorator(self):
        """Detects lfx.base.functions.component decorator."""
        import ast

        code = """
@lfx.base.functions.component
def my_func(x: str) -> str:
    return x
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        assert _has_component_decorator(func_node) is True
