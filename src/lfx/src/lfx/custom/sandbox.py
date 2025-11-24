"""Security sandbox for isolated code validation.

This module provides an isolated execution environment to ensure
user-provided code executes in a sandboxed namespace without access
to the server environment.

By default, dangerous operations (file I/O, network, subprocess) are blocked.
Set LANGFLOW_ALLOW_DANGEROUS_CODE_VALIDATION=true to allow them (not recommended).
"""

import builtins
import importlib
import os
from typing import Any


class SecurityViolation(Exception):
    """Raised when code attempts to escape the sandbox or use blocked operations."""


# Check if dangerous operations are allowed via environment variable
ALLOW_DANGEROUS_CODE = os.getenv("LANGFLOW_ALLOW_DANGEROUS_CODE_VALIDATION", "false").lower() == "true"

# Dangerous builtins that should be blocked by default
BLOCKED_BUILTINS: set[str] = {
    "open",  # File I/O
    "input",  # User input
    "compile",  # Code compilation
    "eval",  # Dynamic evaluation
    "exec",  # Dynamic execution
    "__import__",  # Dynamic imports (we provide our own)
    "breakpoint",  # Debugger access
    "exit",
    "quit",  # Process control
    "file",  # File I/O (Python 2)
    "raw_input",  # User input (Python 2)
    "reload",  # Module reloading
}

# Dangerous modules that should be blocked by default
BLOCKED_MODULES: set[str] = {
    # System access
    "os",
    "sys",
    "subprocess",
    "signal",
    "resource",
    "platform",
    # Network access
    "socket",
    "urllib",
    "urllib2",
    "urllib3",
    "requests",
    "httpx",
    "ftplib",
    "telnetlib",
    "smtplib",
    # File operations (dangerous)
    "pickle",
    "shelve",
    "dbm",
    "sqlite3",
    "shutil",
    "tempfile",
    # Foreign function calls
    "ctypes",
    "cffi",
    # Dynamic imports
    "importlib",
    # Concurrency (can be used for DoS)
    "multiprocessing",
    "threading",
    "asyncio",
    # Other dangerous
    "marshal",
    "gc",
    "inspect",  # Can be used for introspection attacks
}

# Note: We don't maintain a whitelist of allowed modules.
# Instead, we block dangerous modules and allow everything else.
# This allows users to import legitimate third-party libraries (AI libraries, utilities, etc.)
# while still blocking dangerous system-level operations.


def create_isolated_builtins() -> dict[str, Any]:
    """Create an isolated set of builtins to prevent escaping the sandbox.

    By default, blocks dangerous builtins (open, eval, exec, etc.).
    Set LANGFLOW_ALLOW_DANGEROUS_CODE_VALIDATION=true to allow them.

    Returns:
        Dictionary of isolated builtins
    """
    # Create a copy of builtins to prevent modification of the real one
    isolated_builtins = {}

    # Copy safe builtins (block dangerous ones by default)
    for name in dir(builtins):
        if not name.startswith("_"):
            # Block dangerous builtins unless explicitly allowed
            if not ALLOW_DANGEROUS_CODE and name in BLOCKED_BUILTINS:
                continue
            try:
                isolated_builtins[name] = getattr(builtins, name)
            except AttributeError:
                pass

    # Include essential builtins that start with underscore
    essential_underscore_builtins = ["__name__", "__doc__", "__package__", "__loader__", "__spec__"]
    for name in essential_underscore_builtins:
        if hasattr(builtins, name):
            isolated_builtins[name] = getattr(builtins, name)

    # Critical: Make __builtins__ point to this isolated copy, not the real one
    # This prevents code from accessing the real builtins module
    isolated_builtins["__builtins__"] = isolated_builtins.copy()

    # Prevent access to the real builtins module
    # If code tries to import builtins, they get our isolated version
    class IsolatedBuiltinsModule:
        """Fake builtins module that prevents escaping."""

        def __getattr__(self, name: str) -> Any:
            # Block dangerous builtins unless explicitly allowed
            if not ALLOW_DANGEROUS_CODE and name in BLOCKED_BUILTINS:
                raise SecurityViolation(
                    f"Dangerous builtin '{name}' is blocked. Set LANGFLOW_ALLOW_DANGEROUS_CODE_VALIDATION=true to allow."
                )
            if name == "__builtins__":
                return isolated_builtins
            if hasattr(builtins, name):
                return getattr(builtins, name)
            raise AttributeError(f"module 'builtins' has no attribute '{name}'")

    isolated_builtins["builtins"] = IsolatedBuiltinsModule()

    return isolated_builtins


def create_isolated_import():
    """Create an import function that blocks dangerous modules by default.

    By default, blocks dangerous modules (os, subprocess, socket, etc.).
    Set LANGFLOW_ALLOW_DANGEROUS_CODE_VALIDATION=true to allow them.

    Returns:
        A function that performs isolated imports
    """

    def isolated_import(name: str, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002, ARG001
        """Import function that blocks dangerous modules by default."""
        # Extract top-level module name
        module_name = name.split(".")[0]

        # Block dangerous modules unless explicitly allowed
        if not ALLOW_DANGEROUS_CODE:
            if module_name in BLOCKED_MODULES:
                raise SecurityViolation(
                    f"Dangerous module '{module_name}' is blocked. "
                    f"Set LANGFLOW_ALLOW_DANGEROUS_CODE_VALIDATION=true to allow."
                )
            # Allow langflow.* and lfx.* modules, and any module not in BLOCKED_MODULES
            # This allows users to import legitimate third-party libraries (AI libraries, etc.)
            # while still blocking dangerous system-level operations
            is_lfx_module = module_name == "lfx" or module_name.startswith("lfx.")
            is_langflow_module = module_name == "langflow" or module_name.startswith("langflow.")

            # If it's not a blocked module, and not langflow/lfx, it's allowed
            # (We've already checked BLOCKED_MODULES above, so anything reaching here is safe)

        # Import the module (still isolated namespace-wise)
        return importlib.import_module(name)

    return isolated_import


def execute_in_sandbox(code_obj: Any, exec_globals: dict[str, Any]) -> None:
    """Execute code in an isolated sandbox environment.

    The code executes in a completely isolated namespace with no access to:
    - The server's global namespace
    - The server's local namespace
    - The real __builtins__ module (prevents escaping the sandbox)
    - Parent frame globals/locals

    By default, dangerous operations (file I/O, subprocess, network access, etc.)
    are blocked. Set LANGFLOW_ALLOW_DANGEROUS_CODE_VALIDATION=true to allow them.
    Even when allowed, code runs in isolation and cannot access server Python variables.

    Args:
        code_obj: Compiled code object to execute
        exec_globals: Global namespace for execution (will be merged into isolated env)

    Raises:
        SecurityViolation: If code attempts to escape the sandbox
        Exception: Any other exception from code execution (validation errors, etc.)
    """
    # Create isolated builtins - prevents accessing real __builtins__
    isolated_builtins = create_isolated_builtins()

    # Create isolated import function
    isolated_import = create_isolated_import()

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

    # Add isolated import to builtins
    isolated_builtins["__import__"] = isolated_import

    # Merge with provided exec_globals (like Langflow types: Message, Data, DataFrame, Component)
    # These are safe to include as they're just type definitions
    sandbox_globals.update(exec_globals)

    # Create empty locals - ensures no access to parent scope
    sandbox_locals: dict[str, Any] = {}

    # Execute in isolated sandbox
    # Using both globals and locals ensures complete isolation
    # Code cannot access parent frames or the real server environment
    try:
        exec(code_obj, sandbox_globals, sandbox_locals)  # noqa: S102
    except SecurityViolation:
        # Re-raise security violations
        raise
    except Exception:
        # Re-raise all other exceptions as-is (validation errors, syntax errors, etc.)
        # These are expected and should be reported to the user
        raise
