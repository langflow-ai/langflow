"""Tests for component code validation."""

from langflow.agentic.helpers.validation import (
    _extract_class_name_regex,
    _safe_extract_class_name,
    validate_component_code,
)

VALID_COMPONENT_CODE = """from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message


class HelloWorldComponent(Component):
    display_name = "Hello World"
    description = "A simple hello world component."

    inputs = [
        MessageTextInput(name="input_value", display_name="Input"),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="process"),
    ]

    def process(self) -> Message:
        return Message(text=f"Hello, {self.input_value}!")
"""

INVALID_SYNTAX_CODE = """from langflow.custom import Component

class BrokenComponent(Component)
    display_name = "Broken"
"""

INCOMPLETE_CODE = """from langflow.custom import Component
from langflow.io import MessageTextInput, Output


class IncompleteComponent(Component):
    display_name = "Incomplete"

    inputs = [
        MessageTextInput(name="input_value", display_name="Input"),
"""

NON_COMPONENT_CODE = """def hello():
    return "hello"
"""

CODE_WITHOUT_IMPORTS = """class BrokenComponent(Component):
    display_name = "Broken"
"""


class TestValidateComponentCode:
    """Tests for validate_component_code function."""

    def test_should_validate_correct_component(self):
        result = validate_component_code(VALID_COMPONENT_CODE)

        assert result.is_valid is True
        assert result.class_name == "HelloWorldComponent"
        assert result.error is None
        assert result.code == VALID_COMPONENT_CODE

    def test_should_fail_for_syntax_error(self):
        result = validate_component_code(INVALID_SYNTAX_CODE)

        assert result.is_valid is False
        assert result.error is not None
        assert "BrokenComponent" in (result.class_name or "")

    def test_should_fail_for_incomplete_code(self):
        result = validate_component_code(INCOMPLETE_CODE)

        assert result.is_valid is False
        assert result.error is not None

    def test_should_fail_for_non_component_code(self):
        result = validate_component_code(NON_COMPONENT_CODE)

        assert result.is_valid is False
        assert result.error is not None

    def test_should_fail_for_empty_code(self):
        result = validate_component_code("")

        assert result.is_valid is False
        assert result.error is not None

    def test_should_fail_for_missing_imports(self):
        result = validate_component_code(CODE_WITHOUT_IMPORTS)

        assert result.is_valid is False
        assert result.error is not None

    def test_should_include_error_type_in_error_message(self):
        result = validate_component_code(INVALID_SYNTAX_CODE)

        assert result.is_valid is False
        # Error should contain the error type (e.g., "SyntaxError:")
        assert "Error" in result.error or "error" in result.error.lower()

    def test_should_handle_whitespace_only_code(self):
        result = validate_component_code("   \n\t\n  ")

        assert result.is_valid is False
        assert result.error is not None


class TestExtractClassNameRegex:
    """Tests for _extract_class_name_regex helper function."""

    def test_should_extract_class_name_from_component(self):
        code = "class MyComponent(Component):\n    pass"

        result = _extract_class_name_regex(code)

        assert result == "MyComponent"

    def test_should_extract_class_name_with_custom_base(self):
        code = "class MyCustom(CustomComponent):\n    pass"

        result = _extract_class_name_regex(code)

        assert result == "MyCustom"

    def test_should_extract_class_name_with_multiple_inheritance(self):
        code = "class MyComponent(Component, Mixin):\n    pass"

        result = _extract_class_name_regex(code)

        assert result == "MyComponent"

    def test_should_return_none_for_non_component_class(self):
        code = "class RegularClass:\n    pass"

        result = _extract_class_name_regex(code)

        assert result is None

    def test_should_return_none_for_no_class(self):
        code = "def function(): pass"

        result = _extract_class_name_regex(code)

        assert result is None

    def test_should_handle_class_with_spaces(self):
        code = "class   MyComponent   (   Component   ):\n    pass"

        result = _extract_class_name_regex(code)

        assert result == "MyComponent"


class TestSafeExtractClassName:
    """Tests for _safe_extract_class_name helper function."""

    def test_should_extract_from_valid_code(self):
        result = _safe_extract_class_name(VALID_COMPONENT_CODE)

        assert result == "HelloWorldComponent"

    def test_should_fallback_to_regex_for_syntax_error(self):
        result = _safe_extract_class_name(INVALID_SYNTAX_CODE)

        assert result == "BrokenComponent"

    def test_should_return_none_for_no_class(self):
        result = _safe_extract_class_name("print('hello')")

        assert result is None

    def test_should_handle_empty_code(self):
        result = _safe_extract_class_name("")

        assert result is None


class TestValidationResultSchema:
    """Tests for ValidationResult schema."""

    def test_should_have_correct_fields_on_success(self):
        result = validate_component_code(VALID_COMPONENT_CODE)

        assert hasattr(result, "is_valid")
        assert hasattr(result, "code")
        assert hasattr(result, "error")
        assert hasattr(result, "class_name")

    def test_should_have_correct_fields_on_failure(self):
        result = validate_component_code(INVALID_SYNTAX_CODE)

        assert hasattr(result, "is_valid")
        assert hasattr(result, "code")
        assert hasattr(result, "error")
        assert hasattr(result, "class_name")


class TestEdgeCases:
    """Edge case tests for validation."""

    def test_should_handle_component_with_unicode_names(self):
        code = """from langflow.custom import Component

class UnicodeComponent(Component):
    display_name = "Componente Português"
    description = "中文描述"
"""
        result = validate_component_code(code)

        # May or may not be valid depending on component requirements
        assert result.class_name == "UnicodeComponent"

    def test_should_handle_component_with_many_inputs(self):
        code = """from langflow.custom import Component
from langflow.io import MessageTextInput, Output


class ManyInputsComponent(Component):
    display_name = "Many Inputs"

    inputs = [
        MessageTextInput(name=f"input_{i}", display_name=f"Input {i}")
        for i in range(10)
    ]

    outputs = [
        Output(display_name="Output", name="output", method="process"),
    ]

    def process(self):
        return "done"
"""
        result = validate_component_code(code)

        assert result.class_name == "ManyInputsComponent"

    def test_should_handle_deeply_nested_code(self):
        code = """from langflow.custom import Component
from langflow.io import Output


class DeepComponent(Component):
    display_name = "Deep"

    outputs = [
        Output(display_name="Output", name="output", method="process"),
    ]

    def process(self):
        def inner():
            def deeper():
                return "deep"
            return deeper()
        return inner()
"""
        result = validate_component_code(code)

        assert result.class_name == "DeepComponent"
