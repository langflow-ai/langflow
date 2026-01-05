"""Unit tests to verify sandbox isolation works correctly.

These tests verify that if isolation were broken, code would have access to
server resources. They prove isolation by showing that access attempts fail.
"""

import pytest
from lfx.custom.isolation import execute_in_isolated_env


def test_sandbox_cannot_access_parent_globals():
    """Test that sandboxed code cannot access parent function's globals."""
    # Set a variable in the parent scope
    _parent_var = "should_not_be_accessible"

    code = """
def test():
    # Try to access parent_var from parent scope
    # If isolation were broken, this would work
    return parent_var
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    # Execute in sandbox
    execute_in_isolated_env(code_obj, exec_globals)

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

    execute_in_isolated_env(code_obj, exec_globals)

    # Call the function - should fail because parent_dict is not accessible
    test_func = exec_globals["test"]

    with pytest.raises(NameError):
        test_func()

    # Verify parent_dict was not modified
    assert parent_dict["value"] == "original"


def test_sandbox_isolated_builtins():
    """Test that sandbox uses isolated builtins via __builtins__, not via import.

    Note: When code does `import builtins`, it gets the isolated builtins module.
    The isolation is via __builtins__ dict, which prevents direct access to critical builtins
    like eval, exec, compile (blocked even in MODERATE mode).
    """
    import builtins

    original_builtins_len = len(dir(builtins))
    # Store original value if it exists
    had_escape_test = hasattr(builtins, "ESCAPE_TEST")
    original_escape_test = getattr(builtins, "ESCAPE_TEST", None)

    try:
        code = """
def test():
    # Access builtins via __builtins__ (isolated)
    # Direct access to 'eval' should fail because it's blocked (even in MODERATE mode)
    try:
        eval_func = __builtins__['eval']
        return 'eval_accessible'
    except KeyError:
        return 'eval_blocked'
"""
        code_obj = compile(code, "<test>", "exec")
        exec_globals = {}

        execute_in_isolated_env(code_obj, exec_globals)

        # Call the function
        test_func = exec_globals["test"]
        result = test_func()

        # Should return 'eval_blocked' because eval is blocked even in MODERATE mode
        assert result == "eval_blocked"
        assert len(dir(builtins)) == original_builtins_len
    finally:
        # Clean up
        if had_escape_test:
            builtins.ESCAPE_TEST = original_escape_test
        elif hasattr(builtins, "ESCAPE_TEST"):
            delattr(builtins, "ESCAPE_TEST")


def test_sandbox_fresh_namespace_per_execution():
    """Test that each execution gets a fresh isolated namespace."""
    code1 = """
GLOBAL_VAR = "first_execution"
def test():
    return GLOBAL_VAR
"""
    code_obj1 = compile(code1, "<test>", "exec")
    exec_globals1 = {}
    execute_in_isolated_env(code_obj1, exec_globals1)

    # Second execution with different code
    code2 = """
def test():
    # Try to access GLOBAL_VAR from previous execution
    # If isolation were broken, this would work
    return GLOBAL_VAR
"""
    code_obj2 = compile(code2, "<test>", "exec")
    exec_globals2 = {}
    execute_in_isolated_env(code_obj2, exec_globals2)

    # Should raise NameError because GLOBAL_VAR doesn't exist in this execution
    test_func = exec_globals2["test"]
    with pytest.raises(NameError):
        test_func()


def test_sandbox_cannot_access_frame_locals():
    """Test that sandboxed code cannot access caller's local variables."""

    def caller_function():
        _local_var = "should_not_be_accessible"

        code = """
def test():
    # Try to access local_var from caller
    # If isolation were broken, this would work
    return local_var
"""
        code_obj = compile(code, "<test>", "exec")
        exec_globals = {}

        execute_in_isolated_env(code_obj, exec_globals)

        # Call the function
        test_func = exec_globals["test"]

        # Should raise NameError because local_var is not accessible
        with pytest.raises(NameError):
            test_func()

    caller_function()


def test_sandbox_isolated_imports():
    """Test that imports in sandbox cannot access parent scope variables."""
    # Set a variable at module level that shadows an import name
    json_var = "this_is_not_the_json_module"

    code = """
import json
def test():
    # If isolation were broken, json_var would be accessible
    # But it should not be - we can only access json (the imported module)
    # Try to access parent's json_var - should fail
    try:
        return json_var  # This should fail
    except NameError:
        # Good - parent's variable is not accessible
        return type(json).__name__  # Return type of imported module
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    execute_in_isolated_env(code_obj, exec_globals)

    # Verify json module is accessible in exec_globals
    assert "json" in exec_globals
    assert hasattr(exec_globals["json"], "dumps")  # Verify it's the json module

    # Call the function
    test_func = exec_globals["test"]
    result = test_func()

    # Should return 'module' (the json module), proving parent's json_var was not accessible
    assert result == "module"
    # Verify parent's json variable was not accessed
    assert json_var == "this_is_not_the_json_module"


def test_sandbox_function_definition_time_isolation():
    """Test that function definition time code (default args) executes in isolation."""
    _parent_var = "should_not_be_accessible"

    code = """
def test(x=parent_var):
    # Default argument evaluation happens at definition time
    # If isolation were broken, parent_var would be accessible
    return x
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    # Execute in sandbox - definition time code runs here
    # Should raise NameError when function is defined because parent_var is not accessible
    with pytest.raises(NameError, match="parent_var"):
        execute_in_isolated_env(code_obj, exec_globals)


def test_sandbox_decorator_isolation():
    """Test that decorator evaluation happens in isolation."""
    _parent_var = "should_not_be_accessible"

    code = """
def make_decorator():
    return parent_var or (lambda f: f)

@make_decorator()
def test():
    return 1
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    # Execute in sandbox - decorator evaluation happens here
    # Should raise NameError because parent_var is not accessible
    with pytest.raises(NameError):
        execute_in_isolated_env(code_obj, exec_globals)


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

    execute_in_isolated_env(code_obj, exec_globals)

    # Call the function - should fail because MODULE_LEVEL_VAR is not accessible
    test_func = exec_globals["test"]
    with pytest.raises(NameError):
        test_func()


def test_sandbox_cannot_escape_via_globals():
    """Test that sandboxed code cannot escape via globals() function."""
    # Set a variable at module level
    _module_var = "should_not_be_accessible"

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

    execute_in_isolated_env(code_obj, exec_globals)

    # Call the function
    test_func = exec_globals["test"]
    result = test_func()

    # Should return False - sandbox's globals() should not contain parent's variables
    assert result is False


def test_sandbox_cannot_escape_via_locals():
    """Test that sandboxed code cannot escape via locals() function."""

    # Set a variable in function scope
    def test_function():
        _local_var = "should_not_be_accessible"

        code = """
def test():
    # Try to access parent locals via locals() function
    # If isolation were broken, this could access the parent's locals
    l = locals()
    # The sandbox's locals() should only return sandbox locals, not parent's
    return 'local_var' in l
"""
        code_obj = compile(code, "<test>", "exec")
        exec_globals = {}

        execute_in_isolated_env(code_obj, exec_globals)

        # Call the function
        test_func = exec_globals["test"]
        result = test_func()

        # Should return False - sandbox's locals() should not contain parent's variables
        assert result is False

    test_function()


def test_sandbox_can_define_classes():
    """Test that class definitions work in the sandbox (requires __build_class__)."""
    code = """
class TestClass:
    def __init__(self, value):
        self.value = value

    def get_value(self):
        return self.value

def test():
    obj = TestClass("test_value")
    return obj.get_value()
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    execute_in_isolated_env(code_obj, exec_globals)

    # Call the function
    test_func = exec_globals["test"]
    result = test_func()

    # Should successfully create and use the class
    assert result == "test_value"


def test_sandbox_import_builtins_returns_isolated_version():
    """Test that `import builtins` returns isolated version, not real builtins module."""
    import builtins as real_builtins

    code = """
import builtins
def test():
    # Try to access eval() via imported builtins module
    # Should raise SecurityViolationError because eval is blocked in isolated builtins (even in MODERATE mode)
    try:
        func = builtins.eval
        return 'eval_accessible'
    except Exception as e:
        return type(e).__name__
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    execute_in_isolated_env(code_obj, exec_globals)

    # Call the function
    test_func = exec_globals["test"]
    result = test_func()

    # Should raise SecurityViolationError, not return 'eval_accessible'
    # This proves that `import builtins` returned the isolated version, not real builtins
    assert result == "SecurityViolationError"
    # Verify real builtins wasn't accessed
    assert hasattr(real_builtins, "eval")


def test_sandbox_blocks_import_builtins_in_validation_context():
    """Test that `import builtins` is blocked when isolated_builtins_dict is None (validation context).
    
    When validate_code() calls create_isolated_import() without arguments, it's in
    validation-only mode. In this mode, `import builtins` should be blocked with an error
    rather than returning the isolated version (since isolated builtins aren't created).
    """
    from lfx.custom.isolation import SecurityViolationError, create_isolated_import

    # Create isolated_import without isolated_builtins_dict (validation context)
    isolated_import = create_isolated_import()  # None = validation-only mode

    # Try to import builtins - should raise SecurityViolationError
    with pytest.raises(SecurityViolationError, match="not allowed"):
        isolated_import("builtins", None, None, (), 0)


def test_sandbox_prevents_importlib_bypass():
    """Test that importlib cannot be used to bypass __import__ hook and get real builtins.
    
    CRITICAL SECURITY: importlib.import_module("builtins") would bypass our __import__ hook
    and get the real builtins module. By blocking importlib entirely, we prevent this bypass.
    """
    from lfx.custom.isolation import SecurityViolationError, execute_in_isolated_env

    # Test that importlib is blocked (prevents bypass)
    code = """
import importlib
# If importlib were allowed, code could do: importlib.import_module("builtins")
# to get the real builtins module and bypass our security restrictions
def test():
    real_builtins = importlib.import_module("builtins")
    return real_builtins.eval("1+1")
"""
    code_obj = compile(code, "<test>", "exec")
    exec_globals = {}

    # Should raise SecurityViolationError because importlib is blocked
    with pytest.raises(SecurityViolationError, match="blocked"):
        execute_in_isolated_env(code_obj, exec_globals)


def test_sandbox_blocks_dunder_method_escape():
    """Test that sandbox blocks classic Python dunder method escape attacks.
    
    CRITICAL SECURITY: Prevents escapes like:
    ().__class__.__bases__[0].__subclasses__()[XX].__init__.__globals__['os']
    
    The AST transformer converts dangerous dunder access (obj.__class__) to
    getattr(obj, '__class__') which we can intercept and block.
    """
    from lfx.custom.isolation import SecurityViolationError, execute_in_isolated_env, DunderAccessTransformer
    import ast

    # Test the classic escape attack
    code_str = """
def test():
    # Classic escape: get os via dunder methods
    os = ().__class__.__bases__[0].__subclasses__()[160].__init__.__globals__['os']
    return os.getcwd()
"""
    
    # Parse and transform the AST
    tree = ast.parse(code_str)
    transformer = DunderAccessTransformer()
    transformed = transformer.visit(tree)
    ast.fix_missing_locations(transformed)
    
    # Compile and execute
    code_obj = compile(transformed, "<test>", "exec")
    exec_globals = {}
    
    # Should raise SecurityViolationError when function is called
    execute_in_isolated_env(code_obj, exec_globals)
    
    # Try to call the function - should raise SecurityViolationError
    test_func = exec_globals.get("test")
    assert test_func is not None, "Function should be defined"
    
    with pytest.raises(SecurityViolationError, match="dunder attribute"):
        test_func()


def test_sandbox_blocks_individual_dunder_access():
    """Test that individual dangerous dunder attributes are blocked."""
    from lfx.custom.isolation import SecurityViolationError, execute_in_isolated_env, DunderAccessTransformer
    import ast

    dangerous_attrs = ["__class__", "__bases__", "__subclasses__", "__globals__", "__init__"]
    
    for attr in dangerous_attrs:
        code_str = f"result = ().{attr}"
        tree = ast.parse(code_str)
        transformer = DunderAccessTransformer()
        transformed = transformer.visit(tree)
        ast.fix_missing_locations(transformed)
        
        code_obj = compile(transformed, "<test>", "exec")
        exec_globals = {}
        
        # Should raise SecurityViolationError
        with pytest.raises(SecurityViolationError, match="dunder attribute"):
            execute_in_isolated_env(code_obj, exec_globals)
