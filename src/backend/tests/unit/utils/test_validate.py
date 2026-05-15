"""Unit tests for validate.py utilities."""

import ast
import warnings
from unittest.mock import Mock, patch

import pytest
from lfx.custom.validate import (
    _create_langflow_execution_context,
    add_type_ignores,
    build_class_constructor,
    compile_class_code,
    create_class,
    create_function,
    create_type_ignore_class,
    eval_function,
    execute_function,
    extract_class_code,
    extract_class_name,
    extract_function_name,
    prepare_global_scope,
    validate_code,
)


class TestAddTypeIgnores:
    """Test cases for add_type_ignores function."""

    def test_adds_type_ignore_when_missing(self):
        """Test that TypeIgnore is added when not present."""
        # Remove TypeIgnore if it exists
        if hasattr(ast, "TypeIgnore"):
            delattr(ast, "TypeIgnore")

        add_type_ignores()

        assert hasattr(ast, "TypeIgnore")
        assert issubclass(ast.TypeIgnore, ast.AST)
        assert ast.TypeIgnore._fields == ()

    def test_does_nothing_when_already_exists(self):
        """Test that function doesn't modify existing TypeIgnore."""
        # Ensure TypeIgnore exists first
        add_type_ignores()
        original_type_ignore = ast.TypeIgnore

        add_type_ignores()

        assert ast.TypeIgnore is original_type_ignore


class TestValidateCode:
    """Test cases for validate_code function."""

    def test_valid_code_with_function(self):
        """Test validation passes for valid code with function."""
        code = """
def hello_world():
    return "Hello, World!"
"""
        result = validate_code(code)
        assert result["imports"]["errors"] == []
        assert result["function"]["errors"] == []

    def test_code_with_valid_imports(self):
        """Test validation passes for code with valid imports."""
        code = """
import os
import sys

def get_path():
    return os.path.join(sys.path[0], "test")
"""
        result = validate_code(code)
        assert result["imports"]["errors"] == []
        assert result["function"]["errors"] == []

    def test_code_with_invalid_imports(self):
        """Test validation fails for code with invalid imports."""
        code = """
import nonexistent_module

def test_func():
    return nonexistent_module.some_function()
"""
        result = validate_code(code)
        assert len(result["imports"]["errors"]) == 1
        assert "nonexistent_module" in result["imports"]["errors"][0]

    def test_code_with_syntax_error(self):
        """Test validation fails for code with syntax errors."""
        code = """
def broken_function(
    return "incomplete"
"""
        result = validate_code(code)
        # The function should catch the syntax error and return it in the results
        assert len(result["function"]["errors"]) >= 1
        error_message = " ".join(result["function"]["errors"])
        assert (
            "SyntaxError" in error_message or "invalid syntax" in error_message or "was never closed" in error_message
        )

    def test_code_with_function_execution_error(self):
        """Test validation fails when function execution fails."""
        code = """
def error_function():
    undefined_variable + 1
"""
        result = validate_code(code)
        # This should pass parsing but may fail execution
        assert result["imports"]["errors"] == []

    def test_empty_code(self):
        """Test validation handles empty code."""
        result = validate_code("")
        assert result["imports"]["errors"] == []
        assert result["function"]["errors"] == []

    def test_code_with_multiple_imports(self):
        """Test validation handles multiple imports."""
        code = """
import os
import sys
import json
import nonexistent1
import nonexistent2

def test_func():
    return json.dumps({"path": os.getcwd()})
"""
        result = validate_code(code)
        assert len(result["imports"]["errors"]) == 2
        assert any("nonexistent1" in err for err in result["imports"]["errors"])
        assert any("nonexistent2" in err for err in result["imports"]["errors"])

    @patch("lfx.custom.validate.logger")
    def test_logging_on_parse_error(self, mock_logger):
        """Test that parsing errors are logged."""
        # Structlog doesn't have opt method, so hasattr(logger, "opt") returns False
        mock_logger.debug = Mock()

        code = "invalid python syntax +++"
        validate_code(code)

        # With structlog, we expect logger.debug to be called with exc_info=True
        mock_logger.debug.assert_called_with("Error parsing code", exc_info=True)


class TestCreateLangflowExecutionContext:
    """Test cases for _create_langflow_execution_context function."""

    def test_creates_context_with_langflow_imports(self):
        """Test that context includes langflow imports."""
        # The function imports modules inside try/except blocks
        # We don't need to patch anything, just test it works
        context = _create_langflow_execution_context()

        # Check that the context contains the expected keys
        # The actual imports may succeed or fail, but the function should handle both cases
        assert isinstance(context, dict)
        # These keys should be present regardless of import success/failure
        expected_keys = ["DataFrame", "Message", "Data", "Component", "HandleInput", "Output", "TabInput"]
        for key in expected_keys:
            assert key in context, f"Expected key '{key}' not found in context"

    def test_creates_mock_classes_on_import_failure(self):
        """Test that mock classes are created when imports fail."""
        # Test that the function handles import failures gracefully
        # by checking the actual implementation behavior
        with patch("builtins.__import__", side_effect=ImportError("Module not found")):
            context = _create_langflow_execution_context()

            # Even with import failures, the context should still be created
            assert isinstance(context, dict)
            # The function should create mock classes when imports fail
            if "DataFrame" in context:
                assert isinstance(context["DataFrame"], type)

    def test_includes_typing_imports(self):
        """Test that typing imports are included."""
        context = _create_langflow_execution_context()

        assert "Any" in context
        assert "Dict" in context
        assert "List" in context
        assert "Optional" in context
        assert "Union" in context

    def test_does_not_include_pandas(self):
        """Test that pandas is not included in the langflow execution context."""
        context = _create_langflow_execution_context()
        assert "pd" not in context


class TestEvalFunction:
    """Test cases for eval_function function."""

    def test_evaluates_simple_function(self):
        """Test evaluation of a simple function."""
        function_string = """
def add_numbers(a, b):
    return a + b
"""
        func = eval_function(function_string)
        assert callable(func)
        assert func(2, 3) == 5

    def test_evaluates_function_with_default_args(self):
        """Test evaluation of function with default arguments."""
        function_string = """
def greet(name="World"):
    return f"Hello, {name}!"
"""
        func = eval_function(function_string)
        assert func() == "Hello, World!"
        assert func("Alice") == "Hello, Alice!"

    def test_raises_error_for_no_function(self):
        """Test that error is raised when no function is found."""
        code_string = """
x = 42
y = "hello"
"""
        with pytest.raises(ValueError, match="Function string does not contain a function"):
            eval_function(code_string)

    def test_finds_correct_function_among_multiple(self):
        """Test that the correct function is found when multiple exist."""
        function_string = """
def helper():
    return "helper"

def main_function():
    return "main"
"""
        func = eval_function(function_string)
        # Should return one of the functions (implementation detail)
        assert callable(func)


class TestExecuteFunction:
    """Test cases for execute_function function."""

    def test_executes_function_with_args(self):
        """Test execution of function with arguments."""
        code = """
def multiply(x, y):
    return x * y
"""
        result = execute_function(code, "multiply", 4, 5)
        assert result == 20

    def test_executes_function_with_kwargs(self):
        """Test execution of function with keyword arguments."""
        code = """
def create_message(text, urgent=False):
    prefix = "URGENT: " if urgent else ""
    return prefix + text
"""
        result = execute_function(code, "create_message", "Hello", urgent=True)
        assert result == "URGENT: Hello"

    def test_executes_function_with_imports(self):
        """Test execution of function that uses imports."""
        code = """
import os

def get_current_dir():
    return os.getcwd()
"""
        result = execute_function(code, "get_current_dir")
        assert isinstance(result, str)

    def test_raises_error_for_missing_module(self):
        """Test that error is raised for missing modules."""
        code = """
import nonexistent_module

def test_func():
    return nonexistent_module.test()
"""
        with pytest.raises(ModuleNotFoundError, match="Module nonexistent_module not found"):
            execute_function(code, "test_func")

    def test_raises_error_for_missing_function(self):
        """Test that error is raised when function doesn't exist."""
        code = """
def existing_function():
    return "exists"
"""
        # The function should raise an error when the specified function doesn't exist
        with pytest.raises((ValueError, StopIteration)):
            execute_function(code, "nonexistent_function")


class TestCreateFunction:
    """Test cases for create_function function."""

    def test_creates_callable_function(self):
        """Test that a callable function is created."""
        code = """
def square(x):
    return x ** 2
"""
        func = create_function(code, "square")
        assert callable(func)
        assert func(5) == 25

    def test_handles_imports_in_function(self):
        """Test that imports within function are handled."""
        code = """
import math

def calculate_area(radius):
    return math.pi * radius ** 2
"""
        func = create_function(code, "calculate_area")
        result = func(2)
        assert abs(result - 12.566370614359172) < 0.0001

    def test_handles_from_imports(self):
        """Test that from imports are handled correctly."""
        code = """
from math import sqrt

def hypotenuse(a, b):
    return sqrt(a**2 + b**2)
"""
        func = create_function(code, "hypotenuse")
        assert func(3, 4) == 5.0

    def test_raises_error_for_missing_module(self):
        """Test that error is raised for missing modules."""
        code = """
import nonexistent_module

def test_func():
    return "test"
"""
        with pytest.raises(ModuleNotFoundError, match="Module nonexistent_module not found"):
            create_function(code, "test_func")


class TestCreateClass:
    """Test cases for create_class function."""

    def test_creates_simple_class(self):
        """Test creation of a simple class."""
        code = """
class TestClass:
    def __init__(self, value=None):
        self.value = value

    def get_value(self):
        return self.value
"""
        cls = create_class(code, "TestClass")
        instance = cls()
        assert hasattr(instance, "__init__")
        assert hasattr(instance, "get_value")

    def test_handles_class_with_imports(self):
        """Test creation of class that uses imports."""
        code = """
import json

class JsonHandler:
    def __init__(self):
        self.data = {}

    def to_json(self):
        return json.dumps(self.data)
"""
        cls = create_class(code, "JsonHandler")
        instance = cls()
        assert hasattr(instance, "to_json")

    def test_replaces_legacy_imports(self):
        """Test that legacy import statements are replaced."""
        code = """
from langflow import CustomComponent

class MyComponent(CustomComponent):
    def build(self):
        return "test"
"""
        # Capture what code prepare_global_scope receives so we can assert the rewrite happened.
        # Return a dict with both CustomComponent (the rewritten symbol) and MyComponent
        # (so create_class's exec_globals[class_name] lookup succeeds).
        seen_modules = []

        def fake_prepare(module):
            seen_modules.append(ast.unparse(module))
            return {
                "CustomComponent": type("CustomComponent", (), {}),
                "MyComponent": type("MyComponent", (), {}),
            }

        with patch("lfx.custom.validate.prepare_global_scope", side_effect=fake_prepare):
            create_class(code, "MyComponent")

        assert seen_modules, "prepare_global_scope was not called"
        assert "from langflow.custom import CustomComponent" in seen_modules[0]
        assert "from langflow import CustomComponent" not in seen_modules[0]

    def test_handles_syntax_error(self):
        """Test that syntax errors are handled properly."""
        code = """
class BrokenClass
    def __init__(self):
        pass
"""
        with pytest.raises(ValueError, match="Syntax error in code"):
            create_class(code, "BrokenClass")

    def test_name_error_hints_at_legacy_lfx_import(self):
        """Surface a hint for names previously auto-injected by DEFAULT_IMPORT_STRING.

        Components that lean on the removed preamble get an actionable hint
        pointing at the missing lfx import.
        """
        code = """
class Broken:
    inputs = [StrInput(name="x")]
"""
        with pytest.raises(ValueError, match=r"add `from lfx\.io import StrInput`"):
            create_class(code, "Broken")

    def test_name_error_without_legacy_match_omits_hint(self):
        """Unknown names get the plain message — no misleading hint."""
        code = """
class Broken:
    x = some_random_undefined_name
"""
        with pytest.raises(ValueError, match="some_random_undefined_name") as exc_info:
            create_class(code, "Broken")
        assert "Add `from " not in str(exc_info.value)

    def test_name_error_hints_at_langchain_import(self):
        """Names dropped from the langchain half of DEFAULT_IMPORT_STRING also surface a hint.

        ``Tool``, ``BaseLanguageModel`` etc. were injected via the langchain
        preamble. We now resolve them lazily from ``lfx.field_typing.names``
        so users with components that leaned on the auto-import get an
        actionable message instead of a bare NameError.
        """
        code = """
class Broken:
    tool: Tool = None
"""
        with pytest.raises(ValueError, match=r"add `from langchain_core\.tools import Tool`"):
            create_class(code, "Broken")

    def test_handles_validation_error(self):
        """Test that validation errors are handled properly."""
        code = """
class TestClass:
    def __init__(self):
        pass
"""
        # Create a proper ValidationError instance
        from pydantic_core import ValidationError as CoreValidationError

        validation_error = CoreValidationError.from_exception_data("TestClass", [])

        with (
            patch("lfx.custom.validate.prepare_global_scope", side_effect=validation_error),
            pytest.raises(ValueError, match=r".*"),
        ):
            create_class(code, "TestClass")


class TestHelperFunctions:
    """Test cases for helper functions."""

    def test_create_type_ignore_class(self):
        """Test creation of TypeIgnore class."""
        type_ignore_class = create_type_ignore_class()
        assert issubclass(type_ignore_class, ast.AST)
        assert type_ignore_class._fields == ()

    def test_extract_function_name(self):
        """Test extraction of function name from code."""
        code = """
def my_function():
    return "test"
"""
        name = extract_function_name(code)
        assert name == "my_function"

    def test_extract_function_name_no_function(self):
        """Test error when no function found."""
        code = "x = 42"
        with pytest.raises(ValueError, match="No function definition found"):
            extract_function_name(code)

    def test_extract_class_name(self):
        """Test extraction of Component class name."""
        code = """
class MyComponent(Component):
    def build(self):
        pass
"""
        name = extract_class_name(code)
        assert name == "MyComponent"

    def test_extract_class_name_no_component(self):
        """Test error when no Component subclass found."""
        code = """
class RegularClass:
    pass
"""
        with pytest.raises(TypeError, match="No Component subclass found"):
            extract_class_name(code)

    def test_extract_class_name_syntax_error(self):
        """Test error handling for syntax errors in extract_class_name."""
        code = "class BrokenClass"
        with pytest.raises(ValueError, match="Invalid Python code"):
            extract_class_name(code)


class TestPrepareGlobalScope:
    """Test cases for prepare_global_scope function."""

    def test_handles_imports(self):
        """Test that imports are properly handled."""
        code = """
import os
import sys

def test():
    pass
"""
        module = ast.parse(code)
        scope = prepare_global_scope(module)
        assert "os" in scope
        assert "sys" in scope

    def test_handles_from_imports(self):
        """Test that from imports are properly handled."""
        code = """
from os import path
from sys import version

def test():
    pass
"""
        module = ast.parse(code)
        scope = prepare_global_scope(module)
        assert "path" in scope
        assert "version" in scope

    def test_handles_import_errors(self):
        """Test that import errors are properly raised."""
        code = """
import nonexistent_module

def test():
    pass
"""
        module = ast.parse(code)
        with pytest.raises(ModuleNotFoundError, match="No module named 'nonexistent_module'"):
            prepare_global_scope(module)

    def test_handles_langchain_warnings(self):
        """Test that langchain warnings are suppressed."""
        code = """
from langchain_core.messages import BaseMessage

def test():
    pass
"""
        module = ast.parse(code)

        with patch("importlib.import_module") as mock_import:
            mock_module = Mock()
            mock_module.BaseMessage = Mock()
            mock_import.return_value = mock_module

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                prepare_global_scope(module)
                # Should not have langchain warnings
                langchain_warnings = [warning for warning in w if "langchain" in str(warning.message).lower()]
                assert len(langchain_warnings) == 0

    def test_executes_definitions(self):
        """Test that class and function definitions are executed."""
        code = """
def helper():
    return "helper"

class TestClass:
    value = 42
"""
        module = ast.parse(code)
        scope = prepare_global_scope(module)
        assert "helper" in scope
        assert "TestClass" in scope
        assert callable(scope["helper"])
        assert scope["TestClass"].value == 42

    def test_preserves_future_annotations_for_pep563_typing(self):
        """Preserve PEP 563 lazy-annotation semantics in the compiled module.

        Components use ``from __future__ import annotations`` plus type-only
        imports under ``TYPE_CHECKING:``. Without preserving __future__, the
        class body would NameError on TYPE_CHECKING-only symbols (e.g.
        AgentComponent with ``-> list[Tool]``).
        """
        code = """
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.tools import Tool


class Sample:
    async def get_tools(self) -> list[Tool]:
        return []
"""
        module = ast.parse(code)
        scope = prepare_global_scope(module)
        assert "Sample" in scope
        # Annotation must be the lazy string form, not the resolved object — which
        # would have NameError'd at class-body time without PEP 563.
        assert scope["Sample"]().get_tools.__annotations__["return"] == "list[Tool]"


class TestToolModeIntrospection:
    """End-to-end regression for the full tool-mode introspection path.

    Compile happens fine (PEP 563 keeps annotations as strings), but enabling
    tool mode on a component triggers ``_get_method_return_type("to_toolkit")``
    which calls ``get_type_hints`` and tries to *resolve* those strings back to
    class objects. The resolution needs ``Tool`` in scope. Components import
    ``Tool`` only under ``if TYPE_CHECKING:`` (per cold-start hygiene), so plain
    ``get_type_hints`` raises ``NameError``. ``get_runtime_type_hints`` injects
    the public ``lfx.field_typing`` names so the resolution succeeds.

    This test compiles a real ``Component`` subclass via ``eval_custom_component_code``
    — the same path the langflow API uses — and asserts ``_get_method_return_type``
    on a tool-mode-style method returns a non-empty list instead of NameError'ing.
    """

    def test_get_method_return_type_resolves_typecheck_only_tool_annotation(self):
        from lfx.custom.eval import eval_custom_component_code

        code = """
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.tools import Tool

from lfx.custom.custom_component.component import Component
from lfx.io import StrInput, Output


class ToolModeSample(Component):
    inputs = [StrInput(name="x")]
    outputs = [Output(name="out", method="build")]

    async def my_tool_method(self) -> list[Tool]:
        return []

    def build(self):
        return self.x
"""
        cls = eval_custom_component_code(code)
        instance = cls()

        # The bug surface: this call uses get_runtime_type_hints to resolve the
        # `-> list[Tool]` annotation. Plain get_type_hints would NameError because
        # ``Tool`` isn't in the exec_globals (only imported under TYPE_CHECKING).
        return_type = instance._get_method_return_type("my_tool_method")

        assert return_type, f"Expected non-empty return type, got {return_type!r}"
        assert "Tool" in return_type[0], f"Expected 'Tool' in {return_type!r}"


class TestClassCodeOperations:
    """Test cases for class code operation functions."""

    def test_extract_class_code(self):
        """Test extraction of class code from module."""
        code = """
def helper():
    pass

class MyClass:
    def method(self):
        pass
"""
        module = ast.parse(code)
        class_code = extract_class_code(module, "MyClass")
        assert isinstance(class_code, ast.ClassDef)
        assert class_code.name == "MyClass"

    def test_compile_class_code(self):
        """Test compilation of class code."""
        code = """
class TestClass:
    def method(self):
        return "test"
"""
        module = ast.parse(code)
        class_code = extract_class_code(module, "TestClass")
        compiled = compile_class_code(class_code)
        assert compiled is not None

    def test_build_class_constructor(self):
        """Test building class constructor."""
        code = """
class SimpleClass:
    def __init__(self):
        self.value = "test"
"""
        module = ast.parse(code)
        class_code = extract_class_code(module, "SimpleClass")
        compiled = compile_class_code(class_code)

        constructor = build_class_constructor(compiled, {}, "SimpleClass")
        assert constructor is not None
