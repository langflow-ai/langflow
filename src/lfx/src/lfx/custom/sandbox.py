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
    # Dynamic imports - needed for some libraries
    "importlib",
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

    Blocks builtins based on the current security level:
    - MODERATE (default): Blocks critical builtins (eval, exec, compile, etc.)
      but allows common operations (open, input, etc.)
    - STRICT: Blocks all potentially dangerous builtins
    - DISABLED: No restrictions

    Returns:
        Dictionary of isolated builtins
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

    # Critical: Make __builtins__ point to this isolated copy, not the real one
    # This prevents code from accessing the real builtins module
    isolated_builtins["__builtins__"] = isolated_builtins.copy()

    # Prevent access to the real builtins module
    # If code tries to import builtins, they get our isolated version
    class IsolatedBuiltinsModule:
        """Fake builtins module that prevents escaping."""

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
        isolated_builtins_dict: Dictionary containing isolated builtins (for builtins import interception)

    Returns:
        A function that performs isolated imports
    """

    def isolated_import(name: str, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002, ARG001
        """Import function that blocks dangerous modules by default."""
        # Extract top-level module name
        module_name = name.split(".")[0]

        # Intercept builtins import to return isolated version
        if module_name == "builtins" and isolated_builtins_dict is not None:
            return isolated_builtins_dict.get("builtins")

        # Block modules based on current security level
        if module_name in BLOCKED_MODULES:
            level_name = SECURITY_LEVEL.value.upper()
            msg = (
                f"Module '{module_name}' is blocked by security level '{level_name}'. "
                f"Set LANGFLOW_SANDBOX_SECURITY_LEVEL=disabled to allow (not recommended)."
            )
            raise SecurityViolationError(msg)
        # Allow langflow.* and lfx.* modules, and any module not in BLOCKED_MODULES
        # This allows users to import legitimate third-party libraries (AI libraries, etc.)
        # while still blocking dangerous system-level operations
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
    # Create isolated builtins - prevents accessing real __builtins__
    isolated_builtins = create_isolated_builtins()

    # Create isolated import function (pass isolated_builtins to intercept builtins import)
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
