# ruff: noqa: ARG002
"""Integration tests for custom code blocking feature."""

from unittest.mock import Mock, patch

import pytest
from lfx.custom.validate import create_class, create_function, eval_function, execute_function, extract_display_name


class TestExtractDisplayName:
    """Unit tests for extract_display_name function."""

    def test_extract_display_name_simple(self):
        """Test extracting display_name from a simple component."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    display_name = "Test Component"
"""
        result = extract_display_name(code)
        assert result == "Test Component"

    def test_extract_display_name_with_other_attributes(self):
        """Test extracting display_name when other attributes are present."""
        code = """
from lfx.custom import Component

class MyComponent(Component):
    description = "A test component"
    display_name = "My Custom Component"
    icon = "icon.svg"
"""
        result = extract_display_name(code)
        assert result == "My Custom Component"

    def test_extract_display_name_no_display_name(self):
        """Test that None is returned when display_name is not present."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    description = "A test component"
"""
        result = extract_display_name(code)
        assert result is None

    def test_extract_display_name_not_a_component(self):
        """Test that None is returned for non-Component classes."""
        code = """
class RegularClass:
    display_name = "Not a Component"
"""
        result = extract_display_name(code)
        assert result is None

    def test_extract_display_name_multiple_classes(self):
        """Test extracting display_name from first Component subclass."""
        code = """
from lfx.custom import Component

class FirstComponent(Component):
    display_name = "First Component"

class SecondComponent(Component):
    display_name = "Second Component"
"""
        result = extract_display_name(code)
        assert result == "First Component"

    def test_extract_display_name_with_docstring(self):
        """Test extracting display_name when class has docstring."""
        code = '''
from lfx.custom import Component

class TestComponent(Component):
    """This is a test component."""
    display_name = "Test Component"

    def build(self):
        pass
'''
        result = extract_display_name(code)
        assert result == "Test Component"

    def test_extract_display_name_invalid_syntax(self):
        """Test that None is returned for invalid Python syntax."""
        code = "this is not valid python code {"
        result = extract_display_name(code)
        assert result is None

    def test_extract_display_name_empty_string(self):
        """Test that None is returned for empty string."""
        code = ""
        result = extract_display_name(code)
        assert result is None

    def test_extract_display_name_with_f_string(self):
        """Test extracting display_name when it's an f-string (should return None)."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    display_name = f"Dynamic {name}"
"""
        result = extract_display_name(code)
        assert result is None

    def test_extract_display_name_nested_in_body(self):
        """Test extracting display_name from class body assignments."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    def __init__(self):
        self.display_name = "Should Not Extract This"

    display_name = "Correct Display Name"
"""
        result = extract_display_name(code)
        assert result == "Correct Display Name"


class TestBlockCustomCodeIntegration:
    """Integration tests for blocking custom code execution."""

    def test_create_class_allowed_when_blocking_disabled(self):
        """Test that create_class works when blocking is disabled."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    display_name = "Test"
"""
        # Should work when blocking is disabled (default)
        result = create_class(code, "TestComponent")
        assert result is not None

    def test_create_class_blocked_when_hash_not_in_index(self, monkeypatch):
        """Test that create_class is blocked when hash not in index and env var is false."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    display_name = "Test"
"""
        # Set environment variable to disable custom components
        monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "false")

        # Mock the hash lookup to return False (hash not found)
        with patch("lfx.custom.hash_validator.is_code_hash_allowed") as mock_hash_check:
            mock_hash_check.return_value = False
            with pytest.raises(ValueError, match="Custom Component 'Test' is not allowed"):
                create_class(code, "TestComponent")

            # Verify is_code_hash_allowed was called
            mock_hash_check.assert_called_once()

    def test_create_class_allowed_when_hash_in_index(self, monkeypatch):
        """Test that create_class works when hash is in index and env var is false."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    display_name = "Test"
"""
        # Set environment variable to disable custom components
        monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "false")

        # Mock the hash lookup to return True (hash found)
        with patch("lfx.custom.hash_validator.is_code_hash_allowed") as mock_hash_check:
            mock_hash_check.return_value = True
            # Should not raise
            result = create_class(code, "TestComponent")
            assert result is not None

            # Verify is_code_hash_allowed was called
            mock_hash_check.assert_called_once()

    def test_create_function_allowed_when_blocking_disabled(self):
        """Test that create_function works when blocking is disabled."""
        code = """
def test_function(x):
    return x * 2
"""
        # Should work when blocking is disabled (default)
        result = create_function(code, "test_function")
        assert result is not None

    def test_create_function_blocked_when_hash_not_in_index(self):
        """Test that create_function is blocked when hash not in index."""
        code = """
def test_function(x):
    return x * 2
"""
        # Mock settings to disable allowing (enable blocking)
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock hash lookup to return False (hash not found)
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = False
            with pytest.raises(ValueError, match="Custom Component 'test_function' is not allowed"):
                create_function(code, "test_function")

    def test_create_function_allowed_when_hash_in_index(self):
        """Test that create_function works when hash is in index."""
        code = """
def test_function(x):
    return x * 2
"""
        # Mock settings to disable allowing (enable blocking)
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False

        # Mock hash lookup to return True (hash found)
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = True
            # Should not raise
            result = create_function(code, "test_function")
            assert result is not None

    def test_blocking_respects_environment_variable(self, monkeypatch):
        """Test that blocking respects LANGFLOW_ALLOW_CUSTOM_COMPONENTS env var."""
        code = """
from lfx.custom import Component

class TestComponent(Component):
    display_name = "Test"
"""
        # Test 1: When allow_custom_components=False, hash not found should block
        mock_settings = Mock()
        mock_settings.settings.allow_custom_components = False
        mock_settings.settings.allow_code_execution_components = True
        mock_settings.settings.allow_nightly_core_components = False

        # Mock get_settings_service to return our mock settings
        with patch("lfx.custom.hash_validator.get_settings_service") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            # Mock _get_cached_hashes to return empty set (hash not found)
            with patch("lfx.custom.hash_validator._get_cached_hashes") as mock_get_hashes:
                mock_get_hashes.return_value = set()

                with pytest.raises(ValueError, match="Custom Component 'Test' is not allowed"):
                    create_class(code, "TestComponent")

        # Test 2: When allow_custom_components=True, should work even if hash not found
        mock_settings.settings.allow_custom_components = True

        with patch("lfx.custom.hash_validator.get_settings_service") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            # Mock _get_cached_hashes to return empty set (hash not found, but should be allowed)
            with patch("lfx.custom.hash_validator._get_cached_hashes") as mock_get_hashes:
                mock_get_hashes.return_value = set()

                result = create_class(code, "TestComponent")
                assert result is not None


class TestEvalFunctionBlocking:
    """Tests for eval_function hash validation blocking."""

    def test_eval_function_allowed_when_blocking_disabled(self):
        """Test that eval_function works when blocking is disabled (default)."""
        code = """
def test_function(x):
    return x * 2
"""
        result = eval_function(code)
        assert result is not None
        assert result(5) == 10

    def test_eval_function_blocked_when_hash_not_in_index(self):
        """Test that eval_function is blocked when hash not in index."""
        code = """
def test_function(x):
    return x * 2
"""
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = False
            with pytest.raises(ValueError, match="Custom function evaluation is not allowed"):
                eval_function(code)

    def test_eval_function_allowed_when_hash_in_index(self):
        """Test that eval_function works when hash is in index."""
        code = """
def test_function(x):
    return x * 2
"""
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = True
            result = eval_function(code)
            assert result is not None
            assert result(5) == 10

    def test_eval_function_blocked_on_exception(self):
        """Test that eval_function blocks when hash validation raises exception (fail-closed)."""
        code = """
def test_function(x):
    return x * 2
"""
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = False
            with pytest.raises(ValueError, match="Custom function evaluation is not allowed"):
                eval_function(code)


class TestExecuteFunctionBlocking:
    """Tests for execute_function hash validation blocking."""

    def test_execute_function_blocked_when_hash_not_in_index(self):
        """Test that execute_function is blocked when hash not in index."""
        code = """
def test_function(x):
    return x * 2
"""
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = False
            with pytest.raises(ValueError, match="Custom Component 'test_function' is not allowed"):
                execute_function(code, "test_function", 5)

    def test_execute_function_allowed_when_hash_in_index(self):
        """Test that execute_function works when hash is in index."""
        code = """
def test_function(x):
    return x * 2
"""
        with patch("lfx.custom.validate._check_and_block_if_not_allowed") as mock_check:
            mock_check.return_value = True
            result = execute_function(code, "test_function", 5)
            assert result == 10


class TestCodeParserSafety:
    """Tests for code_parser construct_eval_env using importlib instead of exec."""

    def test_construct_eval_env_with_importlib(self):
        """Test that construct_eval_env correctly uses importlib for imports."""
        from lfx.custom.code_parser.code_parser import CodeParser

        code = """
from typing import Optional
def test_func() -> Optional[str]:
    return None
"""
        parser = CodeParser(code)
        parser.parse_code()

        # construct_eval_env should handle tuple imports (from X import Y)
        eval_env = parser.construct_eval_env("Optional[str]", tuple(parser.data["imports"]))
        assert "Optional" in eval_env

    def test_construct_eval_env_with_module_alias(self):
        """Test that construct_eval_env handles module aliases correctly."""
        from lfx.custom.code_parser.code_parser import CodeParser

        code = """
import json
def test_func() -> json:
    pass
"""
        parser = CodeParser(code)
        parser.parse_code()

        eval_env = parser.construct_eval_env("json", tuple(parser.data["imports"]))
        import json

        assert eval_env.get("json") is json

    def test_construct_eval_env_no_exec_used(self):
        """Test that construct_eval_env does not use exec (uses importlib instead)."""
        import ast
        import inspect
        import textwrap

        from lfx.custom.code_parser.code_parser import CodeParser

        source = textwrap.dedent(inspect.getsource(CodeParser.construct_eval_env))
        tree = ast.parse(source)
        # Check that there are no exec() calls in the AST
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "exec":
                pytest.fail("construct_eval_env should not use exec()")


class TestAllExecPathsProtected:
    """Tests to verify all exec/eval paths in validate.py are protected."""

    def test_all_public_exec_functions_have_hash_check(self):
        """Verify that all functions in validate.py that call exec() have hash validation."""
        import inspect

        from lfx.custom import validate

        # List of functions that should have _check_and_block_if_not_allowed
        functions_with_exec = ["validate_code", "execute_function", "create_function", "create_class", "eval_function"]

        for func_name in functions_with_exec:
            func = getattr(validate, func_name)
            source = inspect.getsource(func)
            assert "_check_and_block_if_not_allowed" in source, (
                f"Function {func_name} uses exec() but does not call _check_and_block_if_not_allowed"
            )
