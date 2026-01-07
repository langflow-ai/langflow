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
    functions while allowing safe ones. Code can access builtins via `__builtins__` dict
    or directly (e.g., `eval()`, `__builtins__['eval']`). We create an isolated dict with
    dangerous builtins removed.

    Note: `import builtins` is blocked entirely by create_isolated_import(). Code can use
    builtins directly (print(), len(), str(), etc.) without importing the builtins module.

    Blocks builtins based on the current security level:
    - MODERATE (default): Blocks critical builtins (eval, exec, compile, open, etc.)
      but allows common operations (print, len, str, dict, list, etc.)
    - STRICT: Blocks all potentially dangerous builtins.
    - DISABLED: No restrictions

    Returns:
        Dictionary of isolated builtins, including:
        - Safe builtin functions (len, str, int, etc.)
        - "__builtins__" key pointing to isolated copy
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

    # CRITICAL SECURITY: Block access to real builtins module
    # Code can access builtins via __builtins__ dict (e.g., `__builtins__['eval']` or just `eval()`)
    # Solution: Point __builtins__ to our isolated copy with dangerous builtins removed
    isolated_builtins["__builtins__"] = isolated_builtins.copy()

    # Note: `import builtins` is blocked entirely by create_isolated_import()
    # Code can use builtins directly (print(), len(), etc.) without importing

    return isolated_builtins


def create_isolated_import():
    """Create an import function that blocks modules based on security level.

    Blocks modules based on the current security level:
    - MODERATE (default): Blocks critical modules (os, sys, subprocess, etc.)
      but allows common operations (requests, httpx, asyncio, tempfile, etc.)
    - STRICT: Blocks all potentially dangerous modules
    - DISABLED: No restrictions

    Note: `import builtins` is always blocked. Code can use builtins directly
    (print(), len(), str(), etc.) without importing the builtins module.

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

        # CRITICAL SECURITY: Block `import builtins` entirely to prevent isolation escape
        # Code can use builtins directly (print(), len(), str(), etc.) without importing
        # There's no legitimate need to import the builtins module
        if module_name == "builtins":
            msg = (
                "Import of 'builtins' module is not allowed. "
                "This is a security restriction to prevent isolation escape. "
                "Use builtins directly (e.g., print(), len(), str()) instead of importing builtins."
            )
            raise SecurityViolationError(msg)

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
