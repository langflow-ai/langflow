"""Isolation for code validation and execution.

This module provides isolated import and execution environments to ensure
user-provided code executes in an isolated namespace without access to
dangerous system modules or builtins.

SECURITY STATUS:
- ✅ Module-level imports ARE blocked (e.g., `import subprocess` at top of file)
- ✅ Class/function definitions execute in isolation
- ❌ Runtime method imports are NOT blocked (e.g., `import subprocess` inside `build()` method)

TODO: Block runtime imports in component methods
When a component method executes `import subprocess` at runtime, it bypasses isolation
because methods execute as normal Python code. See RUNTIME_IMPORT_ISOLATION_PLAN.md for
implementation plan.

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
    Set LANGFLOW_ISOLATION_SECURITY_LEVEL to one of: "moderate", "strict", "disabled"
    Default: "moderate"
"""

from lfx.custom.isolation.config import SecurityLevel, SecurityViolationError
from lfx.custom.isolation.execution import execute_in_isolated_env
from lfx.custom.isolation.isolation import create_isolated_builtins, create_isolated_import
from lfx.custom.isolation.transformer import DunderAccessTransformer

__all__ = [
    "DunderAccessTransformer",
    "SecurityLevel",
    "SecurityViolationError",
    "create_isolated_builtins",
    "create_isolated_import",
    "execute_in_isolated_env",
]
