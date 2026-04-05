"""Tests for component code validation.

Tests the _extract_class_name_regex, _safe_extract_class_name,
validate_component_code, and static validation helpers.
"""

import ast
import os
from unittest.mock import patch

from langflow.agentic.helpers.validation import (
    _extract_class_name_regex,
    _extract_io_names,
    _extract_output_methods,
    _safe_extract_class_name,
    validate_component_code,
)

MODULE = "langflow.agentic.helpers.validation"


def _parse(code: str) -> ast.Module:
    return ast.parse(code)


class TestExtractClassNameRegex:
    """Tests for regex-based class name extraction."""

    def test_should_extract_class_name_from_component_subclass(self):
        """Should extract 'MyComponent' from class MyComponent(Component)."""
        code = "class MyComponent(Component):\n    pass"
        assert _extract_class_name_regex(code) == "MyComponent"

    def test_should_return_none_when_no_component_class(self):
        """Should return None when code has no Component subclass."""
        code = "class Foo(Bar):\n    pass"
        assert _extract_class_name_regex(code) is None

    def test_should_extract_from_multi_parent_class(self):
        """Should extract name from class with multiple parents including Component."""
        code = "class MyComp(Component, Mixin):\n    pass"
        assert _extract_class_name_regex(code) == "MyComp"

    def test_should_extract_from_custom_component_subclass(self):
        """Should extract name from CustomComponent subclass."""
        code = "class Analyzer(CustomComponent):\n    pass"
        assert _extract_class_name_regex(code) == "Analyzer"

    def test_should_return_none_for_empty_code(self):
        """Should return None for empty string."""
        assert _extract_class_name_regex("") is None


class TestSafeExtractClassName:
    """Tests for safe class name extraction with fallback."""

    def test_should_use_ast_when_available(self):
        """Should use extract_class_name when it succeeds."""
        with patch(f"{MODULE}.extract_class_name", return_value="ASTName"):
            result = _safe_extract_class_name("class ASTName(Component): pass")
            assert result == "ASTName"

    def test_should_fallback_to_regex_on_syntax_error(self):
        """Should fallback to regex when extract_class_name raises SyntaxError."""
        code = "class Broken(Component):\n    pass"
        with patch(f"{MODULE}.extract_class_name", side_effect=SyntaxError("bad")):
            result = _safe_extract_class_name(code)
            assert result == "Broken"

    def test_should_fallback_to_regex_on_value_error(self):
        """Should fallback to regex when extract_class_name raises ValueError."""
        code = "class Fallback(Component):\n    pass"
        with patch(f"{MODULE}.extract_class_name", side_effect=ValueError("no class")):
            result = _safe_extract_class_name(code)
            assert result == "Fallback"

    def test_should_fallback_to_regex_on_type_error(self):
        """Should fallback to regex when extract_class_name raises TypeError."""
        code = "class TypeErr(Component):\n    pass"
        with patch(f"{MODULE}.extract_class_name", side_effect=TypeError("bad type")):
            result = _safe_extract_class_name(code)
            assert result == "TypeErr"


class TestExtractIONames:
    """Tests for static extraction of input/output names from AST."""

    def test_should_extract_input_and_output_names(self):
        """Should extract input and output names from well-formed component."""
        code = """
class MyComponent(Component):
    inputs = [
        StrInput(name="query", display_name="Query"),
        IntInput(name="count", display_name="Count"),
    ]
    outputs = [
        Output(name="result", display_name="Result", method="build"),
    ]
"""
        input_names, output_names = _extract_io_names(_parse(code), "MyComponent")
        assert input_names == {"query", "count"}
        assert output_names == {"result"}

    def test_should_return_empty_sets_when_no_io(self):
        """Should return empty sets when class has no inputs/outputs."""
        code = "class MyComponent(Component):\n    pass"
        input_names, output_names = _extract_io_names(_parse(code), "MyComponent")
        assert input_names == set()
        assert output_names == set()

    def test_should_detect_overlapping_names(self):
        """Should extract names that allow overlap detection."""
        code = """
class BadComponent(Component):
    inputs = [
        StrInput(name="data", display_name="Data"),
    ]
    outputs = [
        Output(name="data", display_name="Data", method="build"),
    ]
"""
        input_names, output_names = _extract_io_names(_parse(code), "BadComponent")
        assert input_names & output_names == {"data"}

    def test_should_return_empty_sets_when_class_not_found(self):
        """Should return empty sets when class_name doesn't match any class."""
        code = "class OtherComponent(Component):\n    pass"
        input_names, output_names = _extract_io_names(_parse(code), "NonExistent")
        assert input_names == set()
        assert output_names == set()

    def test_should_ignore_starred_elements_in_inputs(self):
        """Should gracefully skip *ParentClass.inputs unpacking."""
        code = """
class MyComponent(Component):
    inputs = [
        *SomeParent.inputs,
        StrInput(name="extra", display_name="Extra"),
    ]
    outputs = []
"""
        input_names, output_names = _extract_io_names(_parse(code), "MyComponent")
        assert input_names == {"extra"}
        assert output_names == set()


class TestExtractOutputMethods:
    """Tests for static extraction of output method names from AST."""

    def test_should_extract_method_names(self):
        """Should extract method names from Output definitions."""
        code = """
class MyComponent(Component):
    outputs = [
        Output(name="a", method="build_a"),
        Output(name="b", method="build_b"),
    ]
"""
        methods = _extract_output_methods(_parse(code), "MyComponent")
        assert methods == ["build_a", "build_b"]

    def test_should_return_empty_list_when_no_outputs(self):
        """Should return empty list when class has no outputs."""
        code = "class MyComponent(Component):\n    pass"
        methods = _extract_output_methods(_parse(code), "MyComponent")
        assert methods == []

    def test_should_return_empty_list_when_class_not_found(self):
        """Should return empty list when class_name doesn't match."""
        code = "class Other(Component):\n    pass"
        methods = _extract_output_methods(_parse(code), "NonExistent")
        assert methods == []


class TestValidateComponentCode:
    """Tests for full component code validation."""

    def test_should_not_execute_code_during_validation(self):
        """Validation must NOT execute arbitrary code — static analysis only.

        This is the primary security test: if validation calls exec() on the
        generated code, an attacker who can influence LLM output can achieve
        arbitrary server-side code execution.
        """
        env_key = "_LANGFLOW_SECURITY_VALIDATION_TEST"
        os.environ.pop(env_key, None)

        malicious_code = f"""
import os
os.environ["{env_key}"] = "EXPLOITED"

class MaliciousComponent(Component):
    display_name = "Malicious"
    description = "Test"

    inputs = []
    outputs = [
        Output(name="result", display_name="Result", method="build_result"),
    ]

    def build_result(self):
        return "test"
"""
        validate_component_code(malicious_code)

        assert os.environ.get(env_key) is None, (
            "validate_component_code executed arbitrary code! "
            "The os.environ assignment in the LLM-generated code was executed server-side."
        )

        os.environ.pop(env_key, None)

    def test_should_return_valid_for_well_formed_component(self):
        """Should return is_valid=True for syntactically correct component code."""
        code = """
class GoodComponent(Component):
    display_name = "Good"
    description = "A good component"

    inputs = [
        StrInput(name="query", display_name="Query"),
    ]
    outputs = [
        Output(name="result", display_name="Result", method="build_result"),
    ]

    def build_result(self):
        return self.query
"""
        result = validate_component_code(code)

        assert result.is_valid is True
        assert result.class_name == "GoodComponent"
        assert result.error is None

    def test_should_return_invalid_on_syntax_error(self):
        """Should return is_valid=False for code with syntax errors."""
        code = "class BadComp(Component):\n    def broken(self\n"
        result = validate_component_code(code)

        assert result.is_valid is False
        assert "SyntaxError" in result.error

    def test_should_return_invalid_when_output_method_has_no_return(self):
        """Should detect output methods that don't return a value."""
        code = """
class NoReturnComponent(Component):
    display_name = "NoReturn"

    inputs = []
    outputs = [
        Output(name="result", display_name="Result", method="build_result"),
    ]

    def build_result(self):
        pass
"""
        result = validate_component_code(code)

        assert result.is_valid is False
        assert "build_result" in result.error
        assert "return" in result.error.lower()

    def test_should_return_invalid_when_overlapping_io_names(self):
        """Should detect overlapping input/output names."""
        code = """
class OverlapComponent(Component):
    display_name = "Overlap"

    inputs = [
        StrInput(name="data", display_name="Data"),
    ]
    outputs = [
        Output(name="data", display_name="Data", method="build_data"),
    ]

    def build_data(self):
        return self.data
"""
        result = validate_component_code(code)

        assert result.is_valid is False
        assert "data" in result.error.lower()

    def test_should_return_invalid_when_no_class_name(self):
        """Should return is_valid=False when class name cannot be extracted."""
        with patch(f"{MODULE}._safe_extract_class_name", return_value=None):
            result = validate_component_code("x = 1")

            assert result.is_valid is False
            assert result.class_name is None
            assert "Could not extract class name" in result.error

    def test_should_preserve_code_in_result(self):
        """Result should contain the original code."""
        code = "class Comp(Component):\n    pass"
        result = validate_component_code(code)
        assert result.code == code

    def test_should_handle_component_with_no_outputs(self):
        """Should return valid for component with inputs but no outputs."""
        code = """
class InputOnlyComponent(Component):
    display_name = "InputOnly"

    inputs = [
        StrInput(name="query", display_name="Query"),
    ]
    outputs = []

    def run(self):
        pass
"""
        result = validate_component_code(code)
        assert result.is_valid is True
