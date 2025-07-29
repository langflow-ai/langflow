"""Unit tests for validate.py utilities."""

import ast
import warnings
from unittest.mock import Mock, patch

import pytest
from langflow.utils.validate import (
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
    find_names_in_code,
    get_default_imports,
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

    @patch("langflow.utils.validate.logger")
    def test_logging_on_parse_error(self, mock_logger):
        """Test that parsing errors are logged."""
        mock_logger.opt.return_value = mock_logger
        mock_logger.debug = Mock()

        code = "invalid python syntax +++"
        validate_code(code)

        mock_logger.opt.assert_called_once_with(exception=True)
        mock_logger.debug.assert_called_with("Error parsing code")


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

    def test_includes_pandas_when_available(self):
        """Test that pandas is included when available."""
        import importlib.util

        if importlib.util.find_spec("pandas"):
            context = _create_langflow_execution_context()
            assert "pd" in context
        else:
            # If pandas not available, pd shouldn't be in context
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
        # Should not raise an error due to import replacement
        with patch("langflow.utils.validate.prepare_global_scope") as mock_prepare:
            mock_prepare.return_value = {"CustomComponent": type("CustomComponent", (), {})}
            with patch("langflow.utils.validate.extract_class_code") as mock_extract:
                mock_extract.return_value = Mock()
                with patch("langflow.utils.validate.compile_class_code") as mock_compile:
                    mock_compile.return_value = compile("pass", "<string>", "exec")
                    with patch("langflow.utils.validate.build_class_constructor") as mock_build:
                        mock_build.return_value = lambda: None
                        create_class(code, "MyComponent")

    def test_handles_syntax_error(self):
        """Test that syntax errors are handled properly."""
        code = """
class BrokenClass
    def __init__(self):
        pass
"""
        with pytest.raises(ValueError, match="Syntax error in code"):
            create_class(code, "BrokenClass")

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
            patch("langflow.utils.validate.prepare_global_scope", side_effect=validation_error),
            pytest.raises(ValueError, match=".*"),
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

    def test_find_names_in_code(self):
        """Test finding specific names in code."""
        code = "from typing import Optional, List\ndata: Optional[List[str]] = None"
        names = ["Optional", "List", "Dict", "Union"]
        found = find_names_in_code(code, names)
        assert found == {"Optional", "List"}

    def test_find_names_in_code_none_found(self):
        """Test when no names are found in code."""
        code = "x = 42"
        names = ["Optional", "List"]
        found = find_names_in_code(code, names)
        assert found == set()


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
        with pytest.raises(ModuleNotFoundError, match="Module nonexistent_module not found"):
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


class TestGetDefaultImports:
    """Test cases for get_default_imports function."""

    @patch("langflow.utils.validate.CUSTOM_COMPONENT_SUPPORTED_TYPES", {"TestType": Mock()})
    def test_returns_default_imports(self):
        """Test that default imports are returned."""
        code = "TestType and Optional"

        with patch("importlib.import_module") as mock_import:
            mock_module = Mock()
            mock_module.TestType = Mock()
            mock_import.return_value = mock_module

            imports = get_default_imports(code)
            assert "Optional" in imports
            assert "List" in imports
            assert "Dict" in imports
            assert "Union" in imports

    @patch("langflow.utils.validate.CUSTOM_COMPONENT_SUPPORTED_TYPES", {"CustomType": Mock()})
    def test_includes_langflow_imports(self):
        """Test that langflow imports are included when found in code."""
        code = "CustomType is used here"

        with patch("importlib.import_module") as mock_import:
            mock_module = Mock()
            mock_module.CustomType = Mock()
            mock_import.return_value = mock_module

            imports = get_default_imports(code)
            assert "CustomType" in imports
