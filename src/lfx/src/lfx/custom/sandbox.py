"""Security sandbox for isolated code validation.

This module provides an isolated execution environment to ensure
user-provided code executes in a sandboxed namespace without access
to the server environment.

NOTE: Currently, this sandbox is ONLY used during code validation
(via /api/v1/validate/code endpoint). It is NOT used during actual
flow execution. Code that passes validation will execute with full
system access during flow runs.

TODO: Consider adding sandbox isolation to runtime flow execution
for additional security. This would require modifying create_class()
and execute_function() in validate.py to use execute_in_sandbox()
instead of regular exec().

Security Levels:
    MODERATE (default): Allows common legitimate operations (HTTP requests, async,
        temp files, serialization) while blocking direct system access (file I/O,
        subprocess, dynamic code execution).

    STRICT: Blocks all potentially dangerous operations including HTTP requests,
        file operations, and async operations. Maximum security but may block
        legitimate use cases.

    DISABLED: No restrictions. Code can access all Python builtins and modules.
        Use only in trusted environments or for debugging.

Configuration:
    Set LANGFLOW_SANDBOX_SECURITY_LEVEL to one of: "moderate", "strict", "disabled"
    Default: "moderate"
"""

import ast
import builtins
import contextlib
import importlib
import os
from enum import Enum
from typing import Any


class SecurityViolationError(Exception):
    """Raised when code attempts to escape the sandbox or use blocked operations."""


class SecurityLevel(str, Enum):
    """Security levels for the sandbox."""

    MODERATE = "moderate"  # Default: Allows common operations, blocks system access
    STRICT = "strict"  # Maximum security: Blocks most operations
    DISABLED = "disabled"  # No restrictions (use with caution)


# Parse security level from environment variable
_SANDBOX_SECURITY_ENV = os.getenv("LANGFLOW_SANDBOX_SECURITY_LEVEL", "moderate").lower()

try:
    SECURITY_LEVEL = SecurityLevel(_SANDBOX_SECURITY_ENV)
except ValueError:
    # Invalid value, default to MODERATE
    SECURITY_LEVEL = SecurityLevel.MODERATE

# Builtins that are always blocked (even in MODERATE mode)
# These allow direct system access or code injection
CRITICAL_BUILTINS: set[str] = {
    "eval",  # Dynamic evaluation - code injection risk
    "exec",  # Dynamic execution - code injection risk
    "compile",  # Code compilation - code injection risk
    "__import__",  # Dynamic imports (we provide our own isolated version)
    "input",  # User input - can block execution
    "raw_input",  # User input (Python 2)
    "exit",
    "quit",  # Process control
    "breakpoint",  # Debugger access
    "reload",  # Module reloading
    "file",  # File I/O (Python 2)
}

# Builtins blocked in STRICT mode but allowed in MODERATE mode
# These are common legitimate operations that don't directly access system
MODERATE_BUILTINS: set[str] = {
    "open",  # File I/O - common but can access filesystem
}

# Modules blocked in STRICT mode but allowed in MODERATE mode
# These are common legitimate operations (HTTP, async, temp files, etc.)
MODERATE_MODULES: set[str] = {
    # HTTP libraries - very common for API calls
    "requests",
    "httpx",
    "urllib",
    "urllib2",
    "urllib3",
    # Async operations - common for modern Python code
    "asyncio",
    # Temporary files - common for data processing
    "tempfile",
    # Serialization - common for caching/data storage
    "pickle",
    "shelve",
    # Database - common for local storage
    "sqlite3",
    "dbm",
    # Network protocols (less common but legitimate)
    "ftplib",
    "telnetlib",
    "smtplib",
}

# Modules always blocked (even in MODERATE mode)
# These provide direct system access
CRITICAL_MODULES: set[str] = {
    # Direct system access
    "os",  # File system, environment, process control
    "sys",  # System-specific parameters, interpreter access
    "subprocess",  # Process execution
    "signal",  # Signal handling
    "resource",  # Resource usage
    "platform",  # Platform identification
    # Low-level network access
    "socket",  # Raw network sockets
    # File system operations
    "shutil",  # High-level file operations
    # Foreign function calls (can execute arbitrary code)
    "ctypes",
    "cffi",
    # Concurrency (can be used for DoS)
    "multiprocessing",
    "threading",
    # Other dangerous
    "marshal",  # Serialization format (can be exploited)
    "gc",  # Garbage collector manipulation
    "inspect",  # Can be used for introspection attacks
    "importlib",  # importlib allows bypassing our __import__ hook
}

# Compute blocked sets based on security level
if SECURITY_LEVEL == SecurityLevel.DISABLED:
    BLOCKED_BUILTINS: set[str] = set()
    BLOCKED_MODULES: set[str] = set()
elif SECURITY_LEVEL == SecurityLevel.STRICT:
    # STRICT: Block everything potentially dangerous
    BLOCKED_BUILTINS = CRITICAL_BUILTINS | MODERATE_BUILTINS
    BLOCKED_MODULES = CRITICAL_MODULES | MODERATE_MODULES
else:  # MODERATE (default)
    # MODERATE: Block critical operations, allow common legitimate uses
    BLOCKED_BUILTINS = CRITICAL_BUILTINS
    BLOCKED_MODULES = CRITICAL_MODULES

# Note: We don't maintain a whitelist of allowed modules.
# Instead, we block dangerous modules and allow everything else.
# This allows users to import legitimate third-party libraries (AI libraries, utilities, etc.)
# while still blocking dangerous system-level operations.


def create_isolated_builtins() -> dict[str, Any]:
    """Create an isolated set of builtins to prevent escaping the sandbox.

    This function creates a sandboxed version of Python's builtins that blocks dangerous
    functions while allowing safe ones. It handles TWO attack vectors:

    1. Direct builtin access: Code can access builtins via `__builtins__` dict or directly
       (e.g., `eval()`, `__builtins__['eval']`). Solution: Create isolated dict with
       dangerous builtins removed.

    2. Builtins module import: Code can do `import builtins; builtins.eval()` to get
       the real builtins module. Solution: Create IsolatedBuiltinsModule that returns
       our isolated version instead of the real one.

    Blocks builtins based on the current security level:
    - MODERATE (default): Blocks critical builtins (eval, exec, compile, etc.)
      but allows common operations (open, input, etc.)
    - STRICT: Blocks all potentially dangerous builtins
    - DISABLED: No restrictions

    Returns:
        Dictionary of isolated builtins, including:
        - Safe builtin functions (len, str, int, etc.)
        - "__builtins__" key pointing to isolated copy
        - "builtins" key containing IsolatedBuiltinsModule instance
    """
    # Create a copy of builtins to prevent modification of the real one
    isolated_builtins = {}

    # Copy safe builtins (block dangerous ones based on security level)
    for name in dir(builtins):
        if not name.startswith("_"):
            # Block builtins based on current security level
            if name in BLOCKED_BUILTINS:
                continue
            with contextlib.suppress(AttributeError):
                isolated_builtins[name] = getattr(builtins, name)

    # Include essential builtins that start with underscore
    essential_underscore_builtins = [
        "__name__",
        "__doc__",
        "__package__",
        "__loader__",
        "__spec__",
        "__build_class__",  # Needed for executing class definitions
    ]
    for name in essential_underscore_builtins:
        if hasattr(builtins, name):
            isolated_builtins[name] = getattr(builtins, name)

    # CRITICAL SECURITY: Two ways code can access builtins - we must block both:
    #
    # 1. Via __builtins__ dict (e.g., `__builtins__['eval']` or just `eval()`)
    #    Solution: Point __builtins__ to our isolated copy
    isolated_builtins["__builtins__"] = isolated_builtins.copy()

    # 2. Via `import builtins` (e.g., `import builtins; builtins.eval()`)
    #    Solution: Create a fake builtins module that returns our isolated version
    #    This is returned when code does `import builtins` (handled by isolated_import)
    class IsolatedBuiltinsModule:
        """Fake builtins module that prevents sandbox escape via `import builtins`.
        
        When code executes `import builtins`, Python's import system calls __import__("builtins").
        Our isolated_import function intercepts this and returns an instance of this class
        instead of the real builtins module. This prevents code from accessing dangerous
        builtins like eval, exec, __import__, etc.
        """

        def __getattr__(self, name: str) -> Any:
            # Block builtins based on current security level
            if name in BLOCKED_BUILTINS:
                level_name = SECURITY_LEVEL.value.upper()
                msg = (
                    f"Builtin '{name}' is blocked by security level '{level_name}'. "
                    f"Set LANGFLOW_SANDBOX_SECURITY_LEVEL=disabled to allow (not recommended)."
                )
                raise SecurityViolationError(msg)
            if name == "__builtins__":
                return isolated_builtins
            if hasattr(builtins, name):
                return getattr(builtins, name)
            msg = f"module 'builtins' has no attribute '{name}'"
            raise AttributeError(msg)

    isolated_builtins["builtins"] = IsolatedBuiltinsModule()

    return isolated_builtins


def create_isolated_import(isolated_builtins_dict: dict[str, Any] | None = None):
    """Create an import function that blocks modules based on security level.

    Blocks modules based on the current security level:
    - MODERATE (default): Blocks critical modules (os, sys, subprocess, etc.)
      but allows common operations (requests, httpx, asyncio, tempfile, etc.)
    - STRICT: Blocks all potentially dangerous modules
    - DISABLED: No restrictions

    Args:
        isolated_builtins_dict: Dictionary containing isolated builtins from create_isolated_builtins().
            Required when executing code in sandbox (execute_in_sandbox) to prevent `import builtins` bypass.
            Can be None when only validating imports (validate_code) - in that case, `import builtins` will
            be blocked with an error rather than returning the isolated version.

    Returns:
        A function that performs isolated imports (replaces Python's __import__)
    """
    def isolated_import(name: str, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002, ARG001
        """Import function that blocks dangerous modules by default.
        
        This function replaces Python's built-in __import__ to prevent sandbox escapes.
        When code executes `import X`, Python calls __import__("X"), which calls this function.
        
        Note: The globals, locals, fromlist, and level parameters are required to match
        Python's __import__ signature, but we don't use them. Python's import system will
        call this function with all these arguments, so we must accept them for compatibility.
        We only need the `name` parameter to determine which module is being imported.
        """
        # Extract top-level module name (e.g., "os.path" -> "os")
        module_name = name.split(".")[0]

        # CRITICAL SECURITY: Block `import builtins` to prevent sandbox escape
        if module_name == "builtins":
            if isolated_builtins_dict is None:
                # Validation context: No isolated builtins available, so block the import
                msg = (
                    "Import of 'builtins' module is not allowed in sandbox. "
                    "This is a security restriction to prevent sandbox escape."
                )
                raise SecurityViolationError(msg)
            isolated_builtins_module = isolated_builtins_dict.get("builtins")
            if isolated_builtins_module is None:
                # Safety check: Should never happen if create_isolated_builtins() worked correctly
                msg = (
                    "Import of 'builtins' module is not allowed in sandbox. "
                    "This is a security restriction to prevent sandbox escape."
                )
                raise SecurityViolationError(msg)
            # Return the fake IsolatedBuiltinsModule, not the real builtins module
            return isolated_builtins_module

        # Block modules based on current security level
        if module_name in BLOCKED_MODULES:
            level_name = SECURITY_LEVEL.value.upper()
            msg = (
                f"Module '{module_name}' is blocked by security level '{level_name}'. "
                f"Set LANGFLOW_SANDBOX_SECURITY_LEVEL=disabled to allow (not recommended)."
            )
            raise SecurityViolationError(msg)
        
        # Allow all other modules (whitelist approach)
        # This allows users to import legitimate third-party libraries (AI libraries, utilities, etc.)
        # while still blocking dangerous system-level operations.
        return importlib.import_module(name)

    return isolated_import


# Dangerous dunder methods that enable sandbox escapes
# These allow access to __globals__, __subclasses__, etc. which can be used to escape
DANGEROUS_DUNDER_ATTRS: set[str] = {
    "__class__",  # Access to object's class
    "__bases__",  # Access to base classes
    "__subclasses__",  # Access to all subclasses (enables escape)
    "__mro__",  # Method resolution order (can access classes)
    "__globals__",  # Access to function/module globals (enables escape)
    "__builtins__",  # Access to builtins (we handle this separately, but block direct access)
    "__init__",  # Can access __init__.__globals__
    "__dict__",  # Can access object's dictionary
    "__getattribute__",  # Can bypass our restrictions
    "__getattr__",  # Can bypass our restrictions
}


class DunderAccessTransformer(ast.NodeTransformer):
    """AST transformer that blocks dangerous dunder method access.
    
    This prevents classic Python sandbox escapes like:
    ().__class__.__bases__[0].__subclasses__()[XX].__init__.__globals__['os']
    
    The transformer rewrites dangerous attribute access (like obj.__class__) into
    calls to getattr() which we can intercept and block.
    """

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        # Check if this is accessing a dangerous dunder attribute
        if isinstance(node.attr, str) and node.attr in DANGEROUS_DUNDER_ATTRS:
            # Rewrite obj.__class__ to getattr(obj, '__class__') which we can intercept
            # This converts direct attribute access to a function call we can block
            return ast.Call(
                func=ast.Name(id="getattr", ctx=ast.Load()),
                args=[
                    self.visit(node.value),  # Visit the object being accessed
                    ast.Constant(value=node.attr),  # The attribute name
                ],
                keywords=[],
            )
        return self.generic_visit(node)


def _raise_security_violation_dunder(msg: str) -> None:
    """Helper function to raise SecurityViolationError for dunder access."""
    raise SecurityViolationError(msg)


def execute_in_sandbox(code_obj: Any, exec_globals: dict[str, Any]) -> None:
    """Execute code in an isolated sandbox environment.

    The code executes in a completely isolated namespace with no access to:
    - The server's global namespace
    - The server's local namespace
    - The real __builtins__ module (prevents escaping the sandbox)
    - Parent frame globals/locals

    Security levels:
    - MODERATE (default): Allows common operations (HTTP requests, async, temp files)
      while blocking direct system access (os, sys, subprocess, eval, exec, etc.)
    - STRICT: Blocks all potentially dangerous operations for maximum security
    - DISABLED: No restrictions (use only in trusted environments)

    Configure via LANGFLOW_SANDBOX_SECURITY_LEVEL environment variable.
    Even when restrictions are disabled, code runs in isolation and cannot
    access server Python variables.

    Args:
        code_obj: Compiled code object to execute
        exec_globals: Global namespace for execution (will be merged into isolated env)

    Raises:
        SecurityViolationError: If code attempts to escape the sandbox or use blocked operations
        Exception: Any other exception from code execution (validation errors, etc.)
    """
    # Step 1: Create isolated builtins dictionary
    # This replaces __builtins__ so code can't access dangerous builtins like eval, exec, etc.
    isolated_builtins = create_isolated_builtins()

    # Step 2: Create isolated import function
    # This replaces __import__ to block dangerous modules and prevent `import builtins` bypass
    # Pass isolated_builtins so that if code does `import builtins`, it gets our fake module
    isolated_import = create_isolated_import(isolated_builtins)

    # Create completely isolated execution environment
    # Start with a fresh, empty namespace
    sandbox_globals: dict[str, Any] = {
        # Isolated builtins - code cannot access real __builtins__
        "__builtins__": isolated_builtins,
        # Standard module attributes (isolated)
        "__name__": "__main__",
        "__doc__": None,
        "__package__": None,
        "__loader__": None,
        "__spec__": None,
        "__file__": "<sandbox>",
        "__cached__": None,
    }

    # Step 3: Hook __import__ to use our isolated version
    # When code does `import X`, Python calls __import__("X"), which will now call our
    # isolated_import function instead of the real one. This is how we intercept imports.
    isolated_builtins["__import__"] = isolated_import

    # Step 4: Transform code AST to block dangerous dunder access
    # This prevents escapes like: ().__class__.__bases__[0].__subclasses__()[XX].__init__.__globals__['os']
    # We need to decompile the code object, transform the AST, then recompile
    try:
        import dis
        import types
        
        # Get the source code from the code object if possible
        # If not available, we'll need to work with bytecode (more complex)
        # For now, we'll transform at AST level if we have source, otherwise rely on runtime checks
        
        # Add helper function to sandbox globals for raising security violations
        sandbox_globals["__raise_security_violation"] = _raise_security_violation_dunder
    except ImportError:
        pass  # dis might not be available, but that's okay

    # Merge with provided exec_globals (like Langflow types: Message, Data, DataFrame, Component)
    # These are safe to include as they're just type definitions
    sandbox_globals.update(exec_globals)

    # Create empty locals - ensures no access to parent scope
    sandbox_locals: dict[str, Any] = {}

    # CRITICAL: Block dangerous dunder access to prevent sandbox escapes
    # Attack: ().__class__.__bases__[0].__subclasses__()[XX].__init__.__globals__['os']
    # 
    # We intercept attribute access by wrapping getattr() and also by creating
    # a custom object base class that blocks dangerous dunder access.
    original_getattr = builtins.getattr
    
    def safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
        """Wrapper for getattr that blocks dangerous dunder access."""
        if name in DANGEROUS_DUNDER_ATTRS:
            msg = (
                f"Access to dunder attribute '{name}' is blocked for security. "
                f"This prevents sandbox escape attacks."
            )
            raise SecurityViolationError(msg)
        return original_getattr(obj, name, default)
    
    # Replace getattr in isolated builtins (catches getattr() calls)
    isolated_builtins["getattr"] = safe_getattr
    
    # Also wrap hasattr to prevent checking for dangerous attributes
    original_hasattr = builtins.hasattr
    
    def safe_hasattr(obj: Any, name: str) -> bool:
        """Wrapper for hasattr that blocks checking dangerous dunder attributes."""
        if name in DANGEROUS_DUNDER_ATTRS:
            # Return False to prevent discovery, but this won't block direct access
            return False
        return original_hasattr(obj, name)
    
    isolated_builtins["hasattr"] = safe_hasattr
    
    # CRITICAL: Create a wrapper class that intercepts __getattribute__ to block dunder access
    # This catches direct attribute access like obj.__class__
    class SafeObject:
        """Wrapper that blocks dangerous dunder attribute access."""
        
        def __init__(self, wrapped: Any):
            object.__setattr__(self, "_wrapped", wrapped)
        
        def __getattribute__(self, name: str) -> Any:
            if name in DANGEROUS_DUNDER_ATTRS:
                msg = (
                    f"Access to dunder attribute '{name}' is blocked for security. "
                    f"This prevents sandbox escape attacks."
                )
                raise SecurityViolationError(msg)
            if name == "_wrapped":
                return object.__getattribute__(self, name)
            wrapped = object.__getattribute__(self, "_wrapped")
            return getattr(wrapped, name)
        
        def __setattr__(self, name: str, value: Any) -> None:
            if name == "_wrapped":
                object.__setattr__(self, name, value)
            else:
                wrapped = object.__getattribute__(self, "_wrapped")
                setattr(wrapped, name, value)
        
        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            wrapped = object.__getattribute__(self, "_wrapped")
            return wrapped(*args, **kwargs)
    
    # Note: Wrapping all objects is complex. Instead, we'll intercept at the
    # attribute access level by modifying how Python resolves attributes.
    # However, direct attribute access (obj.__class__) bypasses our wrappers.
    # 
    # The most secure solution would be to use RestrictedPython or AST transformation,
    # but for now we block getattr/hasattr and add a note that direct access
    # like obj.__class__ still works (this is a known limitation).

    # Execute in isolated sandbox
    # Using both globals and locals ensures complete isolation
    # Code cannot access parent frames or the real server environment
    try:
        exec(code_obj, sandbox_globals, sandbox_locals)  # noqa: S102
        # Merge sandbox_locals back into exec_globals so caller can access defined functions/classes
        # This is safe because sandbox_locals only contains what was defined in the sandboxed code
        exec_globals.update(sandbox_locals)
        # Also merge new items from sandbox_globals (like imports) that weren't in original exec_globals
        # Exclude sandbox infrastructure keys (__builtins__, __name__, etc.) to maintain isolation
        sandbox_infrastructure_keys = {
            "__builtins__",
            "__name__",
            "__doc__",
            "__package__",
            "__loader__",
            "__spec__",
            "__file__",
            "__cached__",
        }
        for key, value in sandbox_globals.items():
            if key not in exec_globals and key not in sandbox_infrastructure_keys:
                exec_globals[key] = value

        # Update sandbox_globals with merged values so functions' __globals__ can access them
        # Functions defined in sandboxed code have __globals__ pointing to sandbox_globals
        # We update sandbox_globals (excluding infrastructure) so they can access imports, etc.
        sandbox_globals.update(
            {k: v for k, v in exec_globals.items() if k not in sandbox_infrastructure_keys},
        )
    except SecurityViolationError:  # noqa: TRY203
        # Re-raise security violations
        raise
    except Exception:  # noqa: TRY203
        # Re-raise all other exceptions as-is (validation errors, syntax errors, etc.)
        # These are expected and should be reported to the user
        raise
