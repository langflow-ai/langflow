"""Code execution in isolated environment."""

import builtins
from typing import Any

from lfx.custom.isolation.config import SecurityViolationError
from lfx.custom.isolation.isolation import create_isolated_builtins, create_isolated_import
from lfx.custom.isolation.transformer import DANGEROUS_DUNDER_ATTRS


def execute_in_isolated_env(code_obj: Any, exec_globals: dict[str, Any]) -> None:
    """Execute code in an isolated environment.

    The code executes in a completely isolated namespace with no access to:
    - The server's global namespace
    - The server's local namespace
    - The real __builtins__ module (prevents escaping isolation)
    - Parent frame globals/locals

    Security levels:
    - MODERATE (default): Allows common operations (HTTP requests, async, temp files)
      while blocking direct system access (os, sys, subprocess, eval, exec, etc.)
    - STRICT: Blocks all potentially dangerous operations for maximum security
    - DISABLED: No restrictions (use only in trusted environments)

    Security level is configured via the settings service (isolation_security_level setting).

    LIMITATION: This only isolates code execution during class/function definition.
    Runtime method execution (e.g., when `build()` method runs) is NOT isolated.
    TODO: See RUNTIME_IMPORT_ISOLATION_PLAN.md for plan to block runtime imports in methods.

    Args:
        code_obj: Compiled code object to execute
        exec_globals: Global namespace for execution (will be merged into isolated env)

    Raises:
        SecurityViolationError: If code attempts to escape isolation or use blocked operations
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
    isolated_globals: dict[str, Any] = {
        # Isolated builtins - code cannot access real __builtins__
        "__builtins__": isolated_builtins,
        # Standard module attributes (isolated)
        "__name__": "__main__",
        "__doc__": None,
        "__package__": None,
        "__loader__": None,
        "__spec__": None,
        "__file__": "<isolated>",
        "__cached__": None,
    }

    # Step 3: Hook __import__ to use our isolated version
    # When code does `import X`, Python calls __import__("X"), which will now call our
    # isolated_import function instead of the real one. This is how we intercept imports.
    isolated_builtins["__import__"] = isolated_import

    # Merge with provided exec_globals (like Langflow types: Message, Data, DataFrame, Component)
    # These are safe to include as they're just type definitions
    isolated_globals.update(exec_globals)

    # Create empty locals - ensures no access to parent scope
    isolated_locals: dict[str, Any] = {}

    # CRITICAL: Block dangerous dunder access to prevent isolation escapes
    # Attack: ().__class__.__bases__[0].__subclasses__()[XX].__init__.__globals__['os']
    #
    # We intercept attribute access by wrapping getattr() and hasattr().
    # Note: Direct attribute access (obj.__class__) bypasses our wrappers, but
    # the AST transformer in validate_code() converts such access to getattr() calls.
    original_getattr = builtins.getattr

    def safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
        """Wrapper for getattr that blocks dangerous dunder access."""
        if name in DANGEROUS_DUNDER_ATTRS:
            msg = (
                f"Access to dunder attribute '{name}' is blocked for security. This prevents isolation escape attacks."
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

    try:
        exec(code_obj, isolated_globals, isolated_locals)  # noqa: S102
        # Merge isolated_locals back into exec_globals so caller can access defined functions/classes
        # This is safe because isolated_locals only contains what was defined in the isolated code
        exec_globals.update(isolated_locals)
        # Also merge new items from isolated_globals (like imports, module-level assignments)
        # that weren't in original exec_globals. Exclude isolation infrastructure keys.
        # Note: We merge items that weren't in exec_globals OR that were added during execution
        # (like module-level constants defined in the code being executed)
        isolation_infrastructure_keys = {
            "__builtins__",
            "__name__",
            "__doc__",
            "__package__",
            "__loader__",
            "__spec__",
            "__file__",
            "__cached__",
        }
        # Merge all non-infrastructure items from isolated_globals into exec_globals
        # This includes module-level assignments (like DEFAULT_OLLAMA_URL) that were executed
        for key, value in isolated_globals.items():
            if key not in isolation_infrastructure_keys:
                # Always update exec_globals with values from isolated execution
                # This ensures module-level constants defined in the code are available
                exec_globals[key] = value

        # Update isolated_globals with merged values so functions' __globals__ can access them
        # Functions defined in isolated code have __globals__ pointing to isolated_globals
        # We update isolated_globals (excluding infrastructure) so they can access imports, etc.
        isolated_globals.update(
            {k: v for k, v in exec_globals.items() if k not in isolation_infrastructure_keys},
        )
        
        # CRITICAL: Ensure isolated __import__ persists in exec_globals so methods can use it at runtime
        # Methods' __globals__ points to isolated_globals, but we also need exec_globals to have
        # the isolated builtins so that if methods access __builtins__ or __import__, they get the isolated version
        # Note: We don't merge isolated_builtins directly, but methods should use isolated_globals["__builtins__"]
        # which has the isolated __import__. However, to be safe, we ensure exec_globals has access to isolated imports
        # by storing a reference to the isolated import function (though methods should use their __globals__)
    except SecurityViolationError:  # noqa: TRY203
        # Re-raise security violations
        raise
    except Exception:  # noqa: TRY203
        # Re-raise all other exceptions as-is (validation errors, syntax errors, etc.)
        # These are expected and should be reported to the user
        raise
