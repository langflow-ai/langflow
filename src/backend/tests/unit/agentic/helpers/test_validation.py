"""Tests for component code validation.

Tests the _extract_class_name_regex, _safe_extract_class_name,
and validate_component_code functions.
"""

from unittest.mock import MagicMock, patch

from langflow.agentic.helpers.validation import (
    _extract_class_name_regex,
    _safe_extract_class_name,
    validate_component_code,
)

MODULE = "langflow.agentic.helpers.validation"


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


class TestValidateComponentCode:
    """Tests for full component code validation."""

    def test_should_return_valid_result_on_success(self):
        """Should return is_valid=True with class_name when validation succeeds."""
        mock_class = MagicMock()
        mock_class.return_value = MagicMock()  # instance

        with (
            patch(f"{MODULE}._safe_extract_class_name", return_value="GoodComp"),
            patch(f"{MODULE}.create_class", return_value=mock_class),
        ):
            result = validate_component_code("class GoodComp(Component): pass")

            assert result.is_valid is True
            assert result.class_name == "GoodComp"
            assert result.error is None

    def test_should_return_invalid_on_create_class_error(self):
        """Should return is_valid=False when create_class raises."""
        with (
            patch(f"{MODULE}._safe_extract_class_name", return_value="BadComp"),
            patch(f"{MODULE}.create_class", side_effect=SyntaxError("invalid syntax")),
        ):
            result = validate_component_code("class BadComp(Component): pass")

            assert result.is_valid is False
            assert "SyntaxError" in result.error
            assert "invalid syntax" in result.error

    def test_should_return_invalid_on_instantiation_error(self):
        """Should return is_valid=False when class instantiation fails."""
        mock_class = MagicMock()
        mock_class.side_effect = RuntimeError("overlapping names")

        with (
            patch(f"{MODULE}._safe_extract_class_name", return_value="InitFail"),
            patch(f"{MODULE}.create_class", return_value=mock_class),
        ):
            result = validate_component_code("class InitFail(Component): pass")

            assert result.is_valid is False
            assert "RuntimeError" in result.error

    def test_should_return_invalid_when_no_class_name(self):
        """Should return is_valid=False when class name cannot be extracted."""
        with patch(f"{MODULE}._safe_extract_class_name", return_value=None):
            result = validate_component_code("x = 1")

            assert result.is_valid is False
            assert result.class_name is None
            assert "Could not extract class name" in result.error

    def test_should_capture_error_type_and_message(self):
        """Error string should contain '{ErrorType}: {message}' format."""
        with (
            patch(f"{MODULE}._safe_extract_class_name", return_value="Comp"),
            patch(f"{MODULE}.create_class", side_effect=NameError("undefined var")),
        ):
            result = validate_component_code("class Comp(Component): pass")

            assert result.error == "NameError: undefined var"

    def test_should_preserve_code_in_result(self):
        """Result should contain the original code."""
        code = "class Comp(Component): pass"
        with (
            patch(f"{MODULE}._safe_extract_class_name", return_value="Comp"),
            patch(f"{MODULE}.create_class", side_effect=ValueError("bad")),
        ):
            result = validate_component_code(code)

            assert result.code == code
