"""Isolation functions for builtins and imports."""

import builtins
import contextlib
import importlib
from typing import Any

from lfx.custom.isolation.config import (
    SecurityViolationError,
    get_blocked_builtins,
    get_blocked_modules,
    get_security_level,
)


def create_isolated_builtins() -> dict[str, Any]:
    """Create an isolated set of builtins to prevent escaping isolation.

    This function creates an isolated version of Python's builtins that blocks dangerous
    functions while allowing safe ones. It handles TWO attack vectors:

    1. Direct builtin access: Code can access builtins via `__builtins__` dict or directly
       (e.g., `eval()`, `__builtins__['eval']`). Solution: Create isolated dict with
       dangerous builtins removed.

    2. Builtins module import: Code can do `import builtins; builtins.eval()` to get
       the real builtins module. Solution: Create IsolatedBuiltinsModule that returns
       our isolated version instead of the real one.

    Blocks builtins based on the current security level:
    - MODERATE (default): Blocks critical builtins (eval, exec, compile, open, etc.)
      but allows common operations (HTTP requests, async, temp files, etc.)
    - STRICT: Blocks all potentially dangerous builtins.
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
    blocked_builtins = get_blocked_builtins()
    for name in dir(builtins):
        if not name.startswith("_"):
            # Block builtins based on current security level
            if name in blocked_builtins:
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
        """Fake builtins module that prevents escape via `import builtins`.

        When code executes `import builtins`, Python's import system calls __import__("builtins").
        Our isolated_import function intercepts this and returns an instance of this class
        instead of the real builtins module. This prevents code from accessing dangerous
        builtins like eval, exec, __import__, etc.
        """

        def __getattr__(self, name: str) -> Any:
            # Block builtins based on current security level
            blocked_builtins = get_blocked_builtins()
            if name in blocked_builtins:
                level_name = get_security_level().value.upper()
                msg = (
                    f"Builtin '{name}' is blocked by security level '{level_name}'. "
                    f"Configure isolation_security_level setting to change this."
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
            Required when executing code in isolated environment (execute_in_isolated_env) to prevent
            `import builtins` bypass. Can be None when only validating imports (validate_code) - in
            that case, `import builtins` will be blocked with an error rather than returning the
            isolated version.

    Returns:
        A function that performs isolated imports (replaces Python's __import__)
    """

    def isolated_import(name: str, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002, ARG001
        """Import function that blocks dangerous modules by default.

        This function replaces Python's built-in __import__ to prevent isolation escapes.
        When code executes `import X`, Python calls __import__("X"), which calls this function.

        Note: The globals, locals, fromlist, and level parameters are required to match
        Python's __import__ signature, but we don't use them. Python's import system will
        call this function with all these arguments, so we must accept them for compatibility.
        We only need the `name` parameter to determine which module is being imported.
        """
        # Extract top-level module name (e.g., "os.path" -> "os")
        module_name = name.split(".")[0]

        # CRITICAL SECURITY: Block `import builtins` to prevent isolation escape
        if module_name == "builtins":
            if isolated_builtins_dict is None:
                # Validation context: No isolated builtins available, so block the import
                msg = (
                    "Import of 'builtins' module is not allowed. "
                    "This is a security restriction to prevent isolation escape."
                )
                raise SecurityViolationError(msg)
            isolated_builtins_module = isolated_builtins_dict.get("builtins")
            if isolated_builtins_module is None:
                # Safety check: Should never happen if create_isolated_builtins() worked correctly
                msg = (
                    "Import of 'builtins' module is not allowed. "
                    "This is a security restriction to prevent isolation escape."
                )
                raise SecurityViolationError(msg)
            # Return the fake IsolatedBuiltinsModule, not the real builtins module
            return isolated_builtins_module

        # Block modules based on current security level
        blocked_modules = get_blocked_modules()
        if module_name in blocked_modules:
            level_name = get_security_level().value.upper()
            msg = (
                f"Module '{module_name}' is blocked by security level '{level_name}'. "
                f"Configure isolation_security_level setting to change this."
            )
            raise SecurityViolationError(msg)

        # Allow all other modules (whitelist approach)
        # This allows users to import legitimate third-party libraries (AI libraries, utilities, etc.)
        # while still blocking dangerous system-level operations.
        return importlib.import_module(name)

    return isolated_import
