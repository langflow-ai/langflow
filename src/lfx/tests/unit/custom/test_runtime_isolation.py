"""Tests for runtime isolation in flow execution.

These tests verify that isolation is enforced when code is executed at runtime
via create_class() and execute_function(), not just during validation.
"""

import importlib
from contextlib import contextmanager
from textwrap import dedent
from unittest.mock import MagicMock, patch

import pytest
from lfx.custom.isolation import SecurityViolationError
from lfx.custom.validate import create_class, execute_function


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
        import lfx.custom.isolation.execution as execution_module
        import lfx.custom.isolation.isolation as isolation_module
        import lfx.custom.validate as validate_module

        config_module.clear_cache()
        importlib.reload(config_module)
        importlib.reload(isolation_module)
        importlib.reload(execution_module)
        importlib.reload(validate_module)

        yield

        # Restore default
        config_module.clear_cache()
        importlib.reload(config_module)
        importlib.reload(isolation_module)
        importlib.reload(execution_module)
        importlib.reload(validate_module)


class TestRuntimeIsolationCreateClass:
    """Test isolation in create_class() at runtime."""

    def test_create_class_blocks_os_module_moderate(self):
        """Test that create_class blocks os module in MODERATE mode."""
        code = dedent("""
        from langflow.custom import Component
        import os
        
        class TestComponent(Component):
            def build(self):
                return os.getcwd()
        """)

        with mock_isolation_settings("moderate"):
            with pytest.raises(SecurityViolationError, match="Module 'os' is blocked"):
                create_class(code, "TestComponent")

    def test_create_class_blocks_subprocess_moderate(self):
        """Test that create_class blocks subprocess in MODERATE mode."""
        code = dedent("""
        from langflow.custom import Component
        import subprocess
        
        class TestComponent(Component):
            def build(self):
                return subprocess.run(["echo", "test"])
        """)

        with mock_isolation_settings("moderate"):
            with pytest.raises(SecurityViolationError, match="Module 'subprocess' is blocked"):
                create_class(code, "TestComponent")

    def test_create_class_allows_requests_moderate(self):
        """Test that create_class allows requests in MODERATE mode."""
        code = dedent("""
        from langflow.custom import Component
        import requests
        
        class TestComponent(Component):
            def build(self):
                return requests.get("https://example.com")
        """)

        with mock_isolation_settings("moderate"):
            # Should not raise SecurityViolationError
            result = create_class(code, "TestComponent")
            assert result.__name__ == "TestComponent"

    def test_create_class_blocks_requests_strict(self):
        """Test that create_class blocks requests in STRICT mode."""
        code = dedent("""
        from langflow.custom import Component
        import requests
        
        class TestComponent(Component):
            def build(self):
                return requests.get("https://example.com")
        """)

        with mock_isolation_settings("strict"):
            with pytest.raises(SecurityViolationError, match="Module 'requests' is blocked"):
                create_class(code, "TestComponent")

    def test_create_class_blocks_dangerous_builtins_moderate(self):
        """Test that create_class blocks dangerous builtins even in MODERATE mode."""
        code = dedent("""
        from langflow.custom import Component
        
        class TestComponent(Component):
            def build(self):
                return eval("1+1")
        """)

        with mock_isolation_settings("moderate"):
            with pytest.raises(SecurityViolationError, match="Builtin 'eval' is blocked"):
                create_class(code, "TestComponent")

    def test_create_class_allows_safe_code_moderate(self):
        """Test that create_class allows safe code in MODERATE mode."""
        code = dedent("""
        from langflow.custom import Component
        import json
        import math
        
        class TestComponent(Component):
            def build(self):
                data = {"value": math.sqrt(16)}
                return json.dumps(data)
        """)

        with mock_isolation_settings("moderate"):
            result = create_class(code, "TestComponent")
            assert result.__name__ == "TestComponent"

    def test_create_class_allows_everything_disabled(self):
        """Test that create_class allows everything in DISABLED mode."""
        code = dedent("""
        from langflow.custom import Component
        import os
        import subprocess
        
        class TestComponent(Component):
            def build(self):
                return os.getcwd()
        """)

        with mock_isolation_settings("disabled"):
            # Should not raise SecurityViolationError
            result = create_class(code, "TestComponent")
            assert result.__name__ == "TestComponent"


class TestRuntimeIsolationExecuteFunction:
    """Test isolation in execute_function() at runtime."""

    def test_execute_function_blocks_os_module_moderate(self):
        """Test that execute_function blocks os module in MODERATE mode."""
        code = dedent("""
        import os
        
        def test_func():
            return os.getcwd()
        """)

        with mock_isolation_settings("moderate"):
            with pytest.raises(SecurityViolationError, match="Module 'os' is blocked"):
                execute_function(code, "test_func")

    def test_execute_function_blocks_subprocess_moderate(self):
        """Test that execute_function blocks subprocess in MODERATE mode."""
        code = dedent("""
        import subprocess
        
        def test_func():
            return subprocess.run(["echo", "test"])
        """)

        with mock_isolation_settings("moderate"):
            with pytest.raises(SecurityViolationError, match="Module 'subprocess' is blocked"):
                execute_function(code, "test_func")

    def test_execute_function_allows_requests_moderate(self):
        """Test that execute_function allows requests in MODERATE mode."""
        code = dedent("""
        import requests
        
        def test_func():
            return requests.get("https://example.com")
        """)

        with mock_isolation_settings("moderate"):
            # Should not raise SecurityViolationError (but may fail on network)
            # We just want to verify it's not blocked
            try:
                execute_function(code, "test_func")
            except SecurityViolationError:
                pytest.fail("requests should be allowed in MODERATE mode")
            except Exception:
                # Network errors are fine, we just want to verify it's not blocked
                pass

    def test_execute_function_blocks_requests_strict(self):
        """Test that execute_function blocks requests in STRICT mode."""
        code = dedent("""
        import requests
        
        def test_func():
            return requests.get("https://example.com")
        """)

        with mock_isolation_settings("strict"):
            with pytest.raises(SecurityViolationError, match="Module 'requests' is blocked"):
                execute_function(code, "test_func")

    def test_execute_function_blocks_dangerous_builtins_moderate(self):
        """Test that execute_function blocks dangerous builtins even in MODERATE mode."""
        code = dedent("""
        def test_func():
            return eval("1+1")
        """)

        with mock_isolation_settings("moderate"):
            with pytest.raises(SecurityViolationError, match="Builtin 'eval' is blocked"):
                execute_function(code, "test_func")

    def test_execute_function_allows_safe_code_moderate(self):
        """Test that execute_function allows safe code in MODERATE mode."""
        code = dedent("""
        import json
        import math
        
        def test_func():
            data = {"value": math.sqrt(16)}
            return json.dumps(data)
        """)

        with mock_isolation_settings("moderate"):
            result = execute_function(code, "test_func")
            assert result == '{"value": 4.0}'

    def test_execute_function_with_args_moderate(self):
        """Test that execute_function works with arguments in MODERATE mode."""
        code = dedent("""
        def test_func(x, y):
            return x + y
        """)

        with mock_isolation_settings("moderate"):
            result = execute_function(code, "test_func", 2, 3)
            assert result == 5

    def test_execute_function_allows_everything_disabled(self):
        """Test that execute_function allows everything in DISABLED mode."""
        code = dedent("""
        import os
        
        def test_func():
            return os.getcwd()
        """)

        with mock_isolation_settings("disabled"):
            # Should not raise SecurityViolationError
            result = execute_function(code, "test_func")
            assert isinstance(result, str)  # Should return a directory path


class TestRuntimeIsolationNamespace:
    """Test namespace isolation at runtime."""

    def test_create_class_cannot_access_server_variables(self):
        """Test that create_class cannot access server Python variables."""
        # Set a server variable
        server_secret = "secret_value_12345"

        code = dedent("""
        from langflow.custom import Component
        
        class TestComponent(Component):
            def build(self):
                # This should raise NameError, not access server_secret
                return server_secret
        """)

        with mock_isolation_settings("moderate"):
            result_class = create_class(code, "TestComponent")
            # When we try to instantiate and call build(), it should fail
            instance = result_class()
            with pytest.raises(NameError, match="name 'server_secret' is not defined"):
                instance.build()

    def test_execute_function_cannot_access_server_variables(self):
        """Test that execute_function cannot access server Python variables."""
        # Set a server variable
        server_secret = "secret_value_12345"

        code = dedent("""
        def test_func():
            # This should raise NameError, not access server_secret
            return server_secret
        """)

        with mock_isolation_settings("moderate"):
            with pytest.raises(NameError, match="name 'server_secret' is not defined"):
                execute_function(code, "test_func")
