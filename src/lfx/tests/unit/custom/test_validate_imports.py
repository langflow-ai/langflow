"""Tests for import validation in validate_code endpoint.

Tests that validate_code() properly blocks dangerous imports at:
- Module level
- Function body level (static analysis)
- Method body level (static analysis)
- Decorator level (execution)
- Default argument level (execution)
"""

import importlib
from contextlib import contextmanager
from textwrap import dedent
from unittest.mock import MagicMock, patch

import pytest

from lfx.custom.validate import validate_code


@contextmanager
def mock_isolation_settings(security_level="moderate"):
    """Context manager to mock isolation settings service.
    
    Args:
        security_level: The security level to use ("moderate", "strict", or "disabled")
    """
    with patch("lfx.services.deps.get_settings_service") as mock_get_settings:
        mock_settings_service = MagicMock()
        mock_settings_service.settings.isolation_security_level = security_level
        mock_get_settings.return_value = mock_settings_service
        
        # Clear cache and reload modules to pick up new settings
        import lfx.custom.isolation.config as config_module
        import lfx.custom.isolation.isolation as isolation_module
        import lfx.custom.validate as validate_module
        
        config_module.clear_cache()
        importlib.reload(config_module)
        importlib.reload(isolation_module)
        importlib.reload(validate_module)
        
        yield
        
        # Restore default
        config_module.clear_cache()
        importlib.reload(config_module)
        importlib.reload(isolation_module)
        importlib.reload(validate_module)


class TestModuleLevelImports:
    """Test that module-level imports are blocked."""

    def test_blocked_module_import_moderate(self):
        """Test that dangerous modules are blocked at module level in MODERATE mode."""
        code = dedent("""
        import subprocess
        
        def test():
            return "ok"
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["imports"]["errors"]) > 0
            assert any("subprocess" in str(e).lower() for e in errors["imports"]["errors"])

    def test_blocked_module_importfrom_moderate(self):
        """Test that dangerous modules are blocked with import from in MODERATE mode."""
        code = dedent("""
        from subprocess import run
        
        def test():
            return "ok"
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["imports"]["errors"]) > 0
            assert any("subprocess" in str(e).lower() for e in errors["imports"]["errors"])

    def test_allowed_module_import_moderate(self):
        """Test that allowed modules pass validation in MODERATE mode."""
        code = dedent("""
        import json
        import requests
        
        def test():
            return "ok"
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["imports"]["errors"]) == 0
            assert len(errors["function"]["errors"]) == 0

    def test_blocked_module_import_strict(self):
        """Test that requests is blocked in STRICT mode."""
        code = dedent("""
        import requests
        
        def test():
            return "ok"
        """)
        
        with mock_isolation_settings("strict"):
            errors = validate_code(code)
            assert len(errors["imports"]["errors"]) > 0
            assert any("requests" in str(e).lower() for e in errors["imports"]["errors"])


class TestFunctionBodyImports:
    """Test that imports inside function bodies are detected via static analysis."""

    def test_blocked_import_in_function_body_moderate(self):
        """Test that dangerous imports in function bodies are blocked."""
        code = dedent("""
        def test():
            import subprocess
            return subprocess.run(['echo', 'test'])
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) > 0
            assert any("subprocess" in str(e).lower() for e in errors["function"]["errors"])
            assert any("test" in str(e).lower() for e in errors["function"]["errors"])

    def test_blocked_importfrom_in_function_body_moderate(self):
        """Test that dangerous import from in function bodies are blocked."""
        code = dedent("""
        def test():
            from subprocess import run
            return run(['echo', 'test'])
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) > 0
            assert any("subprocess" in str(e).lower() for e in errors["function"]["errors"])

    def test_allowed_import_in_function_body_moderate(self):
        """Test that allowed imports in function bodies pass validation."""
        code = dedent("""
        def test():
            import json
            return json.dumps({'test': 'data'})
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) == 0

    def test_blocked_import_in_function_body_strict(self):
        """Test that requests is blocked in function body in STRICT mode."""
        code = dedent("""
        def test():
            import requests
            return requests.get('https://example.com')
        """)
        
        with mock_isolation_settings("strict"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) > 0
            assert any("requests" in str(e).lower() for e in errors["function"]["errors"])

    def test_multiple_imports_in_function_body(self):
        """Test that multiple blocked imports in function body are all detected."""
        code = dedent("""
        def test():
            import os
            import subprocess
            import sys
            return "test"
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) >= 3  # Should catch all three
            error_text = " ".join(str(e) for e in errors["function"]["errors"]).lower()
            assert "os" in error_text or "subprocess" in error_text or "sys" in error_text

    def test_nested_function_with_import(self):
        """Test that imports in nested functions are detected."""
        code = dedent("""
        def outer():
            def inner():
                import subprocess
                return subprocess.run(['echo', 'test'])
            return inner()
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) > 0
            assert any("subprocess" in str(e).lower() for e in errors["function"]["errors"])
            # Should mention nested function context
            error_text = " ".join(str(e) for e in errors["function"]["errors"]).lower()
            assert "inner" in error_text or "nested" in error_text


class TestMethodBodyImports:
    """Test that imports inside class method bodies are detected."""

    def test_blocked_import_in_method_body_moderate(self):
        """Test that dangerous imports in method bodies are blocked."""
        code = dedent("""
        class MyComponent:
            def build(self):
                import subprocess
                return subprocess.run(['echo', 'test'])
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) > 0
            assert any("subprocess" in str(e).lower() for e in errors["function"]["errors"])
            assert any("build" in str(e).lower() for e in errors["function"]["errors"])

    def test_blocked_import_in_multiple_methods(self):
        """Test that imports in multiple methods are all detected."""
        code = dedent("""
        class MyComponent:
            def build(self):
                import os
                return os.getcwd()
            
            def update(self):
                import subprocess
                return subprocess.run(['echo', 'test'])
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) >= 2
            error_text = " ".join(str(e) for e in errors["function"]["errors"]).lower()
            assert ("os" in error_text or "subprocess" in error_text)

    def test_allowed_import_in_method_body_moderate(self):
        """Test that allowed imports in method bodies pass validation."""
        code = dedent("""
        class MyComponent:
            def build(self):
                import json
                return json.dumps({'test': 'data'})
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) == 0

    def test_nested_class_with_import(self):
        """Test that imports in nested class methods are detected."""
        code = dedent("""
        class Outer:
            class Inner:
                def method(self):
                    import subprocess
                    return subprocess.run(['echo', 'test'])
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) > 0
            assert any("subprocess" in str(e).lower() for e in errors["function"]["errors"])


class TestDecoratorImports:
    """Test that imports in decorators are blocked during execution."""

    def test_blocked_import_in_decorator_moderate(self):
        """Test that dangerous imports in decorators are blocked."""
        code = dedent("""
        import subprocess
        
        @subprocess.run(['echo', 'test'])
        def test():
            return "ok"
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            # Should fail at module-level import OR decorator execution
            assert len(errors["imports"]["errors"]) > 0 or len(errors["function"]["errors"]) > 0

    def test_blocked_builtin_in_decorator_moderate(self):
        """Test that dangerous builtins in decorators are blocked."""
        code = dedent("""
        @eval("print('hacked')")
        def test():
            return "ok"
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) > 0
            assert any("eval" in str(e).lower() for e in errors["function"]["errors"])

    def test_lambda_decorator_with_import(self):
        """Test that lambda decorators with imports are blocked."""
        code = dedent("""
        @(lambda: __import__('subprocess').run(['echo', 'test']))()
        def test():
            return "ok"
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) > 0
            assert any("__import__" in str(e) or "subprocess" in str(e).lower() for e in errors["function"]["errors"])


class TestDefaultArgumentImports:
    """Test that imports in default arguments are blocked during execution."""

    def test_blocked_import_in_default_arg_moderate(self):
        """Test that dangerous imports in default arguments are blocked."""
        code = dedent("""
        def test(x=__import__('subprocess').run(['echo', 'test'])):
            return x
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) > 0
            assert any("__import__" in str(e) or "subprocess" in str(e).lower() for e in errors["function"]["errors"])


class TestAsyncFunctions:
    """Test that async functions are handled correctly."""

    def test_blocked_import_in_async_function_body(self):
        """Test that dangerous imports in async function bodies are blocked."""
        code = dedent("""
        async def test():
            import subprocess
            return subprocess.run(['echo', 'test'])
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) > 0
            assert any("subprocess" in str(e).lower() for e in errors["function"]["errors"])

    def test_blocked_import_in_async_method_body(self):
        """Test that dangerous imports in async method bodies are blocked."""
        code = dedent("""
        class MyComponent:
            async def build(self):
                import subprocess
                return subprocess.run(['echo', 'test'])
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) > 0
            assert any("subprocess" in str(e).lower() for e in errors["function"]["errors"])


class TestComplexScenarios:
    """Test complex scenarios with multiple import locations."""

    def test_module_and_function_body_imports(self):
        """Test that both module-level and function-body imports are caught."""
        code = dedent("""
        import os
        
        def test():
            import subprocess
            return "test"
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            # Should catch both
            assert len(errors["imports"]["errors"]) > 0  # Module-level
            assert len(errors["function"]["errors"]) > 0  # Function body

    def test_allowed_and_blocked_mixed(self):
        """Test that allowed imports pass but blocked ones fail."""
        code = dedent("""
        import json  # Allowed
        import subprocess  # Blocked
        
        def test():
            import requests  # Allowed in MODERATE
            import os  # Blocked
            return "test"
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            # Should catch blocked ones
            assert len(errors["imports"]["errors"]) > 0  # subprocess
            assert len(errors["function"]["errors"]) > 0  # os

    def test_no_imports_passes(self):
        """Test that code with no imports passes validation."""
        code = dedent("""
        def test():
            x = 1 + 1
            return x
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["imports"]["errors"]) == 0
            assert len(errors["function"]["errors"]) == 0

    def test_disabled_mode_allows_everything(self):
        """Test that DISABLED mode allows all imports."""
        code = dedent("""
        import subprocess
        import os
        
        def test():
            import sys
            return "test"
        """)
        
        with mock_isolation_settings("disabled"):
            errors = validate_code(code)
            # Should pass - no errors
            assert len(errors["imports"]["errors"]) == 0
            assert len(errors["function"]["errors"]) == 0


class TestErrorMessages:
    """Test that error messages are informative."""

    def test_error_message_includes_function_name(self):
        """Test that error messages include the function name."""
        code = dedent("""
        def my_function():
            import subprocess
            return "test"
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) > 0
            error_text = " ".join(str(e) for e in errors["function"]["errors"]).lower()
            assert "my_function" in error_text

    def test_error_message_includes_method_name(self):
        """Test that error messages include the method name."""
        code = dedent("""
        class MyComponent:
            def build(self):
                import subprocess
                return "test"
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) > 0
            error_text = " ".join(str(e) for e in errors["function"]["errors"]).lower()
            assert "build" in error_text or "mycomponent" in error_text

    def test_error_message_includes_module_name(self):
        """Test that error messages include the blocked module name."""
        code = dedent("""
        def test():
            import subprocess
            return "test"
        """)
        
        with mock_isolation_settings("moderate"):
            errors = validate_code(code)
            assert len(errors["function"]["errors"]) > 0
            error_text = " ".join(str(e) for e in errors["function"]["errors"]).lower()
            assert "subprocess" in error_text

