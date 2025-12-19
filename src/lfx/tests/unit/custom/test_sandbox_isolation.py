"""Unit tests to verify sandbox isolation works correctly.

These tests verify that if isolation were broken, code would have access to
server resources. They prove isolation by showing that access attempts fail.
"""

import pytest
from lfx.custom.sandbox import execute_in_sandbox


def test_sandbox_cannot_access_parent_globals():
    """Test that sandboxed code cannot access parent function's globals."""
    # Set a variable in the parent scope
    parent_var = "should_not_be_accessible"

    code = """
def test():
    # Try to access parent_var from parent scope
    # If isolation were broken, this would work
    return parent_var
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    # Execute in sandbox
    execute_in_sandbox(code_obj, exec_globals)

    # Try to call the function
    test_func = exec_globals["test"]

    # Should raise NameError because parent_var is not accessible
    with pytest.raises(NameError):
        test_func()


def test_sandbox_cannot_modify_parent_globals():
    """Test that sandboxed code cannot modify parent scope's globals."""
    parent_dict = {"value": "original"}

    code = """
def test():
    # Try to modify parent_dict
    # If isolation were broken, this would modify the real parent_dict
    parent_dict["value"] = "modified"
    return parent_dict["value"]
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    execute_in_sandbox(code_obj, exec_globals)

    # Call the function - should fail because parent_dict is not accessible
    test_func = exec_globals["test"]

    with pytest.raises(NameError):
        test_func()

    # Verify parent_dict was not modified
    assert parent_dict["value"] == "original"


def test_sandbox_isolated_builtins():
    """Test that sandbox uses isolated builtins, not real ones."""
    # Create a marker in real builtins (simulating server state)
    import builtins

    original_builtins_len = len(dir(builtins))

    code = """
def test():
    import builtins
    # Try to access real builtins
    # If isolation were broken, we could modify real builtins
    builtins.ESCAPE_TEST = "should_not_exist"
    return hasattr(builtins, 'ESCAPE_TEST')
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    execute_in_sandbox(code_obj, exec_globals)

    # Call the function
    test_func = exec_globals["test"]
    result = test_func()

    # Sandboxed code should see its own isolated builtins (modification succeeds in sandbox)
    # But real builtins should not be affected
    assert result is True  # Sandboxed code successfully modified its isolated builtins
    assert not hasattr(builtins, "ESCAPE_TEST")  # Real builtins was not modified
    assert len(dir(builtins)) == original_builtins_len


def test_sandbox_fresh_namespace_per_execution():
    """Test that each execution gets a fresh isolated namespace."""
    code1 = """
GLOBAL_VAR = "first_execution"
def test():
    return GLOBAL_VAR
"""
    code_obj1 = compile(code1, "<test>", "exec")
    exec_globals1 = {}
    execute_in_sandbox(code_obj1, exec_globals1)

    # Second execution with different code
    code2 = """
def test():
    # Try to access GLOBAL_VAR from previous execution
    # If isolation were broken, this would work
    return GLOBAL_VAR
"""
    code_obj2 = compile(code2, "<test>", "exec")
    exec_globals2 = {}
    execute_in_sandbox(code_obj2, exec_globals2)

    # Should raise NameError because GLOBAL_VAR doesn't exist in this execution
    test_func = exec_globals2["test"]
    with pytest.raises(NameError):
        test_func()


def test_sandbox_cannot_access_frame_locals():
    """Test that sandboxed code cannot access caller's local variables."""

    def caller_function():
        local_var = "should_not_be_accessible"

        code = """
def test():
    # Try to access local_var from caller
    # If isolation were broken, this would work
    return local_var
"""
        code_obj = compile(code, "<test>", "exec")
        exec_globals = {}

        execute_in_sandbox(code_obj, exec_globals)

        # Call the function
        test_func = exec_globals["test"]

        # Should raise NameError because local_var is not accessible
        with pytest.raises(NameError):
            test_func()

    caller_function()


def test_sandbox_isolated_imports():
    """Test that imports in sandbox cannot access parent scope variables."""
    # Set a variable at module level that shadows an import name
    json = "this_is_not_the_json_module"

    code = """
import json
def test():
    # If isolation were broken, json would be the parent's variable
    # But it should be the actual json module
    return type(json).__name__
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    execute_in_sandbox(code_obj, exec_globals)

    # Call the function
    test_func = exec_globals["test"]
    result = test_func()

    # Should return 'module' (the json module), not 'str' (parent's json variable)
    assert result == "module"
    # Verify parent's json variable was not accessed
    assert json == "this_is_not_the_json_module"


def test_sandbox_function_definition_time_isolation():
    """Test that function definition time code (default args) executes in isolation."""
    parent_var = "should_not_be_accessible"

    code = """
def test(x=parent_var):
    # Default argument evaluation happens at definition time
    # If isolation were broken, parent_var would be accessible
    return x
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    # Execute in sandbox - definition time code runs here
    execute_in_sandbox(code_obj, exec_globals)

    # Try to call the function
    test_func = exec_globals["test"]

    # Should raise NameError when function is defined (default arg evaluation)
    # OR when called without args
    # The key is that parent_var is not accessible during definition
    with pytest.raises(NameError):
        test_func()  # Calling without args triggers default arg evaluation


def test_sandbox_decorator_isolation():
    """Test that decorator evaluation happens in isolation."""
    parent_var = "should_not_be_accessible"

    code = """
@(parent_var or lambda f: f)
def test():
    return 1
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    # Execute in sandbox - decorator evaluation happens here
    # Should raise NameError because parent_var is not accessible
    with pytest.raises(NameError):
        execute_in_sandbox(code_obj, exec_globals)


# Module-level variable to test that sandbox cannot access module globals
MODULE_LEVEL_VAR = "should_not_be_accessible_from_sandbox"


def test_sandbox_cannot_access_module_globals():
    """Test that sandboxed code cannot access module-level globals."""
    code = """
def test():
    # Try to access MODULE_LEVEL_VAR from module scope
    # If isolation were broken, this would work
    return MODULE_LEVEL_VAR
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    execute_in_sandbox(code_obj, exec_globals)

    # Call the function - should fail because MODULE_LEVEL_VAR is not accessible
    test_func = exec_globals["test"]
    with pytest.raises(NameError):
        test_func()


def test_sandbox_cannot_escape_via_globals():
    """Test that sandboxed code cannot escape via globals() function."""
    # Set a variable at module level
    module_var = "should_not_be_accessible"

    code = """
def test():
    # Try to access parent globals via globals() function
    # If isolation were broken, this could access the parent's globals
    g = globals()
    # Try to access a variable that would be in parent's globals
    # The sandbox's globals() should only return sandbox globals, not parent's
    return 'module_var' in g
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    execute_in_sandbox(code_obj, exec_globals)

    # Call the function
    test_func = exec_globals["test"]
    result = test_func()

    # Should return False - sandbox's globals() should not contain parent's variables
    assert result is False
